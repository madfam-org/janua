"""
Application Performance Monitoring (APM)
Comprehensive performance tracking, metrics collection, and distributed tracing
"""

import time
import asyncio
import uuid
import psutil
import structlog
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from contextlib import asynccontextmanager
import aioredis
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, generate_latest
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricReader

from app.config import settings

logger = structlog.get_logger()


class MetricType(Enum):
    """Types of metrics we can collect"""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"


class TraceLevel(Enum):
    """Trace detail levels"""
    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"
    DEBUG = "debug"


@dataclass
class PerformanceMetric:
    """Individual performance metric"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class TraceSpan:
    """Distributed trace span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "started"
    error: Optional[str] = None


@dataclass
class PerformanceProfile:
    """Performance profile for a request/operation"""
    request_id: str
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    database_calls: int = 0
    redis_calls: int = 0
    external_api_calls: int = 0
    error_count: int = 0
    traces: List[TraceSpan] = field(default_factory=list)
    custom_metrics: Dict[str, float] = field(default_factory=dict)


class APMCollector:
    """Core APM data collector and processor"""

    def __init__(self):
        self.registry = CollectorRegistry()
        self.redis_client: Optional[aioredis.Redis] = None
        self.active_traces: Dict[str, TraceSpan] = {}
        self.active_profiles: Dict[str, PerformanceProfile] = {}

        # Prometheus metrics
        self.request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )

        self.request_counter = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )

        self.database_operations = Histogram(
            'database_operation_duration_seconds',
            'Database operation duration',
            ['operation', 'table'],
            registry=self.registry
        )

        self.redis_operations = Histogram(
            'redis_operation_duration_seconds',
            'Redis operation duration',
            ['operation', 'key_pattern'],
            registry=self.registry
        )

        self.system_cpu_usage = Gauge(
            'system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=self.registry
        )

        self.system_memory_usage = Gauge(
            'system_memory_usage_percent',
            'System memory usage percentage',
            registry=self.registry
        )

        self.application_memory = Gauge(
            'application_memory_bytes',
            'Application memory usage in bytes',
            registry=self.registry
        )

        self.active_connections = Gauge(
            'active_database_connections',
            'Number of active database connections',
            registry=self.registry
        )

        self.error_rate = Counter(
            'application_errors_total',
            'Total application errors',
            ['error_type', 'component'],
            registry=self.registry
        )

        # Initialize OpenTelemetry
        self._setup_tracing()
        self._setup_metrics()

        # Start background tasks
        asyncio.create_task(self._system_metrics_collector())

    def _setup_tracing(self):
        """Initialize distributed tracing"""
        try:
            # Set up Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=getattr(settings, 'JAEGER_HOST', 'localhost'),
                agent_port=getattr(settings, 'JAEGER_PORT', 6831),
            )

            # Set up tracer provider
            trace.set_tracer_provider(TracerProvider())
            tracer = trace.get_tracer(__name__)

            # Add span processor
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)

            self.tracer = tracer
            logger.info("Distributed tracing initialized with Jaeger")

        except Exception as e:
            logger.warning("Failed to initialize Jaeger tracing", error=str(e))
            self.tracer = trace.get_tracer(__name__)

    def _setup_metrics(self):
        """Initialize metrics collection"""
        try:
            # Prometheus metrics reader
            prometheus_reader = PrometheusMetricReader()

            # Set up meter provider
            meter_provider = MeterProvider(metric_readers=[prometheus_reader])
            metrics.set_meter_provider(meter_provider)

            self.meter = metrics.get_meter(__name__)
            logger.info("Metrics collection initialized with Prometheus")

        except Exception as e:
            logger.warning("Failed to initialize metrics", error=str(e))

    async def initialize_redis(self):
        """Initialize Redis connection for APM data storage"""
        try:
            self.redis_client = aioredis.from_url(
                f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/2",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("APM Redis connection initialized")
        except Exception as e:
            logger.error("Failed to initialize APM Redis", error=str(e))

    async def _system_metrics_collector(self):
        """Background task to collect system metrics"""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.system_cpu_usage.set(cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                self.system_memory_usage.set(memory.percent)

                # Application memory
                process = psutil.Process()
                app_memory = process.memory_info().rss
                self.application_memory.set(app_memory)

                # Store in Redis for historical data
                if self.redis_client:
                    timestamp = int(time.time())
                    await self.redis_client.zadd(
                        "apm:system_metrics",
                        {
                            f"cpu:{timestamp}": cpu_percent,
                            f"memory:{timestamp}": memory.percent,
                            f"app_memory:{timestamp}": app_memory
                        }
                    )

                    # Keep only last 24 hours of data
                    cutoff = timestamp - (24 * 60 * 60)
                    await self.redis_client.zremrangebyscore("apm:system_metrics", 0, cutoff)

                await asyncio.sleep(30)  # Collect every 30 seconds

            except Exception as e:
                logger.error("System metrics collection error", error=str(e))
                await asyncio.sleep(60)

    def start_trace(self, operation_name: str, parent_span_id: Optional[str] = None) -> str:
        """Start a new trace span"""
        span_id = str(uuid.uuid4())
        trace_id = parent_span_id.split(':')[0] if parent_span_id else str(uuid.uuid4())

        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=datetime.now()
        )

        self.active_traces[span_id] = span
        return span_id

    def end_trace(self, span_id: str, status: str = "completed", error: Optional[str] = None):
        """End a trace span"""
        if span_id not in self.active_traces:
            return

        span = self.active_traces[span_id]
        span.end_time = datetime.now()
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status
        span.error = error

        # Store completed span
        asyncio.create_task(self._store_trace(span))
        del self.active_traces[span_id]

    def add_trace_tag(self, span_id: str, key: str, value: Any):
        """Add tag to active trace"""
        if span_id in self.active_traces:
            self.active_traces[span_id].tags[key] = value

    def add_trace_log(self, span_id: str, message: str, level: str = "info", **kwargs):
        """Add log entry to active trace"""
        if span_id in self.active_traces:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
                **kwargs
            }
            self.active_traces[span_id].logs.append(log_entry)

    async def _store_trace(self, span: TraceSpan):
        """Store completed trace span"""
        if not self.redis_client:
            return

        try:
            trace_data = {
                "span_id": span.span_id,
                "trace_id": span.trace_id,
                "parent_span_id": span.parent_span_id,
                "operation_name": span.operation_name,
                "start_time": span.start_time.isoformat(),
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "duration_ms": span.duration_ms,
                "tags": span.tags,
                "logs": span.logs,
                "status": span.status,
                "error": span.error
            }

            # Store individual span
            await self.redis_client.hset(
                f"apm:trace:{span.trace_id}:{span.span_id}",
                mapping=trace_data
            )

            # Add to trace index
            await self.redis_client.zadd(
                f"apm:trace_index:{span.trace_id}",
                {span.span_id: time.time()}
            )

            # Add to global trace list
            await self.redis_client.zadd(
                "apm:traces",
                {span.trace_id: time.time()}
            )

            # Set expiration (keep traces for 7 days)
            await self.redis_client.expire(f"apm:trace:{span.trace_id}:{span.span_id}", 604800)
            await self.redis_client.expire(f"apm:trace_index:{span.trace_id}", 604800)

        except Exception as e:
            logger.error("Failed to store trace", error=str(e), span_id=span.span_id)

    def start_performance_profile(self, request_id: str, operation: str) -> str:
        """Start performance profiling for a request"""
        profile = PerformanceProfile(
            request_id=request_id,
            operation=operation,
            start_time=datetime.now()
        )

        self.active_profiles[request_id] = profile
        return request_id

    def end_performance_profile(self, request_id: str):
        """End performance profiling"""
        if request_id not in self.active_profiles:
            return

        profile = self.active_profiles[request_id]
        profile.end_time = datetime.now()
        profile.duration_ms = (profile.end_time - profile.start_time).total_seconds() * 1000

        # Get final system metrics
        try:
            process = psutil.Process()
            profile.cpu_usage = psutil.cpu_percent()
            profile.memory_usage = process.memory_info().rss
        except:
            pass

        # Store completed profile
        asyncio.create_task(self._store_performance_profile(profile))
        del self.active_profiles[request_id]

    def increment_profile_counter(self, request_id: str, counter_type: str):
        """Increment a counter in the performance profile"""
        if request_id in self.active_profiles:
            profile = self.active_profiles[request_id]
            if counter_type == "database":
                profile.database_calls += 1
            elif counter_type == "redis":
                profile.redis_calls += 1
            elif counter_type == "external_api":
                profile.external_api_calls += 1
            elif counter_type == "error":
                profile.error_count += 1

    def add_custom_metric(self, request_id: str, metric_name: str, value: float):
        """Add custom metric to performance profile"""
        if request_id in self.active_profiles:
            self.active_profiles[request_id].custom_metrics[metric_name] = value

    async def _store_performance_profile(self, profile: PerformanceProfile):
        """Store completed performance profile"""
        if not self.redis_client:
            return

        try:
            profile_data = {
                "request_id": profile.request_id,
                "operation": profile.operation,
                "start_time": profile.start_time.isoformat(),
                "end_time": profile.end_time.isoformat() if profile.end_time else None,
                "duration_ms": profile.duration_ms,
                "cpu_usage": profile.cpu_usage,
                "memory_usage": profile.memory_usage,
                "database_calls": profile.database_calls,
                "redis_calls": profile.redis_calls,
                "external_api_calls": profile.external_api_calls,
                "error_count": profile.error_count,
                "custom_metrics": profile.custom_metrics
            }

            # Store profile
            await self.redis_client.hset(
                f"apm:profile:{profile.request_id}",
                mapping=profile_data
            )

            # Add to performance index
            await self.redis_client.zadd(
                f"apm:performance:{profile.operation}",
                {profile.request_id: profile.duration_ms or 0}
            )

            # Add to global performance list
            await self.redis_client.zadd(
                "apm:profiles",
                {profile.request_id: time.time()}
            )

            # Set expiration (keep profiles for 7 days)
            await self.redis_client.expire(f"apm:profile:{profile.request_id}", 604800)

        except Exception as e:
            logger.error("Failed to store performance profile", error=str(e), request_id=profile.request_id)

    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        self.request_counter.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        self.request_duration.labels(method=method, endpoint=endpoint, status_code=status_code).observe(duration)

    def record_database_operation(self, operation: str, table: str, duration: float):
        """Record database operation metrics"""
        self.database_operations.labels(operation=operation, table=table).observe(duration)

    def record_redis_operation(self, operation: str, key_pattern: str, duration: float):
        """Record Redis operation metrics"""
        self.redis_operations.labels(operation=operation, key_pattern=key_pattern).observe(duration)

    def record_error(self, error_type: str, component: str):
        """Record application error"""
        self.error_rate.labels(error_type=error_type, component=component).inc()

    def set_active_connections(self, count: int):
        """Set active database connections count"""
        self.active_connections.set(count)

    def get_metrics(self) -> str:
        """Get Prometheus metrics output"""
        return generate_latest(self.registry).decode('utf-8')

    async def get_performance_summary(self, operation: Optional[str] = None,
                                    hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        if not self.redis_client:
            return {}

        try:
            cutoff_time = time.time() - (hours * 3600)

            if operation:
                # Get performance data for specific operation
                profile_ids = await self.redis_client.zrangebyscore(
                    f"apm:performance:{operation}",
                    cutoff_time, "+inf",
                    withscores=True
                )
            else:
                # Get all recent profiles
                profile_ids = await self.redis_client.zrangebyscore(
                    "apm:profiles",
                    cutoff_time, "+inf"
                )

            if not profile_ids:
                return {"message": "No performance data available"}

            # Gather performance statistics
            total_requests = len(profile_ids)
            durations = []
            error_counts = []
            db_calls = []
            redis_calls = []

            for profile_id in profile_ids:
                if isinstance(profile_id, tuple):
                    profile_id = profile_id[0]

                profile_data = await self.redis_client.hgetall(f"apm:profile:{profile_id}")
                if profile_data:
                    if profile_data.get('duration_ms'):
                        durations.append(float(profile_data['duration_ms']))
                    if profile_data.get('error_count'):
                        error_counts.append(int(profile_data['error_count']))
                    if profile_data.get('database_calls'):
                        db_calls.append(int(profile_data['database_calls']))
                    if profile_data.get('redis_calls'):
                        redis_calls.append(int(profile_data['redis_calls']))

            summary = {
                "period_hours": hours,
                "operation": operation or "all",
                "total_requests": total_requests,
                "performance": {
                    "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                    "min_duration_ms": min(durations) if durations else 0,
                    "max_duration_ms": max(durations) if durations else 0,
                    "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
                    "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
                },
                "errors": {
                    "total_errors": sum(error_counts),
                    "error_rate": sum(error_counts) / total_requests if total_requests > 0 else 0,
                },
                "database": {
                    "avg_calls_per_request": sum(db_calls) / len(db_calls) if db_calls else 0,
                    "total_db_calls": sum(db_calls),
                },
                "redis": {
                    "avg_calls_per_request": sum(redis_calls) / len(redis_calls) if redis_calls else 0,
                    "total_redis_calls": sum(redis_calls),
                }
            }

            return summary

        except Exception as e:
            logger.error("Failed to generate performance summary", error=str(e))
            return {"error": "Failed to generate summary"}


# Global APM instance
apm_collector = APMCollector()


# Decorators for automatic instrumentation
def trace_async(operation_name: Optional[str] = None):
    """Decorator to automatically trace async functions"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            span_id = apm_collector.start_trace(span_name)

            try:
                apm_collector.add_trace_tag(span_id, "function", func.__name__)
                apm_collector.add_trace_tag(span_id, "module", func.__module__)

                result = await func(*args, **kwargs)
                apm_collector.end_trace(span_id, "completed")
                return result

            except Exception as e:
                apm_collector.end_trace(span_id, "error", str(e))
                apm_collector.record_error(type(e).__name__, func.__module__)
                raise

        return wrapper
    return decorator


def trace_sync(operation_name: Optional[str] = None):
    """Decorator to automatically trace sync functions"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            span_id = apm_collector.start_trace(span_name)

            try:
                apm_collector.add_trace_tag(span_id, "function", func.__name__)
                apm_collector.add_trace_tag(span_id, "module", func.__module__)

                result = func(*args, **kwargs)
                apm_collector.end_trace(span_id, "completed")
                return result

            except Exception as e:
                apm_collector.end_trace(span_id, "error", str(e))
                apm_collector.record_error(type(e).__name__, func.__module__)
                raise

        return wrapper
    return decorator


def profile_performance(operation: Optional[str] = None):
    """Decorator to automatically profile function performance"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())
            op_name = operation or f"{func.__module__}.{func.__name__}"
            apm_collector.start_performance_profile(request_id, op_name)

            try:
                result = await func(*args, **kwargs)
                apm_collector.end_performance_profile(request_id)
                return result

            except Exception as e:
                apm_collector.increment_profile_counter(request_id, "error")
                apm_collector.end_performance_profile(request_id)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())
            op_name = operation or f"{func.__module__}.{func.__name__}"
            apm_collector.start_performance_profile(request_id, op_name)

            try:
                result = func(*args, **kwargs)
                apm_collector.end_performance_profile(request_id)
                return result

            except Exception as e:
                apm_collector.increment_profile_counter(request_id, "error")
                apm_collector.end_performance_profile(request_id)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Context managers for manual instrumentation
@asynccontextmanager
async def trace_context(operation_name: str, parent_span_id: Optional[str] = None):
    """Context manager for manual tracing"""
    span_id = apm_collector.start_trace(operation_name, parent_span_id)
    try:
        yield span_id
        apm_collector.end_trace(span_id, "completed")
    except Exception as e:
        apm_collector.end_trace(span_id, "error", str(e))
        raise


@asynccontextmanager
async def performance_context(request_id: str, operation: str):
    """Context manager for manual performance profiling"""
    apm_collector.start_performance_profile(request_id, operation)
    try:
        yield request_id
        apm_collector.end_performance_profile(request_id)
    except Exception as e:
        apm_collector.increment_profile_counter(request_id, "error")
        apm_collector.end_performance_profile(request_id)
        raise


# Health check and monitoring functions
async def get_apm_health() -> Dict[str, Any]:
    """Get APM system health status"""
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "redis": "unknown",
            "metrics": "active",
            "tracing": "active"
        }
    }

    # Check Redis connectivity
    if apm_collector.redis_client:
        try:
            await apm_collector.redis_client.ping()
            health["components"]["redis"] = "healthy"
        except Exception as e:
            health["components"]["redis"] = f"unhealthy: {str(e)}"
            health["status"] = "degraded"
    else:
        health["components"]["redis"] = "not_configured"
        health["status"] = "degraded"

    # Check active traces and profiles
    health["active_traces"] = len(apm_collector.active_traces)
    health["active_profiles"] = len(apm_collector.active_profiles)

    return health


async def initialize_apm():
    """Initialize APM system"""
    await apm_collector.initialize_redis()
    logger.info("APM system initialized successfully")