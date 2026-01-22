"""
Invitation models with Pydantic schemas.
"""

from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
import enum

# Re-export SQLAlchemy model from __init__.py
from . import Invitation as InvitationModel


class InvitationStatus(str, enum.Enum):
    """Invitation status enumeration."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


# Pydantic Schemas


class InvitationCreate(BaseModel):
    """Schema for creating an invitation."""

    organization_id: str
    email: EmailStr
    role: str = Field(default="member", pattern="^(owner|admin|member|viewer)$")
    message: Optional[str] = Field(None, max_length=500)
    expires_in: int = Field(default=7, ge=1, le=30)  # days


class InvitationUpdate(BaseModel):
    """Schema for updating an invitation."""

    role: Optional[str] = Field(None, pattern="^(owner|admin|member|viewer)$")
    message: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None


class InvitationResponse(BaseModel):
    """Schema for invitation response."""

    id: str
    organization_id: str
    email: str
    role: str
    status: str
    invited_by: str
    message: Optional[str]
    expires_at: datetime
    created_at: datetime
    invite_url: str
    email_sent: bool = False

    class Config:
        from_attributes = True
        orm_mode = True


class InvitationAcceptRequest(BaseModel):
    """Schema for accepting an invitation."""

    token: str
    user_id: Optional[str] = None  # If user already exists
    # For new user registration
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8)


class InvitationAcceptResponse(BaseModel):
    """Schema for invitation acceptance response."""

    success: bool
    user_id: str
    organization_id: str
    message: str
    is_new_user: bool = False


class InvitationListResponse(BaseModel):
    """Schema for paginated invitation list."""

    invitations: List[InvitationResponse]
    total: int
    pending_count: int = 0
    accepted_count: int = 0
    expired_count: int = 0


class BulkInvitationCreate(BaseModel):
    """Schema for creating multiple invitations."""

    organization_id: str
    emails: List[EmailStr] = Field(..., min_items=1, max_items=100)
    role: str = Field(default="member", pattern="^(owner|admin|member|viewer)$")
    message: Optional[str] = Field(None, max_length=500)
    expires_in: int = Field(default=7, ge=1, le=30)  # days


class BulkInvitationResponse(BaseModel):
    """Schema for bulk invitation response."""

    successful: List[InvitationResponse]
    failed: List[Dict[str, str]]  # email -> error message
    total_sent: int
    total_failed: int


# Re-export SQLAlchemy model for convenience
Invitation = InvitationModel
