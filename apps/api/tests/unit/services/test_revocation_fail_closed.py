"""Token revocation and refresh-reuse checks fail closed when Redis is down.

Owner decision (2026-10-04): revocation checks fail closed.

Until 2026-10 the revocation list (`blacklist:<jti>`) and refresh-token reuse
detection (`blacklist:refresh:<jti>`) were read through the Redis circuit
breaker's fallback operations. While Redis was unreachable, or a replica's
breaker was open, the fallback answer was "not revoked", so a logged-out,
rotated-away or replayed token was accepted. They are now read with strict
operations, which raise `RedisUnavailableError` (answered 503 + Retry-After).

What these tests pin:

- healthy Redis: a token that is not revoked behaves exactly as before, and a
  revoked one is refused;
- Redis down: the check raises, it never answers "not revoked", and nothing is
  rotated or written;
- breaker open while Redis answers: the strict read still reaches Redis, so a
  revoked token is refused (the old fallback would have accepted it);
- a reused refresh token stays refused and, as before, the reuse revokes the
  token family.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis
import pytest

from app.core.jwt_manager import jwt_manager
from app.core.redis_circuit_breaker import (
    CircuitState,
    RedisUnavailableError,
    ResilientRedisClient,
)
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


def _redis():
    server = fakeredis.FakeServer()
    return server, ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    )


def _open(client: ResilientRedisClient) -> None:
    cb = client.circuit_breaker
    cb.state = CircuitState.OPEN
    cb.failure_count = cb.failure_threshold
    cb.last_failure_time = datetime.utcnow()


def _access_token():
    token, jti, _ = AuthService.create_access_token(
        user_id=str(uuid4()), tenant_id=str(uuid4()), email="person@example.com"
    )
    return token, jti


def _auth_redis(client):
    return patch("app.services.auth_service.get_redis", AsyncMock(return_value=client))


class TestVerifyTokenRevocationList:
    async def test_healthy_redis_not_revoked_is_accepted(self):
        _, client = _redis()
        token, jti = _access_token()
        with _auth_redis(client):
            payload = await AuthService.verify_token(token, token_type="access")
        assert payload is not None
        assert payload["jti"] == jti

    async def test_healthy_redis_revoked_is_refused(self):
        _, client = _redis()
        token, jti = _access_token()
        await client.strict_set(f"blacklist:{jti}", "1", ex=60)
        with _auth_redis(client):
            assert await AuthService.verify_token(token, token_type="access") is None

    async def test_redis_down_raises_instead_of_accepting(self):
        server, client = _redis()
        token, jti = _access_token()
        await client.strict_set(f"blacklist:{jti}", "1", ex=60)
        server.connected = False
        with _auth_redis(client), pytest.raises(RedisUnavailableError):
            await AuthService.verify_token(token, token_type="access")

    async def test_redis_down_raises_even_for_a_token_that_was_never_revoked(self):
        server, client = _redis()
        token, _ = _access_token()
        server.connected = False
        with _auth_redis(client), pytest.raises(RedisUnavailableError):
            await AuthService.verify_token(token, token_type="access")

    async def test_open_breaker_still_reads_redis_and_refuses_a_revoked_token(self):
        # The old fallback `get` answered None ("not revoked") on an open
        # breaker without asking Redis. The strict read asks Redis.
        _, client = _redis()
        token, jti = _access_token()
        await client.strict_set(f"blacklist:{jti}", "1", ex=60)
        _open(client)
        assert await client.get(f"blacklist:{jti}") is None  # what the old path saw
        with _auth_redis(client):
            assert await AuthService.verify_token(token, token_type="access") is None

    async def test_an_invalid_token_is_refused_without_asking_redis(self):
        server, client = _redis()
        server.connected = False
        with _auth_redis(client):
            assert await AuthService.verify_token("not-a-token", token_type="access") is None


class TestIdentifyToken:
    """Bookkeeping callers (sign-out, sessions list) keep working during an outage."""

    async def test_healthy_redis_is_exactly_verify_token(self):
        _, client = _redis()
        token, jti = _access_token()
        await client.strict_set(f"blacklist:{jti}", "1", ex=60)
        with _auth_redis(client):
            assert await AuthService.identify_token(token, token_type="access") is None

    async def test_redis_down_falls_back_to_signature_checked_claims(self):
        server, client = _redis()
        token, jti = _access_token()
        server.connected = False
        with _auth_redis(client):
            payload = await AuthService.identify_token(token, token_type="access")
        assert payload is not None and payload["jti"] == jti

    async def test_redis_down_still_refuses_a_forged_token(self):
        server, client = _redis()
        server.connected = False
        with _auth_redis(client):
            assert await AuthService.identify_token("not-a-token", token_type="access") is None


# ---------------------------------------------------------------------------
# AuthService.refresh_tokens (POST /api/v1/auth/refresh)
# ---------------------------------------------------------------------------


def _refresh_patches():
    """Claim resolvers refresh_tokens calls; not what is under test here."""
    return (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value={}),
        ),
        patch("app.services.service_principal.service_principal_claims", return_value={}),
    )


def _db_with_session(session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = session
    db = AsyncMock()
    db.execute.return_value = result
    db.get.return_value = SimpleNamespace(
        id=session.user_id if session else uuid4(),
        tenant_id=uuid4(),
        email="person@example.com",
        is_active=True,
    )
    return db


def _refresh_token():
    user_id, tenant_id = uuid4(), uuid4()
    token, jti, family, _ = AuthService.create_refresh_token(
        user_id=str(user_id), tenant_id=str(tenant_id)
    )
    session = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        refresh_token_jti=jti,
        access_token_jti="access-jti-1",
        is_active=True,
    )
    return token, jti, family, session


class TestRefreshTokens:
    async def test_healthy_rotation_unchanged_and_old_token_is_blacklisted(self):
        _, client = _redis()
        token, jti, _, session = _refresh_token()
        db = _db_with_session(session)
        p = _refresh_patches()
        with _auth_redis(client), p[0], p[1], p[2]:
            result = await AuthService.refresh_tokens(db, token)
        assert result is not None
        assert session.refresh_token_jti != jti  # rotated
        assert await client.strict_get(f"blacklist:{jti}") == "1"
        db.commit.assert_awaited()

    async def test_reused_refresh_token_stays_refused(self):
        _, client = _redis()
        token, _, _, session = _refresh_token()
        p = _refresh_patches()
        with _auth_redis(client), p[0], p[1], p[2]:
            assert await AuthService.refresh_tokens(_db_with_session(session), token) is not None
            replay_db = _db_with_session(session)
            assert await AuthService.refresh_tokens(replay_db, token) is None
        # Refused at the revocation list: no session lookup, nothing rotated.
        replay_db.execute.assert_not_awaited()
        replay_db.commit.assert_not_awaited()

    async def test_redis_down_refuses_with_unavailable_and_rotates_nothing(self):
        server, client = _redis()
        token, jti, _, session = _refresh_token()
        db = _db_with_session(session)
        server.connected = False
        p = _refresh_patches()
        with _auth_redis(client), p[0], p[1], p[2], pytest.raises(RedisUnavailableError):
            await AuthService.refresh_tokens(db, token)
        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()
        assert session.refresh_token_jti == jti

    async def test_redis_down_never_accepts_a_reused_refresh_token(self):
        server, client = _redis()
        token, _, _, session = _refresh_token()
        p = _refresh_patches()
        with _auth_redis(client), p[0], p[1], p[2]:
            assert await AuthService.refresh_tokens(_db_with_session(session), token) is not None
            server.connected = False
            with pytest.raises(RedisUnavailableError):
                await AuthService.refresh_tokens(_db_with_session(session), token)

    async def test_reuse_the_list_missed_still_revokes_the_family(self):
        # A rotated-away token whose blacklist entry is absent (expired, or a
        # write Redis did not take) matches no active session row: as before,
        # that is treated as reuse and the whole family is revoked.
        _, client = _redis()
        token, _, family, _ = _refresh_token()
        sibling = SimpleNamespace(
            access_token_jti="sib-access",
            refresh_token_jti="sib-refresh",
            is_active=True,
            revoked_at=None,
            revoked_reason=None,
        )
        lookup = MagicMock()
        lookup.scalar_one_or_none.return_value = None
        family_rows = MagicMock()
        family_rows.scalars.return_value.all.return_value = [sibling]
        db = AsyncMock()
        db.execute.side_effect = [lookup, family_rows]
        with _auth_redis(client):
            assert await AuthService.refresh_tokens(db, token) is None
        assert sibling.is_active is False
        assert sibling.revoked_reason == "family_revoked_security"
        assert await client.strict_exists("blacklist:sib-access", "blacklist:sib-refresh") == 2


class TestRevocationWritesAreNotSilent:
    async def test_a_lost_blacklist_write_is_logged_as_an_error(self):
        from app.services import auth_service as module
        from app.services import token_revocation

        _, client = _redis()
        _open(client)  # fallback write: stored nowhere
        # The write (and its error log) lives in token_revocation since 2026-10.
        with patch.object(token_revocation, "logger") as log:
            await module._blacklist_jti(client, "jti-1", 60, reason="user_logout")
        assert log.error.called
        assert await client.strict_get("blacklist:jti-1") is None


# ---------------------------------------------------------------------------
# JWTManager.refresh_token_pair (reuse detection on `blacklist:refresh:<jti>`)
# ---------------------------------------------------------------------------


def _core_redis(client):
    return patch("app.core.redis.get_redis", AsyncMock(return_value=client))


class TestJwtManagerReuseDetection:
    async def test_healthy_reuse_is_refused_and_revokes_the_family(self):
        _, client = _redis()
        token, jti, family, _ = jwt_manager.create_refresh_token(str(uuid4()))
        await client.strict_set(f"blacklist:refresh:{jti}", "revoked", ex=60)
        db = AsyncMock()
        with (
            _core_redis(client),
            patch.object(jwt_manager, "revoke_token_family", AsyncMock()) as revoke,
        ):
            assert await jwt_manager.refresh_token_pair(token, db) is None
        revoke.assert_awaited_once()
        assert revoke.await_args.args[0] == family
        db.execute.assert_not_awaited()

    async def test_redis_down_raises_and_neither_accepts_nor_revokes(self):
        server, client = _redis()
        token, jti, _, _ = jwt_manager.create_refresh_token(str(uuid4()))
        await client.strict_set(f"blacklist:refresh:{jti}", "revoked", ex=60)
        server.connected = False
        db = AsyncMock()
        with (
            _core_redis(client),
            patch.object(jwt_manager, "revoke_token_family", AsyncMock()) as revoke,
            pytest.raises(RedisUnavailableError),
        ):
            await jwt_manager.refresh_token_pair(token, db)
        revoke.assert_not_awaited()
        db.execute.assert_not_awaited()

    async def test_open_breaker_still_detects_reuse(self):
        _, client = _redis()
        token, jti, _, _ = jwt_manager.create_refresh_token(str(uuid4()))
        await client.strict_set(f"blacklist:refresh:{jti}", "revoked", ex=60)
        _open(client)
        assert await client.exists(f"blacklist:refresh:{jti}") == 0  # the old answer
        with (
            _core_redis(client),
            patch.object(jwt_manager, "revoke_token_family", AsyncMock()) as revoke,
        ):
            assert await jwt_manager.refresh_token_pair(token, AsyncMock()) is None
        revoke.assert_awaited_once()

    async def test_healthy_unused_token_proceeds_to_the_session_check(self):
        _, client = _redis()
        token, _, _, _ = jwt_manager.create_refresh_token(str(uuid4()))
        no_session = MagicMock()
        no_session.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.return_value = no_session
        with _core_redis(client):
            assert await jwt_manager.refresh_token_pair(token, db) is None
        db.execute.assert_awaited_once()

    async def test_a_lost_blacklist_write_is_logged_as_an_error(self):
        _, client = _redis()
        _open(client)
        with _core_redis(client), patch("app.core.jwt_manager.logger") as log:
            await jwt_manager.blacklist_token("jti-2", "refresh")
        assert log.error.called
        log.info.assert_not_called()
