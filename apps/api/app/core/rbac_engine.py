"""
Role-Based Access Control (RBAC) Engine
Hierarchical permission system with dynamic role evaluation
"""

from enum import Enum
from functools import wraps
from typing import Dict, List, Optional, Set

import structlog
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import TenantContext
from app.models import OrganizationCustomRole, OrganizationMember
from app.models.enterprise import RoleType

logger = structlog.get_logger()


class ResourceType(Enum):
    """Resource types for permission checking"""

    ORGANIZATION = "organization"
    USER = "user"
    ROLE = "role"
    PROJECT = "project"
    API_KEY = "api_key"
    WEBHOOK = "webhook"
    AUDIT_LOG = "audit_log"
    BILLING = "billing"
    SETTINGS = "settings"


class Action(Enum):
    """Standard CRUD actions + admin"""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    ADMIN = "admin"  # Full control
    EXECUTE = "execute"  # For specific operations


class RBACEngine:
    """Core RBAC engine for permission evaluation"""

    def __init__(self):
        self._permission_cache: Dict[str, Set[str]] = {}
        self._role_hierarchy_cache: Dict[str, List[str]] = {}

    async def check_permission(
        self,
        session: AsyncSession,
        user_id: str,
        resource_type: ResourceType,
        action: Action,
        resource_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a user has permission to perform an action on a resource

        Args:
            session: Database session
            user_id: User performing the action
            resource_type: Type of resource being accessed
            action: Action being performed
            resource_id: Specific resource ID (for resource-level permissions)
            organization_id: Organization context

        Returns:
            Boolean indicating permission granted
        """
        try:
            # Get organization context
            org_id = organization_id or TenantContext.get_organization_id()
            if not org_id:
                logger.warning("No organization context for permission check")
                return False

            # Get user's membership and role
            membership = await self._get_user_membership(session, user_id, org_id)
            if not membership:
                logger.debug("User not a member of organization", user_id=user_id, org_id=org_id)
                return False

            # Check if user is suspended or inactive
            if membership.status != "active":
                logger.debug(
                    "User membership not active", user_id=user_id, status=membership.status
                )
                return False

            # Get all permissions for user (role + custom)
            permissions = await self._get_user_permissions(session, membership)

            # Check permission
            permission_string = self._build_permission_string(resource_type, action)

            # Check exact permission
            if permission_string in permissions:
                return True

            # Check wildcard permissions
            if self._check_wildcard_permission(permission_string, permissions):
                return True

            # Check admin override
            if f"{resource_type.value}:admin" in permissions or "*:admin" in permissions:
                return True

            # Resource-specific check if resource_id provided
            if resource_id:
                return await self._check_resource_permission(
                    session, user_id, resource_type, action, resource_id, permissions
                )

            return False

        except Exception as e:
            logger.error("Permission check failed", error=str(e))
            return False

    async def get_user_permissions(
        self, session: AsyncSession, user_id: str, organization_id: Optional[str] = None
    ) -> Set[str]:
        """Get all permissions for a user in an organization"""

        org_id = organization_id or TenantContext.get_organization_id()
        if not org_id:
            return set()

        membership = await self._get_user_membership(session, user_id, org_id)
        if not membership:
            return set()

        return await self._get_user_permissions(session, membership)

    async def has_any_permission(
        self,
        session: AsyncSession,
        user_id: str,
        permissions: List[str],
        organization_id: Optional[str] = None,
    ) -> bool:
        """Check if user has any of the specified permissions"""

        user_permissions = await self.get_user_permissions(session, user_id, organization_id)

        return any(perm in user_permissions for perm in permissions)

    async def has_all_permissions(
        self,
        session: AsyncSession,
        user_id: str,
        permissions: List[str],
        organization_id: Optional[str] = None,
    ) -> bool:
        """Check if user has all of the specified permissions"""

        user_permissions = await self.get_user_permissions(session, user_id, organization_id)

        return all(perm in user_permissions for perm in permissions)

    # Private helper methods

    async def _get_user_membership(
        self, session: AsyncSession, user_id: str, organization_id: str
    ) -> Optional[OrganizationMember]:
        """Get user's membership in organization"""

        # TODO: Implement Redis cache using key: f"membership:{user_id}:{organization_id}"
        # Check cache first
        # In production, implement Redis cache

        result = await session.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.user_id == user_id,
                    OrganizationMember.organization_id == organization_id,
                )
            )
        )

        return result.scalar_one_or_none()

    async def _get_user_permissions(
        self, session: AsyncSession, membership: OrganizationMember
    ) -> Set[str]:
        """Get all permissions for a membership (role + custom)"""

        permissions = set()

        # Get role permissions
        if membership.role_id:
            role_permissions = await self._get_role_permissions(session, membership.role_id)
            permissions.update(role_permissions)

        # Add custom permissions
        if membership.custom_permissions:
            permissions.update(membership.custom_permissions)

        return permissions

    async def _get_role_permissions(self, session: AsyncSession, role_id: str) -> Set[str]:
        """Get all permissions for a role (including inherited)"""

        # Check cache
        if role_id in self._permission_cache:
            return self._permission_cache[role_id]

        permissions = set()

        # Get role
        result = await session.execute(
            select(OrganizationCustomRole).where(OrganizationCustomRole.id == role_id)
        )
        role = result.scalar_one_or_none()

        if not role:
            return permissions

        # Add role's direct permissions
        if role.permissions:
            permissions.update(role.permissions)

        # Get inherited permissions from parent role
        if role.parent_role_id:
            parent_permissions = await self._get_role_permissions(session, role.parent_role_id)
            permissions.update(parent_permissions)

        # Cache the result
        self._permission_cache[role_id] = permissions

        return permissions

    def _build_permission_string(self, resource_type: ResourceType, action: Action) -> str:
        """Build permission string like 'users:read'"""
        return f"{resource_type.value}:{action.value}"

    def _check_wildcard_permission(self, permission: str, user_permissions: Set[str]) -> bool:
        """Check if permission matches any wildcard patterns"""

        resource, action = permission.split(":")

        # Check resource wildcard
        if f"*:{action}" in user_permissions:
            return True

        # Check action wildcard
        if f"{resource}:*" in user_permissions:
            return True

        # Check full wildcard
        if "*:*" in user_permissions:
            return True

        return False

    async def _check_resource_permission(
        self,
        session: AsyncSession,
        user_id: str,
        resource_type: ResourceType,
        action: Action,
        resource_id: str,
        permissions: Set[str],
    ) -> bool:
        """Check resource-specific permissions"""

        # Resource-specific permission string
        specific_perm = f"{resource_type.value}:{resource_id}:{action.value}"
        if specific_perm in permissions:
            return True

        # Check ownership-based permissions
        if f"{resource_type.value}:own:{action.value}" in permissions:
            return await self._check_resource_ownership(
                session, user_id, resource_type, resource_id
            )

        return False

    async def _check_resource_ownership(
        self, session: AsyncSession, user_id: str, resource_type: ResourceType, resource_id: str
    ) -> bool:
        """Check if user owns the resource"""

        # Implementation depends on resource type
        # This is a simplified example

        if resource_type == ResourceType.USER:
            return resource_id == user_id

        # Add other resource ownership checks as needed

        return False


class PermissionManager:
    """High-level permission management interface"""

    def __init__(self, rbac_engine: RBACEngine):
        self.rbac_engine = rbac_engine

    def require_permission(
        self, resource_type: ResourceType, action: Action, resource_id: Optional[str] = None
    ):
        """Decorator to require permission for endpoint"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract session and user from kwargs
                session = kwargs.get("db")
                user_id = kwargs.get("current_user_id")

                if not session or not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required"
                    )

                # Check permission
                has_permission = await self.rbac_engine.check_permission(
                    session=session,
                    user_id=user_id,
                    resource_type=resource_type,
                    action=action,
                    resource_id=resource_id,
                )

                if not has_permission:
                    logger.warning(
                        "Permission denied",
                        user_id=user_id,
                        resource=resource_type.value,
                        action=action.value,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {resource_type.value}:{action.value}",
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def require_any_permission(self, permissions: List[str]):
        """Decorator to require any of the listed permissions"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                session = kwargs.get("db")
                user_id = kwargs.get("current_user_id")

                if not session or not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required"
                    )

                has_permission = await self.rbac_engine.has_any_permission(
                    session=session, user_id=user_id, permissions=permissions
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: requires one of {permissions}",
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator


# Subscription tier definitions (synced from Dhanam)
# These are PARALLEL to org roles — a user is "admin" AND "pro_tier" simultaneously.
# Org role = what they can do. Tier = what features/limits the org has access to.
# Stored on Organization.subscription_tier, not as a user-level role.
TIER_ROLES = {
    "free_tier": {
        "features": ["basic_auth", "email_password"],
        "mau_limit": 2000,
    },
    "pro_tier": {
        "features": ["basic_auth", "email_password", "sso", "mfa", "webhooks", "custom_roles"],
        "mau_limit": 10000,
    },
    "scale_tier": {
        "features": [
            "basic_auth",
            "email_password",
            "sso",
            "mfa",
            "webhooks",
            "custom_roles",
            "scim",
            "audit_log",
        ],
        "mau_limit": 50000,
    },
    "enterprise_tier": {
        "features": ["*"],
        "mau_limit": None,
    },
}

VALID_TIERS = set(TIER_ROLES.keys())


class DefaultRoles:
    """Default system roles and their permissions"""

    OWNER = {
        "name": "Owner",
        "description": "Full control over the organization",
        "permissions": ["*:*"],  # All permissions
        "type": RoleType.SYSTEM,
        "priority": 100,
    }

    ADMIN = {
        "name": "Admin",
        "description": "Administrative access",
        "permissions": [
            "organization:*",
            "user:*",
            "role:*",
            "project:*",
            "settings:*",
            "webhook:*",
            "api_key:*",
        ],
        "type": RoleType.SYSTEM,
        "priority": 90,
    }

    MEMBER = {
        "name": "Member",
        "description": "Regular member access",
        "permissions": [
            "organization:read",
            "user:read",
            "user:own:update",  # Can update own profile
            "project:read",
            "project:create",
            "project:own:*",  # Full control over own projects
        ],
        "type": RoleType.SYSTEM,
        "priority": 50,
    }

    VIEWER = {
        "name": "Viewer",
        "description": "Read-only access",
        "permissions": ["organization:read", "user:read", "project:read", "settings:read"],
        "type": RoleType.SYSTEM,
        "priority": 10,
    }


# Global instances
rbac_engine = RBACEngine()
permission_manager = PermissionManager(rbac_engine)


# Convenience decorators
require_permission = permission_manager.require_permission
require_any_permission = permission_manager.require_any_permission


# Initialization function for creating default roles
async def initialize_default_roles(session: AsyncSession, organization_id: str):
    """Create default roles for a new organization"""

    default_roles = [
        DefaultRoles.OWNER,
        DefaultRoles.ADMIN,
        DefaultRoles.MEMBER,
        DefaultRoles.VIEWER,
    ]

    for role_data in default_roles:
        role = OrganizationCustomRole(
            organization_id=organization_id,
            name=role_data["name"],
            permissions=role_data["permissions"],
        )
        session.add(role)

    await session.commit()
    logger.info("Default roles created", organization_id=organization_id)
