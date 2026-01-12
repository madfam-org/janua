"""
Redis Circuit Breaker

Implements circuit breaker pattern for Redis to prevent cascading failures
and provide graceful degradation when Redis is unavailable.
"""

from typing import Optional, Any, Dict, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import structlog
import redis.asyncio as redis
from functools import wraps

logger = structlog.get_logger()


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Redis is failing, using fallback
    HALF_OPEN = "half_open"  # Testing if Redis has recovered


class RedisCircuitBreaker:
    """
    Circuit breaker for Redis operations with fallback mechanisms.

    States:
    - CLOSED: Normal operation, requests go to Redis
    - OPEN: Redis is failing, requests use fallback (in-memory cache)
    - HALF_OPEN: Testing recovery, allowing limited requests to Redis
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,  # seconds
        half_open_max_calls: int = 3
    ):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.half_open_calls = 0
        self.last_failure_time: Optional[datetime] = None

        # In-memory fallback cache (limited size)
        self._fallback_cache: Dict[str, Any] = {}
        self._cache_max_size = 1000
        self._cache_hits = 0
        self._cache_misses = 0

        # Metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.fallback_calls = 0

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.state != CircuitState.OPEN:
            return False

        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    def _record_success(self):
        """Record a successful call"""
        self.successful_calls += 1
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            logger.info("Redis recovery successful, closing circuit")
            self.state = CircuitState.CLOSED
            self.half_open_calls = 0

    def _record_failure(self):
        """Record a failed call"""
        self.failed_calls += 1
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Redis still failing during recovery, reopening circuit")
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
        elif self.failure_count >= self.failure_threshold:
            logger.error(
                "Redis circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )
            self.state = CircuitState.OPEN

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state and metrics"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "fallback_calls": self.fallback_calls,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._fallback_cache),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }

    async def execute(
        self,
        redis_operation: Callable,
        fallback_value: Any = None,
        cache_key: Optional[str] = None
    ) -> Any:
        """
        Execute a Redis operation with circuit breaker protection.

        Args:
            redis_operation: Async function to call Redis
            fallback_value: Value to return if Redis is unavailable
            cache_key: Optional key for in-memory fallback cache

        Returns:
            Result from Redis or fallback value
        """
        self.total_calls += 1

        # Check if we should attempt to reset the circuit
        if self._should_attempt_reset():
            logger.info("Attempting Redis recovery")
            self.state = CircuitState.HALF_OPEN
            self.half_open_calls = 0

        # If circuit is open, use fallback immediately
        if self.state == CircuitState.OPEN:
            self.fallback_calls += 1
            return self._get_fallback(cache_key, fallback_value)

        # If half-open, limit the number of calls
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                self.fallback_calls += 1
                return self._get_fallback(cache_key, fallback_value)
            self.half_open_calls += 1

        # Try to execute Redis operation
        try:
            result = await redis_operation()
            self._record_success()

            # Cache the result if a cache key is provided
            if cache_key is not None:
                self._cache_fallback(cache_key, result)

            return result

        except redis.RedisError as e:
            logger.warning("Redis operation failed", error=str(e), cache_key=cache_key)
            self._record_failure()
            return self._get_fallback(cache_key, fallback_value)

        except Exception as e:
            logger.error("Unexpected error in Redis operation", error=str(e))
            self._record_failure()
            return self._get_fallback(cache_key, fallback_value)

    def _get_fallback(self, cache_key: Optional[str], default_value: Any) -> Any:
        """Get value from fallback cache or return default"""
        if cache_key and cache_key in self._fallback_cache:
            self._cache_hits += 1
            logger.debug("Using fallback cache", key=cache_key)
            return self._fallback_cache[cache_key]

        self._cache_misses += 1
        logger.debug("Fallback cache miss", key=cache_key, using_default=True)
        return default_value

    def _cache_fallback(self, key: str, value: Any):
        """Store value in fallback cache with size limit"""
        # Simple LRU: remove oldest if at capacity
        if len(self._fallback_cache) >= self._cache_max_size:
            # Remove first item (oldest)
            self._fallback_cache.pop(next(iter(self._fallback_cache)))

        self._fallback_cache[key] = value


class ResilientRedisClient:
    """
    Redis client wrapper with circuit breaker and fallback mechanisms.

    Provides graceful degradation when Redis is unavailable:
    - Sessions: Fall back to JWT-only authentication (stateless)
    - Rate limiting: Allow requests (fail open for availability)
    - Caching: Return None and fetch from database
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.circuit_breaker = RedisCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=3
        )

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.get(key)

        return await self.circuit_breaker.execute(
            operation,
            fallback_value=default,
            cache_key=f"get:{key}"
        )

    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Set value with fallback (returns success status)"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            result = await self.redis.set(key, value, ex=ex, **kwargs)
            # Also cache in fallback for gets
            self.circuit_breaker._cache_fallback(f"get:{key}", value)
            return result

        result = await self.circuit_breaker.execute(
            operation,
            fallback_value=False  # Indicate write failed
        )
        return bool(result)

    async def setex(
        self,
        key: str,
        time: int,
        value: Any,
    ) -> bool:
        """Set value with expiration time (setex compatibility wrapper)"""
        return await self.set(key, value, ex=time)

    async def delete(self, *keys: str) -> int:
        """Delete keys with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.delete(*keys)

        return await self.circuit_breaker.execute(
            operation,
            fallback_value=0  # Indicate no keys deleted
        )

    async def exists(self, *keys: str) -> int:
        """Check if keys exist with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.exists(*keys)

        return await self.circuit_breaker.execute(
            operation,
            fallback_value=0  # Assume keys don't exist
        )

    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.hget(name, key)

        return await self.circuit_breaker.execute(
            operation,
            fallback_value=None,
            cache_key=f"hget:{name}:{key}"
        )

    async def hgetall(self, name: str) -> Dict:
        """Get all hash fields with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.hgetall(name)

        return await self.circuit_breaker.execute(
            operation,
            fallback_value={},
            cache_key=f"hgetall:{name}"
        )

    async def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        mapping: Optional[Dict] = None
    ) -> int:
        """Set hash field with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.hset(name, key=key, value=value, mapping=mapping)

        return await self.circuit_breaker.execute(
            operation,
            fallback_value=0
        )

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.expire(key, seconds)

        result = await self.circuit_breaker.execute(
            operation,
            fallback_value=False
        )
        return bool(result)

    async def ping(self) -> bool:
        """Ping Redis with fallback"""
        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            await self.redis.ping()
            return True

        result = await self.circuit_breaker.execute(
            operation,
            fallback_value=False
        )
        return bool(result)

    def get_circuit_status(self) -> Dict[str, Any]:
        """Get circuit breaker status and metrics"""
        return self.circuit_breaker.get_state()

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        circuit_status = self.get_circuit_status()
        redis_available = await self.ping()

        return {
            "redis_available": redis_available,
            "circuit_breaker": circuit_status,
            "degraded_mode": circuit_status["state"] != "closed"
        }
