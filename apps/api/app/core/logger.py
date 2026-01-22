"""
Structured logging configuration for Janua API
Replaces print() statements with structured JSON logging
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds timestamp and formats log records
    """

    def add_fields(
        self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Add log level
        log_record["level"] = record.levelname

        # Add module info
        log_record["module"] = record.module
        log_record["function"] = record.funcName

        # Add any extra fields
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        if hasattr(record, "organization_id"):
            log_record["organization_id"] = record.organization_id
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure structured logging for the application

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON format; otherwise use standard format
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        # JSON formatter for production
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(module)s %(funcName)s %(message)s"
        )
    else:
        # Standard formatter for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual information to all log records
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        # Add extra context to all log records
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Merge adapter's extra fields
        for key, value in self.extra.items():
            kwargs["extra"][key] = value

        return msg, kwargs


def get_context_logger(
    name: str,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> LoggerAdapter:
    """
    Get a logger with contextual information

    Args:
        name: Logger name
        user_id: User ID to include in logs
        organization_id: Organization ID to include in logs
        request_id: Request ID to include in logs

    Returns:
        Logger adapter with context
    """
    logger = get_logger(name)
    extra = {}

    if user_id:
        extra["user_id"] = user_id
    if organization_id:
        extra["organization_id"] = organization_id
    if request_id:
        extra["request_id"] = request_id

    return LoggerAdapter(logger, extra)


# Example usage:
# from app.core.logger import get_logger, get_context_logger
#
# # Basic usage
# logger = get_logger(__name__)
# logger.info("User authenticated successfully", extra={"user_id": user_id})
#
# # Context logger (automatically adds context to all logs)
# logger = get_context_logger(__name__, user_id=user.id, request_id=request_id)
# logger.info("Password reset initiated")  # Automatically includes user_id and request_id
