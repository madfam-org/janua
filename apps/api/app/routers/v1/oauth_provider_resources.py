"""Protected-resource (MCP connector) authorization, its consent, and GET /oauth/authorize/resume.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import html
import json
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import has_mfa_assurance
from app.auth.authorize_resume import authorize_query
from app.auth.login_method import normalize_login_method
from app.auth.resource_consent_page import render_resource_consent_page
from app.core.protected_resources import (
    OFFLINE_ACCESS_SCOPE,
    PROTECTED_RESOURCES,
    InvalidResourceIndicator,
    ProtectedResource,
    all_cimd_client_ids,
    all_cimd_hosts,
    canonical_resource,
    granted_scopes,
    is_loopback_redirect,
    redirect_display_host,
    redirect_uri_matches,
)
from app.core.redis import ResilientRedisClient
from app.models import OAuthClient, User
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_clients import _redirect_with_oauth_error
from app.routers.v1.oauth_provider_scopes import _client_grant_types
from app.routers.v1.oauth_provider_shared import (
    AUTH_CODE_TTL,
    _build_safe_callback_url,
    _redacted,
    router,
)
from app.services.client_id_metadata import (
    ClientMetadataError,
    is_url_client_id,
    resolve_client_metadata,
)

#: Pre-login state for a resource-bound request outlives the 15-minute magic
#: link that may resume it (the default path keeps 10 minutes).
RESOURCE_PRE_LOGIN_TTL = 20 * 60


#: How long the stored consent request waits for the person's answer.
RESOURCE_AUTH_REQUEST_TTL = 600


#: RFC 7636 §4.2: an S256 challenge is BASE64URL(SHA256(verifier)), 43 chars.
_S256_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")


#: RFC 7636 §4.1: the verifier's alphabet and length.
_CODE_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


_TOKEN_RESPONSE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}


_ERROR_PAGE_MESSAGES = {
    "invalid_client": "La aplicación que pidió el acceso no está autorizada o no se pudo verificar.",
    "invalid_request": "La solicitud de acceso no es válida.",
    "invalid_target": "El recurso solicitado no existe o no está disponible.",
    "unauthorized_client": "Esta aplicación no tiene permiso para pedir acceso a este recurso.",
    "server_error": "No se pudo completar la autorización.",
}


@dataclass(frozen=True)
class _ResourceClient:
    """The client of a resource-bound request, from its CIMD document or its row."""

    client_id: str
    kind: str  # "cimd" | "registered"
    client_name: Optional[str]
    redirect_uris: tuple[str, ...]
    grant_types: frozenset[str]
    cimd_host: Optional[str] = None
    db_client: Optional[OAuthClient] = None

    def app_host(self, redirect_uri: str) -> str:
        """Who is asking, as a host: the client_id host, else the redirect host."""
        return self.cimd_host or redirect_display_host(redirect_uri)


def _resource_values(value: Any) -> list[str]:
    """The `resource` values of a request (RFC 8707 allows repeating it).

    Anything that is not a string or a list of strings — notably FastAPI's own
    `Query(None)` / `Form(None)` default when a route function is called
    directly — means "no resource".
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]
    return []


def _select_resource(values: list[str]) -> tuple[Optional[ProtectedResource], Optional[str]]:
    """(the registered resource, None) or (None, why it is `invalid_target`)."""
    if not values:
        return None, "the resource parameter is required for this client"
    canonical: set[str] = set()
    for value in values:
        try:
            canonical.add(canonical_resource(value))
        except InvalidResourceIndicator:
            return None, "the resource must be an absolute URI without a fragment"
    if len(canonical) != 1:
        return None, "exactly one resource per request is supported"
    resource = PROTECTED_RESOURCES.get(next(iter(canonical)))
    if resource is None:
        return None, "unknown resource"
    return resource, None


def _registered_redirect_uris(client: OAuthClient) -> tuple[str, ...]:
    uris = client.redirect_uris or []
    if isinstance(uris, str):
        # Some rows store the array double-encoded (see auth.py's resolvers).
        try:
            uris = json.loads(uris)
        except json.JSONDecodeError:
            uris = []
    if not isinstance(uris, list):
        return ()
    return tuple(uri for uri in uris if isinstance(uri, str))


async def _resolve_resource_client(
    client_id: str, resource: Optional[ProtectedResource], db: AsyncSession
) -> tuple[Optional[_ResourceClient], Optional[str]]:
    """(the client behind `client_id`, None), or (None, why it was refused).

    The reason is for the log only; the person sees a fixed message.

    A URL client_id is fetched as a Client ID Metadata Document only when it is
    one of the resource's pinned client_id URLs (on its host allowlist). With no
    usable resource the union of every resource's pins decides, so the
    `invalid_target` error can still be delivered to a verified redirect URI.
    """
    if is_url_client_id(client_id):
        if resource is not None:
            hosts = resource.client_policy.cimd_hosts
            pinned = resource.client_policy.cimd_client_ids
        else:
            hosts, pinned = all_cimd_hosts(), all_cimd_client_ids()
        try:
            metadata = await resolve_client_metadata(
                client_id, allowed_hosts=hosts, pinned_client_ids=pinned
            )
        except ClientMetadataError as exc:
            return None, exc.description
        return (
            _ResourceClient(
                client_id=metadata.client_id,
                kind="cimd",
                client_name=metadata.client_name,
                redirect_uris=metadata.redirect_uris,
                grant_types=frozenset(metadata.grant_types),
                cimd_host=metadata.host,
            ),
            None,
        )
    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client or not client.is_active:
        return None, "unknown or disabled client"
    return (
        _ResourceClient(
            client_id=client_id,
            kind="registered",
            client_name=client.name,
            redirect_uris=_registered_redirect_uris(client),
            grant_types=frozenset(_client_grant_types(client)),
            db_client=client,
        ),
        None,
    )


def _resource_policy_error(
    resource: ProtectedResource, client: _ResourceClient, redirect_uri: str
) -> Optional[str]:
    """Why `client` may not obtain tokens for `resource` via `redirect_uri`, or None."""
    policy = resource.client_policy
    if client.kind == "cimd":
        if (
            client.cimd_host not in policy.cimd_hosts
            or policy.pinned_client_id(client.client_id) is None
        ):
            return "this client is not allowed to request this resource"
    elif not client.redirect_uris or not all(
        policy.allows_redirect(uri) for uri in client.redirect_uris
    ):
        return "the client's registered redirect URIs are outside this resource's policy"
    if not policy.allows_redirect(redirect_uri):
        return "this redirect URI is not allowed for this resource"
    if "authorization_code" not in client.grant_types:
        return "this client may not use the authorization_code grant"
    return None


def _authorization_error_page(error: str, description: str) -> HTMLResponse:
    """A refusal shown to the person, never redirected (untrusted redirect URI)."""
    message = _ERROR_PAGE_MESSAGES.get(error, _ERROR_PAGE_MESSAGES["server_error"])
    content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No se pudo autorizar - Janua</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #f4f1ec; color: #1f2933; display: flex; align-items: center;
               justify-content: center; min-height: 100vh; margin: 0; padding: 16px; }}
        main {{ background: #fff; border-radius: 14px; padding: 28px; max-width: 440px;
               box-shadow: 0 12px 40px rgba(31, 41, 51, 0.16); }}
        h1 {{ font-size: 20px; margin: 0 0 12px; }}
        p {{ line-height: 1.5; }}
        code {{ font-size: 12px; color: #52606d; word-break: break-word; }}
    </style>
</head>
<body>
    <main>
        <h1>No se pudo autorizar la conexión</h1>
        <p>{html.escape(message)} Vuelve a la aplicación e inténtalo de nuevo.</p>
        <p><code>{html.escape(error)}: {html.escape(description)}</code></p>
    </main>
</body>
</html>
"""
    return HTMLResponse(content=content, status_code=400, headers={"Cache-Control": "no-store"})


def _login_redirect_for_resource(
    *,
    pre_login_id: str,
    client_id: str,
    app_name: str,
    login_method: Optional[str],
    mfa_required: bool = False,
) -> RedirectResponse:
    params = {"auth_request_id": pre_login_id, "client_id": client_id, "client_name": app_name}
    if login_method:
        params["login_method"] = login_method
    if mfa_required:
        params["mfa_required"] = "1"
    return RedirectResponse(url=f"/api/v1/auth/login?{urlencode(params)}", status_code=302)


async def _authorize_protected_resource(
    *,
    request: Request,
    current_user: Optional[User],
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: Optional[str],
    state: Optional[str],
    code_challenge: Optional[str],
    code_challenge_method: Optional[str],
    prompt: Optional[str],
    login_method: Optional[str],
    resource_values: list[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
):
    """GET /authorize for a protected resource (see the section comment above).

    `current_user` is who `authorize_get` resolved from the request
    (`get_user_from_cookie_or_header`, the one reader of the session cookies),
    or None.
    """
    resource, resource_error = _select_resource(resource_values)

    # 1. Who is asking, and may the answer go to `redirect_uri`? Until both are
    #    known nothing is redirected (RFC 6749 §4.1.2.1).
    client, refusal = await _resolve_resource_client(client_id, resource, db)
    if client is None:
        _oauth_provider_shared.logger.warning(
            "oauth.resource_authorize.refused",
            error="invalid_client",
            reason=refusal,
            client_kind="cimd" if is_url_client_id(client_id) else "registered",
        )
        return _authorization_error_page("invalid_client", "the client could not be verified")
    if not redirect_uri_matches(redirect_uri, client.redirect_uris):
        _oauth_provider_shared.logger.warning(
            "oauth.resource_authorize.refused",
            error="invalid_request",
            reason="redirect_uri_not_registered",
            client_id=client_id,
        )
        return _authorization_error_page(
            "invalid_request", "redirect_uri is not registered for this client"
        )

    def refuse(error: str, description: str) -> RedirectResponse:
        _oauth_provider_shared.logger.info(
            "oauth.resource_authorize.refused",
            error=error,
            reason=description,
            client_id=client_id,
        )
        return _redirect_with_oauth_error(
            redirect_uri,
            error=error,
            error_description=description,
            state=state,
            client_validated=True,
        )

    # 2. The request itself; errors now go back to the verified redirect URI.
    if resource is None:
        return refuse("invalid_target", resource_error or "unknown resource")
    if response_type != "code":
        return refuse("unsupported_response_type", "only response_type=code is supported")
    policy_error = _resource_policy_error(resource, client, redirect_uri)
    if policy_error:
        return refuse("unauthorized_client", policy_error)
    if not code_challenge:
        return refuse("invalid_request", "PKCE is required: send code_challenge")
    if code_challenge_method != "S256":
        return refuse("invalid_request", "code_challenge_method must be S256")
    if not _S256_CHALLENGE.match(code_challenge):
        return refuse("invalid_request", "code_challenge is not a valid S256 challenge")

    # An absent or empty `scope` asks for the resource's scopes (RFC 6749 §3.3
    # lets the server apply a default); `offline_access` must be asked for.
    requested = scope.split() if scope is not None and scope.strip() else None
    scopes, offline_access = granted_scopes(resource, requested)
    if not scopes:
        return refuse("invalid_scope", "no requested scope is available for this resource")
    if "refresh_token" not in client.grant_types:
        offline_access = False

    prompt_values = {value for value in (prompt or "").strip().lower().split() if value}
    force_login = "login" in prompt_values or "select_account" in prompt_values
    silent = "none" in prompt_values and not force_login

    app_host = client.app_host(redirect_uri)

    async def send_to_login(*, mfa_required: bool = False) -> RedirectResponse:
        pre_login_id = secrets.token_urlsafe(16)
        pre_login_data = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "resource": resource.resource,
            "login_method": normalize_login_method(login_method) or resource.preferred_login_method,
        }
        await redis.strict_set(
            f"oauth:pre_login:{pre_login_id}",
            json.dumps(pre_login_data),
            ex=RESOURCE_PRE_LOGIN_TTL,
        )
        return _login_redirect_for_resource(
            pre_login_id=pre_login_id,
            client_id=client_id,
            app_name=f"{resource.display_name} ({app_host})",
            login_method=pre_login_data["login_method"],
            mfa_required=mfa_required,
        )

    if not current_user or force_login:
        if silent:
            return refuse("login_required", "no active Janua session")
        return await send_to_login()

    # Same identity gates as the default path: verified email (after the
    # grace period) and, when enforced, a second factor.
    if _oauth_provider_shared.settings.REQUIRE_EMAIL_VERIFICATION and not getattr(current_user, "email_verified", False):
        created_at = getattr(current_user, "created_at", None)
        if created_at:
            grace = timedelta(hours=_oauth_provider_shared.settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
            if datetime.utcnow() >= created_at + grace:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required. Please verify your email before authorizing third-party applications.",
                )

    from app.auth.tenant_login_context import require_client_membership

    if client.db_client is not None:
        await require_client_membership(db, current_user, client.db_client)
    try:
        authentication_assurance = await _oauth_provider_shared.assurance_for_request(request, db, current_user)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        if silent:
            return refuse("interaction_required", "authentication must be renewed")
        return await send_to_login()
    organization_id = getattr(client.db_client, "organization_id", None)
    if await _oauth_provider_shared.user_requires_mfa(db, current_user, organization_id) and not has_mfa_assurance(
        authentication_assurance
    ):
        if silent:
            return refuse("interaction_required", "multi-factor authentication is required")
        return await send_to_login(mfa_required=True)

    # A silent request cannot bypass either MFA or the resource's consent.
    if silent:
        return refuse("consent_required", "consent is required for this resource")

    # 3. Consent, in Spanish, every time.
    csrf_token = await _oauth_provider_shared._generate_csrf_token(str(current_user.id), redis)
    granted = scopes + ([OFFLINE_ACCESS_SCOPE] if offline_access else [])
    auth_request_id = secrets.token_urlsafe(16)
    auth_request_data = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(granted),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "resource": resource.resource,
        "user_id": str(current_user.id),
        "authentication_assurance": authentication_assurance,
    }
    await redis.strict_set(
        f"oauth:auth_request:{auth_request_id}",
        json.dumps(auth_request_data),
        ex=RESOURCE_AUTH_REQUEST_TTL,
    )
    loopback = is_loopback_redirect(redirect_uri)
    page = render_resource_consent_page(
        resource=resource,
        # A registered client on a loopback redirect has no host worth naming.
        app_host=(
            app_host
            if client.kind == "cimd" or not loopback
            else "Una aplicación en esta computadora"
        ),
        client_name=client.client_name,
        redirect_host=redirect_display_host(redirect_uri),
        loopback=loopback,
        scopes=scopes,
        offline_access=offline_access,
        user_email=getattr(current_user, "email", "") or "",
        auth_request_id=auth_request_id,
        csrf_token=csrf_token,
    )
    return HTMLResponse(content=page, headers={"Cache-Control": "no-store"})


async def _complete_protected_resource_consent(
    *,
    request: Request,
    current_user: User,
    auth_request: dict,
    action: str,
    db: AsyncSession,
    redis: ResilientRedisClient,
):
    """POST /consent for a protected resource: re-verify, then code or access_denied."""
    resource = PROTECTED_RESOURCES.get(auth_request.get("resource") or "")
    redirect_uri = auth_request.get("redirect_uri") or ""
    state = auth_request.get("state")
    client_id = auth_request.get("client_id") or ""
    if resource is None:
        return _authorization_error_page("invalid_target", "the resource is no longer available")
    if auth_request.get("user_id") != str(current_user.id):
        return _authorization_error_page(
            "invalid_request", "the signed-in account changed; start the connection again"
        )
    # Defense in depth: the stored request was validated when the page was
    # rendered, but the registry or the client's document may have changed.
    client, refusal = await _resolve_resource_client(client_id, resource, db)
    if client is None:
        _oauth_provider_shared.logger.warning("oauth.resource_consent.refused", error="invalid_client", reason=refusal)
        return _authorization_error_page("invalid_client", "the client could not be verified")
    if not redirect_uri_matches(redirect_uri, client.redirect_uris) or _resource_policy_error(
        resource, client, redirect_uri
    ):
        return _authorization_error_page(
            "unauthorized_client", "the client or its redirect URI is no longer allowed"
        )

    if action != "allow":
        _oauth_provider_shared.logger.info(
            "oauth.resource_consent.denied",
            client_id=client_id,
            resource=resource.resource,
            user=_redacted(current_user.id),
        )
        return _redirect_with_oauth_error(
            redirect_uri,
            error="access_denied",
            error_description="the user denied the request",
            state=state,
            client_validated=True,
        )

    from app.auth.authentication_assurance import validate_live_assurance
    from app.auth.tenant_login_context import require_client_membership

    if client.db_client is not None:
        await require_client_membership(db, current_user, client.db_client)
    authentication_assurance = await _oauth_provider_shared.assurance_for_request(request, db, current_user)
    previous_assurance = await validate_live_assurance(
        db, current_user, auth_request.get("authentication_assurance", {})
    )
    if previous_assurance.get("sid") != authentication_assurance.get("sid"):
        raise HTTPException(428, "Authentication changed; start the connection again")
    organization_id = getattr(client.db_client, "organization_id", None)
    if await _oauth_provider_shared.user_requires_mfa(db, current_user, organization_id) and not has_mfa_assurance(
        authentication_assurance
    ):
        raise HTTPException(428, "Multi-factor authentication required")

    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "authentication_assurance": authentication_assurance,
        "redirect_uri": redirect_uri,
        "scope": auth_request.get("scope") or "",
        "resource": resource.resource,
        "nonce": None,
        "code_challenge": auth_request.get("code_challenge"),
        "code_challenge_method": "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _oauth_provider_shared._store_auth_code(auth_code, code_data, redis)

    if client.db_client is not None:
        try:
            client.db_client.last_used_at = datetime.utcnow()
            await db.commit()
        except Exception as e:
            _oauth_provider_shared.logger.warning("Failed to update client last_used_at", error=str(e))

    _oauth_provider_shared.logger.info(
        "oauth.resource_consent.granted",
        client_id=client_id,
        resource=resource.resource,
        scopes=code_data["scope"],
        user=_redacted(current_user.id),
    )
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state
    return RedirectResponse(
        url=_build_safe_callback_url(redirect_uri, callback_params, client_validated=True),
        status_code=302,
    )


@router.get("/authorize/resume")
async def authorize_resume(
    auth_request_id: str = Query(..., min_length=8, max_length=64),
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
):
    """Resume a protected-resource authorization after sign-in by email link.

    The emailed link's destination is stored in a 500-character column, and a
    full authorize URL for a Client ID Metadata Document client with a
    `resource` comes close to that. The link therefore carries only this short
    URL; the authorize parameters stay in the pre-login record, which for
    these requests outlives the link (RESOURCE_PRE_LOGIN_TTL).
    """
    stored = await redis.strict_get(f"oauth:pre_login:{auth_request_id}")
    params: Optional[dict] = None
    if stored:
        try:
            params = json.loads(stored)
        except (json.JSONDecodeError, TypeError):
            params = None
    if not isinstance(params, dict) or not params.get("resource"):
        return _authorization_error_page(
            "invalid_request", "this sign-in request expired; start the connection again"
        )
    return RedirectResponse(
        url=f"/api/v1/oauth/authorize?{urlencode(authorize_query(params))}", status_code=302
    )
