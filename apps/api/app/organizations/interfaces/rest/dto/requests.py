"""
Request DTOs for organization endpoints
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator

from app.models import OrganizationRole


class CreateOrganizationRequest(BaseModel):
    """Request to create an organization"""

    name: str = Field(..., min_length=1, max_length=200, description="Organization name")
    slug: str = Field(
        ..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$", description="Organization slug"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Organization description"
    )
    billing_email: Optional[str] = Field(None, description="Billing email address")

    @validator("slug")
    def validate_slug(cls, v):  # noqa: N805 - pydantic validators use cls
        """Ensure slug is lowercase and valid"""
        return v.lower()

    class Config:
        schema_extra = {
            "example": {
                "name": "My Organization",
                "slug": "my-org",
                "description": "A description of my organization",
                "billing_email": "billing@myorg.com",
            }
        }


class UpdateOrganizationRequest(BaseModel):
    """Request to update an organization"""

    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Organization name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Organization description"
    )
    logo_url: Optional[str] = Field(None, max_length=500, description="Logo URL")
    billing_email: Optional[str] = Field(None, description="Billing email address")
    settings: Optional[dict] = Field(None, description="Organization settings")

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Organization Name",
                "description": "Updated description",
                "logo_url": "https://example.com/logo.png",
                "billing_email": "billing@myorg.com",
                "settings": {"feature_enabled": True},
            }
        }


class InviteMemberRequest(BaseModel):
    """Request to invite a member to an organization"""

    email: str = Field(..., description="Email address of the person to invite")
    role: OrganizationRole = Field(OrganizationRole.MEMBER, description="Role to assign")
    permissions: List[str] = Field(default_factory=list, description="Additional permissions")
    message: Optional[str] = Field(None, max_length=1000, description="Optional invitation message")

    @validator("email")
    def validate_email(cls, v):  # noqa: N805 - pydantic validators use cls
        """Validate email format"""
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "role": "member",
                "permissions": ["read", "write"],
                "message": "Welcome to our organization!",
            }
        }


class UpdateMemberRoleRequest(BaseModel):
    """Request to update a member's role"""

    role: OrganizationRole = Field(..., description="New role to assign")

    class Config:
        schema_extra = {"example": {"role": "admin"}}


class TransferOwnershipRequest(BaseModel):
    """Request to transfer organization ownership"""

    new_owner_id: str = Field(..., description="ID of the new owner")

    class Config:
        schema_extra = {"example": {"new_owner_id": "123e4567-e89b-12d3-a456-426614174000"}}


class CreateRoleRequest(BaseModel):
    """Request to create a custom role"""

    name: str = Field(..., min_length=1, max_length=100, description="Role name")
    description: Optional[str] = Field(None, max_length=500, description="Role description")
    permissions: List[str] = Field(default_factory=list, description="Role permissions")

    class Config:
        schema_extra = {
            "example": {
                "name": "Content Manager",
                "description": "Can manage content but not settings",
                "permissions": ["read", "write", "manage_content"],
            }
        }
