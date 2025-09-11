"""
Type definitions and Pydantic models for the Plinto SDK
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum


# Enums
class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OrganizationRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"
    APPLE = "apple"
    MICROSOFT = "microsoft"


class WebhookEventType(str, Enum):
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_SIGNED_IN = "user.signed_in"
    USER_SIGNED_OUT = "user.signed_out"
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    MEMBER_ROLE_UPDATED = "member.role_updated"


# Base Models
class BaseResponse(BaseModel):
    """Base response model"""
    
    class Config:
        from_attributes = True


# User Models
class User(BaseResponse):
    """User model"""
    id: str
    email: str
    email_verified: bool
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None
    phone_number: Optional[str] = None
    phone_verified: bool = False
    timezone: Optional[str] = None
    locale: Optional[str] = None
    status: UserStatus
    mfa_enabled: bool = False
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime] = None
    user_metadata: Dict[str, Any] = Field(default_factory=dict)


class UserUpdateRequest(BaseModel):
    """User profile update request"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=1000)
    phone_number: Optional[str] = Field(None, max_length=20)
    timezone: Optional[str] = Field(None, max_length=50)
    locale: Optional[str] = Field(None, max_length=10)
    user_metadata: Optional[Dict[str, Any]] = None


# Authentication Models
class SignUpRequest(BaseModel):
    """Sign up request model"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    
    @validator('username')
    def validate_username(cls, v):
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v


class SignInRequest(BaseModel):
    """Sign in request model"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str
    
    @validator('username')
    def validate_credentials(cls, v, values):
        if not v and not values.get('email'):
            raise ValueError('Either email or username must be provided')
        return v


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignInResponse(BaseResponse):
    """Sign in response model"""
    user: User
    tokens: TokenResponse


class AuthResponse(BaseResponse):
    """Generic auth response model"""
    user: User
    tokens: TokenResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class MagicLinkRequest(BaseModel):
    """Magic link request"""
    email: EmailStr
    redirect_url: Optional[str] = None


# Session Models
class Session(BaseResponse):
    """Session model"""
    id: str
    user_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    is_current: bool = False
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    revoked: bool = False


# Organization Models
class Organization(BaseResponse):
    """Organization model"""
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    owner_id: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    org_metadata: Dict[str, Any] = Field(default_factory=dict)
    billing_email: Optional[str] = None
    billing_plan: str = "free"
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    is_owner: bool = False
    user_role: Optional[OrganizationRole] = None


class OrganizationCreateRequest(BaseModel):
    """Organization creation request"""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: Optional[str] = Field(None, max_length=1000)
    billing_email: Optional[str] = None
    
    @validator('slug')
    def validate_slug(cls, v):
        return v.lower()


class OrganizationUpdateRequest(BaseModel):
    """Organization update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    logo_url: Optional[str] = Field(None, max_length=500)
    billing_email: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class OrganizationMember(BaseResponse):
    """Organization member model"""
    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    profile_image_url: Optional[str] = None
    role: OrganizationRole
    permissions: List[str] = Field(default_factory=list)
    joined_at: datetime
    invited_by: Optional[str] = None


class OrganizationInviteRequest(BaseModel):
    """Organization invitation request"""
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER
    permissions: Optional[List[str]] = Field(default_factory=list)
    message: Optional[str] = None


class OrganizationInvitation(BaseResponse):
    """Organization invitation model"""
    id: str
    organization_id: str
    organization_name: str
    email: str
    role: OrganizationRole
    permissions: List[str] = Field(default_factory=list)
    invited_by: str
    inviter_name: Optional[str] = None
    status: str
    created_at: datetime
    expires_at: datetime


# MFA Models
class MFAStatusResponse(BaseResponse):
    """MFA status response"""
    enabled: bool
    verified: bool
    backup_codes_remaining: int
    last_used_at: Optional[datetime] = None


class MFAEnableRequest(BaseModel):
    """MFA enable request"""
    password: str


class MFAEnableResponse(BaseResponse):
    """MFA enable response"""
    secret: str
    qr_code: str
    backup_codes: List[str]
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    """MFA verification request"""
    code: str = Field(..., min_length=6, max_length=6)


class MFADisableRequest(BaseModel):
    """MFA disable request"""
    password: str
    code: Optional[str] = Field(None, min_length=6, max_length=6)


# Passkey Models
class PasskeyResponse(BaseResponse):
    """Passkey response model"""
    id: str
    name: Optional[str] = None
    authenticator_attachment: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    sign_count: int = 0


class PasskeyRegisterRequest(BaseModel):
    """Passkey registration request"""
    credential: Dict[str, Any]
    name: Optional[str] = Field(None, max_length=100)


class PasskeyUpdateRequest(BaseModel):
    """Passkey update request"""
    name: str = Field(..., min_length=1, max_length=100)


# Webhook Models
class WebhookEndpoint(BaseResponse):
    """Webhook endpoint model"""
    id: str
    url: str
    secret: str
    events: List[WebhookEventType]
    is_active: bool = True
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    created_at: datetime
    updated_at: datetime


class WebhookEndpointCreateRequest(BaseModel):
    """Webhook endpoint creation request"""
    url: str
    events: List[WebhookEventType]
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class WebhookEndpointUpdateRequest(BaseModel):
    """Webhook endpoint update request"""
    url: Optional[str] = None
    events: Optional[List[WebhookEventType]] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class WebhookEvent(BaseResponse):
    """Webhook event model"""
    id: str
    type: WebhookEventType
    data: Dict[str, Any]
    created_at: datetime


class WebhookDelivery(BaseResponse):
    """Webhook delivery model"""
    id: str
    webhook_endpoint_id: str
    webhook_event_id: str
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    attempt: int = 1
    delivered_at: Optional[datetime] = None
    created_at: datetime


# Admin Models
class AdminStatsResponse(BaseResponse):
    """Admin statistics response"""
    total_users: int
    active_users: int
    suspended_users: int
    deleted_users: int
    total_organizations: int
    total_sessions: int
    active_sessions: int
    mfa_enabled_users: int
    oauth_accounts: int
    passkeys_registered: int
    users_last_24h: int
    sessions_last_24h: int


class SystemHealthResponse(BaseResponse):
    """System health response"""
    status: str
    database: str
    cache: str
    storage: str
    email: str
    uptime: float
    version: str
    environment: str


# OAuth Models
class OAuthProviderInfo(BaseResponse):
    """OAuth provider information"""
    provider: OAuthProvider
    name: str
    enabled: bool
    linked: bool = False
    provider_email: Optional[str] = None
    linked_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class OAuthAccount(BaseResponse):
    """OAuth account model"""
    provider: OAuthProvider
    provider_id: str
    provider_email: str
    created_at: datetime
    updated_at: datetime


# Pagination Models
class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(BaseResponse):
    """Paginated response base"""
    meta: PaginationMeta


class UserListResponse(PaginatedResponse):
    """User list response"""
    users: List[User]


class OrganizationListResponse(PaginatedResponse):
    """Organization list response"""
    organizations: List[Organization]


class SessionListResponse(PaginatedResponse):
    """Session list response"""
    sessions: List[Session]


class WebhookEndpointListResponse(PaginatedResponse):
    """Webhook endpoint list response"""
    endpoints: List[WebhookEndpoint]