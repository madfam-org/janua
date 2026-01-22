"""
Response DTOs for organization endpoints
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    """Response model for organization details"""

    id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    slug: str = Field(..., description="Organization slug")
    description: Optional[str] = Field(None, description="Organization description")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    owner_id: str = Field(..., description="Owner user ID")
    settings: Dict = Field(default_factory=dict, description="Organization settings")
    org_metadata: Dict = Field(default_factory=dict, description="Organization metadata")
    billing_email: Optional[str] = Field(None, description="Billing email")
    billing_plan: str = Field(..., description="Billing plan")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    member_count: int = Field(..., description="Number of members")
    is_owner: bool = Field(..., description="Whether current user is owner")
    user_role: Optional[str] = Field(None, description="Current user's role")

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "My Organization",
                "slug": "my-org",
                "description": "A sample organization",
                "logo_url": "https://example.com/logo.png",
                "owner_id": "456e7890-e89b-12d3-a456-426614174001",
                "settings": {"feature_enabled": True},
                "org_metadata": {"created_by": "admin"},
                "billing_email": "billing@myorg.com",
                "billing_plan": "free",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "member_count": 5,
                "is_owner": True,
                "user_role": "owner",
            }
        }


class MemberResponse(BaseModel):
    """Response model for organization member"""

    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="Email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    display_name: Optional[str] = Field(None, description="Display name")
    profile_image_url: Optional[str] = Field(None, description="Profile image URL")
    role: str = Field(..., description="Member role")
    permissions: List[str] = Field(default_factory=list, description="Member permissions")
    joined_at: datetime = Field(..., description="Join timestamp")
    invited_by: Optional[str] = Field(None, description="ID of user who invited this member")

    class Config:
        schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "display_name": "John Doe",
                "profile_image_url": "https://example.com/avatar.png",
                "role": "member",
                "permissions": ["read", "write"],
                "joined_at": "2023-01-01T00:00:00Z",
                "invited_by": "456e7890-e89b-12d3-a456-426614174001",
            }
        }


class InvitationResponse(BaseModel):
    """Response model for organization invitation"""

    id: str = Field(..., description="Invitation ID")
    organization_id: str = Field(..., description="Organization ID")
    organization_name: str = Field(..., description="Organization name")
    email: str = Field(..., description="Invited email")
    role: str = Field(..., description="Invited role")
    permissions: List[str] = Field(default_factory=list, description="Invited permissions")
    invited_by: str = Field(..., description="ID of inviter")
    inviter_name: Optional[str] = Field(None, description="Name of inviter")
    status: str = Field(..., description="Invitation status")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                "organization_name": "My Organization",
                "email": "user@example.com",
                "role": "member",
                "permissions": ["read", "write"],
                "invited_by": "789e0123-e89b-12d3-a456-426614174002",
                "inviter_name": "Jane Doe",
                "status": "pending",
                "created_at": "2023-01-01T00:00:00Z",
                "expires_at": "2023-01-08T00:00:00Z",
            }
        }


class RoleResponse(BaseModel):
    """Response model for organization role"""

    id: str = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: List[str] = Field(default_factory=list, description="Role permissions")
    is_system: bool = Field(..., description="Whether this is a system role")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Content Manager",
                "description": "Can manage content but not settings",
                "permissions": ["read", "write", "manage_content"],
                "is_system": False,
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            }
        }


class InviteResultResponse(BaseModel):
    """Response model for invitation creation"""

    message: str = Field(..., description="Success message")
    invitation_id: str = Field(..., description="Created invitation ID")
    expires_at: datetime = Field(..., description="Invitation expiration")

    class Config:
        schema_extra = {
            "example": {
                "message": "Invitation sent successfully",
                "invitation_id": "123e4567-e89b-12d3-a456-426614174000",
                "expires_at": "2023-01-08T00:00:00Z",
            }
        }


class AcceptInvitationResponse(BaseModel):
    """Response model for invitation acceptance"""

    message: str = Field(..., description="Success message")
    organization: Dict = Field(..., description="Organization details")

    class Config:
        schema_extra = {
            "example": {
                "message": "Successfully joined organization",
                "organization": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "My Organization",
                    "slug": "my-org",
                },
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response"""

    message: str = Field(..., description="Success message")

    class Config:
        schema_extra = {"example": {"message": "Operation completed successfully"}}
