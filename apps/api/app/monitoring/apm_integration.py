"""
Production Monitoring and APM Integration
Integrates with DataDog, New Relic, AppDynamics, and Prometheus
"""

import time
import json
import asyncio
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import psutil
import redis.asyncio as aioredis

# Try importing APM agents (optional dependencies)
try:
    import ddtrace
    from ddtrace import tracer as dd_tracer

    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False

try:
    import newrelic.agent

    NEWRELIC_AVAILABLE = True
except ImportError:
    NEWRELIC_AVAILABLE = False

try:
    from appdynamics import agent as appd_agent

    APPDYNAMICS_AVAILABLE = True
except ImportError:
    APPDYNAMICS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

logger = logging.getLogger(__name__)


# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

http_requests_in_progress = Gauge("http_requests_in_progress", "HTTP requests in progress")

error_rate = Counter(
    "application_errors_total", "Total application errors", ["error_type", "endpoint"]
)

database_query_duration = Histogram(
    "database_query_duration_seconds", "Database query duration in seconds", ["query_type", "table"]
)

cache_hits = Counter("cache_hits_total", "Total cache hits", ["cache_type"])

cache_misses = Counter("cache_misses_total", "Total cache misses", ["cache_type"])

active_users = Gauge("active_users", "Number of active users")

authentication_attempts = Counter(
    "authentication_attempts_total", "Total authentication attempts", ["method", "status"]
)

mfa_verifications = Counter(
    "mfa_verifications_total", "Total MFA verifications", ["method", "status"]
)


class APMConfig:
    """Configuration for APM integrations"""

    def __init__(self):
        self.datadog_enabled = DATADOG_AVAILABLE and self._get_env_bool("DD_ENABLED", False)
        self.newrelic_enabled = NEWRELIC_AVAILABLE and self._get_env_bool(
            "NEW_RELIC_ENABLED", False
        )
        self.appd_enabled = APPDYNAMICS_AVAILABLE and self._get_env_bool("APPD_ENABLED", False)
        self.prometheus_enabled = self._get_env_bool("PROMETHEUS_ENABLED", True)
        self.opentelemetry_enabled = OPENTELEMETRY_AVAILABLE and self._get_env_bool(
            "OTEL_ENABLED", False
        )

        # DataDog configuration
        if self.datadog_enabled:
            ddtrace.config.env = self._get_env("DD_ENV", "production")
            ddtrace.config.service = self._get_env("DD_SERVICE", "janua-api")
            ddtrace.config.version = self._get_env("DD_VERSION", "1.0.0")

        # New Relic configuration
        if self.newrelic_enabled:
            newrelic.agent.initialize()

        # AppDynamics configuration
        if self.appd_enabled:
            appd_config = {
                "host": self._get_env("APPD_CONTROLLER_HOST"),
                "port": int(self._get_env("APPD_CONTROLLER_PORT", "443")),
                "ssl": self._get_env_bool("APPD_SSL", True),
                "account": self._get_env("APPD_ACCOUNT"),
                "access_key": self._get_env("APPD_ACCESS_KEY"),
                "app": self._get_env("APPD_APP_NAME", "Janua"),
                "tier": self._get_env("APPD_TIER_NAME", "API"),
                "node": self._get_env("APPD_NODE_NAME", "api-node-1"),
            }
            appd_agent.init(appd_config)

        # OpenTelemetry configuration
        if self.opentelemetry_enabled:
            resource = Resource.create({"service.name": "janua-api", "service.version": "1.0.0"})

            provider = TracerProvider(resource=resource)

            # Configure Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=self._get_env("JAEGER_HOST", "localhost"),
                agent_port=int(self._get_env("JAEGER_PORT", "6831")),
            )

            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

            trace.set_tracer_provider(provider)

    def _get_env(self, key: str, default: str = "") -> str:
        import os

        return os.getenv(key, default)

    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        import os

        return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


class ProductionMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive production monitoring middleware
    Integrates with multiple APM solutions and provides metrics
    """

    def __init__(self, app, config: Optional[APMConfig] = None):
        super().__init__(app)
        self.config = config or APMConfig()
        self.redis_client = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis for distributed metrics"""
        try:
            import os

            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                asyncio.create_task(self._connect_redis(redis_url))
        except Exception as e:
            logger.error(f"Failed to initialize Redis for monitoring: {e}")

    async def _connect_redis(self, redis_url: str):
        """Connect to Redis asynchronously"""
        try:
            self.redis_client = await aioredis.from_url(redis_url)
        except Exception as e:
            logger.error(f"Redis connection failed for monitoring: {e}")

    async def dispatch(self, request: Request, call_next):
        """Process request with comprehensive monitoring"""

        # Start timing
        start_time = time.time()

        # Increment in-progress gauge
        http_requests_in_progress.inc()

        # Initialize tracing context
        trace_id = self._generate_trace_id()
        request.state.trace_id = trace_id

        # DataDog tracing
        dd_span = None
        if self.config.datadog_enabled:
            dd_span = dd_tracer.trace(
                request.url.path,
                service="janua-api",
                resource=f"{request.method} {request.url.path}",
                span_type="web",
            )
            dd_span.set_tag("http.method", request.method)
            dd_span.set_tag("http.url", str(request.url))

        # New Relic transaction
        nr_transaction = None
        if self.config.newrelic_enabled:
            nr_transaction = newrelic.agent.current_transaction()
            if nr_transaction:
                newrelic.agent.set_transaction_name(f"{request.method} {request.url.path}")

        # OpenTelemetry span
        otel_span = None
        if self.config.opentelemetry_enabled:
            tracer = trace.get_tracer(__name__)
            otel_span = tracer.start_span(
                f"{request.method} {request.url.path}",
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.scheme": request.url.scheme,
                    "http.host": request.url.hostname,
                    "http.target": request.url.path,
                },
            )

        try:
            # Process request
            response = await call_next(request)

            # Record success metrics
            self._record_success_metrics(request, response, start_time, trace_id)

            # Update APM spans with response data
            if dd_span:
                dd_span.set_tag("http.status_code", response.status_code)

            if otel_span:
                otel_span.set_attribute("http.status_code", response.status_code)

            return response

        except Exception as e:
            # Record error metrics
            self._record_error_metrics(request, e, start_time, trace_id)

            # Update APM spans with error data
            if dd_span:
                dd_span.set_tag("error", True)
                dd_span.set_tag("error.message", str(e))
                dd_span.set_tag("error.stack", traceback.format_exc())

            if nr_transaction:
                newrelic.agent.notice_error()

            if otel_span:
                otel_span.record_exception(e)
                otel_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

            raise

        finally:
            # Cleanup
            http_requests_in_progress.dec()

            if dd_span:
                dd_span.finish()

            if otel_span:
                otel_span.end()

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID"""
        import uuid

        return str(uuid.uuid4())

    def _record_success_metrics(
        self, request: Request, response: Response, start_time: float, trace_id: str
    ):
        """Record success metrics to all monitoring systems"""

        duration = time.time() - start_time

        # Prometheus metrics
        http_requests_total.labels(
            method=request.method, endpoint=request.url.path, status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method, endpoint=request.url.path
        ).observe(duration)

        # Custom metrics for business logic
        if request.url.path.startswith("/api/v1/auth"):
            self._record_auth_metrics(request, response)

        # Log slow requests
        if duration > 1.0:  # Requests taking more than 1 second
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path} "
                f"took {duration:.2f}s (trace_id: {trace_id})"
            )

        # Send to Redis for distributed aggregation
        if self.redis_client:
            asyncio.create_task(
                self._send_to_redis(
                    "metrics:requests",
                    {
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration": duration,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            )

    def _record_error_metrics(
        self, request: Request, error: Exception, start_time: float, trace_id: str
    ):
        """Record error metrics to all monitoring systems"""

        duration = time.time() - start_time
        error_type = type(error).__name__

        # Prometheus metrics
        error_rate.labels(error_type=error_type, endpoint=request.url.path).inc()

        # Log error with context
        logger.error(
            f"Request failed: {request.method} {request.url.path} "
            f"error: {error_type}: {str(error)} (trace_id: {trace_id})",
            exc_info=True,
        )

        # Send to Redis for analysis
        if self.redis_client:
            asyncio.create_task(
                self._send_to_redis(
                    "metrics:errors",
                    {
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error_type": error_type,
                        "error_message": str(error),
                        "duration": duration,
                        "timestamp": datetime.utcnow().isoformat(),
                        "stack_trace": traceback.format_exc(),
                    },
                )
            )

    def _record_auth_metrics(self, request: Request, response: Response):
        """Record authentication-specific metrics"""

        if request.url.path == "/api/v1/auth/signin":
            status = "success" if response.status_code == 200 else "failure"
            authentication_attempts.labels(method="password", status=status).inc()

        elif request.url.path == "/api/v1/mfa/verify":
            status = "success" if response.status_code == 200 else "failure"
            mfa_verifications.labels(
                method="totp", status=status  # Could be extracted from request
            ).inc()

    async def _send_to_redis(self, key: str, data: Dict[str, Any]):
        """Send metrics to Redis for aggregation"""
        try:
            if self.redis_client:
                await self.redis_client.lpush(key, json.dumps(data))
                # Trim to keep only recent data
                await self.redis_client.ltrim(key, 0, 10000)
        except Exception as e:
            logger.error(f"Failed to send metrics to Redis: {e}")


class DatabaseMonitoring:
    """Database query monitoring"""

    @staticmethod
    def monitor_query(query_type: str, table: str):
        """Decorator to monitor database queries"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)

                    # Record successful query
                    duration = time.time() - start_time
                    database_query_duration.labels(query_type=query_type, table=table).observe(
                        duration
                    )

                    if duration > 0.5:  # Log slow queries
                        logger.warning(
                            f"Slow query detected: {query_type} on {table} " f"took {duration:.2f}s"
                        )

                    return result

                except Exception:
                    # Record failed query
                    error_rate.labels(
                        error_type="database_error", endpoint=f"{query_type}_{table}"
                    ).inc()
                    raise

            return wrapper

        return decorator


class CacheMonitoring:
    """Cache performance monitoring"""

    @staticmethod
    def monitor_cache(cache_type: str):
        """Decorator to monitor cache operations"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)

                # Determine if it was a hit or miss based on result
                if result is not None:
                    cache_hits.labels(cache_type=cache_type).inc()
                else:
                    cache_misses.labels(cache_type=cache_type).inc()

                return result

            return wrapper

        return decorator


class HealthMetrics:
    """System health metrics collector"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self._start_background_collection()

    def _start_background_collection(self):
        """Start background metrics collection"""
        asyncio.create_task(self._collect_metrics_loop())

    async def _collect_metrics_loop(self):
        """Continuously collect system metrics"""
        while True:
            try:
                await self._collect_system_metrics()
                await self._collect_application_metrics()
                await asyncio.sleep(30)  # Collect every 30 seconds
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _collect_system_metrics(self):
        """Collect system-level metrics"""

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()

        # Disk usage
        disk = psutil.disk_usage("/")

        # Network I/O
        network = psutil.net_io_counters()

        metrics = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "disk_percent": disk.percent,
            "network_bytes_sent": network.bytes_sent,
            "network_bytes_recv": network.bytes_recv,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Send to monitoring systems
        if self.redis_client:
            await self.redis_client.hset(
                "metrics:system", mapping={k: str(v) for k, v in metrics.items()}
            )

        # Send custom metrics to APM
        if DATADOG_AVAILABLE:
            from datadog import statsd

            statsd.gauge("system.cpu.percent", cpu_percent)
            statsd.gauge("system.memory.percent", memory.percent)
            statsd.gauge("system.disk.percent", disk.percent)

    async def _collect_application_metrics(self):
        """Collect application-level metrics"""

        if self.redis_client:
            # Get active user count
            active_users_count = await self.redis_client.scard("active_users")
            active_users.set(active_users_count or 0)

            # Get session count
            session_count = await self.redis_client.zcard("active_sessions")

            metrics = {
                "active_users": active_users_count or 0,
                "active_sessions": session_count or 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self.redis_client.hset(
                "metrics:application", mapping={k: str(v) for k, v in metrics.items()}
            )


class CustomMetrics:
    """Custom business metrics"""

    @staticmethod
    def track_business_event(event_name: str, properties: Dict[str, Any]):
        """Track custom business events"""

        # Send to DataDog
        if DATADOG_AVAILABLE:
            from datadog import statsd

            statsd.increment(
                f"business.{event_name}", tags=[f"{k}:{v}" for k, v in properties.items()]
            )

        # Send to New Relic
        if NEWRELIC_AVAILABLE:
            newrelic.agent.record_custom_event(event_name, properties)

        # Log for debugging
        logger.info(f"Business event: {event_name}", extra=properties)


def create_monitoring_middleware(app) -> ProductionMonitoringMiddleware:
    """Factory function to create monitoring middleware"""
    config = APMConfig()
    return ProductionMonitoringMiddleware(app, config)


async def get_prometheus_metrics():
    """Endpoint to expose Prometheus metrics"""
    return Response(content=generate_latest(), media_type="text/plain")
