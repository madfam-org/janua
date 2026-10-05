"""
Health check endpoints for monitoring integration
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.redis import get_redis, get_redis_public_status
from app.core.redis_circuit_breaker import ResilientRedisClient

router = APIRouter(prefix="/health", tags=["health"])

# This will be injected from main.py
health_checker = None


def get_health_checker():
    """Dependency to get health checker instance"""
    if health_checker is None:
        raise HTTPException(status_code=503, detail="Health checker not initialized")
    return health_checker


async def check_encryption_key_health():
    """Health check: verify FIELD_ENCRYPTION_KEY is set in production (SOC 2 CF-09)."""
    from app.config import settings

    if settings.ENVIRONMENT == "production" and not settings.FIELD_ENCRYPTION_KEY:
        return False
    return True


async def check_kms_health() -> bool:
    """Health check: verify KMS/secrets provider is accessible (SOC 2 CF-06)."""
    from app.core.secrets_provider import get_secrets_provider

    provider = get_secrets_provider()
    return await provider.health_check()


@router.get("")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "janua-api",
        "version": "1.0.0",
    }


@router.get("/detailed")
async def detailed_health_check(checker=Depends(get_health_checker)) -> Dict[str, Any]:
    """Detailed health check with all registered checks"""
    result = await checker.check_health()

    # Add KMS health check
    from app.core.secrets_provider import get_secrets_provider

    provider = get_secrets_provider()
    kms_healthy = await provider.health_check()
    result.setdefault("checks", {})["kms"] = {
        "status": "healthy" if kms_healthy else "unhealthy",
        "provider": provider.provider_name,
    }
    # This replica's Redis breaker (each pod has its own).
    result["checks"]["redis_circuit"] = get_redis_public_status()

    return result


# Checks the readiness probe REPORTS but does not gate on.
#
# Redis (owner decision 2026-10-04: "make readiness independent of Redis"). Both
# API replicas share one Redis, so a Redis-wide outage used to fail readiness on
# every replica at once and empty the Service, taking JWKS and OIDC discovery
# (which never touch Redis) down with it, and with them sign-in for every
# relying party. The Redis-backed routes already answer 503 + Retry-After on
# their own while Redis is unreachable, so keeping the pods in the Service
# costs nothing there. The outage is still visible: it is reported in the body
# (`redis`, `redis_circuit`, `degraded`) and must be alerted on from there.
READINESS_REPORTED_ONLY = frozenset({"redis"})


@router.get("/ready")
async def readiness_check(checker=Depends(get_health_checker)) -> Dict[str, Any]:
    """Kubernetes readiness probe endpoint.

    Gates on every registered critical check EXCEPT those in
    `READINESS_REPORTED_ONLY` (Redis). Redis is still checked, by a strict
    PING through this replica's own client (see `_check_redis_health` in
    main.py), and reported:

    - `redis`: "healthy" / "unhealthy" / "error";
    - `redis_circuit`: this replica's breaker state (from #694);
    - `degraded`: the reported-only checks that are not healthy;
    - `status`: "ready", or "degraded" when `degraded` is non-empty.

    The HTTP status stays 200 while only reported-only checks fail.
    """
    result = await checker.check_health()
    checks: Dict[str, Any] = result.get("checks", {})

    gating_failures = [
        name
        for name, check in checks.items()
        if check.get("critical")
        and name not in READINESS_REPORTED_ONLY
        and check.get("status") != "healthy"
    ]
    if gating_failures:
        raise HTTPException(status_code=503, detail="Service not ready")

    degraded = sorted(
        name
        for name in READINESS_REPORTED_ONLY
        if name in checks and checks[name].get("status") != "healthy"
    )

    return {
        "status": "degraded" if degraded else "ready",
        "timestamp": result["timestamp"],
        "redis": checks.get("redis", {}).get("status", "not_registered"),
        "redis_circuit": get_redis_public_status(),
        "degraded": degraded,
    }


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/redis")
async def redis_health(redis_client: ResilientRedisClient = Depends(get_redis)) -> Dict[str, Any]:
    """
    Get Redis health status including circuit breaker state.

    Returns:
        - redis_available: Whether Redis is currently accessible
        - circuit_breaker: Circuit breaker metrics and state
        - degraded_mode: Whether system is running in degraded mode
    """
    return await redis_client.health_check()


@router.get("/circuit-breaker")
async def circuit_breaker_status(
    redis_client: ResilientRedisClient = Depends(get_redis),
) -> Dict[str, Any]:
    """
    Get detailed circuit breaker metrics.

    Useful for monitoring and alerting on Redis failures.
    """
    return redis_client.get_circuit_status()
