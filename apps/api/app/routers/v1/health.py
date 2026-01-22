"""
Health check endpoints for monitoring integration
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime

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


@router.get("/metrics")
async def system_metrics(
    redis_client: ResilientRedisClient = Depends(get_redis), checker=Depends(get_health_checker)
) -> Dict[str, Any]:
    """
    Get combined system health metrics for dashboard display.

    Returns latency metrics for API, database, and Redis,
    plus cache hit rate statistics.
    """
    import time

    # Measure API response time (self-measurement)
    api_start = time.perf_counter()

    # Get health check results with timing
    health_result = await checker.check_health()

    api_latency_ms = (time.perf_counter() - api_start) * 1000

    # Get Redis stats
    redis_stats = redis_client.get_circuit_status()

    # Calculate cache hit rate
    total_cache_ops = redis_stats.get("cache_hits", 0) + redis_stats.get("cache_misses", 0)
    cache_hit_rate = 0
    if total_cache_ops > 0:
        cache_hit_rate = round((redis_stats.get("cache_hits", 0) / total_cache_ops) * 100, 1)
    else:
        # If no cache operations yet, use successful_calls ratio as proxy
        total_calls = redis_stats.get("total_calls", 0)
        successful_calls = redis_stats.get("successful_calls", 0)
        if total_calls > 0:
            cache_hit_rate = round((successful_calls / total_calls) * 100, 1)

    # Extract latencies from health checks
    db_latency = health_result.get("checks", {}).get("database", {}).get("duration_ms", 0)
    redis_latency = health_result.get("checks", {}).get("redis", {}).get("duration_ms", 0)

    return {
        "status": health_result.get("status", "unknown"),
        "timestamp": health_result.get("timestamp"),
        "metrics": {
            "api_response_time_ms": round(api_latency_ms, 1),
            "database_latency_ms": round(db_latency, 1),
            "redis_latency_ms": round(redis_latency, 1),
            "cache_hit_rate_percent": cache_hit_rate,
        },
        "redis_stats": {
            "circuit_state": redis_stats.get("state", "unknown"),
            "total_calls": redis_stats.get("total_calls", 0),
            "successful_calls": redis_stats.get("successful_calls", 0),
            "failed_calls": redis_stats.get("failed_calls", 0),
        },
    }
