import asyncio
import time
from typing import Optional

import redis.asyncio as redis
import structlog

from app.config import settings
from app.core.redis_circuit_breaker import ResilientRedisClient

logger = structlog.get_logger()

# Global Redis clients
_raw_redis_client: Optional[redis.Redis] = None
_resilient_redis_client: Optional[ResilientRedisClient] = None

# Authentication cannot use the cache's permissive fallback. If its initial
# connection failed, recover a separate pool without changing cache policy.
_security_redis_client: Optional[redis.Redis] = None
_security_recovery_lock = asyncio.Lock()
_security_retry_at = 0.0
_SECURITY_CONNECT_TIMEOUT = 5.0
_SECURITY_CLEANUP_TIMEOUT = 1.0
_SECURITY_RETRY_DELAY = 5.0


async def recover_security_redis() -> Optional[redis.Redis]:
    """Recover an initially unavailable security client, without cache fallback.

    Only a successfully connected pool is published. Concurrent requests share
    one probe; a failed probe imposes a per-worker cooldown. Once connected,
    redis-py handles reconnects and callers continue checking operation errors.
    """
    global _security_redis_client, _security_retry_at

    if _security_redis_client is not None:
        return _security_redis_client
    if time.monotonic() < _security_retry_at:
        return None

    async with _security_recovery_lock:
        if _security_redis_client is not None:
            return _security_redis_client
        if time.monotonic() < _security_retry_at:
            return None

        candidate = None
        connected = False
        try:
            candidate = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=settings.REDIS_DECODE_RESPONSES,
                max_connections=settings.REDIS_POOL_SIZE,
                socket_connect_timeout=_SECURITY_CONNECT_TIMEOUT,
                socket_timeout=_SECURITY_CONNECT_TIMEOUT,
            )
            connected = bool(
                await asyncio.wait_for(candidate.ping(), timeout=_SECURITY_CONNECT_TIMEOUT)
            )
            if connected:
                _security_redis_client = candidate
                return candidate
        except Exception:
            # No connection details or credentials belong in authentication logs.
            pass
        finally:
            if not connected:
                _security_retry_at = time.monotonic() + _SECURITY_RETRY_DELAY
                if candidate is not None:
                    try:
                        await asyncio.wait_for(
                            candidate.aclose(), timeout=_SECURITY_CLEANUP_TIMEOUT
                        )
                    except Exception:
                        pass
        return None


async def init_redis():
    """Initialize Redis connection with circuit breaker protection"""
    global _raw_redis_client, _resilient_redis_client

    try:
        # Create raw Redis client
        _raw_redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=settings.REDIS_DECODE_RESPONSES,
            max_connections=settings.REDIS_POOL_SIZE,
        )

        # Test connection
        await _raw_redis_client.ping()
        logger.info("Redis initialized successfully")

    except Exception as e:
        logger.warning("Failed to initialize Redis - running in degraded mode", error=str(e))
        _raw_redis_client = None

    # Create resilient client (works with or without raw client)
    _resilient_redis_client = ResilientRedisClient(_raw_redis_client)


async def get_redis() -> ResilientRedisClient:
    """Get circuit breaker-protected Redis client"""
    if _resilient_redis_client is None:
        await init_redis()
    return _resilient_redis_client


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
