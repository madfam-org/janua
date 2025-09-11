"""
Exception classes for the Plinto SDK
"""

from typing import Optional, Dict, Any


class PlintoError(Exception):
    """Base exception for all Plinto SDK errors"""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}


class AuthenticationError(PlintoError):
    """Raised when authentication fails"""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: Optional[int] = 401,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code, response_data)


class ValidationError(PlintoError):
    """Raised when request validation fails"""
    
    def __init__(
        self,
        message: str = "Validation failed",
        status_code: Optional[int] = 400,
        response_data: Optional[Dict[str, Any]] = None,
        field_errors: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message, status_code, response_data)
        self.field_errors = field_errors or {}


class NotFoundError(PlintoError):
    """Raised when a resource is not found"""
    
    def __init__(
        self,
        message: str = "Resource not found",
        status_code: Optional[int] = 404,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code, response_data)


class PermissionError(PlintoError):
    """Raised when user lacks permission for an operation"""
    
    def __init__(
        self,
        message: str = "Permission denied",
        status_code: Optional[int] = 403,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code, response_data)


class RateLimitError(PlintoError):
    """Raised when rate limit is exceeded"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: Optional[int] = 429,
        response_data: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, status_code, response_data)
        self.retry_after = retry_after


class NetworkError(PlintoError):
    """Raised when network/connection errors occur"""
    
    def __init__(
        self,
        message: str = "Network error",
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.original_error = original_error


class ServerError(PlintoError):
    """Raised when server errors occur (5xx status codes)"""
    
    def __init__(
        self,
        message: str = "Server error",
        status_code: Optional[int] = 500,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code, response_data)


class ConfigurationError(PlintoError):
    """Raised when SDK configuration is invalid"""
    
    def __init__(
        self,
        message: str = "Configuration error",
    ):
        super().__init__(message)