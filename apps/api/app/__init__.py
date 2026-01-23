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
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    JanuaAPIException,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

# Main application factory
from .main import create_app

# Models for external integrations
from .models import (
    AuditLog,
    Organization,
    OrganizationRole,
    Session,
    User,
    UserStatus,
)

# SDK response models
from .schemas.sdk_models import (
    APIStatus,
    PaginationMetadata,
    SDKBaseResponse,
    SDKDataResponse,
    SDKErrorResponse,
    SDKListResponse,
    SDKSuccessResponse,
)

# SDK support utilities
from .sdk import (
    APIError,
    AuthenticationFlow,
    AuthenticationMethod,
    BaseAPIClient,
    ClientConfig,
    NetworkError,
    RequestOptions,
    RetryConfig,
    SDKError,
    ServerError,
    TokenManager,
)
from .sdk import (
    AuthenticationError as SDKAuthenticationError,
)
from .sdk import (
    RateLimitError as SDKRateLimitError,
)
from .sdk import (
    ValidationError as SDKValidationError,
)

# Core services for programmatic access
from .services.auth_service import AuthService
from .services.cache import CacheService
from .services.jwt_service import JWTService

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
    "SDKRateLimitError",
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
