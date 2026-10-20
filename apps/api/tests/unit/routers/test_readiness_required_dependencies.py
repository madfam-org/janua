"""Staging can require healthy registered DB/Redis without changing prod readiness."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers.v1.health import get_health_checker, router


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("database", "redis", "required_status"),
    [
        ("healthy", "healthy", 200),
        ("unhealthy", "healthy", 503),
        ("healthy", "error", 503),
        ("unhealthy", "unhealthy", 503),
        (None, "healthy", 503),
        ("healthy", None, 503),
        (None, None, 503),
    ],
)
async def test_required_dependencies_reject_missing_or_unhealthy_checks(
    database, redis, required_status
):
    checks = {
        name: {"critical": True, "status": status, "error": "private-driver-detail"}
        for name, status in {"database": database, "redis": redis}.items()
        if status is not None
    }
    checker = AsyncMock()
    checker.check_health.return_value = {"checks": checks, "timestamp": "test"}
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_health_checker] = lambda: checker
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        default = await client.get("/api/v1/health/ready")
        required = await client.get("/api/v1/health/ready?require_dependencies=true")

    assert default.status_code == 200  # Preserve production's availability decision.
    assert required.status_code == required_status
    assert "private-driver-detail" not in required.text
    if required_status == 200:
        assert required.json()["status"] == "ready"
        assert required.json()["degraded"] == []
    else:
        assert required.json() == {"detail": "Service not ready"}
