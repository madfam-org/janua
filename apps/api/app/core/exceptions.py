"""
Unified Exception System for Janua

This module provides a hierarchical exception system that unifies:
1. API/HTTP exceptions (app/exceptions.py)
2. SSO-specific exceptions (app/sso/exceptions.py)
3. Internal service exceptions

All exceptions inherit from a common base (JanuaException) for consistent
error handling and logging across the application.
"""

from typing import Optional, Dict, Any


# ============================================================================
# Base Exception
# ============================================================================


class JanuaException(Exception):
    """
    Base exception for all Janua errors.

    All custom exceptions in the Janua codebase should inherit from this class
    to enable consistent error handling and logging.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization"""
        return {"error": self.__class__.__name__, "message": self.message, "details": self.details}


# ============================================================================
# API/HTTP Exceptions
# ============================================================================


class JanuaAPIException(JanuaException):
    """
    Base exception for HTTP/API errors.

    Includes HTTP status code and error code for API responses.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__.upper()

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API response dictionary"""
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class AuthenticationError(JanuaAPIException):
    """Raised when authentication fails (401)"""

    def __init__(
        self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=401, error_code="AUTHENTICATION_ERROR", details=details
        )


class TokenError(JanuaAPIException):
    """Raised when token operations fail (401)"""

    def __init__(self, message: str = "Token error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message, status_code=401, error_code="TOKEN_ERROR", details=details
        )


class AuthorizationError(JanuaAPIException):
    """Raised when authorization/permission check fails (403)"""

    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message, status_code=403, error_code="AUTHORIZATION_ERROR", details=details
        )


class ValidationError(JanuaAPIException):
    """Raised when input validation fails (422)"""

    def __init__(
        self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=422, error_code="VALIDATION_ERROR", details=details
        )


class NotFoundError(JanuaAPIException):
    """Raised when a resource is not found (404)"""

    def __init__(
        self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=404, error_code="NOT_FOUND_ERROR", details=details
        )


class ConflictError(JanuaAPIException):
    """Raised when a resource conflict occurs (409)"""

    def __init__(
        self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=409, error_code="CONFLICT_ERROR", details=details
        )


class RateLimitError(JanuaAPIException):
    """Raised when rate limit is exceeded (429)"""

    def __init__(
        self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=429, error_code="RATE_LIMIT_ERROR", details=details
        )


class ExternalServiceError(JanuaAPIException):
    """Raised when external service calls fail (502)"""

    def __init__(
        self, message: str = "External service error", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=502, error_code="EXTERNAL_SERVICE_ERROR", details=details
        )


# ============================================================================
# SSO-Specific Exceptions
# ============================================================================


class JanuaSSOException(JanuaAPIException):
    """
    Base exception for SSO-related errors.

    Extends JanuaAPIException to include HTTP status codes while maintaining
    SSO-specific attributes like provider and metadata.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, status_code=status_code, error_code=error_code, details=details
        )


class SSOAuthenticationError(JanuaSSOException):
    """Raised when SSO authentication fails"""

    def __init__(
        self, message: str, provider: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if provider:
            details["provider"] = provider

        super().__init__(
            message=message, status_code=401, error_code="SSO_AUTHENTICATION_ERROR", details=details
        )
        self.provider = provider


class SSOValidationError(JanuaSSOException):
    """Raised when SSO configuration or data validation fails"""

    def __init__(
        self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if field:
            details["field"] = field

        super().__init__(
            message=message, status_code=422, error_code="SSO_VALIDATION_ERROR", details=details
        )
        self.field = field


class SSOConfigurationError(JanuaSSOException):
    """Raised when SSO provider configuration is invalid or incomplete"""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        missing_fields: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider
        if missing_fields:
            details["missing_fields"] = missing_fields

        super().__init__(
            message=message, status_code=500, error_code="SSO_CONFIGURATION_ERROR", details=details
        )
        self.provider = provider
        self.missing_fields = missing_fields or []


class SSOMetadataError(JanuaSSOException):
    """Raised when SAML metadata parsing or validation fails"""

    def __init__(
        self,
        message: str,
        metadata_source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if metadata_source:
            details["metadata_source"] = metadata_source

        super().__init__(
            message=message, status_code=422, error_code="SSO_METADATA_ERROR", details=details
        )
        self.metadata_source = metadata_source


class SSOCertificateError(JanuaSSOException):
    """Raised when certificate validation or operations fail"""

    def __init__(
        self,
        message: str,
        certificate_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if certificate_id:
            details["certificate_id"] = certificate_id

        super().__init__(
            message=message, status_code=500, error_code="SSO_CERTIFICATE_ERROR", details=details
        )
        self.certificate_id = certificate_id


class SSOProvisioningError(JanuaSSOException):
    """Raised when user provisioning (JIT - Just In Time) fails"""

    def __init__(
        self,
        message: str,
        user_data: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if user_data:
            details["user_data"] = user_data

        super().__init__(
            message=message, status_code=500, error_code="SSO_PROVISIONING_ERROR", details=details
        )
        self.user_data = user_data or {}


# ============================================================================
# Internal Service Exceptions
# ============================================================================


class JanuaServiceException(JanuaException):
    """
    Base exception for internal service errors.

    Used for errors that occur within services but aren't necessarily
    meant to be exposed directly to API clients.
    """


class DatabaseError(JanuaServiceException):
    """Raised when database operations fail"""

    def __init__(
        self, message: str = "Database operation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)


class CacheError(JanuaServiceException):
    """Raised when cache operations fail"""

    def __init__(
        self, message: str = "Cache operation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)


class ConfigurationError(JanuaServiceException):
    """Raised when configuration is invalid or missing"""

    def __init__(
        self, message: str = "Configuration error", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Base
    "JanuaException",
    "JanuaAPIException",
    "JanuaSSOException",
    "JanuaServiceException",
    # API Exceptions
    "AuthenticationError",
    "TokenError",
    "AuthorizationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ExternalServiceError",
    # SSO Exceptions
    "SSOAuthenticationError",
    "SSOValidationError",
    "SSOConfigurationError",
    "SSOMetadataError",
    "SSOCertificateError",
    "SSOProvisioningError",
    # Service Exceptions
    "DatabaseError",
    "CacheError",
    "ConfigurationError",
]
