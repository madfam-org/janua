from typing import Any, Dict, Optional

import redis.asyncio as redis
import structlog

from app.config import settings
from app.core.redis_circuit_breaker import ResilientRedisClient

logger = structlog.get_logger()

# Global Redis clients
_raw_redis_client: Optional[redis.Redis] = None
_resilient_redis_client: Optional[ResilientRedisClient] = None


async def init_redis():
    """Initialize Redis connection with circuit breaker protection.

    The client is kept even when the first PING fails. `redis.from_url` builds a
    lazy connection pool that reconnects on the next command, so a Redis blip at
    pod start must not leave this process without a client for its whole life.
    (Until 2026-10 the client was dropped here and never rebuilt: a replica that
    booted during a blip ran every Redis call on the breaker's fallback forever,
    while its probes — which open their own connection — kept reporting Redis
    healthy.) Only a client that cannot be constructed at all (an invalid URL)
    leaves `_raw_redis_client` unset.
    """
    global _raw_redis_client, _resilient_redis_client

    try:
        _raw_redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=settings.REDIS_DECODE_RESPONSES,
            max_connections=settings.REDIS_POOL_SIZE,
            # Bound connection attempts so an unreachable Redis fails a call in
            # seconds (a retryable 503 for strict callers) instead of hanging it
            # for the OS TCP timeout.
            socket_connect_timeout=max(settings.REDIS_CONNECTION_TIMEOUT, 1) / 1000,
        )
    except Exception as e:
        logger.error(
            "Failed to construct Redis client - running in degraded mode",
            error_type=type(e).__name__,
        )
        _raw_redis_client = None

    if _raw_redis_client is not None:
        try:
            await _raw_redis_client.ping()
            logger.info("Redis initialized successfully")
        except Exception as e:
            logger.warning(
                "Redis not reachable at init; keeping the client so it reconnects",
                error_type=type(e).__name__,
            )

    # Create resilient client (works with or without raw client)
    _resilient_redis_client = ResilientRedisClient(_raw_redis_client)


async def get_redis() -> ResilientRedisClient:
    """Get circuit breaker-protected Redis client"""
    if _resilient_redis_client is None:
        await init_redis()
    return _resilient_redis_client


def get_redis_public_status() -> Dict[str, Any]:
    """This process's breaker summary for health endpoints (no hosts, no keys)."""
    if _resilient_redis_client is None:
        return {"state": "uninitialized", "client_initialized": False}
    return _resilient_redis_client.get_public_status()


async def get_raw_redis() -> Optional[redis.Redis]:
    """Get raw Redis client for cases requiring direct access"""
    if _raw_redis_client is None:
        await init_redis()
    return _raw_redis_client


class RateLimiter:
    """Simple rate limiter using Redis"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check if rate limit is exceeded

        Args:
            key: Rate limit key (e.g., f"rate_limit:{ip}:{endpoint}")
            limit: Maximum number of requests
            window: Time window in seconds

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        pipe = self.redis.pipeline()
        now = await self.redis.time()
        current_time = now[0]

        # Remove old entries
        pipe.zremrangebyscore(key, 0, current_time - window)

        # Count current entries
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(current_time): current_time})

        # Set expiry
        pipe.expire(key, window)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= limit:
            return False, 0

        return True, limit - current_count - 1


class SessionStore:
    """Session storage using Redis"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "session:"
        self.ttl = 60 * 60 * 24  # 24 hours

    async def set(self, session_id: str, data: dict, ttl: Optional[int] = None):
        """Store session data"""
        key = f"{self.prefix}{session_id}"
        ttl = ttl or self.ttl

        # Store as hash
        await self.redis.hset(key, mapping=data)
        await self.redis.expire(key, ttl)

    async def get(self, session_id: str) -> Optional[dict]:
        """Get session data"""
        key = f"{self.prefix}{session_id}"
        data = await self.redis.hgetall(key)
        return data if data else None

    async def delete(self, session_id: str):
        """Delete session"""
        key = f"{self.prefix}{session_id}"
        await self.redis.delete(key)

    async def extend(self, session_id: str, ttl: Optional[int] = None):
        """Extend session TTL"""
        key = f"{self.prefix}{session_id}"
        ttl = ttl or self.ttl
        await self.redis.expire(key, ttl)
