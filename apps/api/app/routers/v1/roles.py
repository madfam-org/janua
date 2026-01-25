"""
Role Management Router

REST endpoints for creating, managing, and assigning roles.
Roles define permission sets that can be assigned to organization members.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import OrganizationMember, User
from app.services.role_service import SYSTEM_ROLES, RoleService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "Not found"},
    },
)


# Pydantic schemas
class RoleCreate(BaseModel):
    """Schema for creating a new role"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Role name (e.g., 'Developer', 'Support')",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Role description",
    )
    permissions: List[str] = Field(
        default=[],
        description="List of permissions (e.g., ['users:read', 'org:read'])",
    )


class RoleUpdate(BaseModel):
    """Schema for updating a role"""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Role name",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Role description",
    )
    permissions: Optional[List[str]] = Field(
        default=None,
        description="List of permissions",
    )


class RoleResponse(BaseModel):
    """Role response schema"""

    id: str
    organization_id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Paginated list of roles"""

    items: List[RoleResponse]
    total: int
    page: int
    per_page: int


class RoleAssignment(BaseModel):
    """Schema for assigning a role to a user"""

    user_id: str = Field(..., description="ID of the user to assign the role to")
    role_name: str = Field(..., description="Name of the role to assign")


class MemberRoleResponse(BaseModel):
    """Response after role assignment"""

    user_id: str
    organization_id: str
    role: str
    message: str


class PermissionInfo(BaseModel):
    """Permission information"""

    permission: str
    description: str
    category: str


# Permission descriptions for documentation
PERMISSION_DESCRIPTIONS = {
    "*": ("Full access to all resources", "system"),
    "org:read": ("View organization details", "organization"),
    "org:update": ("Update organization settings", "organization"),
    "org:delete": ("Delete organization", "organization"),
    "users:read": ("View user profiles", "users"),
    "users:create": ("Invite new users", "users"),
    "users:update": ("Update user profiles", "users"),
    "users:delete": ("Remove users", "users"),
    "users:update:self": ("Update own profile", "users"),
    "users:read:self": ("View own profile", "users"),
    "settings:read": ("View settings", "settings"),
    "settings:update": ("Update settings", "settings"),
    "integrations:read": ("View integrations", "integrations"),
    "integrations:create": ("Create integrations", "integrations"),
    "integrations:update": ("Update integrations", "integrations"),
    "integrations:delete": ("Delete integrations", "integrations"),
    "webhooks:read": ("View webhooks", "webhooks"),
    "webhooks:create": ("Create webhooks", "webhooks"),
    "webhooks:update": ("Update webhooks", "webhooks"),
    "webhooks:delete": ("Delete webhooks", "webhooks"),
    "api_keys:read": ("View API keys", "api_keys"),
    "api_keys:create": ("Create API keys", "api_keys"),
    "api_keys:delete": ("Revoke API keys", "api_keys"),
    "billing:read": ("View billing", "billing"),
    "billing:update": ("Manage billing", "billing"),
}


async def get_user_organization_id(
    user: User,
    db: AsyncSession,
    organization_id: Optional[str] = None,
) -> uuid.UUID:
    """
    Get the organization ID for role operations.

    If organization_id is provided, validates user is admin of that org.
    Otherwise, returns the user's first organization where they are admin.
    """
    if organization_id:
        org_uuid = uuid.UUID(organization_id)
        # Validate user is admin of this organization
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == org_uuid,
                OrganizationMember.role.in_(["owner", "admin"]),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="Admin access required for this organization",
            )
        return org_uuid
    else:
        # Get user's first organization where they are admin
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.role.in_(["owner", "admin"]),
            ).order_by(OrganizationMember.created_at)
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=403,
                detail="Admin access required. You must be an admin of at least one organization.",
            )
        return membership.organization_id


@router.get("", response_model=RoleListResponse)
async def list_roles(
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    include_system: bool = Query(True, description="Include system roles"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all roles for an organization.

    Returns both system roles (owner, admin, member, viewer) and custom roles.
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    roles, total = await service.list_roles(
        organization_id=org_uuid,
        include_system=include_system,
        page=page,
        per_page=per_page,
    )

    return RoleListResponse(
        items=[
            RoleResponse(
                id=str(role.id),
                organization_id=str(role.organization_id),
                name=role.name,
                description=role.description,
                permissions=role.permissions or [],
                is_system=role.is_system,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
            for role in roles
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    data: RoleCreate,
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new custom role.

    Custom roles allow fine-grained permission control beyond the default
    system roles (owner, admin, member, viewer).
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    try:
        role = await service.create_role(
            organization_id=org_uuid,
            name=data.name,
            description=data.description,
            permissions=data.permissions,
            user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RoleResponse(
        id=str(role.id),
        organization_id=str(role.organization_id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/system", response_model=List[dict])
async def list_system_roles(
    current_user: User = Depends(get_current_user),
):
    """
    List all available system roles and their default permissions.

    System roles are predefined and cannot be modified:
    - **owner**: Full organization access
    - **admin**: Administrative access
    - **member**: Standard member access
    - **viewer**: Read-only access
    """
    return [
        {
            "name": role_data["name"],
            "key": role_key,
            "description": role_data["description"],
            "permissions": role_data["permissions"],
            "is_system": True,
        }
        for role_key, role_data in SYSTEM_ROLES.items()
    ]


@router.get("/permissions", response_model=List[PermissionInfo])
async def list_available_permissions(
    current_user: User = Depends(get_current_user),
):
    """
    List all available permissions that can be assigned to roles.

    Permissions follow the format `resource:action` (e.g., `users:read`).
    Wildcards are supported: `users:*` grants all user permissions.
    """
    return [
        PermissionInfo(
            permission=perm,
            description=desc[0],
            category=desc[1],
        )
        for perm, desc in PERMISSION_DESCRIPTIONS.items()
    ]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific role.
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")

    role = await service.get_role(role_uuid, org_uuid)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return RoleResponse(
        id=str(role.id),
        organization_id=str(role.organization_id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    data: RoleUpdate,
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a role.

    Note: System roles (owner, admin, member, viewer) can only have their
    description updated. Name and permissions cannot be modified.
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")

    try:
        role = await service.update_role(
            role_id=role_uuid,
            organization_id=org_uuid,
            name=data.name,
            description=data.description,
            permissions=data.permissions,
            user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return RoleResponse(
        id=str(role.id),
        organization_id=str(role.organization_id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: str,
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a custom role.

    System roles cannot be deleted.
    Roles with assigned members cannot be deleted.
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")

    try:
        success = await service.delete_role(role_uuid, org_uuid, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not success:
        raise HTTPException(status_code=404, detail="Role not found")

    return None


@router.post("/assign", response_model=MemberRoleResponse)
async def assign_role(
    data: RoleAssignment,
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a role to an organization member.

    The user must already be a member of the organization.
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    try:
        user_uuid = uuid.UUID(data.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    try:
        member = await service.assign_role_to_member(
            organization_id=org_uuid,
            user_id=user_uuid,
            role_name=data.role_name,
            assigned_by=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MemberRoleResponse(
        user_id=str(member.user_id),
        organization_id=str(member.organization_id),
        role=member.role,
        message=f"Role '{data.role_name}' assigned successfully",
    )


@router.post("/initialize", response_model=List[RoleResponse])
async def initialize_roles(
    organization_id: Optional[str] = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initialize system roles for an organization.

    This creates the default system roles (owner, admin, member, viewer)
    if they don't already exist. Usually called automatically when creating
    a new organization.
    """
    org_uuid = await get_user_organization_id(current_user, db, organization_id)
    service = RoleService(db)

    roles = await service.initialize_system_roles(org_uuid)

    return [
        RoleResponse(
            id=str(role.id),
            organization_id=str(role.organization_id),
            name=role.name,
            description=role.description,
            permissions=role.permissions or [],
            is_system=role.is_system,
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        for role in roles
    ]
