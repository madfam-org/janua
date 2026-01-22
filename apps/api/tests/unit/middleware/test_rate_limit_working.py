import pytest

pytestmark = pytest.mark.asyncio


"""
Working tests for Rate Limit Middleware
"""

import pytest
from unittest.mock import Mock, AsyncMock
from app.middleware.rate_limit import RateLimitMiddleware


class TestRateLimitWorking:
    """Working rate limit tests"""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        app = Mock()
        middleware = RateLimitMiddleware(app)
        middleware.redis = AsyncMock()
        return middleware

    @pytest.mark.asyncio
    async def test_rate_limit_allows_request(self, middleware):
        """Test rate limit allows requests under limit"""
        request = Mock()
        request.client.host = "127.0.0.1"
        request.url.path = "/api/test"

        middleware.redis.get.return_value = b"5"  # Under default limit

        call_next = AsyncMock()
        response = Mock()
        call_next.return_value = response

        result = await middleware(request, call_next)

        assert result == response
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_excessive_requests(self, middleware):
        """Test rate limit blocks excessive requests"""
        request = Mock()
        request.client.host = "127.0.0.1"
        request.url.path = "/api/test"

        middleware.redis.get.return_value = b"100"  # Over default limit

        call_next = AsyncMock()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await middleware(request, call_next)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)
