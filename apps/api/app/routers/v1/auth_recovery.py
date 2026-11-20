"""Password recovery and change: the JSON endpoints and the hosted forgot/reset pages.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse

from fastapi import BackgroundTasks, Depends, Form, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.hosted_locale import (
    hidden_ui_locales_field,
    hosted_copy,
    hosted_locale,
    page_locale,
    password_policy_message,
    ui_locales_query,
)
from app.auth.hosted_locale import html_lang as hosted_html_lang
from app.config import settings
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.database import get_db
from app.dependencies import get_current_user
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.routers.v1.auth_shared import (
    _busy_label_attr,
    _map_mail_organization,
    _recovery_page_html,
    limiter,
    router,
    security,
)
from app.services.email_send_audit import (
    CORRELATION_HEADER,
    attach_issuance,
    is_map_destination,
    uuid_metadata,
)
from app.services.user_lookup import (
    AmbiguousEmailAcrossPools,
    log_ambiguous_email,
    resolve_user_by_email_across_pools,
)

from ...models import PasswordReset, User
from ...models import Session as UserSession


async def _dispatch_password_reset(
    email: str,
    redirect_base_raw: Optional[str],
    background_tasks: BackgroundTasks,
    db,
    *,
    email_locale: Optional[str] = None,
    client_id: Optional[str] = None,
    auth_request_id: Optional[str] = None,
    return_url: Optional[str] = None,
    mail_correlation_id=None,
):
    """Issue a user-requested reset; verified MAP mail has a durable exact receipt.

    Account absence stays neutral. A MAP audit outage fails before any account
    lookup, and native client identity pools never inherit a mail organization.
    """
    from app.auth.map_mail_hold import is_map_login_client
    from app.auth.tenant_login_context import login_client_context, login_user

    redis = await _auth_shared.get_redis() if (client_id or auth_request_id) else None
    selected_client, context = await login_client_context(
        db, redis, auth_request_id=auth_request_id, client_id=client_id, return_url=return_url
    )
    allowed = {
        value.strip()
        for value in (settings.PASSWORD_RESET_REDIRECT_ORIGINS or "").split(",")
        if value.strip()
    }
    redirect_base = redirect_base_raw if redirect_base_raw in allowed else None
    # Client/transaction destinations were validated against native registration.
    # A standalone product reset page also needs its explicit configured allowlist.
    requested_destination = context.get("redirect_uri") or return_url
    map_destination = requested_destination if is_map_destination(requested_destination) else None
    if redirect_base and is_map_destination(redirect_base):
        if selected_client is None:
            selected_client = await _auth_shared._map_mail_client(db, redirect_base, None)
        else:
            registered = selected_client.redirect_uris or []
            if isinstance(registered, str):
                registered = json.loads(registered)
            target = urlparse(redirect_base)
            if not any(isinstance(uri, str) and (
                urlparse(uri).scheme, urlparse(uri).netloc
            ) == (target.scheme, target.netloc) for uri in registered):
                raise HTTPException(400, "Recovery destination does not match native client")
        map_destination = redirect_base
    map_client = selected_client if (
        is_map_login_client(selected_client)
        and (map_destination is not None or not requested_destination)
    ) else None
    mail_audit_id, mail_org = None, None
    if map_client is not None:
        mail_org = _map_mail_organization(map_client, map_destination)
        if map_destination is None:
            uris = map_client.redirect_uris or []
            if isinstance(uris, str):
                uris = json.loads(uris)
            map_destination = next(uri for uri in uris if isinstance(uri, str) and is_map_destination(uri))
        try:
            mail_audit_id = await _auth_shared.add_intent(
                db,
                audit_id=uuid_metadata(mail_correlation_id) or uuid.uuid4(),
                source_app="crea-map",
                message_kind="password_recovery",
                trigger_kind="map_password_recovery_request",
                provenance="registered_map_recovery",
                org_id=mail_org,
            )
            await db.commit()
        except Exception as error:
            await db.rollback()
            raise HTTPException(503, "Recovery mail audit unavailable") from error

    async def not_issued():
        if mail_audit_id is not None:
            await attach_issuance(db, mail_audit_id, not_issued=True)
            await db.commit()
        return mail_audit_id

    if selected_client is not None:
        try:
            user = await login_user(db, email, selected_client, active_only=True)
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
            return await not_issued()
    else:
        user = await _auth_shared.get_user_by_email(db, email, tenant_id=None, active_only=True)
        if not user:
            try:
                user = await resolve_user_by_email_across_pools(db, email, active_only=True)
            except AmbiguousEmailAcrossPools as exc:
                log_ambiguous_email(exc, entry_point="password_reset")
                return await not_issued()
    if not (user and settings.EMAIL_ENABLED):
        return await not_issued()

    reset_token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id, token=reset_token, expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset)
    try:
        if mail_audit_id is not None:
            await db.flush()
            await attach_issuance(db, mail_audit_id, password_reset_id=reset.id)
        await db.commit()
    except Exception as error:
        await db.rollback()
        if mail_audit_id is not None:
            raise HTTPException(503, "Recovery mail issuance audit unavailable") from error
        raise

    if selected_client is not None:
        redis = redis or await _auth_shared.get_redis()
        await redis.strict_set(
            "auth:reset-context:" + hashlib.sha256(reset_token.encode()).hexdigest(),
            json.dumps(
                {
                    "client_id": selected_client.client_id,
                    "auth_request_id": auth_request_id,
                    "return_url": return_url,
                    "locale": email_locale or "es",
                }
            ),
            ex=3600,
        )

    extra = (
        {"mail_audit_id": str(mail_audit_id), "branding_redirect_url": map_destination}
        if mail_audit_id is not None else {}
    )
    background_tasks.add_task(
        _auth_shared.send_password_reset_email_task,
        user.email,
        reset_token,
        redirect_base,
        locale=email_locale or getattr(user, "locale", None),
        formality=getattr(user, "spanish_formality", None),
        org_id=mail_org or (
            getattr(selected_client, "organization_id", None)
            if selected_client else getattr(user, "tenant_id", None)
        ),
        **extra,
    )
    return mail_audit_id


async def _consume_password_reset(token: str, new_password: str, db) -> tuple[bool, str]:
    """Validate a reset token, sign the user out everywhere and set the new
    password — shared by the JSON endpoint and the hosted reset form. Token
    check precedes policy check so a dead link surfaces before a weak password
    does.

    A completed reset revokes EVERY session of the user (owner decision
    2026-10-04, J3-003): the person resetting may be signed in nowhere, and a
    session stolen before the reset must not survive it. Unlike password
    change, no session is kept.

    Order: revoke first, password second, one commit.

    1. Every live session is revoked through `AuthService.revoke_sessions`
       with `strict=True`: its refresh family, refresh JTI and access JTI go on
       the revocation list, and the rows are marked revoked (not committed yet).
       When Redis cannot take a write this raises `RedisUnavailableError`
       (503 + Retry-After, as since #695); the transaction is rolled back, so
       the password, the reset token and the rows are untouched and the same
       link works again once Redis answers.
    2. The new password and the used token are set, and the revoked rows, the
       password and the token are committed together.

    So there is no moment when the new password is set and an old session
    still refreshes: the revocation is in Redis before the password commit,
    and the rows are revoked in the same commit. The opposite order (password
    first) would leave the new password set with the old sessions live
    whenever the revocation then failed. A failure between the two steps
    leaves the user signed out with the old password and an unused link,
    which is safe and retryable.
    """
    result = await db.execute(
        select(PasswordReset)
        .where(
            PasswordReset.token == token,
            PasswordReset.used == False,
            PasswordReset.expires_at > datetime.utcnow(),
        )
        .with_for_update()
    )
    reset = result.scalar_one_or_none()

    if not reset:
        return False, "Invalid or expired reset token"

    valid, message = _auth_shared.AuthService.validate_password_strength(new_password)
    if not valid:
        return False, message

    user = await db.get(User, reset.user_id)

    # Step 1: revoke every session, strictly, before the password changes.
    try:
        revoked = await _auth_shared.AuthService.invalidate_user_sessions(
            db, user.id, reason="password_reset", strict=True, commit=False
        )
    except RedisUnavailableError:
        await db.rollback()
        raise

    # Step 2: the new password, committed with the revoked rows.
    user.password_hash = _auth_shared.AuthService.hash_password(new_password)
    # Completing a reset proves control of the mailbox the token was mailed
    # to — the same evidence the magic-link flow auto-verifies on. Without
    # this, an unverified account recovers its password only to be blocked
    # minutes later at the authorize endpoint's REQUIRE_EMAIL_VERIFICATION
    # gate (observed live 2026-08-13).
    user.email_verified = True

    reset.used = True
    reset.used_at = datetime.utcnow()

    await db.commit()

    # A sign-in that checked the OLD password while this reset ran can commit
    # its session after step 1's query. Sweep once more now that the new
    # password is committed. Best-effort Redis writes are enough here: the
    # row is revoked and `/auth/refresh` refuses a row that is not live.
    revoked += await _auth_shared.AuthService.invalidate_user_sessions(db, user.id, reason="password_reset")

    await _auth_shared.log_activity(db, str(user.id), "password_reset", {"sessions_revoked": revoked})
    await _auth_shared.log_audit_event(db, str(user.id), "password_reset", {"sessions_revoked": revoked})

    return True, "Password successfully reset"


@router.post("/password/forgot")
@limiter.limit("3/hour")  # Strict rate limiting for password reset requests
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    """Request a reset; the neutral UUID never proves account existence."""
    correlation = uuid.uuid4()
    response.headers[CORRELATION_HEADER] = str(correlation)
    await _dispatch_password_reset(
        forgot_data.email,
        forgot_data.redirect_base,
        background_tasks,
        db,
        client_id=forgot_data.client_id,
        auth_request_id=forgot_data.auth_request_id,
        return_url=forgot_data.return_url,
        mail_correlation_id=correlation,
    )
    # Don't reveal if user exists
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/password/reset")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password with token"""
    ok, message = await _consume_password_reset(request.token, request.new_password, db)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


def _reset_form_body(token: str, error: Optional[str] = None, locale: str = "en") -> str:
    """The reset form. `error` is plain text (escaped here); `locale` is a
    `page_locale` value, and English renders the form it always rendered."""
    import html as html_mod

    c = hosted_copy(locale)
    error_html = f'<div class="alert-error">{html_mod.escape(error)}</div>' if error else ""
    return f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>{c["reset_tagline"]}</p></div>
        {error_html}
        <form method="POST" action="/api/v1/auth/reset-password-form"{_busy_label_attr(c["busy_saving"])}>
            <input type="hidden" name="token" value="{html_mod.escape(token)}">{hidden_ui_locales_field(locale)}
            <div class="form-group">
                <label for="new_password">{c["reset_new_password_label"]}</label>
                <input type="password" id="new_password" name="new_password" required autocomplete="new-password" autofocus>
            </div>
            <div class="form-group">
                <label for="confirm_password">{c["reset_confirm_label"]}</label>
                <input type="password" id="confirm_password" name="confirm_password" required autocomplete="new-password">
            </div>
            <p class="hint">{c["reset_policy_hint"]}</p>
            <button type="submit">{c["reset_button"]}</button>
        </form>
        <div class="footer">{c["footer"]}</div>
    """


def _reset_page_html(body: str, locale: str) -> str:
    """The recovery shell in the reset page's language (title and `lang`)."""
    return _recovery_page_html(
        body, title=hosted_copy(locale)["recovery_title"], lang=hosted_html_lang(locale)
    )


@router.get("/forgot-password")
async def forgot_password_page(
    ui_locales: Optional[str] = None,
    client_id: Optional[str] = None,
    auth_request_id: Optional[str] = None,
    return_url: Optional[str] = None,
):
    """Hosted forgot-password page, linked from the hosted login page.

    Before this page existed the hosted login form offered no recovery
    affordance at all — a user who forgot their password had nowhere to go
    (observed live 2026-08-13). `ui_locales` is the login page's language,
    carried on its "Forgot your password?" link (English when absent)."""
    from fastapi.responses import HTMLResponse

    locale = page_locale(ui_locales)
    c = hosted_copy(locale)
    body = f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>{c["recovery_tagline"]}</p></div>
        <p class="lead">{c["recovery_lead"]}</p>
        <form method="POST" action="/api/v1/auth/forgot-password-form"{_busy_label_attr(c["busy_sending"])}>
            {hidden_ui_locales_field(locale)}
            <input type="hidden" name="client_id" value="{__import__("html").escape(client_id or "", quote=True)}">
            <input type="hidden" name="auth_request_id" value="{__import__("html").escape(auth_request_id or "", quote=True)}">
            <input type="hidden" name="return_url" value="{__import__("html").escape(return_url or "", quote=True)}">
            <div class="form-group">
                <label for="email">{c["email_label"]}</label>
                <input type="email" id="email" name="email" required autocomplete="email" autofocus>
            </div>
            <button type="submit">{c["recovery_button"]}</button>
        </form>
        <div class="footer">{c["footer"]}</div>
    """
    return HTMLResponse(
        content=_recovery_page_html(body, title=c["recovery_title"], lang=hosted_html_lang(locale))
    )


@router.post("/forgot-password-form")
@limiter.limit("3/hour")  # Same budget as the JSON endpoint — one recovery surface
async def forgot_password_form(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    ui_locales: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    auth_request_id: Optional[str] = Form(None),
    return_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Browser half of /password/forgot: same dispatch, rendered as a page.
    No redirect_base — the emailed link lands on the API-hosted reset page.
    The page's language (`ui_locales`) is also the reset mail's."""
    import html as html_mod

    from fastapi.responses import HTMLResponse

    locale = page_locale(ui_locales)
    c = hosted_copy(locale)
    correlation = uuid.uuid4()
    await _dispatch_password_reset(
        email,
        None,
        background_tasks,
        db,
        email_locale=hosted_locale(ui_locales),
        client_id=client_id or None,
        auth_request_id=auth_request_id or None,
        return_url=return_url or None,
        mail_correlation_id=correlation,
    )
    retry_params = {"ui_locales": locale}
    retry_params.update({k: v for k, v in {
        "client_id": client_id, "auth_request_id": auth_request_id, "return_url": return_url,
    }.items() if v})
    retry_url = "/api/v1/auth/forgot-password?" + urlencode(retry_params)
    body = f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>{c["recovery_tagline"]}</p></div>
        <div class="alert-ok">{c["recovery_sent"].format(email=html_mod.escape(email))}</div>
        <p class="lead">{c["recovery_retry"].format(retry_url=html_mod.escape(retry_url, quote=True))}</p>
        <div class="footer">{c["footer"]}</div>
    """
    return HTMLResponse(
        content=_recovery_page_html(body, title=c["recovery_title"], lang=hosted_html_lang(locale)),
        headers={CORRELATION_HEADER: str(correlation), "cache-control": "no-store"},
    )


@router.get("/reset-password")
async def reset_password_page(token: Optional[str] = None, ui_locales: Optional[str] = None):
    """Hosted reset page — the reset email's default landing since 2026-08-13.

    The previous default pointed at the product frontend, whose
    /auth/reset-password route sits behind the login wall: a user who cannot
    log in (the entire premise of a reset) was bounced to /login and the
    token was lost. This page is served by the API itself, on the same host
    that mints the token, so it can never be auth-walled away.

    `ui_locales` is the reset email's language, carried on its link (English
    when absent); the form carries it on to every page it answers with."""
    from fastapi.responses import HTMLResponse

    locale = page_locale(ui_locales)
    c = hosted_copy(locale)
    if not token:
        forgot_url = f"/api/v1/auth/forgot-password{ui_locales_query(locale)}"
        body = f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>{c["reset_tagline"]}</p></div>
        <div class="alert-error">{c["reset_missing_token"]}</div>
        <p class="lead">{c["reset_missing_token_retry"].format(forgot_url=forgot_url)}</p>
        <div class="footer">{c["footer"]}</div>
        """
        return HTMLResponse(content=_reset_page_html(body, locale), status_code=400)
    return HTMLResponse(
        content=_reset_page_html(_reset_form_body(token, locale=locale), locale),
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post("/reset-password-form")
@limiter.limit("10/hour")
async def reset_password_form(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    ui_locales: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Browser half of /password/reset: identical token validation and policy
    via _consume_password_reset, rendered as pages instead of JSON."""
    from fastapi.responses import HTMLResponse

    locale = page_locale(ui_locales)
    c = hosted_copy(locale)

    if new_password != confirm_password:
        return HTMLResponse(
            content=_reset_page_html(
                _reset_form_body(token, c["reset_mismatch"], locale=locale), locale
            ),
            status_code=400,
        )

    ok, message = await _consume_password_reset(token, new_password, db)
    if ok:
        redis = await _auth_shared.get_redis()
        context_key = "auth:reset-context:" + hashlib.sha256(token.encode()).hexdigest()
        raw_context = await redis.strict_get(context_key)
        if raw_context:
            from app.auth.tenant_login_context import login_client_context

            context = json.loads(raw_context)
            await login_client_context(
                db, redis, client_id=context["client_id"], return_url=context.get("return_url")
            )
            await redis.strict_delete(context_key)
            target = context.get("return_url")
            if not target:
                target = "/api/v1/auth/login?" + urlencode(
                    {
                        "client_id": context["client_id"],
                        "auth_request_id": context.get("auth_request_id") or "",
                        "ui_locales": "es",
                    }
                )
            import html

            return HTMLResponse(
                content=_recovery_page_html(
                    "<h1>Contraseña guardada</h1><p>Tu contraseña ya está lista. Tus sesiones anteriores se cerraron.</p>"
                    '<a href="' + html.escape(target, quote=True) + '">Volver a entrar al MAP</a>',
                    lang="es",
                ),
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )
        body = f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>{c["reset_done_tagline"]}</p></div>
        <div class="alert-ok">{c["reset_done"]}</div>
        <div class="footer">{c["footer"]}</div>
        """
        return HTMLResponse(content=_reset_page_html(body, locale))

    if message == "Invalid or expired reset token":
        forgot_url = f"/api/v1/auth/forgot-password{ui_locales_query(locale)}"
        body = f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>{c["reset_tagline"]}</p></div>
        <div class="alert-error">{c["reset_expired"]}</div>
        <p class="lead">{c["reset_expired_retry"].format(forgot_url=forgot_url)}</p>
        <div class="footer">{c["footer"]}</div>
        """
        return HTMLResponse(content=_reset_page_html(body, locale), status_code=400)

    # Policy rejection — the token is still live, re-render the form with the
    # policy message so the user can try a stronger password on the same link.
    # The message is translated here, not at its source: the JSON endpoint
    # keeps returning the English policy text.
    return HTMLResponse(
        content=_reset_page_html(
            _reset_form_body(token, password_policy_message(message, locale), locale=locale),
            locale,
        ),
        status_code=400,
    )


@router.post("/password/change")
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Change password for authenticated user"""
    # Verify current password
    if not _auth_shared.AuthService.verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password
    valid, message = _auth_shared.AuthService.validate_password_strength(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Update password
    current_user.password_hash = _auth_shared.AuthService.hash_password(request.new_password)
    await db.commit()

    # SECURITY: Revoke all sessions except current one to prevent stolen session reuse
    # Extract current session ID from the JWT claims
    current_session_id = None
    try:
        token = credentials.credentials
        payload = await _auth_shared.AuthService.identify_token(token, token_type="access")
        if payload:
            # Find current session by access token JTI
            result = await db.execute(
                select(UserSession).where(UserSession.access_token_jti == payload.get("jti"))
            )
            current_session = result.scalar_one_or_none()
            if current_session:
                current_session_id = current_session.id
    except Exception:
        pass  # If we can't determine current session, revoke all

    # Every OTHER session's refresh-token family stops refreshing and its
    # current access token is blacklisted; the session that changed the
    # password stays signed in.
    await _auth_shared.AuthService.invalidate_user_sessions(
        db, current_user.id, exclude_session_id=current_session_id, reason="password_change"
    )

    # Log activity
    await _auth_shared.log_activity(db, str(current_user.id), "password_change", {}, req)
    await _auth_shared.log_audit_event(db, str(current_user.id), "password_change", {}, req)

    return {"message": "Password successfully changed"}
