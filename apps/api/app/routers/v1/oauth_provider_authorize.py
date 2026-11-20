"""GET /oauth/authorize.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import html
import json
import secrets
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import has_mfa_assurance
from app.auth.hosted_locale import UI_LOCALES_PARAM, hosted_locale, page_locale, with_ui_locales
from app.auth.invite_only_page import render_invite_only_refusal
from app.auth.login_method import normalize_login_method
from app.auth.sessions_cookie import SESSIONS_COOKIE_NAME, read_sessions_cookie
from app.core.database import get_db
from app.core.redis import ResilientRedisClient
from app.core.reserved_oauth_boundaries import is_reserved_scope
from app.routers.v1 import oauth_provider_clients as _oauth_provider_clients
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_clients import (
    _account_chooser_html,
    _is_first_party_preconsented,
    _is_marked_public_client,
    _public_first_party_refusal,
    _redirect_with_oauth_error,
    _resolve_held_accounts,
)
from app.routers.v1.oauth_provider_resources import _authorize_protected_resource, _resource_values
from app.routers.v1.oauth_provider_scopes import _require_grantable_scope
from app.routers.v1.oauth_provider_shared import (
    AUTH_CODE_TTL,
    _build_safe_callback_url,
    _redacted,
    router,
)
from app.services.client_id_metadata import is_url_client_id
from app.services.consent_service import ConsentService
from app.services.invite_only_clients import has_invited_access


@router.get("/authorize")
async def authorize_get(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("openid"),
    state: Optional[str] = Query(None),
    nonce: Optional[str] = Query(None),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
    prompt: Optional[str] = Query(
        None,
        description=(
            "OIDC prompt parameter — a space-delimited set. Honored: 'none' "
            "(silent auth: issue a code immediately if a valid Janua session "
            "cookie is present, otherwise redirect with error=login_required); "
            "'login' (force the interactive login form even when the session "
            "cookie is valid — never auto-issue a code); 'select_account' "
            "(render a chooser over the sessions this browser holds; with no held "
            "session it degrades to 'login'). 'none' is mutually exclusive with the others; if "
            "combined, the interactive force wins. Absent: the default "
            "interactive path (reuse a valid session, otherwise show login). "
            "MFA and consent gates are preserved under every value."
        ),
    ),
    login_method: Optional[str] = Query(
        None,
        description=(
            "Which method the hosted login page offers first when the browser "
            "holds no session: 'magic_link' (email a sign-in link) or "
            "'password'. Unknown values are ignored; absent means the "
            "deployment default (HOSTED_LOGIN_DEFAULT_METHOD)."
        ),
    ),
    ui_locales: Optional[str] = Query(
        None,
        description=(
            "OIDC ui_locales: space-separated BCP 47 tags in order of "
            "preference. The hosted login, sign-in link and recovery pages "
            "render in the first one Janua supports (es or en); absent or "
            "unsupported means English, as before."
        ),
    ),
    resource: Optional[List[str]] = Query(
        None,
        description=(
            "RFC 8707 resource indicator: the protected resource (e.g. an MCP "
            "server URL) the token is for. Must name a registered resource; "
            "the access token's `aud` is that URI. Absent: the default flow."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
):
    """
    OAuth 2.0 Authorization Endpoint (GET).

    If user is not authenticated, redirect to login page.
    If user is authenticated, show consent screen or auto-approve.

    A request with `resource`, or with an https `client_id` (a Client ID
    Metadata Document), goes through `_authorize_protected_resource` instead:
    registered resources and clients only, PKCE S256, consent every time.

    Authentication is checked, in this order (see
    `get_user_from_cookie_or_header`, which owns the rule):
    - Authorization header (Bearer token)
    - janua_sso cookie (the estate session — preferred over the one below since
      J9, because a stale hosted-login cookie no host in the estate can delete
      must not outrank the login that just happened)
    - janua_access_token cookie (set by the hosted login form)

    OIDC `prompt=none` (silent auth, ADR 2026-05-04-selva-unified-sso):
        - Valid session present → issue code immediately, skip consent UI.
        - No / expired session → redirect back with `error=login_required`.
        - Consent missing → redirect back with `error=consent_required`.
        - Email verification or MFA required → respect those checks; never
          bypass them just because `prompt=none` was requested.
    """
    # Get user from header or cookie (supports browser-based OAuth flow)
    current_user = await _oauth_provider_shared.get_user_from_cookie_or_header(request, db)

    resource_values = _resource_values(resource)
    if resource_values or is_url_client_id(client_id):
        scope_param = scope
        if isinstance(request, Request) and "scope" not in request.query_params:
            scope_param = None  # omitted: every scope of the resource
        return await _authorize_protected_resource(
            request=request,
            current_user=current_user,
            response_type=response_type,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope_param,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            prompt=prompt,
            login_method=login_method,
            resource_values=resource_values,
            db=db,
            redis=redis,
        )

    # OIDC `prompt` is a space-delimited SET of values, not a single token.
    prompt_values = {p for p in (prompt or "").strip().lower().split() if p}
    silent_auth = "none" in prompt_values
    # `prompt=login` forces re-authentication; `prompt=select_account` asks for an
    # account chooser. select_account renders a chooser over the sessions this
    # browser holds (`janua_sessions`); with no held session it degrades to
    # `login` — the spec-permitted fallback when the AS cannot offer a selection.
    # Either one forces the interactive path even when a valid session cookie is
    # present. `none` is mutually exclusive with these per OIDC; if a client sends
    # `none` with `login`/`select_account`, silent auth is refused below and the
    # force applies, which is the safe (interactive) resolution.
    force_login = ("login" in prompt_values) or ("select_account" in prompt_values)
    wants_chooser = "select_account" in prompt_values
    # If a client illegally combines `none` with `login`/`select_account`, the
    # interactive force wins — never auto-issue a code when re-auth was demanded.
    if force_login:
        silent_auth = False

    # Validate response_type
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_response_type: Only 'code' is supported",
        )

    # Validate client
    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_client: Unknown client_id",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_client: Client is disabled",
        )

    # SECURITY: Validate redirect_uri against registered URIs (CWE-601 prevention)
    # This MUST happen before ANY redirect to prevent open redirect attacks
    if not _oauth_provider_shared._validate_redirect_uri(redirect_uri, client.redirect_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_redirect_uri: URI not registered for this client",
        )

    # Validate PKCE - SECURITY: Only S256 is allowed (OAuth 2.1 requirement)
    if code_challenge_method and code_challenge_method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: Only S256 code_challenge_method is supported",
        )

    # SECURITY: PKCE is required for public (non-confidential) clients
    if not getattr(client, "is_confidential", False) and not code_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: PKCE (code_challenge) is required for public clients",
        )

    # SECURITY: the requested scope is narrowed to the client's `allowed_scopes`
    # BEFORE it is stored anywhere (pre-login request, consent request, code),
    # matching the client_credentials grant's allowlist. Unlisted scopes are
    # dropped (RFC 6749 §3.3); a request of which nothing is allowed is refused
    # with `invalid_scope`. redirect_uri is validated above, so redirecting the
    # error is safe.
    requested_scope = scope
    try:
        scope = _require_grantable_scope(scope, client, grant="authorization_code")
    except ValueError as exc:
        return _redirect_with_oauth_error(
            redirect_uri,
            error="invalid_scope",
            error_description=str(exc),
            state=state,
            client_validated=True,
        )

    # PUBLIC first-party clients (owner decision 2026-11-18). A public client an
    # operator marked with `madfam:silent_auth` may use prompt=none and skip the
    # consent screen, but only when this request binds the code to the
    # registered app (`_public_first_party_refusal`) and the row was registered
    # by a platform admin (the trust rule service boundaries use for reserved
    # values). Unmarked public clients and confidential clients are untouched.
    public_first_party = False
    public_refusal: Optional[tuple[str, str]] = None
    if _is_marked_public_client(client):
        public_refusal = _public_first_party_refusal(
            client,
            redirect_uri=redirect_uri,
            requested_scope=requested_scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        if public_refusal is None and not await _oauth_provider_shared.client_registered_by_platform_admin(db, client):
            public_refusal = ("interaction_required", "silent_auth not allowed for this client")
            _oauth_provider_shared.logger.warning(
                "oauth.public_first_party.marker_not_trusted",
                client_id=client_id,
                reason="client not registered by a platform admin",
            )
        public_first_party = public_refusal is None
        if public_refusal is not None:
            _oauth_provider_shared.logger.info(
                "oauth.public_first_party.not_applied",
                client_id=client_id,
                silent=silent_auth,
                reason=public_refusal[1],
            )

    # SECURITY: silent-auth (prompt=none) is restricted to pre-registered
    # first-party clients. A third-party app cannot use prompt=none to skip
    # the consent UI even if the user has a Janua session.
    if silent_auth and not (_oauth_provider_clients._is_silent_auth_allowed(client) or public_first_party):
        error, error_description = public_refusal or (
            "interaction_required",
            "silent_auth not allowed for this client",
        )
        _oauth_provider_shared.logger.warning(
            "Rejected prompt=none from non-first-party client",
            client_id=client_id,
            client_name=client.name,
            error=error,
        )
        return _redirect_with_oauth_error(
            redirect_uri,
            error=error,
            error_description=error_description,
            state=state,
            client_validated=True,
        )

    # If user not authenticated — or re-auth was demanded via prompt=login /
    # prompt=select_account — send the browser through the interactive login form.
    # A forced re-auth must NOT auto-issue a code off a still-valid session cookie;
    # the login form is where the second factor and a fresh credential are proven,
    # so this path preserves the MFA and consent gates (login re-runs them) rather
    # than skipping straight to a code.
    if not current_user or force_login:
        if force_login:
            _oauth_provider_shared.logger.info(
                "prompt forcing interactive login despite a session",
                prompt_value=("select_account" if "select_account" in prompt_values else "login"),
                client_id=client_id,
            )
        # OIDC prompt=none: must NOT prompt — return error and let the caller
        # decide whether to fall back to interactive flow. (Unreachable when
        # force_login is set, since that clears silent_auth above.)
        if silent_auth:
            _oauth_provider_shared.logger.info(
                "prompt=none but no Janua session — emitting login_required",
                client_id=client_id,
            )
            return _redirect_with_oauth_error(
                redirect_uri,
                error="login_required",
                error_description="No active Janua session for silent auth",
                state=state,
                client_validated=True,
            )
        # SECURITY: Store full OAuth parameters in Redis instead of encoding them
        # into the redirect URL. This avoids double-encoding issues with urlencode()
        # that caused redirect loops when the 'next' URL contained query params.
        # Pattern matches the consent flow storage at lines 580-596.
        pre_login_id = secrets.token_urlsafe(16)
        # The client's preferred first method travels with the request: the
        # hosted page reads it from the login URL, and the hosted magic-link
        # form finds the rest of the authorize request under this key.
        requested_login_method = normalize_login_method(login_method)
        # The page language travels the same way: stored with the request (so
        # the rebuilt authorize URL after an emailed link still carries it) and
        # named on the login URL. Normalized here; None leaves both unchanged.
        requested_ui_locale = hosted_locale(ui_locales)
        pre_login_data = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "login_method": requested_login_method,
            "ui_locales": requested_ui_locale,
        }
        # Strict: if Redis cannot hold the request, answer a retryable 503 now
        # rather than send the browser to a login page whose id leads nowhere.
        await redis.strict_set(
            f"oauth:pre_login:{pre_login_id}",
            json.dumps(pre_login_data),
            ex=600,  # 10 minutes TTL
        )

        # Pass only the opaque ID plus display-only params to the login page
        login_param_values = {
            "auth_request_id": pre_login_id,
            "client_id": client_id,
            "client_name": client.name,
        }
        if requested_login_method:
            login_param_values["login_method"] = requested_login_method
        if requested_ui_locale:
            login_param_values[UI_LOCALES_PARAM] = requested_ui_locale
        login_params = urlencode(login_param_values)
        login_url = f"/api/v1/auth/login?{login_params}"

        # prompt=select_account: render a chooser over the accounts this browser
        # holds, rather than jumping straight to a login form. With no held
        # account that still lives, fall through to the login form — the
        # spec-permitted degrade. The chooser only lists accounts a switch could
        # actually front (each `sid` re-checked live), and each choice re-points
        # janua_sso then lands back here for that account; "Use another account"
        # is this same login form.
        if wants_chooser:
            held_sids = read_sessions_cookie(request.cookies.get(SESSIONS_COOKIE_NAME))
            accounts = await _resolve_held_accounts(held_sids, db)
            if accounts:
                authorize_params = {
                    "response_type": response_type,
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "scope": scope,
                }
                for key, value in (
                    ("state", state),
                    ("nonce", nonce),
                    ("code_challenge", code_challenge),
                    ("code_challenge_method", code_challenge_method),
                ):
                    if value is not None:
                        authorize_params[key] = value
                # The page language survives the chooser: the resumed /authorize
                # (and every hosted page after it) gets `ui_locales=es` back, and
                # "Use another account" is `login_url`, which already names it.
                # Only the normalized constant travels, never the raw parameter;
                # English adds nothing, so its `next` is unchanged.
                chooser_locale = page_locale(ui_locales)
                authorize_next = with_ui_locales(
                    f"/api/v1/oauth/authorize?{urlencode(authorize_params)}", chooser_locale
                )
                return HTMLResponse(
                    content=_account_chooser_html(
                        accounts,
                        authorize_next=authorize_next,
                        add_account_url=login_url,
                        client_name=client.name or "",
                        locale=chooser_locale,
                    )
                )

        return RedirectResponse(url=login_url, status_code=302)

    # INVITE-ONLY CLIENTS (2026-10-22). A client listed in INVITE_ONLY_CLIENTS
    # admits only people entitled to its product; everyone else stops here,
    # before email verification, MFA, consent or a code. The token endpoint
    # repeats the check (code AND refresh grants), so this page is the visible
    # half of the gate, not the only one. See services/invite_only_clients.py.
    if not await has_invited_access(current_user, client.client_id, db):
        _oauth_provider_shared.logger.info(
            "authorize.invite_only_refused",
            client_id=client_id,
            user=_redacted(getattr(current_user, "id", "")),
            silent=silent_auth,
        )
        if silent_auth:
            return _redirect_with_oauth_error(
                redirect_uri,
                error="access_denied",
                error_description="invite_only",
                state=state,
                client_validated=True,
            )
        other_account_url = None
        if isinstance(request, Request):
            retry = [(k, v) for k, v in request.query_params.multi_items() if k != "prompt"]
            retry_query = urlencode([*retry, ("prompt", "login")])
            other_account_url = f"/api/v1/oauth/authorize?{retry_query}"
        return render_invite_only_refusal(
            app_name=client.name or client_id,
            locale=page_locale(ui_locales),
            other_account_url=other_account_url,
        )

    # SECURITY: Require email verification for OAuth authorization
    if _oauth_provider_shared.settings.REQUIRE_EMAIL_VERIFICATION and not getattr(current_user, "email_verified", False):
        # Check grace period for new accounts
        from datetime import timedelta

        if current_user.created_at:
            grace_period = timedelta(hours=_oauth_provider_shared.settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
            grace_deadline = current_user.created_at + grace_period
            if datetime.utcnow() >= grace_deadline:
                # Silent auth must surface this as an OAuth error redirect, not
                # an HTML 403 — the caller can then decide whether to escalate
                # to interactive flow.
                if silent_auth:
                    return _redirect_with_oauth_error(
                        redirect_uri,
                        error="login_required",
                        error_description="email_verification_required",
                        state=state,
                        client_validated=True,
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required. Please verify your email before authorizing third-party applications.",
                )

    authentication_assurance = await _oauth_provider_shared.assurance_for_request(request, db, current_user)
    if await _oauth_provider_shared.user_requires_mfa(db, current_user, client.organization_id) and not has_mfa_assurance(
        authentication_assurance
    ):
        if silent_auth:
            return _redirect_with_oauth_error(
                redirect_uri,
                error="login_required",
                error_description="mfa_required",
                state=state,
                client_validated=True,
            )
        pre_login_id = secrets.token_urlsafe(24)
        # The page language follows the same rule as the unauthenticated
        # branch above: only the normalized constant is stored (the rebuilt
        # authorize URL forwards it) and named on the login URL, never the raw
        # parameter. No language asked for means no `ui_locales` at all, so the
        # login page is the English default like every other hosted page.
        mfa_ui_locale = hosted_locale(ui_locales)
        pending = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "ui_locales": mfa_ui_locale,
        }
        await redis.strict_set("oauth:pre_login:" + pre_login_id, json.dumps(pending), ex=600)
        auth_time = authentication_assurance.get("auth_time")
        if isinstance(auth_time, int) and 0 <= time.time() - auth_time <= 300:
            from app.auth.hosted_security import start_factor_flow

            return await start_factor_flow(
                request,
                db,
                current_user,
                methods=authentication_assurance.get("amr", []),
                authenticated_at=auth_time,
                auth_request_id=pre_login_id,
                client_id=client_id,
            )
        mfa_login_params = {"client_id": client_id, "auth_request_id": pre_login_id}
        if mfa_ui_locale:
            mfa_login_params[UI_LOCALES_PARAM] = mfa_ui_locale
        return RedirectResponse("/api/v1/auth/login?" + urlencode(mfa_login_params), 302)

    # Check if user has already consented to all requested scopes
    requested_scopes = ConsentService.parse_scopes(scope)
    has_consent = await ConsentService.has_consent(db, current_user.id, client_id, requested_scopes)

    # B6: first-party surfaces are pre-consented. Without this, the silent path
    # answers consent_required for a client nobody would have been asked about,
    # and the interactive path shows "MADFAM would like access to MADFAM".
    if not has_consent and _is_first_party_preconsented(client):
        _oauth_provider_shared.logger.info(
            "First-party client pre-consented — skipping consent screen",
            client_id=client_id,
            client_name=client.name,
            user_id=str(current_user.id),
        )
        has_consent = True
    elif not has_consent and public_first_party:
        # A marked public client is pre-consented for the scopes it is
        # registered for, EXCEPT reserved ones (product role scopes such as
        # `<product>:<role>`, `madfam:silent_auth` itself, and the rest of
        # `core/reserved_oauth_boundaries.py`). Those skip the screen only when
        # this person already granted them to this client on the consent
        # screen; otherwise she is asked (interactive) or the caller gets
        # consent_required (silent).
        reserved_requested = {s for s in requested_scopes if is_reserved_scope(s)}
        if not reserved_requested or await ConsentService.has_consent(
            db, current_user.id, client_id, reserved_requested
        ):
            _oauth_provider_shared.logger.info(
                "Public first-party client pre-consented — skipping consent screen",
                client_id=client_id,
                client_name=client.name,
                user_id=str(current_user.id),
            )
            has_consent = True
        else:
            _oauth_provider_shared.logger.info(
                "oauth.public_first_party.reserved_scope_needs_consent",
                client_id=client_id,
                reserved_scopes=sorted(reserved_requested),
            )

    if not has_consent:
        # OIDC prompt=none: never show an interactive consent screen. If the
        # user hasn't pre-consented, signal consent_required to the caller.
        #
        # For confidential clients this branch is unreachable on the silent
        # path by construction: `silent_auth` already required
        # `_is_silent_auth_allowed(client)`, and B6 pre-consents exactly those
        # clients. A marked PUBLIC client reaches it when it asks for a
        # reserved scope the person has not granted it yet.
        if silent_auth:
            _oauth_provider_shared.logger.info(
                "prompt=none but consent missing — emitting consent_required",
                client_id=client_id,
                user_id=str(current_user.id),
            )
            return _redirect_with_oauth_error(
                redirect_uri,
                error="consent_required",
                error_description="User has not consented to requested scopes",
                state=state,
                client_validated=True,
            )
        # Show consent screen
        csrf_token = await _oauth_provider_shared._generate_csrf_token(str(current_user.id), redis)
        scope_descriptions = ConsentService.get_scope_descriptions()

        # Build scope list for display
        scope_display = []
        for s in requested_scopes:
            if s in scope_descriptions:
                name, desc = scope_descriptions[s]
                scope_display.append({"scope": s, "name": name, "description": desc})
            else:
                scope_display.append({"scope": s, "name": s, "description": f"Access {s}"})

        # Pre-generate scope items HTML (avoids f-string bracket issues in Python <3.12)
        # SECURITY: All user-controlled content is HTML escaped to prevent XSS
        scope_items_html = ""
        for s in scope_display:
            escaped_name = html.escape(s["name"])
            escaped_desc = html.escape(s["description"])
            scope_items_html += f"""
            <div class="scope-item">
                <svg class="scope-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                </svg>
                <div class="scope-text">
                    <h4>{escaped_name}</h4>
                    <p>{escaped_desc}</p>
                </div>
            </div>
            """

        # Pre-generate redirect URI display (escaped for XSS protection)
        redirect_display = (
            redirect_uri.split("//")[1].split("/")[0] if "//" in redirect_uri else redirect_uri
        )
        escaped_redirect_display = html.escape(redirect_display)

        # SECURITY: Escape all user-controlled content for the consent HTML
        escaped_client_name = html.escape(client.name or "Unknown Application")
        escaped_user_email = html.escape(current_user.email or "")

        # Store authorization request for POST handler
        auth_request_id = secrets.token_urlsafe(16)
        auth_request_data = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        }
        # Strict, like the CSRF token above: the consent form is only rendered
        # once both are in Redis, where every replica can read them.
        await redis.strict_set(
            f"oauth:auth_request:{auth_request_id}",
            json.dumps(auth_request_data),
            ex=600,  # 10 minutes
        )

        # The form submits once: a second click (or a double-click) would post
        # the same single-use CSRF token again, and that second response — a 403
        # — is the one the browser shows, although the first one succeeded. The
        # guard is a flag, not `disabled` on the buttons: a disabled submitter
        # drops its `action` value from the form data.
        consent_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authorize {escaped_client_name} - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .consent-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 450px;
        }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ font-size: 24px; color: #333; margin-bottom: 8px; }}
        .header p {{ color: #666; font-size: 14px; }}
        .client-info {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .client-name {{ font-size: 18px; font-weight: 600; color: #333; }}
        .client-url {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .scopes-section {{ margin-bottom: 24px; }}
        .scopes-title {{ font-size: 14px; font-weight: 600; color: #333; margin-bottom: 12px; }}
        .scope-item {{
            display: flex;
            align-items: flex-start;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }}
        .scope-item:last-child {{ border-bottom: none; }}
        .scope-icon {{ width: 24px; height: 24px; margin-right: 12px; color: #667eea; }}
        .scope-text h4 {{ font-size: 14px; font-weight: 500; color: #333; }}
        .scope-text p {{ font-size: 12px; color: #666; margin-top: 2px; }}
        .user-info {{ font-size: 12px; color: #888; margin-bottom: 20px; text-align: center; }}
        .legal-links {{ text-align: center; margin-bottom: 20px; font-size: 11px; color: #888; }}
        .legal-links a {{ color: #667eea; text-decoration: none; }}
        .legal-links a:hover {{ text-decoration: underline; }}
        .buttons {{ display: flex; gap: 12px; }}
        button {{
            flex: 1;
            padding: 14px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            border: none;
        }}
        .btn-allow {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .btn-deny {{
            background: #f1f3f4;
            color: #333;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #888; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="consent-container">
        <div class="header">
            <h1>&#128274; Authorize Application</h1>
            <p>An application is requesting access to your account</p>
        </div>

        <div class="client-info">
            <div class="client-name">{escaped_client_name}</div>
            <div class="client-url">{escaped_redirect_display}</div>
        </div>

        <div class="scopes-section">
            <div class="scopes-title">This application will be able to:</div>
            {scope_items_html}
        </div>

        <div class="user-info">
            Signed in as <strong>{escaped_user_email}</strong>
        </div>

        <div class="legal-links">
            By allowing, you agree to the
            <a href="https://madfam.io/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a>
            and
            <a href="https://madfam.io/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.
        </div>

        <form method="POST" action="/api/v1/oauth/consent"
              onsubmit="if (this.dataset.submitted) {{ return false; }} this.dataset.submitted = '1'; return true;">
            <input type="hidden" name="auth_request_id" value="{auth_request_id}">
            <input type="hidden" name="csrf_token" value="{csrf_token}">
            <div class="buttons">
                <button type="submit" name="action" value="deny" class="btn-deny">Deny</button>
                <button type="submit" name="action" value="allow" class="btn-allow">Allow</button>
            </div>
        </form>

        <div class="footer">
            Powered by Janua Identity Platform
        </div>
    </div>
</body>
</html>
"""
        return HTMLResponse(content=consent_html)

    # User has consented - generate authorization code
    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "authentication_assurance": authentication_assurance,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method or "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _oauth_provider_shared._store_auth_code(auth_code, code_data, redis)

    # Update client last_used_at
    client.last_used_at = datetime.utcnow()
    await db.commit()

    # SECURITY: Redirect back to client with authorization code
    # The redirect_uri was validated at the start of this function against the client's registered URIs
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state

    callback_url = _build_safe_callback_url(redirect_uri, callback_params, client_validated=True)
    return RedirectResponse(url=callback_url, status_code=302)
