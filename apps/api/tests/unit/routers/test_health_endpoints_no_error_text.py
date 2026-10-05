"""Health and readiness endpoints publish status fields only (J4-002).

Owner decision (2026-10-04): "yes to both fixes".

`GET /ready` used to return `get_database_health()` verbatim, including the
driver's `error` string, and `HealthChecker` put `str(e)` of a failing check
into `/api/v1/health/detailed`. During an outage that text can carry an
internal hostname, an IP or a DSN. Now every health/readiness endpoint returns
status fields only (`healthy`, `status`, `degraded`, the Redis and breaker
fields); the detail is logged server-side, redacted.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
import pytest_asyncio

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient

from app.core.redis_circuit_breaker import ResilientRedisClient
from app.services.monitoring import HealthChecker, redact_error_text

pytestmark = pytest.mark.asyncio

# What a real driver error can carry. None of it may reach a response body.
DB_HOST = "db-internal.example.test"
DB_SECRET = "fixture-not-a-real-password"
DB_ERROR = (
    f"could not connect to server: postgresql+asyncpg://janua:{DB_SECRET}@{DB_HOST}:5432/janua"
    " (10.0.0.12)"
)
LEAK_MARKERS = (
    DB_ERROR,
    DB_HOST,
    DB_SECRET,
    "10.0.0.12",
    "postgresql+asyncpg",
    "could not connect",
)


def _assert_no_leak(text: str) -> None:
    for marker in LEAK_MARKERS:
        assert marker not in text, f"{marker!r} leaked into a health response"


def _redis(connected: bool = True) -> ResilientRedisClient:
    server = fakeredis.FakeServer()
    client = ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    )
    server.connected = connected
    return client


def _db_health_reports_error() -> AsyncMock:
    """`get_database_health()` during an outage: a dict carrying the driver text."""
    return AsyncMock(return_value={"healthy": False, "error": DB_ERROR})


def _db_health_raises() -> AsyncMock:
    return AsyncMock(side_effect=OSError(DB_ERROR))


def _db_health_ok() -> AsyncMock:
    return AsyncMock(return_value={"healthy": True, "response_time_ms": 1.0})


async def _raising_check():
    raise ConnectionError(DB_ERROR)


def _checker(extra_failing_check: bool = False) -> HealthChecker:
    """The checks main.py registers (real database and Redis checks)."""
    from app.main import _check_database_health, _check_redis_health
    from app.routers.v1.health import check_encryption_key_health

    checker = HealthChecker(AsyncMock())
    checker.register_check("database", _check_database_health, critical=True)
    checker.register_check("redis", _check_redis_health, critical=True)
    checker.register_check("encryption_key", check_encryption_key_health, critical=False)
    if extra_failing_check:
        # A check that raises with the driver text (the HealthChecker path
        # that used to copy `str(e)` into the body).
        checker.register_check("dependency", _raising_check, critical=False)
    return checker


@pytest_asyncio.fixture
async def call():
    from app.main import app
    from app.routers.v1 import health as health_v1

    saved_checker = health_v1.health_checker

    async def _call(
        path: str,
        *,
        db_health: AsyncMock | None = None,
        redis=None,
        extra_failing_check: bool = False,
    ):
        health_v1.health_checker = _checker(extra_failing_check)
        client = redis or _redis()
        get = AsyncMock(return_value=client)

        async def _redis_dependency():
            return client

        saved = dict(app.dependency_overrides)
        # /api/v1/health/redis and /circuit-breaker take Redis via Depends.
        # Keyed on the function health.py captured at import (tests/conftest.py
        # swaps app.core.redis.get_redis afterwards).
        app.dependency_overrides[health_v1.get_redis] = _redis_dependency
        try:
            with (
                patch("app.core.redis.get_redis", get),
                patch("app.main.get_redis", get),
                patch("app.main.get_database_health", db_health or _db_health_reports_error()),
            ):
                transport = ASGITransport(app=app, raise_app_exceptions=False)
                async with AsyncClient(transport=transport, base_url="http://test") as http:
                    return await http.get(path)
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)

    yield _call
    health_v1.health_checker = saved_checker


def _health_get_paths() -> list[str]:
    """Every GET path whose name is health or readiness (no path params).

    Read from the OpenAPI document: the app includes routers lazily, so
    `app.routes` does not list the included routes.
    """
    from app.main import app

    return sorted(
        path
        for path, operations in app.openapi()["paths"].items()
        if "get" in operations and "{" not in path and ("health" in path or path.endswith("/ready"))
    )


class TestReadyRoot:
    """`GET /ready` (the root summary referenced by the helm/production manifests)."""

    @pytest.mark.parametrize("db_health", [_db_health_reports_error, _db_health_raises])
    async def test_a_database_error_never_reaches_the_body(self, call, db_health):
        resp = await call("/ready", db_health=db_health())

        assert resp.status_code == 200, resp.text
        _assert_no_leak(resp.text)
        body = resp.json()
        # The status fields still reflect the outage.
        assert body["status"] == "degraded"
        assert body["database"] == {"healthy": False, "status": "unhealthy"}
        assert body["degraded"] == ["database"]
        assert body["redis"] is True
        assert "error" not in body["database"]

    async def test_only_status_fields_are_published(self, call):
        resp = await call("/ready")

        assert set(resp.json()) == {"status", "database", "redis", "redis_circuit", "degraded"}
        assert set(resp.json()["database"]) == {"healthy", "status"}

    async def test_redis_down_is_reported(self, call):
        resp = await call("/ready", db_health=_db_health_ok(), redis=_redis(connected=False))

        body = resp.json()
        assert resp.status_code == 200
        assert body["status"] == "degraded"
        assert body["redis"] is False
        assert body["degraded"] == ["redis"]
        assert body["database"] == {"healthy": True, "status": "healthy"}
        assert "state" in body["redis_circuit"]

    async def test_healthy_is_ready(self, call):
        resp = await call("/ready", db_health=_db_health_ok())

        body = resp.json()
        assert body["status"] == "ready"
        assert body["database"] == {"healthy": True, "status": "healthy"}
        assert body["redis"] is True
        assert body["degraded"] == []

    async def test_the_detail_is_logged_redacted(self, call, caplog):
        with caplog.at_level(logging.WARNING, logger="app.main"):
            await call("/ready", db_health=_db_health_reports_error())

        logged = "\n".join(r.getMessage() for r in caplog.records if r.name == "app.main")
        assert "Database health check unhealthy" in logged
        assert DB_SECRET not in logged
        assert "postgresql+asyncpg://***@" in logged


class TestDetailedHealth:
    async def test_a_raising_check_reports_error_status_without_its_text(self, call):
        resp = await call("/api/v1/health/detailed", extra_failing_check=True)

        assert resp.status_code == 200, resp.text
        _assert_no_leak(resp.text)
        body = resp.json()
        assert body["checks"]["dependency"] == {"status": "error", "critical": False}
        assert body["checks"]["database"]["status"] == "unhealthy"
        assert body["status"] == "unhealthy"

    async def test_the_raising_check_is_logged_redacted(self, call, caplog):
        with caplog.at_level(logging.ERROR, logger="app.services.monitoring"):
            await call("/api/v1/health/detailed", extra_failing_check=True)

        logged = "\n".join(r.getMessage() for r in caplog.records)
        assert "Health check dependency failed: ConnectionError" in logged
        assert DB_SECRET not in logged


class TestEveryHealthEndpoint:
    def test_the_sweep_covers_the_known_endpoints(self):
        paths = _health_get_paths()
        for expected in (
            "/health",
            "/ready",
            "/api/v1/health",
            "/api/v1/health/ready",
            "/api/v1/health/detailed",
            "/api/v1/health/live",
            "/api/v1/health/redis",
            "/api/v1/health/circuit-breaker",
            "/api/v1/admin/health",
            "/api/v1/alerts/health",
        ):
            assert expected in paths, paths

    @pytest.mark.parametrize("db_health", [_db_health_reports_error, _db_health_raises])
    async def test_a_simulated_database_error_appears_in_no_health_body(self, call, db_health):
        paths = _health_get_paths()
        assert paths
        for path in paths:
            resp = await call(path, db_health=db_health(), extra_failing_check=True)
            # Authenticated variants (e.g. /api/v1/admin/health) answer 401/403
            # here; they must not leak either.
            assert resp.status_code < 500, (path, resp.status_code, resp.text)
            _assert_no_leak(resp.text)

    async def test_readiness_status_fields_still_reflect_the_error(self, call):
        resp = await call("/api/v1/health/ready", db_health=_db_health_raises())

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] == {"healthy": False, "status": "unhealthy"}
        assert body["degraded"] == ["database"]


class TestAdminHealth:
    async def test_cache_failure_is_status_only(self):
        from app.routers.v1 import admin

        user = MagicMock()
        db = MagicMock()
        db.execute = AsyncMock()
        email = MagicMock()
        email.check_health = AsyncMock(return_value={"status": "healthy"})
        with (
            patch.object(admin, "check_admin_permission", lambda _user: None),
            patch("app.core.redis.get_redis", AsyncMock(side_effect=OSError(DB_ERROR))),
            patch(
                "app.services.resend_email_service.get_resend_email_service",
                MagicMock(return_value=email),
            ),
        ):
            result = await admin.get_system_health(current_user=user, db=db)

        assert result.cache == "unhealthy"
        _assert_no_leak(result.model_dump_json())


class TestRedactErrorText:
    def test_dsn_credentials_are_removed(self):
        redacted = redact_error_text(DB_ERROR)
        assert DB_SECRET not in redacted
        assert "postgresql+asyncpg://***@" in redacted

    def test_password_pairs_are_removed(self):
        redacted = redact_error_text("connect failed: host=db password=abc123 user=janua")
        assert "abc123" not in redacted
        assert "password=***" in redacted

    def test_plain_text_is_unchanged_and_length_is_capped(self):
        assert redact_error_text("connection refused") == "connection refused"
        assert len(redact_error_text("x" * 1000)) <= 303
