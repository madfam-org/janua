"""Session routes: register/login aliases, logout, refresh, sign-out, account switching and GET /auth/me.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

from typing import Optional
from urllib.parse import parse_qs, urlparse

from fastapi import BackgroundTasks, Depends, Form, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.hosted_locale import DEFAULT_HOSTED_LOCALE, UI_LOCALES_PARAM, hosted_copy, page_locale
from app.auth.hosted_locale import html_lang as hosted_html_lang
from app.auth.sessions_cookie import (
    SESSIONS_COOKIE_NAME,
    clear_sessions_cookie,
    read_sessions_cookie,
    remove_sid,
    set_sessions_cookie,
)
from app.auth.sso_cookie import (
    SSO_COOKIE_NAME,
    clear_sso_cookie,
    mint_sso_cookie_value,
    revoke_sso_cookie_session,
    sso_cookie_kwargs,
)
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_current_user_for_sign_out
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_schemas import (
    RefreshTokenRequest,
    SignInRequest,
    SignInResponse,
    SignUpRequest,
    TokenResponse,
    UserResponse,
)
from app.routers.v1.auth_shared import limiter, logger, router, security
from app.routers.v1.auth_signin import sign_in, sign_up

from ...models import Session as UserSession
from ...models import User


# Alias for /signup (the TypeScript SDK and @janua/ui components post to /register)
@router.post("/register", response_model=SignInResponse)
@limiter.limit("3/minute")  # Same strict rate limiting as /signup
async def register(
    request: Request,
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new user account (alias for /signup)"""
    return await sign_up(request, signup_data, background_tasks, db)


# Alias for /signin (tests expect /login)
@router.post("/login", response_model=SignInResponse)
@limiter.limit("5/minute")
async def login(credentials: SignInRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and get tokens (alias for /signin)"""
    return await sign_in(credentials, request, db)


# Alias for /signout (tests expect /logout)
@router.post("/logout")
async def logout(
    req: Request,
    response: Response,
    current_user: User = Depends(get_current_user_for_sign_out),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Sign out current session (alias for /signout).

    SSO (J5/R1): this is the endpoint `@madfam/janua-next` calls from its logout
    route, and it relays the `janua_sso` deletion this sets back to the browser —
    the mirror of the relay that delivered the cookie. See `sign_out`.
    """
    return await sign_out(current_user, credentials, db, req=req, response=response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    result = await _auth_shared.AuthService.refresh_tokens(db, request.refresh_token)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token, refresh_token = result

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/signout")
async def sign_out(
    current_user: User = Depends(get_current_user_for_sign_out),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    req: Request = None,
    response: Response = None,
):
    """Sign out current session.

    SSO (J5/R1): besides the existing blacklist + session revocation, this
    revokes whatever `janua_sso` references and deletes the cookie with the same
    Domain and Path it was set with. Both halves are needed: deleting the cookie
    only clears this browser, while revoking the `sessions` row is what stops a
    copy of the cookie taken earlier. The signature is verified before anything
    is revoked, so a forged cookie cannot end someone else's session.

    `req`/`response` default to None so the existing direct callers and tests,
    which invoke this as a plain coroutine, keep working unchanged.
    """
    token = credentials.credentials
    # identify_token, not verify_token: sign-out must still revoke the session
    # row and clear cookies while Redis is down (see AuthService.identify_token).
    payload = await _auth_shared.AuthService.identify_token(token, token_type="access")

    if payload:
        # Revoke this session: its row, its refresh-token family (so
        # /auth/refresh refuses it) and its access token's JTI. Best-effort:
        # sign-out must never fail on bookkeeping.
        try:
            # The presented access token, even when no row is found for it.
            await _auth_shared.AuthService.revoke_access_token(payload, reason="user_logout")
        except Exception:
            logger.warning("Failed to blacklist the access token on sign-out", exc_info=True)

        try:
            result = await db.execute(
                select(UserSession).where(UserSession.access_token_jti == payload["jti"])
            )
            session = result.scalar_one_or_none()

            if session:
                await _auth_shared.AuthService.revoke_sessions([session], reason="user_logout")
                await db.commit()
        except Exception:
            logger.warning("Failed to revoke the session row on sign-out", exc_info=True)

    # SSO (J5/R1): revoke the estate session and clear its cookie. Best-effort,
    # exactly like the blacklisting above — logout must never fail on this.
    try:
        if req is not None and await revoke_sso_cookie_session(req.cookies.get("janua_sso"), db):
            await db.commit()
    except Exception:
        pass
    if response is not None:
        clear_sso_cookie(response)

    # Log activity (best-effort, don't fail logout)
    try:
        await _auth_shared.log_activity(db, str(current_user.id), "signout", {})
    except Exception:
        pass
    try:
        await _auth_shared.log_audit_event(db, str(current_user.id), "signout", {})
    except Exception:
        pass

    return {"message": "Successfully signed out"}


class SwitchSessionRequest(BaseModel):
    """Body of POST /auth/switch-session and the per-account sign-out."""

    sid: str = Field(..., description="Session id (sessions.id) to bring to the front")
    next: Optional[str] = Field(
        None, description="Where to send the browser after switching (validated)"
    )
    return_sid: bool = Field(
        False,
        description=(
            "Two-tab focus opt-in. When true, the switch redirect carries the "
            "chosen sid back to the landing page as a URL FRAGMENT "
            "(`#janua_sid=<sid>`) so a tab can store it in sessionStorage and "
            "assert it per-tab via the `X-Janua-Session` header. A fragment is "
            "never sent to any server, so this leaks the sid to no host log; and "
            "the sid is only ever a reference gated by the held-set, so it "
            "escalates nothing (see sessions_cookie.py / the authorize resolver). "
            "Default false keeps the browser-wide chooser flow byte-for-byte."
        ),
    )


def _held_sids(request: Optional[Request]) -> list[str]:
    """The verified list of session ids `janua_sessions` carries on this request."""
    if request is None:
        return []
    return read_sessions_cookie(request.cookies.get(SESSIONS_COOKIE_NAME))


def _fronted_sid(request: Optional[Request]) -> Optional[str]:
    """The `sid` `janua_sso` currently points at, if the cookie verifies.

    Signature/type/expiry are enforced by the SSO token verifier; a forged or
    wrong-typed value yields None. This does NOT prove the row is live — callers
    that re-front or revoke re-read the row — it only says which sid is fronted.
    """
    if request is None:
        return None
    from app.auth.sso_cookie import SSO_TOKEN_TYPE
    from app.core.jwt_manager import jwt_manager

    value = request.cookies.get(SSO_COOKIE_NAME)
    if not value:
        return None
    payload = jwt_manager.verify_token(value, token_type=SSO_TOKEN_TYPE, verify_audience=False)
    if not payload:
        return None
    sid = payload.get("sid")
    return str(sid) if sid else None


@router.post("/switch-session")
async def switch_session(
    body: SwitchSessionRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Bring a held estate account to the front, without re-authentication.

    Multi-account (Layer 3): re-points `janua_sso` at `body.sid` — but only when
    that sid is BOTH vouched for by this browser's signed `janua_sessions` cookie
    AND still a live, active `sessions` row of an active user. The signed cookie
    stops a browser inventing a sid it was never granted; the live-row re-read is
    what actually authorises the switch, so a revoked or expired session in the
    held list can never be fronted. No bearer is needed and none is minted — the
    switch only moves the pointer among sessions already proven live.

    On success `janua_sso` is set to the chosen sid and the response 302-redirects
    to a validated `next` (default `/`). A sid not in the held set, or whose row is
    not live, is refused with 400 rather than silently ignored.
    """
    return await _switch_to_held_session(
        req,
        db,
        sid=body.sid,
        next_url=getattr(body, "next", None),
        return_sid=bool(getattr(body, "return_sid", False)),
    )


async def _switch_to_held_session(
    req: Request,
    db,
    *,
    sid: str,
    next_url: Optional[str],
    return_sid: bool,
):
    """Shared core of the JSON and form switch routes. Every guard lives here.

    Raises HTTPException(400) for a sid that is not in the signed held-set or
    whose row is not live; otherwise returns the 302 that re-points `janua_sso`.
    """
    held = _held_sids(req)
    if sid not in held:
        raise HTTPException(
            status_code=400,
            detail="invalid_request: session is not held by this browser",
        )

    user, session = await _auth_shared.resolve_session_by_id(sid, db)
    if user is None or session is None:
        raise HTTPException(
            status_code=400,
            detail="invalid_request: session is not active",
        )

    from fastapi.responses import RedirectResponse

    safe_next = _auth_shared.validate_redirect_url(next_url or "/", default_url="/")
    if return_sid:
        # Two-tab focus: hand the chosen sid to the landing page as a FRAGMENT.
        # Appended AFTER validation, and only to the already-validated same-origin
        # target, so it cannot be used to smuggle a redirect. A fragment is never
        # transmitted to a server, so the sid appears in no request line or log;
        # the tab reads it client-side, stores it in sessionStorage, and strips
        # it from the address bar. The sid is only a reference the held-set gates
        # (see the authorize resolver), so surfacing it here escalates nothing.
        # `validate_redirect_url` returns fragment-free targets for the paths this
        # flow uses; if one ever carried its own fragment we keep ours last, which
        # is the one the tab reads.
        safe_next = f"{safe_next}#janua_sid={session.id}"
    redirect = RedirectResponse(url=safe_next, status_code=302)
    # Re-point the fronted-session cookie on the redirect that is actually sent.
    # `janua_sessions` is left intact — the held set does not change on a switch,
    # only which one is fronted.
    redirect.set_cookie(
        key=SSO_COOKIE_NAME,
        value=mint_sso_cookie_value(str(user.id), str(session.id)),
        **sso_cookie_kwargs(),
    )
    return redirect


def _form_post_is_same_origin(req: Request) -> bool:
    """Origin check for a cookie-authenticated, form-encoded POST (CSRF defence).

    `janua_sso` and `janua_sessions` are SameSite=Lax, so a cross-SITE form post
    carries neither and is refused by the held-set check anyway. Same-site is
    wider than same-origin, though: every host under the estate's cookie Domain
    is the same site. So the form route also requires the request's `Origin`
    (or, when a browser omits it, `Referer`) to name Janua itself: this
    request's own Host or the configured public origin. A request with neither
    header, or with `Origin: null`, is refused.
    """
    source = req.headers.get("origin")
    if not source or source == "null":
        source = req.headers.get("referer")
    if not source:
        return False
    source_host = urlparse(source).netloc.lower()
    if not source_host:
        return False
    allowed = {req.headers.get("host", "").lower()}
    public_host = urlparse(settings.public_base_url or "").netloc.lower()
    if public_host:
        allowed.add(public_host)
    allowed.discard("")
    return source_host in allowed


def _switch_page_locale(next_url: Optional[str]) -> str:
    """The page language of a chooser click, read from its ``next``.

    The chooser posts only ``sid`` and ``next``; ``next`` is the rebuilt
    ``/oauth/authorize`` request, which carries ``ui_locales=es`` when the
    chooser spoke Spanish (and nothing for English). The value is posted by the
    browser, so it is only ever normalized to a page locale constant.
    """
    if not next_url or not isinstance(next_url, str):
        return DEFAULT_HOSTED_LOCALE
    requested = parse_qs(urlparse(next_url).query).get(UI_LOCALES_PARAM, [None])[0]
    return page_locale(requested)


def _switch_refused_html(reason_key: str, locale: str = DEFAULT_HOSTED_LOCALE) -> str:
    """A short page for a refused chooser click (the browser is on a form post).

    ``reason_key`` names a ``switch_refused_*`` row of ``HOSTED_COPY``;
    ``locale`` is a page locale constant. English is byte for byte the page this
    route answered before it spoke Spanish.
    """
    copy = hosted_copy(locale)
    return f"""<!DOCTYPE html>
<html lang="{hosted_html_lang(locale)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{copy["chooser_title"]}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #f5f5f7; color: #333; display: flex; align-items: center;
               justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
        .box {{ background: white; border-radius: 12px; padding: 32px; max-width: 420px;
               box-shadow: 0 8px 30px rgba(0,0,0,0.12); }}
        h1 {{ font-size: 20px; margin: 0 0 12px; }}
        p {{ font-size: 14px; line-height: 1.5; color: #555; margin: 0; }}
    </style>
</head>
<body>
    <div class="box">
        <h1>{copy["switch_refused_heading"]}</h1>
        <p>{copy[reason_key]} {copy["switch_refused_next_step"]}</p>
    </div>
</body>
</html>
"""


@router.post("/switch-session/form")
async def switch_session_form(
    req: Request,
    sid: str = Form(...),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Form-encoded twin of `/switch-session`, for the `prompt=select_account` chooser.

    The chooser is a plain HTML page, so each account is a top-level
    `application/x-www-form-urlencoded` POST; the JSON route answers those with
    422. This route accepts the form, applies the SAME guards (sid in the signed
    held-set AND a live row — `_switch_to_held_session`), adds an Origin check
    because it is a cookie-authenticated form post, and on success 302s to the
    validated `next` — the chooser sets it to the original `/authorize` request,
    so the authorization flow resumes for the chosen account. Refusals answer a
    short HTML page, never a JSON body, because a person is looking at it.
    """
    from fastapi.responses import HTMLResponse

    # A refusal speaks the chooser's language (from `next`); English otherwise.
    locale = _switch_page_locale(next)
    if not _form_post_is_same_origin(req):
        logger.warning("switch_session_form.rejected", reason="cross_origin")
        return HTMLResponse(
            _switch_refused_html("switch_refused_cross_origin", locale),
            status_code=403,
        )
    try:
        redirect = await _switch_to_held_session(req, db, sid=sid, next_url=next, return_sid=False)
        # An explicit chooser click must survive the resumed authorize request.
        # A newer hosted session otherwise outranks the chosen older held row.
        # Clear its browser credentials on this SAME response, using the exact
        # Domain/Path of _set_session_cookies; do not revoke any held session or
        # change ordinary cookie precedence outside this explicit chooser flow.
        delete_kwargs: dict = {"path": "/", "secure": True, "samesite": "lax"}
        if settings.COOKIE_DOMAIN:
            delete_kwargs["domain"] = settings.COOKIE_DOMAIN
        redirect.delete_cookie("janua_access_token", httponly=False, **delete_kwargs)
        redirect.delete_cookie("janua_refresh_token", httponly=True, **delete_kwargs)
        return redirect
    except HTTPException as exc:
        logger.info("switch_session_form.rejected", reason=str(exc.detail))
        return HTMLResponse(
            _switch_refused_html("switch_refused_not_held", locale),
            status_code=exc.status_code,
        )


@router.post("/sessions/sign-out-one")
async def sign_out_one_account(
    body: SwitchSessionRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Sign out ONE held account, keeping the others signed in.

    Removes `body.sid` from `janua_sessions` and revokes that `sessions` row
    (best-effort — the removal from the held set is the half that clears this
    browser, the revocation is the half that stops a copy of the pointer taken
    earlier). If the removed account was the fronted one, `janua_sso` is
    re-pointed at the most-recent remaining held account, or cleared when none
    remain. The sid must be in the held set; an unheld sid is refused so this
    endpoint cannot be used to revoke arbitrary sessions.
    """
    held = _held_sids(req)
    if body.sid not in held:
        raise HTTPException(
            status_code=400,
            detail="invalid_request: session is not held by this browser",
        )

    # Revoke the row (best-effort; never fail sign-out on it).
    try:
        if await _auth_shared.revoke_sso_session(body.sid, db):
            await db.commit()
    except Exception:
        logger.warning("Failed to revoke session on per-account sign-out", exc_info=True)

    remaining = remove_sid(held, body.sid)
    set_sessions_cookie(response, remaining)

    # If we just signed out the fronted account, re-front another held one.
    if _fronted_sid(req) == body.sid:
        new_front = None
        for candidate in reversed(remaining):
            user, session = await _auth_shared.resolve_session_by_id(candidate, db)
            if user is not None and session is not None:
                new_front = (user, session)
                break
        if new_front is not None:
            user, session = new_front
            response.set_cookie(
                key=SSO_COOKIE_NAME,
                value=mint_sso_cookie_value(str(user.id), str(session.id)),
                **sso_cookie_kwargs(),
            )
        else:
            clear_sso_cookie(response)

    return {"message": "Signed out of the account", "remaining": len(remaining)}


@router.post("/sessions/sign-out-all")
async def sign_out_all_accounts(
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Sign out of EVERY held account and clear both estate cookies.

    Revokes every `sessions` row named in `janua_sessions` (plus whatever
    `janua_sso` points at, in case it drifted from the list), then deletes both
    cookies with the exact Domain/Path they were set with. Best-effort revocation
    per row, exactly like `sign_out` — clearing the browser must never fail
    because one revocation could not complete.
    """
    held = _held_sids(req)
    fronted = _fronted_sid(req)
    to_revoke = list(dict.fromkeys([*held, *([fronted] if fronted else [])]))

    revoked_any = False
    for sid in to_revoke:
        try:
            if await _auth_shared.revoke_sso_session(sid, db):
                revoked_any = True
        except Exception:
            logger.warning("Failed to revoke a session on sign-out-all", exc_info=True)
    if revoked_any:
        try:
            await db.commit()
        except Exception:
            logger.warning("Failed to commit revocations on sign-out-all", exc_info=True)

    clear_sso_cookie(response)
    clear_sessions_cookie(response)
    return {"message": "Signed out of all accounts", "revoked": len(to_revoke)}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        email_verified=current_user.email_verified,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        profile_image_url=current_user.profile_image_url,
        is_admin=getattr(current_user, "is_admin", False),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_sign_in_at=current_user.last_sign_in_at,
    )
