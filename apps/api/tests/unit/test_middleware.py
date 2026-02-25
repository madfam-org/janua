"""
Tests for middleware modules
"""

from unittest.mock import patch
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


class TestDynamicCORSMiddlewareDefaults:
    """Test DynamicCORSMiddleware default configuration."""

    def _make_app_with_cors(self, **cors_kwargs):
        """Create a minimal Starlette app with DynamicCORSMiddleware."""
        from app.middleware.dynamic_cors import DynamicCORSMiddleware

        async def homepage(request):
            return PlainTextResponse("OK")

        app = Starlette(routes=[Route("/", homepage)])

        # Patch settings.cors_origins_list to avoid database dependency
        with patch("app.middleware.dynamic_cors.settings") as mock_settings:
            mock_settings.cors_origins_list = ["http://localhost:3000"]
            middleware = DynamicCORSMiddleware(app, enable_database_origins=False, **cors_kwargs)

        return middleware

    def test_default_allow_headers_are_explicit(self):
        """Test that default allow_headers is an explicit allowlist, not wildcard."""
        middleware = self._make_app_with_cors()
        assert "*" not in middleware.allow_headers
        assert "Authorization" in middleware.allow_headers
        assert "Content-Type" in middleware.allow_headers
        assert "X-CSRF-Token" in middleware.allow_headers

    def test_explicit_allow_headers_override_default(self):
        """Test that passing explicit allow_headers overrides the default."""
        custom_headers = ["Authorization", "Content-Type"]
        middleware = self._make_app_with_cors(allow_headers=custom_headers)
        assert middleware.allow_headers == custom_headers

    def test_default_allow_methods(self):
        """Test default allow_methods list."""
        middleware = self._make_app_with_cors()
        assert "GET" in middleware.allow_methods
        assert "POST" in middleware.allow_methods
        assert "OPTIONS" in middleware.allow_methods

    def test_default_allow_headers_list(self):
        """Test the full default allow_headers list."""
        middleware = self._make_app_with_cors()
        expected = [
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "Accept",
            "Origin",
            "X-CSRF-Token",
            "X-Request-ID",
        ]
        assert middleware.allow_headers == expected


class TestMiddleware:
    """Test middleware functionality"""

    def test_placeholder(self):
        """Placeholder test"""
        assert True
