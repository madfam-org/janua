"""
Redis Circuit Breaker

Implements circuit breaker pattern for Redis to prevent cascading failures
and provide graceful degradation when Redis is unavailable.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class RedisUnavailableError(Exception):
    """Raised by the strict operations when Redis cannot serve the call.

    Strict operations exist for security state that must be shared by every API
    replica: OAuth consent CSRF tokens, stored authorization requests and
    authorization codes. For that state the breaker's fallback is wrong twice
    over: a fallback "write" is stored nowhere (or only in one pod's memory),
    and a fallback "read" can serve a value another pod already consumed. The
    caller must answer a retryable error instead (see
    `app.core.error_handling.redis_unavailable_handler`).
    """


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
        half_open_max_calls: int = 3,
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

        # Strict (no-fallback) operations, counted separately so an operator can
        # tell "callers degraded silently" (fallback_calls) from "callers were
        # refused with a retryable error" (strict_failures).
        self.strict_calls = 0
        self.strict_failures = 0

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
                threshold=self.failure_threshold,
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
            "strict_calls": self.strict_calls,
            "strict_failures": self.strict_failures,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
        }

    def get_public_state(self) -> Dict[str, Any]:
        """Breaker summary that is safe to publish on unauthenticated probes.

        State, timing and counters only: never keys, values, hostnames or error
        text (the full `get_state` carries cache sizes and is also free of
        those, but this is the stable, minimal contract for `/ready`).
        """
        return {
            "state": self.state.value,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "fallback_calls": self.fallback_calls,
            "strict_failures": self.strict_failures,
        }

    def record_strict_result(self, ok: bool) -> None:
        """Feed a strict operation's outcome into the breaker.

        A strict call is real evidence about Redis, so it moves the breaker the
        same way a protected call does. One addition: a strict SUCCESS while the
        circuit is OPEN moves it to HALF_OPEN at once, so the next protected
        call probes Redis instead of serving fallbacks for the rest of
        `recovery_timeout`. The readiness probe makes a strict ping every probe
        period, which bounds how long a pod keeps degrading silently after
        Redis is back.
        """
        self.strict_calls += 1
        if ok:
            self._record_success()
            if self.state == CircuitState.OPEN:
                logger.info("Redis answered a strict call; moving circuit to half-open")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
        else:
            self.strict_failures += 1
            self._record_failure()

    def invalidate_fallback(self, *redis_keys: str) -> None:
        """Drop every fallback-cache entry derived from these Redis keys.

        Called on delete: a value Redis no longer holds must never come back
        from this pod's memory when the circuit opens later (replay of a
        consumed single-use value).
        """
        if not redis_keys or not self._fallback_cache:
            return
        targets = set(redis_keys)
        for cache_key in list(self._fallback_cache):
            kind, _, rest = cache_key.partition(":")
            if kind == "get" or kind == "hgetall":
                name = rest
            elif kind == "hget":
                name = rest.rsplit(":", 1)[0]
            else:
                continue
            if name in targets:
                self._fallback_cache.pop(cache_key, None)

    async def execute(
        self, redis_operation: Callable, fallback_value: Any = None, cache_key: Optional[str] = None
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
            failure_threshold=5, recovery_timeout=60, half_open_max_calls=3
        )

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.get(key)

        return await self.circuit_breaker.execute(
            operation, fallback_value=default, cache_key=f"get:{key}"
        )

    async def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> bool:
        """Set value with fallback (returns success status)"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            result = await self.redis.set(key, value, ex=ex, **kwargs)
            # Also cache in fallback for gets
            self.circuit_breaker._cache_fallback(f"get:{key}", value)
            return result

        result = await self.circuit_breaker.execute(
            operation, fallback_value=False  # Indicate write failed
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
        """Delete keys with fallback.

        The pod-local fallback copies of these keys are dropped first, whether or
        not Redis answers, so a deleted value cannot be served from memory later.
        """
        self.circuit_breaker.invalidate_fallback(*keys)

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.delete(*keys)

        return await self.circuit_breaker.execute(
            operation, fallback_value=0  # Indicate no keys deleted
        )

    async def exists(self, *keys: str) -> int:
        """Check if keys exist with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.exists(*keys)

        return await self.circuit_breaker.execute(
            operation, fallback_value=0  # Assume keys don't exist
        )

    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.hget(name, key)

        return await self.circuit_breaker.execute(
            operation, fallback_value=None, cache_key=f"hget:{name}:{key}"
        )

    async def hgetall(self, name: str) -> Dict:
        """Get all hash fields with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.hgetall(name)

        return await self.circuit_breaker.execute(
            operation, fallback_value={}, cache_key=f"hgetall:{name}"
        )

    async def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        mapping: Optional[Dict] = None,
    ) -> int:
        """Set hash field with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.hset(name, key=key, value=value, mapping=mapping)

        return await self.circuit_breaker.execute(operation, fallback_value=0)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            return await self.redis.expire(key, seconds)

        result = await self.circuit_breaker.execute(operation, fallback_value=False)
        return bool(result)

    async def ping(self) -> bool:
        """Ping Redis with fallback"""

        async def operation():
            if self.redis is None:
                raise redis.RedisError("Redis client not initialized")
            await self.redis.ping()
            return True

        result = await self.circuit_breaker.execute(operation, fallback_value=False)
        return bool(result)

    # ------------------------------------------------------------------
    # Strict operations: no fallback value, no pod-local cache.
    #
    # Use these for state that must be identical on every replica and whose
    # loss must be visible: OAuth consent CSRF tokens, stored authorization
    # requests, authorization codes, token revocation lists, WebAuthn
    # challenges and social-login state. They try Redis whatever the circuit state
    # (the circuit protects fallback-able callers; a strict caller has no
    # fallback to protect) and raise RedisUnavailableError on any failure.
    # ------------------------------------------------------------------

    async def _strict(self, operation: Callable[[Any], Awaitable[Any]]) -> Any:
        client = self.redis
        if client is None:
            self.circuit_breaker.record_strict_result(False)
            raise RedisUnavailableError("Redis client not initialized")
        try:
            result = await operation(client)
        except (redis.RedisError, OSError, asyncio.TimeoutError) as e:
            logger.warning("Strict Redis operation failed", error_type=type(e).__name__)
            self.circuit_breaker.record_strict_result(False)
            raise RedisUnavailableError(type(e).__name__) from e
        self.circuit_breaker.record_strict_result(True)
        return result

    async def strict_set(self, key: str, value: Any, ex: int) -> None:
        """SET key value EX ex, or raise RedisUnavailableError. Never cached locally."""

        async def operation(client: redis.Redis) -> Any:
            ok = await client.set(key, value, ex=ex)
            if not ok:
                raise redis.RedisError("SET was not acknowledged")
            return ok

        await self._strict(operation)

    async def strict_set_nx(self, key: str, value: Any, ex: int) -> bool:
        """SET key value EX ex NX: True when this call created the key.

        False means the key already existed (another caller got there first).
        The answer comes from Redis itself, so of two concurrent callers on any
        replicas exactly one sees True — what single-use refresh tokens need.
        Raises RedisUnavailableError when Redis cannot answer.
        """

        async def operation(client: redis.Redis) -> bool:
            return bool(await client.set(key, value, ex=ex, nx=True))

        return await self._strict(operation)

    async def strict_get(self, key: str) -> Optional[Any]:
        """GET key from Redis itself (None = absent), or raise RedisUnavailableError."""
        return await self._strict(lambda client: client.get(key))

    async def strict_exists(self, *keys: str) -> int:
        """EXISTS keys against Redis itself (count of keys present), or raise.

        For revocation lists: the breaker's `exists` answers 0 ("not revoked")
        when Redis is unreachable, which accepts a revoked token. This one
        raises RedisUnavailableError instead, so the caller answers 503.
        """
        return int(await self._strict(lambda client: client.exists(*keys)))

    async def strict_delete(self, *keys: str) -> int:
        """DEL keys; returns how many Redis actually removed, or raises.

        The count is what makes single-use values single-use across replicas:
        of two concurrent consumers, exactly one sees 1.
        """
        self.circuit_breaker.invalidate_fallback(*keys)
        return int(await self._strict(lambda client: client.delete(*keys)))

    async def strict_ping(self) -> None:
        """PING through this process's own client, or raise RedisUnavailableError."""
        await self._strict(lambda client: client.ping())

    def get_circuit_status(self) -> Dict[str, Any]:
        """Get circuit breaker status and metrics"""
        status = self.circuit_breaker.get_state()
        status["client_initialized"] = self.redis is not None
        return status

    def get_public_status(self) -> Dict[str, Any]:
        """Per-pod breaker summary safe for unauthenticated health endpoints."""
        status = self.circuit_breaker.get_public_state()
        status["client_initialized"] = self.redis is not None
        return status

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        circuit_status = self.get_circuit_status()
        redis_available = await self.ping()

        return {
            "redis_available": redis_available,
            "circuit_breaker": circuit_status,
            "degraded_mode": circuit_status["state"] != "closed",
        }
