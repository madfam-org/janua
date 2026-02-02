"""
Health check endpoints for monitoring integration
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.redis import get_redis
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
    return await checker.check_health()


@router.get("/ready")
async def readiness_check(checker=Depends(get_health_checker)) -> Dict[str, Any]:
    """Kubernetes readiness probe endpoint"""
    result = await checker.check_health()

    if result["status"] != "healthy":
        raise HTTPException(status_code=503, detail="Service not ready")

    return {"status": "ready", "timestamp": result["timestamp"]}


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
