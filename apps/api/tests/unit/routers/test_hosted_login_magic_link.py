"""Hosted login: magic link first when the client asks, password otherwise.

GET /api/v1/auth/login is where /authorize sends a browser without a session.
Until 2026-09-17 it rendered only an email + password form, although Janua has
had a complete passwordless path (POST /magic-link, the emailed callback,
first-contact user creation) all along. A public PKCE client whose users hold
no password — the Yantra4D Studio — had nowhere to send them. These tests pin:

* the method precedence (request hint → HOSTED_LOGIN_DEFAULT_METHOD → password),
* that magic link is offered only when the deployment can send mail,
* that /authorize carries `login_method` into the pre-login request and the
  login URL,
* that the hosted magic-link form issues a link whose destination is the
  REBUILT AUTHORIZE REQUEST (state + PKCE intact) on Janua's public origin, so
  the emailed link — opened in any tab — completes the same sign-in.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.login_method import effective_login_method, normalize_login_method
from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, MagicLink, User
from app.routers.v1.oauth_provider import authorize_get

LOGIN_URL = "/api/v1/auth/login"
MAGIC_FORM_URL = "/api/v1/auth/login-form/magic-link"
PASSWORD_FORM_ACTION = 'action="/api/v1/auth/login-form"'
MAGIC_FORM_ACTION = 'action="/api/v1/auth/login-form/magic-link"'


@pytest.fixture
def mail_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_MAGIC_LINKS", True)
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "HOSTED_LOGIN_DEFAULT_METHOD", "password")
    # A loopback public origin is on the default redirect allow-list, which is
    # what lets the continuation URL pass validate_redirect_url in this test.
    monkeypatch.setattr(settings, "JANUA_CUSTOM_DOMAIN", None)
    monkeypatch.setattr(settings, "BASE_URL", "http://localhost:8000")


@pytest_asyncio.fixture
async def hosted_client(mail_enabled):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    import fakeredis.aioredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _fake_get_redis():
        return fake_redis

    # conftest re-binds app.core.redis.get_redis at import time; a router that
    # was imported before that holds the original object, so key the override
    # on the reference the auth router actually passed to Depends().
    from app.routers.v1 import auth as auth_router

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = _fake_get_redis
    app.dependency_overrides[auth_router.get_redis] = _fake_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.__dict__["_redis"] = fake_redis
        client.__dict__["_sessions"] = session_factory
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


# ── the vocabulary ─────────────────────────────────────────────────────────

class TestLoginMethodPrecedence:
    def test_normalises_and_never_rejects(self):
        assert normalize_login_method("magic_link") == "magic_link"
        assert normalize_login_method(" Magic-Link ") == "magic_link"
        assert normalize_login_method("password") == "password"
        for bogus in ("sms", "", None, 42, "magic link"):
            assert normalize_login_method(bogus) is None

    def test_request_beats_deployment_default(self, mail_enabled, monkeypatch):
        monkeypatch.setattr(settings, "HOSTED_LOGIN_DEFAULT_METHOD", "magic_link")
        assert effective_login_method("password") == "password"
        assert effective_login_method(None) == "magic_link"
        assert effective_login_method("bogus") == "magic_link"

    def test_magic_link_needs_mail(self, mail_enabled, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
        assert effective_login_method("magic_link") == "password"
        monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
        monkeypatch.setattr(settings, "ENABLE_MAGIC_LINKS", False)
        assert effective_login_method("magic_link") == "password"


# ── the page ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_page_is_password_with_a_link_to_magic(hosted_client):
    resp = await hosted_client.get(LOGIN_URL, params={"auth_request_id": "req-1", "client_id": "c1", "client_name": "Studio"})
    assert resp.status_code == 200
    body = resp.text
    assert PASSWORD_FORM_ACTION in body
    assert 'name="password"' in body
    assert MAGIC_FORM_ACTION not in body
    assert "Email me a sign-in link instead" in body
    # The switch keeps the OAuth context.
    assert "login_method=magic_link" in body
    assert "auth_request_id=req-1" in body
    assert "client_id=c1" in body


@pytest.mark.asyncio
async def test_login_method_magic_link_renders_email_first(hosted_client):
    resp = await hosted_client.get(
        LOGIN_URL,
        params={"auth_request_id": "req-1", "client_id": "c1", "client_name": "Studio", "login_method": "magic_link"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert MAGIC_FORM_ACTION in body
    assert "Email me a sign-in link" in body
    assert 'name="password"' not in body
    assert PASSWORD_FORM_ACTION not in body
    assert '<input type="hidden" name="auth_request_id" value="req-1">' in body
    assert "Use a password instead" in body
    assert "login_method=password" in body and "auth_request_id=req-1" in body


@pytest.mark.asyncio
async def test_deployment_default_can_be_magic_link(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "HOSTED_LOGIN_DEFAULT_METHOD", "magic_link")
    resp = await hosted_client.get(LOGIN_URL)
    assert MAGIC_FORM_ACTION in resp.text
    assert 'name="password"' not in resp.text


@pytest.mark.asyncio
async def test_magic_link_mode_falls_back_when_mail_is_off(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    resp = await hosted_client.get(LOGIN_URL, params={"login_method": "magic_link"})
    body = resp.text
    assert PASSWORD_FORM_ACTION in body
    assert MAGIC_FORM_ACTION not in body
    # Nothing to switch to: no dead link is offered.
    assert "sign-in link instead" not in body


@pytest.mark.asyncio
async def test_unknown_method_is_ignored(hosted_client):
    resp = await hosted_client.get(LOGIN_URL, params={"login_method": "sms"})
    assert PASSWORD_FORM_ACTION in resp.text


# ── /authorize carries the hint ────────────────────────────────────────────

def _client_stub():
    return SimpleNamespace(
        client_id="jnc_studio",
        is_active=True,
        is_confidential=False,
        name="yantra4d-studio",
        allowed_scopes=["openid", "profile", "email"],
        redirect_uris=["https://app.yantra4d.com"],
        audience="yantra4d-api",
        last_used_at=None,
    )


@pytest.mark.asyncio
async def test_authorize_stores_and_forwards_login_method():
    redis = AsyncMock()
    with (
        patch("app.routers.v1.oauth_provider.get_user_from_cookie_or_header", AsyncMock(return_value=None)),
        patch("app.routers.v1.oauth_provider._get_oauth_client", AsyncMock(return_value=_client_stub())),
        patch("app.routers.v1.oauth_provider._validate_redirect_uri", MagicMock(return_value=True)),
    ):
        resp = await authorize_get(
            request=MagicMock(),
            response_type="code",
            client_id="jnc_studio",
            redirect_uri="https://app.yantra4d.com",
            scope="openid profile email",
            state="csrf-1",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt=None,
            login_method="magic_link",
            db=AsyncMock(),
            redis=redis,
        )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("/api/v1/auth/login?")
    query = parse_qs(urlparse(location).query)
    assert query["login_method"] == ["magic_link"]
    assert query["client_name"] == ["yantra4d-studio"]
    redis.setex.assert_awaited_once()
    key, _ttl, payload = redis.setex.await_args.args
    assert key.startswith("oauth:pre_login:")
    stored = json.loads(payload)
    assert stored["login_method"] == "magic_link"
    assert stored["state"] == "csrf-1" and stored["code_challenge"] == "abc"


@pytest.mark.asyncio
async def test_authorize_without_hint_leaves_login_url_unchanged():
    redis = AsyncMock()
    with (
        patch("app.routers.v1.oauth_provider.get_user_from_cookie_or_header", AsyncMock(return_value=None)),
        patch("app.routers.v1.oauth_provider._get_oauth_client", AsyncMock(return_value=_client_stub())),
        patch("app.routers.v1.oauth_provider._validate_redirect_uri", MagicMock(return_value=True)),
    ):
        resp = await authorize_get(
            request=MagicMock(), response_type="code", client_id="jnc_studio",
            redirect_uri="https://app.yantra4d.com", scope="openid", state="s", nonce=None,
            code_challenge="abc", code_challenge_method="S256", prompt=None, login_method="bogus",
            db=AsyncMock(), redis=redis,
        )
    assert "login_method" not in resp.headers["location"]
    assert json.loads(redis.setex.await_args.args[2])["login_method"] is None


# ── the hosted form issues a link that resumes the authorize request ──────

@pytest.mark.asyncio
async def test_form_issues_link_whose_destination_resumes_the_authorize_request(hosted_client):
    redis = hosted_client.__dict__["_redis"]
    await redis.set(
        "oauth:pre_login:req-1",
        json.dumps({
            "response_type": "code", "client_id": "jnc_studio",
            "redirect_uri": "https://app.yantra4d.com", "scope": "openid profile email",
            "state": "csrf-1", "nonce": None, "code_challenge": "abc",
            "code_challenge_method": "S256", "login_method": "magic_link",
        }),
    )
    mailer = MagicMock()
    with patch("app.routers.v1.auth.send_magic_link_email_task", mailer):
        resp = await hosted_client.post(
            MAGIC_FORM_URL,
            # A deliverable-looking domain: the validator rejects reserved names such as .test
            data={"email": "Aldo@Studio-Test.io", "auth_request_id": "req-1", "client_id": "jnc_studio", "client_name": "Studio"},
        )
    assert resp.status_code == 200, resp.text
    assert "Check your inbox" in resp.text
    assert "a***@studio-test.io" in resp.text.lower()
    assert "Use a password instead" in resp.text and "login_method=password" in resp.text

    sessions = hosted_client.__dict__["_sessions"]
    async with sessions() as session:
        links = (await session.execute(select(MagicLink))).scalars().all()
        users = (await session.execute(select(User))).scalars().all()
    assert len(links) == 1 and len(users) == 1, "first contact creates the user and one link"
    link = links[0]
    assert link.email == users[0].email
    destination = link.redirect_url
    assert destination.startswith("http://localhost:8000/api/v1/oauth/authorize?"), destination
    query = parse_qs(urlparse(destination).query)
    assert query["state"] == ["csrf-1"]
    assert query["code_challenge"] == ["abc"]
    assert query["client_id"] == ["jnc_studio"]
    assert query["redirect_uri"] == ["https://app.yantra4d.com"]
    assert "login_method" not in query
    # The mail carried the same destination and the minted token.
    mailer.assert_called_once()
    args = mailer.call_args.args
    assert args[0] == users[0].email and args[1] == link.token and args[2] == destination
    # "Use a password instead" must still work: the pre-login request survives.
    assert await redis.get("oauth:pre_login:req-1") is not None


@pytest.mark.asyncio
async def test_form_with_expired_context_says_so(hosted_client):
    with patch("app.routers.v1.auth.send_magic_link_email_task", MagicMock()) as mailer:
        resp = await hosted_client.post(MAGIC_FORM_URL, data={"email": "a@studio-test.io", "auth_request_id": "gone"})
    assert resp.status_code == 400
    assert "Sign-in session expired" in resp.text
    mailer.assert_not_called()


@pytest.mark.asyncio
async def test_form_rejects_a_bad_email_and_keeps_the_magic_form(hosted_client):
    with patch("app.routers.v1.auth.send_magic_link_email_task", MagicMock()) as mailer:
        resp = await hosted_client.post(MAGIC_FORM_URL, data={"email": "not-an-email", "next": "/"})
    assert resp.status_code == 400
    assert MAGIC_FORM_ACTION in resp.text
    assert "valid email" in resp.text
    mailer.assert_not_called()


@pytest.mark.asyncio
async def test_form_without_mail_offers_the_password_form(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    resp = await hosted_client.post(MAGIC_FORM_URL, data={"email": "a@studio-test.io", "next": "/"})
    assert resp.status_code == 400
    assert PASSWORD_FORM_ACTION in resp.text


# ── the client name is text, never markup ──────────────────────────────────
#
# `client_name` arrives from the query string (GET /login) and from the form
# (POST /login-form/magic-link); both pages print it. The page renderers own
# the escaping, so a caller cannot forget it and cannot double-escape it.

HOSTILE_NAME = '<script>alert("x")</script> & Co'
ESCAPED_NAME = "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Co"


@pytest.mark.asyncio
async def test_login_page_escapes_the_client_name(hosted_client):
    resp = await hosted_client.get(
        LOGIN_URL, params={"client_name": HOSTILE_NAME, "login_method": "magic_link"}
    )
    assert resp.status_code == 200
    assert HOSTILE_NAME not in resp.text
    assert f"Signing in to <strong>{ESCAPED_NAME}</strong>" in resp.text
    # the hidden field carries it back, escaped as an attribute value
    assert f'name="client_name" value="{ESCAPED_NAME}"' in resp.text


@pytest.mark.asyncio
async def test_magic_form_error_page_escapes_the_client_name(hosted_client):
    with patch("app.routers.v1.auth.send_magic_link_email_task", MagicMock()):
        resp = await hosted_client.post(
            MAGIC_FORM_URL,
            data={"email": "not-an-email", "next": "/", "client_name": HOSTILE_NAME},
        )
    assert resp.status_code == 400
    assert HOSTILE_NAME not in resp.text
    assert f"Signing in to <strong>{ESCAPED_NAME}</strong>" in resp.text


@pytest.mark.asyncio
async def test_check_inbox_page_escapes_the_client_name_once(hosted_client):
    with patch("app.routers.v1.auth.send_magic_link_email_task", MagicMock()):
        resp = await hosted_client.post(
            MAGIC_FORM_URL,
            data={"email": "a@studio-test.io", "next": "/", "client_name": HOSTILE_NAME},
        )
    assert resp.status_code == 200
    assert HOSTILE_NAME not in resp.text
    assert f"continue to <strong>{ESCAPED_NAME}</strong>" in resp.text
    assert "&amp;amp;" not in resp.text
