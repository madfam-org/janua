"""
Type definitions for the Janua Python SDK.

This module contains all the data models and type definitions used throughout
the SDK, implemented using Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, ConfigDict


# ====================
# Enumerations
# ====================

class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PENDING = "pending"


class OrganizationRole(str, Enum):
    """Organization member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    DISCORD = "discord"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    APPLE = "apple"


class WebhookEventType(str, Enum):
    """Webhook event types."""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_SIGNED_IN = "user.signed_in"
    USER_SIGNED_OUT = "user.signed_out"
    SESSION_CREATED = "session.created"
    SESSION_EXPIRED = "session.expired"
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    ORGANIZATION_MEMBER_ADDED = "organization.member_added"
    ORGANIZATION_MEMBER_REMOVED = "organization.member_removed"
    ORGANIZATION_MEMBER_UPDATED = "organization.member_updated"


class SessionStatus(str, Enum):
    """Session status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ====================
# Base Models
# ====================

class BaseResponse(BaseModel):
    """Base response model with common fields."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(10, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: Optional[str] = Field("asc", pattern="^(asc|desc)$")


class PaginatedResponse(BaseResponse):
    """Base paginated response."""
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")


# ====================
# User Models
# ====================

class User(BaseResponse):
    """User model."""
    id: UUID
    email: EmailStr
    email_verified: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    phone_number: Optional[str] = None
    phone_verified: bool = False
    status: UserStatus = UserStatus.ACTIVE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime] = None
    mfa_enabled: bool = False
    passkeys_enabled: bool = False
    oauth_accounts: List["OAuthAccount"] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    """User update request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    phone_number: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UserListResponse(PaginatedResponse):
    """User list response."""
    users: List[User]


# ====================
# Authentication Models
# ====================

class SignUpRequest(BaseModel):
    """Sign up request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    invite_code: Optional[str] = None


class SignInRequest(BaseModel):
    """Sign in request."""
    email: EmailStr
    password: str
    remember_me: bool = False


class TokenResponse(BaseResponse):
    """Token response."""
    access_token: str
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    scope: Optional[str] = None


# Alias for compatibility
AuthTokens = TokenResponse


class AuthResponse(BaseResponse):
    """Authentication response."""
    user: User
    tokens: TokenResponse
    session: Optional["Session"] = None


class SignInResponse(AuthResponse):
    """Sign in response with user and tokens."""


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""
    email: EmailStr
    redirect_url: Optional[HttpUrl] = None


class ResetPasswordRequest(BaseModel):
    """Reset password request."""
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class MagicLinkRequest(BaseModel):
    """Magic link request."""
    email: EmailStr
    redirect_url: Optional[HttpUrl] = None
    expires_in: Optional[int] = Field(3600, ge=300, le=86400, description="Expiration in seconds")


# ====================
# Session Models
# ====================

class Session(BaseResponse):
    """Session model."""
    id: UUID
    user_id: UUID
    token: str
    status: SessionStatus = SessionStatus.ACTIVE
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    last_activity_at: datetime


class SessionListResponse(PaginatedResponse):
    """Session list response."""
    sessions: List[Session]


# ====================
# Organization Models
# ====================

class Organization(BaseResponse):
    """Organization model."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    website_url: Optional[HttpUrl] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    owner_id: UUID


class OrganizationMember(BaseResponse):
    """Organization member model."""
    id: UUID
    organization_id: UUID
    user_id: UUID
    user: Optional[User] = None
    role: OrganizationRole
    permissions: List[str] = Field(default_factory=list)
    joined_at: datetime
    updated_at: datetime


class OrganizationInvitation(BaseResponse):
    """Organization invitation model."""
    id: UUID
    organization_id: UUID
    organization: Optional[Organization] = None
    email: EmailStr
    role: OrganizationRole
    invited_by_id: UUID
    invited_by: Optional[User] = None
    accepted: bool = False
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None


class OrganizationCreateRequest(BaseModel):
    """Organization create request."""
    name: str = Field(..., min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=3, max_length=50, pattern="^[a-z0-9-]+$")
    description: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    website_url: Optional[HttpUrl] = None
    metadata: Optional[Dict[str, Any]] = None


class OrganizationUpdateRequest(BaseModel):
    """Organization update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    website_url: Optional[HttpUrl] = None
    metadata: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class OrganizationInviteRequest(BaseModel):
    """Organization invite request."""
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER
    send_email: bool = True


class OrganizationListResponse(PaginatedResponse):
    """Organization list response."""
    organizations: List[Organization]


class OrganizationMemberListResponse(PaginatedResponse):
    """Organization member list response."""
    members: List[OrganizationMember]


# ====================
# MFA Models
# ====================

class MFAStatusResponse(BaseResponse):
    """MFA status response."""
    enabled: bool
    methods: List[str] = Field(default_factory=list)
    backup_codes_remaining: int = 0
    last_verified_at: Optional[datetime] = None


class MFAEnableRequest(BaseModel):
    """MFA enable request."""
    method: str = Field("totp", description="MFA method to enable")
    password: str = Field(..., description="Current password for verification")


class MFAEnableResponse(BaseResponse):
    """MFA enable response."""
    secret: str
    qr_code: str
    backup_codes: List[str]
    recovery_codes: List[str]


class MFAVerifyRequest(BaseModel):
    """MFA verify request."""
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]+$")
    method: str = Field("totp")


class MFADisableRequest(BaseModel):
    """MFA disable request."""
    password: str
    code: Optional[str] = Field(None, min_length=6, max_length=6)


# ====================
# Passkey Models
# ====================

class PasskeyResponse(BaseResponse):
    """Passkey response."""
    id: UUID
    user_id: UUID
    name: str
    credential_id: str
    public_key: str
    sign_count: int
    transports: List[str]
    created_at: datetime
    last_used_at: Optional[datetime] = None


class PasskeyRegisterRequest(BaseModel):
    """Passkey register request."""
    name: str = Field(..., min_length=1, max_length=100)
    credential: Dict[str, Any]


class PasskeyUpdateRequest(BaseModel):
    """Passkey update request."""
    name: str = Field(..., min_length=1, max_length=100)


class PasskeyListResponse(PaginatedResponse):
    """Passkey list response."""
    passkeys: List[PasskeyResponse]


# ====================
# Webhook Models
# ====================

class WebhookEndpoint(BaseResponse):
    """Webhook endpoint model."""
    id: UUID
    url: HttpUrl
    description: Optional[str] = None
    events: List[WebhookEventType]
    enabled: bool = True
    secret: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    failure_count: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None


class WebhookEndpointCreateRequest(BaseModel):
    """Webhook endpoint create request."""
    url: HttpUrl
    events: List[WebhookEventType]
    description: Optional[str] = None
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None


class WebhookEndpointUpdateRequest(BaseModel):
    """Webhook endpoint update request."""
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class WebhookEvent(BaseResponse):
    """Webhook event model."""
    id: UUID
    endpoint_id: UUID
    event_type: WebhookEventType
    payload: Dict[str, Any]
    created_at: datetime
    delivered_at: Optional[datetime] = None
    attempts: int = 0
    status: str
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    next_retry_at: Optional[datetime] = None


class WebhookDelivery(BaseResponse):
    """Webhook delivery model."""
    id: UUID
    event_id: UUID
    endpoint_id: UUID
    status: str
    attempt: int
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class WebhookEndpointListResponse(PaginatedResponse):
    """Webhook endpoint list response."""
    endpoints: List[WebhookEndpoint]


class WebhookEventListResponse(PaginatedResponse):
    """Webhook event list response."""
    events: List[WebhookEvent]


# ====================
# Admin Models
# ====================

class AdminStatsResponse(BaseResponse):
    """Admin statistics response."""
    total_users: int
    active_users: int
    total_organizations: int
    total_sessions: int
    active_sessions: int
    mfa_enabled_users: int
    passkey_enabled_users: int
    oauth_connected_users: int
    period_start: datetime
    period_end: datetime
    user_growth: float
    organization_growth: float


class SystemHealthResponse(BaseResponse):
    """System health response."""
    status: str
    version: str
    uptime: int
    database_status: str
    cache_status: str
    queue_status: str
    storage_status: str
    services: Dict[str, str]
    last_checked_at: datetime


# ====================
# OAuth Models
# ====================

class OAuthProviderInfo(BaseResponse):
    """OAuth provider information."""
    provider: OAuthProvider
    enabled: bool
    client_id: str
    authorization_url: str
    token_url: str
    scopes: List[str]


class OAuthAccount(BaseResponse):
    """OAuth account model."""
    id: UUID
    user_id: UUID
    provider: OAuthProvider
    provider_user_id: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OAuthAuthorizeRequest(BaseModel):
    """OAuth authorize request."""
    provider: OAuthProvider
    redirect_url: HttpUrl
    state: Optional[str] = None
    code_challenge: Optional[str] = None


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    provider: OAuthProvider
    code: str
    state: Optional[str] = None
    code_verifier: Optional[str] = None


# Update forward references
User.model_rebuild()
AuthResponse.model_rebuild()
OrganizationInvitation.model_rebuild()
OrganizationMember.model_rebuild()