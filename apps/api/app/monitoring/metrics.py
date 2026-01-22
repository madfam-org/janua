"""
Prometheus Metrics Collection

Provides Prometheus-compatible metrics for performance monitoring:
- Request latency histograms
- Database query counters
- Cache hit rate gauges
- Error rate counters
"""

from typing import Optional
import structlog

logger = structlog.get_logger()

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available, metrics disabled")


# Initialize metrics if Prometheus is available
if PROMETHEUS_AVAILABLE:
    # Request latency histogram
    request_latency = Histogram(
        "janua_request_latency_milliseconds",
        "Request latency in milliseconds",
        labelnames=["method", "path", "status"],
        buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
    )

    # Database query counter
    db_queries_total = Counter(
        "janua_db_queries_total", "Total database queries executed", labelnames=["path"]
    )

    # Cache hit rate gauge
    cache_hit_rate_gauge = Gauge("janua_cache_hit_rate_percent", "Cache hit rate percentage")

    # Request counter
    requests_total = Counter(
        "janua_requests_total", "Total HTTP requests", labelnames=["method", "path", "status"]
    )

    # Error counter
    errors_total = Counter("janua_errors_total", "Total errors", labelnames=["error_type", "path"])

    # Active sessions gauge
    active_sessions = Gauge("janua_active_sessions", "Number of active user sessions")

    # Auth operation latency
    auth_operation_latency = Histogram(
        "janua_auth_operation_milliseconds",
        "Authentication operation latency",
        labelnames=["operation"],
        buckets=(5, 10, 25, 50, 100, 250, 500, 1000),
    )


def record_request_latency(method: str, path: str, status: int, latency: float):
    """Record request latency to Prometheus"""
    if not PROMETHEUS_AVAILABLE:
        return

    try:
        request_latency.labels(method=method, path=path, status=status).observe(latency)
        requests_total.labels(method=method, path=path, status=status).inc()
    except Exception as e:
        logger.warning("Failed to record request latency", error=str(e))


def record_db_queries(path: str, count: int):
    """Record database query count"""
    if not PROMETHEUS_AVAILABLE:
        return

    try:
        db_queries_total.labels(path=path).inc(count)
    except Exception as e:
        logger.warning("Failed to record DB queries", error=str(e))


def record_cache_hit_rate(hit_rate: float):
    """Record cache hit rate"""
    if not PROMETHEUS_AVAILABLE:
        return

    try:
        cache_hit_rate_gauge.set(hit_rate)
    except Exception as e:
        logger.warning("Failed to record cache hit rate", error=str(e))


def record_error(error_type: str, path: str):
    """Record error occurrence"""
    if not PROMETHEUS_AVAILABLE:
        return

    try:
        errors_total.labels(error_type=error_type, path=path).inc()
    except Exception as e:
        logger.warning("Failed to record error", error=str(e))


def record_active_sessions(count: int):
    """Update active sessions count"""
    if not PROMETHEUS_AVAILABLE:
        return

    try:
        active_sessions.set(count)
    except Exception as e:
        logger.warning("Failed to record active sessions", error=str(e))


def record_auth_operation(operation: str, latency_ms: float):
    """Record authentication operation latency"""
    if not PROMETHEUS_AVAILABLE:
        return

    try:
        auth_operation_latency.labels(operation=operation).observe(latency_ms)
    except Exception as e:
        logger.warning("Failed to record auth operation", error=str(e))


def get_metrics() -> Optional[bytes]:
    """Get current metrics in Prometheus format"""
    if not PROMETHEUS_AVAILABLE:
        return None

    try:
        return generate_latest()
    except Exception as e:
        logger.error("Failed to generate metrics", error=str(e))
        return None


def get_content_type() -> str:
    """Get Prometheus content type"""
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"
    return CONTENT_TYPE_LATEST
