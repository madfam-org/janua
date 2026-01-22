"""
Organization Members API Routes
Complete member lifecycle management endpoints
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from ...dependencies import get_db, get_current_user, get_redis
from ...services.organization_member_service import OrganizationMemberService
from ...services.rbac_service import RBACService
from ...models import User


# Pydantic schemas
class MemberAddRequest(BaseModel):
    user_id: UUID
    role: str = "member"
    metadata: Optional[dict] = None


class MemberUpdateRoleRequest(BaseModel):
    new_role: str


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str = "member"
    expires_in_days: int = 7


class InvitationAcceptRequest(BaseModel):
    token: str


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: str
    status: str
    joined_at: str
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class InvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    role: str
    token: str
    status: str
    expires_at: str
    created_at: str

    class Config:
        from_attributes = True


# Create router
router = APIRouter(prefix="/organizations/{organization_id}/members", tags=["Organization Members"])


@router.get("", response_model=List[MemberResponse])
async def get_members(
    organization_id: UUID,
    include_removed: bool = Query(False, description="Include removed members"),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Get all organization members"""
    # Check permissions
    rbac = RBACService(db, redis)
    await rbac.enforce_permission(current_user.id, organization_id, "org:read")

    service = OrganizationMemberService(db, redis)
    members = await service.get_members(organization_id, include_removed)

    return members


@router.post("/add", response_model=MemberResponse)
async def add_member(
    organization_id: UUID,
    request: MemberAddRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Add a new member to organization"""
    # Check permissions
    rbac = RBACService(db, redis)
    await rbac.enforce_permission(current_user.id, organization_id, "users:create")

    service = OrganizationMemberService(db, redis)
    member = await service.add_member(
        organization_id=organization_id,
        user_id=request.user_id,
        role=request.role,
        invited_by=current_user.id,
        metadata=request.metadata,
    )

    return member


@router.delete("/{user_id}")
async def remove_member(
    organization_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Remove member from organization"""
    # Check permissions
    rbac = RBACService(db, redis)
    await rbac.enforce_permission(current_user.id, organization_id, "users:delete")

    # Prevent self-removal
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from organization",
        )

    service = OrganizationMemberService(db, redis)
    await service.remove_member(
        organization_id=organization_id, user_id=user_id, removed_by=current_user.id
    )

    return {"message": "Member removed successfully"}


@router.patch("/{user_id}/role", response_model=MemberResponse)
async def update_member_role(
    organization_id: UUID,
    user_id: UUID,
    request: MemberUpdateRoleRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Update member's role"""
    # Check permissions
    rbac = RBACService(db, redis)
    await rbac.enforce_permission(current_user.id, organization_id, "users:update")

    # Check if user has permission to assign this role
    current_role = await rbac.get_user_role(current_user.id, organization_id)
    if not rbac.has_higher_role(current_role, request.new_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign role higher than your own"
        )

    service = OrganizationMemberService(db, redis)
    member = await service.update_member_role(
        organization_id=organization_id,
        user_id=user_id,
        new_role=request.new_role,
        updated_by=current_user.id,
    )

    return member


@router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    organization_id: UUID,
    request: InvitationCreateRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Create invitation for new member"""
    # Check permissions
    rbac = RBACService(db, redis)
    await rbac.enforce_permission(current_user.id, organization_id, "users:invite")

    # Check if user can invite with this role
    current_role = await rbac.get_user_role(current_user.id, organization_id)
    if not rbac.has_higher_role(current_role, request.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot invite with role higher than your own",
        )

    service = OrganizationMemberService(db, redis)
    invitation = await service.create_invitation(
        organization_id=organization_id,
        email=request.email,
        role=request.role,
        invited_by=current_user.id,
        expires_in_days=request.expires_in_days,
    )

    return invitation


@router.post("/invitations/accept", response_model=MemberResponse)
async def accept_invitation(
    request: InvitationAcceptRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Accept invitation and become member"""
    service = OrganizationMemberService(db, redis)
    member = await service.accept_invitation(token=request.token, user_id=current_user.id)

    return member


@router.get("/check-permission")
async def check_permission(
    organization_id: UUID,
    permission: str = Query(..., description="Permission to check"),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Check if current user has specific permission"""
    service = OrganizationMemberService(db, redis)
    has_permission = await service.has_permission(
        user_id=current_user.id, organization_id=organization_id, required_role=permission
    )

    return {"has_permission": has_permission, "permission": permission}
