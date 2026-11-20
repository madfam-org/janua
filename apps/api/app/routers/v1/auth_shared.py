"""Helpers shared by the /auth route modules: activity and audit logging, session cookies, hosted-page plumbing and redirect resolution.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import json
from typing import Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.security import HTTPBearer
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorize_resume import authorize_query
from app.auth.hosted_locale import DEFAULT_HOSTED_LOCALE, UI_LOCALES_PARAM, hidden_ui_locales_field
from app.auth.magic_link_limits import enforce_magic_link_limits  # noqa: F401 (patch point)
from app.auth.sessions_cookie import (
    SESSIONS_COOKIE_NAME,
    append_sid,
    read_sessions_cookie,
    set_sessions_cookie,
)
from app.auth.sso_cookie import (
    resolve_session_by_id,  # noqa: F401 (patch point)
    revoke_sso_session,  # noqa: F401 (patch point)
    set_sso_cookie,
)
from app.config import settings
from app.core.rate_limit_keys import client_ip_key
from app.core.redis import (
    ResilientRedisClient,
    get_redis,  # noqa: F401 (patch point)
)
from app.core.url_security import validate_redirect_url
from app.models.system_settings import SettingKeys
from app.routers.v1 import oauth
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.auth_service import AuthService  # noqa: F401 (patch point)
from app.services.email_send_audit import (
    add_intent,  # noqa: F401 (patch point)
    is_map_destination,
)
from app.services.email_service import (
    send_magic_link_email_task,  # noqa: F401 (patch point)
    send_password_reset_email_task,  # noqa: F401 (patch point)
)
from app.services.invite_only_clients import is_invite_only
from app.services.system_settings_service import SystemSettingsService
from app.services.user_lookup import get_user_by_email  # noqa: F401 (patch point)
from app.services.webhooks import trigger_user_webhook  # noqa: F401 (patch point)

from ...models import ActivityLog

logger = structlog.get_logger()


# Initialize rate limiter
limiter = Limiter(key_func=client_ip_key)


router = APIRouter(prefix="/auth", tags=["Authentication"])

# Include OAuth sub-router (first, before any /auth route, as always)
router.include_router(oauth.router)


security = HTTPBearer()


async def log_activity(
    db: Session, user_id: str, action: str, details: Dict = None, request: Request = None
):
    """Log user activity"""
    activity = ActivityLog(
        user_id=user_id,
        action=action,
        activity_metadata=details or {},  # Model uses activity_metadata, not details
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(activity)
    await db.commit()


# SOC 2 CF-08: Audit event type mapping for auth actions
_AUDIT_EVENT_MAP = {
    "signup": AuditEventType.AUTH_SIGNUP,
    "signin": AuditEventType.AUTH_SIGNIN,
    "signout": AuditEventType.AUTH_SIGNOUT,
    "password_change": AuditEventType.AUTH_PASSWORD_CHANGE,
    "password_reset": AuditEventType.AUTH_PASSWORD_RESET,
    "email_verified": AuditEventType.USER_UPDATE,
}


async def signups_enabled(db: Session) -> bool:
    """Resolve whether self-service signup is currently allowed.

    Precedence (most specific wins):
      1. `auth.allow_signups` system setting (DB-backed runtime switch) — lets an
         operator flip signups on/off via the admin settings API WITHOUT a
         redeploy. This is the live switch the `SettingKeys.AUTH_ALLOW_SIGNUPS`
         key was always meant to be but previously was read nowhere.
      2. `settings.ENABLE_SIGNUPS` (env/config) — the deploy-time default and the
         fallback used whenever the DB toggle is unset.

    The DB value is coerced from its stored form (SystemSettingsService persists
    scalars as strings), so "false"/"0"/"no"/"off"/"" all read as False. A failure
    reading the settings table must never silently harden the gate shut, so any
    error defers to the config default rather than inventing a decision.
    """
    try:
        service = SystemSettingsService(db)
        raw = await service.get_setting(SettingKeys.AUTH_ALLOW_SIGNUPS, default=None)
    except Exception:
        return settings.ENABLE_SIGNUPS

    if raw is None:
        return settings.ENABLE_SIGNUPS
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() not in {"false", "0", "no", "off", ""}


async def log_audit_event(
    db: Session, user_id: str, action: str, details: Dict = None, request: Request = None
):
    """Log to SOC 2 audit trail (CF-08) alongside activity log."""
    event_type = _AUDIT_EVENT_MAP.get(action)
    if not event_type:
        return
    try:
        audit_logger = AuditLogger(db)
        await audit_logger.log(
            event_type=event_type,
            tenant_id="default",
            identity_id=user_id,
            details=details or {},
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            severity="info",
        )
    except Exception:
        # Audit logging failure should not break auth flow
        pass


def _oauth_context_hidden_fields_html(
    *,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    client_name: Optional[str],
    next_url: Optional[str] = None,
    ui_locale: Optional[str] = None,
) -> str:
    """Hidden form fields that preserve OAuth context across retries.

    `ui_locale` (a NORMALIZED page language) carries a non-English page
    language forward; English adds nothing, so English forms are unchanged.
    """
    import html

    parts: list[str] = []
    if auth_request_id:
        parts.append(
            f'<input type="hidden" name="auth_request_id" value="{html.escape(auth_request_id)}">'
        )
    elif next_url:
        parts.append(f'<input type="hidden" name="next" value="{html.escape(next_url)}">')
    if client_id:
        parts.append(f'<input type="hidden" name="client_id" value="{html.escape(client_id)}">')
    if client_name:
        parts.append(f'<input type="hidden" name="client_name" value="{html.escape(client_name)}">')
    parts.append(hidden_ui_locales_field(ui_locale))
    return "".join(parts)


async def _recover_authorize_url_from_client(client_id: str, db) -> Optional[str]:
    """Send the user back to the CLIENT so it can start a fresh flow.

    This used to rebuild a synthetic /oauth/authorize URL from the client's
    registration. That URL carried no `state`, no `nonce` and no PKCE
    challenge, because the server cannot know them — only the client that
    started the flow does. Every modern OIDC client validates `state` and a
    PKCE verifier against its own cookies, so the callback produced by such a
    fabricated request could never be accepted: Auth.js rejects it with
    `response parameter "state" missing` (observed in prod 2026-08-13).

    A recovery that cannot succeed is worse than an honest restart. Returning
    the client's own origin lets it mint a new state + verifier pair the way
    it always does.
    """
    from ...models import OAuthClient as _OAuthClient

    stmt = select(_OAuthClient).where(_OAuthClient.client_id == client_id)
    result = await db.execute(stmt)
    oauth_client = result.scalar_one_or_none()
    if not oauth_client or not oauth_client.is_active or not oauth_client.redirect_uris:
        return None

    redirect_uris = oauth_client.redirect_uris
    if isinstance(redirect_uris, str):
        try:
            redirect_uris = json.loads(redirect_uris)
        except json.JSONDecodeError:
            redirect_uris = []
    if not redirect_uris:
        return None

    # The origin of the registered callback is the product itself. Landing
    # there re-enters the product's own sign-in entry point, which starts a
    # complete authorize request (state + PKCE) that its callback can verify.
    parsed = urlparse(redirect_uris[0])
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def _login_expired_url(*, client_id: Optional[str], locale: str) -> str:
    """The GET page a sign-in POST sends the browser to when its request is gone
    and cannot be restarted from here (see login_form)."""
    params: dict[str, str] = {}
    if client_id:
        params["client_id"] = client_id
    if locale != DEFAULT_HOSTED_LOCALE:
        params[UI_LOCALES_PARAM] = locale
    query = f"?{urlencode(params)}" if params else ""
    return f"/api/v1/auth/login-expired{query}"


def _set_session_cookies(
    response,
    access_token: str,
    refresh_token: str,
    *,
    user=None,
    session=None,
    request=None,
) -> None:
    """Set the hosted-flow session cookies on a response.

    Extracted so the password path (login_form) and the second-factor path
    (login_form_mfa) set identical cookies — same names, flags, TTLs, and
    optional cross-subdomain domain — instead of drifting between two copies.
    The access cookie is intentionally non-HttpOnly (the browser SDK reads it for
    API calls); the refresh cookie is HttpOnly.

    SSO (J5/R1): when `user` and `session` are supplied, this also sets
    `janua_sso` — the HttpOnly estate cookie `@madfam/janua-next` relays to the
    browser after a server-to-server magic-link exchange, and the only session
    reference `/authorize` can see when a person arrives from another product.
    See `app/auth/sso_cookie.py` for why it is a separate cookie. `user`/`session`
    are keyword-only and optional so no existing caller changes behaviour by
    accident: a caller that cannot name the session row emits no `janua_sso`
    rather than one that could never be revoked.

    Multi-account (Layer 3): when `request` is also supplied, this APPENDS the
    new session's `sid` to `janua_sessions` — the companion cookie that remembers
    every estate account this browser holds — without disturbing the others.
    `janua_sso` stays the pointer to the freshly-fronted session; `janua_sessions`
    keeps the full set so a later switch need not re-authenticate. Optional and
    keyword-only so a caller with no request in scope emits `janua_sso` alone,
    exactly as before. See `app/auth/sessions_cookie.py`.
    """
    access_cookie_kwargs: dict = {
        "httponly": False,
        "samesite": "lax",
        "secure": True,
        "max_age": 3600,  # 1 hour
    }
    refresh_cookie_kwargs: dict = {
        "httponly": True,
        "samesite": "lax",
        "secure": True,
        "max_age": 604800,  # 7 days
    }
    if settings.COOKIE_DOMAIN:
        access_cookie_kwargs["domain"] = settings.COOKIE_DOMAIN
        refresh_cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(key="janua_access_token", value=access_token, **access_cookie_kwargs)
    response.set_cookie(key="janua_refresh_token", value=refresh_token, **refresh_cookie_kwargs)

    if user is not None and session is not None:
        set_sso_cookie(response, str(getattr(user, "id", "")), session)
        session_id = getattr(session, "id", None)
        if request is not None and session_id:
            held = read_sessions_cookie(request.cookies.get(SESSIONS_COOKIE_NAME))
            set_sessions_cookie(response, append_sid(held, str(session_id)))


async def _resolve_oauth_redirect_target(
    *,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    next_url: str,
    redis: ResilientRedisClient,
    db,
) -> str:
    """Resolve where to send the browser after a hosted login completes.

    Mirrors login_form's redirect logic for the second-factor path: prefer the
    OAuth authorize URL rebuilt from the Redis-stored params (keyed by
    auth_request_id), fall back to the client's registered origin, and otherwise
    use the validated `next` URL. Does NOT delete the Redis key (the caller does,
    after a session is created), matching login_form's single-use semantics.
    """
    if auth_request_id:
        stored_data = await redis.get(f"oauth:pre_login:{auth_request_id}")
        if stored_data:
            try:
                auth_params = json.loads(stored_data)
                query_params = authorize_query(auth_params)
                return f"/api/v1/oauth/authorize?{urlencode(query_params)}"
            except (json.JSONDecodeError, KeyError):
                pass
        # Redis lost the params — try the client's registered origin.
        if client_id:
            recovered = await _recover_authorize_url_from_client(client_id, db)
            if recovered:
                return recovered
        return "/"
    # Non-OAuth login: validate the caller-supplied next URL (CWE-601).
    return validate_redirect_url(next_url, default_url="/")


# ONE PRESS ON EVERY HOSTED FORM (2026-11-19). A hosted form's POST takes about
# a second (the password hash) plus the redirect chain after it. Until then the
# button stayed live, and a second press (or Enter) started a new submission
# that cancelled the navigation in flight; the browser then showed the answer to
# the second POST, which found its sign-in request already used. So each hosted
# form names its busy label (`data-busy-label`) and this script disables the
# button and says it is working after the first submit. It is a same-origin
# file, not an inline block: the API's CSP allows `script-src 'self'`, and a
# file keeps working if `'unsafe-inline'` (there for Swagger UI) is ever
# dropped. `pageshow` re-enables the button when the browser restores the page
# from its back/forward cache, and a timer does after 20 s, so a stalled
# network never leaves a dead button. Without script the forms work exactly as
# before (the server also answers a repeated POST with a page, see login_form).
HOSTED_FORM_SCRIPT_PATH = "/api/v1/auth/hosted-form.js"


HOSTED_FORM_SCRIPT_TAG = f'\n    <script src="{HOSTED_FORM_SCRIPT_PATH}" defer></script>'


HOSTED_FORM_SCRIPT = """(function () {
  "use strict";
  var forms = document.querySelectorAll("form[data-busy-label]");
  Array.prototype.forEach.call(forms, function (form) {
    var button = form.querySelector('button[type="submit"]');
    if (!button) return;
    var label = button.textContent;
    var status = document.createElement("span");
    status.setAttribute("role", "status");
    status.style.cssText =
      "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap";
    form.appendChild(status);
    var timer = null;
    function reset() {
      if (timer) window.clearTimeout(timer);
      timer = null;
      form.removeAttribute("data-submitting");
      form.removeAttribute("aria-busy");
      button.disabled = false;
      button.textContent = label;
      status.textContent = "";
    }
    form.addEventListener("submit", function (event) {
      if (form.getAttribute("data-submitting") === "1") {
        event.preventDefault();
        return;
      }
      var busy = form.getAttribute("data-busy-label");
      form.setAttribute("data-submitting", "1");
      form.setAttribute("aria-busy", "true");
      button.disabled = true;
      button.textContent = busy;
      status.textContent = busy;
      timer = window.setTimeout(reset, 20000);
    });
    window.addEventListener("pageshow", function (event) {
      if (event.persisted) reset();
    });
  });
})();
"""


def _busy_label_attr(label: str) -> str:
    """` data-busy-label="…"` for a hosted form tag (the label is our own copy)."""
    import html as _html

    return f' data-busy-label="{_html.escape(label, quote=True)}"'


def _recovery_page_html(
    body: str, title: str = "Password recovery - Janua", lang: str = "en"
) -> str:
    """Visual shell for the hosted recovery pages — same look as the hosted
    login page (whose CSS is inlined per-page by existing convention)."""
    return f"""
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>{HOSTED_FORM_SCRIPT_TAG}
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ font-size: 28px; color: #333; margin-bottom: 8px; }}
        .logo p {{ color: #666; font-size: 14px; }}
        .lead {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .lead a {{ color: #667eea; }}
        .hint {{ color: #666; font-size: 12px; margin: -8px 0 16px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        .alert-error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .alert-ok {{
            background: #e8f5ee;
            color: #14683c;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="login-container">
{body}
    </div>
</body>
</html>
"""


async def _map_mail_client(db, redirect_url, client_id):
    """Derive MAP origin from registered active redirects, never caller tags."""
    from app.models import OAuthClient
    from app.services.email_branding import CTM_ORG_ID

    direct_map = is_map_destination(redirect_url)
    client = await _oauth_client_for_redirect(db, redirect_url) if direct_map else None
    if not direct_map and redirect_url:
        target = urlparse(redirect_url)
        named = parse_qs(target.query).get("client_id", [None])[0]
        issuer_host = urlparse(settings.public_base_url).hostname
        if (
            target.hostname == issuer_host
            and target.path.rstrip("/") == "/api/v1/oauth/authorize"
            and named
        ):
            if client_id is not None and named != client_id:
                raise HTTPException(status_code=400, detail="Login destination client mismatch")
            result = await db.execute(
                select(OAuthClient).where(
                    OAuthClient.client_id == named, OAuthClient.is_active.is_(True)
                )
            )
            candidate = result.scalar_one_or_none()
            uris = getattr(candidate, "redirect_uris", None) or []
            if isinstance(uris, str):
                try:
                    uris = json.loads(uris)
                except (ValueError, TypeError):
                    uris = []
            if isinstance(uris, list) and any(
                isinstance(uri, str) and is_map_destination(uri) for uri in uris
            ):
                client = candidate
    if direct_map or client is not None:
        client_org = getattr(client, "organization_id", None)
        if client is None or (client_org is not None and str(client_org) != str(CTM_ORG_ID)):
            raise HTTPException(status_code=503, detail="MAP login destination binding unavailable")
        return client
    return None


def _map_mail_organization(client, redirect_url):
    """Mail tenant is independent of the platform identity pool.

    Real MAP/ensayo registrations share a native platform-pool OAuth client.
    Resolve the mail organization from server-owned sender bindings after the
    active registered destination has been verified, never from an org hint.
    """
    from app.services.email_branding import CTM_ORG_ID
    from app.services.email_sender import binding_for

    if client is not None and getattr(client, "organization_id", None) is not None and str(client.organization_id) != str(CTM_ORG_ID):
        raise HTTPException(503, "MAP mail organization binding unavailable")
    target = redirect_url if is_map_destination(redirect_url) else None
    if target is None:
        uris = getattr(client, "redirect_uris", None) or []
        if isinstance(uris, str):
            try:
                uris = json.loads(uris)
            except (ValueError, TypeError):
                uris = []
        target = next(
            (uri for uri in uris if isinstance(uri, str) and is_map_destination(uri)), None
        )
    binding = binding_for(redirect_url=target)
    if target is None or str(binding.org_id) != str(CTM_ORG_ID):
        raise HTTPException(status_code=503, detail="MAP mail organization binding unavailable")
    return str(binding.org_id)


async def _invite_only_destination(
    db: Session, redirect_url: Optional[str], client_id: Optional[str]
) -> bool:
    """Is this sign-in link for an invite-only client?

    The hosted form names its client. A `POST /magic-link` names a destination:
    either a product URL (its host's registered client decides) or Janua's own
    `/oauth/authorize` continuation, whose `client_id` query parameter does.
    Cheap when no client is invite-only: nothing is read.
    """
    if client_id:
        return is_invite_only(client_id)
    if not settings.INVITE_ONLY_CLIENTS.strip() or not redirect_url:
        return False
    parsed = urlparse(redirect_url)
    if parsed.path.rstrip("/").endswith("/oauth/authorize"):
        named = parse_qs(parsed.query).get("client_id", [None])[0]
        if named and is_invite_only(named):
            return True
    client = await _oauth_client_for_redirect(db, redirect_url)
    return bool(client is not None and is_invite_only(client.client_id))


async def _session_audience_for_redirect(db: Session, redirect_url: Optional[str]) -> Optional[str]:
    """The per-client audience for a magic-link session, from the redirect host.

    A magic link that forwards to a product should mint a session that
    product's verifier accepts — the audience registered on the OAuth client
    whose redirect_uris share the destination's host. Matching is by HOST, not
    full URI: the magic-link redirect (`/portal/verify`) is not an OAuth
    callback path, but the host names the same product. The redirect_url was
    already allowlist-validated when the link was requested; this only decides
    which registered audience the session carries.

    None (no redirect, no host match, or client without an audience) keeps the
    platform default — exactly what every session minted before this existed.
    """
    client = await _oauth_client_for_redirect(db, redirect_url, require_audience=True)
    return client.audience if client else None


async def _oauth_client_for_redirect(
    db: Session, redirect_url: Optional[str], *, require_audience: bool = False
):
    """The active OAuth client whose redirect_uris share the destination's host.

    Factored out of :func:`_session_audience_for_redirect` so the same host →
    client mapping can answer two questions: which audience a session carries,
    and which ORGANIZATION owns the requesting product (the preferred user pool
    when an email could exist in more than one). ``require_audience`` keeps the
    audience resolver's original filter — a client without an audience never
    changed the session's audience — while the pool resolver wants any active
    client for the host.
    """
    if not redirect_url:
        return None
    host = urlparse(redirect_url).hostname
    if not host:
        return None

    from ...models import OAuthClient as _OAuthClient

    stmt = select(_OAuthClient).where(
        _OAuthClient.is_active == True,  # noqa: E712 — SQLAlchemy comparator
    )
    if require_audience:
        stmt = stmt.where(_OAuthClient.audience.isnot(None))
    result = await db.execute(stmt)
    for client in result.scalars():
        uris = client.redirect_uris or []
        # Some prod rows store the array double-encoded — a JSON string
        # CONTAINING the array — and iterating a string yields characters,
        # which would make this resolver silently match nothing. Same
        # tolerance the OAuth recovery path above applies.
        if isinstance(uris, str):
            try:
                uris = json.loads(uris)
            except json.JSONDecodeError:
                uris = []
        for uri in uris:
            if isinstance(uri, str) and urlparse(uri).hostname == host:
                return client
    return None


async def _preferred_pool_for_redirect(db: Session, redirect_url: Optional[str]):
    """The organization id to prefer when an email matches more than one pool."""
    client = await _oauth_client_for_redirect(db, redirect_url)
    return getattr(client, "organization_id", None) if client else None
