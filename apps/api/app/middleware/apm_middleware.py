"""
APM Middleware for FastAPI
Automatic request tracing, performance monitoring, and metrics collection
"""

import time
import uuid
import asyncio
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

from app.monitoring.apm import apm_collector
from app.core.models import RequestContext

logger = structlog.get_logger()


class APMMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for automatic APM instrumentation"""

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list] = None,
        trace_level: str = "standard",
        enable_profiling: bool = True,
        enable_tracing: bool = True
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]
        self.trace_level = trace_level
        self.enable_profiling = enable_profiling
        self.enable_tracing = enable_tracing

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process each HTTP request with APM instrumentation"""

        # Skip monitoring for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract request information
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "unknown")
        client_ip = self._get_client_ip(request)

        start_time = time.time()

        # Start performance profiling
        if self.enable_profiling:
            apm_collector.start_performance_profile(request_id, f"{method} {path}")

        # Start distributed tracing
        trace_id = None
        if self.enable_tracing:
            # Check for existing trace context
            parent_trace = request.headers.get("x-trace-id")
            trace_id = apm_collector.start_trace(f"HTTP {method} {path}", parent_trace)

            # Add trace context to request
            apm_collector.add_trace_tag(trace_id, "http.method", method)
            apm_collector.add_trace_tag(trace_id, "http.path", path)
            apm_collector.add_trace_tag(trace_id, "http.user_agent", user_agent)
            apm_collector.add_trace_tag(trace_id, "client.ip", client_ip)
            apm_collector.add_trace_tag(trace_id, "request.id", request_id)

        # Store context in request state
        request.state.apm_context = {
            "request_id": request_id,
            "trace_id": trace_id,
            "start_time": start_time
        }

        response = None
        status_code = 500
        error_occurred = False

        try:
            # Process the request
            response = await call_next(request)
            status_code = response.status_code

            # Check if this is an error response
            if status_code >= 400:
                error_occurred = True
                if self.enable_profiling:
                    apm_collector.increment_profile_counter(request_id, "error")

                if self.enable_tracing and trace_id:
                    apm_collector.add_trace_tag(trace_id, "error", True)
                    apm_collector.add_trace_tag(trace_id, "http.status_code", status_code)

        except Exception as e:
            # Handle unhandled exceptions
            error_occurred = True
            status_code = 500

            logger.error("Unhandled exception in request",
                        request_id=request_id,
                        error=str(e),
                        path=path,
                        method=method)

            if self.enable_profiling:
                apm_collector.increment_profile_counter(request_id, "error")

            if self.enable_tracing and trace_id:
                apm_collector.add_trace_tag(trace_id, "error", True)
                apm_collector.add_trace_tag(trace_id, "error.message", str(e))
                apm_collector.add_trace_log(trace_id, f"Exception: {str(e)}", "error")

            # Record error in metrics
            apm_collector.record_error(type(e).__name__, "http_middleware")

            # Return error response
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id}
            )

        finally:
            # Calculate request duration
            end_time = time.time()
            duration = end_time - start_time

            # Record HTTP request metrics
            apm_collector.record_http_request(method, path, status_code, duration)

            # End performance profiling
            if self.enable_profiling:
                apm_collector.end_performance_profile(request_id)

            # End distributed tracing
            if self.enable_tracing and trace_id:
                apm_collector.add_trace_tag(trace_id, "http.status_code", status_code)
                apm_collector.add_trace_tag(trace_id, "duration_ms", duration * 1000)

                trace_status = "error" if error_occurred else "completed"
                apm_collector.end_trace(trace_id, trace_status)

            # Add response headers
            if response:
                response.headers["X-Request-ID"] = request_id
                if trace_id:
                    response.headers["X-Trace-ID"] = trace_id
                response.headers["X-Response-Time"] = f"{duration:.3f}s"

            # Log request completion
            log_level = "warning" if error_occurred else "info"
            logger.log(
                log_level,
                "HTTP request completed",
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration * 1000,
                client_ip=client_ip,
                user_agent=user_agent
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first (load balancer/proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check for real IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct client
        if request.client:
            return request.client.host

        return "unknown"


class DatabaseAPMMiddleware:
    """Middleware for database operation monitoring"""

    @staticmethod
    async def monitor_database_operation(operation: str, table: str, query: str):
        """Monitor database operation performance"""
        start_time = time.time()

        # Get current request context if available
        request_id = getattr(RequestContext.get(), 'request_id', None)

        try:
            # Increment database call counter in active profile
            if request_id:
                apm_collector.increment_profile_counter(request_id, "database")

            # The actual database operation would happen here
            # This is a wrapper/decorator function
            yield

        finally:
            # Record operation timing
            duration = time.time() - start_time
            apm_collector.record_database_operation(operation, table, duration)


class RedisAPMMiddleware:
    """Middleware for Redis operation monitoring"""

    @staticmethod
    async def monitor_redis_operation(operation: str, key_pattern: str):
        """Monitor Redis operation performance"""
        start_time = time.time()

        # Get current request context if available
        request_id = getattr(RequestContext.get(), 'request_id', None)

        try:
            # Increment Redis call counter in active profile
            if request_id:
                apm_collector.increment_profile_counter(request_id, "redis")

            # The actual Redis operation would happen here
            yield

        finally:
            # Record operation timing
            duration = time.time() - start_time
            apm_collector.record_redis_operation(operation, key_pattern, duration)


# Decorator for automatic database operation monitoring
def monitor_db_operation(operation: str, table: str):
    """Decorator to monitor database operations"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    # Get current request context
                    request_id = getattr(RequestContext.get(), 'request_id', None)
                    if request_id:
                        apm_collector.increment_profile_counter(request_id, "database")

                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    apm_collector.record_database_operation(operation, table, duration)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    # Get current request context
                    request_id = getattr(RequestContext.get(), 'request_id', None)
                    if request_id:
                        apm_collector.increment_profile_counter(request_id, "database")

                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    apm_collector.record_database_operation(operation, table, duration)
            return sync_wrapper
    return decorator


# Decorator for automatic Redis operation monitoring
def monitor_redis_operation(operation: str, key_pattern: str = "unknown"):
    """Decorator to monitor Redis operations"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    # Get current request context
                    request_id = getattr(RequestContext.get(), 'request_id', None)
                    if request_id:
                        apm_collector.increment_profile_counter(request_id, "redis")

                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    apm_collector.record_redis_operation(operation, key_pattern, duration)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    # Get current request context
                    request_id = getattr(RequestContext.get(), 'request_id', None)
                    if request_id:
                        apm_collector.increment_profile_counter(request_id, "redis")

                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    apm_collector.record_redis_operation(operation, key_pattern, duration)
            return sync_wrapper
    return decorator


# Decorator for external API call monitoring
def monitor_external_api(service_name: str):
    """Decorator to monitor external API calls"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    # Get current request context
                    request_id = getattr(RequestContext.get(), 'request_id', None)
                    if request_id:
                        apm_collector.increment_profile_counter(request_id, "external_api")

                    result = await func(*args, **kwargs)
                    return result
                except Exception:
                    # Record external API error
                    apm_collector.record_error("external_api_error", service_name)
                    raise
                finally:
                    duration = time.time() - start_time
                    # You could add specific external API metrics here
                    logger.info("External API call",
                              service=service_name,
                              duration_ms=duration * 1000)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    # Get current request context
                    request_id = getattr(RequestContext.get(), 'request_id', None)
                    if request_id:
                        apm_collector.increment_profile_counter(request_id, "external_api")

                    result = func(*args, **kwargs)
                    return result
                except Exception:
                    # Record external API error
                    apm_collector.record_error("external_api_error", service_name)
                    raise
                finally:
                    duration = time.time() - start_time
                    logger.info("External API call",
                              service=service_name,
                              duration_ms=duration * 1000)
            return sync_wrapper
    return decorator