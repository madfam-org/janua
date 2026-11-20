"""Sign-in link browser binding and pages (interstitial, dead link, check your inbox).

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

from fastapi import Request
from sqlalchemy import select

from app.auth.hosted_locale import (
    DEFAULT_HOSTED_LOCALE,
    UI_LOCALES_PARAM,
    hosted_copy,
    hosted_locale,
)
from app.auth.hosted_locale import html_lang as hosted_html_lang
from app.config import settings
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_shared import _recovery_page_html, logger

from ...models import MagicLink

#: The browser-binding cookie the interstitial's GET sets (2026-10-07).
#:
#: A random, HttpOnly value scoped to the callback path. The POST that spends a
#: link records a digest of it next to the spend (in Redis, for
#: MAGIC_LINK_REPLAY_GRACE_SECONDS); only a request carrying the SAME value can
#: finish the hand-off again inside that window. It identifies a browser, not a
#: person, and carries nothing else.
MAGIC_LINK_BROWSER_COOKIE = "janua_ml_browser"


_MAGIC_LINK_BROWSER_COOKIE_PATH = "/api/v1/auth/magic-link/callback"


_MAGIC_LINK_BROWSER_COOKIE_MAX_AGE = 3600


_MAGIC_LINK_BROWSER_VALUE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _magic_link_browser_binding(request: Optional[Request]) -> Optional[str]:
    """This browser's binding value, or None (no cookie, or not one of ours)."""
    if request is None:
        return None
    try:
        value = request.cookies.get(MAGIC_LINK_BROWSER_COOKIE)
    except Exception:
        return None
    if isinstance(value, str) and _MAGIC_LINK_BROWSER_VALUE.match(value):
        return value
    return None


def _set_magic_link_browser_cookie(response) -> None:
    """Give this browser a binding value (the GET calls this when it has none)."""
    response.set_cookie(
        key=MAGIC_LINK_BROWSER_COOKIE,
        value=secrets.token_urlsafe(32),
        max_age=_MAGIC_LINK_BROWSER_COOKIE_MAX_AGE,
        path=_MAGIC_LINK_BROWSER_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _magic_link_spend_key(token: str) -> str:
    return "magic_link:spent:" + hashlib.sha256(token.encode()).hexdigest()


def _magic_link_binding_digest(binding: str) -> str:
    return hashlib.sha256(binding.encode()).hexdigest()


async def _remember_magic_link_spend(token: str, binding: Optional[str]) -> None:
    """Record WHICH browser spent this link, for the replay grace window.

    Called after `used_at` is set and BEFORE anything commits, so a concurrent
    press that is waiting on the row lock finds the record the moment it gets
    the row. Best effort: if Redis cannot take it, the only loss is the replay
    (a repeat press then gets the honest "already used" page, as before).
    """
    grace = settings.MAGIC_LINK_REPLAY_GRACE_SECONDS
    if grace <= 0 or not binding:
        return
    try:
        redis_client = await _auth_shared.get_redis()
        await redis_client.strict_set(
            _magic_link_spend_key(token), _magic_link_binding_digest(binding), ex=grace
        )
    except Exception as exc:
        logger.warning("magic_link.spend_not_recorded", error_type=type(exc).__name__)


async def _magic_link_by_token(db, token: str):
    """The link row whatever its state — used to say WHY a link is dead."""
    result = await db.execute(select(MagicLink).where(MagicLink.token == token))
    return result.scalar_one_or_none()


async def _spent_here_moments_ago(magic_link, binding: Optional[str]) -> bool:
    """Did THIS browser spend this link within the replay grace window?

    True only when all hold: the link was spent; the spend is younger than
    MAGIC_LINK_REPLAY_GRACE_SECONDS; and the browser presents the binding value
    recorded at the spend. Any doubt (no cookie, Redis unreachable, a digest
    mismatch) answers False, which shows the "already used" page.
    """
    grace = settings.MAGIC_LINK_REPLAY_GRACE_SECONDS
    if grace <= 0 or not binding or magic_link is None or magic_link.used_at is None:
        return False
    used_at = magic_link.used_at
    if used_at.tzinfo is not None:
        # The column is naive UTC; never compare aware with naive (janua#702).
        used_at = used_at.astimezone(timezone.utc).replace(tzinfo=None)
    if datetime.utcnow() - used_at > timedelta(seconds=grace):
        return False
    try:
        redis_client = await _auth_shared.get_redis()
        stored = await redis_client.strict_get(_magic_link_spend_key(magic_link.token))
    except Exception as exc:
        logger.warning("magic_link.replay_check_unavailable", error_type=type(exc).__name__)
        return False
    if isinstance(stored, bytes):
        stored = stored.decode("ascii", "ignore")
    if not isinstance(stored, str) or not stored:
        return False
    return hmac.compare_digest(stored, _magic_link_binding_digest(binding))


def _magic_link_page_html(redirect_url: Optional[str], title: str, body_html: str) -> str:
    """The shell both magic-link pages share: the interstitial and the dead page.

    Branded from the DESTINATION host via `resolve_branding`, the same signal
    the email itself was branded from (`email_branding.py`), so the page a CTM
    person lands on carries the Crea header their mail carried rather than a
    MADFAM page they were not expecting. An unknown or absent destination
    resolves to the MADFAM default. The language follows the destination too
    (see `_magic_link_interstitial_is_spanish`).
    """
    import html as html_mod

    from app.services.email_branding import resolve_branding

    branding = resolve_branding(redirect_url=redirect_url)
    lang = "es-MX" if _magic_link_interstitial_is_spanish(redirect_url) else "en"
    header_name = html_mod.escape(str(branding.get("header_name", "MADFAM")))
    header_bg = html_mod.escape(str(branding.get("header_bg", "")))
    header_fg = html_mod.escape(str(branding.get("header_fg", "#ffffff")))

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex">
    <title>{html_mod.escape(title)}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f4f5f7;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            width: 100%;
            max-width: 420px;
            overflow: hidden;
        }}
        .brand {{
            background: {header_bg};
            color: {header_fg};
            padding: 20px;
            text-align: center;
            font-weight: 700;
            font-size: 18px;
        }}
        .body {{ padding: 32px; text-align: center; }}
        h1 {{ font-size: 22px; color: #1b1c2e; margin-bottom: 10px; }}
        p {{ color: #5c5f72; font-size: 15px; line-height: 1.5; margin-bottom: 24px; }}
        button, .action {{
            display: block;
            width: 100%;
            padding: 14px;
            background: {header_bg};
            color: {header_fg};
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            min-height: 48px;
            text-decoration: none;
        }}
        button:disabled {{ opacity: 0.6; cursor: progress; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="brand">{header_name}</div>
        <div class="body">
{body_html}
        </div>
    </div>
</body>
</html>
"""


def _magic_link_dead_page(magic_link=None):
    """The dead-link page both halves of the callback show, saying WHY.

    Shared so the GET (which only reads) and the POST (which spends) cannot
    drift into telling the same person two different stories.

    It used to be one English page for every case («Link expired … expire after
    15 minutes»). On 2026-10-07 that sentence was wrong for the person reading
    it: their link had been spent one second earlier by their own first press of
    the button, and "expired after 15 minutes" sent them to request link after
    link. The three cases call for different next steps, so the page names
    them. Saying "already used" tells someone holding the link nothing they can
    use: they cannot sign in with it either way.

      • used    — the link worked once already; the first press may already
                  have signed them in, so the page links back to the product.
      • expired — the link outlived its 15 minutes; ask for a new one.
      • invalid — no such link (a truncated copy, a mangled URL).

    The page follows the destination's language and brand, like the
    interstitial before it, and offers the product's front door (the
    destination's origin, re-validated against the allowlist) as the way on.
    """
    import html as html_mod

    from fastapi.responses import HTMLResponse

    redirect_url = getattr(magic_link, "redirect_url", None) if magic_link is not None else None
    spanish = _magic_link_interstitial_is_spanish(redirect_url)
    if magic_link is None:
        reason = "invalid"
    elif magic_link.used_at is not None:
        reason = "used"
    else:
        reason = "expired"

    copy = {
        ("used", True): (
            "Este enlace ya se usó",
            "Cada enlace sirve una sola vez. Si tocaste «Entrar» más de una vez, "
            "el primer toque pudo haberte dejado dentro: abre el sitio para comprobarlo.",
            "Si no entraste, pide un enlace nuevo desde ahí y toca «Entrar» una sola vez.",
        ),
        ("used", False): (
            "This link was already used",
            "Each link works once. If you pressed the button more than once, the first "
            "press may already have signed you in: open the site to check.",
            "If you are not signed in, request a new link there and press the button once.",
        ),
        ("expired", True): (
            "Este enlace venció",
            "Los enlaces de acceso duran 15 minutos.",
            "Pide uno nuevo desde la página donde estabas entrando.",
        ),
        ("expired", False): (
            "This link expired",
            "Sign-in links last 15 minutes.",
            "Request a new one from the page you were signing in to.",
        ),
        ("invalid", True): (
            "Este enlace no es válido",
            "Puede que se haya copiado incompleto.",
            "Abre el enlace completo desde el correo, o pide uno nuevo desde la página "
            "donde estabas entrando.",
        ),
        ("invalid", False): (
            "This link is not valid",
            "It may have been copied incompletely.",
            "Open the whole link from the email, or request a new one from the page you "
            "were signing in to.",
        ),
    }[(reason, spanish)]
    heading, lede, next_step = copy

    action_html = ""
    destination = _auth_shared.validate_redirect_url(redirect_url, default_url=None) if redirect_url else None
    if destination:
        parsed = urlparse(destination)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            front_door = f"{parsed.scheme}://{parsed.netloc}/"
            label = f"Ir a {parsed.hostname}" if spanish else f"Go to {parsed.hostname}"
            action_html = (
                f'            <a class="action" href="{html_mod.escape(front_door)}">'
                f"{html_mod.escape(label)}</a>\n"
            )

    body_html = (
        f"            <h1>{html_mod.escape(heading)}</h1>\n"
        f"            <p>{html_mod.escape(lede)}</p>\n"
        f"            <p>{html_mod.escape(next_step)}</p>\n"
        f"{action_html}"
    )
    return HTMLResponse(
        content=_magic_link_page_html(redirect_url, heading, body_html),
        status_code=400,
        headers={
            "cache-control": "no-store",
            "referrer-policy": "no-referrer",
            "x-robots-tag": "noindex, nofollow",
        },
    )


def _magic_link_interstitial_html(token: str, redirect_url: Optional[str]) -> str:
    """The scanner-proof interstitial: one button that POSTs the token back.

    Branded and worded from the DESTINATION host (`_magic_link_page_html`): the
    CTM hosts are Spanish, and a person mid-sign-in should not be handed an
    English button. Anything else keeps English, which is what every other
    hosted page here renders.

    ONE PRESS (2026-10-07). The hand-off after the press takes seconds: the
    POST, then the product's own redirect chain. All that time this page stays
    on screen with a live button, and every further press starts a new form
    submission that CANCELS the navigation already in flight — the browser then
    shows the answer to the last press. So the button disables itself and says
    it is working. `pageshow` re-enables it when the browser restores this page
    from its back/forward cache, so "back" never leaves a dead button. Without
    script the page works exactly as before, and a repeat press is still
    covered on the server by the replay grace window (see the POST).
    """
    import html as html_mod

    spanish = _magic_link_interstitial_is_spanish(redirect_url)
    heading = "Entrar" if spanish else "Sign in"
    explanation = (
        "Confirma que eres tú quien abrió este enlace."
        if spanish
        else "Confirm it was you who opened this link."
    )
    action = "Entrar" if spanish else "Continue"
    working = "Entrando…" if spanish else "Signing you in…"

    body_html = f"""            <h1>{html_mod.escape(heading)}</h1>
            <p>{html_mod.escape(explanation)}</p>
            <form method="POST" action="/api/v1/auth/magic-link/callback" data-janua-magic-link-form>
                <input type="hidden" name="token" value="{html_mod.escape(token)}">
                <button type="submit" data-label="{html_mod.escape(action)}" data-working="{html_mod.escape(working)}">{html_mod.escape(action)}</button>
            </form>
            <script>
            (function () {{
                var form = document.querySelector("form[data-janua-magic-link-form]");
                if (!form) return;
                var button = form.querySelector("button");
                form.addEventListener("submit", function (event) {{
                    if (form.getAttribute("data-sent") === "1") {{ event.preventDefault(); return; }}
                    form.setAttribute("data-sent", "1");
                    button.disabled = true;
                    button.textContent = button.getAttribute("data-working");
                }});
                window.addEventListener("pageshow", function (event) {{
                    if (!event.persisted) return;
                    form.removeAttribute("data-sent");
                    button.disabled = false;
                    button.textContent = button.getAttribute("data-label");
                }});
            }})();
            </script>
"""
    return _magic_link_page_html(redirect_url, heading, body_html)


def _magic_link_interstitial_is_spanish(redirect_url: Optional[str]) -> bool:
    """Does this destination serve a Spanish-speaking tenant?

    Reuses `CTM_HOSTS` — the same registry that decides the email's branding —
    rather than introducing a second host list that could disagree with it. The
    hosts that take the hosted hop today are all CTM's.
    """
    if not redirect_url:
        return False
    from app.services.email_branding import CTM_HOSTS

    parsed = urlparse(redirect_url)
    # A destination that carries the page language says so itself: the hosted
    # form's continuation (/oauth/authorize?...&ui_locales=es) and an operator
    # invitation's entry URL (product-invites) both do (2026-10-22).
    requested = parse_qs(parsed.query).get(UI_LOCALES_PARAM, [None])[0]
    if requested is not None and hosted_locale(requested):
        return hosted_locale(requested) == "es"
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(host == h or host.endswith(f".{h}") for h in CTM_HOSTS)


def _mask_email(email: str) -> str:
    """`a***@example.com` — enough to confirm the address, not to leak it."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


def _check_inbox_page_html(
    *,
    app_name: str,
    email: str,
    password_url: Optional[str],
    locale: str = DEFAULT_HOSTED_LOCALE,
    invite_only: bool = False,
) -> str:
    import html as _html

    c = hosted_copy(locale)
    switch = (
        f'<p class="lead"><a href="{_html.escape(password_url)}">{c["switch_to_password"]}</a></p>'
        if password_url
        else ""
    )
    masked = _html.escape(_mask_email(email))
    app = _html.escape(app_name)
    if invite_only:
        # Same words whether or not the address has access (no enumeration).
        sent = (
            f"{c['inbox_if_invited']} <strong>{app}</strong>{c['inbox_if_invited_tail']} "
            f"<strong>{masked}</strong>."
        )
    else:
        sent = (
            f"{c['inbox_sent_to']} <strong>{masked}</strong>.\n"
            f"        {c['inbox_open_on_device']} <strong>{app}</strong>."
        )
    return _recovery_page_html(
        f"""<h1>&#9993;&#65039; {c["inbox_heading"]}</h1>
        <p class="lead">{sent}</p>
        <p class="hint">{c["inbox_hint"]}</p>
        {switch}""",
        title=c["inbox_title"],
        lang=hosted_html_lang(locale),
    )
