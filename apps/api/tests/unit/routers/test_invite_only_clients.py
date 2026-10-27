"""Invite-only clients and operator invitations (2026-10-22, MADFAM CV beta).

Pins, end to end over the real app with SQLite + fakeredis:

* the policy parser fails CLOSED (a listed client without a product is locked);
* /oauth/authorize refuses a signed-in person without the client's product
  entitlement (page for interactive, access_denied for prompt=none) and lets an
  entitled one through; open clients are untouched;
* the token endpoint refuses the code and refresh grants the same way;
* a sign-in link for an invite-only client never creates an identity, and the
  hosted form answers identically for invited and unknown addresses;
* POST /internal/product-invites creates a passwordless identity, grants the
  product, mints ONE single-use link that lands on Janua (never on the product)
  and queues ONE mail naming the client; re-inviting is the resend;
* /revoke cancels the entitlement and spends the unused invitation links;
* /auth/app-entry forwards to the client's front door and drops ?token=.

No real address appears anywhere: every address is on example.com.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import (
    Base,
    EntitlementSource,
    MagicLink,
    OAuthClient,
    User,
    UserEntitlement,
    UserStatus,
)
from app.routers.v1 import oauth_provider
from app.services.entitlements_service import Entitlement
from app.services.invite_only_clients import (
    has_invited_access,
    invite_only_product,
    parse_invite_only_clients,
)

CLIENT_ID = "jnc_cv_test_client"
OPEN_CLIENT_ID = "jnc_open_test_client"
INTERNAL_KEY = "test-internal-api-key-product-invites"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}
INVITE_URL = "/api/v1/internal/product-invites"
REVOKE_URL = "/api/v1/internal/product-invites/revoke"
MAGIC_FORM_URL = "/api/v1/auth/login-form/magic-link"
INVITEE = "invitee@beta-cv.example.com"
STRANGER = "stranger@beta-cv.example.com"


@pytest.fixture
def invite_only(monkeypatch):
    monkeypatch.setattr(settings, "INVITE_ONLY_CLIENTS", f"{CLIENT_ID}=cv")
    monkeypatch.setattr(settings, "ENABLE_MAGIC_LINKS", True)
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "JANUA_CUSTOM_DOMAIN", None)
    monkeypatch.setattr(settings, "BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)


@pytest_asyncio.fixture
async def env(invite_only):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with sessions() as session:
            yield session

    import fakeredis.aioredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _fake_get_redis():
        return fake_redis

    from app.routers.v1 import auth as auth_router

    owner_id = uuid.uuid4()
    async with sessions() as session:
        for client_id, name in ((CLIENT_ID, "MADFAM CV"), (OPEN_CLIENT_ID, "Open App")):
            session.add(
                OAuthClient(
                    created_by=owner_id,
                    client_id=client_id,
                    client_secret_hash="not-a-real-hash",
                    client_secret_prefix="jns_test",
                    name=name,
                    redirect_uris=[f"https://{client_id}.example.com/api/auth/callback/janua"],
                    is_active=True,
                )
            )
        await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = _fake_get_redis
    app.dependency_overrides[auth_router.get_redis] = _fake_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield SimpleNamespace(http=client, sessions=sessions, redis=fake_redis)
    app.dependency_overrides.clear()
    await engine.dispose()


async def _rows(sessions, model):
    async with sessions() as session:
        return (await session.execute(select(model))).scalars().all()


# ── the policy ─────────────────────────────────────────────────────────────


class TestPolicy:
    def test_parses_pairs_and_locks_a_client_without_a_product(self):
        policy = parse_invite_only_clients(" a=cv , b= , c=Bad Slug, =orphan, d=yantra4d ")
        assert policy == {"a": "cv", "b": "", "c": "", "d": "yantra4d"}

    def test_empty_setting_leaves_every_client_open(self, monkeypatch):
        monkeypatch.setattr(settings, "INVITE_ONLY_CLIENTS", "")
        assert invite_only_product(CLIENT_ID) is None

    @pytest.mark.asyncio
    async def test_access_follows_the_product_entitlement(self, monkeypatch):
        monkeypatch.setattr(settings, "INVITE_ONLY_CLIENTS", f"{CLIENT_ID}=cv,locked=")
        user = SimpleNamespace(id=uuid.uuid4())
        entitled = [Entitlement("cv", "beta", None, EntitlementSource.ADMIN_GRANT)]
        other = [Entitlement("karafiel", "pro", None, EntitlementSource.ADMIN_GRANT)]
        target = "app.services.entitlements_service.get_user_entitlements"
        with patch(target, AsyncMock(return_value=entitled)):
            assert await has_invited_access(user, CLIENT_ID, AsyncMock()) is True
            assert await has_invited_access(user, "locked", AsyncMock()) is False
        with patch(target, AsyncMock(return_value=other)):
            assert await has_invited_access(user, CLIENT_ID, AsyncMock()) is False
        with patch(target, AsyncMock(side_effect=RuntimeError("db down"))):
            assert await has_invited_access(user, CLIENT_ID, AsyncMock()) is False
        # An open client never reads anything.
        with patch(target, AsyncMock(side_effect=AssertionError("read"))):
            assert await has_invited_access(user, OPEN_CLIENT_ID, AsyncMock()) is True


# ── /oauth/authorize ───────────────────────────────────────────────────────


def _client(client_id=CLIENT_ID, name="MADFAM CV"):
    return SimpleNamespace(
        client_id=client_id,
        is_active=True,
        is_confidential=True,
        name=name,
        allowed_scopes=["openid", "profile", "email", "offline_access"],
        redirect_uris=["https://cv.example.com/api/auth/callback/janua"],
        audience="cv-api",
        organization_id=None,
        last_used_at=None,
    )


async def _authorize(user, client, *, prompt=None, ui_locales=None, entitlements=()):
    with (
        patch.object(oauth_provider, "get_user_from_cookie_or_header", AsyncMock(return_value=user)),
        patch.object(oauth_provider, "_get_oauth_client", AsyncMock(return_value=client)),
        patch.object(oauth_provider, "_validate_redirect_uri", MagicMock(return_value=True)),
        patch.object(oauth_provider, "_is_silent_auth_allowed", MagicMock(return_value=True)),
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=list(entitlements)),
        ),
    ):
        return await oauth_provider.authorize_get(
            request=MagicMock(),
            response_type="code",
            client_id=client.client_id,
            redirect_uri="https://cv.example.com/api/auth/callback/janua",
            scope="openid profile email",
            state="state-1",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt=prompt,
            login_method=None,
            ui_locales=ui_locales,
            db=AsyncMock(),
            redis=AsyncMock(),
        )


def _user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="someone@beta-cv.example.com",
        email_verified=True,
        created_at=datetime.utcnow(),
        status=UserStatus.ACTIVE,
        mfa_enabled=False,
        is_admin=False,
    )


@pytest.mark.asyncio
async def test_authorize_refuses_an_uninvited_person_with_a_page_in_their_language(invite_only):
    resp = await _authorize(_user(), _client(), ui_locales="es-MX")
    assert resp.status_code == 403
    body = resp.body.decode()
    assert '<html lang="es-MX">' in body
    assert "Esta cuenta no tiene acceso a <strong>MADFAM CV</strong>" in body
    assert "El acceso es por invitación" in body
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_authorize_refusal_is_english_without_ui_locales(invite_only):
    resp = await _authorize(_user(), _client())
    assert resp.status_code == 403
    assert "This account has no access to <strong>MADFAM CV</strong>" in resp.body.decode()


@pytest.mark.asyncio
async def test_silent_authorize_answers_access_denied(invite_only):
    resp = await _authorize(_user(), _client(), prompt="none")
    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["error"] == ["access_denied"]
    assert query["error_description"] == ["invite_only"]
    assert query["state"] == ["state-1"]


@pytest.mark.asyncio
async def test_authorize_lets_an_invited_person_through(invite_only):
    entitled = [Entitlement("cv", "beta", None, EntitlementSource.ADMIN_GRANT)]
    with patch.object(oauth_provider.ConsentService, "has_consent", AsyncMock(return_value=False)):
        resp = await _authorize(_user(), _client(), entitlements=entitled, prompt="none")
    # Past the gate: the next stop for this (non-first-party) stub is consent.
    assert "invite_only" not in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_open_clients_are_untouched(invite_only):
    with patch.object(oauth_provider.ConsentService, "has_consent", AsyncMock(return_value=False)):
        resp = await _authorize(_user(), _client(OPEN_CLIENT_ID, "Open App"), prompt="none")
    assert "invite_only" not in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_authorize_carries_ui_locales_to_the_login_page(invite_only):
    redis = AsyncMock()
    with (
        patch.object(oauth_provider, "get_user_from_cookie_or_header", AsyncMock(return_value=None)),
        patch.object(oauth_provider, "_get_oauth_client", AsyncMock(return_value=_client())),
        patch.object(oauth_provider, "_validate_redirect_uri", MagicMock(return_value=True)),
    ):
        resp = await oauth_provider.authorize_get(
            request=MagicMock(), response_type="code", client_id=CLIENT_ID,
            redirect_uri="https://cv.example.com/api/auth/callback/janua", scope="openid",
            state="s", nonce=None, code_challenge="abc", code_challenge_method="S256",
            prompt=None, login_method="magic_link", ui_locales="es-MX en", db=AsyncMock(),
            redis=redis,
        )
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["ui_locales"] == ["es"]
    stored = json.loads(redis.strict_set.await_args.args[1])
    assert stored["ui_locales"] == "es"
    from app.auth.authorize_resume import authorize_query

    assert authorize_query(stored)["ui_locales"] == "es"


# ── the token endpoint ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_token_grants_refuse_an_uninvited_person(invite_only):
    target = "app.services.entitlements_service.get_user_entitlements"
    with patch(target, AsyncMock(return_value=[])):
        with pytest.raises(HTTPException) as refused:
            await oauth_provider._require_invited_access(_user(), _client(), AsyncMock())
    assert refused.value.status_code == 400
    assert refused.value.detail.startswith("invalid_grant")
    entitled = [Entitlement("cv", "beta", None, EntitlementSource.ADMIN_GRANT)]
    with patch(target, AsyncMock(return_value=entitled)):
        await oauth_provider._require_invited_access(_user(), _client(), AsyncMock())
    # Open client: no read, no refusal.
    with patch(target, AsyncMock(side_effect=AssertionError("read"))):
        await oauth_provider._require_invited_access(
            _user(), _client(OPEN_CLIENT_ID, "Open App"), AsyncMock()
        )


# ── sign-in links never create identities for an invite-only client ───────


async def _pre_login(redis, request_id="req-1", client_id=CLIENT_ID, ui_locales="es"):
    await redis.set(
        f"oauth:pre_login:{request_id}",
        json.dumps({
            "response_type": "code", "client_id": client_id,
            "redirect_uri": f"https://{client_id}.example.com/api/auth/callback/janua",
            "scope": "openid", "state": "s", "nonce": None, "code_challenge": "abc",
            "code_challenge_method": "S256", "login_method": "magic_link",
            "ui_locales": ui_locales,
        }),
    )


@pytest.mark.asyncio
async def test_hosted_form_does_not_create_a_stranger_and_says_the_same_thing(env):
    await _pre_login(env.redis)
    mailer = MagicMock()
    with patch("app.routers.v1.auth.send_magic_link_email_task", mailer):
        resp = await env.http.post(
            MAGIC_FORM_URL,
            data={"email": STRANGER, "auth_request_id": "req-1", "client_id": CLIENT_ID,
                  "client_name": "MADFAM CV", "ui_locales": "es"},
        )
    assert resp.status_code == 200, resp.text
    assert "Si esta dirección tiene invitación a <strong>MADFAM CV</strong>" in resp.text
    assert '<html lang="es-MX">' in resp.text
    mailer.assert_not_called()
    assert await _rows(env.sessions, User) == []
    assert await _rows(env.sessions, MagicLink) == []

    # An invited address gets a link, in the page's language, behind the SAME words.
    async with env.sessions() as session:
        session.add(User(email=INVITEE, status=UserStatus.ACTIVE, user_metadata={}))
        await session.commit()
    with patch("app.routers.v1.auth.send_magic_link_email_task", mailer):
        resp = await env.http.post(
            MAGIC_FORM_URL,
            data={"email": INVITEE, "auth_request_id": "req-1", "client_id": CLIENT_ID,
                  "client_name": "MADFAM CV", "ui_locales": "es"},
        )
    assert "Si esta dirección tiene invitación a <strong>MADFAM CV</strong>" in resp.text
    mailer.assert_called_once()
    assert mailer.call_args.kwargs["locale"] == "es"
    destination = mailer.call_args.args[2]
    assert parse_qs(urlparse(destination).query)["ui_locales"] == ["es"]


@pytest.mark.asyncio
async def test_open_client_still_creates_on_first_contact(env):
    await _pre_login(env.redis, client_id=OPEN_CLIENT_ID, ui_locales=None)
    mailer = MagicMock()
    with patch("app.routers.v1.auth.send_magic_link_email_task", mailer):
        resp = await env.http.post(
            MAGIC_FORM_URL,
            data={"email": STRANGER, "auth_request_id": "req-1", "client_id": OPEN_CLIENT_ID,
                  "client_name": "Open App"},
        )
    assert resp.status_code == 200
    assert "Check your inbox" in resp.text and "We emailed a sign-in link to" in resp.text
    assert len(await _rows(env.sessions, User)) == 1
    mailer.assert_called_once()


@pytest.mark.asyncio
async def test_api_magic_link_for_an_invite_only_host_creates_nobody(env):
    mailer = MagicMock()
    with patch("app.routers.v1.auth.send_magic_link_email_task", mailer):
        resp = await env.http.post(
            "/api/v1/auth/magic-link",
            json={"email": STRANGER, "redirect_url": f"https://{CLIENT_ID}.example.com/"},
        )
    assert resp.status_code == 200
    mailer.assert_not_called()
    assert await _rows(env.sessions, User) == []


# ── operator invitations ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_creates_grants_and_mails_one_link(env):
    mailer = MagicMock()
    with patch("app.routers.v1.internal_product_invites.send_product_invite_email_task", mailer):
        resp = await env.http.post(
            INVITE_URL,
            json={"email": "Invitee@Beta-CV.example.com", "client_id": CLIENT_ID,
                  "first_name": "Ana", "formality": "tu"},
            headers=AUTH,
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user_created"] is True and body["entitlement_granted"] is True
    assert body["product"] == "cv" and body["tier"] == "beta"
    assert "token" not in json.dumps(body).lower()

    [user] = await _rows(env.sessions, User)
    assert user.email == INVITEE and user.password_hash is None
    assert user.locale == "es" and user.status == UserStatus.ACTIVE
    [grant] = await _rows(env.sessions, UserEntitlement)
    assert (grant.product, grant.tier, grant.expires_at) == ("cv", "beta", None)
    assert grant.source == EntitlementSource.ADMIN_GRANT
    [link] = await _rows(env.sessions, MagicLink)
    assert link.used_at is None
    assert timedelta(hours=71) < link.expires_at - datetime.utcnow() <= timedelta(hours=72)
    entry = urlparse(link.redirect_url)
    assert entry.netloc == "localhost:8000" and entry.path == "/api/v1/auth/app-entry"
    assert parse_qs(entry.query) == {"client_id": [CLIENT_ID], "ui_locales": ["es"]}

    mailer.assert_called_once()
    args, kwargs = mailer.call_args
    assert args == (INVITEE, link.token)
    assert kwargs["app_name"] == "MADFAM CV" and kwargs["expires_hours"] == 72
    assert kwargs["locale"] == "es" and kwargs["formality"] == "tu"

    # Re-inviting is the resend: same person, same grant, a fresh link.
    with patch("app.routers.v1.internal_product_invites.send_product_invite_email_task", mailer):
        again = await env.http.post(INVITE_URL, json={"email": INVITEE, "client_id": CLIENT_ID}, headers=AUTH)
    assert again.status_code == 201
    assert again.json()["user_created"] is False and again.json()["entitlement_granted"] is False
    assert len(await _rows(env.sessions, MagicLink)) == 2
    assert len(await _rows(env.sessions, User)) == 1


@pytest.mark.asyncio
async def test_invite_refuses_open_clients_and_needs_the_key(env):
    resp = await env.http.post(INVITE_URL, json={"email": INVITEE, "client_id": OPEN_CLIENT_ID}, headers=AUTH)
    assert resp.status_code == 409
    resp = await env.http.post(INVITE_URL, json={"email": INVITEE, "client_id": CLIENT_ID})
    assert resp.status_code in (401, 403, 422)  # missing X-Internal-API-Key
    assert await _rows(env.sessions, User) == []


@pytest.mark.asyncio
async def test_invite_refuses_a_suspended_account(env):
    async with env.sessions() as session:
        session.add(User(email=INVITEE, status=UserStatus.SUSPENDED, user_metadata={}))
        await session.commit()
    resp = await env.http.post(INVITE_URL, json={"email": INVITEE, "client_id": CLIENT_ID}, headers=AUTH)
    assert resp.status_code == 409
    assert await _rows(env.sessions, UserEntitlement) == []


@pytest.mark.asyncio
async def test_revoke_cancels_the_grant_and_spends_unused_links(env):
    with patch("app.routers.v1.internal_product_invites.send_product_invite_email_task", MagicMock()):
        await env.http.post(INVITE_URL, json={"email": INVITEE, "client_id": CLIENT_ID}, headers=AUTH)
    resp = await env.http.post(REVOKE_URL, json={"email": INVITEE, "client_id": CLIENT_ID}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    assert resp.json()["changed"] is True and resp.json()["links_spent"] == 1
    [grant] = await _rows(env.sessions, UserEntitlement)
    assert grant.expires_at is not None and grant.expires_at <= datetime.utcnow()
    [link] = await _rows(env.sessions, MagicLink)
    assert link.used_at is not None
    again = await env.http.post(REVOKE_URL, json={"email": INVITEE, "client_id": CLIENT_ID}, headers=AUTH)
    assert again.json()["changed"] is False and again.json()["links_spent"] == 0
    unknown = await env.http.post(REVOKE_URL, json={"email": STRANGER, "client_id": CLIENT_ID}, headers=AUTH)
    assert unknown.status_code == 404


# ── where the invitation link lands ───────────────────────────────────────


@pytest.mark.asyncio
async def test_app_entry_goes_to_the_front_door_and_drops_the_token(env):
    resp = await env.http.get(
        "/api/v1/auth/app-entry",
        params={"client_id": CLIENT_ID, "ui_locales": "es", "token": "an-access-token"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == f"https://{CLIENT_ID}.example.com/"
    assert resp.headers["cache-control"] == "no-store"
    # Cross-origin, the product is sent only Janua's origin as referrer.
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    unknown = await env.http.get("/api/v1/auth/app-entry", params={"client_id": "nope"})
    assert unknown.status_code == 404


def test_interstitial_follows_the_destinations_ui_locales():
    from app.routers.v1.auth import _magic_link_interstitial_is_spanish

    assert _magic_link_interstitial_is_spanish(
        "http://localhost:8000/api/v1/auth/app-entry?client_id=x&ui_locales=es"
    )
    assert not _magic_link_interstitial_is_spanish(
        "http://localhost:8000/api/v1/auth/app-entry?client_id=x&ui_locales=en"
    )
    assert _magic_link_interstitial_is_spanish("https://map.creatumundo.mx/x")
    assert not _magic_link_interstitial_is_spanish("https://app.example.com/x")
