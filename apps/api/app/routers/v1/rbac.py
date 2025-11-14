"""
RBAC API Routes
Role-based access control and policy management
"""
from typing import List, Optional, Dict, Set
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from ...dependencies import get_db, get_current_user, get_redis
from ...services.rbac_service import RBACService
from ...models import User


# Pydantic schemas
class PermissionCheckRequest(BaseModel):
    permission: str
    organization_id: Optional[UUID] = None
    resource_id: Optional[UUID] = None
    context: Optional[Dict] = None


class BulkPermissionCheckRequest(BaseModel):
    permissions: List[str]
    organization_id: Optional[UUID] = None


class PolicyCreateRequest(BaseModel):
    name: str
    permission: str
    conditions: Dict
    organization_id: UUID


class PolicyUpdateRequest(BaseModel):
    name: Optional[str] = None
    permission: Optional[str] = None
    conditions: Optional[Dict] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    id: UUID
    organization_id: Optional[UUID]
    name: str
    permission: str
    conditions: Dict
    is_active: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


# Create router
router = APIRouter(prefix="/rbac", tags=["RBAC"])


@router.post("/check-permission")
async def check_permission(
    request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Check if user has specific permission"""
    service = RBACService(db, redis)
    has_permission = await service.check_permission(
        user_id=current_user.id,
        organization_id=request.organization_id,
        permission=request.permission,
        resource_id=request.resource_id,
        context=request.context
    )

    return {
        "has_permission": has_permission,
        "permission": request.permission,
        "user_id": current_user.id
    }


@router.post("/check-permissions")
async def check_permissions_bulk(
    request: BulkPermissionCheckRequest,
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Check multiple permissions at once"""
    service = RBACService(db, redis)
    results = await service.bulk_check_permissions(
        user_id=current_user.id,
        organization_id=request.organization_id,
        permissions=request.permissions
    )

    return {
        "permissions": results,
        "user_id": current_user.id
    }


@router.get("/permissions")
async def get_user_permissions(
    organization_id: Optional[UUID] = Query(None, description="Organization ID"),
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Get all permissions for current user"""
    service = RBACService(db, redis)
    permissions = await service.get_user_permissions(
        user_id=current_user.id,
        organization_id=organization_id
    )

    return {
        "permissions": list(permissions),
        "user_id": current_user.id,
        "organization_id": organization_id
    }


@router.get("/role")
async def get_user_role(
    organization_id: UUID = Query(..., description="Organization ID"),
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Get user's role in organization"""
    service = RBACService(db, redis)
    role = await service.get_user_role(
        user_id=current_user.id,
        organization_id=organization_id
    )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this organization"
        )

    return {
        "role": role,
        "user_id": current_user.id,
        "organization_id": organization_id,
        "role_level": service.get_role_level(role)
    }


@router.post("/policies", response_model=PolicyResponse)
async def create_policy(
    request: PolicyCreateRequest,
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Create new conditional access policy"""
    # Check permissions
    service = RBACService(db, redis)
    await service.enforce_permission(
        user_id=current_user.id,
        organization_id=request.organization_id,
        permission="policies:create"
    )

    policy = await service.create_policy(
        organization_id=request.organization_id,
        name=request.name,
        permission=request.permission,
        conditions=request.conditions,
        created_by=current_user.id
    )

    return policy


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID,
    request: PolicyUpdateRequest,
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Update existing policy"""
    service = RBACService(db, redis)

    # Get policy to check organization
    from ...models import RBACPolicy
    result = await db.execute(select(RBACPolicy).where(RBACPolicy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    # Check permissions
    await service.enforce_permission(
        user_id=current_user.id,
        organization_id=policy.organization_id,
        permission="policies:update"
    )

    # Update policy
    updates = request.dict(exclude_unset=True)
    updated_policy = await service.update_policy(
        policy_id=policy_id,
        updates=updates,
        updated_by=current_user.id
    )

    return updated_policy


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Delete policy (soft delete)"""
    service = RBACService(db, redis)

    # Get policy to check organization
    from ...models import RBACPolicy
    result = await db.execute(select(RBACPolicy).where(RBACPolicy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    # Check permissions
    await service.enforce_permission(
        user_id=current_user.id,
        organization_id=policy.organization_id,
        permission="policies:delete"
    )

    await service.delete_policy(policy_id)

    return {"message": "Policy deleted successfully"}


@router.get("/policies")
async def list_policies(
    organization_id: UUID = Query(..., description="Organization ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """List all policies for organization"""
    service = RBACService(db, redis)

    # Check permissions
    await service.enforce_permission(
        user_id=current_user.id,
        organization_id=organization_id,
        permission="policies:read"
    )

    from ...models import RBACPolicy
    stmt = select(RBACPolicy).where(
        RBACPolicy.organization_id == organization_id
    )

    if is_active is not None:
        stmt = stmt.where(RBACPolicy.is_active == is_active)

    result = await db.execute(stmt)
    policies = result.scalars().all()

    return {
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "permission": p.permission,
                "conditions": p.conditions,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in policies
        ],
        "total": len(policies)
    }


@router.post("/enforce")
async def enforce_permission(
    request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Enforce permission or return 403"""
    service = RBACService(db, redis)

    try:
        await service.enforce_permission(
            user_id=current_user.id,
            organization_id=request.organization_id,
            permission=request.permission,
            resource_id=request.resource_id,
            context=request.context
        )
        return {"status": "granted", "permission": request.permission}
    except HTTPException as e:
        if e.status_code == status.HTTP_403_FORBIDDEN:
            return {"status": "denied", "permission": request.permission, "reason": e.detail}
        raise