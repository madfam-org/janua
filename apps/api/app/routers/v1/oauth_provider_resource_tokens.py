"""Token-endpoint client authentication and the protected-resource (MCP connector) code exchange and refresh.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import has_mfa_assurance
from app.core.protected_resources import (
    OFFLINE_ACCESS_SCOPE,
    PROTECTED_RESOURCES,
    ProtectedResource,
    all_cimd_client_ids,
)
from app.core.redis import ResilientRedisClient
from app.models import OAuthClient, User, UserStatus
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_resources import (
    _CODE_VERIFIER,
    _TOKEN_RESPONSE_HEADERS,
    _select_resource,
)
from app.routers.v1.oauth_provider_scopes import _client_grant_types
from app.routers.v1.oauth_provider_shared import _redacted
from app.services import resource_tokens, token_revocation
from app.services.client_id_metadata import client_id_host, is_url_client_id


@dataclass(frozen=True)
class _TokenClient:
    """An authenticated (or, for a public client, identified) token-endpoint client."""

    client_id: str
    kind: str  # "cimd" | "registered"
    grant_types: frozenset[str]
    cimd_host: Optional[str] = None
    db_client: Optional[OAuthClient] = None


def _oauth_token_error(
    error: str, description: str, status_code: int = 400, *, basic_auth: bool = False
) -> JSONResponse:
    """An RFC 6749 §5.2 error: `{"error", "error_description"}`, never cached.

    Clients act on the `error` code itself — Claude, for one, starts a new
    authorization only when a refresh answers `invalid_grant` — so this path
    never uses Janua's general error envelope.
    """
    headers = dict(_TOKEN_RESPONSE_HEADERS)
    if status_code == 401 and basic_auth:
        headers["WWW-Authenticate"] = 'Basic realm="janua"'
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
        headers=headers,
    )


def _pinned_cimd_client_id(client_id: Optional[str]) -> Optional[str]:
    """The pinned CIMD client_id (a registry string) equal to `client_id`, or None."""
    for pinned in sorted(all_cimd_client_ids()):
        if pinned == client_id:
            return pinned
    return None


def _cimd_client_allowed(resource: ProtectedResource, client: "_TokenClient") -> bool:
    policy = resource.client_policy
    return (
        client.cimd_host in policy.cimd_hosts
        and policy.pinned_client_id(client.client_id) is not None
    )


def _token_client_from_row(client: OAuthClient) -> _TokenClient:
    return _TokenClient(
        client_id=client.client_id,
        kind="registered",
        grant_types=frozenset(_client_grant_types(client)),
        db_client=client,
    )


async def _authenticate_resource_token_client(
    client_id: Optional[str],
    client_secret: Optional[str],
    used_basic_auth: bool,
    db: AsyncSession,
) -> tuple[Optional[_TokenClient], Optional[JSONResponse]]:
    """(client, None) or (None, the RFC 6749 error response)."""
    if not client_id:
        return None, _oauth_token_error("invalid_request", "client_id is required")
    if is_url_client_id(client_id):
        pinned = _pinned_cimd_client_id(client_id)
        if pinned is None:
            return None, _oauth_token_error(
                "invalid_client", "this client is not allowed at this server", 401
            )
        if client_secret or used_basic_auth:
            # A CIMD client is public here (its document says or supports
            # token_endpoint_auth_method "none"): PKCE only, never a secret.
            return None, _oauth_token_error(
                "invalid_client",
                "this client authenticates with PKCE only",
                401,
                basic_auth=used_basic_auth,
            )
        return (
            _TokenClient(
                client_id=pinned,
                kind="cimd",
                grant_types=frozenset({"authorization_code", "refresh_token"}),
                cimd_host=client_id_host(pinned),
            ),
            None,
        )

    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client or not client.is_active:
        return None, _oauth_token_error(
            "invalid_client", "unknown or disabled client", 401, basic_auth=used_basic_auth
        )
    if client.is_confidential and (not client_secret or not client.verify_secret(client_secret)):
        return None, _oauth_token_error(
            "invalid_client", "client authentication failed", 401, basic_auth=used_basic_auth
        )
    return _token_client_from_row(client), None


async def _active_user(user_id: Any, db: AsyncSession) -> Optional[User]:
    """The ACTIVE user with this id, else None.

    Only a malformed id is "no user"; a database failure propagates (a 5xx the
    client retries), never `invalid_grant`, which would make Claude discard a
    good refresh token.
    """
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (TypeError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None or getattr(user, "status", None) != UserStatus.ACTIVE:
        return None
    if getattr(user, "is_active", True) is False:
        return None
    return user


def _resource_token_response(
    *,
    resource: ProtectedResource,
    subject: str,
    client: _TokenClient,
    access_scopes: list[str],
    refresh_token: Optional[str],
    grant_type: str,
    authentication_assurance: Optional[dict] = None,
) -> JSONResponse:
    access = resource_tokens.mint_access_token(
        resource=resource,
        subject=subject,
        client_id=client.client_id,
        scopes=access_scopes,
        authentication_assurance=authentication_assurance,
    )
    response_scope = access_scopes + ([OFFLINE_ACCESS_SCOPE] if refresh_token else [])
    body: dict[str, Any] = {
        "access_token": access.token,
        "token_type": "Bearer",
        "expires_in": access.expires_in,
        "scope": " ".join(response_scope),
    }
    if refresh_token:
        body["refresh_token"] = refresh_token
    _oauth_provider_shared.logger.info(
        "oauth.resource_token.issued",
        grant_type=grant_type,
        client_id=client.client_id,
        resource=resource.resource,
        scopes=" ".join(access_scopes),
        refresh_token_issued=bool(refresh_token),
        user=_redacted(subject),
    )
    return JSONResponse(content=body, headers=dict(_TOKEN_RESPONSE_HEADERS))


def _requested_resource_mismatch(
    resource_values: list[str], bound: ProtectedResource
) -> Optional[JSONResponse]:
    """`invalid_target` unless the request names nothing, or exactly `bound`."""
    if not resource_values:
        return None
    requested, error = _select_resource(resource_values)
    if requested is None:
        return _oauth_token_error("invalid_target", error or "unknown resource")
    if requested.resource != bound.resource:
        return _oauth_token_error(
            "invalid_target", "the resource does not match the one this grant was issued for"
        )
    return None


async def _exchange_resource_code(
    *,
    code: str,
    code_data: dict,
    redirect_uri: Optional[str],
    code_verifier: Optional[str],
    client: _TokenClient,
    resource_values: list[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> JSONResponse:
    """authorization_code for a code bound to a protected resource."""
    if code_data.get("client_id") != client.client_id:
        _oauth_provider_shared.logger.warning("token.rejected", reason="client_mismatch", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "the code was not issued to this client")
    resource = PROTECTED_RESOURCES.get(code_data.get("resource") or "")
    if resource is None:
        return _oauth_token_error("invalid_grant", "the code's resource is no longer available")
    mismatch = _requested_resource_mismatch(resource_values, resource)
    if mismatch is not None:
        return mismatch
    if client.kind == "cimd" and not _cimd_client_allowed(resource, client):
        return _oauth_token_error(
            "unauthorized_client", "this client may not obtain tokens for this resource"
        )
    if "authorization_code" not in client.grant_types:
        return _oauth_token_error("unauthorized_client", "grant type not allowed for this client")
    if redirect_uri is not None and redirect_uri != code_data.get("redirect_uri"):
        _oauth_provider_shared.logger.warning("token.rejected", reason="redirect_uri_mismatch", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "redirect_uri does not match the authorization")
    challenge = code_data.get("code_challenge")
    if not challenge or code_data.get("code_challenge_method") != "S256":
        return _oauth_token_error("invalid_grant", "the code was not issued with PKCE S256")
    if not code_verifier:
        return _oauth_token_error("invalid_request", "code_verifier is required")
    if not _CODE_VERIFIER.match(code_verifier) or not _oauth_provider_shared._verify_pkce(
        code_verifier, challenge, "S256"
    ):
        _oauth_provider_shared.logger.warning("token.rejected", reason="pkce_mismatch", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "PKCE verification failed")

    # Single use: of two concurrent redemptions exactly one deletes the code.
    if not await _oauth_provider_shared._delete_auth_code(code, redis):
        _oauth_provider_shared.logger.warning("token.rejected", reason="code_already_redeemed", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "the code is invalid or was already used")

    user = await _active_user(code_data.get("user_id"), db)
    if user is None:
        return _oauth_token_error("invalid_grant", "the account is not active")

    from app.auth.authentication_assurance import validate_live_assurance
    from app.auth.tenant_login_context import require_client_membership

    try:
        if client.db_client is not None:
            await require_client_membership(db, user, client.db_client)
        authentication_assurance = await validate_live_assurance(
            db, user, code_data.get("authentication_assurance", {})
        )
    except HTTPException as exc:
        if exc.status_code not in (401, 403):
            raise
        return _oauth_token_error("invalid_grant", "the authentication is no longer active")
    organization_id = getattr(client.db_client, "organization_id", None)
    if await _oauth_provider_shared.user_requires_mfa(db, user, organization_id) and not has_mfa_assurance(
        authentication_assurance
    ):
        return _oauth_token_error("invalid_grant", "multi-factor authentication is required")

    granted = (code_data.get("scope") or "").split()
    access_scopes = [scope for scope in granted if scope in resource.scope_names]
    if not access_scopes:
        return _oauth_token_error("invalid_scope", "no scope of this resource was granted")

    refresh_token = None
    if OFFLINE_ACCESS_SCOPE in granted and "refresh_token" in client.grant_types:
        refresh_token = resource_tokens.mint_refresh_token(
            resource=resource,
            subject=str(user.id),
            client_id=client.client_id,
            scope=" ".join(access_scopes + [OFFLINE_ACCESS_SCOPE]),
            authentication_assurance=authentication_assurance,
        )

    if client.db_client is not None:
        client.db_client.last_used_at = datetime.utcnow()
        try:
            await db.commit()
        except Exception as e:
            _oauth_provider_shared.logger.warning("Failed to update client last_used_at", error=str(e))

    return _resource_token_response(
        resource=resource,
        subject=str(user.id),
        client=client,
        access_scopes=access_scopes,
        refresh_token=refresh_token,
        grant_type="authorization_code",
        authentication_assurance=authentication_assurance,
    )


async def _refresh_resource_token(
    *,
    refresh_token: Optional[str],
    scope: Optional[str],
    client: _TokenClient,
    resource_values: list[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> JSONResponse:
    """refresh_token for a resource refresh token: rotate, detect reuse, never upscope."""
    if not refresh_token:
        return _oauth_token_error("invalid_request", "refresh_token is required")
    claims = resource_tokens.verify_refresh_token(refresh_token)
    if claims is None:
        return _oauth_token_error("invalid_grant", "the refresh token is invalid or expired")
    if claims["client_id"] != client.client_id:
        _oauth_provider_shared.logger.warning(
            "token.rejected", reason="refresh_client_mismatch", client_id=client.client_id
        )
        return _oauth_token_error(
            "invalid_grant", "the refresh token was not issued to this client"
        )
    resource = PROTECTED_RESOURCES.get(claims["resource"])
    if resource is None:
        return _oauth_token_error("invalid_grant", "the token's resource is no longer available")
    mismatch = _requested_resource_mismatch(resource_values, resource)
    if mismatch is not None:
        return mismatch
    if client.kind == "cimd" and not _cimd_client_allowed(resource, client):
        return _oauth_token_error("invalid_grant", "this client may no longer use this resource")
    if "refresh_token" not in client.grant_types:
        return _oauth_token_error("unauthorized_client", "grant type not allowed for this client")

    # Revoked through POST /oauth/revoke, or a family closed by reuse? Strict
    # read: 503 when Redis cannot answer, never "not revoked".
    if await token_revocation.is_revoked(redis, claims, "refresh"):
        return _oauth_token_error("invalid_grant", "the refresh token was revoked")

    original = claims["scope"].split()
    current_scopes = [name for name in original if name in resource.scope_names]
    if scope is not None and scope.strip():
        requested = scope.split()
        if not set(requested) <= set(original):
            return _oauth_token_error("invalid_scope", "a refresh cannot add scopes")
        access_scopes = [name for name in current_scopes if name in requested]
    else:
        access_scopes = current_scopes
    if not access_scopes:
        return _oauth_token_error("invalid_scope", "no scope of this resource remains")

    user = await _active_user(claims["sub"], db)
    if user is None:
        return _oauth_token_error("invalid_grant", "the account is not active")

    from app.auth.authentication_assurance import validate_live_assurance
    from app.auth.tenant_login_context import require_client_membership

    try:
        if client.db_client is not None:
            await require_client_membership(db, user, client.db_client)
        authentication_assurance = await validate_live_assurance(db, user, claims)
    except HTTPException as exc:
        if exc.status_code not in (401, 403):
            raise
        return _oauth_token_error("invalid_grant", "the authentication is no longer active")
    organization_id = getattr(client.db_client, "organization_id", None)
    if await _oauth_provider_shared.user_requires_mfa(db, user, organization_id) and not has_mfa_assurance(
        authentication_assurance
    ):
        return _oauth_token_error("invalid_grant", "multi-factor authentication is required")

    # Single use. The first redemption wins the SET NX; any later one is reuse
    # of a rotated token, so the whole family is revoked.
    first_use = await redis.strict_set_nx(
        f"{resource_tokens.USED_REFRESH_KEY_PREFIX}{claims['jti']}",
        "1",
        ex=token_revocation.seconds_until(claims.get("exp"), resource.refresh_token_idle_seconds),
    )
    if not first_use:
        await token_revocation.revoke_family(
            redis,
            claims["family"],
            ttl=resource.refresh_token_idle_seconds,
            reason="resource_refresh_token_reuse",
            strict=True,
        )
        _oauth_provider_shared.logger.warning(
            "oauth.resource_refresh.reuse_detected",
            client_id=client.client_id,
            resource=resource.resource,
            user=_redacted(claims["sub"]),
        )
        return _oauth_token_error("invalid_grant", "the refresh token was already used")

    # The new refresh token keeps the original scope (RFC 6749 §6) and family.
    new_refresh_token = resource_tokens.mint_refresh_token(
        resource=resource,
        subject=str(user.id),
        client_id=client.client_id,
        scope=claims["scope"],
        family=claims["family"],
        family_iat=claims["family_iat"],
        authentication_assurance=authentication_assurance,
    )
    return _resource_token_response(
        resource=resource,
        subject=str(user.id),
        client=client,
        access_scopes=access_scopes,
        refresh_token=new_refresh_token,
        grant_type="refresh_token",
        authentication_assurance=authentication_assurance,
    )


async def _token_for_protected_resource(
    *,
    grant_type: str,
    code: Optional[str],
    redirect_uri: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    refresh_token: Optional[str],
    code_verifier: Optional[str],
    scope: Optional[str],
    resource_values: list[str],
    used_basic_auth: bool,
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> JSONResponse:
    client, error = await _authenticate_resource_token_client(
        client_id, client_secret, used_basic_auth, db
    )
    if client is None:
        return error or _oauth_token_error("invalid_client", "client authentication failed", 401)

    if grant_type == "authorization_code":
        if not code:
            return _oauth_token_error("invalid_request", "code is required")
        code_data = await _oauth_provider_shared._get_auth_code(code, redis)
        if not code_data:
            return _oauth_token_error("invalid_grant", "the code is invalid or expired")
        if not code_data.get("resource"):
            # RFC 8707: a grant made without a resource cannot become one.
            return _oauth_token_error(
                "invalid_target", "this code was not issued for a protected resource"
            )
        return await _exchange_resource_code(
            code=code,
            code_data=code_data,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            client=client,
            resource_values=resource_values,
            db=db,
            redis=redis,
        )
    if grant_type == "refresh_token":
        if refresh_token and not resource_tokens.looks_like_resource_refresh_token(refresh_token):
            # Garbage, or a refresh token of the default flow (which names no
            # resource and can never become a resource token): either way the
            # grant is unusable here, and `invalid_grant` is what tells a
            # client like Claude to authorize again.
            return _oauth_token_error(
                "invalid_grant", "the refresh token is invalid for this resource"
            )
        return await _refresh_resource_token(
            refresh_token=refresh_token,
            scope=scope,
            client=client,
            resource_values=resource_values,
            db=db,
            redis=redis,
        )
    if grant_type == "client_credentials":
        return _oauth_token_error(
            "invalid_target", "client_credentials tokens are not issued for protected resources"
        )
    return _oauth_token_error("unsupported_grant_type", f"unsupported grant type: {grant_type}")
