"""
Shared dependencies and utilities for organization routes
"""

import uuid
from typing import Optional
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, select

from app.database import get_db
from app.models import User, Organization, organization_members
from app.routers.v1.auth import get_current_user
from .schemas import OrganizationRole


async def get_user_organization_role(db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> Optional[str]:
    """Get user's role in an organization"""
    result = await db.execute(select(organization_members).where(
        and_(
            organization_members.c.user_id == user_id,
            organization_members.c.organization_id == org_id
        )
    ))
    member = result.first()

    return member.role if member else None


async def check_organization_permission(
    db: Session,
    user: User,
    org_id: uuid.UUID,
    required_role: str = "member"
) -> Organization:
    """Check if user has required permission in organization"""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Owner always has access
    if org.owner_id == user.id:
        return org

    # Check membership and role
    user_role = await get_user_organization_role(db, user.id, org_id)
    if not user_role:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    # Role hierarchy: owner > admin > member > guest
    role_hierarchy = {
        "guest": 0,
        "member": 1,
        "admin": 2,
        "owner": 3
    }

    if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return org


async def check_organization_admin_permission(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Organization:
    """Dependency to check admin permission for organization"""
    return await check_organization_permission(
        db, current_user, uuid.UUID(org_id), "admin"
    )


async def check_organization_member_permission(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Organization:
    """Dependency to check member permission for organization"""
    return await check_organization_permission(
        db, current_user, uuid.UUID(org_id), "member"
    )


async def check_organization_owner_permission(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Organization:
    """Dependency to check owner permission for organization"""
    result = await db.execute(select(Organization).where(Organization.id == uuid.UUID(org_id)))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organization owner can perform this action")

    return org


async def validate_unique_slug(db: Session, slug: str, exclude_org_id: Optional[uuid.UUID] = None) -> bool:
    """Validate that organization slug is unique"""
    stmt = select(Organization).where(Organization.slug == slug)

    if exclude_org_id:
        stmt = stmt.where(Organization.id != exclude_org_id)

    result = await db.execute(stmt)
    existing_org = result.scalar_one_or_none()
    if existing_org:
        raise HTTPException(status_code=400, detail="Organization slug already exists")

    return True


async def validate_invitation_email(db: Session, org_id: uuid.UUID, email: str) -> bool:
    """Validate invitation email (not already a member or pending invitation)"""
    from app.models import OrganizationInvitation

    # Check if user is already a member
    user_result = await db.execute(select(User).where(User.email == email))
    user_query = user_result.scalar_one_or_none()
    if user_query:
        member_result = await db.execute(select(organization_members).where(
            and_(
                organization_members.c.user_id == user_query.id,
                organization_members.c.organization_id == org_id
            )
        ))
        member_exists = member_result.first()

        if member_exists:
            raise HTTPException(status_code=400, detail="User is already a member of this organization")

    # Check if there's already a pending invitation
    invitation_result = await db.execute(select(OrganizationInvitation).where(
        and_(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.email == email,
            OrganizationInvitation.status == "pending"
        )
    ))
    pending_invitation = invitation_result.scalar_one_or_none()

    if pending_invitation:
        raise HTTPException(status_code=400, detail="There is already a pending invitation for this email")

    return True


def get_organization_permissions(role: str, custom_permissions: Optional[list] = None) -> list:
    """Get permissions for a given role"""
    base_permissions = {
        "guest": ["view_organization"],
        "member": ["view_organization", "view_members"],
        "admin": ["view_organization", "view_members", "manage_members", "manage_settings"],
        "owner": ["view_organization", "view_members", "manage_members", "manage_settings", "manage_billing", "delete_organization"]
    }

    permissions = base_permissions.get(role, [])

    if custom_permissions:
        permissions.extend(custom_permissions)

    return list(set(permissions))  # Remove duplicates