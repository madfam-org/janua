import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for rate limiting middleware
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from starlette.responses import Response

from app.middleware.rate_limit import RateLimitMiddleware, RateLimitExceeded


class TestRateLimitExceeded:
    """Test rate limit exception."""
    
    def test_rate_limit_exceeded_creation(self):
        """Test RateLimitExceeded exception creation."""
        retry_after = 60
        exception = RateLimitExceeded(retry_after)
        
        assert exception.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exception.detail == "Rate limit exceeded"
        assert exception.headers["Retry-After"] == str(retry_after)


class TestRateLimitMiddleware:
    """Test rate limiting middleware functionality."""
    
    def test_middleware_initialization_default(self):
        """Test middleware initialization with default values."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        assert middleware.app == app
        assert middleware.redis_client is None
        assert middleware.default_limit == 100
        assert middleware.window_seconds == 60
        assert middleware.enable_tenant_limits is True
    
    @pytest.mark.asyncio
    async def test_dispatch_without_redis(self):
        """Test middleware dispatch when Redis is not available."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, redis_client=None)
        
        request = MagicMock(spec=Request)
        call_next = AsyncMock(return_value=Response())
        
        response = await middleware.dispatch(request, call_next)
        
        # Should proceed without rate limiting when Redis is not available
        call_next.assert_called_once_with(request)
        assert isinstance(response, Response)
    
    @pytest.mark.asyncio
    async def test_dispatch_with_rate_limit_allowed(self):
        """Test middleware dispatch when rate limit is not exceeded."""
        app = MagicMock()
        redis_client = AsyncMock()
        middleware = RateLimitMiddleware(app, redis_client=redis_client)
        
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.url.path = "/api/test"
        request.method = "GET"
        
        call_next = AsyncMock(return_value=Response())
        
        with patch.object(middleware, '_check_rate_limit', return_value=(True, 0)) as mock_check:
            response = await middleware.dispatch(request, call_next)
            
            mock_check.assert_called_once()
            call_next.assert_called_once_with(request)
            assert isinstance(response, Response)
    
    @pytest.mark.asyncio
    async def test_dispatch_with_rate_limit_exceeded(self):
        """Test middleware dispatch when rate limit is exceeded."""
        app = MagicMock()
        redis_client = AsyncMock()
        middleware = RateLimitMiddleware(app, redis_client=redis_client)
        
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.url.path = "/api/test"
        request.method = "GET"
        
        call_next = AsyncMock()
        
        with patch.object(middleware, '_check_rate_limit', return_value=(False, 60)) as mock_check:
            with pytest.raises(RateLimitExceeded) as exc_info:
                await middleware.dispatch(request, call_next)
            
            mock_check.assert_called_once()
            call_next.assert_not_called()
            assert exc_info.value.headers["Retry-After"] == "60"
    
    def test_get_rate_limit_key_ip_only(self):
        """Test rate limit key generation for IP-only limiting."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        request.url.path = "/api/test"
        request.method = "GET"
        
        key = middleware._get_rate_limit_key(request)
        expected = "rate_limit:192.168.1.1:/api/test"
        
        assert key == expected
    
    def test_get_rate_limit_for_endpoint_default(self):
        """Test getting rate limit for endpoint with default limit."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, default_limit=100)
        
        limit = middleware._get_rate_limit_for_endpoint("/api/test", "GET")
        
        assert limit == 100
