"""A second press of the interstitial's button must not strand the person.

THE INCIDENT (2026-10-07, production, a CTM brand host). A person on an iPhone
(mail app -> Safari) could not sign in: every link they opened ended on the
dead-link page. The API logs for their two links (15:25:47 and 15:27:59 UTC)
show the same shape both times:

    GET  /magic-link/callback?token=T   200   interstitial rendered
    POST /magic-link/callback           302   token spent, session minted (1.0 s / 3.0 s)
    POST /magic-link/callback           400   same token again, 0.4-2 s later
    POST /magic-link/callback           400   ...

So the link did NOT expire and was NOT mangled: the first press spent it and
minted a session. The page then stays on screen, with a live button, for the
whole hand-off (the POST took up to 3 s, then the product's own redirect
chain). Each further press starts a new form submission, which cancels the
navigation already in flight, and the browser shows the response of the LAST
press: the 400 «Link expired» page. Re-opening the email link afterwards only
showed the same page (the GET of a spent link).

What these tests pin:

  1. The browser that spent a link moments ago can finish the hand-off: a
     repeat POST (or a re-opened GET) from THAT browser, inside
     MAGIC_LINK_REPLAY_GRACE_SECONDS, completes the sign-in. "That browser" is
     proven by an HttpOnly cookie the GET sets, never by IP or user-agent.
  2. Any other browser still gets nothing from a spent link (one-time holds).
  3. The dead page says WHY (already used / expired / not valid), in the
     destination's language, with a way back to the product.
  4. The interstitial disables its button once pressed.
  5. The spend is a locked read, so two concurrent POSTs cannot both pass the
     "unused" check (two 302s for one link were logged at 15:28:14 UTC).
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Base, MagicLink, User, UserStatus
from app.routers.v1 import auth as auth_router

pytestmark = pytest.mark.asyncio

CTM_DESTINATION = "https://map.creatumundo.mx/api/auth/magic-complete"
IPHONE_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"
)


# --------------------------------------------------------------------------
# Harness: a real (SQLite) magic_links/users pair, a real Redis protocol
# (fakeredis behind the production ResilientRedisClient), and a "browser" that
# keeps its cookies between requests the way Safari does.
# --------------------------------------------------------------------------


@pytest.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(c, tables=[User.__table__, MagicLink.__table__])
        )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def redis_client():
    return ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))


@pytest.fixture
def exchange(redis_client):
    """Everything around the spend that is not under test, made deterministic.

    `create_session` hands out a NEW access token per call so a test can tell a
    replayed hand-off from the first one.
    """
    minted = []

    async def _create_session(db, user, **kwargs):
        minted.append(kwargs)
        return f"ACCESS-{len(minted)}", f"REFRESH-{len(minted)}", SimpleNamespace(id=uuid4())

    def _validate(url, default_url=None, **_kwargs):
        if url and url.startswith("https://map.creatumundo.mx/"):
            return url
        return default_url

    with (
        patch.object(
            auth_router.AuthService, "create_session", AsyncMock(side_effect=_create_session)
        ),
        patch.object(auth_router, "_session_audience_for_redirect", AsyncMock(return_value=None)),
        patch.object(auth_router, "validate_redirect_url", MagicMock(side_effect=_validate)),
        patch.object(auth_router, "log_activity", AsyncMock()),
        patch.object(auth_router, "get_redis", AsyncMock(return_value=redis_client)),
        patch("app.auth.mfa_enforcement.mfa_required_for", MagicMock(return_value=False)),
    ):
        yield minted


async def _issue(
    db, *, minutes_left: int = 15, redirect_url: Optional[str] = CTM_DESTINATION
) -> str:
    user = User(email="integrante@example.test", email_verified=True, status=UserStatus.ACTIVE)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = f"tok-{uuid4().hex}{uuid4().hex}"
    db.add(
        MagicLink(
            user_id=user.id,
            email=user.email,
            token=token,
            redirect_url=redirect_url,
            expires_at=datetime.utcnow() + timedelta(minutes=minutes_left),
        )
    )
    await db.commit()
    return token


async def _row(db, token: str) -> MagicLink:
    from sqlalchemy import select

    return (await db.execute(select(MagicLink).where(MagicLink.token == token))).scalar_one()


class Browser:
    """A cookie jar plus request factory — just enough of Safari for this flow."""

    def __init__(self, user_agent: str = IPHONE_SAFARI):
        self.cookies: Dict[str, str] = {}
        self.user_agent = user_agent

    def request(self, method: str) -> Request:
        headers = [(b"user-agent", self.user_agent.encode())]
        if self.cookies:
            jar = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            headers.append((b"cookie", jar.encode()))
        return Request(
            {
                "type": "http",
                "method": method,
                "scheme": "https",
                "server": ("auth.madfam.io", 443),
                "path": "/api/v1/auth/magic-link/callback",
                "query_string": b"",
                "headers": headers,
                "client": ("198.51.100.7", 51000),
            }
        )

    def keep(self, response) -> None:
        for name, value in response.raw_headers:
            if name.lower() != b"set-cookie":
                continue
            pair = value.decode().split(";", 1)[0]
            key, _, val = pair.partition("=")
            if "max-age=0" in value.decode().lower():
                self.cookies.pop(key, None)
            else:
                self.cookies[key] = val

    async def open_link(self, token: str, db):
        """GET the emailed link (the interstitial)."""
        handler = auth_router.magic_link_callback_interstitial
        kwargs = {"token": token, "db": db}
        if "request" in inspect.signature(handler).parameters:
            kwargs["request"] = self.request("GET")
        response = await handler(**kwargs)
        self.keep(response)
        return response

    async def press_button(self, token: str, db):
        """POST the interstitial's form (one press of «Entrar»)."""
        response = await auth_router.magic_link_callback(
            token=token, req=self.request("POST"), db=db
        )
        self.keep(response)
        return response


def _text(response) -> str:
    return response.body.decode()


# --------------------------------------------------------------------------
# 1. The incident: a second press from the same browser
# --------------------------------------------------------------------------


class TestSecondPressFromTheSameBrowser:
    async def test_second_press_after_the_spend_still_signs_in(self, db, exchange):
        token = await _issue(db)
        phone = Browser()

        assert (await phone.open_link(token, db)).status_code == 200
        first = await phone.press_button(token, db)
        assert first.status_code == 302
        assert first.headers["location"] == f"{CTM_DESTINATION}?token=ACCESS-1"

        # The press the person actually sees the answer to.
        second = await phone.press_button(token, db)
        assert second.status_code == 302, _text(second) if second.status_code != 302 else ""
        assert second.headers["location"] == f"{CTM_DESTINATION}?token=ACCESS-2"

    async def test_a_third_press_still_lands(self, db, exchange):
        """The 15:28 UTC attempt pressed three times in 3.3 s."""
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        for _ in range(3):
            response = await phone.press_button(token, db)
        assert response.status_code == 302
        assert response.headers["location"].startswith(f"{CTM_DESTINATION}?token=ACCESS-")

    async def test_reopening_the_email_link_moments_later_shows_the_button_again(
        self, db, exchange
    ):
        """The link was re-opened from the mail app four times within 80 s of the spend."""
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        await phone.press_button(token, db)

        again = await phone.open_link(token, db)
        assert again.status_code == 200
        assert 'action="/api/v1/auth/magic-link/callback"' in _text(again)
        # Re-rendering spends nothing and mints nothing.
        assert len(exchange) == 1

        finish = await phone.press_button(token, db)
        assert finish.status_code == 302

    async def test_the_spend_is_recorded_once(self, db, exchange):
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        await phone.press_button(token, db)
        used_at = (await _row(db, token)).used_at
        await phone.press_button(token, db)
        assert (await _row(db, token)).used_at == used_at


# --------------------------------------------------------------------------
# 2. One-time still holds for everyone else
# --------------------------------------------------------------------------


class TestOneTimeForEveryoneElse:
    async def test_another_browser_cannot_replay_a_spent_link(self, db, exchange):
        token = await _issue(db)
        phone, other = Browser(), Browser()
        await phone.open_link(token, db)
        assert (await phone.press_button(token, db)).status_code == 302

        await other.open_link(token, db)  # a scanner or a forwarded email
        response = await other.press_button(token, db)
        assert response.status_code == 400
        assert len(exchange) == 1, "a spent link must never mint for another browser"

    async def test_a_browser_without_cookies_cannot_replay(self, db, exchange):
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        await phone.press_button(token, db)
        phone.cookies.clear()  # «Block All Cookies»
        assert (await phone.press_button(token, db)).status_code == 400

    async def test_the_grace_window_closes(self, db, exchange):
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        await phone.press_button(token, db)

        row = await _row(db, token)
        grace = auth_router.settings.MAGIC_LINK_REPLAY_GRACE_SECONDS
        row.used_at = datetime.utcnow() - timedelta(seconds=grace + 1)
        await db.commit()

        response = await phone.press_button(token, db)
        assert response.status_code == 400
        assert len(exchange) == 1

    async def test_grace_zero_disables_the_replay(self, db, exchange):
        token = await _issue(db)
        phone = Browser()
        with patch.object(auth_router.settings, "MAGIC_LINK_REPLAY_GRACE_SECONDS", 0):
            await phone.open_link(token, db)
            await phone.press_button(token, db)
            assert (await phone.press_button(token, db)).status_code == 400

    async def test_redis_down_falls_back_to_the_honest_page(self, db, exchange, redis_client):
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        await phone.press_button(token, db)

        broken = MagicMock()
        broken.strict_get = AsyncMock(side_effect=auth_router.RedisUnavailableError("down"))
        with patch.object(auth_router, "get_redis", AsyncMock(return_value=broken)):
            response = await phone.press_button(token, db)
        assert response.status_code == 400
        assert len(exchange) == 1

    def test_the_browser_cookie_is_httponly_secure_and_scoped(self):
        from fastapi.responses import HTMLResponse

        response = HTMLResponse("x")
        auth_router._set_magic_link_browser_cookie(response)
        header = next(v.decode() for k, v in response.raw_headers if k == b"set-cookie")
        assert header.startswith(f"{auth_router.MAGIC_LINK_BROWSER_COOKIE}=")
        assert "HttpOnly" in header and "Secure" in header
        assert "samesite=lax" in header.lower()
        assert "Path=/api/v1/auth/magic-link/callback" in header


# --------------------------------------------------------------------------
# 3. The dead page says why, in the destination's language
# --------------------------------------------------------------------------


class TestDeadPageSaysWhy:
    async def test_used_link_in_spanish_for_a_ctm_destination(self, db, exchange):
        token = await _issue(db)
        phone, other = Browser(), Browser()
        await phone.open_link(token, db)
        await phone.press_button(token, db)

        page = await other.open_link(token, db)
        assert page.status_code == 400
        html = _text(page)
        assert 'lang="es-MX"' in html
        assert "Este enlace ya se usó" in html
        # A way back to the product, where the person may already be signed in.
        assert 'href="https://map.creatumundo.mx/"' in html
        assert "Link expired" not in html

    async def test_expired_link_says_expired(self, db, exchange):
        token = await _issue(db, minutes_left=-1)
        page = await Browser().open_link(token, db)
        assert page.status_code == 400
        html = _text(page)
        assert "Este enlace venció" in html
        assert "15 minutos" in html

    async def test_unknown_token_gets_the_generic_page(self, db, exchange):
        page = await Browser().open_link("not-a-real-token", db)
        assert page.status_code == 400
        assert "This link is not valid" in _text(page)

    async def test_dead_page_is_not_cached(self, db, exchange):
        page = await Browser().open_link("not-a-real-token", db)
        assert page.headers["cache-control"] == "no-store"


# --------------------------------------------------------------------------
# 4. The interstitial stops a second press where it can
# --------------------------------------------------------------------------


class TestInterstitialGuardsTheButton:
    async def test_button_is_disabled_once_pressed(self, db, exchange):
        token = await _issue(db)
        html = _text(await Browser().open_link(token, db))
        assert "data-janua-magic-link-form" in html
        # Plain string slicing, not a regex: the page is ours and fixed; this
        # only locates the one inline guard.
        assert html.count("<script>") == 1, "the interstitial must carry its double-submit guard"
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        assert "disabled = true" in script
        assert "pageshow" in script, "a back-navigation must re-enable the button"
        assert "Entrando" in html

    async def test_get_sets_the_browser_cookie_once(self, db, exchange):
        token = await _issue(db)
        phone = Browser()
        await phone.open_link(token, db)
        first = phone.cookies[auth_router.MAGIC_LINK_BROWSER_COOKIE]
        await phone.open_link(token, db)
        assert (
            phone.cookies[auth_router.MAGIC_LINK_BROWSER_COOKIE] == first
        ), "re-opening the link must not rotate the binding a pending press relies on"


# --------------------------------------------------------------------------
# 5. Concurrent presses cannot both pass the "unused" check
# --------------------------------------------------------------------------


def test_the_spend_reads_the_row_under_a_lock():
    """Two concurrent POSTs for one link both returned 302 at 15:28:14 UTC: both
    read used_at IS NULL before either committed. The read that decides the
    spend must lock the row (SELECT ... FOR UPDATE on Postgres), so the second
    press waits for the first and then takes the replay path."""
    source = inspect.getsource(auth_router.magic_link_callback)
    assert ".with_for_update()" in source


def test_the_get_still_spends_nothing():
    source = inspect.getsource(auth_router.magic_link_callback_interstitial)
    assert "used_at = datetime.utcnow()" not in source
    assert "create_session" not in source
    assert "_set_session_cookies" not in source
