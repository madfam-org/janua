"""
SDK error handling classes that translate to platform-specific error types.

These error classes provide consistent error handling across all SDK platforms
while maintaining platform-specific idioms and conventions.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from abc import ABC


class SDKError(Exception, ABC):
    """
    Base SDK error class.

    All platform SDKs will inherit from their platform's equivalent:
    - Python: Exception
    - TypeScript: Error
    - Go: error interface
    - Java: Exception
    - Swift: Error protocol
    - Kotlin: Exception
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.request_id = request_id
        self.timestamp = timestamp or datetime.utcnow()
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code='{self.error_code}', "
            f"request_id='{self.request_id}'"
            f")"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
        }


class APIError(SDKError):
    """
    API-level errors from the Janua service.

    Represents errors returned by the API with HTTP status codes.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
        response_body: Optional[str] = None,
    ):
        super().__init__(message, error_code, request_id, timestamp, details)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        return f"[{self.status_code}] [{self.error_code}] {self.message}"

    @classmethod
    def from_api_response(cls, response: Dict[str, Any], status_code: int) -> "APIError":
        """Create an APIError from an API error response."""
        error_data = response.get("error", {})
        return cls(
            message=error_data.get("message", "Unknown API error"),
            status_code=status_code,
            error_code=error_data.get("code"),
            request_id=error_data.get("request_id"),
            timestamp=datetime.fromisoformat(error_data["timestamp"])
            if error_data.get("timestamp")
            else None,
            details=error_data.get("details"),
            response_body=str(response),
        )


class ValidationError(APIError):
    """
    Validation errors for request data.

    Contains field-level validation errors for detailed error reporting.
    """

    def __init__(
        self,
        message: str,
        validation_errors: List[Dict[str, Any]],
        status_code: int = 400,
        error_code: str = "VALIDATION_ERROR",
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            request_id=request_id,
            timestamp=timestamp,
            details={"validation_errors": validation_errors},
        )
        self.validation_errors = validation_errors

    def get_field_errors(self, field_name: str) -> List[Dict[str, Any]]:
        """Get validation errors for a specific field."""
        return [error for error in self.validation_errors if error.get("field") == field_name]

    def has_field_error(self, field_name: str) -> bool:
        """Check if a specific field has validation errors."""
        return len(self.get_field_errors(field_name)) > 0

    @classmethod
    def from_api_response(cls, response: Dict[str, Any], status_code: int) -> "ValidationError":
        """Create a ValidationError from an API validation error response."""
        error_data = response.get("error", {})
        validation_errors = error_data.get("details", {}).get("validation_errors", [])

        return cls(
            message=error_data.get("message", "Validation failed"),
            validation_errors=validation_errors,
            status_code=status_code,
            error_code=error_data.get("code", "VALIDATION_ERROR"),
            request_id=error_data.get("request_id"),
            timestamp=datetime.fromisoformat(error_data["timestamp"])
            if error_data.get("timestamp")
            else None,
        )


class AuthenticationError(APIError):
    """
    Authentication-related errors.

    Includes issues with tokens, credentials, and authentication flows.
    """

    def __init__(
        self,
        message: str,
        auth_type: Optional[str] = None,
        error_code: str = "AUTHENTICATION_ERROR",
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
            request_id=request_id,
            timestamp=timestamp,
            details=details,
        )
        self.auth_type = auth_type

    def is_token_expired(self) -> bool:
        """Check if the error is due to an expired token."""
        return self.error_code in ["TOKEN_EXPIRED", "ACCESS_TOKEN_EXPIRED"]

    def requires_reauthentication(self) -> bool:
        """Check if the error requires complete reauthentication."""
        return self.error_code in [
            "INVALID_CREDENTIALS",
            "REFRESH_TOKEN_EXPIRED",
            "TOKEN_REVOKED",
            "ACCOUNT_SUSPENDED",
        ]


class AuthorizationError(APIError):
    """
    Authorization/permission errors.

    User is authenticated but lacks permission for the requested resource.
    """

    def __init__(
        self,
        message: str,
        required_permission: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        error_code: str = "AUTHORIZATION_ERROR",
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            status_code=403,
            error_code=error_code,
            request_id=request_id,
            timestamp=timestamp,
            details=details,
        )
        self.required_permission = required_permission
        self.resource_type = resource_type
        self.resource_id = resource_id


class RateLimitError(APIError):
    """
    Rate limiting errors.

    Includes information about when to retry the request.
    """

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        reset_time: Optional[datetime] = None,
        error_code: str = "RATE_LIMIT_EXCEEDED",
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        details = {}
        if limit is not None:
            details["limit"] = limit
        if remaining is not None:
            details["remaining"] = remaining
        if reset_time:
            details["reset_time"] = reset_time.isoformat()

        super().__init__(
            message=message,
            status_code=429,
            error_code=error_code,
            request_id=request_id,
            timestamp=timestamp,
            details=details,
        )
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time

    def get_retry_delay(self) -> int:
        """Get the recommended retry delay in seconds."""
        if self.retry_after:
            return self.retry_after
        if self.reset_time:
            return max(0, int((self.reset_time - datetime.utcnow()).total_seconds()))
        return 60  # Default fallback


class ServerError(APIError):
    """
    Server-side errors (5xx status codes).

    Represents internal server errors, maintenance mode, etc.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "SERVER_ERROR",
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
        is_retryable: bool = True,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            request_id=request_id,
            timestamp=timestamp,
            details=details,
        )
        self.is_retryable = is_retryable

    def is_maintenance_mode(self) -> bool:
        """Check if the error is due to maintenance mode."""
        return self.error_code == "MAINTENANCE_MODE" or self.status_code == 503


class NetworkError(SDKError):
    """
    Network-level errors.

    Connection issues, timeouts, DNS resolution failures, etc.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "NETWORK_ERROR",
        original_error: Optional[Exception] = None,
        is_timeout: bool = False,
        is_connection_error: bool = False,
    ):
        super().__init__(message=message, error_code=error_code)
        self.original_error = original_error
        self.is_timeout = is_timeout
        self.is_connection_error = is_connection_error

    def __str__(self) -> str:
        if self.original_error:
            return f"{self.message}: {str(self.original_error)}"
        return self.message


class ConfigurationError(SDKError):
    """
    SDK configuration errors.

    Invalid API keys, missing configuration, invalid URLs, etc.
    """

    def __init__(
        self,
        message: str,
        config_field: Optional[str] = None,
        error_code: str = "CONFIGURATION_ERROR",
    ):
        super().__init__(message=message, error_code=error_code)
        self.config_field = config_field


# Error factory functions for creating errors from API responses
def create_error_from_response(
    response_data: Dict[str, Any], status_code: int, response_body: Optional[str] = None
) -> APIError:
    """
    Create the appropriate error type from an API error response.

    This function analyzes the error response and creates the most specific
    error type available.
    """
    error_data = response_data.get("error", {})
    error_code = error_data.get("code", "UNKNOWN_ERROR")
    message = error_data.get("message", "Unknown error occurred")

    # Create specific error types based on status code and error code
    if status_code == 400 and error_code == "VALIDATION_ERROR":
        return ValidationError.from_api_response(response_data, status_code)

    elif status_code == 401:
        return AuthenticationError(
            message=message,
            error_code=error_code,
            request_id=error_data.get("request_id"),
            timestamp=datetime.fromisoformat(error_data["timestamp"])
            if error_data.get("timestamp")
            else None,
            details=error_data.get("details"),
        )

    elif status_code == 403:
        details = error_data.get("details", {})
        return AuthorizationError(
            message=message,
            required_permission=details.get("required_permission"),
            resource_type=details.get("resource_type"),
            resource_id=details.get("resource_id"),
            error_code=error_code,
            request_id=error_data.get("request_id"),
            timestamp=datetime.fromisoformat(error_data["timestamp"])
            if error_data.get("timestamp")
            else None,
        )

    elif status_code == 429:
        details = error_data.get("details", {})
        retry_after = error_data.get("retry_after")
        reset_time = None
        if details.get("reset_time"):
            reset_time = datetime.fromisoformat(details["reset_time"])

        return RateLimitError(
            message=message,
            retry_after=retry_after,
            limit=details.get("limit"),
            remaining=details.get("remaining"),
            reset_time=reset_time,
            error_code=error_code,
            request_id=error_data.get("request_id"),
            timestamp=datetime.fromisoformat(error_data["timestamp"])
            if error_data.get("timestamp")
            else None,
        )

    elif status_code >= 500:
        return ServerError(
            message=message,
            status_code=status_code,
            error_code=error_code,
            request_id=error_data.get("request_id"),
            timestamp=datetime.fromisoformat(error_data["timestamp"])
            if error_data.get("timestamp")
            else None,
            details=error_data.get("details"),
            is_retryable=status_code in [500, 502, 503, 504],
        )

    else:
        # Generic API error for unspecified error types
        return APIError.from_api_response(response_data, status_code)


# Platform-specific error mapping hints for SDK generation
ERROR_TYPE_MAPPING = {
    # Maps Python error types to platform-specific equivalents
    "python": {
        "SDKError": "Exception",
        "APIError": "requests.HTTPError",
        "NetworkError": "requests.ConnectionError",
        "ValidationError": "ValueError",
    },
    "typescript": {
        "SDKError": "Error",
        "APIError": "APIError extends Error",
        "NetworkError": "NetworkError extends Error",
        "ValidationError": "ValidationError extends Error",
    },
    "go": {
        "SDKError": "error",
        "APIError": "APIError struct implementing error",
        "NetworkError": "NetworkError struct implementing error",
        "ValidationError": "ValidationError struct implementing error",
    },
    "java": {
        "SDKError": "Exception",
        "APIError": "APIException extends Exception",
        "NetworkError": "NetworkException extends Exception",
        "ValidationError": "ValidationException extends Exception",
    },
    "swift": {
        "SDKError": "Error protocol",
        "APIError": "APIError: Error",
        "NetworkError": "NetworkError: Error",
        "ValidationError": "ValidationError: Error",
    },
    "kotlin": {
        "SDKError": "Exception",
        "APIError": "APIException : Exception",
        "NetworkError": "NetworkException : Exception",
        "ValidationError": "ValidationException : Exception",
    },
}
