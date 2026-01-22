"""
Janua - Enterprise-grade authentication and user management platform

A comprehensive authentication platform providing SSO, RBAC, multi-tenancy,
and enterprise security features for modern applications.
"""

__version__ = "0.1.0"
__author__ = "Janua Team"
__email__ = "team@janua.dev"
__license__ = "AGPL-3.0"
__url__ = "https://janua.dev"

# Core API exports for package consumers
from .config import Settings, get_settings
from .exceptions import (
    JanuaAPIException,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ExternalServiceError,
)

# Main application factory
from .main import create_app

# Core services for programmatic access
from .services.auth_service import AuthService
from .services.jwt_service import JWTService
from .services.cache import CacheService

# SDK support utilities
from .sdk import (
    BaseAPIClient,
    ClientConfig,
    AuthenticationMethod,
    RetryConfig,
    RequestOptions,
    TokenManager,
    AuthenticationFlow,
    SDKError,
    APIError,
    ValidationError as SDKValidationError,
    AuthenticationError as SDKAuthenticationError,
    RateLimitError,
    ServerError,
    NetworkError,
)

# SDK response models
from .schemas.sdk_models import (
    SDKBaseResponse,
    SDKDataResponse,
    SDKListResponse,
    SDKSuccessResponse,
    SDKErrorResponse,
    PaginationMetadata,
    APIStatus,
)

# Models for external integrations
from .models import (
    User,
    Organization,
    Session,
    AuditLog,
    UserStatus,
    OrganizationRole,
)

# Public API
__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__url__",
    # Application factory
    "create_app",
    # Configuration
    "Settings",
    "get_settings",
    # Exceptions
    "JanuaAPIException",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ExternalServiceError",
    # Core services
    "AuthService",
    "JWTService",
    "CacheService",
    # SDK utilities
    "BaseAPIClient",
    "ClientConfig",
    "AuthenticationMethod",
    "RetryConfig",
    "RequestOptions",
    "TokenManager",
    "AuthenticationFlow",
    "SDKError",
    "APIError",
    "SDKValidationError",
    "SDKAuthenticationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    # SDK response models
    "SDKBaseResponse",
    "SDKDataResponse",
    "SDKListResponse",
    "SDKSuccessResponse",
    "SDKErrorResponse",
    "PaginationMetadata",
    "APIStatus",
    # Models
    "User",
    "Organization",
    "Session",
    "AuditLog",
    "UserStatus",
    "OrganizationRole",
]
