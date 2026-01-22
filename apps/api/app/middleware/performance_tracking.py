"""
Performance Tracking Middleware

Tracks request latency, database query counts, and cache hit rates.
Integrates with Prometheus for metrics collection.
"""

import time
from typing import Callable
from uuid import uuid4

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger()


class PerformanceTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request performance metrics

    Metrics tracked:
    - Request latency (p50, p95, p99)
    - Database query count per request
    - Cache hit/miss rates
    - Error rates by endpoint
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.metrics_enabled = True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request performance"""

        # Generate request ID for tracking
        request_id = str(uuid4())[:8]
        request.state.request_id = request_id

        # Track start time
        start_time = time.time()

        # Initialize performance context
        request.state.perf = {
            "db_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "start_time": start_time,
        }

        # Structured logging context
        log_context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        }

        try:
            # Process request
            response = await call_next(request)

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Get performance metrics
            perf = request.state.perf
            db_queries = perf.get("db_queries", 0)
            cache_hits = perf.get("cache_hits", 0)
            cache_misses = perf.get("cache_misses", 0)

            # Calculate cache hit rate
            total_cache_ops = cache_hits + cache_misses
            hit_rate = (cache_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0

            # Log performance metrics
            logger.info(
                "request_completed",
                **log_context,
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
                db_queries=db_queries,
                cache_hit_rate=round(hit_rate, 1) if total_cache_ops > 0 else None,
            )

            # Add performance headers (helpful for debugging)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{latency_ms:.2f}ms"

            if self.metrics_enabled:
                response.headers["X-DB-Queries"] = str(db_queries)
                if total_cache_ops > 0:
                    response.headers["X-Cache-Hit-Rate"] = f"{hit_rate:.1f}%"

            # Record metrics for Prometheus (if available)
            await self._record_prometheus_metrics(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency=latency_ms,
                db_queries=db_queries,
                cache_hit_rate=hit_rate,
            )

            return response

        except Exception as e:
            # Log error with performance context
            latency_ms = (time.time() - start_time) * 1000

            logger.error(
                "request_failed",
                **log_context,
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=round(latency_ms, 2),
            )

            raise

    async def _record_prometheus_metrics(
        self,
        method: str,
        path: str,
        status_code: int,
        latency: float,
        db_queries: int,
        cache_hit_rate: float,
    ):
        """Record metrics to Prometheus (if available)"""
        try:
            from app.monitoring.metrics import (
                record_request_latency,
                record_db_queries,
                record_cache_hit_rate,
            )

            # Record latency histogram
            record_request_latency(method=method, path=path, status=status_code, latency=latency)

            # Record DB query count
            if db_queries > 0:
                record_db_queries(path=path, count=db_queries)

            # Record cache hit rate
            if cache_hit_rate > 0:
                record_cache_hit_rate(hit_rate=cache_hit_rate)

        except ImportError:
            # Prometheus not available, skip metrics
            pass
        except Exception as e:
            # Don't fail requests due to metrics errors
            logger.warning("Failed to record Prometheus metrics", error=str(e))


# Helper functions for tracking within request handlers


def increment_db_query_count(request: Request, count: int = 1):
    """Increment DB query counter for current request"""
    if hasattr(request.state, "perf"):
        request.state.perf["db_queries"] = request.state.perf.get("db_queries", 0) + count


def increment_cache_hit(request: Request):
    """Increment cache hit counter for current request"""
    if hasattr(request.state, "perf"):
        request.state.perf["cache_hits"] = request.state.perf.get("cache_hits", 0) + 1


def increment_cache_miss(request: Request):
    """Increment cache miss counter for current request"""
    if hasattr(request.state, "perf"):
        request.state.perf["cache_misses"] = request.state.perf.get("cache_misses", 0) + 1
