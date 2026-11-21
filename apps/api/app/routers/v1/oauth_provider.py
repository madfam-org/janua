"""
OAuth2 Provider Endpoints for Janua

This module implements the OAuth 2.0 Authorization Server endpoints that allow
external applications (like Enclii) to authenticate users via Janua.

Implements:
- Authorization Endpoint (GET/POST /oauth/authorize)
- Token Endpoint (POST /oauth/token)
- UserInfo Endpoint (GET /oauth/userinfo)

Based on RFC 6749 (OAuth 2.0) and OpenID Connect Core 1.0

Split on 2026-11-19 (the repository's 800-line pre-commit limit) into the
modules below. No behaviour change: `router` (prefix /oauth) and
`logout_router` are created in `oauth_provider_shared`, and the route modules,
imported here in the order their routes were declared, put every route on
them; `router.routes` and `logout_router.routes` are the same lists.

| Module | What it holds |
|---|---|
| `oauth_provider_schemas` | request/response models |
| `oauth_provider_shared` | the routers, token audiences and verification, consent CSRF, the browser session user, authorization codes, redirect validation, PKCE, ID tokens |
| `oauth_provider_scopes` | client grant types and scopes, data API scope, service-client claims |
| `oauth_provider_clients` | silent sign-in, pre-consent, public-client rules, account chooser, error redirects |
| `oauth_provider_resources` | protected-resource authorization and consent, GET /authorize/resume |
| `oauth_provider_authorize` | GET /authorize |
| `oauth_provider_consent` | POST /consent, POST /authorize |
| `oauth_provider_resource_tokens` | token client authentication, protected-resource exchange and refresh |
| `oauth_provider_grants` | client credentials, authorization code and refresh token grants |
| `oauth_provider_device_grant` | client credentials for a shared device (client kind `device`) |
| `oauth_provider_token` | POST /token |
| `oauth_provider_userinfo` | /userinfo, /introspect, /revoke, GET/POST /logout |

Names tests patch live in one module each (`settings`, `get_redis`,
`get_user_from_cookie_or_header`, `_get_oauth_client`, … in
`oauth_provider_shared`; `_is_silent_auth_allowed` in `oauth_provider_clients`),
and the other modules call them through it, so
`patch("app.routers.v1.<module>.X")` reaches every caller. Every name other code
imports from here is re-exported.
"""

import importlib

from app.routers.v1.oauth_provider_shared import logout_router, router  # noqa: F401 (app.main mounts these)

#: Every module the OAuth provider is made of, this one first (for source checks
#: and tooling that used to read app/routers/v1/oauth_provider.py alone).
MODULES = (
    "oauth_provider",
    "oauth_provider_schemas",
    "oauth_provider_shared",
    "oauth_provider_scopes",
    "oauth_provider_clients",
    "oauth_provider_resources",
    "oauth_provider_authorize",
    "oauth_provider_consent",
    "oauth_provider_resource_tokens",
    "oauth_provider_grants",
    "oauth_provider_device_grant",
    "oauth_provider_token",
    "oauth_provider_userinfo",
)

# The route modules, imported in the order their routes were declared here:
# importing one declares its routes on `router`, so this order is the route
# order. A loop, not import statements, so import sorting cannot reorder it.
for _route_module in (
    "oauth_provider_resources",
    "oauth_provider_authorize",
    "oauth_provider_consent",
    "oauth_provider_token",
    "oauth_provider_userinfo",
):
    importlib.import_module(f"app.routers.v1.{_route_module}")

# Re-exports: every name other modules and tests import from this module.
from app.auth.authentication_assurance import (
    assurance_for_request,  # noqa: E402,F401
    user_requires_mfa,  # noqa: E402,F401
)
from app.auth.sso_cookie import resolve_session_by_id  # noqa: E402,F401
from app.config import settings  # noqa: E402,F401
from app.core.database import get_db  # noqa: E402,F401
from app.core.jwt_manager import jwt_manager  # noqa: E402,F401
from app.core.redis import get_redis  # noqa: E402,F401
from app.core.url_security import (
    is_safe_redirect_url,  # noqa: E402,F401
    validate_oauth_redirect_uri,  # noqa: E402,F401
    validate_post_logout_redirect_uri,  # noqa: E402,F401
)
from app.routers.v1.oauth_provider_authorize import (  # noqa: E402,F401
    authorize_get,
)
from app.routers.v1.oauth_provider_clients import (  # noqa: E402,F401
    _S256_CHALLENGE_SHAPE,
    _account_chooser_html,
    _is_first_party_preconsented,
    _is_marked_public_client,
    _is_silent_auth_allowed,
    _public_first_party_refusal,
    _redirect_with_oauth_error,
    _resolve_held_accounts,
)
from app.routers.v1.oauth_provider_consent import (  # noqa: E402,F401
    authorize_post,
    handle_consent,
)
from app.routers.v1.oauth_provider_device_grant import (  # noqa: E402,F401
    _handle_device_client_credentials_grant,
)
from app.routers.v1.oauth_provider_grants import (  # noqa: E402,F401
    _audit_service_token_app_roles,
    _handle_authorization_code_grant,
    _handle_client_credentials_grant,
    _handle_refresh_token_grant,
    _require_invited_access,
)
from app.routers.v1.oauth_provider_resource_tokens import (  # noqa: E402,F401
    _active_user,
    _authenticate_resource_token_client,
    _cimd_client_allowed,
    _exchange_resource_code,
    _oauth_token_error,
    _pinned_cimd_client_id,
    _refresh_resource_token,
    _requested_resource_mismatch,
    _resource_token_response,
    _token_client_from_row,
    _token_for_protected_resource,
    _TokenClient,
)
from app.routers.v1.oauth_provider_resources import (  # noqa: E402,F401
    _CODE_VERIFIER,
    _ERROR_PAGE_MESSAGES,
    _S256_CHALLENGE,
    _TOKEN_RESPONSE_HEADERS,
    RESOURCE_AUTH_REQUEST_TTL,
    RESOURCE_PRE_LOGIN_TTL,
    _authorization_error_page,
    _authorize_protected_resource,
    _complete_protected_resource_consent,
    _login_redirect_for_resource,
    _registered_redirect_uris,
    _resolve_resource_client,
    _resource_policy_error,
    _resource_values,
    _ResourceClient,
    _select_resource,
    authorize_resume,
)
from app.routers.v1.oauth_provider_schemas import (  # noqa: E402,F401
    AuthorizationRequest,
    TokenRequest,
    TokenResponse,
    UserInfoResponse,
)
from app.routers.v1.oauth_provider_scopes import (  # noqa: E402,F401
    APP_ROLE_SCOPE_PATTERN,
    DATA_API_ROLE,
    DATA_API_SCOPE,
    DEFAULT_CLIENT_GRANT_TYPES,
    DEFAULT_CLIENT_SCOPES,
    ORG_MEMBERSHIP_ROLE_SCOPES,
    USER_GRANT_IDENTITY_SCOPES,
    _client_allowed_scopes,
    _client_grant_types,
    _data_api_claims,
    _get_client_credentials_claims,
    _narrow_to_allowed_scopes,
    _parse_requested_scopes,
    _require_grantable_scope,
    _service_account_email,
    _service_client_app_roles,
)
from app.routers.v1.oauth_provider_shared import (  # noqa: E402,F401
    AUTH_CODE_PREFIX,
    AUTH_CODE_TTL,
    CSRF_TOKEN_TTL,
    DEVICE_TOKEN_TTL_SECONDS,
    SERVICE_TOKEN_TTL_SECONDS,
    _accepted_audiences_for_client,
    _audiences_from_claims,
    _build_safe_callback_url,
    _delete_auth_code,
    _generate_csrf_token,
    _generate_id_token,
    _get_auth_code,
    _get_oauth_client,
    _get_user_entitlements,
    _get_user_org_claims,
    _hosted_cookie_session,
    _merge_audiences,
    _redacted,
    _resolve_token_client,
    _session_started_at,
    _store_auth_code,
    _validate_csrf_token,
    _validate_redirect_uri,
    _verify_oauth_token,
    _verify_own_access_token,
    _verify_pkce,
    get_user_from_cookie_or_header,
    logger,
)
from app.routers.v1.oauth_provider_token import (  # noqa: E402,F401
    token,
)
from app.routers.v1.oauth_provider_userinfo import (  # noqa: E402,F401
    _authenticate_revoking_client,
    _clear_janua_session_cookies,
    _perform_oidc_end_session,
    _revoke_protected_resource_token,
    _verified_token_of_client,
    introspect,
    oidc_end_session,
    oidc_end_session_post,
    revoke,
    userinfo,
)
from app.services import token_revocation  # noqa: E402,F401
from app.services.audit_logger import (
    AuditEventType,  # noqa: E402,F401
    AuditLogger,  # noqa: E402,F401
)
from app.services.consent_service import ConsentService  # noqa: E402,F401
from app.services.entitlements_service import (
    entitlements_to_claim,  # noqa: E402,F401
    get_user_entitlements,  # noqa: E402,F401
)
from app.services.oauth_client_authority import client_registered_by_platform_admin  # noqa: E402,F401
from app.services.service_principal import service_principal_claims  # noqa: E402,F401

