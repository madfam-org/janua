"""
Comprehensive Security Headers Middleware Test Suite
Tests for security header injection and Content Security Policy handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from starlette.responses import Response

from app.middleware.security_headers import SecurityHeadersMiddleware

pytestmark = pytest.mark.asyncio


class TestSecurityHeadersMiddlewareInitialization:
    """Test middleware initialization."""

    def test_middleware_initialization_default(self):
        """Test middleware initializes with default strict mode."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.app == app
        assert middleware.strict is True

    def test_middleware_initialization_strict_true(self):
        """Test middleware initializes with strict=True."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True)

        assert middleware.strict is True

    def test_middleware_initialization_strict_false(self):
        """Test middleware initializes with strict=False."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=False)

        assert middleware.strict is False


class TestSecurityHeadersBasicHeaders:
    """Test basic security headers are added."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app, strict=True)

    @pytest.fixture
    def mock_request(self):
        """Create mock HTTP request."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/v1/users"
        return request

    @pytest.fixture
    def mock_response(self):
        """Create mock response with mutable headers."""
        response = MagicMock(spec=Response)
        response.headers = {}
        return response

    async def test_x_content_type_options_header(self, middleware, mock_request, mock_response):
        """Test X-Content-Type-Options header is added."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["X-Content-Type-Options"] == "nosniff"

    async def test_x_frame_options_header(self, middleware, mock_request, mock_response):
        """Test X-Frame-Options header is added."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["X-Frame-Options"] == "DENY"

    async def test_x_xss_protection_header(self, middleware, mock_request, mock_response):
        """Test X-XSS-Protection header is added."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["X-XSS-Protection"] == "1; mode=block"

    async def test_referrer_policy_header(self, middleware, mock_request, mock_response):
        """Test Referrer-Policy header is added."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_permissions_policy_header(self, middleware, mock_request, mock_response):
        """Test Permissions-Policy header is added."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "Permissions-Policy" in result.headers
        assert "camera=()" in result.headers["Permissions-Policy"]
        assert "microphone=()" in result.headers["Permissions-Policy"]
        assert "geolocation=()" in result.headers["Permissions-Policy"]

    async def test_server_header_set(self, middleware, mock_request, mock_response):
        """Test Server header is set to Janua-API."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["Server"] == "Janua-API"


class TestHSTSHeader:
    """Test Strict-Transport-Security (HSTS) header."""

    @pytest.fixture
    def mock_response(self):
        """Create mock response with mutable headers."""
        response = MagicMock(spec=Response)
        response.headers = {}
        return response

    async def test_hsts_on_https_request(self, mock_response):
        """Test HSTS header added for HTTPS requests."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=False)

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/test"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        assert "Strict-Transport-Security" in result.headers
        assert "max-age=31536000" in result.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in result.headers["Strict-Transport-Security"]
        assert "preload" in result.headers["Strict-Transport-Security"]

    async def test_hsts_on_http_with_strict_mode(self, mock_response):
        """Test HSTS header added for HTTP requests when strict mode is enabled."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True)

        request = MagicMock(spec=Request)
        request.url.scheme = "http"
        request.url.path = "/api/test"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        assert "Strict-Transport-Security" in result.headers

    async def test_no_hsts_on_http_without_strict_mode(self, mock_response):
        """Test HSTS header not added for HTTP requests when strict mode is disabled."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=False)

        request = MagicMock(spec=Request)
        request.url.scheme = "http"
        request.url.path = "/api/test"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        assert "Strict-Transport-Security" not in result.headers


class TestContentSecurityPolicy:
    """Test Content-Security-Policy header."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app, strict=True)

    @pytest.fixture
    def mock_response(self):
        """Create mock response with mutable headers."""
        response = MagicMock(spec=Response)
        response.headers = {}
        return response

    async def test_csp_default_src(self, middleware, mock_response):
        """Test CSP default-src directive."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/users"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp

    async def test_csp_frame_ancestors(self, middleware, mock_response):
        """Test CSP frame-ancestors directive."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/users"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    async def test_csp_upgrade_insecure_requests(self, middleware, mock_response):
        """Test CSP upgrade-insecure-requests directive."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/users"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "upgrade-insecure-requests" in csp

    async def test_csp_connect_src(self, middleware, mock_response):
        """Test CSP connect-src directive includes api.janua.dev."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/users"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "connect-src 'self' https://api.janua.dev https://cloudflareinsights.com" in csp

    async def test_csp_form_action_self_only(self, middleware, mock_response):
        """Test CSP form-action directive is 'self' only (no explicit URLs)."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/users"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "form-action 'self'" in csp


class TestCSPDynamicApiHost:
    """Test CSP connect-src uses configurable api_host parameter."""

    @pytest.fixture
    def mock_response(self):
        """Create mock response with mutable headers."""
        response = MagicMock(spec=Response)
        response.headers = {}
        return response

    async def test_csp_connect_src_default_host(self, mock_response):
        """Test CSP connect-src uses default api.janua.dev host."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True)

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/v1/users"

        call_next = AsyncMock(return_value=mock_response)
        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "connect-src 'self' https://api.janua.dev https://cloudflareinsights.com" in csp

    async def test_csp_connect_src_custom_host(self, mock_response):
        """Test CSP connect-src uses custom api_host when provided."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True, api_host="auth.madfam.io")

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/v1/users"

        call_next = AsyncMock(return_value=mock_response)
        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "connect-src 'self' https://auth.madfam.io https://cloudflareinsights.com" in csp
        assert "api.janua.dev" not in csp

    async def test_csp_form_action_self_only_custom_host(self, mock_response):
        """Test CSP form-action is 'self' only regardless of custom api_host."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True, api_host="auth.madfam.io")

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/v1/users"

        call_next = AsyncMock(return_value=mock_response)
        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "form-action 'self'" in csp

    async def test_csp_swagger_cdn_allowed(self, mock_response):
        """Test CSP allows CDN resources needed by Swagger UI."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True)

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/v1/users"

        call_next = AsyncMock(return_value=mock_response)
        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in csp


class TestCSPSwaggerRelaxation:
    """Test CSP relaxation for Swagger documentation endpoints."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app, strict=True)

    @pytest.fixture
    def mock_response(self):
        """Create mock response with mutable headers."""
        response = MagicMock(spec=Response)
        response.headers = {}
        return response

    async def test_csp_relaxed_for_docs_endpoint(self, middleware, mock_response):
        """Test CSP is relaxed for /docs endpoint."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/docs"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "'unsafe-eval'" in csp

    async def test_csp_relaxed_for_redoc_endpoint(self, middleware, mock_response):
        """Test CSP is relaxed for /redoc endpoint."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/redoc"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "'unsafe-eval'" in csp

    async def test_csp_relaxed_for_openapi_endpoint(self, middleware, mock_response):
        """Test CSP is relaxed for /openapi.json endpoint."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/openapi.json"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "'unsafe-eval'" in csp

    async def test_csp_strict_for_api_endpoint(self, middleware, mock_response):
        """Test CSP remains strict for regular API endpoints."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/v1/users"

        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        # Regular endpoints should not have unsafe-eval
        assert "'unsafe-eval'" not in csp


class TestServerHeaderRemoval:
    """Test server header handling."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app, strict=True)

    async def test_server_header_removed_if_present(self, middleware):
        """Test server header is removed if present in response."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/test"

        response = MagicMock(spec=Response)
        response.headers = {"server": "uvicorn"}

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        assert "server" not in result.headers

    async def test_no_error_if_server_header_missing(self, middleware):
        """Test no error if server header is not present."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/test"

        response = MagicMock(spec=Response)
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        # Should not raise an error
        assert "Server" in result.headers
        assert result.headers["Server"] == "Janua-API"


class TestMiddlewareCallsNextHandler:
    """Test middleware properly calls next handler."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app, strict=True)

    async def test_calls_next_handler(self, middleware):
        """Test middleware calls the next handler in chain."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/test"

        response = MagicMock(spec=Response)
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)

    async def test_returns_response_from_next_handler(self, middleware):
        """Test middleware returns the response from next handler."""
        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/test"

        expected_response = MagicMock(spec=Response)
        expected_response.headers = {}

        call_next = AsyncMock(return_value=expected_response)

        result = await middleware.dispatch(request, call_next)

        assert result is expected_response


class TestAllHeadersPresence:
    """Test all required security headers are present."""

    async def test_all_required_headers_present(self):
        """Test all security headers are added to response."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, strict=True)

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.path = "/api/test"

        response = MagicMock(spec=Response)
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "Permissions-Policy",
            "Server",
        ]

        for header in required_headers:
            assert header in result.headers, f"Missing header: {header}"
