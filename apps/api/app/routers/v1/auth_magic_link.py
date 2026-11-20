"""Sign-in link redemption and the hosted link form: GET/POST /auth/magic-link/callback, POST /auth/magic-link/verify, POST /auth/login-form/magic-link.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import BackgroundTasks, Depends, Form, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorize_resume import authorize_query, is_resource_bound
from app.auth.hosted_locale import DEFAULT_HOSTED_LOCALE, hosted_copy, hosted_locale, page_locale
from app.auth.hosted_locale import html_lang as hosted_html_lang
from app.auth.login_method import (
    LOGIN_METHOD_MAGIC_LINK,
    LOGIN_METHOD_PASSWORD,
    magic_link_login_available,
)
from app.config import settings
from app.core.redis import ResilientRedisClient
from app.database import get_db
from app.routers.v1 import auth_magic_link_issue as _auth_magic_link_issue
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_hosted_pages import _hosted_login_page_html, _login_page_switch_url
from app.routers.v1.auth_magic_link_pages import (
    _check_inbox_page_html,
    _magic_link_browser_binding,
    _magic_link_by_token,
    _magic_link_dead_page,
    _magic_link_interstitial_html,
    _remember_magic_link_spend,
    _set_magic_link_browser_cookie,
    _spent_here_moments_ago,
)
from app.routers.v1.auth_schemas import (
    MagicLinkRequest,
    SignInResponse,
    TokenResponse,
    UserResponse,
    VerifyMagicLinkRequest,
)
from app.routers.v1.auth_shared import (
    _oauth_context_hidden_fields_html,
    _recover_authorize_url_from_client,
    _recovery_page_html,
    _set_session_cookies,
    logger,
    router,
)
from app.services.client_privacy_notices import client_privacy_notice_url
from app.services.invite_only_clients import is_invite_only

from ...models import MagicLink, User, UserStatus


@router.get("/magic-link/callback")
async def magic_link_callback_interstitial(
    token: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Render the scanner-proof interstitial. SPENDS NOTHING.

    ⚠️ THE TOKEN IS ONE-TIME, SO A GET MUST CONSUME NOTHING.

    Mail clients and their safe-link / preview scanners GET every URL in an
    email. Until 2026-09-06 this route VERIFIED on the GET: it burned
    `used_at`, minted a session and redirected. A scanner's fetch therefore
    spent the link and the human's own click replayed a spent token —
    "could not sign in". That is not hypothetical: it is the failure this
    estate already hit once (nauta portal, first real ceremony 2026-08-16),
    and it is the reason `@madfam/janua-next` splits its own magic-link route
    exactly this way. This route was written for the no-`redirect_url`
    fallback and never received the same treatment; the J6 hosted hop makes it
    the PRIMARY path for the client's brand hosts, so it had to be fixed
    before that traffic arrives.

    The split is the entire security property:
      • GET (here) renders a one-button page and spends NOTHING.
      • POST (below) is the ONLY place the token is exchanged.

    Do NOT "simplify" this back into a GET that verifies.

    Validation that only READS is still done here, so an already-dead link says
    so immediately (and why) instead of showing a button that cannot work.

    THE BROWSER BINDING (2026-10-07). This GET gives the browser an HttpOnly
    `janua_ml_browser` cookie if it has none; the POST that spends the link
    records it. A browser that spent this link moments ago and opens it again
    (they re-open the email when the first attempt seemed to fail) gets the
    button again instead of the dead page; its press then finishes the
    hand-off. Everyone else still gets the dead page.
    """
    from fastapi.responses import HTMLResponse

    if not token:
        return _magic_link_dead_page(None)

    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token == token,
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > datetime.utcnow(),
        )
    )
    magic_link = result.scalar_one_or_none()
    binding = _magic_link_browser_binding(request)
    if not magic_link:
        dead = await _magic_link_by_token(db, token)
        if not await _spent_here_moments_ago(dead, binding):
            return _magic_link_dead_page(dead)
        magic_link = dead

    response = HTMLResponse(
        content=_magic_link_interstitial_html(token, magic_link.redirect_url),
        status_code=200,
        headers={
            "cache-control": "no-store",
            # The one-time token is in this URL's query string. `no-referrer`
            # keeps it out of any Referer header this page's own assets send.
            "referrer-policy": "no-referrer",
            "x-robots-tag": "noindex, nofollow",
        },
    )
    if binding is None:
        # Never rotate an existing value: a press already in flight was
        # recorded against it.
        _set_magic_link_browser_cookie(response)
    return response


@router.post("/magic-link/callback")
async def magic_link_callback(
    token: Optional[str] = Form(default=None),
    req: Request = None,
    db: Session = Depends(get_db),
):
    """Spend the clicked magic link and forward to the product with a session.

    The ONLY place the one-time token is exchanged — reached by the
    interstitial's button, never by a scanner (see the GET above).

    A link in an email is a GET, and only Janua can trade the one-time magic
    token for a session — so without this route the whole passwordless flow
    had no door to knock on: `/magic-link/verify` is a POST returning JSON,
    which no mail client can reach. Products (nauta's /portal/verify) expect
    to be handed the access token on the query string; that contract is why
    the token travels this way rather than in a body.

    THE HOSTED HOP (J6). This route is also what makes estate SSO reachable
    from a host OUTSIDE the cookie domain. The browser IS on auth.madfam.io
    for this hop, so this is the one moment the issuer can set its own
    first-party `janua_sso` cookie for a person signing in from
    `map.creatumundo.mx` — a host that can never receive it by relay, because a
    browser rejects a `.madfam.io` cookie from a `creatumundo.mx` page. The
    forward below keeps `?token=` exactly as products expect.

    A SECOND PRESS (2026-10-07). Production logs showed a person's first press
    spend the link (302) and their next presses, 0.4–2 s later, answered 400 —
    and the browser shows the answer to the LAST press, so they saw a dead link
    after a successful spend, link after link. Two things now hold:

      • The spend reads the row under a lock (`with_for_update`), so of two
        concurrent presses exactly one spends; the other waits, then finds the
        link spent. (Before, both could pass the "unused" check: two 302s were
        logged for one link.)
      • A press from the browser that spent the link, inside
        MAGIC_LINK_REPLAY_GRACE_SECONDS, finishes the hand-off again: same
        user, same destination, a fresh session. "The browser that spent it"
        is the `janua_ml_browser` cookie recorded at the spend, never an IP or
        a user-agent. Any other browser, or a press after the window, gets the
        "already used" page. A link still signs in exactly one browser.
    """
    from fastapi.responses import HTMLResponse, RedirectResponse

    if not token:
        return _magic_link_dead_page(None)

    binding = _magic_link_browser_binding(req)
    result = await db.execute(
        select(MagicLink)
        .where(
            MagicLink.token == token,
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > datetime.utcnow(),
        )
        .with_for_update()
    )
    magic_link = result.scalar_one_or_none()
    replay = False
    if not magic_link:
        dead = await _magic_link_by_token(db, token)
        if not await _spent_here_moments_ago(dead, binding):
            return _magic_link_dead_page(dead)
        magic_link, replay = dead, True

    result = await db.execute(
        select(User).where(User.id == magic_link.user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    if not user:
        return _magic_link_dead_page(None)

    from app.auth.authentication_assurance import user_requires_mfa
    from app.auth.hosted_security import start_factor_flow

    bound_client = await _auth_shared._oauth_client_for_redirect(db, magic_link.redirect_url)
    if await user_requires_mfa(db, user, getattr(bound_client, "organization_id", None)):
        # Claim the emailed credential once, even while the factor is pending.
        if replay:
            return _magic_link_dead_page(magic_link)
        magic_link.used_at = datetime.utcnow()
        user.email_verified = True
        await db.commit()
        return await start_factor_flow(
            req,
            db,
            user,
            methods=["email"],
            authenticated_at=int(datetime.now(timezone.utc).timestamp()),
            client_id=getattr(bound_client, "client_id", None),
            next_url=magic_link.redirect_url,
        )

    if not replay:
        # Burn the token before minting anything: a link that has produced a
        # session must never produce one for another browser. The spend record
        # is written before the first commit (create_session's), so a press
        # waiting on this row's lock finds it as soon as it gets the row.
        magic_link.used_at = datetime.utcnow()
        await _remember_magic_link_spend(token, binding)

    access_token, refresh_token, session = await _auth_shared.AuthService.create_session(
        db,
        user,
        ip_address=req.client.host if req and req.client else None,
        user_agent=req.headers.get("user-agent") if req else None,
        audience=await _auth_shared._session_audience_for_redirect(db, magic_link.redirect_url),
        authentication_methods=["email"],
        authenticated_at=datetime.utcnow(),
    )

    # Signing in by emailed link proves control of the mailbox.
    if not user.email_verified:
        user.email_verified = True
    await db.commit()

    activity = {"method": "magic_link"}
    if replay:
        activity["replay"] = True
    await _auth_shared.log_activity(db, str(user.id), "signin", activity, req)

    # Re-validate at redemption: the allowlist may have changed since the link
    # was issued, and this is the moment a credential is handed over.
    destination = _auth_shared.validate_redirect_url(magic_link.redirect_url, default_url=None)
    if not destination:
        return HTMLResponse(
            content=_recovery_page_html(
                "<h1>✅ Signed in</h1>"
                '<p class="lede">Your link was valid, but its destination is no longer '
                "an allowed address, so we did not forward you.</p>"
                "<p>Return to the site you were signing in to and try again.</p>"
            ),
            status_code=400,
        )

    separator = "&" if "?" in destination else "?"
    redirect = RedirectResponse(
        url=f"{destination}{separator}token={access_token}", status_code=302
    )
    # SSO (B1): also leave an issuer-side browser session behind. The redirect
    # keeps `?token=` exactly as products expect — nothing about the contract
    # changes — but the browser IS on auth.madfam.io for this hop, so this is
    # the one moment the issuer can set its own cookie on a magic-link login.
    # Without it `/authorize?prompt=none` has no session to recognise and every
    # silent hop between products falls back to a fresh magic link.
    _set_session_cookies(
        redirect, access_token, refresh_token, user=user, session=session, request=req
    )
    return redirect


@router.post("/magic-link/verify", response_model=SignInResponse)
async def verify_magic_link(
    request: VerifyMagicLinkRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Sign in with magic link token.

    SSO (B1): besides returning the tokens in the body — the contract
    `@madfam/janua-next` and nauta's integration package depend on, unchanged —
    this also sets the issuer session cookies on the response. That costs
    nothing when the caller is a server (Node keeps the Set-Cookie and drops
    it), and it is what makes `/authorize?prompt=none` work when a browser
    posts here directly.
    """
    # Find valid magic link
    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token == request.token,
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > datetime.utcnow(),
        )
    )
    magic_link = result.scalar_one_or_none()

    if not magic_link:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")

    # Get user
    result = await db.execute(
        select(User).where(User.id == magic_link.user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # SECURITY (2026-08-23): enforce MFA on the JSON magic-link path too. A JSON
    # caller receives the same mfa_required + mfa_token contract the /signin path
    # uses, and completes at /mfa/challenge/verify. The link is NOT burned on an
    # MFA interrupt, so the user isn't stranded. Both voluntary enrollment and
    # organization policy are enforced, independently of the legacy global flag.
    from app.auth.authentication_assurance import user_requires_mfa
    from app.auth.mfa_enforcement import mint_mfa_challenge_token

    if await user_requires_mfa(db, user):
        await _auth_shared.log_activity(
            db, str(user.id), "signin", {"method": "magic_link", "mfa_required": True}, req
        )
        return SignInResponse(
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                email_verified=user.email_verified,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                profile_image_url=user.profile_image_url,
                is_admin=getattr(user, "is_admin", False),
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_sign_in_at=user.last_sign_in_at,
            ),
            tokens=None,
            mfa_required=True,
            mfa_token=mint_mfa_challenge_token(
                user,
                methods=["email"],
                audience=await _auth_shared._session_audience_for_redirect(db, magic_link.redirect_url),
            ),
        )

    # Mark magic link as used
    magic_link.used_at = datetime.utcnow()

    # Create session, with the audience of the product the link forwards to.
    access_token, refresh_token, session = await _auth_shared.AuthService.create_session(
        db,
        user,
        ip_address=req.client.host,
        user_agent=req.headers.get("user-agent"),
        audience=await _auth_shared._session_audience_for_redirect(db, magic_link.redirect_url),
        authentication_methods=["email"],
        authenticated_at=datetime.utcnow(),
    )

    # Log activity
    await _auth_shared.log_activity(db, str(user.id), "signin", {"method": "magic_link"}, req)

    # SSO (B1): same tokens the body carries, also as issuer session cookies.
    # The response body below is byte-for-byte what it was before.
    _set_session_cookies(
        response, access_token, refresh_token, user=user, session=session, request=req
    )

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, "is_admin", False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


async def _oauth_continuation_url(
    *,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    next_url: Optional[str],
    redis: ResilientRedisClient,
    db,
) -> Optional[str]:
    """The absolute URL a browser must land on, WITH a Janua session, to finish
    what it started.

    For an OAuth login this rebuilds `/api/v1/oauth/authorize?…` from the
    `oauth:pre_login:<id>` payload the same way `login_form` does on its
    `redis_hit` branch: the stored params carry the client's `state` and PKCE
    challenge, so the continuation is a COMPLETE authorize request the client's
    callback will accept. It is absolute on `public_base_url` because an emailed
    link is opened wherever the person reads mail — often a different tab: the
    link lands on janua's own callback, which mints the session cookie and then
    forwards here, and `/authorize` recognises the cookie and issues the code.

    On a Redis miss it falls back to the client's registered origin (a fresh
    start, the same recovery `login_form` uses), and a non-OAuth login goes to
    its validated `next`. None means nothing safe can be rebuilt.
    """
    base = settings.public_base_url.rstrip("/")
    if auth_request_id:
        stored = await redis.get(f"oauth:pre_login:{auth_request_id}")
        if stored:
            try:
                params = json.loads(stored)
                if is_resource_bound(params):
                    # The link's destination is stored in a 500-character
                    # column; a full authorize URL for a protected resource
                    # (URL client_id + resource) can exceed it. The resume URL
                    # rebuilds it from this same record, which for these
                    # requests outlives the link.
                    resume = urlencode({"auth_request_id": auth_request_id})
                    return f"{base}/api/v1/oauth/authorize/resume?{resume}"
                query = authorize_query(params)
                return f"{base}/api/v1/oauth/authorize?{urlencode(query)}"
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.warning(
                    "login_form_magic_link.pre_login_unparseable",
                    auth_request_id=auth_request_id,
                    error=str(exc),
                )
        if client_id:
            return await _recover_authorize_url_from_client(client_id, db)
        return None
    safe_next = _auth_shared.validate_redirect_url(next_url or "/", default_url="/")
    return safe_next if safe_next.startswith(("http://", "https://")) else f"{base}{safe_next}"


# Hosted-login half of "sign in by email link": the page's magic-link form posts
# here. Issues the link through the same path as POST /magic-link, with the
# pending OAuth authorization as the link's destination.
@router.post("/login-form/magic-link")
# Limited inside `_issue_magic_link`, like POST /magic-link (see there).
async def login_form_magic_link(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    next: str = Form("/"),
    auth_request_id: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    ui_locales: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    redis: ResilientRedisClient = Depends(_auth_shared.get_redis),
):
    """Email a sign-in link whose destination resumes the pending OAuth request.

    The password form (`/login-form`) signs the person in on the spot and
    redirects to the rebuilt authorize URL. This form cannot: the proof arrives
    later, by mail, in whatever tab the person reads it. So the rebuilt
    authorize URL becomes the magic link's `redirect_url` — the emailed
    callback mints the session cookie on this origin and forwards there, and
    `/authorize` completes as if the person had just typed a password. The
    `oauth:pre_login` key is deliberately NOT consumed here: "Use a password
    instead" must still work after a link was requested.
    """
    from fastapi.responses import HTMLResponse
    from pydantic import ValidationError

    safe_next = _auth_shared.validate_redirect_url(next or "/", default_url="/")
    locale = page_locale(ui_locales)
    copy = hosted_copy(locale)
    hidden_fields = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=safe_next if not auth_request_id else None,
        ui_locale=locale,
    )
    app_name = client_name or "Application"

    def _password_url() -> str:
        return _login_page_switch_url(
            method=LOGIN_METHOD_PASSWORD,
            auth_request_id=auth_request_id,
            client_id=client_id,
            client_name=client_name,
            next_url=safe_next if not auth_request_id else None,
            ui_locale=locale,
        )

    def _rerender(message: str, status_code: int) -> HTMLResponse:
        return HTMLResponse(
            content=_hosted_login_page_html(
                app_name=app_name,
                hidden_fields=hidden_fields,
                method=LOGIN_METHOD_MAGIC_LINK,
                switch_url=_password_url(),
                error_message=message,
                locale=locale,
                privacy_notice_url=client_privacy_notice_url(client_id),
            ),
            status_code=status_code,
        )

    if not magic_link_login_available():
        return HTMLResponse(
            content=_hosted_login_page_html(
                app_name=app_name,
                hidden_fields=hidden_fields,
                method=LOGIN_METHOD_PASSWORD,
                switch_url=None,
                error_message=copy["magic_unavailable"],
                locale=locale,
                privacy_notice_url=client_privacy_notice_url(client_id),
            ),
            status_code=400,
        )

    continuation = await _oauth_continuation_url(
        auth_request_id=auth_request_id,
        client_id=client_id,
        next_url=next,
        redis=redis,
        db=db,
    )
    if continuation is None:
        logger.warning(
            "login_form_magic_link.no_continuation",
            auth_request_id=auth_request_id,
            client_id_present=bool(client_id),
        )
        return HTMLResponse(
            content=_recovery_page_html(
                f"<h1>{copy['session_expired_title']}</h1>"
                f'<p class="lead">{copy["session_expired_body"]}</p>',
                title=copy["sign_in_title"],
                lang=hosted_html_lang(locale),
            ),
            status_code=400,
        )

    try:
        # FORCE THE HOSTED HOP. This flow's destination is ALWAYS janua's own
        # rebuilt /oauth/authorize URL, which lives on the cookie domain
        # (auth.madfam.io), so the DERIVED rule in should_use_hosted_hop()
        # declines the hop: it asks whether the destination can RECEIVE the
        # estate cookie, but /authorize never REDEEMS the one-time token — only
        # /magic-link/callback does. Without the hop the emailed link is
        # `{authorize_url}&token=…`; authorize ignores the token, no session is
        # set, and the person is bounced to the password form in a loop (found
        # live 2026-09-17, caro@ on the yantra4d hosted login — the first click
        # of any hosted-form link since J6/#618 shipped). Forcing the hop routes
        # the link through /magic-link/callback, which mints the session cookie
        # on this origin and then forwards to the authorize URL.
        magic_link_data = MagicLinkRequest(email=email, redirect_url=continuation, hosted_hop=True)
    except ValidationError:
        return _rerender(copy["invalid_email"], 400)

    # The page language decides the mail's language too: the person reading
    # this form in Spanish asked for Spanish (an explicit request beats the
    # stored profile and the deployment default — email_i18n.resolve_locale).
    explicit_email_locale = hosted_locale(ui_locales)
    try:
        user = await _auth_magic_link_issue._issue_magic_link(
            request,
            magic_link_data,
            background_tasks,
            db,
            client_id=client_id,
            email_locale=explicit_email_locale,
        )
    except HTTPException as exc:
        if locale != DEFAULT_HOSTED_LOCALE:
            # The API's details are English sentences for integrators; a
            # Spanish page shows its own words instead of a mixed-language one.
            detail = copy["magic_send_failed"]
        else:
            detail = exc.detail if isinstance(exc.detail, str) else copy["magic_send_failed"]
        return _rerender(detail, exc.status_code if exc.status_code in (400, 403, 429) else 400)

    invite_only = is_invite_only(client_id)
    logger.info(
        "login_form_magic_link.sent" if user is not None else "login_form_magic_link.not_invited",
        auth_request_id=auth_request_id,
        client_id=client_id,
    )
    return HTMLResponse(
        content=_check_inbox_page_html(
            app_name=app_name,
            # An invite-only client never says whether the address has access:
            # the page is the same for both, and so is the masked address it
            # shows (the one TYPED, which is the stored one for an existing user
            # up to case).
            email=user.email if user is not None else magic_link_data.email,
            password_url=_password_url(),
            locale=locale,
            invite_only=invite_only,
        )
    )
