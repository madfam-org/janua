"""Security Redis recovery uses connected pools, never permissive cache data."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.core import redis as redis_module
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.services.token_state import token_is_revoked


@pytest.fixture
def recovery(monkeypatch):
    monkeypatch.setattr(redis_module, "_security_redis_client", None)
    monkeypatch.setattr(redis_module, "_security_recovery_lock", asyncio.Lock())
    monkeypatch.setattr(redis_module, "_security_retry_at", 0.0)
    # A private clock avoids sleeping and does not patch asyncio's own clock.
    clock = Mock()
    clock.monotonic.return_value = 100.0
    monkeypatch.setattr(redis_module, "time", clock)
    factory = Mock()
    monkeypatch.setattr(redis_module.redis, "from_url", factory)
    return clock, factory


def pool():
    return Mock(
        ping=AsyncMock(return_value=True),
        get=AsyncMock(return_value=None),
        aclose=AsyncMock(),
    )


def payload():
    return {"jti": "synthetic-access", "type": "access", "exp": time.time() + 3600}


@pytest.mark.asyncio
async def test_concurrent_outage_then_recovery_without_cache_policy_change(recovery):
    clock, factory = recovery
    unavailable, connected = pool(), pool()
    unavailable.ping.side_effect = ConnectionError("synthetic outage")
    factory.side_effect = [unavailable, connected]
    cache = ResilientRedisClient(None)
    cache.get = AsyncMock(return_value=None)

    async def check():
        return await token_is_revoked(payload(), cache)

    failures = await asyncio.gather(*(check() for _ in range(20)), return_exceptions=True)
    assert all(
        isinstance(failure, HTTPException) and failure.status_code == 503 for failure in failures
    )
    assert factory.call_count == 1
    unavailable.aclose.assert_awaited_once()
    assert redis_module._security_redis_client is None

    # Calls during cooldown fail closed without creating additional pools.
    clock.monotonic.return_value = 104.0
    with pytest.raises(HTTPException) as denied:
        await check()
    assert denied.value.status_code == 503
    assert factory.call_count == 1

    # A wave after cooldown shares one recovery probe and resumes online checks.
    clock.monotonic.return_value = 105.0
    assert await asyncio.gather(*(check() for _ in range(20))) == [False] * 20
    assert factory.call_count == 2
    connected.ping.assert_awaited_once()
    connected.aclose.assert_not_awaited()
    assert redis_module._security_redis_client is connected
    assert cache.redis is None
    cache.get.assert_not_awaited()

    # Recovery does not weaken revocation, or ignore a subsequent outage.
    connected.get.return_value = "revoked"
    assert await check() is True
    connected.get.side_effect = ConnectionError("synthetic second outage")
    with pytest.raises(HTTPException) as denied:
        await check()
    assert denied.value.status_code == 503
    assert factory.call_count == 2


@pytest.mark.asyncio
async def test_pool_is_not_published_before_ping_completes(recovery):
    _, factory = recovery
    candidate = pool()
    started, release = asyncio.Event(), asyncio.Event()

    async def ping():
        started.set()
        await release.wait()
        return True

    candidate.ping.side_effect = ping
    factory.return_value = candidate
    checks = [asyncio.create_task(redis_module.recover_security_redis()) for _ in range(12)]
    try:
        await started.wait()
        assert redis_module._security_redis_client is None
        assert factory.call_count == 1
        assert not any(check.done() for check in checks)
    finally:
        release.set()
    assert await asyncio.gather(*checks) == [candidate] * 12
    candidate.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_hung_connection_times_out_closes_and_can_recover(recovery, monkeypatch):
    clock, factory = recovery
    candidate, connected = pool(), pool()
    candidate.ping.side_effect = asyncio.Event().wait
    factory.side_effect = [candidate, connected]
    monkeypatch.setattr(redis_module, "_SECURITY_CONNECT_TIMEOUT", 0.01)
    results = await asyncio.wait_for(
        asyncio.gather(*(redis_module.recover_security_redis() for _ in range(10))),
        timeout=1,
    )
    assert results == [None] * 10
    candidate.aclose.assert_awaited_once()
    assert redis_module._security_redis_client is None
    assert factory.call_count == 1
    clock.monotonic.return_value = 105.0
    assert await redis_module.recover_security_redis() is connected


@pytest.mark.asyncio
async def test_cancelled_probe_closes_pool_and_releases_guard(recovery):
    clock, factory = recovery
    candidate, connected = pool(), pool()
    started = asyncio.Event()

    async def ping():
        started.set()
        await asyncio.Event().wait()

    candidate.ping.side_effect = ping
    factory.side_effect = [candidate, connected]
    task = asyncio.create_task(redis_module.recover_security_redis())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    candidate.aclose.assert_awaited_once()
    assert redis_module._security_redis_client is None
    assert not redis_module._security_recovery_lock.locked()
    clock.monotonic.return_value = 105.0
    assert await redis_module.recover_security_redis() is connected


@pytest.mark.asyncio
async def test_hung_cleanup_is_bounded_and_probe_guard_released(recovery, monkeypatch):
    _, factory = recovery
    candidate = pool()
    candidate.ping.side_effect = ConnectionError("synthetic outage")
    candidate.aclose.side_effect = asyncio.Event().wait
    factory.return_value = candidate
    monkeypatch.setattr(redis_module, "_SECURITY_CLEANUP_TIMEOUT", 0.01)
    assert await asyncio.wait_for(redis_module.recover_security_redis(), timeout=1) is None
    assert not redis_module._security_recovery_lock.locked()
    assert redis_module._security_redis_client is None


@pytest.mark.asyncio
async def test_healthy_existing_raw_client_needs_no_recovery_pool(recovery):
    _, factory = recovery
    raw = pool()
    assert await token_is_revoked(payload(), ResilientRedisClient(raw)) is False
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["factory", "false_ping"])
async def test_failed_probe_never_publishes_pool(recovery, failure):
    _, factory = recovery
    candidate = pool()
    factory.return_value = candidate
    if failure == "factory":
        factory.side_effect = RuntimeError("synthetic configuration error")
    else:
        candidate.ping.return_value = False
    assert await redis_module.recover_security_redis() is None
    assert redis_module._security_redis_client is None
    if failure == "false_ping":
        candidate.aclose.assert_awaited_once()
