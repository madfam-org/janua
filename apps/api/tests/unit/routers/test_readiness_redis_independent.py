"""Readiness does not depend on Redis (J2-012).

Owner decision (2026-10-04): "yes, make readiness independent of Redis".

The readiness probe (`GET /api/v1/health/ready`, see
k8s/base/deployments/janua-api.yaml) used to answer 503 whenever this replica
could not PING Redis. Both replicas share one Redis, so a Redis-wide outage
emptied the Service within about 30 s and took JWKS and OIDC discovery down
with it, breaking sign-in for every relying party.

Now:

- Redis down: readiness answers 200, `status: degraded`, `redis: unhealthy`,
  `degraded: ["redis"]` and the breaker state; JWKS and discovery answer 200;
  a Redis-backed route answers 503 + Retry-After.
- Redis healthy: readiness answers 200 `status: ready` exactly as before (the
  new fields are additive).
- Every other critical check still gates readiness as before.
- Liveness is unchanged.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis
import pytest
import pytest_asyncio

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient

from app.core.redis_circuit_breaker import ResilientRedisClient
from app.services.auth_service import AuthService
from app.services.monitoring import HealthChecker

pytestmark = pytest.mark.asyncio

READY = "/api/v1/health/ready"


def _redis(connected: bool = True) -> ResilientRedisClient:
    server = fakeredis.FakeServer()
    client = ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    )
    server.connected = connected
    return client


def _checker(database_ok: bool = True) -> HealthChecker:
    """The checks main.py registers, with the database stubbed."""
    from app.main import _check_redis_health
    from app.routers.v1.health import check_encryption_key_health

    checker = HealthChecker(AsyncMock())

    async def database():
        return database_ok

    checker.register_check("database", database, critical=True)
    checker.register_check("redis", _check_redis_health, critical=True)
    checker.register_check("encryption_key", check_encryption_key_health, critical=False)
    return checker


@pytest_asyncio.fixture
async def call():
    from app.database import get_db
    from app.main import app
    from app.routers.v1 import health as health_v1

    saved_checker = health_v1.health_checker

    async def _no_db():
        yield AsyncMock()

    async def _call(method, path, *, redis, checker=None, uninitialised=False, **kwargs):
        health_v1.health_checker = None if uninitialised else (checker or _checker())
        app.dependency_overrides[get_db] = _no_db
        get = AsyncMock(return_value=redis)
        try:
            with (
                patch("app.core.redis.get_redis", get),
                patch("app.main.get_redis", get),
                patch("app.services.auth_service.get_redis", get),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as http:
                    return await http.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(get_db, None)

    yield _call
    health_v1.health_checker = saved_checker


class TestRedisDown:
    async def test_readiness_stays_200_and_reports_redis_degraded(self, call):
        resp = await call("GET", READY, redis=_redis(connected=False))

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["redis"] == "unhealthy"
        assert body["degraded"] == ["redis"]
        assert "state" in body["redis_circuit"]

    async def test_jwks_and_discovery_keep_answering(self, call):
        redis = _redis(connected=False)
        jwks = await call("GET", "/.well-known/jwks.json", redis=redis)
        discovery = await call("GET", "/.well-known/openid-configuration", redis=redis)
        assert jwks.status_code == 200
        assert discovery.status_code == 200
        assert "jwks_uri" in discovery.json()

    async def test_a_redis_backed_route_answers_503(self, call):
        token, _, _, _ = AuthService.create_refresh_token(
            user_id=str(uuid4()), tenant_id=str(uuid4())
        )
        resp = await call(
            "POST",
            "/api/v1/auth/refresh",
            redis=_redis(connected=False),
            json={"refresh_token": token},
        )
        assert resp.status_code == 503
        assert resp.headers["retry-after"].isdigit()

    async def test_liveness_is_unchanged(self, call):
        redis = _redis(connected=False)
        assert (await call("GET", "/api/v1/health/live", redis=redis)).status_code == 200
        assert (await call("GET", "/health", redis=redis)).status_code == 200


class TestRedisHealthy:
    async def test_readiness_is_ready(self, call):
        resp = await call("GET", READY, redis=_redis())

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ready"
        assert body["redis"] == "healthy"
        assert body["degraded"] == []
        assert "timestamp" in body and "redis_circuit" in body


class TestOtherDependenciesStillGate:
    async def test_a_failing_critical_check_not_reported_only_is_still_503(self, call):
        # The database is reported-only too since J3-001 (see
        # test_readiness_database_reported.py); any other critical check gates.
        async def failing():
            return False

        for redis in (_redis(), _redis(connected=False)):
            checker = _checker()
            checker.register_check("some_critical_dependency", failing, critical=True)
            resp = await call("GET", READY, redis=redis, checker=checker)
            assert resp.status_code == 503

    async def test_an_uninitialised_health_checker_is_503(self, call):
        # The one gating failure left today (runbook: "keep alerting on a 503
        # from readiness"), whether or not Redis answers.
        for redis in (_redis(), _redis(connected=False)):
            resp = await call("GET", READY, redis=redis, uninitialised=True)
            assert resp.status_code == 503

    async def test_a_non_critical_check_does_not_gate(self, call):
        checker = _checker()

        async def failing():
            return False

        checker.register_check("encryption_key", failing, critical=False)
        resp = await call("GET", READY, redis=_redis(), checker=checker)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
