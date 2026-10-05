"""A completed password reset signs the user out everywhere (J3-003).

Owner decision (2026-10-04): "yes, go with all three recommendations".

The forgot-password flow (`POST /auth/password/reset` and the hosted
`POST /auth/reset-password-form`) used to set the new password and revoke no
session, so a session stolen before the reset kept refreshing after it. Now
the reset revokes EVERY session of the user through
`AuthService.revoke_sessions` (no session is kept: the person resetting may be
signed in nowhere), strictly:

- before the reset, a session refreshes; after it, every session's refresh
  token answers 401, its refresh family and access JTI are on the revocation
  list, and the rows record `password_reset`;
- the reset itself still succeeds, and the new password works;
- Redis down: 503 + Retry-After at the revoke step, and nothing is applied
  (password, reset token and session rows unchanged), so the same link works
  once Redis answers.

Driven through the real app with a real (SQLite) database and a
fakeredis-backed `ResilientRedisClient`.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
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

from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Base, PasswordReset, User, UserStatus
from app.models import Session as UserSession
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio

OLD_PASSWORD = "Old-Passw0rd!-placeholder"
NEW_PASSWORD = "New-Passw0rd!-placeholder"


@pytest_asyncio.fixture
async def env():
    from app import dependencies
    from app.core import redis as core_redis
    from app.core.database import get_db as core_get_db
    from app.database import get_db
    from app.main import app
    from app.routers.v1 import auth as auth_router

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
    for dep in {core_redis.get_redis, dependencies.get_redis, auth_router.get_redis}:
        app.dependency_overrides[dep] = lambda: redis

    user = User(
        id=uuid.uuid4(),
        email="reset-revokes@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
        password_hash=AuthService.hash_password(OLD_PASSWORD),
    )
    async with factory() as session:
        session.add(user)
        await session.commit()

    get = AsyncMock(return_value=redis)
    with (
        patch("app.core.redis.get_redis", get),
        patch("app.services.auth_service.get_redis", get),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield SimpleNamespace(http=http, factory=factory, redis=redis, server=server, user=user)

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    await engine.dispose()


async def _sign_in(env):
    async with env.factory() as db:
        fresh = await db.get(User, env.user.id)
        access, refresh, session = await AuthService.create_session(db, fresh)
        return refresh, session.id


async def _reset_token(env) -> str:
    token = secrets.token_urlsafe(32)
    async with env.factory() as db:
        db.add(
            PasswordReset(
                user_id=env.user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
        )
        await db.commit()
    return token


async def _refresh(env, refresh_token):
    return await env.http.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


async def _reset(env, token):
    return await env.http.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD}
    )


async def _row(env, session_id) -> UserSession:
    async with env.factory() as db:
        result = await db.execute(select(UserSession).where(UserSession.id == session_id))
        return result.scalar_one()


async def _user(env) -> User:
    async with env.factory() as db:
        return await db.get(User, env.user.id)


async def _reset_row(env, token) -> PasswordReset:
    async with env.factory() as db:
        result = await db.execute(select(PasswordReset).where(PasswordReset.token == token))
        return result.scalar_one()


class TestResetRevokesEverySession:
    async def test_before_the_reset_a_session_refreshes(self, env):
        refresh, _ = await _sign_in(env)
        assert (await _refresh(env, refresh)).status_code == 200

    async def test_after_the_reset_every_session_is_refused(self, env):
        sessions = [await _sign_in(env) for _ in range(2)]
        token = await _reset_token(env)

        resp = await _reset(env, token)

        assert resp.status_code == 200, resp.text
        for refresh, session_id in sessions:
            assert (await _refresh(env, refresh)).status_code == 401
            row = await _row(env, session_id)
            assert row.revoked is True
            assert row.is_active is False
            assert row.revoked_reason == "password_reset"
            # The refresh family and the current access token are on the
            # revocation list, not only the row.
            assert await env.redis.strict_exists(f"revoked_family:{row.refresh_token_family}")
            assert await env.redis.strict_exists(f"blacklist:{row.access_token_jti}")

    async def test_the_reset_itself_succeeds(self, env):
        await _sign_in(env)
        token = await _reset_token(env)

        assert (await _reset(env, token)).status_code == 200

        user = await _user(env)
        assert AuthService.verify_password(NEW_PASSWORD, user.password_hash)
        assert (await _reset_row(env, token)).used is True
        # A session started after the reset (with the new password) works.
        refresh, _ = await _sign_in(env)
        assert (await _refresh(env, refresh)).status_code == 200

    async def test_the_hosted_reset_form_revokes_too(self, env):
        refresh, _ = await _sign_in(env)
        token = await _reset_token(env)

        resp = await env.http.post(
            "/api/v1/auth/reset-password-form",
            data={
                "token": token,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
        )

        assert resp.status_code == 200, resp.text
        assert (await _refresh(env, refresh)).status_code == 401

    async def test_a_user_signed_in_nowhere_resets(self, env):
        token = await _reset_token(env)
        assert (await _reset(env, token)).status_code == 200


class TestResetFailsClosedWhenRedisIsDown:
    async def test_503_and_nothing_is_applied(self, env):
        refresh, session_id = await _sign_in(env)
        token = await _reset_token(env)

        env.server.connected = False
        resp = await _reset(env, token)

        assert resp.status_code == 503, resp.text
        assert resp.headers["retry-after"].isdigit()
        # Not half-applied: old password, unused link, live session row.
        user = await _user(env)
        assert AuthService.verify_password(OLD_PASSWORD, user.password_hash)
        assert not AuthService.verify_password(NEW_PASSWORD, user.password_hash)
        assert (await _reset_row(env, token)).used is False
        row = await _row(env, session_id)
        assert row.revoked is False
        assert row.is_active is True

        # Once Redis answers, the same link completes the reset and revokes.
        env.server.connected = True
        assert (await _reset(env, token)).status_code == 200
        assert (await _refresh(env, refresh)).status_code == 401
        user = await _user(env)
        assert AuthService.verify_password(NEW_PASSWORD, user.password_hash)

    async def test_the_hosted_form_answers_a_503_page(self, env):
        await _sign_in(env)
        token = await _reset_token(env)

        env.server.connected = False
        resp = await env.http.post(
            "/api/v1/auth/reset-password-form",
            data={
                "token": token,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
            headers={"Accept": "text/html"},
        )

        assert resp.status_code == 503
        assert resp.headers["retry-after"].isdigit()
        assert "text/html" in resp.headers["content-type"]
        assert (await _reset_row(env, token)).used is False
