"""Revocation that actually revokes: a revoked session's refresh token stops refreshing.

Owner decision (2026-10-04): "yes, go ahead with the follow-up Janua PR" (J2-006).

Until 2026-10, sign-out, password change and session-limit eviction wrote the
revocation list as `blacklist:<type>:<jti>` and set `sessions.revoked`, while
`/auth/refresh` read only `blacklist:<jti>` and filtered on
`sessions.is_active`. Neither half matched, so a signed-out refresh token kept
refreshing even with Redis healthy.

These tests run the real `AuthService` against a real (SQLite) `sessions`
table and a fakeredis-backed `ResilientRedisClient`:

- sign-out of this session: its refresh family stops refreshing and its access
  token is refused by `verify_token`;
- password change: every OTHER session's family stops refreshing, the session
  that changed the password keeps working;
- session-limit eviction: the evicted session stops refreshing;
- "sign out everywhere": every family of the user stops refreshing;
- the row is the durable record: a revocation whose Redis write was lost still
  stops `/auth/refresh`;
- the `blacklist:<type>:<jti>` spelling is honoured by `verify_token`;
- Redis down: `/auth/refresh` raises `RedisUnavailableError` (503), it never
  answers from a fallback.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis_circuit_breaker import (
    CircuitState,
    RedisUnavailableError,
    ResilientRedisClient,
)
from app.models import Base, User, UserStatus
from app.models import Session as UserSession
from app.services import token_revocation
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def server():
    return fakeredis.FakeServer()


@pytest.fixture
def redis(server):
    client = ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    )
    with patch("app.services.auth_service.get_redis", AsyncMock(return_value=client)):
        yield client


async def _user(db, email="person@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _sign_in(db, user, **kwargs):
    access, refresh, session = await AuthService.create_session(db, user, **kwargs)
    return access, refresh, session


async def _row(db, session_id) -> UserSession:
    result = await db.execute(select(UserSession).where(UserSession.id == session_id))
    row = result.scalar_one()
    await db.refresh(row)
    return row


class TestHealthyRefreshStillWorks:
    async def test_a_live_session_refreshes_and_rotates(self, db, redis):
        user = await _user(db)
        _, refresh, _ = await _sign_in(db, user)
        rotated = await AuthService.refresh_tokens(db, refresh)
        assert rotated is not None
        # The rotated-away token is refused afterwards (rotation, as before).
        assert await AuthService.refresh_tokens(db, refresh) is None
        # The new one works.
        assert await AuthService.refresh_tokens(db, rotated[1]) is not None


class TestSignOutThisSession:
    async def test_signed_out_refresh_token_no_longer_refreshes(self, db, redis):
        user = await _user(db)
        access, refresh, session = await _sign_in(db, user)

        await AuthService.revoke_sessions([session], reason="user_logout")
        await db.commit()

        assert await AuthService.refresh_tokens(db, refresh) is None
        row = await _row(db, session.id)
        assert row.revoked is True and row.is_active is False
        assert row.revoked_reason == "user_logout"
        assert row.revoked_at is not None

    async def test_signed_out_access_token_is_refused_by_verify_token(self, db, redis):
        user = await _user(db)
        access, _, session = await _sign_in(db, user)
        assert await AuthService.verify_token(access, "access") is not None

        await AuthService.revoke_sessions([session], reason="user_logout")
        await db.commit()

        assert await AuthService.verify_token(access, "access") is None

    async def test_a_token_minted_later_in_the_family_is_refused_too(self, db, redis):
        # Revoke after one rotation, then present the token the rotation minted.
        user = await _user(db)
        _, refresh, session = await _sign_in(db, user)
        _, rotated_refresh = await AuthService.refresh_tokens(db, refresh)

        await AuthService.revoke_sessions([await _row(db, session.id)], reason="user_logout")
        await db.commit()

        assert await AuthService.refresh_tokens(db, rotated_refresh) is None

    async def test_other_sessions_of_the_user_keep_working(self, db, redis):
        user = await _user(db)
        _, refresh_a, session_a = await _sign_in(db, user)
        _, refresh_b, _ = await _sign_in(db, user)

        await AuthService.revoke_sessions([session_a], reason="user_logout")
        await db.commit()

        assert await AuthService.refresh_tokens(db, refresh_a) is None
        assert await AuthService.refresh_tokens(db, refresh_b) is not None


class TestSignOutEverywhere:
    async def test_every_family_of_the_user_stops_refreshing(self, db, redis):
        user = await _user(db)
        other = await _user(db, email="someone-else@example.com")
        refreshes = [(await _sign_in(db, user))[1] for _ in range(3)]
        _, other_refresh, _ = await _sign_in(db, other)

        revoked = await AuthService.invalidate_user_sessions(db, user.id, reason="sign_out_all")

        assert revoked == 3
        for refresh in refreshes:
            assert await AuthService.refresh_tokens(db, refresh) is None
        # Another person's session is untouched.
        assert await AuthService.refresh_tokens(db, other_refresh) is not None


class TestPasswordChange:
    async def test_other_sessions_stop_and_the_changing_session_keeps_working(self, db, redis):
        user = await _user(db)
        current_access, current_refresh, current = await _sign_in(db, user)
        other_access, other_refresh, other = await _sign_in(db, user)

        revoked = await AuthService.invalidate_user_sessions(
            db, user.id, exclude_session_id=current.id, reason="password_change"
        )

        assert revoked == 1
        assert await AuthService.refresh_tokens(db, other_refresh) is None
        assert await AuthService.verify_token(other_access, "access") is None
        assert (await _row(db, other.id)).revoked_reason == "password_change"

        assert await AuthService.verify_token(current_access, "access") is not None
        assert await AuthService.refresh_tokens(db, current_refresh) is not None


class TestSessionLimitEviction:
    async def test_the_evicted_session_stops_refreshing(self, db, redis, monkeypatch):
        monkeypatch.setattr(settings, "MAX_SESSIONS_PER_IDENTITY", 2)
        user = await _user(db)
        _, oldest_refresh, oldest = await _sign_in(db, user)
        _, second_refresh, _ = await _sign_in(db, user)
        _, newest_refresh, _ = await _sign_in(db, user)  # evicts the oldest

        assert (await _row(db, oldest.id)).revoked_reason == "session_limit"
        assert await AuthService.refresh_tokens(db, oldest_refresh) is None
        assert await AuthService.refresh_tokens(db, second_refresh) is not None
        assert await AuthService.refresh_tokens(db, newest_refresh) is not None


class TestRevokeSessionById:
    async def test_revoke_session_marks_the_row_and_stops_refresh(self, db, redis):
        user = await _user(db)
        _, refresh, session = await _sign_in(db, user)

        found = await AuthService.revoke_session(db, session.id, reason="user_revoked")
        assert found is True
        await db.commit()

        assert await AuthService.refresh_tokens(db, refresh) is None
        assert (await _row(db, session.id)).revoked_reason == "user_revoked"

    async def test_unknown_or_malformed_id_revokes_nothing(self, db, redis):
        unknown = await AuthService.revoke_session(db, uuid.uuid4())
        malformed = await AuthService.revoke_session(db, "not-a-uuid")
        assert unknown is False and malformed is False


class TestTheRowIsTheDurableRecord:
    async def test_a_lost_redis_write_still_stops_refresh(self, db, redis, server):
        user = await _user(db)
        _, refresh, session = await _sign_in(db, user)

        # Revoke while this replica's breaker is open: every Redis write falls
        # back to "not stored".
        cb = redis.circuit_breaker
        cb.state = CircuitState.OPEN
        cb.failure_count = cb.failure_threshold
        cb.last_failure_time = datetime.utcnow()
        await AuthService.revoke_sessions([session], reason="user_logout")
        await db.commit()
        assert await redis.strict_exists(f"revoked_family:{session.refresh_token_family}") == 0

        # Redis answers again (the strict read reaches it whatever the breaker
        # says); the revocation list says nothing, the row says revoked.
        assert await AuthService.refresh_tokens(db, refresh) is None

    async def test_bulk_admin_style_update_of_revoked_alone_stops_refresh(self, db, redis):
        # Admin suspension, account deletion and admin revoke-all only set
        # `revoked = True` with a bulk UPDATE. That now stops refresh too.
        user = await _user(db)
        _, refresh, session = await _sign_in(db, user)
        row = await _row(db, session.id)
        row.revoked = True
        await db.commit()

        assert await AuthService.refresh_tokens(db, refresh) is None


class TestRevocationListSpellings:
    async def test_typed_spelling_written_by_jwt_manager_is_honoured(self, db, redis):
        token, jti, _, _ = AuthService.create_refresh_token(
            user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4())
        )
        await redis.strict_set(f"blacklist:refresh:{jti}", "revoked", ex=60)
        assert await AuthService.verify_token(token, "refresh") is None

    async def test_family_key_refuses_every_token_of_the_family(self, db, redis):
        token, _, family, _ = AuthService.create_refresh_token(
            user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4())
        )
        await token_revocation.revoke_family(redis, family, reason="test", strict=True)
        assert await AuthService.verify_token(token, "refresh") is None

    async def test_family_key_does_not_touch_access_tokens(self, db, redis):
        # Access tokens carry no family; only their own JTI revokes them.
        token, _, _ = AuthService.create_access_token(
            user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4())
        )
        assert await AuthService.verify_token(token, "access") is not None


class TestRedisDown:
    async def test_refresh_fails_closed(self, db, redis, server):
        user = await _user(db)
        _, refresh, _ = await _sign_in(db, user)
        server.connected = False
        with pytest.raises(RedisUnavailableError):
            await AuthService.refresh_tokens(db, refresh)

    async def test_sign_out_bookkeeping_still_revokes_the_row(self, db, redis, server):
        user = await _user(db)
        _, refresh, session = await _sign_in(db, user)
        server.connected = False
        await AuthService.revoke_sessions([session], reason="user_logout")
        await db.commit()
        server.connected = True
        assert (await _row(db, session.id)).revoked is True
        assert await AuthService.refresh_tokens(db, refresh) is None


class TestSecondsUntil:
    def test_datetime_and_epoch(self):
        assert (
            3500 < token_revocation.seconds_until(datetime.utcnow() + timedelta(hours=1), 7) <= 3600
        )
        assert 3500 < token_revocation.seconds_until(int(time.time()) + 3600, 7) <= 3600

    def test_past_is_at_least_one_second_and_garbage_is_the_default(self):
        assert token_revocation.seconds_until(datetime.utcnow() - timedelta(days=1), 7) == 1
        assert token_revocation.seconds_until(None, 7) == 7
        assert token_revocation.seconds_until("soon", 7) == 7
        assert token_revocation.seconds_until(True, 7) == 7
