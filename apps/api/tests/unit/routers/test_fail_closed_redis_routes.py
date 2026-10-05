"""HTTP behaviour of the fail-closed Redis paths, and what stays up.

Owner decision (2026-10-04): revocation checks fail closed.

While Redis is unreachable:

- `POST /auth/refresh` and `GET /auth/session` answer 503 + Retry-After
  (JSON for API clients) instead of accepting a token whose revocation status
  is unknown;
- passkey (WebAuthn) challenges and social-login state cannot be stored or
  read, so those flows answer 503 up front instead of a confusing "challenge
  expired" / "invalid or expired state" later;
- sign-out still revokes the session row (it does not need the revocation list
  to do that);
- JWKS and the OpenID configuration document, which relying parties use to
  verify tokens locally, never touch Redis and keep answering 200.

With a healthy Redis every one of these paths behaves as before, and the
single-use values stay single-use across replicas.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis
import pytest
from fastapi import HTTPException

# Imported at collection time on purpose (see test_redis_strict_operations.py):
# a session-scoped fixture elsewhere can swap sys.modules["httpx"] for a Mock.
from httpx import ASGITransport, AsyncClient

from app.core.redis_circuit_breaker import (
    CircuitState,
    RedisUnavailableError,
    ResilientRedisClient,
)
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


def _replica(server: fakeredis.FakeServer) -> ResilientRedisClient:
    """One API replica: its own breaker and fallback cache over a shared Redis."""
    return ResilientRedisClient(fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))


def _down() -> ResilientRedisClient:
    server = fakeredis.FakeServer()
    client = _replica(server)
    server.connected = False
    return client


def _open(client: ResilientRedisClient) -> None:
    cb = client.circuit_breaker
    cb.state = CircuitState.OPEN
    cb.failure_count = cb.failure_threshold
    cb.last_failure_time = datetime.utcnow()


async def _call(method: str, path: str, *, redis: ResilientRedisClient, **kwargs):
    """Drive the real app with every Redis lookup served by `redis`."""
    from app import main
    from app.database import get_db

    async def _no_db():
        yield AsyncMock()

    main.app.dependency_overrides[get_db] = _no_db
    get = AsyncMock(return_value=redis)
    try:
        with (
            patch("app.core.redis.get_redis", get),
            patch("app.services.auth_service.get_redis", get),
        ):
            transport = ASGITransport(app=main.app)
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                return await http.request(method, path, **kwargs)
    finally:
        main.app.dependency_overrides.pop(get_db, None)


def _assert_unavailable(resp):
    assert resp.status_code == 503, resp.text
    assert resp.headers["retry-after"].isdigit()
    assert resp.json()["error"]["code"] == "TEMPORARILY_UNAVAILABLE"


class TestTokenRoutesFailClosed:
    async def test_refresh_answers_503_when_redis_is_down(self):
        token, _, _, _ = AuthService.create_refresh_token(
            user_id=str(uuid4()), tenant_id=str(uuid4())
        )
        resp = await _call(
            "POST", "/api/v1/auth/refresh", redis=_down(), json={"refresh_token": token}
        )
        _assert_unavailable(resp)

    async def test_refresh_with_a_revoked_token_is_still_401_on_a_healthy_redis(self):
        server = fakeredis.FakeServer()
        redis = _replica(server)
        token, jti, _, _ = AuthService.create_refresh_token(
            user_id=str(uuid4()), tenant_id=str(uuid4())
        )
        await redis.strict_set(f"blacklist:{jti}", "1", ex=60)
        resp = await _call(
            "POST", "/api/v1/auth/refresh", redis=redis, json={"refresh_token": token}
        )
        assert resp.status_code == 401

    async def test_session_check_answers_503_when_redis_is_down(self):
        token, _, _ = AuthService.create_access_token(
            user_id=str(uuid4()), tenant_id=str(uuid4()), email="person@example.com"
        )
        resp = await _call(
            "GET",
            "/api/v1/auth/session",
            redis=_down(),
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_unavailable(resp)

    async def test_session_check_refuses_a_revoked_token_on_a_healthy_redis(self):
        # Until 2026-10 `verify_token` was not awaited here, so the revocation
        # list was never consulted (and the route failed on the coroutine).
        redis = _replica(fakeredis.FakeServer())
        token, jti, _ = AuthService.create_access_token(
            user_id=str(uuid4()), tenant_id=str(uuid4()), email="person@example.com"
        )
        await redis.strict_set(f"blacklist:{jti}", "1", ex=60)
        resp = await _call(
            "GET",
            "/api/v1/auth/session",
            redis=redis,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_session_check_accepts_a_valid_token_on_a_healthy_redis(self):
        from app.routers.v1.auth import check_session

        user_id = uuid4()
        token, _, _ = AuthService.create_access_token(
            user_id=str(user_id), tenant_id=str(uuid4()), email="person@example.com"
        )
        user = SimpleNamespace(
            id=user_id,
            email="person@example.com",
            username=None,
            first_name=None,
            last_name=None,
            email_verified=True,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        db = AsyncMock()
        db.execute.return_value = result
        request = MagicMock()
        request.cookies = {}
        request.headers = {"authorization": f"Bearer {token}"}
        redis = _replica(fakeredis.FakeServer())
        with patch("app.services.auth_service.get_redis", AsyncMock(return_value=redis)):
            body = await check_session(request=request, db=db)
        assert body["authenticated"] is True
        assert body["user"]["id"] == str(user_id)


class TestSignOutDuringAnOutage:
    async def test_sign_out_still_revokes_the_session_row(self):
        from app.routers.v1.auth import sign_out

        user_id = uuid4()
        token, jti, _ = AuthService.create_access_token(
            user_id=str(user_id), tenant_id=str(uuid4()), email="person@example.com"
        )
        row = SimpleNamespace(revoked=False, refresh_token_jti="r-jti")
        result = MagicMock()
        result.scalar_one_or_none.return_value = row
        db = AsyncMock()
        db.execute.return_value = result
        down = _down()
        with (
            patch("app.services.auth_service.get_redis", AsyncMock(return_value=down)),
            patch("app.core.redis.get_redis", AsyncMock(return_value=down)),
            patch("app.routers.v1.auth.log_activity", AsyncMock()),
            patch("app.routers.v1.auth.log_audit_event", AsyncMock()),
        ):
            await sign_out(
                current_user=SimpleNamespace(id=user_id),
                credentials=SimpleNamespace(credentials=token),
                db=db,
            )
        assert row.revoked is True
        db.commit.assert_awaited()


# ---------------------------------------------------------------------------
# Passkeys (WebAuthn challenges)
# ---------------------------------------------------------------------------


class TestPasskeyChallenges:
    async def test_authentication_options_answer_503_when_redis_is_down(self):
        resp = await _call("POST", "/api/v1/passkeys/authenticate/options", redis=_down(), json={})
        _assert_unavailable(resp)

    async def test_challenge_written_on_one_replica_is_consumed_once_on_another(self):
        from app.routers.v1.passkeys import _consume_challenge

        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        _open(pod_a)  # an open breaker no longer turns the write into a no-op
        resp = await _call("POST", "/api/v1/passkeys/authenticate/options", redis=pod_a, json={})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        key = f"passkey_auth_challenge:{body['sessionId']}"
        assert await _consume_challenge(pod_b, key, "expired") == body["challenge"]
        with pytest.raises(HTTPException) as exc:
            await _consume_challenge(pod_a, key, "expired")
        assert exc.value.status_code == 400

    async def test_concurrent_verifies_consume_a_challenge_exactly_once(self):
        from app.routers.v1.passkeys import _consume_challenge

        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        await pod_a.strict_set("passkey_auth_challenge:s1", "chal", ex=600)
        results = await asyncio.gather(
            _consume_challenge(pod_a, "passkey_auth_challenge:s1", "expired"),
            _consume_challenge(pod_b, "passkey_auth_challenge:s1", "expired"),
            return_exceptions=True,
        )
        assert sorted(type(r).__name__ for r in results) == ["HTTPException", "str"]

    async def test_verify_answers_unavailable_not_expired_when_redis_is_down(self):
        from app.routers.v1.passkeys import verify_authentication

        db = AsyncMock()
        with (
            patch("app.core.redis.get_redis", AsyncMock(return_value=_down())),
            pytest.raises(RedisUnavailableError),
        ):
            await verify_authentication(
                auth_request=SimpleNamespace(credential={"id": "cred"}, email=None),
                session_id="s1",
                request=MagicMock(),
                db=db,
            )
        db.execute.assert_not_awaited()

    async def test_registration_options_answer_unavailable_when_redis_is_down(self):
        from app.routers.v1.passkeys import (
            PasskeyRegisterOptionsRequest,
            get_registration_options,
        )

        no_passkeys = MagicMock()
        no_passkeys.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = no_passkeys
        user = SimpleNamespace(id=uuid4(), email="person@example.com", display_name=None)
        # Options generation is stubbed: this test is about where the challenge
        # is stored, not about the WebAuthn library call before it.
        options = SimpleNamespace(challenge=b"challenge-bytes")
        with (
            patch("app.core.redis.get_redis", AsyncMock(return_value=_down())),
            patch(
                "app.routers.v1.passkeys.generate_registration_options",
                return_value=options,
            ),
            pytest.raises(RedisUnavailableError),
        ):
            await get_registration_options(
                request=PasskeyRegisterOptionsRequest(), current_user=user, db=db
            )


# ---------------------------------------------------------------------------
# Social login (OAuth client) state
# ---------------------------------------------------------------------------


def _github_configured():
    return (
        patch(
            "app.routers.v1.oauth.OAuthService.get_provider_config",
            return_value={"client_id": "c", "client_secret": "s"},
        ),
        patch(
            "app.routers.v1.oauth.OAuthService.get_authorization_url",
            return_value="https://provider.example/authorize",
        ),
    )


class TestSocialLoginState:
    async def test_authorize_answers_503_when_redis_is_down(self):
        p = _github_configured()
        with p[0], p[1]:
            resp = await _call("POST", "/api/v1/auth/oauth/authorize/github", redis=_down())
        _assert_unavailable(resp)

    async def test_callback_answers_503_not_invalid_state_when_redis_is_down(self):
        resp = await _call(
            "GET",
            "/api/v1/auth/oauth/callback/github",
            redis=_down(),
            params={"code": "c0de", "state": "st4te"},
        )
        _assert_unavailable(resp)

    async def test_browser_gets_the_short_page_on_503(self):
        resp = await _call(
            "GET",
            "/api/v1/auth/oauth/callback/github",
            redis=_down(),
            params={"code": "c0de", "state": "st4te"},
            headers={"Accept": "text/html"},
        )
        assert resp.status_code == 503
        assert "temporarily unavailable" in resp.text
        assert resp.headers["retry-after"].isdigit()

    async def test_state_from_one_replica_works_on_another_and_only_once(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        _open(pod_a)
        p = _github_configured()
        with p[0], p[1]:
            start = await _call("POST", "/api/v1/auth/oauth/authorize/github", redis=pod_a)
        assert start.status_code == 200, start.text
        state = start.json()["state"]

        user = SimpleNamespace(
            id=uuid4(),
            email="person@example.com",
            first_name=None,
            last_name=None,
            profile_image_url=None,
        )
        tokens = {"access_token": "a", "refresh_token": "r", "is_new_user": False}
        with patch(
            "app.routers.v1.oauth.OAuthService.handle_oauth_callback",
            AsyncMock(return_value=(user, tokens)),
        ):
            first = await _call(
                "GET",
                "/api/v1/auth/oauth/callback/github",
                redis=pod_b,
                params={"code": "c0de", "state": state},
            )
            replay = await _call(
                "GET",
                "/api/v1/auth/oauth/callback/github",
                redis=pod_a,
                params={"code": "c0de", "state": state},
            )
        assert first.status_code == 200, first.text
        assert replay.status_code == 400


# ---------------------------------------------------------------------------
# What must stay up while Redis is down
# ---------------------------------------------------------------------------


class TestStaysUpDuringAnOutage:
    @pytest.mark.parametrize(
        "path", ["/.well-known/jwks.json", "/.well-known/openid-configuration"]
    )
    async def test_discovery_and_jwks_do_not_depend_on_redis(self, path):
        resp = await _call("GET", path, redis=_down())
        assert resp.status_code == 200, resp.text
