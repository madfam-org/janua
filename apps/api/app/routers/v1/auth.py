"""
Authentication router for v1 API

Split on 2026-11-19 (the repository's 800-line pre-commit limit) into the
modules below. No behaviour change: the one `router` (prefix /auth, created in
`auth_shared`, which also includes the OAuth sub-router first, as before)
receives every route in the order they were declared here, because the route
modules are imported in that order; `router.routes` is the same list.

| Module | What it holds |
|---|---|
| `auth_schemas` | request/response models |
| `auth_shared` | the router, logging, session cookies, hosted-page plumbing, redirect resolution |
| `auth_signin` | POST /signup, POST /signin, GET /session |
| `auth_hosted_pages` | HTML of the hosted sign-in pages |
| `auth_hosted_login` | /login-expired, /hosted-form.js, GET /login, /login-form, /login-form/mfa |
| `auth_sessions` | register/login aliases, logout, refresh, sign-out, account switching, /me |
| `auth_recovery` | password forgot/reset (JSON and hosted pages), password change |
| `auth_email_verification` | email verification |
| `auth_magic_link_issue` | POST /magic-link and the issuing path |
| `auth_magic_link_pages` | sign-in link browser binding and pages |
| `auth_magic_link` | link redemption, /magic-link/verify, /login-form/magic-link |

Names tests patch live in one module each (imports such as `get_redis` and
`AuthService` in `auth_shared`; helpers where they are defined), and the other
modules call them through that module, so `patch("app.routers.v1.<module>.X")`
reaches every caller. Every name other code imports from here is re-exported.
"""

import importlib

from app.routers.v1.auth_shared import router

#: Every module the /auth router is made of, this one first (for source checks
#: and tooling that used to read app/routers/v1/auth.py alone).
MODULES = (
    "auth",
    "auth_schemas",
    "auth_shared",
    "auth_signin",
    "auth_hosted_pages",
    "auth_hosted_login",
    "auth_sessions",
    "auth_recovery",
    "auth_email_verification",
    "auth_magic_link_issue",
    "auth_magic_link_pages",
    "auth_magic_link",
)

# The route modules, imported in the order their routes were declared here:
# importing one declares its routes on `router`, so this order is the route
# order. A loop, not import statements, so import sorting cannot reorder it.
for _route_module in (
    "auth_signin",
    "auth_hosted_login",
    "auth_sessions",
    "auth_recovery",
    "auth_email_verification",
    "auth_magic_link_issue",
    "auth_magic_link",
):
    importlib.import_module(f"app.routers.v1.{_route_module}")

# Re-exports: every name other modules and tests import from this module.
from fastapi.security import HTTPBearer  # noqa: E402,F401
from slowapi import Limiter  # noqa: E402,F401
from sqlalchemy.orm import Session  # noqa: E402,F401

from app.auth.hosted_locale import hosted_locale  # noqa: E402,F401
from app.auth.hosted_security import router as hosted_security_router  # noqa: E402
from app.auth.magic_link_limits import enforce_magic_link_limits  # noqa: E402,F401
from app.auth.sso_cookie import (
    resolve_session_by_id,  # noqa: E402,F401
    revoke_sso_session,  # noqa: E402,F401
)
from app.config import settings  # noqa: E402,F401
from app.core.redis import get_redis  # noqa: E402,F401
from app.core.redis_circuit_breaker import RedisUnavailableError  # noqa: E402,F401
from app.core.url_security import validate_redirect_url  # noqa: E402,F401
from app.database import get_db  # noqa: E402,F401
from app.dependencies import (
    get_current_user,  # noqa: E402,F401
    get_current_user_for_sign_out,  # noqa: E402,F401
)
from app.routers.v1.auth_email_verification import (  # noqa: E402,F401
    resend_verification_email,
    verify_email,
    verify_email_alias,
)
from app.routers.v1.auth_hosted_login import (  # noqa: E402,F401
    hosted_form_script,
    login_expired_page,
    login_form,
    login_form_mfa,
    login_page,
)
from app.routers.v1.auth_hosted_pages import (  # noqa: E402,F401
    _hosted_login_page_html,
    _login_page_switch_url,
    _magic_link_form_html,
    _password_form_html,
    _render_mfa_challenge_page,
)
from app.routers.v1.auth_magic_link import (  # noqa: E402,F401
    _oauth_continuation_url,
    login_form_magic_link,
    magic_link_callback,
    magic_link_callback_interstitial,
    verify_magic_link,
)
from app.routers.v1.auth_magic_link_issue import (  # noqa: E402,F401
    _issue_magic_link,
    send_magic_link,
)
from app.routers.v1.auth_magic_link_pages import (  # noqa: E402,F401
    _MAGIC_LINK_BROWSER_COOKIE_MAX_AGE,
    _MAGIC_LINK_BROWSER_COOKIE_PATH,
    _MAGIC_LINK_BROWSER_VALUE,
    MAGIC_LINK_BROWSER_COOKIE,
    _check_inbox_page_html,
    _magic_link_binding_digest,
    _magic_link_browser_binding,
    _magic_link_by_token,
    _magic_link_dead_page,
    _magic_link_interstitial_html,
    _magic_link_interstitial_is_spanish,
    _magic_link_page_html,
    _magic_link_spend_key,
    _mask_email,
    _remember_magic_link_spend,
    _set_magic_link_browser_cookie,
    _spent_here_moments_ago,
)
from app.routers.v1.auth_recovery import (  # noqa: E402,F401
    _consume_password_reset,
    _dispatch_password_reset,
    _reset_form_body,
    _reset_page_html,
    change_password,
    forgot_password,
    forgot_password_form,
    forgot_password_page,
    reset_password,
    reset_password_form,
    reset_password_page,
)
from app.routers.v1.auth_schemas import (  # noqa: E402,F401
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MagicLinkRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SignInRequest,
    SignInResponse,
    SignUpRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    VerifyMagicLinkRequest,
)
from app.routers.v1.auth_sessions import (  # noqa: E402,F401
    SwitchSessionRequest,
    _form_post_is_same_origin,
    _fronted_sid,
    _held_sids,
    _switch_page_locale,
    _switch_refused_html,
    _switch_to_held_session,
    get_current_user_info,
    login,
    logout,
    refresh_token,
    register,
    sign_out,
    sign_out_all_accounts,
    sign_out_one_account,
    switch_session,
    switch_session_form,
)
from app.routers.v1.auth_shared import (  # noqa: E402,F401
    _AUDIT_EVENT_MAP,
    HOSTED_FORM_SCRIPT,
    HOSTED_FORM_SCRIPT_PATH,
    HOSTED_FORM_SCRIPT_TAG,
    _busy_label_attr,
    _invite_only_destination,
    _login_expired_url,
    _map_mail_client,
    _map_mail_organization,
    _oauth_client_for_redirect,
    _oauth_context_hidden_fields_html,
    _preferred_pool_for_redirect,
    _recover_authorize_url_from_client,
    _recovery_page_html,
    _resolve_oauth_redirect_target,
    _session_audience_for_redirect,
    _set_session_cookies,
    limiter,
    log_activity,
    log_audit_event,
    logger,
    security,
    signups_enabled,
)
from app.routers.v1.auth_signin import (  # noqa: E402,F401
    _resolve_signup_tenant,
    check_session,
    sign_in,
    sign_up,
)
from app.services.account_lockout_service import AccountLockoutService  # noqa: E402,F401
from app.services.audit_logger import (
    AuditEventType,  # noqa: E402,F401
    AuditLogger,  # noqa: E402,F401
)
from app.services.auth_service import AuthService  # noqa: E402,F401
from app.services.email_send_audit import add_intent  # noqa: E402,F401
from app.services.email_service import (
    send_magic_link_email_task,  # noqa: E402,F401
    send_password_reset_email_task,  # noqa: E402,F401
)
from app.services.user_lookup import get_user_by_email  # noqa: E402,F401
from app.services.webhooks import trigger_user_webhook  # noqa: E402,F401

from ...models import (
    ActivityLog,  # noqa: E402,F401
    User,  # noqa: E402,F401
    UserStatus,  # noqa: E402,F401
)
from ...models import Session as UserSession  # noqa: E402,F401

router.include_router(hosted_security_router)
