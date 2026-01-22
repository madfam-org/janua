"""
SDK support utilities and base classes for Janua API consumption.

This module provides the foundation for generating robust, platform-specific
SDKs that work consistently across TypeScript, Python, Go, Java, and mobile platforms.
"""

from .client_base import (
    BaseAPIClient,
    ClientConfig,
    AuthenticationMethod,
    RetryConfig,
    RequestOptions,
)

from .authentication import (
    TokenManager,
    AuthenticationFlow,
    TokenRefreshStrategy,
)

from .error_handling import (
    SDKError,
    APIError,
    ValidationError,
    AuthenticationError,
    RateLimitError,
    ServerError,
    NetworkError,
)

from .response_handlers import (
    ResponseHandler,
    PaginationHandler,
    BulkOperationHandler,
)

__all__ = [
    # Core client classes
    "BaseAPIClient",
    "ClientConfig",
    "AuthenticationMethod",
    "RetryConfig",
    "RequestOptions",
    # Authentication
    "TokenManager",
    "AuthenticationFlow",
    "TokenRefreshStrategy",
    # Error handling
    "SDKError",
    "APIError",
    "ValidationError",
    "AuthenticationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    # Response handling
    "ResponseHandler",
    "PaginationHandler",
    "BulkOperationHandler",
]
