"""
Prometheus Metrics Collection

Provides Prometheus-compatible metrics for performance monitoring:
- Request latency histograms
- Database query counters
- Cache hit rate gauges
- Error rate counters
"""

from typing import Any, Mapping, Optional

import structlog

logger = structlog.get_logger()

# Try to import Prometheus client
try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

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


_KNOWN_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
UNMATCHED_ROUTE = "<unmatched>"


def _is_param_segment(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def route_label(scope: Mapping[str, Any]) -> str:
    """Bounded ``path`` label for a request: the matched route as a template.

    Raw URL paths carry ids, tokens and whatever scanners probe, so they
    would give every distinct URL its own series. Only requests that matched
    a route (``scope["route"]`` is set) are labelled by path; the rest share
    one label.

    The label is the full template (``/api/v1/users/{user_id}``). Depending
    on the FastAPI version, ``scope["route"].path`` either is that full
    template or omits the ``include_router`` prefix (``/users/{user_id}``).
    So the route template is aligned with the tail of the request path, and
    the leading segments it does not cover are the include prefix, taken
    from the request path with any prefix path parameters put back as
    ``{name}``. Whenever the alignment does not hold, the route's own
    template is returned, which is still bounded.
    """
    route = scope.get("route")
    if route is None:
        return UNMATCHED_ROUTE
    template = getattr(route, "path", None)
    # "" is an included router's root route: the prefix is the whole path.
    if not isinstance(template, str) or not (template == "" or template.startswith("/")):
        return UNMATCHED_ROUTE
    fallback = template or UNMATCHED_ROUTE

    path = scope.get("path")
    if not isinstance(path, str) or not path.startswith("/") or ":path}" in template:
        return fallback

    path_segments = path.split("/")
    template_segments = template.split("/")[1:]
    prefix_len = len(path_segments) - len(template_segments)
    if prefix_len < 1:
        return fallback
    for template_segment, path_segment in zip(template_segments, path_segments[prefix_len:]):
        if not _is_param_segment(template_segment) and template_segment != path_segment:
            return fallback

    prefix = path_segments[:prefix_len]
    template_params = {
        seg[1:-1].split(":", 1)[0] for seg in template_segments if _is_param_segment(seg)
    }
    params = scope.get("path_params") or {}
    # Path parameters the template does not hold come from the include
    # prefix; restore their names, right to left.
    for name, value in reversed(list(params.items())):
        if name in template_params:
            continue
        text = str(value)
        for i in range(len(prefix) - 1, 0, -1):
            if prefix[i] == text:
                prefix[i] = "{" + str(name) + "}"
                break
        else:
            return fallback
    return "/".join(prefix + template_segments)


def method_label(method: str) -> str:
    """Bounded ``method`` label: standard methods as-is, anything else OTHER."""
    upper = (method or "").upper()
    return upper if upper in _KNOWN_METHODS else "OTHER"


def record_http_request(
    scope: Mapping[str, Any], method: str, status: int, latency_ms: float
) -> None:
    """Record one served request with bounded labels (route template, method)."""
    record_request_latency(
        method=method_label(method), path=route_label(scope), status=status, latency=latency_ms
    )


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
