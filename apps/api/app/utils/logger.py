"""
Structured logging utility for production-safe logging.

Replaces print() statements with proper logging that can be controlled
by environment and severity level.
"""

import logging
import sys
from typing import Any
from app.config import settings

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class ProductionLogger:
    """
    Production-safe logger that respects environment settings.
    
    In production, only INFO and above are logged.
    In development, all levels are logged.
    """
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
        self.is_debug = settings.DEBUG
        self.environment = settings.ENVIRONMENT
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message (development only)"""
        if self.is_debug:
            self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, exc_info: bool = True, **kwargs: Any) -> None:
        """Log error message with optional exception info"""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
    
    def critical(self, message: str, exc_info: bool = True, **kwargs: Any) -> None:
        """Log critical message"""
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)


# Convenience function for quick logger creation
def create_logger(name: str = __name__) -> ProductionLogger:
    """
    Create a production-safe logger instance.
    
    Usage:
        from app.utils.logger import create_logger
        logger = create_logger(__name__)
        logger.debug("Debug message")
        logger.info("Info message")
    
    Args:
        name: Logger name
        
    Returns:
        ProductionLogger instance
    """
    return ProductionLogger(name)
