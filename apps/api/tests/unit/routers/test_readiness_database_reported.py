"""Readiness reports the database honestly and does not gate on it (J3-001).

Owner decision (2026-10-04): "yes, go with all three recommendations".

The `database` readiness check had never failed: `get_database_health()`
returns a dict, and `HealthChecker` counted any truthy result as healthy, so
`GET /api/v1/health/ready` said `healthy` through every database outage.

Now:

- Database down: readiness answers 200 with `database: {healthy: false,
  status: unhealthy}`, `degraded: ["database"]` and `status: degraded`; no
  error text or hostname is exposed. JWKS and discovery answer 200; a
  database-backed route answers its own error.
- Database healthy: readiness answers 200 `status: ready`, unchanged apart
  from the additive `database` block.
- A hanging database (or Redis) is reported unhealthy within the check's
  bound, so the probe still answers inside the kubelet's timeout.
- `/api/v1/health/detailed` reports the database `unhealthy` too.
- Liveness is unchanged.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
import pytest_asyncio

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.redis_circuit_breaker import ResilientRedisClient
from app.services.monitoring import HealthChecker, _is_healthy

pytestmark = pytest.mark.asyncio

READY = "/api/v1/health/ready"
# What a real driver error can carry; it must never reach the probe's body.
INTERNAL_DETAIL = "could not connect to db-internal.example.test:5432"


def _redis(connected: bool = True) -> ResilientRedisClient:
    server = fakeredis.FakeServer()
    client = ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    )
    server.connected = connected
    return client


def _checker() -> HealthChecker:
    """The checks main.py registers, with the real database check."""
    from app.main import _check_database_health, _check_redis_health
    from app.routers.v1.health import check_encryption_key_health

    checker = HealthChecker(AsyncMock())
    checker.register_check("database", _check_database_health, critical=True)
    checker.register_check("redis", _check_redis_health, critical=True)
    checker.register_check("encryption_key", check_encryption_key_health, critical=False)
    return checker


def _db_health(healthy: bool):
    """What `get_database_health()` returns: always a (truthy) dict."""
    if healthy:
        return AsyncMock(return_value={"healthy": True, "response_time_ms": 1.0})
    return AsyncMock(return_value={"healthy": False, "error": INTERNAL_DETAIL})


def _failing_db_session():
    """A request session whose database is unreachable."""
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=OperationalError("SELECT 1", {}, Exception(INTERNAL_DETAIL))
    )
    session.rollback = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    session.get = AsyncMock(side_effect=OperationalError("SELECT 1", {}, Exception("down")))
    return session


@pytest_asyncio.fixture
async def call():
    from app.core.database import get_db as core_get_db
    from app.database import get_db
    from app.main import app
    from app.routers.v1 import health as health_v1

    saved_checker = health_v1.health_checker

    async def _call(method, path, *, database_ok=True, redis=None, db_health=None, **kwargs):
        health_v1.health_checker = _checker()
        redis = redis or _redis()

        async def _db():
            yield _failing_db_session() if not database_ok else AsyncMock()

        saved = dict(app.dependency_overrides)
        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[core_get_db] = _db
        get = AsyncMock(return_value=redis)
        try:
            with (
                patch("app.core.redis.get_redis", get),
                patch("app.main.get_redis", get),
                patch("app.services.auth_service.get_redis", get),
                patch("app.main.get_database_health", db_health or _db_health(database_ok)),
            ):
                transport = ASGITransport(app=app, raise_app_exceptions=False)
                async with AsyncClient(transport=transport, base_url="http://test") as http:
                    return await http.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)

    yield _call
    health_v1.health_checker = saved_checker


class TestDatabaseDown:
    async def test_readiness_stays_200_and_reports_the_database_degraded(self, call):
        resp = await call("GET", READY, database_ok=False)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] == {"healthy": False, "status": "unhealthy"}
        assert body["degraded"] == ["database"]
        assert body["redis"] == "healthy"
        # Reported, never leaked: no driver error text or hostname.
        assert INTERNAL_DETAIL not in resp.text
        assert "db-internal" not in resp.text

    async def test_database_and_redis_down_both_report(self, call):
        resp = await call("GET", READY, database_ok=False, redis=_redis(connected=False))

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["degraded"] == ["database", "redis"]

    async def test_jwks_and_discovery_keep_answering(self, call):
        jwks = await call("GET", "/.well-known/jwks.json", database_ok=False)
        discovery = await call("GET", "/.well-known/openid-configuration", database_ok=False)
        assert jwks.status_code == 200
        assert discovery.status_code == 200
        assert "jwks_uri" in discovery.json()

    async def test_a_database_backed_route_answers_its_own_error(self, call):
        resp = await call(
            "POST",
            "/api/v1/auth/password/reset",
            database_ok=False,
            json={"token": "any-token", "new_password": "Any-Passw0rd!-placeholder"},
        )
        # The route fails on its own, with the app's database error envelope.
        assert resp.status_code == 503, resp.text
        assert resp.json()["error"]["code"] == "DATABASE_ERROR"
        assert INTERNAL_DETAIL not in resp.text

    async def test_detailed_health_reports_the_database_unhealthy(self, call):
        resp = await call("GET", "/api/v1/health/detailed", database_ok=False)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["database"]["status"] == "unhealthy"

    async def test_liveness_is_unchanged(self, call):
        assert (await call("GET", "/api/v1/health/live", database_ok=False)).status_code == 200
        assert (await call("GET", "/health", database_ok=False)).status_code == 200


class TestDatabaseHealthy:
    async def test_readiness_is_ready(self, call):
        resp = await call("GET", READY)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ready"
        assert body["database"] == {"healthy": True, "status": "healthy"}
        assert body["redis"] == "healthy"
        assert body["degraded"] == []


class TestChecksAreBounded:
    async def test_a_hanging_database_is_reported_unhealthy_in_time(self, call):
        async def hang():
            await asyncio.sleep(30)

        with patch("app.main.READINESS_CHECK_TIMEOUT_SECONDS", 0.05):
            resp = await asyncio.wait_for(
                call("GET", READY, db_health=AsyncMock(side_effect=hang)), timeout=5
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["database"] == {"healthy": False, "status": "unhealthy"}

    async def test_a_hanging_redis_is_reported_unhealthy_in_time(self, call):
        async def hang():
            await asyncio.sleep(30)

        redis = MagicMock()
        redis.strict_ping = AsyncMock(side_effect=hang)
        with patch("app.main.READINESS_CHECK_TIMEOUT_SECONDS", 0.05):
            resp = await asyncio.wait_for(call("GET", READY, redis=redis), timeout=5)

        assert resp.status_code == 200, resp.text
        assert resp.json()["redis"] == "unhealthy"


class TestHealthCheckerReadsDictResults:
    def test_a_dict_counts_only_when_it_says_healthy(self):
        assert _is_healthy({"healthy": True}) is True
        assert _is_healthy({"healthy": False, "error": "down"}) is False
        assert _is_healthy({"error": "no healthy key"}) is False
        assert _is_healthy({}) is False

    def test_bool_results_are_unchanged(self):
        assert _is_healthy(True) is True
        assert _is_healthy(False) is False

    async def test_the_raw_database_health_dict_is_reported_unhealthy(self):
        checker = HealthChecker(AsyncMock())
        checker.register_check("database", _db_health(False), critical=True)

        result = await checker.check_health()

        assert result["checks"]["database"]["status"] == "unhealthy"
        assert result["status"] == "unhealthy"


class TestDatabaseManagerRecovers:
    async def test_an_uninitialised_manager_retries_and_reports_healthy(self):
        from app.core.database_manager import DatabaseManager

        manager = DatabaseManager()
        try:
            health = await manager.health_check()
            assert health["healthy"] is True
        finally:
            await manager.close()

    async def test_a_failed_retry_reports_unhealthy_without_detail(self):
        from app.core.database_manager import DatabaseManager

        manager = DatabaseManager()
        with patch.object(
            DatabaseManager, "initialize", AsyncMock(side_effect=OSError(INTERNAL_DETAIL))
        ):
            health = await manager.health_check()
        assert health["healthy"] is False
        assert INTERNAL_DETAIL not in str(health)
