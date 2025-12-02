"""
Global Rate Limiting Configuration for ALL Endpoints
Ensures 100% endpoint coverage with appropriate limits per endpoint category
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional, Tuple

import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


class EndpointRateLimitConfig:
    """Configuration for different endpoint categories"""

    # Critical auth endpoints - strict limits
    AUTH_LIMITS = {
        "/api/v1/auth/signup": (5, 3600),  # 5 per hour
        "/api/v1/auth/signin": (10, 300),  # 10 per 5 minutes
        "/api/v1/auth/password/reset": (3, 3600),  # 3 per hour
        "/api/v1/auth/password/forgot": (3, 3600),  # 3 per hour
        "/api/v1/auth/magic-link": (5, 3600),  # 5 per hour
        "/api/v1/auth/refresh": (20, 300),  # 20 per 5 minutes
        "/api/v1/auth/signout": (10, 60),  # 10 per minute
    }

    # MFA endpoints - moderate limits
    MFA_LIMITS = {
        "/api/v1/mfa/setup": (5, 300),  # 5 per 5 minutes
        "/api/v1/mfa/verify": (10, 300),  # 10 attempts per 5 minutes
        "/api/v1/mfa/disable": (3, 300),  # 3 per 5 minutes
        "/api/v1/mfa/backup-codes": (3, 3600),  # 3 per hour
        "/api/v1/mfa/totp/setup": (5, 300),
        "/api/v1/mfa/sms/setup": (5, 300),
    }

    # OAuth endpoints
    OAUTH_LIMITS = {
        "/api/v1/oauth/authorize": (20, 300),  # 20 per 5 minutes
        "/api/v1/oauth/callback": (20, 300),
        "/api/v1/oauth/token": (10, 300),
        "/api/v1/oauth/revoke": (10, 300),
    }

    # Passkey/WebAuthn endpoints
    PASSKEY_LIMITS = {
        "/api/v1/passkeys/register": (10, 300),  # 10 per 5 minutes
        "/api/v1/passkeys/authenticate": (15, 300),  # 15 per 5 minutes
        "/api/v1/passkeys/list": (30, 60),  # 30 per minute
    }

    # Admin endpoints - strict for security
    ADMIN_LIMITS = {
        "/api/v1/admin": (10, 60),  # 10 per minute for all admin endpoints
        "/api/v1/rbac": (20, 60),  # 20 per minute for RBAC operations
        "/api/v1/policies": (15, 60),  # 15 per minute for policy management
    }

    # API endpoints - higher limits for normal usage
    API_LIMITS = {
        "/api/v1/users": (100, 60),  # 100 per minute
        "/api/v1/organizations": (50, 60),  # 50 per minute
        "/api/v1/sessions": (50, 60),  # 50 per minute
        "/api/v1/audit-logs": (30, 60),  # 30 per minute
    }

    # Health/monitoring endpoints - very high limits
    MONITORING_LIMITS = {
        "/api/v1/health": (1000, 60),  # 1000 per minute
        "/api/v1/health/live": (1000, 60),
        "/api/v1/health/ready": (1000, 60),
        "/api/v1/metrics": (100, 60),
    }

    # Compliance endpoints
    COMPLIANCE_LIMITS = {
        "/api/v1/compliance/gdpr": (20, 300),  # 20 per 5 minutes
        "/api/v1/compliance/report": (5, 3600),  # 5 per hour
        "/api/v1/compliance/audit": (10, 300),
    }

    # Default limits for any uncategorized endpoints
    DEFAULT_LIMITS = (60, 60)  # 60 requests per minute

    @classmethod
    def get_limit_for_path(cls, path: str) -> Tuple[int, int]:
        """Get rate limit configuration for a specific path"""

        # Check exact matches first
        all_limits = {
            **cls.AUTH_LIMITS,
            **cls.MFA_LIMITS,
            **cls.OAUTH_LIMITS,
            **cls.PASSKEY_LIMITS,
            **cls.ADMIN_LIMITS,
            **cls.API_LIMITS,
            **cls.MONITORING_LIMITS,
            **cls.COMPLIANCE_LIMITS,
        }

        if path in all_limits:
            return all_limits[path]

        # Check prefix matches for grouped endpoints
        for prefix, limits in [
            ("/api/v1/auth", (15, 60)),
            ("/api/v1/mfa", (20, 60)),
            ("/api/v1/oauth", (20, 60)),
            ("/api/v1/passkeys", (20, 60)),
            ("/api/v1/admin", (10, 60)),
            ("/api/v1/rbac", (20, 60)),
            ("/api/v1/compliance", (15, 60)),
            ("/api/v1/health", (1000, 60)),
            ("/api/v1/webhooks", (30, 60)),
            ("/api/v1/graphql", (50, 60)),
        ]:
            if path.startswith(prefix):
                return limits

        # Return default for everything else
        return cls.DEFAULT_LIMITS


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate limiting middleware that ensures 100% endpoint coverage
    Uses Redis for distributed rate limiting across instances
    """

    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        self.local_cache: Dict[str, Dict] = defaultdict(dict)
        self.cleanup_interval = 60  # Cleanup local cache every minute
        self.last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to ALL incoming requests"""

        # Extract path and method
        path = str(request.url.path)
        method = request.method

        # Skip rate limiting for OPTIONS requests (CORS preflight)
        if method == "OPTIONS":
            return await call_next(request)

        # Get client identifier (IP, user ID, or API key)
        client_id = self.get_client_identifier(request)

        # Get rate limit configuration for this endpoint
        max_requests, time_window = EndpointRateLimitConfig.get_limit_for_path(path)

        # Check rate limit
        is_allowed, remaining, reset_time = await self.check_rate_limit(
            client_id, path, max_requests, time_window
        )

        if not is_allowed:
            # Rate limit exceeded
            logger.warning(f"Rate limit exceeded for {client_id} on {path}")

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "error": "too_many_requests",
                    "retry_after": reset_time,
                    "limit": max_requests,
                    "window": time_window,
                    "path": path,
                },
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        # Periodic cleanup of local cache
        if time.time() - self.last_cleanup > self.cleanup_interval:
            await self.cleanup_local_cache()

        return response

    def get_client_identifier(self, request: Request) -> str:
        """Get unique identifier for the client"""

        # Priority order:
        # 1. Authenticated user ID (most accurate)
        # 2. API Key (if present)
        # 3. IP Address (fallback)

        # Check for authenticated user
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.id}"

        # Check for API key in headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Hash the API key for storage
            hashed_key = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            return f"api:{hashed_key}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

    async def check_rate_limit(
        self, client_id: str, path: str, max_requests: int, time_window: int
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit
        Returns: (is_allowed, remaining_requests, reset_timestamp)
        """

        # Create unique key for this client and endpoint
        key = f"rate_limit:{client_id}:{path}"
        current_time = int(time.time())

        # Use Redis if available (for distributed rate limiting)
        if self.redis_client:
            try:
                return await self._check_redis_rate_limit(
                    key, max_requests, time_window, current_time
                )
            except Exception as e:
                logger.error(f"Redis rate limit check failed: {e}")
                # Fall back to local cache

        # Use local in-memory cache as fallback
        return self._check_local_rate_limit(key, max_requests, time_window, current_time)

    async def _check_redis_rate_limit(
        self, key: str, max_requests: int, time_window: int, current_time: int
    ) -> Tuple[bool, int, int]:
        """Check rate limit using Redis"""

        # Use sliding window algorithm
        window_start = current_time - time_window

        # Remove old entries
        await self.redis_client.zremrangebyscore(key, 0, window_start)

        # Count current requests in window
        current_count = await self.redis_client.zcard(key)

        if current_count >= max_requests:
            # Get oldest entry to determine reset time
            oldest = await self.redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_time = int(oldest[0][1]) + time_window
            else:
                reset_time = current_time + time_window

            return False, 0, reset_time

        # Add current request
        await self.redis_client.zadd(key, {str(current_time): current_time})
        await self.redis_client.expire(key, time_window)

        remaining = max_requests - current_count - 1
        reset_time = current_time + time_window

        return True, remaining, reset_time

    def _check_local_rate_limit(
        self, key: str, max_requests: int, time_window: int, current_time: int
    ) -> Tuple[bool, int, int]:
        """Check rate limit using local in-memory cache"""

        # Get or create bucket for this key
        if key not in self.local_cache:
            self.local_cache[key] = {"requests": [], "reset_time": current_time + time_window}

        bucket = self.local_cache[key]
        window_start = current_time - time_window

        # Remove old requests outside the window
        bucket["requests"] = [
            req_time for req_time in bucket["requests"] if req_time > window_start
        ]

        # Check if limit exceeded
        if len(bucket["requests"]) >= max_requests:
            # Calculate reset time based on oldest request
            if bucket["requests"]:
                reset_time = bucket["requests"][0] + time_window
            else:
                reset_time = current_time + time_window

            return False, 0, reset_time

        # Add current request
        bucket["requests"].append(current_time)

        remaining = max_requests - len(bucket["requests"])
        reset_time = current_time + time_window

        return True, remaining, reset_time

    async def cleanup_local_cache(self):
        """Remove expired entries from local cache"""
        current_time = time.time()
        expired_keys = []

        for key, bucket in self.local_cache.items():
            # Remove if no recent requests
            if not bucket["requests"] or all(
                req_time < current_time - 3600 for req_time in bucket["requests"]
            ):
                expired_keys.append(key)

        for key in expired_keys:
            del self.local_cache[key]

        self.last_cleanup = current_time

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")


class AdvancedRateLimitFeatures:
    """Advanced rate limiting features for enterprise requirements"""

    @staticmethod
    async def _get_user_tier(user_id: str, db=None) -> str:
        """
        Fetch user's subscription tier from database.

        Args:
            user_id: User UUID
            db: Database session (optional)

        Returns:
            Tier name: "free", "pro", or "enterprise"
        """
        if not db:
            return "free"  # Default if no DB connection

        try:
            from uuid import UUID

            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession

            from app.models import OrganizationMember, Subscription

            # Convert string to UUID if needed
            if isinstance(user_id, str):
                user_id = UUID(user_id)

            # Get user's organization subscription
            async with db() as session:
                # Find user's active organization membership
                result = await session.execute(
                    select(Subscription.plan_id)
                    .join(
                        OrganizationMember,
                        OrganizationMember.organization_id == Subscription.organization_id,
                    )
                    .where(OrganizationMember.user_id == user_id)
                    .where(OrganizationMember.status == "active")
                    .where(Subscription.status.in_(["active", "trialing"]))
                    .limit(1)
                )
                subscription = result.scalar_one_or_none()

                if not subscription:
                    return "free"

                # Map plan_id to tier
                # Note: This assumes plan names contain tier information
                plan_str = str(subscription).lower()
                if "enterprise" in plan_str:
                    return "enterprise"
                elif "pro" in plan_str or "premium" in plan_str:
                    return "pro"
                else:
                    return "free"

        except Exception as e:
            logger.warning(f"Failed to fetch user tier for {user_id}: {e}")
            return "free"  # Default to free on error

    @staticmethod
    async def apply_user_tier_limits(
        user_id: str, base_limit: int, db=None, redis_client: Optional[redis.Redis] = None
    ) -> int:
        """Apply user tier multipliers (premium users get higher limits)"""

        # Tier multipliers for rate limiting
        tier_multipliers = {
            "free": 1.0,
            "pro": 2.0,
            "premium": 2.0,  # Alias for pro
            "enterprise": 5.0,
        }

        # Fetch actual user tier from database
        user_tier = await AdvancedRateLimitFeatures._get_user_tier(user_id, db)

        return int(base_limit * tier_multipliers.get(user_tier, 1.0))

    @staticmethod
    async def apply_adaptive_limits(path: str, current_load: float, base_limit: int) -> int:
        """Dynamically adjust limits based on system load"""

        # Reduce limits when system is under heavy load
        if current_load > 0.9:
            return int(base_limit * 0.5)  # 50% reduction
        elif current_load > 0.7:
            return int(base_limit * 0.75)  # 25% reduction

        return base_limit

    @staticmethod
    async def apply_burst_allowance(
        client_id: str, path: str, base_limit: int, redis_client: Optional[redis.Redis] = None
    ) -> int:
        """Allow temporary bursts above normal limits"""

        # Allow 20% burst capacity for short periods
        burst_multiplier = 1.2
        burst_key = f"burst:{client_id}:{path}"

        # Check if client has used burst recently
        # For now, always allow burst
        return int(base_limit * burst_multiplier)

    # Circuit breaker state for endpoints
    _endpoint_failures: Dict[str, Dict] = {}
    _circuit_breaker_threshold = 10  # failures before opening circuit
    _circuit_breaker_timeout = 60  # seconds before attempting recovery

    @classmethod
    def get_circuit_breaker_status(cls, path: str) -> bool:
        """
        Check if endpoint should be circuit-broken due to failures.
        
        Uses a simple circuit breaker pattern:
        - CLOSED: Normal operation (returns False)
        - OPEN: Too many failures, reject requests (returns True)
        - After timeout, allow one request through to test recovery
        """
        if path not in cls._endpoint_failures:
            return False
        
        state = cls._endpoint_failures[path]
        failure_count = state.get("failures", 0)
        circuit_opened = state.get("circuit_opened")
        
        # Not enough failures to open circuit
        if failure_count < cls._circuit_breaker_threshold:
            return False
        
        # Circuit is open - check if timeout has passed for recovery attempt
        if circuit_opened:
            time_since_open = time.time() - circuit_opened
            if time_since_open >= cls._circuit_breaker_timeout:
                # Allow one request through (half-open state)
                state["half_open"] = True
                return False
            return True  # Circuit still open
        
        return False

    @classmethod
    def record_endpoint_failure(cls, path: str):
        """Record a failure for circuit breaker tracking"""
        if path not in cls._endpoint_failures:
            cls._endpoint_failures[path] = {"failures": 0}
        
        state = cls._endpoint_failures[path]
        state["failures"] = state.get("failures", 0) + 1
        state["last_failure"] = time.time()
        
        if state["failures"] >= cls._circuit_breaker_threshold:
            if not state.get("circuit_opened"):
                state["circuit_opened"] = time.time()
                logger.warning(
                    f"Circuit breaker opened for endpoint: {path}",
                    extra={"failures": state["failures"]}
                )

    @classmethod
    def record_endpoint_success(cls, path: str):
        """Record success - reset circuit breaker if in half-open state"""
        if path in cls._endpoint_failures:
            state = cls._endpoint_failures[path]
            if state.get("half_open"):
                # Recovery successful, reset circuit
                cls._endpoint_failures[path] = {"failures": 0}
                logger.info(f"Circuit breaker closed for endpoint: {path}")


def create_rate_limit_middleware(app, redis_url: Optional[str] = None):
    """Factory function to create and configure rate limit middleware"""

    redis_client = None
    if redis_url:
        try:
            redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            logger.info("Redis connected for distributed rate limiting")
        except Exception as e:
            logger.warning(f"Redis connection failed, using local rate limiting: {e}")

    return GlobalRateLimitMiddleware(app, redis_client)
