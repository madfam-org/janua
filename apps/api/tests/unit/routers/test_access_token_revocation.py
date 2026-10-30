"""Access tokens honour the revocation list on every bearer path.

Driven through the real app with a real (SQLite) database and a
fakeredis-backed `ResilientRedisClient`, like `test_revocation_routes.py`:

- after sign-out the session's access token is refused (401) by `/auth/me`
  and by any route behind `get_current_user`, and its refresh token by
  `/auth/refresh`;
- that includes access tokens the session was issued before its latest
  refresh (they carry the session's `family`);
- the same user's other sessions keep working, unless they are revoked
  (`DELETE /sessions`), in which case their access tokens stop too;
- sign-out stays idempotent;
- the issuer's own session read at `/authorize` refuses a revoked token;
- with Redis down, authentication answers 503 + Retry-After (fail closed),
  while sign-out and session revocation keep working.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest
import pytest_asyncio

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.jwt_manager import jwt_manager
from app.core.redis_circuit_breaker import RedisUnavailableError, ResilientRedisClient
from app.models import Base, User, UserStatus
from app.models import Session as UserSession
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio

ME = "/api/v1/auth/me"
PROTECTED = "/api/v1/sessions/"  # a representative route behind get_current_user


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

    alice = User(
        id=uuid.uuid4(),
        email="alice-access-revocation@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    bob = User(
        id=uuid.uuid4(),
        email="bob-access-revocation@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    async with factory() as session:
        session.add_all([alice, bob])
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
                http=http, factory=factory, redis=redis, server=server, alice=alice, bob=bob
            )

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    await engine.dispose()


async def _sign_in(env, user):
    async with env.factory() as db:
        fresh = await db.get(User, user.id)
        access, refresh, session = await AuthService.create_session(db, fresh)
        return access, refresh, session.id


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def _me(env, access):
    return await env.http.get(ME, headers=_bearer(access))


async def _protected(env, access):
    return await env.http.get(PROTECTED, headers=_bearer(access))


async def _refresh(env, refresh_token):
    return await env.http.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


async def _logout(env, access):
    return await env.http.post("/api/v1/auth/logout", headers=_bearer(access))


def _assert_unavailable(resp):
    assert resp.status_code == 503, resp.text
    assert resp.headers["retry-after"].isdigit()


class TestSignOutRevokesTheAccessToken:
    async def test_before_sign_out_the_access_token_works(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        assert (await _me(env, access)).status_code == 200
        assert (await _protected(env, access)).status_code == 200

    async def test_after_logout_me_and_protected_routes_refuse_it(self, env):
        access, _, _ = await _sign_in(env, env.alice)

        resp = await _logout(env, access)
        assert resp.status_code == 200, resp.text

        assert (await _me(env, access)).status_code == 401
        assert (await _protected(env, access)).status_code == 401

    async def test_after_signout_me_refuses_it(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        resp = await env.http.post("/api/v1/auth/signout", headers=_bearer(access))
        assert resp.status_code == 200, resp.text
        assert (await _me(env, access)).status_code == 401

    async def test_refresh_after_logout_is_refused(self, env):
        access, refresh, _ = await _sign_in(env, env.alice)
        assert (await _logout(env, access)).status_code == 200
        assert (await _refresh(env, refresh)).status_code == 401

    async def test_access_tokens_from_before_a_refresh_are_refused_too(self, env):
        old_access, refresh, _ = await _sign_in(env, env.alice)
        refreshed = await _refresh(env, refresh)
        assert refreshed.status_code == 200, refreshed.text
        new_access = refreshed.json()["access_token"]
        # Both are live before sign-out.
        assert (await _me(env, old_access)).status_code == 200

        assert (await _logout(env, new_access)).status_code == 200

        assert (await _me(env, new_access)).status_code == 401
        assert (await _me(env, old_access)).status_code == 401

    async def test_session_access_tokens_carry_the_session_family(self, env):
        access, refresh, session_id = await _sign_in(env, env.alice)
        claims = jwt_manager.get_unverified_claims(access)
        async with env.factory() as db:
            row = (
                await db.execute(select(UserSession).where(UserSession.id == session_id))
            ).scalar_one()
        assert claims["family"] == row.refresh_token_family
        assert jwt_manager.get_unverified_claims(refresh)["family"] == row.refresh_token_family

    async def test_sign_out_is_idempotent(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        assert (await _logout(env, access)).status_code == 200
        assert (await _logout(env, access)).status_code == 200


class TestOtherSessions:
    async def test_other_sessions_of_the_same_user_keep_working(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        other_access, other_refresh, _ = await _sign_in(env, env.alice)
        bob_access, _, _ = await _sign_in(env, env.bob)

        assert (await _logout(env, access)).status_code == 200

        assert (await _me(env, access)).status_code == 401
        assert (await _me(env, other_access)).status_code == 200
        assert (await _protected(env, other_access)).status_code == 200
        assert (await _refresh(env, other_refresh)).status_code == 200
        assert (await _me(env, bob_access)).status_code == 200

    async def test_revoking_all_other_sessions_refuses_their_access_tokens(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        others = [await _sign_in(env, env.alice) for _ in range(2)]

        resp = await env.http.delete(PROTECTED, headers=_bearer(access))
        assert resp.status_code == 200, resp.text

        for other_access, _, _ in others:
            assert (await _me(env, other_access)).status_code == 401
        assert (await _me(env, access)).status_code == 200

    async def test_revoking_one_session_refuses_its_access_token(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        other_access, _, other_id = await _sign_in(env, env.alice)

        resp = await env.http.delete(f"{PROTECTED}{other_id}", headers=_bearer(access))
        assert resp.status_code == 200, resp.text

        assert (await _me(env, other_access)).status_code == 401
        # A revoked token cannot go on to revoke sessions either.
        resp = await env.http.delete(PROTECTED, headers=_bearer(other_access))
        assert resp.status_code == 401


class TestIssuerSessionRead:
    async def test_authorize_bearer_and_cookie_reads_refuse_a_revoked_token(self, env):
        from app.routers.v1.oauth_provider import _verify_own_access_token

        access, _, _ = await _sign_in(env, env.alice)
        assert (await _verify_own_access_token(access)) is not None

        assert (await _logout(env, access)).status_code == 200

        assert (await _verify_own_access_token(access)) is None

    async def test_unrevoked_verifier_refuses_a_revoked_token(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        assert await jwt_manager.verify_unrevoked_token(access, redis=env.redis) is not None
        assert (await _logout(env, access)).status_code == 200
        assert await jwt_manager.verify_unrevoked_token(access, redis=env.redis) is None


class TestRedisDown:
    async def test_authentication_fails_closed_with_503(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        env.server.connected = False
        _assert_unavailable(await _me(env, access))
        _assert_unavailable(await _protected(env, access))

    async def test_authorize_session_read_raises_instead_of_accepting(self, env):
        from app.routers.v1.oauth_provider import _verify_own_access_token

        access, _, _ = await _sign_in(env, env.alice)
        env.server.connected = False
        with pytest.raises(RedisUnavailableError):
            await _verify_own_access_token(access)

    async def test_sign_out_still_works_and_sticks_after_recovery(self, env):
        access, refresh, session_id = await _sign_in(env, env.alice)
        env.server.connected = False

        resp = await _logout(env, access)
        assert resp.status_code == 200, resp.text

        async with env.factory() as db:
            row = (
                await db.execute(select(UserSession).where(UserSession.id == session_id))
            ).scalar_one()
        assert row.revoked is True
        env.server.connected = True
        assert (await _refresh(env, refresh)).status_code == 401

    async def test_session_revocation_still_works(self, env):
        access, _, _ = await _sign_in(env, env.alice)
        _, _, other_id = await _sign_in(env, env.alice)
        env.server.connected = False

        resp = await env.http.delete(f"{PROTECTED}{other_id}", headers=_bearer(access))

        assert resp.status_code == 200, resp.text


async def test_missing_redis_client_fails_closed_not_500():
    """No client (never initialised / raw client) is an outage, not 'not revoked'."""
    from app.services import token_revocation

    payload = {"jti": "j-missing-client", "family": "f-missing-client"}
    with pytest.raises(RedisUnavailableError):
        await token_revocation.is_revoked(None, payload, "access")
    with pytest.raises(RedisUnavailableError):
        await token_revocation.is_revoked(object(), payload, "access")
    # A raw client is read strictly through the breaker, not refused.
    raw = fakeredis.aioredis.FakeRedis()
    assert await token_revocation.is_revoked(raw, payload, "access") is False
    await raw.set("revoked_family:f-missing-client", "1")
    assert await token_revocation.is_revoked(raw, payload, "access") is True
