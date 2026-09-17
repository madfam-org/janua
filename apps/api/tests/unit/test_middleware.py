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


class TestDynamicCORSWildcardBoundary:
    """A `*.domain` CORS entry must only match on a dot boundary.

    The pre-fix implementation used a bare `origin_domain.endswith(domain)`,
    which accepted `evilmadfam.io` for `*.madfam.io` — an attacker who
    registers a lookalike domain would get credentialed CORS access to the
    Janua API. `core/url_security.py::_host_matches_pattern` already enforced
    the dot boundary; this pins the CORS middleware to the same rule.
    """

    def _middleware(self, allowed):
        from app.middleware.dynamic_cors import DynamicCORSMiddleware

        async def homepage(request):
            return PlainTextResponse("OK")

        app = Starlette(routes=[Route("/", homepage)])
        with patch("app.middleware.dynamic_cors.settings") as mock_settings:
            mock_settings.cors_origins_list = list(allowed)
            return DynamicCORSMiddleware(app, enable_database_origins=False)

    def test_subdomain_still_matches(self):
        mw = self._middleware(["*.madfam.io"])
        allowed = {"*.madfam.io"}
        assert mw._is_origin_allowed("https://crea-map.madfam.io", allowed)
        assert mw._is_origin_allowed("https://auth.madfam.io", allowed)

    def test_base_domain_still_matches(self):
        mw = self._middleware(["*.madfam.io"])
        assert mw._is_origin_allowed("https://madfam.io", {"*.madfam.io"})

    def test_lookalike_domain_is_rejected(self):
        """REGRESSION: fails on the pre-fix bare endswith()."""
        mw = self._middleware(["*.madfam.io"])
        allowed = {"*.madfam.io"}
        assert not mw._is_origin_allowed("https://evilmadfam.io", allowed)
        assert not mw._is_origin_allowed("https://notmadfam.io", allowed)
        assert not mw._is_origin_allowed("https://app.evilmadfam.io", allowed)

    def test_unrelated_domain_is_rejected(self):
        mw = self._middleware(["*.madfam.io"])
        assert not mw._is_origin_allowed("https://evil.com", {"*.madfam.io"})

    def test_exact_origin_match_unaffected(self):
        mw = self._middleware(["https://madfam.io"])
        assert mw._is_origin_allowed("https://madfam.io", {"https://madfam.io"})


class TestMiddleware:
    """Test middleware functionality"""

    def test_placeholder(self):
        """Placeholder test"""
        assert True


class TestDynamicCORSDatabaseOrigins:
    """The client-derived CORS allow-list must actually load.

    ``_load_oauth_client_origins`` and ``_load_database_origins`` import
    ``get_db_session`` from ``app.core.database``. For months nothing defined
    that name; the ImportError was caught by the loaders' broad ``except`` and
    logged at DEBUG, so only the static ``CORS_ORIGINS`` list ever applied and a
    freshly registered client's origin (yantra4d-studio, 2026-09-17) got no
    CORS. These tests pin the import target and the derivation.
    """

    def _middleware(self, static=("https://static.example.test",)):
        from app.middleware.dynamic_cors import DynamicCORSMiddleware

        app = Starlette(routes=[Route("/", lambda r: PlainTextResponse("ok"))])
        with patch("app.middleware.dynamic_cors.settings") as mock_settings:
            mock_settings.cors_origins_list = list(static)
            return DynamicCORSMiddleware(app, enable_database_origins=True)

    def test_get_db_session_is_defined_where_the_loaders_import_it(self):
        from app.core.database import get_db_session as core_session
        from app.database import get_db_session as legacy_session

        for factory in (core_session, legacy_session):
            cm = factory()
            assert hasattr(cm, "__aenter__") and hasattr(cm, "__aexit__"), (
                "get_db_session must be an async context manager (async with ... as db)"
            )

    async def test_oauth_client_origins_are_derived_from_active_clients(self):
        from contextlib import asynccontextmanager

        class FakeResult:
            def all(self):
                return [
                    (["https://app.yantra4d.com", "http://localhost:5173"],),
                    (["https://app.example.test/api/auth/callback"],),
                    (None,),
                ]

        class FakeDB:
            async def execute(self, _stmt):
                return FakeResult()

        @asynccontextmanager
        async def fake_session():
            yield FakeDB()

        with patch("app.core.database.get_db_session", fake_session):
            origins = await self._middleware()._load_oauth_client_origins()

        assert origins == {
            "https://app.yantra4d.com",
            "http://localhost:5173",
            "https://app.example.test",
        }

    async def test_allowed_origins_merge_static_and_derived(self):
        import app.middleware.dynamic_cors as dc

        middleware = self._middleware()
        dc.invalidate_cors_cache()

        async def db_origins():
            return {"https://table.example.test"}

        async def client_origins():
            return {"https://app.yantra4d.com"}

        with (
            patch.object(middleware, "_load_database_origins", db_origins),
            patch.object(middleware, "_load_oauth_client_origins", client_origins),
        ):
            allowed = await middleware._get_allowed_origins()

        assert allowed == {
            "https://static.example.test",
            "https://table.example.test",
            "https://app.yantra4d.com",
        }
        assert middleware._is_origin_allowed("https://app.yantra4d.com", allowed)
        dc.invalidate_cors_cache()

    async def test_loader_failure_is_loud_but_not_fatal(self, caplog):
        import logging
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def broken_session():
            raise RuntimeError("database unavailable")
            yield  # pragma: no cover

        with (
            patch("app.core.database.get_db_session", broken_session),
            caplog.at_level(logging.WARNING, logger="app.middleware.dynamic_cors"),
        ):
            origins = await self._middleware()._load_oauth_client_origins()

        assert origins == set()
        assert any(
            "Could not load CORS origins from OAuth clients" in rec.getMessage()
            and rec.levelno == logging.WARNING
            for rec in caplog.records
        ), "a failing loader must be visible at WARNING, not buried at DEBUG"
