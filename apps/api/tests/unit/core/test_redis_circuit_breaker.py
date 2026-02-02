"""
Unit tests for Redis Circuit Breaker

Tests the circuit breaker pattern implementation for Redis operations.
"""

import pytest
from unittest.mock import AsyncMock

import redis.asyncio as aioredis

from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker, ResilientRedisClient


class TestRedisCircuitBreaker:
    """Test suite for RedisCircuitBreaker"""

    def test_initial_state(self):
        cb = RedisCircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.total_calls == 0

    @pytest.mark.asyncio
    async def test_successful_operation(self):
        cb = RedisCircuitBreaker()

        async def successful_operation():
            return "success"

        result = await cb.execute(successful_operation, fallback_value="fallback")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.successful_calls == 1

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        cb = RedisCircuitBreaker(failure_threshold=3)

        async def failing_operation():
            raise aioredis.RedisError("Connection failed")

        for _ in range(3):
            result = await cb.execute(failing_operation, fallback_value="fallback")
            assert result == "fallback"

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_open_circuit_uses_fallback(self):
        cb = RedisCircuitBreaker(failure_threshold=2)
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise aioredis.RedisError("Fail")

        await cb.execute(operation, fallback_value="fb")
        await cb.execute(operation, fallback_value="fb")
        assert cb.state == CircuitState.OPEN

        call_count = 0
        result = await cb.execute(operation, fallback_value="fallback")
        assert result == "fallback"
        assert call_count == 0
        assert cb.fallback_calls == 1

    @pytest.mark.asyncio
    async def test_fallback_cache(self):
        cb = RedisCircuitBreaker()

        async def successful_op():
            return "cached_value"

        result = await cb.execute(successful_op, fallback_value="default", cache_key="test_key")
        assert result == "cached_value"

        async def failing_op():
            raise aioredis.RedisError("Fail")

        for _ in range(5):
            await cb.execute(failing_op, fallback_value="fb")

        assert cb.state == CircuitState.OPEN

        result = await cb.execute(failing_op, fallback_value="default", cache_key="test_key")
        assert result == "cached_value"

    def test_get_state_returns_metrics(self):
        cb = RedisCircuitBreaker()
        state = cb.get_state()

        assert "state" in state
        assert "failure_count" in state
        assert "total_calls" in state
        assert "successful_calls" in state

    @pytest.mark.asyncio
    async def test_cache_size_limit(self):
        cb = RedisCircuitBreaker()
        cb._cache_max_size = 3

        for i in range(4):
            cb._cache_fallback(f"key_{i}", f"value_{i}")

        assert len(cb._fallback_cache) == 3
        assert "key_0" not in cb._fallback_cache
        assert "key_3" in cb._fallback_cache


class TestResilientRedisClient:
    """Test suite for ResilientRedisClient"""

    @pytest.mark.asyncio
    async def test_get_with_redis_available(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "cached_value"

        client = ResilientRedisClient(mock_redis)
        result = await client.get("test_key")
        assert result == "cached_value"

    @pytest.mark.asyncio
    async def test_get_with_redis_unavailable(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = aioredis.RedisError("Connection failed")

        client = ResilientRedisClient(mock_redis)
        result = await client.get("test_key", default="default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_set_with_redis_available(self):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        client = ResilientRedisClient(mock_redis)
        result = await client.set("test_key", "value", ex=3600)
        assert result is True

    @pytest.mark.asyncio
    async def test_set_with_redis_unavailable(self):
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = aioredis.RedisError("Connection failed")

        client = ResilientRedisClient(mock_redis)
        result = await client.set("test_key", "value")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check(self):
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        client = ResilientRedisClient(mock_redis)
        health = await client.health_check()

        assert "redis_available" in health
        assert "circuit_breaker" in health
        assert "degraded_mode" in health

    @pytest.mark.asyncio
    async def test_get_circuit_status(self):
        client = ResilientRedisClient(None)
        status = client.get_circuit_status()

        assert "state" in status
        assert status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_client_without_redis(self):
        client = ResilientRedisClient(None)

        result = await client.get("key", default="default")
        assert result == "default"

        result = await client.set("key", "value")
        assert result is False

        result = await client.ping()
        assert result is False


class TestCacheBehavior:
    """Test fallback cache behavior"""

    @pytest.mark.asyncio
    async def test_cache_hit_ratio(self):
        cb = RedisCircuitBreaker()
        cb._cache_fallback("key1", "value1")

        result = cb._get_fallback("key1", "default")
        assert result == "value1"
        assert cb._cache_hits == 1

        result = cb._get_fallback("key2", "default")
        assert result == "default"
        assert cb._cache_misses == 1

    def test_cache_eviction_lru(self):
        cb = RedisCircuitBreaker()
        cb._cache_max_size = 2

        cb._cache_fallback("key1", "value1")
        cb._cache_fallback("key2", "value2")
        cb._cache_fallback("key3", "value3")

        assert "key1" not in cb._fallback_cache
        assert "key2" in cb._fallback_cache
        assert "key3" in cb._fallback_cache
