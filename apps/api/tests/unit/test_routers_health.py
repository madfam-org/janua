"""
Tests for the health router (`app/routers/v1/health.py`).

These used to wrap every import and call in `try/except -> pytest.skip`, and
three of them imported names the router no longer has (`ready_check`,
`get_db`), so they skipped on every run and tested nothing. They now call the
router's real functions; an import or signature change fails here instead of
disappearing into the skip count.

The readiness contract itself (Redis and the database reported, not gated;
status-only bodies) is pinned in `routers/test_readiness_redis_independent.py`,
`routers/test_readiness_database_reported.py` and
`routers/test_health_endpoints_no_error_text.py`.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_env():
    """Mock environment variables for testing"""
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "test",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/janua_test",
            "JWT_SECRET_KEY": "test-secret-key",
            "REDIS_URL": "redis://localhost:6379/1",
            "SECRET_KEY": "test-secret-key-for-testing",
        },
    ):
        yield


def test_health_router_imports(mock_env):
    """The health router imports and carries routes."""
    from app.routers.v1.health import router

    assert router is not None
    assert hasattr(router, "routes")


def test_health_endpoint_structure(mock_env):
    """The probe handlers the deployment points at exist."""
    from app.routers.v1.health import health_check, liveness_check, readiness_check

    assert callable(health_check)
    assert callable(readiness_check)
    assert callable(liveness_check)


async def test_health_check_function(mock_env):
    """`GET /api/v1/health` answers without touching a dependency."""
    from app.routers.v1.health import health_check

    result = await health_check()

    assert result["status"] == "healthy"
    assert "timestamp" in result
    assert result["service"] == "janua-api"


async def test_ready_check_function(mock_env):
    """`GET /api/v1/health/ready` with every check healthy is `ready`."""
    from app.routers.v1.health import readiness_check

    checker = AsyncMock()
    checker.check_health.return_value = {
        "status": "healthy",
        "timestamp": "2026-10-05T00:00:00",
        "checks": {
            "database": {"status": "healthy", "critical": True},
            "redis": {"status": "healthy", "critical": True},
            "encryption_key": {"status": "healthy", "critical": False},
        },
    }

    result = await readiness_check(checker=checker)

    assert result["status"] == "ready"
    assert result["degraded"] == []
    assert result["database"] == {"healthy": True, "status": "healthy"}
    assert result["redis"] == "healthy"
    assert "redis_circuit" in result


async def test_ready_check_without_a_health_checker_is_503(mock_env):
    """A health checker that never initialised gates readiness (503).

    Documented in docs/runbooks/oauth-shared-state-redis.md: since Redis and
    the database no longer gate, a 503 from readiness means a gating check
    failed, and today the only one is an uninitialised health checker.
    """
    from app.routers.v1 import health as health_v1

    with patch.object(health_v1, "health_checker", None):
        with pytest.raises(HTTPException) as exc:
            health_v1.get_health_checker()

    assert exc.value.status_code == 503


def test_health_router_routes(mock_env):
    """The router serves the probe paths the deployment uses."""
    from app.routers.v1.health import router

    route_paths = {route.path for route in router.routes}

    assert {"/health", "/health/ready", "/health/live", "/health/detailed"} <= route_paths


def test_health_router_methods(mock_env):
    """Every health route is a GET."""
    from app.routers.v1.health import router

    for route in router.routes:
        if hasattr(route, "methods"):
            assert "GET" in route.methods or "HEAD" in route.methods


def test_health_dependencies(mock_env):
    """The health router is a FastAPI router."""
    from fastapi import APIRouter

    from app.routers.v1.health import router

    assert isinstance(router, APIRouter)


async def test_check_encryption_key_health_non_production(mock_env):
    """Test encryption key health check passes in non-production."""
    from app.routers.v1.health import check_encryption_key_health

    result = await check_encryption_key_health()
    assert result is True


async def test_check_encryption_key_health_production_missing():
    """Test encryption key health check fails in production without key."""
    from app.routers.v1.health import check_encryption_key_health

    with patch("app.config.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.FIELD_ENCRYPTION_KEY = None

        result = await check_encryption_key_health()
        assert result is False
