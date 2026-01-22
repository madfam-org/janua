"""
Unit tests for Redis Circuit Breaker

Tests the circuit breaker pattern implementation for Redis operations.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
import redis.asyncio as redis

from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker, ResilientRedisClient


class TestRedisCircuitBreaker:
    """Test suite for RedisCircuitBreaker"""

    def test_initial_state(self):
        """Circuit breaker should start in CLOSED state"""
        cb = RedisCircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.total_calls == 0

    @pytest.mark.asyncio
    async def test_successful_operation(self):
        """Successful operations should keep circuit CLOSED"""
        cb = RedisCircuitBreaker()

        async def successful_operation():
            return "success"

        result = await cb.execute(successful_operation, fallback_value="fallback")

        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.successful_calls == 1
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Circuit should open after failure threshold is exceeded"""
        cb = RedisCircuitBreaker(failure_threshold=3)

        async def failing_operation():
            raise redis.RedisError("Connection failed")

        # Execute 3 failing operations
        for _ in range(3):
            result = await cb.execute(failing_operation, fallback_value="fallback")
            assert result == "fallback"

        # Circuit should now be OPEN
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3
        assert cb.failed_calls == 3

    @pytest.mark.asyncio
    async def test_open_circuit_uses_fallback(self):
        """OPEN circuit should immediately use fallback without calling Redis"""
        cb = RedisCircuitBreaker(failure_threshold=2)

        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise redis.RedisError("Fail")

        # Open the circuit
        await cb.execute(operation, fallback_value="fb")
        await cb.execute(operation, fallback_value="fb")
        assert cb.state == CircuitState.OPEN

        # Reset call count
        call_count = 0

        # This should use fallback without calling operation
        result = await cb.execute(operation, fallback_value="fallback")
        assert result == "fallback"
        assert call_count == 0  # Operation should not be called
        assert cb.fallback_calls == 1

    @pytest.mark.asyncio
    async def test_fallback_cache(self):
        """Circuit breaker should cache successful responses for fallback"""
        cb = RedisCircuitBreaker()

        # First successful call - should cache result
        async def successful_op():
            return "cached_value"

        result = await cb.execute(successful_op, fallback_value="default", cache_key="test_key")
        assert result == "cached_value"

        # Open the circuit
        async def failing_op():
            raise redis.RedisError("Fail")

        for _ in range(5):
            await cb.execute(failing_op, fallback_value="fb")

        assert cb.state == CircuitState.OPEN

        # Should use cached value
        result = await cb.execute(failing_op, fallback_value="default", cache_key="test_key")
        assert result == "cached_value"
        assert cb._cache_hits == 1

    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        """Circuit should transition to HALF_OPEN for recovery testing"""
        cb = RedisCircuitBreaker(
            failure_threshold=2, recovery_timeout=1, half_open_max_calls=2  # 1 second
        )

        # Open the circuit
        async def failing_op():
            raise redis.RedisError("Fail")

        await cb.execute(failing_op, fallback_value="fb")
        await cb.execute(failing_op, fallback_value="fb")
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next call should transition to HALF_OPEN
        async def successful_op():
            return "success"

        # First call in HALF_OPEN
        result = await cb.execute(successful_op, fallback_value="fb")
        assert result == "success"
        assert cb.state == CircuitState.HALF_OPEN

        # Second successful call should close circuit
        result = await cb.execute(successful_op, fallback_value="fb")
        assert result == "success"
        assert cb.state == CircuitState.HALF_OPEN

        # Third successful call should close circuit
        result = await cb.execute(successful_op, fallback_value="fb")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Failed call in HALF_OPEN should reopen circuit"""
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=1)

        # Open circuit
        async def failing_op():
            raise redis.RedisError("Fail")

        await cb.execute(failing_op, fallback_value="fb")
        await cb.execute(failing_op, fallback_value="fb")
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        await asyncio.sleep(1.1)

        # Fail during HALF_OPEN
        await cb.execute(failing_op, fallback_value="fb")
        assert cb.state == CircuitState.OPEN

    def test_get_state_returns_metrics(self):
        """get_state should return comprehensive metrics"""
        cb = RedisCircuitBreaker()
        state = cb.get_state()

        assert "state" in state
        assert "failure_count" in state
        assert "total_calls" in state
        assert "successful_calls" in state
        assert "failed_calls" in state
        assert "fallback_calls" in state
        assert "cache_hits" in state
        assert "cache_misses" in state
        assert "cache_size" in state

    @pytest.mark.asyncio
    async def test_cache_size_limit(self):
        """Fallback cache should respect size limit"""
        cb = RedisCircuitBreaker()
        cb._cache_max_size = 3

        # Cache 4 items
        for i in range(4):
            cb._cache_fallback(f"key_{i}", f"value_{i}")

        # Cache should only have 3 items (oldest evicted)
        assert len(cb._fallback_cache) == 3
        assert "key_0" not in cb._fallback_cache  # Oldest evicted
        assert "key_3" in cb._fallback_cache  # Newest kept


class TestResilientRedisClient:
    """Test suite for ResilientRedisClient"""

    @pytest.mark.asyncio
    async def test_get_with_redis_available(self):
        """GET should work normally when Redis is available"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "cached_value"

        client = ResilientRedisClient(mock_redis)
        result = await client.get("test_key")

        assert result == "cached_value"
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_with_redis_unavailable(self):
        """GET should return default when Redis is unavailable"""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis.RedisError("Connection failed")

        client = ResilientRedisClient(mock_redis)
        result = await client.get("test_key", default="default_value")

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_set_with_redis_available(self):
        """SET should work normally when Redis is available"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        client = ResilientRedisClient(mock_redis)
        result = await client.set("test_key", "value", ex=3600)

        assert result is True
        mock_redis.set.assert_called_once_with("test_key", "value", ex=3600)

    @pytest.mark.asyncio
    async def test_set_with_redis_unavailable(self):
        """SET should return False when Redis is unavailable"""
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = redis.RedisError("Connection failed")

        client = ResilientRedisClient(mock_redis)
        result = await client.set("test_key", "value")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_with_redis_unavailable(self):
        """DELETE should return 0 when Redis is unavailable"""
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = redis.RedisError("Connection failed")

        client = ResilientRedisClient(mock_redis)
        result = await client.delete("key1", "key2")

        assert result == 0

    @pytest.mark.asyncio
    async def test_hgetall_with_fallback(self):
        """HGETALL should use fallback cache when Redis fails"""
        mock_redis = AsyncMock()

        # First successful call caches the result
        mock_redis.hgetall.return_value = {"field": "value"}

        client = ResilientRedisClient(mock_redis)
        result = await client.hgetall("test_hash")
        assert result == {"field": "value"}

        # Open circuit
        mock_redis.hgetall.side_effect = redis.RedisError("Connection failed")
        for _ in range(5):
            await client.hgetall("other_hash")

        # Should use cached value from first call
        result = await client.hgetall("test_hash")
        assert result == {"field": "value"}

    @pytest.mark.asyncio
    async def test_health_check(self):
        """health_check should return comprehensive status"""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        client = ResilientRedisClient(mock_redis)
        health = await client.health_check()

        assert "redis_available" in health
        assert "circuit_breaker" in health
        assert "degraded_mode" in health

    @pytest.mark.asyncio
    async def test_get_circuit_status(self):
        """get_circuit_status should return circuit breaker metrics"""
        client = ResilientRedisClient(None)
        status = client.get_circuit_status()

        assert "state" in status
        assert "total_calls" in status
        assert status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_client_without_redis(self):
        """Client should work in degraded mode without Redis"""
        client = ResilientRedisClient(None)

        # All operations should gracefully fail
        result = await client.get("key", default="default")
        assert result == "default"

        result = await client.set("key", "value")
        assert result is False

        result = await client.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_progression(self):
        """Test full circuit breaker state progression"""
        mock_redis = AsyncMock()
        client = ResilientRedisClient(mock_redis)

        # Start: Circuit should be CLOSED
        status = client.get_circuit_status()
        assert status["state"] == "closed"

        # Cause failures
        mock_redis.get.side_effect = redis.RedisError("Connection lost")
        for _ in range(5):
            await client.get("key")

        # Circuit should be OPEN
        status = client.get_circuit_status()
        assert status["state"] == "open"
        assert status["failed_calls"] == 5

        # Verify fallback is used
        fallback_calls_before = status["fallback_calls"]
        await client.get("key", default="fallback")
        status = client.get_circuit_status()
        assert status["fallback_calls"] > fallback_calls_before


class TestCacheBehavior:
    """Test fallback cache behavior"""

    @pytest.mark.asyncio
    async def test_cache_hit_ratio(self):
        """Verify cache hit/miss tracking"""
        cb = RedisCircuitBreaker()

        # Cache a value
        cb._cache_fallback("key1", "value1")

        # Hit
        result = cb._get_fallback("key1", "default")
        assert result == "value1"
        assert cb._cache_hits == 1

        # Miss
        result = cb._get_fallback("key2", "default")
        assert result == "default"
        assert cb._cache_misses == 1

    def test_cache_eviction_lru(self):
        """Cache should evict oldest entries when full"""
        cb = RedisCircuitBreaker()
        cb._cache_max_size = 2

        cb._cache_fallback("key1", "value1")
        cb._cache_fallback("key2", "value2")
        cb._cache_fallback("key3", "value3")  # Should evict key1

        assert "key1" not in cb._fallback_cache
        assert "key2" in cb._fallback_cache
        assert "key3" in cb._fallback_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
