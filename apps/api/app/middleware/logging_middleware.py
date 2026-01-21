"""
Logging Middleware for FastAPI
Automatic request/response logging with correlation IDs and structured output
"""

import time
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

from app.logging.structured_logger import (
    structured_logger,
    request_logging_context,
    generate_correlation_id
)

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for comprehensive request/response logging"""

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list] = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 1000,
        sensitive_headers: Optional[list] = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico", "/docs", "/openapi.json"]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.sensitive_headers = sensitive_headers or [
            'authorization', 'cookie', 'x-api-key', 'x-auth-token'
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process each HTTP request with comprehensive logging"""

        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Generate correlation ID
        correlation_id = request.headers.get("x-correlation-id") or generate_correlation_id()
        request.state.correlation_id = correlation_id

        # Extract request information
        start_time = time.time()
        request_size = int(request.headers.get("content-length", 0))

        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")

        # Extract user context if available (from auth middleware)
        user_id = getattr(request.state, 'user_id', None)
        session_id = getattr(request.state, 'session_id', None)

        # Set up logging context
        with request_logging_context(
            request_id=correlation_id,
            user_id=user_id,
            trace_id=request.headers.get("x-trace-id")
        ):
            # Log request start
            await self._log_request_start(
                request=request,
                correlation_id=correlation_id,
                client_ip=client_ip,
                user_agent=user_agent,
                request_size=request_size,
                user_id=user_id,
                session_id=session_id
            )

            response = None
            status_code = 500
            error_details = None

            try:
                # Process the request
                response = await call_next(request)
                status_code = response.status_code

            except Exception as e:
                # Handle unhandled exceptions
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "error_traceback": None  # Don't log full traceback in middleware
                }

                structured_logger.exception(
                    "Unhandled exception in request processing",
                    correlation_id=correlation_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    request_path=request.url.path,
                    request_method=request.method
                )

                # Return error response
                response = JSONResponse(
                    status_code=500,
                    content={
                        "detail": "Internal server error",
                        "correlation_id": correlation_id,
                        "timestamp": time.time()
                    }
                )
                status_code = 500

            finally:
                # Calculate request metrics
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                response_size = int(response.headers.get("content-length", 0)) if response else 0

                # Add response headers
                if response:
                    response.headers["X-Correlation-ID"] = correlation_id
                    response.headers["X-Response-Time"] = f"{duration_ms:.3f}ms"

                # Log request completion
                await self._log_request_completion(
                    request=request,
                    response=response,
                    correlation_id=correlation_id,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_size=request_size,
                    response_size=response_size,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    user_id=user_id,
                    session_id=session_id,
                    error_details=error_details
                )

        return response

    async def _log_request_start(
        self,
        request: Request,
        correlation_id: str,
        client_ip: str,
        user_agent: str,
        request_size: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Log request start with detailed information"""

        # Extract and sanitize headers
        headers = self._sanitize_headers(dict(request.headers))

        # Extract query parameters
        query_params = dict(request.query_params) if request.query_params else {}

        # Request body (if enabled and size is reasonable)
        request_body = None
        if self.log_request_body and request_size > 0 and request_size <= self.max_body_size:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = body_bytes.decode('utf-8')[:self.max_body_size]
            except Exception as e:
                structured_logger.warning(
                    "Failed to read request body for logging",
                    correlation_id=correlation_id,
                    error=str(e)
                )

        # Log the request
        structured_logger.log_request_start(
            request_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=user_agent,
            headers=headers,
            query_params=query_params,
            request_size=request_size,
            request_body=request_body,
            user_id=user_id,
            session_id=session_id,
            url=str(request.url),
            scheme=request.url.scheme,
            host=request.url.hostname,
            port=request.url.port
        )

    async def _log_request_completion(
        self,
        request: Request,
        response: Optional[Response],
        correlation_id: str,
        status_code: int,
        duration_ms: float,
        request_size: int,
        response_size: int,
        client_ip: str,
        user_agent: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """Log request completion with metrics and response details"""

        # Response headers (sanitized)
        response_headers = {}
        if response:
            response_headers = self._sanitize_headers(dict(response.headers))

        # Response body (if enabled and appropriate)
        response_body = None
        if (self.log_response_body and response and
            response_size > 0 and response_size <= self.max_body_size):
            try:
                # Note: This would require custom response handling to capture body
                # For now, we'll skip response body logging to avoid complexity
                pass
            except Exception as e:
                structured_logger.warning(
                    "Failed to read response body for logging",
                    correlation_id=correlation_id,
                    error=str(e)
                )

        # Determine log level based on status code
        if status_code >= 500:
            log_level = "error"
        elif status_code >= 400:
            log_level = "warning"
        else:
            log_level = "info"

        # Performance classification
        performance_tier = self._classify_performance(duration_ms)

        # Log request completion
        log_data = {
            "request_id": correlation_id,
            "http_status_code": status_code,
            "duration_ms": duration_ms,
            "request_size": request_size,
            "response_size": response_size,
            "performance_tier": performance_tier,
            "response_headers": response_headers,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "user_id": user_id,
            "session_id": session_id,
            "http_method": request.method,
            "http_path": request.url.path
        }

        if error_details:
            log_data.update(error_details)

        if response_body:
            log_data["response_body"] = response_body

        structured_logger._log(log_level, "HTTP request completed", **log_data)

        # Log specific events based on status code
        if status_code >= 400:
            structured_logger.log_security_event(
                event_type="http_error_response",
                severity="medium" if status_code < 500 else "high",
                status_code=status_code,
                path=request.url.path,
                client_ip=client_ip,
                user_id=user_id
            )

        # Log performance metrics
        if duration_ms > 1000:  # Slow requests
            structured_logger.log_performance_metric(
                metric_name="slow_request",
                value=duration_ms,
                unit="ms",
                path=request.url.path,
                method=request.method
            )

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

        # Check for CloudFlare header
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip

        # Fallback to direct client
        if request.client:
            return request.client.host

        return "unknown"

    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Remove sensitive information from headers"""
        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.sensitive_headers):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized

    def _classify_performance(self, duration_ms: float) -> str:
        """Classify request performance tier"""
        if duration_ms < 100:
            return "fast"
        elif duration_ms < 500:
            return "normal"
        elif duration_ms < 1000:
            return "slow"
        else:
            return "very_slow"


class DatabaseLoggingMixin:
    """Mixin to add database operation logging to database classes"""

    @staticmethod
    def log_query(operation: str, table: str, query: str, duration_ms: float,
                  rows_affected: Optional[int] = None, error: Optional[str] = None):
        """Log database query execution"""
        log_data = {
            "db_operation": operation,
            "db_table": table,
            "db_query": query[:500] if query else None,  # Truncate long queries
            "duration_ms": duration_ms,
            "rows_affected": rows_affected
        }

        if error:
            log_data["db_error"] = error
            structured_logger.error("Database operation failed", **log_data)
        else:
            structured_logger.debug("Database operation completed", **log_data)

        # Log performance metrics for slow queries
        if duration_ms > 100:
            structured_logger.log_performance_metric(
                metric_name="slow_database_query",
                value=duration_ms,
                unit="ms",
                operation=operation,
                table=table
            )


class SecurityLoggingMixin:
    """Mixin to add security event logging"""

    @staticmethod
    def log_authentication_attempt(user_identifier: str, success: bool,
                                 method: str = "password", ip_address: str = "unknown",
                                 user_agent: str = "unknown", failure_reason: Optional[str] = None):
        """Log authentication attempts"""
        structured_logger.log_authentication(
            action="login_attempt",
            user_id=user_identifier if success else None,
            success=success,
            auth_method=method,
            client_ip=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason
        )

        if not success:
            structured_logger.log_security_event(
                event_type="authentication_failure",
                severity="medium",
                user_identifier=user_identifier,
                auth_method=method,
                client_ip=ip_address,
                failure_reason=failure_reason
            )

    @staticmethod
    def log_authorization_check(user_id: str, resource: str, action: str,
                              allowed: bool, reason: Optional[str] = None):
        """Log authorization checks"""
        structured_logger.log_authorization(
            action=action,
            resource=resource,
            user_id=user_id,
            allowed=allowed,
            reason=reason
        )

        if not allowed:
            structured_logger.log_security_event(
                event_type="authorization_denied",
                severity="medium",
                user_id=user_id,
                resource=resource,
                action=action,
                reason=reason
            )

    @staticmethod
    def log_suspicious_activity(event_type: str, severity: str, description: str,
                              user_id: Optional[str] = None, ip_address: str = "unknown",
                              **additional_data):
        """Log suspicious activities"""
        structured_logger.log_security_event(
            event_type=event_type,
            severity=severity,
            description=description,
            user_id=user_id,
            client_ip=ip_address,
            **additional_data
        )


# Helper functions for specific logging scenarios
def log_api_key_usage(api_key_id: str, endpoint: str, user_id: Optional[str] = None,
                     rate_limited: bool = False):
    """Log API key usage"""
    structured_logger.info(
        "API key usage",
        api_key_id=api_key_id,
        endpoint=endpoint,
        user_id=user_id,
        rate_limited=rate_limited,
        event_type="api_key_usage"
    )

def log_data_export(user_id: str, data_type: str, record_count: int,
                   export_format: str = "json"):
    """Log data export activities"""
    structured_logger.info(
        "Data export",
        user_id=user_id,
        data_type=data_type,
        record_count=record_count,
        export_format=export_format,
        event_type="data_export"
    )

def log_configuration_change(user_id: str, config_key: str, old_value: Any,
                           new_value: Any, component: str = "system"):
    """Log configuration changes"""
    structured_logger.info(
        "Configuration change",
        user_id=user_id,
        config_key=config_key,
        old_value=str(old_value)[:100],
        new_value=str(new_value)[:100],
        component=component,
        event_type="configuration_change"
    )

def log_feature_flag_usage(user_id: Optional[str], flag_name: str, flag_value: bool,
                         context: Optional[Dict[str, Any]] = None):
    """Log feature flag usage"""
    structured_logger.debug(
        "Feature flag evaluation",
        user_id=user_id,
        flag_name=flag_name,
        flag_value=flag_value,
        context=context,
        event_type="feature_flag_usage"
    )