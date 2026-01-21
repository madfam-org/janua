"""
Policy management and evaluation API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, select, delete

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.policy import (
    Policy, Role, UserRole, RolePolicy,
    PolicyCreate, PolicyUpdate, PolicyResponse,
    PolicyEvaluateRequest, PolicyEvaluateResponse,
    RoleCreate, RoleResponse
)
from app.services.policy_engine import PolicyEngine
from app.services.cache import CacheService
from app.services.audit_logger import AuditLogger, AuditAction


router = APIRouter(prefix="/v1/policies", tags=["policies"])


@router.post("/", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new policy (admin only).
    """
    # Create new policy
    policy = Policy(
        tenant_id=current_user.tenant_id,
        name=policy_data.name,
        description=policy_data.description,
        rules=policy_data.rules,
        effect=policy_data.effect.value,
        priority=policy_data.priority,
        target_type=policy_data.target_type.value if policy_data.target_type else None,
        target_id=policy_data.target_id,
        resource_type=policy_data.resource_type,
        resource_pattern=policy_data.resource_pattern,
        actions=policy_data.actions,
        conditions=policy_data.conditions,
        expires_at=policy_data.expires_at
    )
    
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    
    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.POLICY_CREATE,
        user_id=str(current_user.id),
        resource_type="policy",
        resource_id=str(policy.id),
        details={"policy_name": policy.name}
    )
    
    return PolicyResponse.from_orm(policy)


@router.get("/", response_model=List[PolicyResponse])
async def list_policies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    target_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all policies (admin only).
    """
    stmt = select(Policy).where(
        Policy.tenant_id == current_user.tenant_id
    )

    if target_type:
        stmt = stmt.where(Policy.target_type == target_type)

    if resource_type:
        stmt = stmt.where(Policy.resource_type == resource_type)

    if enabled is not None:
        stmt = stmt.where(Policy.enabled == enabled)

    result = await db.execute(stmt.offset(skip).limit(limit))
    policies = result.scalars().all()
    
    return [PolicyResponse.from_orm(p) for p in policies]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get a specific policy by ID (admin only).
    """
    result = await db.execute(select(Policy).where(
        and_(
            Policy.id == policy_id,
            Policy.tenant_id == current_user.tenant_id
        )
    ))
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )
    
    return PolicyResponse.from_orm(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    policy_update: PolicyUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update a policy (admin only).
    """
    result = await db.execute(select(Policy).where(
        and_(
            Policy.id == policy_id,
            Policy.tenant_id == current_user.tenant_id
        )
    ))
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )
    
    # Update fields
    update_data = policy_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(policy, field):
            setattr(policy, field, value)
    
    # Increment version
    policy.version += 1
    
    await db.commit()
    await db.refresh(policy)
    
    # Clear cache for this policy
    cache = CacheService()
    await cache.delete_pattern(f"policy:eval:*")
    
    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.POLICY_UPDATE,
        user_id=str(current_user.id),
        resource_type="policy",
        resource_id=str(policy.id),
        details={"updated_fields": list(update_data.keys())}
    )
    
    return PolicyResponse.from_orm(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a policy (admin only).
    """
    result = await db.execute(select(Policy).where(
        and_(
            Policy.id == policy_id,
            Policy.tenant_id == current_user.tenant_id
        )
    ))
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )
    
    # Delete policy evaluations first
    await db.execute(
        delete(PolicyEvaluation).where(
            PolicyEvaluation.policy_id == policy_id
        )
    )

    # Delete role-policy mappings
    await db.execute(
        delete(RolePolicy).where(
            RolePolicy.policy_id == policy_id
        )
    )
    
    # Delete the policy
    db.delete(policy)
    await db.commit()
    
    # Clear cache
    cache = CacheService()
    await cache.delete_pattern(f"policy:eval:*")
    
    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.POLICY_DELETE,
        user_id=str(current_user.id),
        resource_type="policy",
        resource_id=str(policy_id),
        details={"policy_name": policy.name}
    )
    
    return None


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_policies(
    request: PolicyEvaluateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluate policies for a given request.
    """
    # Initialize policy engine
    cache = CacheService()
    engine = PolicyEngine(db, cache)
    
    # Add user context to request if not present
    if not request.context:
        request.context = {}
    
    request.context.update({
        "user_id": str(current_user.id),
        "tenant_id": str(current_user.tenant_id),
        "organization_id": str(current_user.organization_id) if current_user.organization_id else None
    })
    
    # Evaluate policies
    response = await engine.evaluate(
        request=request,
        tenant_id=str(current_user.tenant_id)
    )
    
    return response


# Role management endpoints

@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new role (admin only).
    """
    # Check if role name already exists
    result = await db.execute(select(Role).where(
        and_(
            Role.tenant_id == current_user.tenant_id,
            Role.name == role_data.name
        )
    ))
    existing_role = result.scalar_one_or_none()
    
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )
    
    # Create new role
    role = Role(
        tenant_id=current_user.tenant_id,
        organization_id=role_data.organization_id if role_data.organization_id else None,
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions
    )
    
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.ROLE_CREATE,
        user_id=str(current_user.id),
        resource_type="role",
        resource_id=str(role.id),
        details={"role_name": role.name}
    )
    
    return RoleResponse.from_orm(role)


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    organization_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all roles.
    """
    stmt = select(Role).where(
        Role.tenant_id == current_user.tenant_id
    )

    if organization_id:
        stmt = stmt.where(
            or_(
                Role.organization_id == organization_id,
                Role.organization_id == None  # Include tenant-level roles
            )
        )

    result = await db.execute(stmt.offset(skip).limit(limit))
    roles = result.scalars().all()
    
    return [RoleResponse.from_orm(r) for r in roles]


@router.post("/roles/{role_id}/assign")
async def assign_role_to_user(
    role_id: str,
    user_id: str,
    organization_id: Optional[str] = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Assign a role to a user (admin only).
    """
    # Verify role exists
    role_result = await db.execute(select(Role).where(
        and_(
            Role.id == role_id,
            Role.tenant_id == current_user.tenant_id
        )
    ))
    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if assignment already exists
    existing_result = await db.execute(select(UserRole).where(
        and_(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.organization_id == organization_id
        )
    ))
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role already assigned to user"
        )
    
    # Create assignment
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        organization_id=organization_id,
        scope="organization" if organization_id else "tenant"
    )
    
    db.add(user_role)
    await db.commit()
    
    # Clear permission cache for user
    cache = CacheService()
    await cache.delete(f"user:permissions:{user_id}")
    
    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.ROLE_ASSIGN,
        user_id=str(current_user.id),
        resource_type="user_role",
        resource_id=str(user_role.id),
        details={
            "role_name": role.name,
            "assigned_to": user_id
        }
    )
    
    return {"message": "Role assigned successfully"}


@router.delete("/roles/{role_id}/unassign")
async def unassign_role_from_user(
    role_id: str,
    user_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Remove a role from a user (admin only).
    """
    # Find assignment
    result = await db.execute(select(UserRole).where(
        and_(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        )
    ))
    user_role = result.scalar_one_or_none()
    
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found"
        )
    
    # Delete assignment
    db.delete(user_role)
    await db.commit()
    
    # Clear permission cache for user
    cache = CacheService()
    await cache.delete(f"user:permissions:{user_id}")
    
    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.ROLE_UNASSIGN,
        user_id=str(current_user.id),
        resource_type="user_role",
        resource_id=str(user_role.id),
        details={
            "role_id": role_id,
            "unassigned_from": user_id
        }
    )
    
    return {"message": "Role unassigned successfully"}