"""
Plinto Python SDK
Official SDK for Plinto Authentication and Identity Platform

A comprehensive Python SDK for the Plinto API providing authentication,
user management, organization management, webhooks, and admin operations.
"""

from .client import PlintoClient
from .exceptions import (
    PlintoError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    NetworkError,
    ServerError,
    ConfigurationError,
)
from .types import (
    # Base types
    User,
    Session,
    Organization,
    OrganizationMember,
    OrganizationInvitation,
    
    # Authentication types
    SignUpRequest,
    SignInRequest,
    SignInResponse,
    TokenResponse,
    AuthResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    MagicLinkRequest,
    
    # User types
    UserUpdateRequest,
    UserListResponse,
    SessionListResponse,
    
    # Organization types
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationInviteRequest,
    OrganizationListResponse,
    
    # MFA types
    MFAStatusResponse,
    MFAEnableRequest,
    MFAEnableResponse,
    MFAVerifyRequest,
    MFADisableRequest,
    
    # Passkey types
    PasskeyResponse,
    PasskeyRegisterRequest,
    PasskeyUpdateRequest,
    
    # Webhook types
    WebhookEndpoint,
    WebhookEndpointCreateRequest,
    WebhookEndpointUpdateRequest,
    WebhookEvent,
    WebhookDelivery,
    WebhookEndpointListResponse,
    
    # Admin types
    AdminStatsResponse,
    SystemHealthResponse,
    
    # OAuth types
    OAuthProviderInfo,
    OAuthAccount,
    
    # Enums
    UserStatus,
    OrganizationRole,
    OAuthProvider,
    WebhookEventType,
)
from .utils import (
    validate_webhook_signature,
    parse_jwt_without_verification,
    is_token_expired,
    TokenValidator,
)

__version__ = "1.0.0"
__all__ = [
    # Main client
    "PlintoClient",
    
    # Exceptions
    "PlintoError",
    "AuthenticationError",
    "ValidationError",
    "NotFoundError",
    "PermissionError",
    "RateLimitError",
    "NetworkError",
    "ServerError",
    "ConfigurationError",
    
    # Base types
    "User",
    "Session",
    "Organization",
    "OrganizationMember",
    "OrganizationInvitation",
    
    # Authentication types
    "SignUpRequest",
    "SignInRequest",
    "SignInResponse",
    "TokenResponse",
    "AuthResponse",
    "RefreshTokenRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "ChangePasswordRequest",
    "MagicLinkRequest",
    
    # User types
    "UserUpdateRequest",
    "UserListResponse",
    "SessionListResponse",
    
    # Organization types
    "OrganizationCreateRequest",
    "OrganizationUpdateRequest",
    "OrganizationInviteRequest",
    "OrganizationListResponse",
    
    # MFA types
    "MFAStatusResponse",
    "MFAEnableRequest",
    "MFAEnableResponse",
    "MFAVerifyRequest",
    "MFADisableRequest",
    
    # Passkey types
    "PasskeyResponse",
    "PasskeyRegisterRequest",
    "PasskeyUpdateRequest",
    
    # Webhook types
    "WebhookEndpoint",
    "WebhookEndpointCreateRequest",
    "WebhookEndpointUpdateRequest",
    "WebhookEvent",
    "WebhookDelivery",
    "WebhookEndpointListResponse",
    
    # Admin types
    "AdminStatsResponse",
    "SystemHealthResponse",
    
    # OAuth types
    "OAuthProviderInfo",
    "OAuthAccount",
    
    # Enums
    "UserStatus",
    "OrganizationRole",
    "OAuthProvider",
    "WebhookEventType",
    
    # Utilities
    "validate_webhook_signature",
    "parse_jwt_without_verification",
    "is_token_expired",
    "TokenValidator",
]