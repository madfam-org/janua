"""
Structured logging configuration for Janua
"""

import logging
import sys
import structlog
from typing import Any, Dict, Optional

from app.config import settings


def configure_logging():
    """Configure structured logging for the application"""

    # Configure standard library logging
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Configure structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.ENVIRONMENT == "development":
        # Pretty printing for development
        shared_processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON for production
        shared_processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize logging configuration
configure_logging()

# Create logger instance
logger = structlog.get_logger(__name__)


class AuditLogger:
    """Specialized logger for audit events"""

    def __init__(self):
        self.logger = structlog.get_logger("audit")

    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Log an audit event"""
        self.logger.info(
            "audit_event",
            event_type=event_type,
            user_id=user_id,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            **kwargs,
        )


class SecurityLogger:
    """Specialized logger for security events"""

    def __init__(self):
        self.logger = structlog.get_logger("security")

    def log_security_event(
        self,
        event_type: str,
        severity: str = "medium",
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Log a security event"""
        self.logger.warning(
            "security_event",
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            **kwargs,
        )


class PerformanceLogger:
    """Specialized logger for performance metrics"""

    def __init__(self):
        self.logger = structlog.get_logger("performance")

    def log_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "ms",
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Log a performance metric"""
        self.logger.info(
            "performance_metric",
            metric=metric_name,
            value=value,
            unit=unit,
            context=context or {},
            **kwargs,
        )


# Export logger instances
audit_logger = AuditLogger()
security_logger = SecurityLogger()
performance_logger = PerformanceLogger()
