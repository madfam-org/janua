"""
Structured Logging System
Comprehensive logging framework with structured output, correlation IDs, and centralized configuration
"""

import os
import sys
import json
import time
import uuid
import asyncio
import traceback
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from enum import Enum
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
import structlog
import logging
import logging.handlers
from pythonjsonlogger import jsonlogger
from opentelemetry import trace

from app.config import settings

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


class LogLevel(Enum):
    """Log levels with numeric values"""
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    TRACE = 5


class LogContext:
    """Thread-local log context for correlation IDs and request tracking"""

    _context = {}

    @classmethod
    def set(cls, key: str, value: Any):
        """Set context value"""
        cls._context[key] = value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get context value"""
        return cls._context.get(key, default)

    @classmethod
    def clear(cls):
        """Clear all context"""
        cls._context.clear()

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context as dict"""
        return cls._context.copy()


class StructuredLogger:
    """Enhanced structured logger with correlation tracking and performance monitoring"""

    def __init__(self, name: str = "plinto"):
        self.name = name
        self.logger = structlog.get_logger(name)
        self._setup_stdlib_logging()

        # Performance tracking
        self.request_start_times: Dict[str, float] = {}
        self.operation_counters: Dict[str, int] = {}

    def _setup_stdlib_logging(self):
        """Configure standard library logging integration"""

        # Create formatters
        json_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d'
        )

        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, getattr(settings, 'LOG_LEVEL', 'INFO')))

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter if getattr(settings, 'LOG_FORMAT', 'json') == 'console' else json_formatter)
        console_handler.setLevel(logging.INFO)

        # File handler (if configured)
        log_file = getattr(settings, 'LOG_FILE', None)
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(json_formatter)
            file_handler.setLevel(logging.DEBUG)
            root_logger.addHandler(file_handler)

        # Error file handler
        error_log_file = getattr(settings, 'ERROR_LOG_FILE', None)
        if error_log_file:
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=10
            )
            error_handler.setFormatter(json_formatter)
            error_handler.setLevel(logging.ERROR)
            root_logger.addHandler(error_handler)

        # Add console handler last
        root_logger.addHandler(console_handler)

        # Prevent duplicate logs
        root_logger.propagate = False

    def _get_base_context(self) -> Dict[str, Any]:
        """Get base logging context"""
        context = {
            "service": "plinto-api",
            "version": getattr(settings, 'VERSION', '1.0.0'),
            "environment": getattr(settings, 'ENVIRONMENT', 'development'),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add request context if available
        request_id = LogContext.get('request_id')
        if request_id:
            context["request_id"] = request_id

        user_id = LogContext.get('user_id')
        if user_id:
            context["user_id"] = user_id

        trace_id = LogContext.get('trace_id')
        if trace_id:
            context["trace_id"] = trace_id

        # Add OpenTelemetry trace context if available
        try:
            span = trace.get_current_span()
            if span and span.is_recording():
                span_context = span.get_span_context()
                context["otel_trace_id"] = format(span_context.trace_id, '032x')
                context["otel_span_id"] = format(span_context.span_id, '016x')
        except:
            pass

        # Add any additional context
        context.update(LogContext.get_all())

        return context

    def _log(self, level: str, message: str, **kwargs):
        """Internal logging method with context enrichment"""
        context = self._get_base_context()
        context.update(kwargs)

        # Add caller information for debugging
        if level.lower() in ['debug', 'trace']:
            frame = sys._getframe(2)
            context["caller"] = {
                "file": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "line": frame.f_lineno
            }

        getattr(self.logger, level.lower())(message, **context)

    def trace(self, message: str, **kwargs):
        """Trace level logging"""
        self._log("debug", f"TRACE: {message}", **kwargs)

    def debug(self, message: str, **kwargs):
        """Debug level logging"""
        self._log("debug", message, **kwargs)

    def info(self, message: str, **kwargs):
        """Info level logging"""
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Warning level logging"""
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Error level logging"""
        self._log("error", message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Critical level logging"""
        self._log("critical", message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        kwargs["exception"] = traceback.format_exc()
        self._log("error", message, **kwargs)

    def log_request_start(self, request_id: str, method: str, path: str, **kwargs):
        """Log HTTP request start"""
        self.request_start_times[request_id] = time.time()
        self.info(
            "HTTP request started",
            request_id=request_id,
            http_method=method,
            http_path=path,
            event_type="request_start",
            **kwargs
        )

    def log_request_end(self, request_id: str, status_code: int, **kwargs):
        """Log HTTP request completion"""
        start_time = self.request_start_times.pop(request_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        level = "error" if status_code >= 400 else "info"
        self._log(
            level,
            "HTTP request completed",
            request_id=request_id,
            http_status_code=status_code,
            duration_ms=duration_ms,
            event_type="request_end",
            **kwargs
        )

    def log_database_operation(self, operation: str, table: str, duration_ms: float, **kwargs):
        """Log database operation"""
        self.info(
            "Database operation",
            db_operation=operation,
            db_table=table,
            duration_ms=duration_ms,
            event_type="database_operation",
            **kwargs
        )

    def log_external_api_call(self, service: str, endpoint: str, duration_ms: float, status_code: Optional[int] = None, **kwargs):
        """Log external API call"""
        level = "error" if status_code and status_code >= 400 else "info"
        self._log(
            level,
            "External API call",
            external_service=service,
            external_endpoint=endpoint,
            duration_ms=duration_ms,
            status_code=status_code,
            event_type="external_api_call",
            **kwargs
        )

    def log_security_event(self, event_type: str, severity: str, **kwargs):
        """Log security-related events"""
        level = "critical" if severity == "high" else "warning" if severity == "medium" else "info"
        self._log(
            level,
            f"Security event: {event_type}",
            security_event_type=event_type,
            security_severity=severity,
            event_type="security_event",
            **kwargs
        )

    def log_performance_metric(self, metric_name: str, value: float, unit: str = "ms", **kwargs):
        """Log performance metrics"""
        self.info(
            "Performance metric",
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            event_type="performance_metric",
            **kwargs
        )

    def log_business_event(self, event_name: str, **kwargs):
        """Log business logic events"""
        self.info(
            f"Business event: {event_name}",
            business_event=event_name,
            event_type="business_event",
            **kwargs
        )

    def log_authentication(self, action: str, user_id: Optional[str] = None, success: bool = True, **kwargs):
        """Log authentication events"""
        level = "info" if success else "warning"
        self._log(
            level,
            f"Authentication {action}",
            auth_action=action,
            auth_success=success,
            user_id=user_id,
            event_type="authentication",
            **kwargs
        )

    def log_authorization(self, action: str, resource: str, user_id: str, allowed: bool, **kwargs):
        """Log authorization events"""
        level = "info" if allowed else "warning"
        self._log(
            level,
            f"Authorization {action}",
            authz_action=action,
            authz_resource=resource,
            authz_allowed=allowed,
            user_id=user_id,
            event_type="authorization",
            **kwargs
        )

    def increment_operation_counter(self, operation: str):
        """Increment operation counter"""
        self.operation_counters[operation] = self.operation_counters.get(operation, 0) + 1

    def get_operation_counts(self) -> Dict[str, int]:
        """Get operation counts"""
        return self.operation_counters.copy()

    def reset_operation_counts(self):
        """Reset operation counts"""
        self.operation_counters.clear()


# Global logger instance
structured_logger = StructuredLogger()


# Decorators for automatic logging
def log_function_call(
    operation_name: Optional[str] = None,
    log_args: bool = False,
    log_result: bool = False,
    level: str = "debug"
):
    """Decorator to automatically log function calls"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            log_data = {"operation": op_name}
            if log_args:
                log_data["args"] = str(args)[:200] if args else None
                log_data["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}

            structured_logger._log(level, f"Function call started: {op_name}", **log_data)
            structured_logger.increment_operation_counter(op_name)

            try:
                result = await func(*args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000
                log_data["duration_ms"] = duration_ms
                log_data["status"] = "success"

                if log_result and result is not None:
                    log_data["result"] = str(result)[:200]

                structured_logger._log(level, f"Function call completed: {op_name}", **log_data)
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_data["duration_ms"] = duration_ms
                log_data["status"] = "error"
                log_data["error"] = str(e)

                structured_logger.error(f"Function call failed: {op_name}", **log_data)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            log_data = {"operation": op_name}
            if log_args:
                log_data["args"] = str(args)[:200] if args else None
                log_data["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}

            structured_logger._log(level, f"Function call started: {op_name}", **log_data)
            structured_logger.increment_operation_counter(op_name)

            try:
                result = func(*args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000
                log_data["duration_ms"] = duration_ms
                log_data["status"] = "success"

                if log_result and result is not None:
                    log_data["result"] = str(result)[:200]

                structured_logger._log(level, f"Function call completed: {op_name}", **log_data)
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_data["duration_ms"] = duration_ms
                log_data["status"] = "error"
                log_data["error"] = str(e)

                structured_logger.error(f"Function call failed: {op_name}", **log_data)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def log_database_operation(operation: str, table: str):
    """Decorator to log database operations"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_database_operation(operation, table, duration_ms, status="success")
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_database_operation(operation, table, duration_ms, status="error", error=str(e))
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_database_operation(operation, table, duration_ms, status="success")
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_database_operation(operation, table, duration_ms, status="error", error=str(e))
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# Context managers
@contextmanager
def log_context(**kwargs):
    """Context manager to set logging context"""
    original_context = LogContext.get_all()

    try:
        for key, value in kwargs.items():
            LogContext.set(key, value)
        yield
    finally:
        LogContext.clear()
        for key, value in original_context.items():
            LogContext.set(key, value)


@asynccontextmanager
async def async_log_context(**kwargs):
    """Async context manager to set logging context"""
    original_context = LogContext.get_all()

    try:
        for key, value in kwargs.items():
            LogContext.set(key, value)
        yield
    finally:
        LogContext.clear()
        for key, value in original_context.items():
            LogContext.set(key, value)


@contextmanager
def request_logging_context(request_id: str, user_id: Optional[str] = None, trace_id: Optional[str] = None):
    """Context manager for request-scoped logging"""
    original_context = LogContext.get_all()

    try:
        LogContext.set('request_id', request_id)
        if user_id:
            LogContext.set('user_id', user_id)
        if trace_id:
            LogContext.set('trace_id', trace_id)
        yield
    finally:
        LogContext.clear()
        for key, value in original_context.items():
            LogContext.set(key, value)


# Utility functions
def generate_correlation_id() -> str:
    """Generate a unique correlation ID"""
    return str(uuid.uuid4())


def get_logger(name: str = "plinto") -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[str] = None,
    error_log_file: Optional[str] = None
):
    """Configure global logging settings"""
    # Update environment variables to affect logger configuration
    os.environ['LOG_LEVEL'] = level
    os.environ['LOG_FORMAT'] = format_type
    if log_file:
        os.environ['LOG_FILE'] = log_file
    if error_log_file:
        os.environ['ERROR_LOG_FILE'] = error_log_file

    # Recreate logger with new configuration
    global structured_logger
    structured_logger = StructuredLogger()


# Export commonly used functions
__all__ = [
    'structured_logger',
    'get_logger',
    'log_function_call',
    'log_database_operation',
    'log_context',
    'async_log_context',
    'request_logging_context',
    'generate_correlation_id',
    'configure_logging',
    'LogContext',
    'LogLevel'
]