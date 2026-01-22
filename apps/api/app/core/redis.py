from typing import Optional
import redis.asyncio as redis
import structlog

from app.config import settings
from app.core.redis_circuit_breaker import ResilientRedisClient

logger = structlog.get_logger()

# Global Redis clients
_raw_redis_client: Optional[redis.Redis] = None
_resilient_redis_client: Optional[ResilientRedisClient] = None


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
