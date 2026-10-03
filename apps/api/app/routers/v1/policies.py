"""
Policy management and evaluation API endpoints.

Route declaration order is load-bearing here. FastAPI/Starlette match routes in
declaration order and return the FIRST full match, so a parametric route such as
``GET /{policy_id}`` will swallow every sibling literal path declared after it
(``/roles`` would be parsed as a policy id). All literal paths are therefore
declared first and the ``/{policy_id}`` handlers are kept last in this module.
See ``tests/unit/routers/test_policies_route_order.py``.
"""

import enum
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import OrganizationMember
from app.models.policy import (
    Policy,
    PolicyCreate,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluation,
    PolicyResponse,
    PolicyUpdate,
    Role,
    RoleCreate,
    RolePolicy,
    RoleResponse,
    UserRole,
)
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.cache import CacheService
from app.services.policy_engine import PolicyEngine

router = APIRouter(prefix="/v1/policies", tags=["policies"])


def _member_org_ids(user):
    """Subquery of the organization ids `user` belongs to.

    `organization_id` is the tenancy column on `policies`, `roles` and
    `organization_members` alike — none of those tables has a `tenant_id`
    column. Scoping every policy query through membership keeps one
    organization's policies invisible to another's admins.
    """
    return select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)


async def _resolve_organization_id(db, user, requested: Optional[str]) -> str:
    """Pick (and authorize) the organization a new policy belongs to.

    An explicit `organization_id` must be one the caller belongs to, otherwise
    an admin of org A could plant a policy in org B. When omitted, it is only
    unambiguous if the caller belongs to exactly one organization.
    """
    result = await db.execute(_member_org_ids(user))
    org_ids = [str(row) for row in result.scalars().all()]

    if requested:
        if str(requested) not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of the requested organization",
            )
        return str(requested)

    if len(org_ids) == 1:
        return org_ids[0]

    if not org_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Caller belongs to no organization; organization_id is required",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Caller belongs to multiple organizations; organization_id is required",
    )


@router.post("/", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Create a new policy (admin only).
    """
    organization_id = await _resolve_organization_id(db, current_user, policy_data.organization_id)

    # Create new policy
    policy = Policy(
        organization_id=organization_id,
        name=policy_data.name,
        description=policy_data.description,
        rules=policy_data.rules,
        effect=policy_data.effect.value,
        priority=policy_data.priority,
        enabled=policy_data.enabled,
        version=1,
        target_type=policy_data.target_type.value if policy_data.target_type else None,
        target_id=policy_data.target_id,
        resource_type=policy_data.resource_type,
        resource_pattern=policy_data.resource_pattern,
        actions=policy_data.actions,
        conditions=policy_data.conditions,
        expires_at=policy_data.expires_at,
    )

    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        event_type=AuditAction.POLICY_CREATE,
        tenant_id=organization_id,
        identity_id=str(current_user.id),
        organization_id=organization_id,
        resource_type="policy",
        resource_id=str(policy.id),
        details={"policy_name": policy.name},
    )
    # The logger flushes into this session; commit so the audit row persists.
    await db.commit()

    return PolicyResponse.from_orm(policy)


@router.get("/", response_model=List[PolicyResponse])
async def list_policies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    target_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all policies (admin only).
    """
    stmt = select(Policy).where(Policy.organization_id.in_(_member_org_ids(current_user)))

    if target_type:
        stmt = stmt.where(Policy.target_type == target_type)

    if resource_type:
        stmt = stmt.where(Policy.resource_type == resource_type)

    if enabled is not None:
        stmt = stmt.where(Policy.enabled == enabled)

    result = await db.execute(stmt.offset(skip).limit(limit))
    policies = result.scalars().all()

    return [PolicyResponse.from_orm(p) for p in policies]


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_policies(
    request: PolicyEvaluateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluate policies for a given request.
    """
    # Initialize policy engine
    cache = CacheService()
    engine = PolicyEngine(db, cache)

    # Evaluation is scoped to one organization. `User` has no `organization_id`
    # column (reading it here used to raise AttributeError); membership is the
    # only link between a user and an organization.
    result = await db.execute(_member_org_ids(current_user).limit(1))
    organization_id = result.scalar_one_or_none()

    if organization_id is None:
        # Fail closed: no organization means no policies can apply.
        return PolicyEvaluateResponse(
            allowed=False,
            reason="Caller belongs to no organization",
        )

    # Default the subject to the caller rather than evaluating an empty subject.
    if not request.subject_id:
        request.subject_id = str(current_user.id)

    # Add user context to request if not present
    if not request.context:
        request.context = {}

    request.context.update(
        {
            "user_id": str(current_user.id),
            "tenant_id": str(current_user.tenant_id) if current_user.tenant_id else None,
            "organization_id": str(organization_id),
        }
    )

    # Evaluate policies
    return await engine.evaluate(request=request, organization_id=str(organization_id))


# Role management endpoints
#
# These literal paths MUST stay above the `/{policy_id}` handlers at the bottom
# of this module, otherwise `/policies/roles` is matched as a policy id.


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Create a new role (admin only).

    Scoped by `organization_id` for the same reason `list_roles` is: `roles` has
    no `tenant_id` column, and `roles.organization_id` is NOT NULL, so the old
    `organization_id=None` fallback could not have inserted a row either.
    """
    organization_id = await _resolve_organization_id(db, current_user, role_data.organization_id)

    # Check if role name already exists within the organization
    result = await db.execute(
        select(Role).where(
            and_(Role.organization_id == organization_id, Role.name == role_data.name)
        )
    )
    existing_role = result.scalar_one_or_none()

    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Role with this name already exists"
        )

    # Create new role
    role = Role(
        organization_id=organization_id,
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        event_type=AuditAction.ROLE_CREATE,
        tenant_id=organization_id,
        identity_id=str(current_user.id),
        organization_id=organization_id,
        resource_type="role",
        resource_id=str(role.id),
        details={"role_name": role.name},
    )
    # The logger flushes into this session; commit so the audit row persists.
    await db.commit()

    return RoleResponse.from_orm(role)


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    organization_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List roles visible to the current user.

    Scoping goes through organization membership because `organization_id` is
    the only tenancy column that exists on the `roles` table (see
    `app.models.Role` and alembic 000_init). The previous `Role.tenant_id`
    filter referenced a column that has never existed and raised AttributeError
    at request time, so this handler could not have returned 200 even once it
    was reachable.
    """
    member_org_ids = select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == current_user.id
    )

    stmt = select(Role).where(Role.organization_id.in_(member_org_ids))

    if organization_id:
        stmt = stmt.where(Role.organization_id == organization_id)

    result = await db.execute(stmt.offset(skip).limit(limit))
    roles = result.scalars().all()

    return [RoleResponse.from_orm(r) for r in roles]


@router.post("/roles/{role_id}/assign")
async def assign_role_to_user(
    role_id: str,
    user_id: str,
    organization_id: Optional[str] = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Assign a role to a user (admin only).
    """
    # Verify the role exists inside an organization the caller belongs to.
    role_result = await db.execute(
        select(Role).where(
            and_(
                Role.id == role_id,
                Role.organization_id.in_(_member_org_ids(current_user)),
            )
        )
    )
    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Check if assignment already exists
    existing_result = await db.execute(
        select(UserRole).where(
            and_(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.organization_id == organization_id,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Role already assigned to user"
        )

    # Create assignment
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        organization_id=organization_id,
        scope="organization" if organization_id else "tenant",
    )

    db.add(user_role)
    await db.commit()

    # Clear permission cache for user
    cache = CacheService()
    await cache.delete(f"user:permissions:{user_id}")

    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        event_type=AuditAction.ROLE_ASSIGN,
        tenant_id=str(role.organization_id) if role.organization_id else "",
        identity_id=str(current_user.id),
        organization_id=str(role.organization_id) if role.organization_id else None,
        resource_type="user_role",
        resource_id=str(user_role.id),
        details={"role_name": role.name, "assigned_to": user_id},
    )
    # The logger flushes into this session; commit so the audit row persists.
    await db.commit()

    return {"message": "Role assigned successfully"}


@router.delete("/roles/{role_id}/unassign")
async def unassign_role_from_user(
    role_id: str, user_id: str, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Remove a role from a user (admin only).
    """
    # Find assignment
    result = await db.execute(
        select(UserRole).where(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
    )
    user_role = result.scalar_one_or_none()

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found"
        )

    # Capture before the row goes away — `user_role` is expired after commit.
    user_role_id = str(user_role.id)
    organization_id = str(user_role.organization_id) if user_role.organization_id else ""

    # Delete assignment. `AsyncSession.delete` must be awaited.
    await db.delete(user_role)
    await db.commit()

    # Clear permission cache for user
    cache = CacheService()
    await cache.delete(f"user:permissions:{user_id}")

    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        event_type=AuditAction.ROLE_UNASSIGN,
        tenant_id=organization_id,
        identity_id=str(current_user.id),
        organization_id=organization_id or None,
        resource_type="user_role",
        resource_id=user_role_id,
        details={"role_id": role_id, "unassigned_from": user_id},
    )
    # The logger flushes into this session; commit so the audit row persists.
    await db.commit()

    return {"message": "Role unassigned successfully"}


# ---------------------------------------------------------------------------
# Parametric single-policy routes.
#
# KEEP THESE LAST. `/{policy_id}` matches any single path segment, so every
# literal sibling route (`/roles`, `/evaluate`, ...) declared BELOW one of these
# becomes permanently unreachable — Starlette returns the first full match in
# declaration order. Add new literal `/policies/<name>` routes above this block.
# ---------------------------------------------------------------------------


async def _get_scoped_policy(db, current_user, policy_id: str) -> Policy:
    """Load a policy the caller's organizations own, or 404.

    A policy belonging to another organization is reported as missing rather
    than forbidden, so the endpoint does not confirm that the id exists.
    """
    result = await db.execute(
        select(Policy).where(
            and_(
                Policy.id == policy_id,
                Policy.organization_id.in_(_member_org_ids(current_user)),
            )
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    return policy


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Get a specific policy by ID (admin only).
    """
    policy = await _get_scoped_policy(db, current_user, policy_id)

    return PolicyResponse.from_orm(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    policy_update: PolicyUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update a policy (admin only).
    """
    policy = await _get_scoped_policy(db, current_user, policy_id)

    # Update fields. Enums arrive as PolicyEffect/PolicyTargetType; the columns
    # are plain strings, so unwrap them before assigning.
    update_data = policy_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if not hasattr(policy, field):
            continue
        setattr(policy, field, value.value if isinstance(value, enum.Enum) else value)

    # Increment version
    policy.version = (policy.version or 0) + 1

    await db.commit()
    await db.refresh(policy)

    # Clear cache for this policy
    cache = CacheService()
    await cache.delete_pattern("policy:eval:*")

    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        event_type=AuditAction.POLICY_UPDATE,
        tenant_id=str(policy.organization_id) if policy.organization_id else "",
        identity_id=str(current_user.id),
        organization_id=str(policy.organization_id) if policy.organization_id else None,
        resource_type="policy",
        resource_id=str(policy.id),
        details={"updated_fields": list(update_data.keys())},
    )
    # The logger flushes into this session; commit so the audit row persists.
    await db.commit()

    return PolicyResponse.from_orm(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Delete a policy (admin only).
    """
    policy = await _get_scoped_policy(db, current_user, policy_id)

    # Capture before the row goes away — `policy` is expired after commit.
    policy_name = policy.name
    organization_id = str(policy.organization_id) if policy.organization_id else ""

    # Delete policy evaluations first
    await db.execute(delete(PolicyEvaluation).where(PolicyEvaluation.policy_id == policy_id))

    # Delete role-policy mappings
    await db.execute(delete(RolePolicy).where(RolePolicy.policy_id == policy_id))

    # Delete the policy. `AsyncSession.delete` is a coroutine — the un-awaited
    # call this replaced left the row in place and only emitted a warning.
    await db.delete(policy)
    await db.commit()

    # Clear cache
    cache = CacheService()
    await cache.delete_pattern("policy:eval:*")

    # Log audit event
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        event_type=AuditAction.POLICY_DELETE,
        tenant_id=organization_id,
        identity_id=str(current_user.id),
        organization_id=organization_id or None,
        resource_type="policy",
        resource_id=str(policy_id),
        details={"policy_name": policy_name},
    )
    # The logger flushes into this session; commit so the audit row persists.
    await db.commit()

    return None
