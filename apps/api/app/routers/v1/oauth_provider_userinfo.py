"""GET /oauth/userinfo, POST /oauth/introspect, POST /oauth/revoke and the OIDC end-session endpoint (GET/POST /logout).

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import json
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sso_cookie import SSO_COOKIE_NAME, clear_sso_cookie, revoke_sso_cookie_session
from app.core.database import get_db
from app.core.protected_resources import PROTECTED_RESOURCES
from app.core.redis import ResilientRedisClient
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.core.url_security import validate_post_logout_redirect_uri
from app.models import OAuthClient, User
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_resource_tokens import _oauth_token_error, _pinned_cimd_client_id
from app.routers.v1.oauth_provider_schemas import UserInfoResponse
from app.routers.v1.oauth_provider_shared import logout_router, router
from app.services import resource_tokens, token_revocation
from app.services.client_id_metadata import is_url_client_id
from app.services.spanish_formality import stored_formality


@router.get("/userinfo", response_model=UserInfoResponse)
async def userinfo(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
):
    """
    OpenID Connect UserInfo Endpoint.

    Returns claims about the authenticated user.
    Requires Bearer token in Authorization header.
    """
    # Get access token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]

    # Verify token
    try:
        payload = await _oauth_provider_shared._verify_oauth_token(token, token_type="access", db=db)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # A token revoked through POST /oauth/revoke is refused like an expired
    # one. Strict read: 503 when Redis cannot answer.
    if not payload or await token_revocation.is_revoked(redis, payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Build response based on scope
    scope = payload.get("scope", "")
    response = UserInfoResponse(sub=str(user.id))

    if "email" in scope or "openid" in scope:
        response.email = user.email
        response.email_verified = getattr(user, "email_verified", True)

    if "profile" in scope or "openid" in scope:
        response.name = getattr(user, "name", None)
        response.given_name = user.first_name or None
        response.family_name = user.last_name or None
        if not response.name and (response.given_name or response.family_name):
            response.name = " ".join(
                part for part in (response.given_name, response.family_name) if part
            )

        response.picture = user.avatar_url or user.profile_image_url or None
        if hasattr(user, "updated_at") and user.updated_at:
            response.updated_at = int(user.updated_at.timestamp())
        # Read live from the row, so a change shows here before the next refresh.
        response.spanish_formality = stored_formality(user)

    return response


@router.post("/introspect")
async def introspect(
    request: Request,
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
):
    """
    OAuth 2.0 Token Introspection Endpoint (RFC 7662).

    Allows resource servers to query token validity. A token revoked through
    `POST /oauth/revoke` is reported `{"active": false}`. The revocation read
    is strict: when Redis cannot answer, this answers 503 + Retry-After rather
    than calling a possibly revoked token active.
    """
    # Authenticate client (required for introspection)
    if not client_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            import base64

            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                client_id, client_secret = decoded.split(":", 1)
            except Exception:
                pass  # Intentionally ignoring - Basic auth decode failure handled by checking client_id below

    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client authentication required",
        )

    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    if client.is_confidential and not client.verify_secret(client_secret or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    # Try to verify the token
    try:
        # Try as access token first
        token_type = token_type_hint or "access"
        payload = await _oauth_provider_shared._verify_oauth_token(
            token,
            token_type=token_type,
            db=db,
            expected_client=client,
        )
        if not payload:
            return {"active": False}
        if await token_revocation.is_revoked(redis, payload, token_type):
            return {"active": False}

        return {
            "active": True,
            "sub": payload.get("sub"),
            "client_id": payload.get("client_id"),
            "scope": payload.get("scope"),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
            "token_type": token_type,
        }
    except RedisUnavailableError:
        raise  # 503 + Retry-After: revocation status unknown
    except Exception:
        # Token is invalid or expired
        return {"active": False}


async def _authenticate_revoking_client(
    request: Request,
    client_id: Optional[str],
    client_secret: Optional[str],
    db: AsyncSession,
) -> OAuthClient:
    """Client authentication for `POST /oauth/revoke` (RFC 7009 §2.1).

    The same rules as the token endpoint: credentials by HTTP Basic or form
    fields; the client must exist and be active; a confidential client must
    present its secret. A public client identifies itself by `client_id`.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        import base64

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_client: Invalid Basic auth",
            )

    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client: client authentication required",
        )

    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    if client.is_confidential and not client.verify_secret(client_secret or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )
    return client


async def _revoke_protected_resource_token(
    *,
    request: Request,
    token: str,
    client_id: Optional[str],
    client_secret: Optional[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
):
    """RFC 7009 for protected-resource tokens (see `revoke`)."""
    if is_url_client_id(client_id):
        pinned = _pinned_cimd_client_id(client_id)
        if pinned is None or client_secret:
            return _oauth_token_error("invalid_client", "client authentication failed", 401)
        caller = pinned
    else:
        caller = (
            await _authenticate_revoking_client(request, client_id, client_secret, db)
        ).client_id

    claims = resource_tokens.verify_refresh_token(token)
    if claims is not None and claims.get("client_id") == caller:
        resource = PROTECTED_RESOURCES.get(claims["resource"])
        await token_revocation.revoke_family(
            redis,
            claims["family"],
            ttl=(
                resource.refresh_token_idle_seconds
                if resource
                else token_revocation.refresh_token_ttl()
            ),
            reason="oauth_revoke",
            strict=True,
        )
        _oauth_provider_shared.logger.info("OAuth token revoked", client_id=caller, token_type="resource_refresh")
    # 200 whether or not anything was revoked (RFC 7009 §2.2).
    return {"message": "Token revoked"}


async def _verified_token_of_client(
    token: str, token_type: str, client: OAuthClient, db: AsyncSession
) -> Optional[dict[str, Any]]:
    """The token's claims when Janua minted it for `client` and it is unexpired."""
    try:
        payload = await _oauth_provider_shared._verify_oauth_token(
            token, token_type=token_type, db=db, expected_client=client
        )
    except Exception:
        return None
    if not payload or payload.get("client_id") != client.client_id:
        # Unknown, invalid, expired, or issued to another client (or a Janua
        # session token, which belongs to no client): nothing to revoke here.
        return None
    return payload


@router.post("/revoke")
async def revoke(
    request: Request,
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
):
    """
    OAuth 2.0 Token Revocation Endpoint (RFC 7009).

    - The client authenticates as at the token endpoint (401 `invalid_client`
      otherwise).
    - `token_type_hint` (`access_token` / `refresh_token`) sets which kind is
      tried first; it is optional and a wrong hint still works (§2.1).
    - A refresh token revokes its whole rotation family: the refresh grant
      refuses it and every token minted from it later (§2.1).
    - An access token is blacklisted by `jti` until it expires: `/userinfo`
      and `/introspect` refuse it. Relying parties that verify tokens
      offline against the JWKS cannot see a revocation; that is what the
      short access-token lifetime and introspection are for.
    - An unknown, invalid or expired token, or one issued to another client,
      changes nothing and still answers 200 (§2.2): the answer never tells a
      client whether a token exists.
    - Fails closed: when Redis cannot store the revocation the answer is 503 +
      Retry-After, never a 200 for a revocation that did not happen.
    - Protected resources: an https `client_id` (CIMD, public: no secret) or
      a resource refresh token is handled by
      `_revoke_protected_resource_token`; a resource refresh token revokes its
      family. Resource access tokens are verified offline by the resource and
      expire within minutes, so revoking one changes nothing (200).
    """
    if is_url_client_id(client_id) or resource_tokens.looks_like_resource_refresh_token(token):
        return await _revoke_protected_resource_token(
            request=request,
            token=token,
            client_id=client_id,
            client_secret=client_secret,
            db=db,
            redis=redis,
        )

    client = await _authenticate_revoking_client(request, client_id, client_secret, db)

    order = ["refresh", "access"] if token_type_hint == "refresh_token" else ["access", "refresh"]
    for token_type in order:
        payload = await _verified_token_of_client(token, token_type, client, db)
        if payload is None:
            continue
        if token_type == "refresh":
            await token_revocation.revoke_family(
                redis, payload.get("family"), reason="oauth_revoke", strict=True
            )
            await token_revocation.revoke_jti(
                redis,
                payload.get("jti"),
                token_revocation.seconds_until(
                    payload.get("exp"), token_revocation.refresh_token_ttl()
                ),
                reason="oauth_revoke",
                strict=True,
            )
        else:
            await token_revocation.revoke_jti(
                redis,
                payload.get("jti"),
                token_revocation.seconds_until(
                    payload.get("exp"), token_revocation.access_token_ttl()
                ),
                reason="oauth_revoke",
                strict=True,
            )
        _oauth_provider_shared.logger.info(
            "OAuth token revoked",
            client_id=client.client_id,
            token_type=token_type,
        )
        break

    # 200 whether or not anything was revoked (RFC 7009 §2.2).
    return {"message": "Token revoked"}


def _clear_janua_session_cookies(response: RedirectResponse) -> None:
    """Clear Janua browser session cookies on logout.

    `janua_sso` is deleted through its own helper because it is set with an
    explicit `Path=/` — a deletion that differs on Domain *or* Path addresses a
    different cookie and leaves the live one in the browser.
    """
    delete_kwargs: dict = {}
    if _oauth_provider_shared.settings.COOKIE_DOMAIN:
        delete_kwargs["domain"] = _oauth_provider_shared.settings.COOKIE_DOMAIN
    for cookie_name in (
        "janua_access_token",
        "janua_refresh_token",
        "access_token",
        "refresh_token",
    ):
        response.delete_cookie(cookie_name, **delete_kwargs)
    clear_sso_cookie(response)


async def _perform_oidc_end_session(
    client_id: str,
    post_logout_redirect_uri: str,
    state: Optional[str],
    db: AsyncSession,
    request: Optional[Request],
) -> RedirectResponse:
    """Shared body for the GET and POST forms of RP-Initiated Logout.

    Clears Janua session cookies, revokes the `janua_sso` row, and 302-redirects
    to an allowlisted `post_logout_redirect_uri`. Both the GET route (used by a
    top-level browser navigation) and the POST route (used by a form submission)
    call this so the two verbs cannot drift apart in their security checks.
    """
    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_client",
        )

    allowed_uris = client.redirect_uris or []
    if isinstance(allowed_uris, str):
        try:
            allowed_uris = json.loads(allowed_uris)
        except json.JSONDecodeError:
            allowed_uris = []

    # SECURITY (CWE-601): the same open-redirect discipline the authorize
    # endpoint documents — an unlisted post_logout_redirect_uri is refused, never
    # redirected to.
    if not validate_post_logout_redirect_uri(post_logout_redirect_uri, allowed_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: post_logout_redirect_uri not registered for client",
        )

    redirect_url = post_logout_redirect_uri
    if state:
        separator = "&" if "?" in redirect_url else "?"
        redirect_url = f"{redirect_url}{separator}{urlencode({'state': state})}"

    # Revoke before clearing: the cookie is the only handle we have on the row.
    # `request` is optional so the existing direct callers and tests, which invoke
    # the wrappers as plain coroutines with keyword args, keep working.
    try:
        if request is not None and await revoke_sso_cookie_session(
            request.cookies.get(SSO_COOKIE_NAME), db
        ):
            await db.commit()
    except Exception:
        _oauth_provider_shared.logger.warning("Failed to revoke janua_sso session on end_session", exc_info=True)

    response = RedirectResponse(url=redirect_url, status_code=302)
    _clear_janua_session_cookies(response)
    return response


@logout_router.get("/logout")
async def oidc_end_session(
    client_id: str = Query(..., description="OAuth client ID"),
    post_logout_redirect_uri: str = Query(
        ..., description="URI to redirect after logout (must match client registration)"
    ),
    state: Optional[str] = Query(None, description="Opaque state forwarded to redirect URI"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    OIDC RP-Initiated Logout endpoint (end_session_endpoint), GET form.

    Clears Janua session cookies and redirects to the registered post-logout URI.
    The GET form is what a top-level browser navigation uses — the only shape that
    reliably lands the `janua_sso` (Domain=.madfam.io) deletion on the browser,
    since an XHR from any single estate host cannot delete an estate-wide cookie.

    SSO (J5/R1): deleting `janua_sso` is the cosmetic half. The half that matters
    is revoking the `sessions` row it references — a copy of the cookie taken
    before logout must stop working, not merely disappear from this browser. The
    cookie's signature is verified before anything is revoked, so a forged value
    cannot end someone else's session.

    `request` is declared last and optional so FastAPI still injects it on the
    real route while the existing keyword-only callers keep working unchanged.
    """
    return await _perform_oidc_end_session(client_id, post_logout_redirect_uri, state, db, request)


@logout_router.post("/logout")
async def oidc_end_session_post(
    client_id: str = Form(..., description="OAuth client ID"),
    post_logout_redirect_uri: str = Form(
        ..., description="URI to redirect after logout (must match client registration)"
    ),
    state: Optional[str] = Form(None, description="Opaque state forwarded to redirect URI"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    OIDC RP-Initiated Logout endpoint (end_session_endpoint), POST form.

    OIDC RP-Initiated Logout 1.0 §2 permits either GET or POST at the
    end_session_endpoint; the POST form reads its parameters from an
    `application/x-www-form-urlencoded` body. Same allowlist validation, same
    cookie clearing, and same `sessions`-row revocation as the GET form — they
    share `_perform_oidc_end_session` so the two verbs cannot diverge on any
    security check.
    """
    return await _perform_oidc_end_session(client_id, post_logout_redirect_uri, state, db, request)
