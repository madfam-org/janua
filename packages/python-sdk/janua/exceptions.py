"""
Exception classes for the Janua Python SDK.

This module defines all custom exceptions that can be raised by the SDK,
providing detailed error information for better error handling.
"""

from typing import Any, Dict, Optional


class JanuaError(Exception):
    """Base exception for all Janua SDK errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a JanuaError.

        Args:
            message: Error message
            code: Error code from the API
            status_code: HTTP status code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the error."""
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        """Detailed representation of the error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"status_code={self.status_code!r})"
        )


class AuthenticationError(JanuaError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, 401, details)


class ValidationError(JanuaError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, 400, details)
        self.errors = details.get("errors", []) if details else []


class NotFoundError(JanuaError):
    """Raised when a resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, 404, details)


class PermissionError(JanuaError):
    """Raised when permission is denied."""

    def __init__(
        self,
        message: str = "Permission denied",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, 403, details)


class AuthorizationError(PermissionError):
    """Raised when authorization fails (alias for PermissionError)."""


class RateLimitError(JanuaError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, code, 429, details)
        self.retry_after = retry_after or details.get("retry_after") if details else None
        self.limit = details.get("limit") if details else None
        self.remaining = details.get("remaining") if details else None
        self.reset_at = details.get("reset_at") if details else None


class NetworkError(JanuaError):
    """Raised when a network error occurs."""

    def __init__(
        self,
        message: str = "Network error occurred",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, code, None, details)
        self.original_error = original_error


class NetworkConnectionError(NetworkError):
    """Raised when a network connection error occurs (alias for NetworkError)."""


class ServerError(JanuaError):
    """Raised when a server error occurs."""

    def __init__(
        self,
        message: str = "Server error occurred",
        code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)


class ConfigurationError(JanuaError):
    """Raised when SDK configuration is invalid."""

    def __init__(
        self,
        message: str = "Invalid configuration",
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, None, details)


class TokenExpiredError(AuthenticationError):
    """Raised when a token has expired."""

    def __init__(
        self,
        message: str = "Token has expired",
        code: Optional[str] = "token_expired",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class InvalidTokenError(AuthenticationError):
    """Raised when a token is invalid."""

    def __init__(
        self,
        message: str = "Invalid token",
        code: Optional[str] = "invalid_token",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class MFARequiredError(AuthenticationError):
    """Raised when MFA is required for authentication."""

    def __init__(
        self,
        message: str = "Multi-factor authentication required",
        code: Optional[str] = "mfa_required",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)
        self.mfa_token = details.get("mfa_token") if details else None
        self.methods = details.get("methods", []) if details else []


class WebhookVerificationError(JanuaError):
    """Raised when webhook signature verification fails."""

    def __init__(
        self,
        message: str = "Webhook verification failed",
        code: Optional[str] = "webhook_verification_failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, 401, details)


class OrganizationError(JanuaError):
    """Raised when an organization-related error occurs."""

    def __init__(
        self,
        message: str = "Organization error",
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)


class UserSuspendedError(AuthenticationError):
    """Raised when a suspended user tries to authenticate."""

    def __init__(
        self,
        message: str = "User account is suspended",
        code: Optional[str] = "user_suspended",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class EmailNotVerifiedError(AuthenticationError):
    """Raised when email verification is required."""

    def __init__(
        self,
        message: str = "Email verification required",
        code: Optional[str] = "email_not_verified",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class PasswordTooWeakError(ValidationError):
    """Raised when a password doesn't meet security requirements."""

    def __init__(
        self,
        message: str = "Password does not meet security requirements",
        code: Optional[str] = "password_too_weak",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)
        self.requirements = details.get("requirements", []) if details else []


class DuplicateEmailError(ValidationError):
    """Raised when attempting to register with an existing email."""

    def __init__(
        self,
        message: str = "Email already exists",
        code: Optional[str] = "duplicate_email",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    def __init__(
        self,
        message: str = "Invalid email or password",
        code: Optional[str] = "invalid_credentials",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class SessionExpiredError(AuthenticationError):
    """Raised when a session has expired."""

    def __init__(
        self,
        message: str = "Session has expired",
        code: Optional[str] = "session_expired",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class InvalidStateError(JanuaError):
    """Raised when an operation is attempted in an invalid state."""

    def __init__(
        self,
        message: str = "Operation not allowed in current state",
        code: Optional[str] = "invalid_state",
        status_code: int = 409,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)


class TimeoutError(NetworkError):
    """Raised when a request times out."""

    def __init__(
        self,
        message: str = "Request timed out",
        code: Optional[str] = "timeout",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, code, details, original_error)


class APIError(JanuaError):
    """Generic API error for unmapped error responses."""

    def __init__(
        self,
        message: str = "API error occurred",
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)


# Mapping of API error codes to exception classes
ERROR_CODE_MAP = {
    "authentication_failed": AuthenticationError,
    "invalid_token": InvalidTokenError,
    "token_expired": TokenExpiredError,
    "mfa_required": MFARequiredError,
    "validation_error": ValidationError,
    "duplicate_email": DuplicateEmailError,
    "password_too_weak": PasswordTooWeakError,
    "not_found": NotFoundError,
    "permission_denied": PermissionError,
    "rate_limit_exceeded": RateLimitError,
    "user_suspended": UserSuspendedError,
    "email_not_verified": EmailNotVerifiedError,
    "invalid_credentials": InvalidCredentialsError,
    "session_expired": SessionExpiredError,
    "webhook_verification_failed": WebhookVerificationError,
    "invalid_state": InvalidStateError,
    "server_error": ServerError,
}


def get_exception_for_error_code(
    code: str,
    message: str,
    status_code: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> JanuaError:
    """
    Get the appropriate exception class for an error code.

    Args:
        code: Error code from the API
        message: Error message
        status_code: HTTP status code
        details: Additional error details

    Returns:
        Appropriate JanuaError subclass instance
    """
    exception_class = ERROR_CODE_MAP.get(code, APIError)
    
    if exception_class == RateLimitError and details:
        return RateLimitError(
            message=message,
            code=code,
            details=details,
            retry_after=details.get("retry_after"),
        )
    elif exception_class == MFARequiredError and details:
        return MFARequiredError(message=message, code=code, details=details)
    else:
        return exception_class(message=message, code=code, details=details)