"""HTTP behaviour of revocation: sign-out, session deletion and RFC 7009 revoke.

Owner decision (2026-10-04): "yes, go ahead with the follow-up Janua PR"
(J2-006, J2-007, J2-010).

Driven through the real app with a real (SQLite) database and a
fakeredis-backed `ResilientRedisClient`:

- `POST /auth/signout`: the session's refresh token stops refreshing (401).
- `DELETE /sessions/{id}`: owner or admin only (anyone else 404); the row is
  revoked, its refresh token stops refreshing, account switching and the
  account chooser stop offering it. `DELETE /sessions` revokes every other
  session and keeps the current one.
- `POST /oauth/revoke` (RFC 7009): client authentication required; a refresh
  token revokes its family (refresh grant then `invalid_grant`, including the
  token a rotation minted from it); an access token is blacklisted (introspect
  inactive, userinfo 401); a wrong `token_type_hint` still works; an unknown
  token, or another client's token, answers 200 and changes nothing; Redis
  down answers 503 + Retry-After.
"""

from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bcrypt
import fakeredis
import pytest
import pytest_asyncio

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.jwt_manager import jwt_manager
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Base, OAuthClient, User, UserStatus
from app.models import Session as UserSession
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio

CLIENT_A = "jnc_test_revoke_client_a"
SECRET_A = "jns_test_revoke_secret_a_placeholder"
CLIENT_B = "jnc_test_revoke_client_b"
SECRET_B = "jns_test_revoke_secret_b_placeholder"
PUBLIC_CLIENT = "jnc_test_revoke_public_client"


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=4)).decode()


def _client(created_by, client_id, secret=None) -> OAuthClient:
    # A public client still has a (never presented) secret hash: the column is
    # NOT NULL. `is_confidential=False` is what makes it public.
    stored = secret or "jns_test_public_unused_placeholder"
    return OAuthClient(
        id=uuid.uuid4(),
        created_by=created_by,
        client_id=client_id,
        client_secret_hash=_hash(stored),
        client_secret_prefix=stored[:8],
        name=client_id,
        redirect_uris=["https://app.example.test/callback"],
        allowed_scopes=["openid", "profile", "email"],
        grant_types=["authorization_code", "refresh_token"],
        is_active=True,
        is_confidential=secret is not None,
    )


@pytest_asyncio.fixture
async def env():
    from app import dependencies
    from app.core import redis as core_redis
    from app.core.database import get_db as core_get_db
    from app.database import get_db
    from app.main import app
    from app.routers.v1 import auth as auth_router
    from app.routers.v1 import oauth_provider

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    server = fakeredis.FakeServer()
    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))

    async def override_get_db():
        async with factory() as session:
            yield session

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    for dep in {
        core_redis.get_redis,
        dependencies.get_redis,
        oauth_provider.get_redis,
        auth_router.get_redis,
    }:
        app.dependency_overrides[dep] = lambda: redis

    admin = User(
        id=uuid.uuid4(),
        email="admin-revocation@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_admin=True,
        is_active=True,
    )
    alice = User(
        id=uuid.uuid4(),
        email="alice-revocation@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    bob = User(
        id=uuid.uuid4(),
        email="bob-revocation@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    async with factory() as session:
        session.add_all([admin, alice, bob])
        await session.flush()
        session.add_all(
            [
                _client(admin.id, CLIENT_A, SECRET_A),
                _client(admin.id, CLIENT_B, SECRET_B),
                _client(admin.id, PUBLIC_CLIENT),
            ]
        )
        await session.commit()

    get = AsyncMock(return_value=redis)
    with (
        patch("app.core.redis.get_redis", get),
        patch("app.services.auth_service.get_redis", get),
        patch("app.routers.v1.oauth_provider.get_redis", get),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield SimpleNamespace(
                http=http,
                factory=factory,
                redis=redis,
                server=server,
                admin=admin,
                alice=alice,
                bob=bob,
            )

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    await engine.dispose()


async def _sign_in(env, user):
    async with env.factory() as db:
        fresh = await db.get(User, user.id)
        access, refresh, session = await AuthService.create_session(db, fresh)
        return access, refresh, session.id


async def _refresh(env, refresh_token):
    return await env.http.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


async def _row(env, session_id) -> UserSession:
    async with env.factory() as db:
        result = await db.execute(select(UserSession).where(UserSession.id == session_id))
        return result.scalar_one()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _assert_unavailable(resp):
    assert resp.status_code == 503, resp.text
    assert resp.headers["retry-after"].isdigit()


# ---------------------------------------------------------------------------
# Sign-out (J2-006)
# ---------------------------------------------------------------------------


class TestSignOut:
    async def test_signed_out_refresh_token_is_refused(self, env):
        access, refresh, session_id = await _sign_in(env, env.alice)

        resp = await env.http.post("/api/v1/auth/signout", headers=_bearer(access))
        assert resp.status_code == 200, resp.text

        assert (await _refresh(env, refresh)).status_code == 401
        row = await _row(env, session_id)
        assert row.revoked is True and row.is_active is False

    async def test_before_sign_out_the_same_refresh_token_works(self, env):
        _, refresh, _ = await _sign_in(env, env.alice)
        resp = await _refresh(env, refresh)
        assert resp.status_code == 200, resp.text

    async def test_refresh_answers_503_when_redis_is_down(self, env):
        _, refresh, _ = await _sign_in(env, env.alice)
        env.server.connected = False
        _assert_unavailable(await _refresh(env, refresh))


# ---------------------------------------------------------------------------
# DELETE /sessions/{id} and DELETE /sessions (J2-007)
# ---------------------------------------------------------------------------


class TestDeleteSession:
    async def test_owner_revokes_their_session_and_its_refresh_stops(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        _, other_refresh, other_id = await _sign_in(env, env.alice)

        resp = await env.http.delete(f"/api/v1/sessions/{other_id}", headers=_bearer(access))

        assert resp.status_code == 200, resp.text
        row = await _row(env, other_id)
        assert row.revoked is True and row.is_active is False
        assert row.revoked_reason == "user_revoked"
        assert (await _refresh(env, other_refresh)).status_code == 401

    async def test_another_user_cannot_revoke_it(self, env):
        _, alice_refresh, alice_session = await _sign_in(env, env.alice)
        bob_access, _, _ = await _sign_in(env, env.bob)

        resp = await env.http.delete(
            f"/api/v1/sessions/{alice_session}", headers=_bearer(bob_access)
        )

        assert resp.status_code == 404
        assert (await _row(env, alice_session)).revoked is False
        assert (await _refresh(env, alice_refresh)).status_code == 200

    async def test_an_admin_can_revoke_it(self, env):
        _, alice_refresh, alice_session = await _sign_in(env, env.alice)
        admin_access, _, _ = await _sign_in(env, env.admin)

        resp = await env.http.delete(
            f"/api/v1/sessions/{alice_session}", headers=_bearer(admin_access)
        )

        assert resp.status_code == 200, resp.text
        assert (await _row(env, alice_session)).revoked_reason == "admin_revoked"
        assert (await _refresh(env, alice_refresh)).status_code == 401

    async def test_revoking_twice_is_refused(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        _, _, other_id = await _sign_in(env, env.alice)
        first = await env.http.delete(f"/api/v1/sessions/{other_id}", headers=_bearer(access))
        assert first.status_code == 200
        resp = await env.http.delete(f"/api/v1/sessions/{other_id}", headers=_bearer(access))
        assert resp.status_code == 400

    async def test_the_revoked_session_leaves_the_list_and_the_account_chooser(self, env):
        from app.auth.sso_cookie import resolve_session_by_id
        from app.routers.v1.oauth_provider import _resolve_held_accounts

        access, _, current_id = await _sign_in(env, env.alice)
        _, _, other_id = await _sign_in(env, env.alice)
        _, _, bob_id = await _sign_in(env, env.bob)

        await env.http.delete(f"/api/v1/sessions/{other_id}", headers=_bearer(access))

        listed = await env.http.get("/api/v1/sessions/", headers=_bearer(access))
        assert listed.status_code == 200, listed.text
        ids = {s["id"] for s in listed.json()["sessions"]}
        assert str(other_id) not in ids and str(current_id) in ids

        async with env.factory() as db:
            assert await resolve_session_by_id(str(other_id), db) == (None, None)
            # Bob's session is held first so Alice's revoked row cannot
            # shadow a live one of hers in the one-per-person reduction.
            held = await _resolve_held_accounts([str(bob_id), str(other_id)], db)
        assert [sid for sid, _ in held] == [str(bob_id)]

    async def test_redis_down_still_revokes_the_row(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        _, other_refresh, other_id = await _sign_in(env, env.alice)
        env.server.connected = False

        resp = await env.http.delete(f"/api/v1/sessions/{other_id}", headers=_bearer(access))

        assert resp.status_code == 200, resp.text
        assert (await _row(env, other_id)).revoked is True
        env.server.connected = True
        assert (await _refresh(env, other_refresh)).status_code == 401


class TestDeleteAllSessions:
    async def test_every_other_session_is_revoked_and_the_current_one_kept(self, env):
        access, current_refresh, current_id = await _sign_in(env, env.alice)
        others = [await _sign_in(env, env.alice) for _ in range(2)]
        _, bob_refresh, _ = await _sign_in(env, env.bob)

        resp = await env.http.delete("/api/v1/sessions/", headers=_bearer(access))

        assert resp.status_code == 200, resp.text
        assert resp.json()["revoked_count"] == 2
        for _, refresh, _ in others:
            assert (await _refresh(env, refresh)).status_code == 401
        assert (await _row(env, current_id)).revoked is False
        assert (await _refresh(env, current_refresh)).status_code == 200
        assert (await _refresh(env, bob_refresh)).status_code == 200


class TestPerAccountSignOut:
    async def test_revoke_sso_session_stops_refresh(self, env):
        from app.auth.sso_cookie import revoke_sso_session

        _, refresh, session_id = await _sign_in(env, env.alice)
        async with env.factory() as db:
            revoked = await revoke_sso_session(str(session_id), db)
            assert revoked is True
            await db.commit()
        assert (await _refresh(env, refresh)).status_code == 401


# ---------------------------------------------------------------------------
# POST /oauth/revoke, RFC 7009 (J2-010)
# ---------------------------------------------------------------------------


def _oauth_tokens(user, client_id):
    audience = settings.JWT_AUDIENCE
    access, _, _ = jwt_manager.create_access_token(
        user_id=str(user.id),
        email=user.email,
        additional_claims={"client_id": client_id, "aud": audience, "scope": "openid"},
    )
    refresh, _, _, _ = jwt_manager.create_refresh_token(
        user_id=str(user.id),
        additional_claims={"client_id": client_id, "aud": audience, "scope": "openid"},
    )
    return access, refresh


async def _revoke(env, token, *, client_id=CLIENT_A, secret=SECRET_A, hint=None, basic=False):
    data = {"token": token}
    headers = {}
    if hint:
        data["token_type_hint"] = hint
    if basic:
        raw = f"{client_id}:{secret}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
    else:
        if client_id:
            data["client_id"] = client_id
        if secret:
            data["client_secret"] = secret
    return await env.http.post("/api/v1/oauth/revoke", data=data, headers=headers)


async def _refresh_grant(env, refresh, *, client_id=CLIENT_A, secret=SECRET_A):
    return await env.http.post(
        "/api/v1/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
            "client_secret": secret,
        },
    )


async def _introspect(env, token, *, client_id=CLIENT_A, secret=SECRET_A):
    return await env.http.post(
        "/api/v1/oauth/introspect",
        data={"token": token, "client_id": client_id, "client_secret": secret},
    )


class TestOAuthRevokeClientAuthentication:
    async def test_no_client_is_401(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        resp = await _revoke(env, refresh, client_id=None, secret=None)
        assert resp.status_code == 401
        assert (await _refresh_grant(env, refresh)).status_code == 200

    async def test_wrong_secret_is_401(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        resp = await _revoke(env, refresh, secret="jns_wrong_placeholder")
        assert resp.status_code == 401
        assert (await _refresh_grant(env, refresh)).status_code == 200

    async def test_unknown_client_is_401(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        resp = await _revoke(env, refresh, client_id="jnc_test_nobody")
        assert resp.status_code == 401

    async def test_basic_auth_is_accepted(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        resp = await _revoke(env, refresh, hint="refresh_token", basic=True)
        assert resp.status_code == 200
        assert (await _refresh_grant(env, refresh)).status_code == 400

    async def test_public_client_identifies_by_client_id(self, env):
        _, refresh = _oauth_tokens(env.alice, PUBLIC_CLIENT)
        resp = await _revoke(env, refresh, client_id=PUBLIC_CLIENT, secret=None)
        assert resp.status_code == 200
        assert await env.redis.strict_exists(
            f"revoked_family:{jwt_manager.get_unverified_claims(refresh)['family']}"
        )


class TestOAuthRevokeRefreshToken:
    async def test_refresh_token_revokes_its_family(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        # Before: the grant works and rotates (same family).
        first = await _refresh_grant(env, refresh)
        assert first.status_code == 200, first.text
        descendant = first.json()["refresh_token"]

        resp = await _revoke(env, refresh, hint="refresh_token")
        assert resp.status_code == 200

        for token in (refresh, descendant):
            refused = await _refresh_grant(env, token)
            assert refused.status_code == 400
            assert "invalid_grant" in refused.text

    async def test_hint_is_optional(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        resp = await _revoke(env, refresh)
        assert resp.status_code == 200
        assert (await _refresh_grant(env, refresh)).status_code == 400


class TestOAuthRevokeAccessToken:
    async def test_access_token_is_blacklisted(self, env):
        access, _ = _oauth_tokens(env.alice, CLIENT_A)
        before = await _introspect(env, access)
        assert before.json()["active"] is True

        resp = await _revoke(env, access, hint="access_token")

        assert resp.status_code == 200

        assert (await _introspect(env, access)).json() == {"active": False}
        userinfo = await env.http.get("/api/v1/oauth/userinfo", headers=_bearer(access))
        assert userinfo.status_code == 401

    async def test_a_wrong_hint_still_revokes(self, env):
        access, _ = _oauth_tokens(env.alice, CLIENT_A)
        resp = await _revoke(env, access, hint="refresh_token")
        assert resp.status_code == 200
        assert (await _introspect(env, access)).json() == {"active": False}

    async def test_the_blacklist_entry_expires_with_the_token(self, env):
        access, _ = _oauth_tokens(env.alice, CLIENT_A)
        await _revoke(env, access, hint="access_token")
        jti = jwt_manager.get_unverified_claims(access)["jti"]
        ttl = await env.redis.redis.ttl(f"blacklist:{jti}")
        assert 0 < ttl <= settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


class TestOAuthRevokeNoOps:
    async def test_unknown_token_answers_200_and_writes_nothing(self, env):
        resp = await _revoke(env, "not-a-token-at-all")
        assert resp.status_code == 200
        assert await env.redis.redis.dbsize() == 0

    async def test_another_clients_token_is_not_revoked(self, env):
        access, refresh = _oauth_tokens(env.alice, CLIENT_A)

        for token in (refresh, access):
            resp = await _revoke(env, token, client_id=CLIENT_B, secret=SECRET_B)
            assert resp.status_code == 200

        assert await env.redis.redis.dbsize() == 0
        assert (await _introspect(env, access)).json()["active"] is True
        assert (await _refresh_grant(env, refresh)).status_code == 200

    async def test_a_janua_session_token_belongs_to_no_client(self, env):
        access, refresh, _ = await _sign_in(env, env.alice)
        for token in (access, refresh):
            resp = await _revoke(env, token)
            assert resp.status_code == 200
        assert (await _refresh(env, refresh)).status_code == 200


class TestOAuthRevokeFailsClosed:
    async def test_redis_down_answers_503_and_does_not_claim_success(self, env):
        _, refresh = _oauth_tokens(env.alice, CLIENT_A)
        env.server.connected = False
        _assert_unavailable(await _revoke(env, refresh, hint="refresh_token"))

    async def test_refresh_grant_and_introspection_answer_503_when_redis_is_down(self, env):
        access, refresh = _oauth_tokens(env.alice, CLIENT_A)
        env.server.connected = False
        _assert_unavailable(await _refresh_grant(env, refresh))
        _assert_unavailable(await _introspect(env, access))

    async def test_an_invalid_token_needs_no_redis_and_answers_200(self, env):
        env.server.connected = False
        resp = await _revoke(env, "not-a-token-at-all")
        assert resp.status_code == 200
