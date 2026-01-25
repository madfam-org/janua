"""
Role Management Service

Business logic for creating, updating, and managing roles.
Works alongside RBACService for permission enforcement.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, OrganizationMember, Role, User

logger = logging.getLogger(__name__)


# Default system roles with their permissions
SYSTEM_ROLES = {
    "owner": {
        "name": "Owner",
        "description": "Organization owner with full access",
        "permissions": ["*"],
        "is_system": True,
    },
    "admin": {
        "name": "Admin",
        "description": "Organization administrator",
        "permissions": [
            "org:read",
            "org:update",
            "users:*",
            "settings:read",
            "settings:update",
            "integrations:*",
            "webhooks:*",
            "api_keys:*",
        ],
        "is_system": True,
    },
    "member": {
        "name": "Member",
        "description": "Regular organization member",
        "permissions": [
            "org:read",
            "users:read",
            "users:update:self",
            "settings:read",
        ],
        "is_system": True,
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access",
        "permissions": [
            "org:read",
            "users:read:self",
        ],
        "is_system": True,
    },
}


class RoleService:
    """Service for role management operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_roles(
        self,
        organization_id: uuid.UUID,
        include_system: bool = True,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Role], int]:
        """
        List roles for an organization.

        Args:
            organization_id: The organization ID
            include_system: Whether to include system roles
            page: Page number (1-indexed)
            per_page: Items per page (max 100)

        Returns:
            Tuple of (list of Role models, total count)
        """
        page = max(1, page)
        per_page = min(max(1, per_page), 100)
        offset = (page - 1) * per_page

        # Build query
        query = select(Role).where(Role.organization_id == organization_id)

        if not include_system:
            query = query.where(Role.is_system == False)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(Role.is_system.desc(), Role.name).offset(offset).limit(per_page)
        result = await self.db.execute(query)
        roles = list(result.scalars().all())

        return roles, total

    async def get_role(
        self,
        role_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Optional[Role]:
        """
        Get a single role by ID.

        Args:
            role_id: The role ID
            organization_id: The organization ID (for authorization)

        Returns:
            The Role model if found, None otherwise
        """
        result = await self.db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_role_by_name(
        self,
        name: str,
        organization_id: uuid.UUID,
    ) -> Optional[Role]:
        """
        Get a role by name within an organization.

        Args:
            name: The role name
            organization_id: The organization ID

        Returns:
            The Role model if found, None otherwise
        """
        result = await self.db.execute(
            select(Role).where(
                Role.name.ilike(name),
                Role.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_role(
        self,
        organization_id: uuid.UUID,
        name: str,
        description: Optional[str],
        permissions: List[str],
        user: User,
    ) -> Role:
        """
        Create a new custom role.

        Args:
            organization_id: The organization ID
            name: Role name
            description: Role description
            permissions: List of permission strings
            user: User creating the role

        Returns:
            The created Role model
        """
        # Check for duplicate name
        existing = await self.get_role_by_name(name, organization_id)
        if existing:
            raise ValueError(f"Role '{name}' already exists in this organization")

        # Validate permission format
        for perm in permissions:
            if ":" not in perm and perm != "*":
                raise ValueError(f"Invalid permission format: {perm}")

        # Create role
        role = Role(
            id=uuid.uuid4(),
            organization_id=organization_id,
            name=name,
            description=description,
            permissions=permissions,
            is_system=False,
        )

        self.db.add(role)

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization_id,
            action="role_created",
            resource_type="role",
            resource_id=str(role.id),
            details={
                "role_name": name,
                "permissions": permissions,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(role)

        logger.info(
            "Role created",
            extra={
                "role_id": str(role.id),
                "role_name": name,
                "organization_id": str(organization_id),
            },
        )

        return role

    async def update_role(
        self,
        role_id: uuid.UUID,
        organization_id: uuid.UUID,
        name: Optional[str],
        description: Optional[str],
        permissions: Optional[List[str]],
        user: User,
    ) -> Optional[Role]:
        """
        Update a role.

        Args:
            role_id: The role ID
            organization_id: The organization ID
            name: New name (optional)
            description: New description (optional)
            permissions: New permissions list (optional)
            user: User making the update

        Returns:
            The updated Role model, or None if not found
        """
        role = await self.get_role(role_id, organization_id)
        if not role:
            return None

        # System roles can only have description updated
        if role.is_system and (name or permissions):
            raise ValueError("Cannot modify name or permissions of system roles")

        changes = {}

        if name and name != role.name:
            # Check for duplicate name
            existing = await self.get_role_by_name(name, organization_id)
            if existing and existing.id != role_id:
                raise ValueError(f"Role '{name}' already exists in this organization")
            changes["name"] = {"old": role.name, "new": name}
            role.name = name

        if description is not None and description != role.description:
            changes["description"] = {"old": role.description, "new": description}
            role.description = description

        if permissions is not None and permissions != role.permissions:
            # Validate permission format
            for perm in permissions:
                if ":" not in perm and perm != "*":
                    raise ValueError(f"Invalid permission format: {perm}")
            changes["permissions"] = {"old": role.permissions, "new": permissions}
            role.permissions = permissions

        if changes:
            role.updated_at = datetime.utcnow()

            # Create audit log
            audit_log = AuditLog(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_id=organization_id,
                action="role_updated",
                resource_type="role",
                resource_id=str(role.id),
                details={
                    "role_name": role.name,
                    "changes": changes,
                },
            )
            self.db.add(audit_log)

            await self.db.commit()
            await self.db.refresh(role)

            logger.info(f"Role updated: {role.id} by user {user.id}")

        return role

    async def delete_role(
        self,
        role_id: uuid.UUID,
        organization_id: uuid.UUID,
        user: User,
    ) -> bool:
        """
        Delete a role.

        Args:
            role_id: The role ID
            organization_id: The organization ID
            user: User performing the deletion

        Returns:
            True if deleted, False if not found
        """
        role = await self.get_role(role_id, organization_id)
        if not role:
            return False

        if role.is_system:
            raise ValueError("Cannot delete system roles")

        # Check if any members have this role
        result = await self.db.execute(
            select(func.count()).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == role.name,
            )
        )
        member_count = result.scalar() or 0

        if member_count > 0:
            raise ValueError(
                f"Cannot delete role '{role.name}': {member_count} member(s) still have this role"
            )

        role_name = role.name

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization_id,
            action="role_deleted",
            resource_type="role",
            resource_id=str(role.id),
            details={
                "role_name": role_name,
            },
        )
        self.db.add(audit_log)

        await self.db.delete(role)
        await self.db.commit()

        logger.info(f"Role deleted: {role_id} ({role_name}) by user {user.id}")

        return True

    async def assign_role_to_member(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role_name: str,
        assigned_by: User,
    ) -> OrganizationMember:
        """
        Assign a role to an organization member.

        Args:
            organization_id: The organization ID
            user_id: The user ID to assign the role to
            role_name: The role name to assign
            assigned_by: User performing the assignment

        Returns:
            The updated OrganizationMember
        """
        # Verify role exists (system or custom)
        role = await self.get_role_by_name(role_name, organization_id)
        if not role and role_name not in SYSTEM_ROLES:
            raise ValueError(f"Role '{role_name}' does not exist")

        # Get member
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise ValueError("User is not a member of this organization")

        old_role = member.role
        member.role = role_name
        member.updated_at = datetime.utcnow()

        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=assigned_by.id,
            organization_id=organization_id,
            action="member_role_changed",
            resource_type="organization_member",
            resource_id=str(member.id),
            details={
                "target_user_id": str(user_id),
                "old_role": old_role,
                "new_role": role_name,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(member)

        logger.info(
            "Role assigned",
            extra={
                "role_name": role_name,
                "user_id": str(user_id),
                "organization_id": str(organization_id),
            },
        )

        return member

    async def initialize_system_roles(
        self,
        organization_id: uuid.UUID,
    ) -> List[Role]:
        """
        Initialize system roles for a new organization.

        Should be called when creating a new organization.

        Args:
            organization_id: The organization ID

        Returns:
            List of created system roles
        """
        created_roles = []

        for role_key, role_data in SYSTEM_ROLES.items():
            # Check if already exists
            existing = await self.get_role_by_name(role_data["name"], organization_id)
            if existing:
                continue

            role = Role(
                id=uuid.uuid4(),
                organization_id=organization_id,
                name=role_data["name"],
                description=role_data["description"],
                permissions=role_data["permissions"],
                is_system=role_data["is_system"],
            )
            self.db.add(role)
            created_roles.append(role)

        if created_roles:
            await self.db.commit()
            for role in created_roles:
                await self.db.refresh(role)

        return created_roles

    async def get_role_permissions(
        self,
        role_name: str,
        organization_id: uuid.UUID,
    ) -> List[str]:
        """
        Get all permissions for a role.

        Args:
            role_name: The role name
            organization_id: The organization ID

        Returns:
            List of permission strings
        """
        # Check custom role first
        role = await self.get_role_by_name(role_name, organization_id)
        if role:
            return role.permissions or []

        # Fall back to system role defaults
        system_role = SYSTEM_ROLES.get(role_name.lower())
        if system_role:
            return system_role["permissions"]

        return []
