"""
Membership domain service containing business logic that doesn't belong to a single entity
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional

from app.models import OrganizationRole
from ..models.membership import OrganizationInvitation


class MembershipService:
    """Domain service for complex membership operations"""

    @staticmethod
    def validate_role_change(
        current_role: OrganizationRole,
        new_role: OrganizationRole,
        requester_role: OrganizationRole,
        is_owner_change: bool = False
    ) -> None:
        """Validate if a role change is allowed"""

        # Owner role changes require special handling
        if current_role == OrganizationRole.OWNER or new_role == OrganizationRole.OWNER:
            if not is_owner_change:
                raise ValueError("Owner role changes require ownership transfer process")

        # Only admins and owners can change roles
        if not MembershipService._has_management_privileges(requester_role):
            raise ValueError("Insufficient privileges to change member roles")

        # Can't promote someone to a role higher than yours (except owner transfer)
        role_hierarchy = MembershipService._get_role_hierarchy()
        requester_level = role_hierarchy.get(requester_role, 0)
        new_role_level = role_hierarchy.get(new_role, 0)

        if new_role_level >= requester_level and requester_role != OrganizationRole.OWNER:
            raise ValueError("Cannot promote member to a role equal or higher than yours")

    @staticmethod
    def validate_member_removal(
        member_role: OrganizationRole,
        requester_role: OrganizationRole,
        is_owner: bool = False
    ) -> None:
        """Validate if a member can be removed"""

        # Can't remove the owner
        if is_owner:
            raise ValueError("Cannot remove organization owner")

        # Only admins and owners can remove members
        if not MembershipService._has_management_privileges(requester_role):
            raise ValueError("Insufficient privileges to remove members")

        # Can't remove someone with equal or higher role (except if you're owner)
        role_hierarchy = MembershipService._get_role_hierarchy()
        requester_level = role_hierarchy.get(requester_role, 0)
        member_level = role_hierarchy.get(member_role, 0)

        if member_level >= requester_level and requester_role != OrganizationRole.OWNER:
            raise ValueError("Cannot remove member with equal or higher role")

    @staticmethod
    def validate_invitation_role(
        invited_role: OrganizationRole,
        inviter_role: OrganizationRole
    ) -> None:
        """Validate if an invitation role is allowed"""

        # Only admins and owners can invite
        if not MembershipService._has_management_privileges(inviter_role):
            raise ValueError("Insufficient privileges to invite members")

        # Can't invite someone to a role higher than yours (except owners)
        role_hierarchy = MembershipService._get_role_hierarchy()
        inviter_level = role_hierarchy.get(inviter_role, 0)
        invited_level = role_hierarchy.get(invited_role, 0)

        if invited_level >= inviter_level and inviter_role != OrganizationRole.OWNER:
            raise ValueError("Cannot invite member to a role equal or higher than yours")

    @staticmethod
    def create_invitation_token() -> str:
        """Generate a secure invitation token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    @staticmethod
    def calculate_invitation_expiry(days: int = 7) -> datetime:
        """Calculate invitation expiry date"""
        return datetime.utcnow() + timedelta(days=days)

    @staticmethod
    def validate_invitation_acceptance(
        invitation: OrganizationInvitation,
        user_email: str
    ) -> None:
        """Validate if an invitation can be accepted"""

        if not invitation.is_pending():
            if invitation.is_expired():
                raise ValueError("Invitation has expired")
            else:
                raise ValueError("Invitation is no longer valid")

        if invitation.email.lower() != user_email.lower():
            raise ValueError("Invitation is for a different email address")

    @staticmethod
    def get_default_permissions_for_role(role: OrganizationRole) -> List[str]:
        """Get default permissions for a role"""
        permission_map = {
            OrganizationRole.OWNER: ["*"],
            OrganizationRole.ADMIN: [
                "manage_members",
                "manage_settings",
                "manage_billing",
                "read",
                "write"
            ],
            OrganizationRole.MEMBER: ["read", "write"],
            OrganizationRole.VIEWER: ["read"]
        }

        return permission_map.get(role, [])

    @staticmethod
    def validate_permissions(permissions: List[str], role: OrganizationRole) -> None:
        """Validate that permissions are appropriate for the role"""
        default_permissions = MembershipService.get_default_permissions_for_role(role)

        # For now, just ensure permissions don't exceed default role permissions
        # In a more complex system, you might have a permission registry
        if role != OrganizationRole.OWNER:  # Owner can have any permissions
            for permission in permissions:
                if permission not in default_permissions and permission != "*":
                    raise ValueError(f"Permission '{permission}' not allowed for role '{role.value}'")

    @staticmethod
    def _has_management_privileges(role: OrganizationRole) -> bool:
        """Check if role has management privileges"""
        return role in [OrganizationRole.ADMIN, OrganizationRole.OWNER]

    @staticmethod
    def _get_role_hierarchy() -> dict:
        """Get role hierarchy mapping"""
        return {
            OrganizationRole.VIEWER: 0,
            OrganizationRole.MEMBER: 1,
            OrganizationRole.ADMIN: 2,
            OrganizationRole.OWNER: 3
        }

    @staticmethod
    def is_role_upgrade(current_role: OrganizationRole, new_role: OrganizationRole) -> bool:
        """Check if role change is an upgrade"""
        hierarchy = MembershipService._get_role_hierarchy()
        current_level = hierarchy.get(current_role, 0)
        new_level = hierarchy.get(new_role, 0)
        return new_level > current_level

    @staticmethod
    def can_access_organization(
        user_role: Optional[OrganizationRole],
        required_role: OrganizationRole = OrganizationRole.MEMBER
    ) -> bool:
        """Check if user role meets required access level"""
        if not user_role:
            return False

        hierarchy = MembershipService._get_role_hierarchy()
        user_level = hierarchy.get(user_role, 0)
        required_level = hierarchy.get(required_role, 0)

        return user_level >= required_level