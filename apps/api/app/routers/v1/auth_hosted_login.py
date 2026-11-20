"""Hosted sign-in routes: GET /auth/login-expired, GET /auth/hosted-form.js, GET /auth/login, POST /auth/login-form, POST /auth/login-form/mfa.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, Form, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorize_resume import authorize_query
from app.auth.hosted_locale import hosted_copy, page_locale, ui_locales_query
from app.auth.hosted_locale import html_lang as hosted_html_lang
from app.auth.login_method import (
    LOGIN_METHOD_MAGIC_LINK,
    LOGIN_METHOD_PASSWORD,
    effective_login_method,
    magic_link_login_available,
)
from app.auth.mfa_enforcement import challenge_replay_key, mfa_challenge_signing_key
from app.core.redis import ResilientRedisClient
from app.database import get_db
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_hosted_pages import (
    _hosted_login_page_html,
    _login_page_switch_url,
    _render_mfa_challenge_page,
)
from app.routers.v1.auth_shared import (
    HOSTED_FORM_SCRIPT,
    HOSTED_FORM_SCRIPT_TAG,
    _busy_label_attr,
    _login_expired_url,
    _oauth_context_hidden_fields_html,
    _recover_authorize_url_from_client,
    _recovery_page_html,
    _resolve_oauth_redirect_target,
    _set_session_cookies,
    limiter,
    logger,
    router,
)
from app.services.account_lockout_service import AccountLockoutService
from app.services.client_privacy_notices import client_privacy_notice_url

from ...models import ActivityLog, User, UserStatus


@router.get("/login-expired", include_in_schema=False)
async def login_expired_page(
    client_id: Optional[str] = None,
    ui_locales: Optional[str] = None,
    db=Depends(get_db),
):
    """«This sign-in request is no longer valid», as a GET page (2026-11-19).

    The hosted sign-in POST lands here (303) when its pending request is gone
    and no registered client can restart it, so the person sees a page, not the
    error body, and a refresh does not submit the form again. The one button
    opens the client's registered origin (looked up here from the registered
    client, never taken from the request), which starts a fresh sign-in; an
    unknown or inactive client gets the words alone.
    """
    import html as _html

    from fastapi.responses import HTMLResponse

    locale = page_locale(ui_locales)
    c = hosted_copy(locale)
    restart = None
    if client_id and len(client_id) <= 255:
        restart = await _recover_authorize_url_from_client(client_id, db)
    button = ""
    if restart:
        button = (
            f'<p><a href="{_html.escape(restart, quote=True)}" style="display:block;'
            "text-align:center;padding:14px;border-radius:8px;color:white;"
            "background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);"
            f'font-weight:600;text-decoration:none">{c["session_expired_restart"]}</a></p>'
        )
    return HTMLResponse(
        content=_recovery_page_html(
            f"<h1>{c['session_expired_title']}</h1>"
            f'<p class="lead">{c["session_expired_body"]}</p>'
            f"{button}",
            title=c["sign_in_title"],
            lang=hosted_html_lang(locale),
        ),
        status_code=400,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/hosted-form.js", include_in_schema=False)
async def hosted_form_script() -> Response:
    """The one-press script every hosted form loads (see HOSTED_FORM_SCRIPT)."""
    return Response(
        content=HOSTED_FORM_SCRIPT,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


# GET /login - Render login form for OAuth flows
@router.get("/login")
async def login_page(
    request: Request,
    next: Optional[str] = None,
    auth_request_id: Optional[str] = None,
    client_id: Optional[str] = None,
    client_name: Optional[str] = None,
    login_method: Optional[str] = None,
    ui_locales: Optional[str] = None,
    db=Depends(get_db),
    redis: ResilientRedisClient = Depends(_auth_shared.get_redis),
):
    """
    Render login page for OAuth authorization flows.

    This endpoint serves an HTML login form that:
    1. Accepts email/password credentials
    2. POSTs to /api/v1/auth/login-form
    3. On success, redirects to the OAuth authorize endpoint

    Query params:
    - auth_request_id: Opaque ID for Redis-stored OAuth params (preferred for OAuth flows)
    - next: URL to redirect to after successful login (fallback for non-OAuth logins)
    - client_id: OAuth client requesting authorization
    - client_name: Human-readable name of the OAuth client
    - ui_locales: the page language /authorize normalized from the client's
      OIDC ui_locales (es or en; absent = English)
    """
    from fastapi.responses import HTMLResponse, RedirectResponse

    locale = page_locale(ui_locales)

    # Stale bookmarked login URLs carry an expired auth_request_id. Restart the
    # OAuth flow instead of rendering a form that cannot complete.
    if auth_request_id and client_id:
        stored_data = await redis.get(f"oauth:pre_login:{auth_request_id}")
        if not stored_data:
            recovered = await _recover_authorize_url_from_client(client_id, db)
            if recovered:
                logger.info(
                    "login_page.stale_auth_request_restarted",
                    auth_request_id=auth_request_id,
                    client_id=client_id,
                )
                return RedirectResponse(url=recovered, status_code=302)

    # SECURITY: Validate the 'next' URL to prevent open redirect attacks (CWE-601)
    safe_next = _auth_shared.validate_redirect_url(next or "/", default_url="/")
    # Plain: both page renderers HTML-escape the name themselves.
    app_name = client_name or "Application"
    hidden_fields = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=safe_next if not auth_request_id else None,
        ui_locale=locale,
    )

    # Which method comes first: the request's hint (carried from /authorize or
    # the switch link), then the deployment default. Magic link is offered only
    # when this deployment can mail one — app/auth/login_method.py.
    method = effective_login_method(login_method)
    switch_url = None
    if magic_link_login_available():
        switch_url = _login_page_switch_url(
            method=(
                LOGIN_METHOD_PASSWORD
                if method == LOGIN_METHOD_MAGIC_LINK
                else LOGIN_METHOD_MAGIC_LINK
            ),
            auth_request_id=auth_request_id,
            client_id=client_id,
            client_name=client_name,
            next_url=safe_next if not auth_request_id else None,
            ui_locale=locale,
        )
    html_content = _hosted_login_page_html(
        app_name=app_name,
        hidden_fields=hidden_fields,
        method=method,
        switch_url=switch_url,
        locale=locale,
        privacy_notice_url=client_privacy_notice_url(client_id),
    )
    if client_id or auth_request_id:
        import html as html_module

        recovery = "/api/v1/auth/forgot-password?" + urlencode(
            {
                "ui_locales": locale,
                "client_id": client_id or "",
                "auth_request_id": auth_request_id or "",
            }
        )
        html_content = html_content.replace(
            "/api/v1/auth/forgot-password" + ui_locales_query(locale),
            html_module.escape(recovery, quote=True),
        )
        if locale == "es":
            html_content = html_content.replace(
                hosted_copy(locale)["forgot_password"], "Crear o recuperar mi contraseña"
            )
    return HTMLResponse(content=html_content)


# Form-based login for OAuth flows (handles browser form POST, sets cookies, redirects)
@router.post("/login-form")
@limiter.limit("5/minute")
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    auth_request_id: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    ui_locales: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    redis: ResilientRedisClient = Depends(_auth_shared.get_redis),
):
    """
    Handle form-based login for OAuth authorization flows.

    This endpoint:
    1. Authenticates the user with email/password
    2. Sets access_token cookie for subsequent requests
    3. Redirects to the OAuth authorize endpoint (reconstructed from Redis) or 'next' URL

    This works without JavaScript, avoiding CSP issues with inline scripts.

    SECURITY: When auth_request_id is present, the OAuth parameters are retrieved from
    Redis and the authorize URL is reconstructed fresh, avoiding double-encoding issues
    with urlencode() that caused redirect loops. Falls back to the 'next' param for
    non-OAuth logins.
    """
    import html

    from fastapi.responses import HTMLResponse, RedirectResponse

    from app.auth.tenant_login_context import (
        LoginRequestExpired,
        login_client_context,
        login_user,
    )

    # Where the browser goes after a successful sign-in. Each outcome is logged
    # under `login_form.redirect_branch`, so a silent UX failure stays diagnosable:
    #   - redis_hit → the pending authorize request resumes (happy path)
    #   - redis_miss_oauth_recovered → the request is gone: it expired, or an
    #     earlier submit of this same form already used it (a double submit:
    #     production incident 2026-11-19, docs/runbooks/incidents/). The
    #     credentials are still checked, against the registered client the form
    #     names; on success the browser goes (303) to that client's registered
    #     origin, which starts a fresh request that the new session completes.
    #   - redis_miss_no_recovery → the request is gone and no registered client
    #     can restart it: no credential check, no session, and a 303 to the GET
    #     page that says so (`/login-expired`). Never the error body as JSON, and
    #     never a page a refresh would POST again.
    #   - non_oauth → the validated `next` URL
    #
    # The pending request is read once, by login_client_context, which also
    # enforces its client and redirect_uri binding. Reading it here a second
    # time let a submit that read it just before another one consumed it fail
    # with the error body.
    safe_next = "/"
    redirect_branch = "non_oauth"
    request_gone = False
    selected_client = None
    if auth_request_id:
        try:
            selected_client, auth_params = await login_client_context(
                db, redis, auth_request_id=auth_request_id, client_id=client_id
            )
        except LoginRequestExpired:
            request_gone = True
            logger.warning(
                "login_form.redirect_branch",
                branch="redis_miss",
                auth_request_id=auth_request_id,
                client_id_present=bool(client_id),
            )
        else:
            # Reconstruct the authorize URL fresh from the stored parameters
            # (the shared list in app/auth/authorize_resume.py, which includes
            # the RFC 8707 `resource`). Only non-None parameters.
            safe_next = f"/api/v1/oauth/authorize?{urlencode(authorize_query(auth_params))}"
            redirect_branch = "redis_hit"
            logger.info(
                "login_form.redirect_branch",
                branch=redirect_branch,
                auth_request_id=auth_request_id,
                client_id=auth_params.get("client_id"),
            )
    else:
        # Fallback: validate the 'next' URL for non-OAuth logins (CWE-601)
        safe_next = _auth_shared.validate_redirect_url(next, default_url="/")

    # Preserve full OAuth context on error-page retries (including client_id so
    # Redis expiry recovery still works after a wrong-password attempt).
    locale = page_locale(ui_locales)
    copy = hosted_copy(locale)
    error_hidden_field = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=safe_next if not auth_request_id else None,
        ui_locale=locale,
    )

    # Helper to return error page
    def make_error_page(error_message: str) -> HTMLResponse:
        error_html = f"""
<!DOCTYPE html>
<html lang="{hosted_html_lang(locale)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{copy["sign_in_title"]}</title>{HOSTED_FORM_SCRIPT_TAG}
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
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 6px; color: #333; font-weight: 500; font-size: 14px; }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
        }}
        input:focus {{ outline: none; border-color: #667eea; }}
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
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>{copy["tagline"]}</p>
        </div>
        <div class="error">{html.escape(error_message)}</div>
        <form method="POST" action="/api/v1/auth/login-form"{_busy_label_attr(copy["busy_signing_in"])}>
            {error_hidden_field}
            <div class="form-group">
                <label for="email">{copy["email_label"]}</label>
                <input type="email" id="email" name="email" value="{html.escape(email)}" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">{copy["password_label"]}</label>
                <input type="password" id="password" name="password" required>
                <div style="text-align:right;margin-top:6px"><a href="/api/v1/auth/forgot-password{ui_locales_query(locale)}" style="color:#667eea;font-size:13px;text-decoration:none">{copy["forgot_password"]}</a></div>
            </div>
            <button type="submit">{copy["sign_in_button"]}</button>
        </form>
        <div class="footer">{copy["footer"]}</div>
    </div>
</body>
</html>
"""
        if client_id or auth_request_id:
            recovery = "/api/v1/auth/forgot-password?" + urlencode(
                {
                    "ui_locales": locale,
                    "client_id": client_id or "",
                    "auth_request_id": auth_request_id or "",
                }
            )
            error_html = error_html.replace(
                "/api/v1/auth/forgot-password" + ui_locales_query(locale),
                html.escape(recovery, quote=True),
            )
        return HTMLResponse(content=error_html, status_code=401)

    if not auth_request_id:
        selected_client, _ = await login_client_context(db, redis, client_id=client_id)
    elif request_gone:
        # The request is gone, so nothing binds this POST to a client but the
        # form's own `client_id`: the same footing as a sign-in that starts
        # fresh at that client. login_client_context still requires a
        # registered, active client, and the identity pool below is that
        # client's; the browser can only be sent to its registered origin.
        recovered = None
        if client_id:
            try:
                selected_client, _ = await login_client_context(db, redis, client_id=client_id)
            except HTTPException:
                selected_client = None
            if selected_client is not None:
                recovered = await _recover_authorize_url_from_client(client_id, db)
        if not recovered:
            logger.warning(
                "login_form.redirect_branch",
                branch="redis_miss_no_recovery",
                client_id_present=bool(client_id),
            )
            return RedirectResponse(
                url=_login_expired_url(client_id=client_id, locale=locale), status_code=303
            )
        safe_next = recovered
        redirect_branch = "redis_miss_oauth_recovered"
        logger.info(
            "login_form.redirect_branch",
            branch=redirect_branch,
            client_id=client_id,
        )

    # Find user by email (without status filter to check lockout first).
    # Untenanted / staff pool (see /signin note) — this hosted flow is platform.
    # Audited 2026-09-03 with the magic-link outage: same reasoning as /signin,
    # password-authenticated and no create branch, so it stays pool-scoped.
    user = await login_user(db, email, selected_client)

    if not user:
        return make_error_page(copy["invalid_credentials"])

    # Check if account is locked
    is_locked, seconds_remaining = AccountLockoutService.is_account_locked(user)
    if is_locked:
        minutes_remaining = (seconds_remaining or 0) // 60 + 1
        return make_error_page(copy["locked_temporarily"].format(minutes=minutes_remaining))

    # Check user status after lockout check
    if user.status != UserStatus.ACTIVE or not user.is_active:
        return make_error_page(copy["invalid_credentials"])

    # Verify password
    if not user.password_hash or not _auth_shared.AuthService.verify_password(password, user.password_hash):
        # Record failed attempt
        ip_address = request.client.host if request.client else None
        is_now_locked, lock_seconds = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=ip_address
        )
        if is_now_locked:
            minutes_remaining = (lock_seconds or 0) // 60 + 1
            return make_error_page(copy["locked_now"].format(minutes=minutes_remaining))
        return make_error_page(copy["invalid_credentials"])

    from app.auth.authentication_assurance import user_requires_mfa
    from app.auth.hosted_security import start_factor_flow

    if await user_requires_mfa(db, user, getattr(selected_client, "organization_id", None)):
        if request_gone:
            # A second factor continues a pending request; this one is gone.
            # Nothing is issued: the GET page restarts sign-in at the client.
            return RedirectResponse(
                url=_login_expired_url(client_id=client_id, locale=locale), status_code=303
            )
        return await start_factor_flow(
            request,
            db,
            user,
            methods=["pwd"],
            authenticated_at=int(datetime.now(timezone.utc).timestamp()),
            auth_request_id=auth_request_id,
            client_id=client_id,
            next_url=safe_next if not auth_request_id else "/",
        )

    # No second factor pending: reset the failure counter only now, so a
    # correct password cannot clear failures counted by /login-form/mfa.
    await AccountLockoutService.reset_failed_attempts(db, user)

    # Create session and tokens
    access_token, refresh_token, session = await _auth_shared.AuthService.create_session(
        db,
        user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        authentication_methods=["pwd"],
        authenticated_at=datetime.utcnow(),
    )

    # SECURITY: Delete the Redis key after successful login (single-use)
    # This prevents replay attacks where a leaked auth_request_id could be reused
    if auth_request_id:
        try:
            await redis.delete(f"oauth:pre_login:{auth_request_id}")
        except Exception:
            pass  # Best-effort cleanup; the key has a TTL anyway

    # SECURITY: Create redirect response with validated URL (CWE-601 mitigation)
    # For OAuth flows, safe_next is the freshly-reconstructed authorize URL, or
    # (request gone) the registered origin of the client the credentials were
    # checked against; for non-OAuth flows it passed the redirect allowlist. A
    # gone request answers 303 so the browser follows with a GET.
    response = RedirectResponse(url=safe_next, status_code=303 if request_gone else 302)

    # Set session cookies (shared with the second-factor path — see helper).
    _set_session_cookies(
        response, access_token, refresh_token, user=user, session=session, request=request
    )

    return response


@router.post("/login-form/mfa")
@limiter.limit("5/minute")
async def login_form_mfa(
    request: Request,
    mfa_token: str = Form(...),
    code: str = Form(...),
    next: str = Form("/"),
    auth_request_id: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    redis: ResilientRedisClient = Depends(_auth_shared.get_redis),
):
    """Complete the second factor for the hosted OAuth browser-login flow (P1 #3).

    The GET /login → POST /login-form path renders the MFA challenge screen (via
    _render_mfa_challenge_page) when MFA is required; that screen POSTs here with
    the short-lived `mfa_token` and the user's code, plus the OAuth context. This
    endpoint verifies the factor, establishes the session cookies, and resumes
    the OAuth redirect — the browser equivalent of POST /mfa/challenge/verify
    (which returns JSON tokens and cannot set cookies or redirect).

    On an invalid code it re-renders the challenge screen (401) with a freshly
    minted challenge token so the user can retry without restarting sign-in.
    """
    from uuid import UUID

    import jwt as pyjwt

    # Decode + validate the challenge token (same contract as
    # /mfa/challenge/verify: HS256 over JWT_SECRET_KEY, type == "mfa_challenge").
    def _reject(msg: str, *, remint_for=None):
        token_for_retry = mfa_token
        if remint_for is not None:
            from app.auth.mfa_enforcement import mint_mfa_challenge_token

            token_for_retry = mint_mfa_challenge_token(
                remint_for,
                methods=payload.get("amr", ["pwd"]),
                audience=payload.get("audience"),
                authenticated_at=payload.get("auth_time", payload.get("iat")),
            )
        return _render_mfa_challenge_page(
            mfa_token=token_for_retry,
            app_name=client_name or "Application",
            auth_request_id=auth_request_id,
            client_id=client_id,
            client_name=client_name,
            next_url=next if not auth_request_id else None,
            error_message=msg,
            status_code=401,
        )

    try:
        payload = pyjwt.decode(
            mfa_token,
            mfa_challenge_signing_key(),
            algorithms=["HS256"],
            options={"require": ["sub", "type", "exp"]},
        )
    except pyjwt.ExpiredSignatureError:
        # Can't re-mint (no user yet) — the challenge is stale, restart sign-in.
        return _reject("Your verification session expired. Please sign in again.")
    except pyjwt.InvalidTokenError:
        return _reject("Invalid verification session. Please sign in again.")

    if payload.get("type") != "mfa_challenge":
        return _reject("Invalid verification session. Please sign in again.")
    used_key = challenge_replay_key(payload)
    if used_key is None:
        return _reject("Invalid verification session. Please sign in again.")

    result = await db.execute(
        select(User)
        .where(
            User.id == UUID(payload.get("sub")),
            User.status == UserStatus.ACTIVE,
            User.is_active.is_(True),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = result.scalar_one_or_none()
    if not user or not user.mfa_enabled or not user.mfa_secret:
        return _reject("Invalid verification session. Please sign in again.")

    # Wrong codes count against the same per-account lockout as passwords; a
    # locked account cannot keep guessing with a re-minted challenge.
    is_locked, _ = AccountLockoutService.is_account_locked(user)
    if is_locked:
        return _reject("Too many failed attempts. Please wait and sign in again.")

    # Verify TOTP, then fall back to a single-use backup code (shared helper).
    from app.routers.v1.mfa import consume_backup_code, consume_totp

    code_valid = await consume_totp(user, user.mfa_secret, code, redis)
    if not code_valid and consume_backup_code(user, code):
        db.add(
            ActivityLog(
                user_id=user.id,
                action="mfa_backup_code_used",
                activity_metadata={"context": "oauth_form"},
            )
        )
        code_valid = True

    if not code_valid:
        is_now_locked, _ = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=request.client.host if request.client else None
        )
        if is_now_locked:
            return _reject("Too many failed attempts. Please wait and sign in again.")
        # Wrong code — re-render with a fresh challenge token so retry works even
        # if the original is close to expiry.
        return _reject("Invalid verification code. Please try again.", remint_for=user)

    if not await redis.strict_set_nx(used_key, "1", ex=300):
        return _reject("Esta verificación ya se utilizó. Vuelve a iniciar sesión.")
    await AccountLockoutService.reset_failed_attempts(db, user)

    # Second factor cleared — create the session and resume the OAuth redirect.
    access_token, refresh_token, session = await _auth_shared.AuthService.create_session(
        db,
        user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        authentication_methods=["pwd", "otp"],
        authenticated_at=datetime.utcfromtimestamp(payload.get("auth_time", payload["iat"])),
        mfa_verified_at=datetime.utcnow(),
    )
    await _auth_shared.log_activity(db, str(user.id), "signin", {"method": "oauth_form", "mfa": "totp"}, request)

    safe_next = await _resolve_oauth_redirect_target(
        auth_request_id=auth_request_id,
        client_id=client_id,
        next_url=next,
        redis=redis,
        db=db,
    )

    # Single-use: drop the pre-login Redis key now that the session exists
    # (matches login_form). Best-effort — the key also has a TTL.
    if auth_request_id:
        try:
            await redis.delete(f"oauth:pre_login:{auth_request_id}")
        except Exception:
            pass

    from fastapi.responses import RedirectResponse

    response = RedirectResponse(url=safe_next, status_code=302)
    _set_session_cookies(
        response, access_token, refresh_token, user=user, session=session, request=request
    )
    return response
