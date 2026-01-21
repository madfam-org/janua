"""
Advanced Rate Limiting System
Provides sophisticated rate limiting with multiple algorithms and Redis backend
"""

import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import redis.asyncio as redis
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


class LimitType(Enum):
    """Rate limit types"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimit:
    """Rate limit configuration"""
    name: str
    limit: int
    window: int  # seconds
    limit_type: LimitType = LimitType.SLIDING_WINDOW
    burst_size: Optional[int] = None
    enabled: bool = True
    description: str = ""


@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    limit_name: str = ""


class AdvancedRateLimiter:
    """Advanced rate limiter with multiple algorithms"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.limits: Dict[str, RateLimit] = {}
        self._initialize_default_limits()

    def _initialize_default_limits(self):
        """Initialize default rate limits"""
        default_limits = [
            RateLimit(
                name="auth_attempts",
                limit=5,
                window=300,  # 5 minutes
                limit_type=LimitType.FIXED_WINDOW,
                description="Authentication attempts per IP"
            ),
            RateLimit(
                name="api_calls",
                limit=1000,
                window=3600,  # 1 hour
                limit_type=LimitType.SLIDING_WINDOW,
                burst_size=50,
                description="General API calls per user"
            ),
            RateLimit(
                name="password_reset",
                limit=3,
                window=3600,  # 1 hour
                limit_type=LimitType.FIXED_WINDOW,
                description="Password reset attempts per email"
            ),
            RateLimit(
                name="registration",
                limit=10,
                window=86400,  # 24 hours
                limit_type=LimitType.FIXED_WINDOW,
                description="User registrations per IP"
            ),
            RateLimit(
                name="webhook_delivery",
                limit=100,
                window=60,  # 1 minute
                limit_type=LimitType.TOKEN_BUCKET,
                burst_size=20,
                description="Webhook deliveries per organization"
            ),
            RateLimit(
                name="file_upload",
                limit=20,
                window=3600,  # 1 hour
                limit_type=LimitType.LEAKY_BUCKET,
                description="File uploads per user"
            ),
        ]

        for limit in default_limits:
            self.limits[limit.name] = limit

    def add_limit(self, rate_limit: RateLimit):
        """Add a new rate limit"""
        self.limits[rate_limit.name] = rate_limit
        logger.info("Rate limit added", name=rate_limit.name, limit=rate_limit.limit)

    def remove_limit(self, name: str):
        """Remove a rate limit"""
        if name in self.limits:
            del self.limits[name]
            logger.info("Rate limit removed", name=name)

    async def check_limit(self, limit_name: str, identifier: str) -> RateLimitResult:
        """Check if request is within rate limit"""
        if limit_name not in self.limits:
            logger.warning("Unknown rate limit", name=limit_name)
            return RateLimitResult(
                allowed=True,
                limit=0,
                remaining=0,
                reset_time=0,
                limit_name=limit_name
            )

        rate_limit = self.limits[limit_name]

        if not rate_limit.enabled:
            return RateLimitResult(
                allowed=True,
                limit=rate_limit.limit,
                remaining=rate_limit.limit,
                reset_time=0,
                limit_name=limit_name
            )

        # Route to appropriate algorithm
        if rate_limit.limit_type == LimitType.FIXED_WINDOW:
            return await self._check_fixed_window(rate_limit, identifier)
        elif rate_limit.limit_type == LimitType.SLIDING_WINDOW:
            return await self._check_sliding_window(rate_limit, identifier)
        elif rate_limit.limit_type == LimitType.TOKEN_BUCKET:
            return await self._check_token_bucket(rate_limit, identifier)
        elif rate_limit.limit_type == LimitType.LEAKY_BUCKET:
            return await self._check_leaky_bucket(rate_limit, identifier)

        return RateLimitResult(
            allowed=False,
            limit=rate_limit.limit,
            remaining=0,
            reset_time=int(time.time() + rate_limit.window),
            limit_name=limit_name
        )

    async def _check_fixed_window(self, rate_limit: RateLimit, identifier: str) -> RateLimitResult:
        """Fixed window rate limiting"""
        current_time = int(time.time())
        window_start = current_time - (current_time % rate_limit.window)
        key = f"rate_limit:fixed:{rate_limit.name}:{identifier}:{window_start}"

        current_count = await self.redis.get(key)
        current_count = int(current_count) if current_count else 0

        if current_count >= rate_limit.limit:
            return RateLimitResult(
                allowed=False,
                limit=rate_limit.limit,
                remaining=0,
                reset_time=window_start + rate_limit.window,
                retry_after=window_start + rate_limit.window - current_time,
                limit_name=rate_limit.name
            )

        # Increment counter
        pipeline = self.redis.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, rate_limit.window)
        await pipeline.execute()

        return RateLimitResult(
            allowed=True,
            limit=rate_limit.limit,
            remaining=rate_limit.limit - current_count - 1,
            reset_time=window_start + rate_limit.window,
            limit_name=rate_limit.name
        )

    async def _check_sliding_window(self, rate_limit: RateLimit, identifier: str) -> RateLimitResult:
        """Sliding window rate limiting"""
        current_time = time.time()
        window_start = current_time - rate_limit.window
        key = f"rate_limit:sliding:{rate_limit.name}:{identifier}"

        # Remove old entries and count current requests
        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(key, 0, window_start)
        pipeline.zcard(key)
        pipeline.expire(key, rate_limit.window)
        results = await pipeline.execute()

        current_count = results[1]

        if current_count >= rate_limit.limit:
            # Get the oldest entry to calculate reset time
            oldest_entries = await self.redis.zrange(key, 0, 0, withscores=True)
            reset_time = int(oldest_entries[0][1] + rate_limit.window) if oldest_entries else int(current_time + rate_limit.window)

            return RateLimitResult(
                allowed=False,
                limit=rate_limit.limit,
                remaining=0,
                reset_time=reset_time,
                retry_after=reset_time - int(current_time),
                limit_name=rate_limit.name
            )

        # Add current request
        await self.redis.zadd(key, {str(current_time): current_time})

        return RateLimitResult(
            allowed=True,
            limit=rate_limit.limit,
            remaining=rate_limit.limit - current_count - 1,
            reset_time=int(current_time + rate_limit.window),
            limit_name=rate_limit.name
        )

    async def _check_token_bucket(self, rate_limit: RateLimit, identifier: str) -> RateLimitResult:
        """Token bucket rate limiting"""
        current_time = time.time()
        key = f"rate_limit:token:{rate_limit.name}:{identifier}"
        bucket_size = rate_limit.burst_size or rate_limit.limit
        refill_rate = rate_limit.limit / rate_limit.window  # tokens per second

        # Get current bucket state
        bucket_data = await self.redis.get(key)

        if bucket_data:
            bucket_state = json.loads(bucket_data)
            last_refill = bucket_state['last_refill']
            tokens = bucket_state['tokens']
        else:
            last_refill = current_time
            tokens = bucket_size

        # Calculate tokens to add
        time_passed = current_time - last_refill
        tokens_to_add = time_passed * refill_rate
        tokens = min(bucket_size, tokens + tokens_to_add)

        if tokens < 1:
            # Calculate when next token will be available
            next_token_time = (1 - tokens) / refill_rate
            return RateLimitResult(
                allowed=False,
                limit=rate_limit.limit,
                remaining=0,
                reset_time=int(current_time + next_token_time),
                retry_after=int(next_token_time),
                limit_name=rate_limit.name
            )

        # Consume one token
        tokens -= 1

        # Update bucket state
        new_state = {
            'tokens': tokens,
            'last_refill': current_time
        }
        await self.redis.setex(key, rate_limit.window * 2, json.dumps(new_state))

        return RateLimitResult(
            allowed=True,
            limit=rate_limit.limit,
            remaining=int(tokens),
            reset_time=int(current_time + (bucket_size - tokens) / refill_rate),
            limit_name=rate_limit.name
        )

    async def _check_leaky_bucket(self, rate_limit: RateLimit, identifier: str) -> RateLimitResult:
        """Leaky bucket rate limiting"""
        current_time = time.time()
        key = f"rate_limit:leaky:{rate_limit.name}:{identifier}"
        bucket_size = rate_limit.limit
        leak_rate = rate_limit.limit / rate_limit.window  # items per second

        # Get current bucket state
        bucket_data = await self.redis.get(key)

        if bucket_data:
            bucket_state = json.loads(bucket_data)
            last_leak = bucket_state['last_leak']
            level = bucket_state['level']
        else:
            last_leak = current_time
            level = 0

        # Calculate how much has leaked
        time_passed = current_time - last_leak
        leaked = time_passed * leak_rate
        level = max(0, level - leaked)

        if level >= bucket_size:
            # Bucket is full
            leak_time = (level - bucket_size + 1) / leak_rate
            return RateLimitResult(
                allowed=False,
                limit=rate_limit.limit,
                remaining=0,
                reset_time=int(current_time + leak_time),
                retry_after=int(leak_time),
                limit_name=rate_limit.name
            )

        # Add request to bucket
        level += 1

        # Update bucket state
        new_state = {
            'level': level,
            'last_leak': current_time
        }
        await self.redis.setex(key, rate_limit.window * 2, json.dumps(new_state))

        return RateLimitResult(
            allowed=True,
            limit=rate_limit.limit,
            remaining=int(bucket_size - level),
            reset_time=int(current_time + level / leak_rate),
            limit_name=rate_limit.name
        )

    async def reset_limit(self, limit_name: str, identifier: str):
        """Reset rate limit for specific identifier"""
        pattern = f"rate_limit:*:{limit_name}:{identifier}*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
        logger.info("Rate limit reset", name=limit_name, identifier=identifier)

    async def get_limit_status(self, limit_name: str, identifier: str) -> Dict:
        """Get current status of a rate limit"""
        if limit_name not in self.limits:
            return {"error": "Unknown rate limit"}

        rate_limit = self.limits[limit_name]
        result = await self.check_limit(limit_name, identifier)

        return {
            "limit_name": limit_name,
            "limit_type": rate_limit.limit_type.value,
            "limit": result.limit,
            "remaining": result.remaining,
            "reset_time": result.reset_time,
            "enabled": rate_limit.enabled
        }


class RateLimitMiddleware:
    """Rate limiting middleware for FastAPI"""

    def __init__(self, redis_client: redis.Redis, default_limits: Optional[List[str]] = None):
        self.rate_limiter = AdvancedRateLimiter(redis_client)
        self.default_limits = default_limits or ["api_calls"]

    async def __call__(self, request: Request, call_next):
        """Apply rate limiting to request"""
        # Extract identifier (IP, user ID, API key, etc.)
        identifier = self._get_identifier(request)

        # Check applicable rate limits
        for limit_name in self._get_applicable_limits(request):
            result = await self.rate_limiter.check_limit(limit_name, identifier)

            if not result.allowed:
                logger.warning(
                    "Rate limit exceeded",
                    limit_name=limit_name,
                    identifier=identifier,
                    limit=result.limit,
                    reset_time=result.reset_time
                )

                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "limit_name": limit_name,
                        "limit": result.limit,
                        "retry_after": result.retry_after
                    },
                    headers={
                        "X-RateLimit-Limit": str(result.limit),
                        "X-RateLimit-Remaining": str(result.remaining),
                        "X-RateLimit-Reset": str(result.reset_time),
                        "Retry-After": str(result.retry_after) if result.retry_after else "60"
                    }
                )

        # Continue with request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        if identifier and self.default_limits:
            primary_limit = self.default_limits[0]
            result = await self.rate_limiter.get_limit_status(primary_limit, identifier)

            if "error" not in result:
                response.headers["X-RateLimit-Limit"] = str(result["limit"])
                response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
                response.headers["X-RateLimit-Reset"] = str(result["reset_time"])

        return response

    def _get_identifier(self, request: Request) -> str:
        """Extract identifier from request"""
        # Priority: User ID > API Key > IP Address

        # Check for authenticated user
        if hasattr(request.state, 'user_id'):
            return f"user:{request.state.user_id}"

        # Check for API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"

        # Fall back to IP address
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.headers.get("X-Real-IP", "")
        if not client_ip and request.client:
            client_ip = request.client.host

        return f"ip:{client_ip}"

    def _get_applicable_limits(self, request: Request) -> List[str]:
        """Determine which rate limits apply to this request"""
        path = request.url.path
        request.method

        # Route-specific limits
        limits = []

        if "/auth/" in path:
            if "login" in path or "token" in path:
                limits.append("auth_attempts")
            elif "register" in path:
                limits.append("registration")
            elif "reset-password" in path:
                limits.append("password_reset")

        if "/upload" in path:
            limits.append("file_upload")

        if "/webhook" in path:
            limits.append("webhook_delivery")

        # Always apply general API limits
        limits.extend(self.default_limits)

        return list(set(limits))  # Remove duplicates


class RateLimitStats:
    """Rate limiting statistics and monitoring"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def record_request(self, limit_name: str, identifier: str, allowed: bool):
        """Record rate limit request for statistics"""
        timestamp = int(time.time())
        stats_key = f"rate_limit_stats:{limit_name}:{timestamp // 60}"  # Per minute stats

        pipeline = self.redis.pipeline()
        pipeline.hincrby(stats_key, "total_requests", 1)
        if not allowed:
            pipeline.hincrby(stats_key, "blocked_requests", 1)
        pipeline.expire(stats_key, 86400)  # Keep for 24 hours
        await pipeline.execute()

    async def get_stats(self, limit_name: str, hours: int = 24) -> Dict:
        """Get rate limiting statistics"""
        current_time = int(time.time())
        stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "block_rate": 0.0,
            "time_range_hours": hours
        }

        # Aggregate stats for the specified time range
        for i in range(hours * 60):  # Per minute stats
            timestamp = current_time - (i * 60)
            stats_key = f"rate_limit_stats:{limit_name}:{timestamp // 60}"

            stat_data = await self.redis.hgetall(stats_key)
            if stat_data:
                stats["total_requests"] += int(stat_data.get("total_requests", 0))
                stats["blocked_requests"] += int(stat_data.get("blocked_requests", 0))

        # Calculate block rate
        if stats["total_requests"] > 0:
            stats["block_rate"] = (stats["blocked_requests"] / stats["total_requests"]) * 100

        return stats


# Dependency injection helpers
async def get_rate_limiter() -> AdvancedRateLimiter:
    """Get rate limiter instance"""
    # This would typically be configured with your Redis connection
    redis_client = redis.from_url("redis://localhost:6379")
    return AdvancedRateLimiter(redis_client)


def create_rate_limit_middleware(redis_url: str = "redis://localhost:6379") -> RateLimitMiddleware:
    """Create rate limiting middleware"""
    redis_client = redis.from_url(redis_url)
    return RateLimitMiddleware(redis_client)