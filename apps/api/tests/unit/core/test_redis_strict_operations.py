"""Strict (no-fallback) Redis operations, init recovery and per-pod visibility.

The breaker's fallback is right for caches and wrong for security state that
every replica must share. These tests pin the strict contract:

- strict operations reach Redis whatever the circuit state, never read or write
  the pod-local fallback cache, and raise RedisUnavailableError on failure;
- deleting a key evicts its pod-local fallback copies (no replay from memory);
- a failed first PING no longer leaves a process without a client for life;
- readiness reflects THIS process's client, and breaker state is published
  without hostnames, keys or error text.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
import redis.asyncio as aioredis

# Imported at collection time on purpose: a session-scoped fixture elsewhere in
# the suite can swap sys.modules["httpx"] for a Mock, so a lazy import inside a
# test could receive the Mock.
from httpx import ASGITransport, AsyncClient

from app.core.redis_circuit_breaker import (
    CircuitState,
    RedisUnavailableError,
    ResilientRedisClient,
)

pytestmark = pytest.mark.asyncio


def _pair():
    server = fakeredis.FakeServer()
    client = ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    )
    return server, client


def _open(client: ResilientRedisClient) -> None:
    cb = client.circuit_breaker
    cb.state = CircuitState.OPEN
    cb.failure_count = cb.failure_threshold
    cb.last_failure_time = datetime.utcnow()


class TestStrictOperations:
    async def test_round_trip(self):
        _, client = _pair()
        await client.strict_set("k", "v", ex=60)
        assert await client.strict_get("k") == "v"
        assert await client.strict_delete("k") == 1
        assert await client.strict_delete("k") == 0
        assert await client.strict_get("k") is None

    async def test_set_applies_the_ttl(self):
        server, client = _pair()
        await client.strict_set("k", "v", ex=60)
        raw = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        assert 0 < await raw.ttl("k") <= 60

    async def test_strict_calls_reach_redis_while_the_circuit_is_open(self):
        _, client = _pair()
        _open(client)
        await client.strict_set("k", "v", ex=60)
        # Evidence that Redis answers: the breaker may probe again right away...
        assert client.circuit_breaker.state == CircuitState.HALF_OPEN
        assert await client.strict_get("k") == "v"
        # ...and a further success closes it.
        assert client.circuit_breaker.state == CircuitState.CLOSED

    async def test_strict_calls_never_touch_the_fallback_cache(self):
        _, client = _pair()
        await client.strict_set("k", "v", ex=60)
        await client.strict_get("k")
        assert client.circuit_breaker._fallback_cache == {}

    async def test_failure_raises_instead_of_returning_a_fallback(self):
        server, client = _pair()
        server.connected = False
        with pytest.raises(RedisUnavailableError):
            await client.strict_set("k", "v", ex=60)
        with pytest.raises(RedisUnavailableError):
            await client.strict_get("k")
        with pytest.raises(RedisUnavailableError):
            await client.strict_delete("k")
        with pytest.raises(RedisUnavailableError):
            await client.strict_ping()
        state = client.circuit_breaker.get_state()
        assert state["strict_failures"] == 4
        assert state["failed_calls"] == 4

    async def test_missing_client_raises(self):
        client = ResilientRedisClient(None)
        with pytest.raises(RedisUnavailableError):
            await client.strict_set("k", "v", ex=60)
        with pytest.raises(RedisUnavailableError):
            await client.strict_get("k")

    async def test_unacknowledged_set_raises(self):
        raw = AsyncMock()
        raw.set.return_value = None
        with pytest.raises(RedisUnavailableError):
            await ResilientRedisClient(raw).strict_set("k", "v", ex=60)

    async def test_programming_errors_are_not_disguised_as_unavailability(self):
        raw = AsyncMock()
        raw.get.side_effect = TypeError("bug")
        with pytest.raises(TypeError):
            await ResilientRedisClient(raw).strict_get("k")


class TestFallbackCacheReplay:
    async def test_deleted_value_is_not_served_from_memory_when_the_circuit_opens(self):
        _, client = _pair()
        await client.set("oauth:code:x", "payload", ex=600)  # copies into fallback cache
        assert await client.get("oauth:code:x") == "payload"
        await client.delete("oauth:code:x")
        _open(client)
        assert await client.get("oauth:code:x") is None

    async def test_delete_evicts_even_when_redis_is_down(self):
        server, client = _pair()
        await client.set("k", "v", ex=600)
        server.connected = False
        await client.delete("k")
        _open(client)
        assert await client.get("k") is None

    async def test_delete_evicts_hash_copies(self):
        cb = ResilientRedisClient(None).circuit_breaker
        cb._cache_fallback("hgetall:session:a", {"u": "1"})
        cb._cache_fallback("hget:session:a:u", "1")
        cb._cache_fallback("get:session:b", "keep")
        cb.invalidate_fallback("session:a")
        assert list(cb._fallback_cache) == ["get:session:b"]


def _fresh_redis_module():
    """Load app/core/redis.py as a new module object.

    tests/conftest.py replaces `get_redis`/`init_redis` on the imported module
    with fakeredis stand-ins, so the real functions are tested from a fresh copy.
    """
    import importlib.util
    from pathlib import Path

    import app.core.redis as patched

    spec = importlib.util.spec_from_file_location(
        "janua_core_redis_under_test", Path(patched.__file__)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestInitKeepsTheClient:
    async def test_failed_first_ping_does_not_drop_the_client(self):
        redis_module = _fresh_redis_module()

        server = fakeredis.FakeServer()
        server.connected = False
        fake = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        with patch.object(redis_module.redis, "from_url", MagicMock(return_value=fake)):
            client = await redis_module.get_redis()  # first use runs init_redis
        assert isinstance(client, ResilientRedisClient)
        assert client.redis is fake
        assert redis_module.get_redis_public_status()["client_initialized"] is True

        # Redis comes back: the same process now stores and reads shared state.
        server.connected = True
        await client.strict_set("oauth:csrf:t", "u", ex=60)
        assert await client.strict_get("oauth:csrf:t") == "u"

    async def test_connect_timeout_is_bounded(self):
        redis_module = _fresh_redis_module()
        from_url = MagicMock(return_value=fakeredis.aioredis.FakeRedis())
        with patch.object(redis_module.redis, "from_url", from_url):
            await redis_module.init_redis()
        timeout = from_url.call_args.kwargs["socket_connect_timeout"]
        assert 0 < timeout <= 30

    async def test_unconstructible_client_is_reported(self):
        redis_module = _fresh_redis_module()
        with patch.object(redis_module.redis, "from_url", MagicMock(side_effect=ValueError("bad"))):
            await redis_module.init_redis()
        status = redis_module.get_redis_public_status()
        assert status["client_initialized"] is False
        with pytest.raises(RedisUnavailableError):
            await (await redis_module.get_redis()).strict_ping()


class TestVisibility:
    async def test_public_status_is_minimal(self):
        _, client = _pair()
        status = client.get_public_status()
        assert set(status) == {
            "state",
            "last_failure_time",
            "fallback_calls",
            "strict_failures",
            "client_initialized",
        }
        assert status["state"] == "closed"

    async def test_public_status_counts_fallbacks_and_reports_open_state(self):
        raw = AsyncMock()
        raw.get.side_effect = aioredis.ConnectionError("down")
        client = ResilientRedisClient(raw)
        for _ in range(client.circuit_breaker.failure_threshold):
            await client.get("k")
        await client.get("k")  # served by the open circuit
        status = client.get_public_status()
        assert status["state"] == "open"
        assert status["fallback_calls"] >= 1
        assert status["last_failure_time"] is not None

    async def test_readiness_uses_this_processes_client(self):
        """A fresh connection can succeed while this replica's client is broken;
        readiness must follow the client requests actually use."""
        from app import main

        broken = ResilientRedisClient(None)
        with patch.object(main, "get_redis", AsyncMock(return_value=broken)):
            assert await main._check_redis_health() is False

        _, healthy = _pair()
        _open(healthy)
        with patch.object(main, "get_redis", AsyncMock(return_value=healthy)):
            assert await main._check_redis_health() is True
        # The probe's strict ping lets the breaker recover within one period.
        assert healthy.circuit_breaker.state == CircuitState.HALF_OPEN

    async def test_ready_endpoint_reports_breaker_and_degrades_without_crashing(self):
        """`/ready` answers 200 "degraded" (not a 500) when Redis is down, and
        publishes the breaker summary — no hostnames, no error text."""
        from app import main

        broken = ResilientRedisClient(None)
        with (
            patch.object(main, "get_redis", AsyncMock(return_value=broken)),
            patch.object(main, "get_redis_public_status", broken.get_public_status),
            patch.object(main, "get_database_health", AsyncMock(return_value={"healthy": True})),
        ):
            transport = ASGITransport(app=main.app)
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["redis"] is False
        assert body["redis_circuit"]["client_initialized"] is False
        assert body["redis_circuit"]["strict_failures"] == 1
        assert "redis://" not in resp.text


class TestUnavailableAnswer:
    """The real app answers RedisUnavailableError with 503 + Retry-After."""

    async def _post_consent(self, accept: str):
        from app import main
        from app.core.database import get_db
        from app.routers.v1 import oauth_provider

        server = fakeredis.FakeServer()
        server.connected = False
        down = ResilientRedisClient(fakeredis.aioredis.FakeRedis(server=server))
        user = MagicMock(id="u-1")
        saved = dict(main.app.dependency_overrides)
        # The dependency object the router captured at import time.
        main.app.dependency_overrides[oauth_provider.get_redis] = lambda: down
        main.app.dependency_overrides[get_db] = lambda: AsyncMock()
        try:
            with patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=user),
            ):
                transport = ASGITransport(app=main.app)
                async with AsyncClient(transport=transport, base_url="http://test") as http:
                    return await http.post(
                        "/api/v1/oauth/consent",
                        data={"auth_request_id": "a", "csrf_token": "t", "action": "allow"},
                        headers={"Accept": accept},
                    )
        finally:
            main.app.dependency_overrides.clear()
            main.app.dependency_overrides.update(saved)

    async def test_api_clients_get_the_error_envelope(self):
        resp = await self._post_consent("application/json")
        assert resp.status_code == 503
        assert resp.headers["retry-after"] == "5"
        body = resp.json()
        assert body["error"]["code"] == "TEMPORARILY_UNAVAILABLE"
        assert "CSRF" not in resp.text

    async def test_browsers_get_a_short_human_page(self):
        resp = await self._post_consent("text/html,application/xhtml+xml")
        assert resp.status_code == 503
        assert resp.headers["retry-after"] == "5"
        assert resp.headers["content-type"].startswith("text/html")
        assert "temporarily unavailable" in resp.text
