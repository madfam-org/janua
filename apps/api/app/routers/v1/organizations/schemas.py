"""
Pydantic models and validation schemas for organizations
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class OrganizationRole(str, Enum):
    """Organization member roles"""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


class InvitationStatus(str, Enum):
    """Invitation status"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


# Request Models
class OrganizationCreateRequest(BaseModel):
    """Organization creation request"""

    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: Optional[str] = Field(None, max_length=1000)
    billing_email: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        """Ensure slug is lowercase and valid"""
        return v.lower()


class OrganizationUpdateRequest(BaseModel):
    """Organization update request"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    logo_url: Optional[str] = Field(None, max_length=500)
    billing_email: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class MemberUpdateRequest(BaseModel):
    """Member role update request"""

    role: OrganizationRole


class InviteMemberRequest(BaseModel):
    """Member invitation request"""

    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    role: OrganizationRole = OrganizationRole.MEMBER
    message: Optional[str] = Field(None, max_length=500)


class CustomRoleCreateRequest(BaseModel):
    """Custom role creation request"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(..., min_items=1)


class CustomRoleUpdateRequest(BaseModel):
    """Custom role update request"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: Optional[List[str]] = None


# Response Models
class UserSummary(BaseModel):
    """User summary for organization responses"""

    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    avatar_url: Optional[str]

    class Config:
        from_attributes = True


class OrganizationResponse(BaseModel):
    """Organization response model"""

    id: str
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    billing_email: Optional[str]
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = None
    settings: Optional[Dict[str, Any]] = None
    # Added for UI compatibility - maps subscription_tier to plan
    plan: Optional[str] = None
    # Owner email for display in organization lists
    owner_email: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationDetailResponse(OrganizationResponse):
    """Detailed organization response with additional fields"""

    owner: UserSummary
    subscription_status: Optional[str] = None
    subscription_plan: Optional[str] = None


class OrganizationMemberResponse(BaseModel):
    """Organization member response"""

    id: str
    user: UserSummary
    role: str
    custom_role_id: Optional[str] = None
    custom_role_name: Optional[str] = None
    joined_at: datetime
    permissions: List[str] = []

    class Config:
        from_attributes = True


class OrganizationInvitationResponse(BaseModel):
    """Organization invitation response"""

    id: str
    email: str
    role: str
    custom_role_id: Optional[str] = None
    custom_role_name: Optional[str] = None
    status: InvitationStatus
    message: Optional[str] = None
    invited_by: UserSummary
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class CustomRoleResponse(BaseModel):
    """Custom role response"""

    id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    created_at: datetime
    created_by: UserSummary
    member_count: int = 0

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """Organization list response"""

    organizations: List[OrganizationResponse]
    total: int
    page: int
    per_page: int


class MemberListResponse(BaseModel):
    """Members list response"""

    members: List[OrganizationMemberResponse]
    total: int
    page: int
    per_page: int


class InvitationListResponse(BaseModel):
    """Invitations list response"""

    invitations: List[OrganizationInvitationResponse]
    total: int
    page: int
    per_page: int


class CustomRoleListResponse(BaseModel):
    """Custom roles list response"""

    roles: List[CustomRoleResponse]
    total: int


class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool = True
    message: str


class TransferOwnershipRequest(BaseModel):
    """Ownership transfer request"""

    new_owner_id: str
    confirmation_password: str
