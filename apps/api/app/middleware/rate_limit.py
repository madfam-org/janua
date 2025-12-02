"""
Rate limiting middleware for API protection
"""

import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis

from app.config import settings
import structlog

logger = structlog.get_logger()


class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit violations"""
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with multiple strategies:
    - Per IP rate limiting
    - Per tenant rate limiting
    - Per endpoint rate limiting
    - Sliding window algorithm
    """

    def __init__(
        self,
        app: ASGIApp = None,
        redis_client: Optional[redis.Redis] = None,
        default_limit: int = 100,
        window_seconds: int = 60,
        enable_tenant_limits: bool = True
    ):
        if app:
            super().__init__(app)
        else:
            # Allow instantiation without app for testing
            self.app = None
        self.redis_client = redis_client
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.enable_tenant_limits = enable_tenant_limits
        
        # Endpoint-specific limits (requests per minute)
        self.endpoint_limits = {
            "/auth/signin": 10,
            "/auth/signup": 5,
            "/auth/password/reset": 3,
            "/auth/verify": 5,
            "/api/v1/sessions": 100,
            "/api/v1/identities": 50,
            "/api/v1/organizations": 30,
            "/api/v1/webhooks": 20,
        }
        
        # Tenant tier limits (requests per minute)
        self.tenant_tier_limits = {
            "community": 100,
            "pro": 1000,
            "scale": 5000,
            "enterprise": 10000,
        }

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting"""
        
        # Skip rate limiting for health checks and internal endpoints
        if request.url.path in ["/health", "/ready", "/.well-known/jwks.json"]:
            return await call_next(request)
        
        # Extract identifiers
        client_ip = self._get_client_ip(request)
        tenant_id = self._get_tenant_id(request)
        endpoint = self._normalize_endpoint(request.url.path)
        
        # Check rate limits
        try:
            # IP-based rate limiting
            ip_limit = self._get_ip_limit(client_ip)
            await self._check_rate_limit(
                key=f"rate_limit:ip:{client_ip}",
                limit=ip_limit,
                window=self.window_seconds,
                identifier=f"IP {client_ip}"
            )
            
            # Endpoint-specific rate limiting
            if endpoint in self.endpoint_limits:
                await self._check_rate_limit(
                    key=f"rate_limit:endpoint:{client_ip}:{endpoint}",
                    limit=self.endpoint_limits[endpoint],
                    window=self.window_seconds,
                    identifier=f"Endpoint {endpoint}"
                )
            
            # Tenant-based rate limiting
            if self.enable_tenant_limits and tenant_id:
                tenant_limit = await self._get_tenant_limit(tenant_id)
                await self._check_rate_limit(
                    key=f"rate_limit:tenant:{tenant_id}",
                    limit=tenant_limit,
                    window=self.window_seconds,
                    identifier=f"Tenant {tenant_id}"
                )
            
        except RateLimitExceeded as e:
            # Log rate limit violation
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {endpoint}",
                extra={
                    "client_ip": client_ip,
                    "tenant_id": tenant_id,
                    "endpoint": endpoint,
                    "retry_after": e.headers.get("Retry-After")
                }
            )
            
            # Track rate limit violations for monitoring
            if self.redis_client:
                await self._track_violation(client_ip, tenant_id, endpoint)
            
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        
        if self.redis_client:
            # Add rate limit info headers
            remaining = await self._get_remaining_requests(
                f"rate_limit:ip:{client_ip}",
                self.default_limit
            )
            response.headers["X-RateLimit-Limit"] = str(self.default_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(
                int(time.time()) + self.window_seconds
            )
        
        return response

    async def _check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        identifier: str
    ) -> None:
        """Check if rate limit is exceeded using sliding window"""
        
        if not self.redis_client:
            return  # Skip if Redis not available
        
        try:
            current_time = time.time()
            window_start = current_time - window
            
            # Remove old entries outside the window
            await self.redis_client.zremrangebyscore(
                key, 0, window_start
            )
            
            # Count requests in current window
            request_count = await self.redis_client.zcard(key)
            
            if request_count >= limit:
                # Calculate retry after based on oldest request in window
                oldest_request = await self.redis_client.zrange(
                    key, 0, 0, withscores=True
                )
                if oldest_request:
                    retry_after = int(
                        oldest_request[0][1] + window - current_time + 1
                    )
                else:
                    retry_after = window
                
                raise RateLimitExceeded(retry_after)
            
            # Add current request to the window
            await self.redis_client.zadd(
                key, {str(current_time): current_time}
            )
            
            # Set expiry for the key
            await self.redis_client.expire(key, window)
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # Allow request to proceed if Redis fails

    async def _get_remaining_requests(
        self,
        key: str,
        limit: int
    ) -> int:
        """Get remaining requests in current window"""
        
        if not self.redis_client:
            return limit
        
        try:
            current_count = await self.redis_client.zcard(key)
            return max(0, limit - current_count)
        except redis.RedisError:
            return limit

    async def _track_violation(
        self,
        client_ip: str,
        tenant_id: Optional[str],
        endpoint: str
    ) -> None:
        """Track rate limit violations for monitoring and security"""
        
        try:
            violation_key = "rate_limit:violations"
            violation_data = {
                "ip": client_ip,
                "tenant_id": tenant_id,
                "endpoint": endpoint,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add to violations list
            await self.redis_client.lpush(
                violation_key,
                json.dumps(violation_data)
            )
            
            # Keep only last 1000 violations
            await self.redis_client.ltrim(violation_key, 0, 999)
            
            # Track repeat offenders
            offender_key = f"rate_limit:offender:{client_ip}"
            violations = await self.redis_client.incr(offender_key)
            await self.redis_client.expire(offender_key, 3600)  # 1 hour
            
            # Auto-ban repeat offenders
            if violations > 10:
                await self._ban_client(client_ip, duration=3600)
                
        except redis.RedisError as e:
            logger.error(f"Failed to track rate limit violation: {e}")

    async def _ban_client(
        self,
        client_ip: str,
        duration: int = 3600
    ) -> None:
        """Temporarily ban a client IP"""
        
        ban_key = f"rate_limit:banned:{client_ip}"
        await self.redis_client.setex(ban_key, duration, "1")
        logger.warning(
            f"Client {client_ip} banned for {duration} seconds due to repeated violations"
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        
        # Check for forwarded IP (behind proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection IP
        if request.client:
            return request.client.host
        
        return "unknown"

    def _get_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request"""
        
        # Check header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_id
        
        # Check JWT claims if authenticated
        if hasattr(request.state, "tenant_id"):
            return request.state.tenant_id
        
        # Check query parameter
        tenant_id = request.query_params.get("tenant_id")
        if tenant_id:
            return tenant_id
        
        return None

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for rate limiting"""
        
        # Remove trailing slash
        path = path.rstrip("/")
        
        # Replace IDs with placeholders
        import re
        
        # UUID pattern
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/:id",
            path
        )
        
        # Numeric ID pattern
        path = re.sub(r"/\d+", "/:id", path)
        
        return path

    def _get_ip_limit(self, client_ip: str) -> int:
        """Get rate limit for specific IP"""
        
        # Check if IP is whitelisted
        if client_ip in settings.RATE_LIMIT_WHITELIST:
            return 100000  # Effectively unlimited
        
        # Check if IP is in a special range (e.g., internal network)
        if client_ip.startswith("10.") or client_ip.startswith("192.168."):
            return self.default_limit * 2
        
        return self.default_limit

    async def _get_tenant_limit(self, tenant_id: str) -> int:
        """Get rate limit for specific tenant based on their plan"""
        
        if not self.redis_client:
            return self.default_limit
        
        try:
            # Get tenant plan from cache
            plan_key = f"tenant:plan:{tenant_id}"
            plan = await self.redis_client.get(plan_key)
            
            if plan:
                plan = plan.decode("utf-8")
                return self.tenant_tier_limits.get(plan, self.default_limit)
            
            # Fetch from database if not in cache
            try:
                from app.database import get_db_session
                from app.models import Organization
                from sqlalchemy import select
                
                async with get_db_session() as db:
                    result = await db.execute(
                        select(Organization.billing_plan)
                        .where(Organization.id == tenant_id)
                    )
                    org_plan = result.scalar_one_or_none()
                    
                    if org_plan:
                        # Cache the plan for future requests (1 hour TTL)
                        await self.redis_client.setex(
                            plan_key, 
                            3600,  # 1 hour cache
                            org_plan
                        )
                        return self.tenant_tier_limits.get(org_plan, self.default_limit)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to fetch tenant plan from database: {e}"
                )
            
            return self.default_limit
            
        except redis.RedisError:
            return self.default_limit


class AdaptiveRateLimiter:
    """
    Advanced rate limiter with adaptive limits based on system load
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.base_limits = {
            "low": 1.5,    # 150% of normal
            "normal": 1.0,  # 100% of normal
            "high": 0.7,    # 70% of normal
            "critical": 0.3 # 30% of normal
        }
    
    async def get_adaptive_limit(
        self,
        base_limit: int,
        endpoint: str
    ) -> int:
        """Calculate adaptive limit based on system load"""
        
        try:
            # Get current system load metrics
            load = await self._get_system_load()
            
            # Get error rate for endpoint
            error_rate = await self._get_error_rate(endpoint)
            
            # Adjust limit based on load
            multiplier = self.base_limits.get(load, 1.0)
            
            # Further reduce if high error rate
            if error_rate > 0.1:  # >10% errors
                multiplier *= 0.5
            
            return int(base_limit * multiplier)
            
        except Exception as e:
            logger.error(f"Failed to calculate adaptive limit: {e}")
            return base_limit
    
    async def _get_system_load(self) -> str:
        """Determine current system load level"""
        
        # Check CPU usage, memory, response times from monitoring
        # This is a simplified example
        metrics_key = "system:metrics:current"
        metrics = await self.redis_client.get(metrics_key)
        
        if not metrics:
            return "normal"
        
        metrics = json.loads(metrics)
        cpu = metrics.get("cpu_percent", 50)
        
        if cpu > 80:
            return "critical"
        elif cpu > 60:
            return "high"
        elif cpu < 30:
            return "low"
        else:
            return "normal"
    
    async def _get_error_rate(self, endpoint: str) -> float:
        """Calculate error rate for endpoint"""
        
        error_key = f"endpoint:errors:{endpoint}"
        total_key = f"endpoint:requests:{endpoint}"
        
        errors = await self.redis_client.get(error_key) or 0
        total = await self.redis_client.get(total_key) or 1
        
        return float(errors) / float(total)