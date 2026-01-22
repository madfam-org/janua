"""
Membership domain entity
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.models import OrganizationRole


@dataclass
class Membership:
    """Organization membership entity with business logic"""

    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    permissions: List[str] = field(default_factory=list)
    joined_at: datetime = field(default_factory=datetime.utcnow)
    invited_by: Optional[UUID] = None

    def __post_init__(self):
        """Validate membership state after creation"""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Ensure membership business rules are maintained"""
        if not self.organization_id:
            raise ValueError("Organization ID cannot be empty")

        if not self.user_id:
            raise ValueError("User ID cannot be empty")

        if not isinstance(self.role, OrganizationRole):
            raise ValueError("Role must be a valid OrganizationRole")

        if not isinstance(self.permissions, list):
            raise ValueError("Permissions must be a list")

    def update_role(self, new_role: OrganizationRole) -> None:
        """Update member role with validation"""
        if not isinstance(new_role, OrganizationRole):
            raise ValueError("Role must be a valid OrganizationRole")

        self.role = new_role

    def add_permission(self, permission: str) -> None:
        """Add a permission to the member"""
        if not permission or not isinstance(permission, str):
            raise ValueError("Permission must be a non-empty string")

        if permission not in self.permissions:
            self.permissions.append(permission)

    def remove_permission(self, permission: str) -> None:
        """Remove a permission from the member"""
        if permission in self.permissions:
            self.permissions.remove(permission)

    def has_permission(self, permission: str) -> bool:
        """Check if member has a specific permission"""
        return permission in self.permissions

    def has_role_hierarchy_access(self, required_role: OrganizationRole) -> bool:
        """Check if member's role meets the required hierarchy level"""
        role_hierarchy = {
            OrganizationRole.VIEWER: 0,
            OrganizationRole.MEMBER: 1,
            OrganizationRole.ADMIN: 2,
            OrganizationRole.OWNER: 3,
        }

        user_level = role_hierarchy.get(self.role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        return user_level >= required_level

    def can_manage_members(self) -> bool:
        """Check if member can manage other members"""
        return self.has_role_hierarchy_access(OrganizationRole.ADMIN)

    def can_manage_settings(self) -> bool:
        """Check if member can manage organization settings"""
        return self.has_role_hierarchy_access(OrganizationRole.ADMIN)

    def can_manage_billing(self) -> bool:
        """Check if member can manage billing"""
        return self.has_role_hierarchy_access(OrganizationRole.ADMIN)

    def can_transfer_ownership(self) -> bool:
        """Check if member can transfer ownership"""
        return self.role == OrganizationRole.OWNER

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "organization_id": str(self.organization_id),
            "user_id": str(self.user_id),
            "role": self.role.value,
            "permissions": self.permissions,
            "joined_at": self.joined_at,
            "invited_by": str(self.invited_by) if self.invited_by else None,
        }


@dataclass
class OrganizationInvitation:
    """Organization invitation entity with business logic"""

    id: UUID
    organization_id: UUID
    email: str
    role: OrganizationRole
    permissions: List[str] = field(default_factory=list)
    token: str = ""
    invited_by: UUID = field(default_factory=lambda: UUID("00000000-0000-0000-0000-000000000000"))
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate invitation state after creation"""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Ensure invitation business rules are maintained"""
        if not self.organization_id:
            raise ValueError("Organization ID cannot be empty")

        if not self.email or not self._is_valid_email(self.email):
            raise ValueError("Valid email is required")

        if not isinstance(self.role, OrganizationRole):
            raise ValueError("Role must be a valid OrganizationRole")

        if self.status not in ["pending", "accepted", "expired", "revoked"]:
            raise ValueError("Invalid invitation status")

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format"""
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(email_pattern, email))

    def is_expired(self) -> bool:
        """Check if invitation has expired"""
        return datetime.utcnow() > self.expires_at

    def is_pending(self) -> bool:
        """Check if invitation is still pending"""
        return self.status == "pending" and not self.is_expired()

    def accept(self) -> None:
        """Accept the invitation"""
        if not self.is_pending():
            raise ValueError("Invitation is not available for acceptance")

        self.status = "accepted"
        self.accepted_at = datetime.utcnow()

    def expire(self) -> None:
        """Mark invitation as expired"""
        if self.status == "pending":
            self.status = "expired"

    def revoke(self) -> None:
        """Revoke the invitation"""
        if self.status == "pending":
            self.status = "revoked"

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "email": self.email,
            "role": self.role.value,
            "permissions": self.permissions,
            "token": self.token,
            "invited_by": str(self.invited_by),
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "accepted_at": self.accepted_at,
        }
