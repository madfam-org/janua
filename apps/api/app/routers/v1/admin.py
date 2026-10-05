"""
Admin API endpoints for system management
"""

import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers.v1.auth import get_current_user
from app.routers.v1.organizations.dependencies import validate_unique_slug
from app.services.account_lockout_service import AccountLockoutService
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.auth_service import AuthService
from app.services.entitlements_service import (
    cancel_entitlement,
    remove_org_product_tier,
    set_org_product_tier,
    upsert_entitlement,
)
from app.services.system_settings_service import SystemSettingsService, invalidate_cors_cache

# Application start time for uptime calculation
APPLICATION_START_TIME = time.time()

from ...models import (
    ActivityLog,
    EntitlementSource,
    OAuthAccount,
    OAuthProvider,
    Organization,
    OrganizationMember,
    Passkey,
    PasswordReset,
    User,
    UserStatus,
    organization_members,
)
from ...models import Session as UserSession
from ...services.user_lookup import get_user_by_email

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminStatsResponse(BaseModel):
    """Admin statistics response"""

    total_users: int
    active_users: int
    suspended_users: int
    deleted_users: int
    total_organizations: int
    total_sessions: int
    active_sessions: int
    mfa_enabled_users: int
    oauth_accounts: int
    passkeys_registered: int
    users_last_24h: int
    sessions_last_24h: int


class SystemHealthResponse(BaseModel):
    """System health response"""

    status: str
    database: str
    cache: str
    storage: str
    email: str
    uptime: float
    version: str
    environment: str


class UserAdminResponse(BaseModel):
    """Admin user response with additional details"""

    id: str
    email: str
    email_verified: bool
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    status: str
    mfa_enabled: bool
    is_admin: bool
    organizations_count: int
    sessions_count: int
    oauth_providers: List[str]
    passkeys_count: int
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime]


class OrganizationAdminResponse(BaseModel):
    """Admin organization response"""

    id: str
    name: str
    slug: str
    owner_id: str
    owner_email: str
    billing_plan: str
    billing_email: Optional[str]
    members_count: int
    created_at: datetime
    updated_at: datetime


class ActivityLogResponse(BaseModel):
    """Activity log response"""

    id: str
    user_id: str
    user_email: str
    action: str
    details: dict
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


class AdminUserUpdateRequest(BaseModel):
    """Admin user update request"""

    status: Optional[UserStatus] = None
    is_admin: Optional[bool] = None
    email_verified: Optional[bool] = None


# Org roles a membership may carry. Deliberately an allowlist: these are
# ORG-SCOPED roles (member/admin/owner) entirely separate from the platform-wide
# User.is_admin flag. Keeping the two disjoint is the no-privilege-escalation
# boundary — an org "admin" must never confer platform admin, and vice-versa.
_ALLOWED_ORG_ROLES = {"member", "admin", "owner"}


class AdminOrganizationCreateRequest(BaseModel):
    """Admin: create an organization owned by a SPECIFIED existing user.

    The self-service `POST /organizations/` always sets owner = the caller, and
    janua exposes no ownership-transfer endpoint. That makes it impossible for an
    operator to stand up a CUSTOMER's canonical org (owned by the customer's
    master user, not the operator) — which is exactly what onboarding a tenant
    like a client account requires. This admin endpoint fills that gap: the owner
    is named explicitly and must already exist.
    """

    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    # The owner is an EXISTING user, addressed by email (the human-meaningful key
    # an operator has) or by id. Exactly one must be provided.
    owner_email: Optional[EmailStr] = Field(
        None, description="Email of the existing user to own the org."
    )
    owner_id: Optional[str] = Field(
        None, description="UUID of the existing user to own the org (alternative to owner_email)."
    )
    description: Optional[str] = Field(None, max_length=1000)
    billing_email: Optional[EmailStr] = None


class AdminOrganizationUpdateRequest(BaseModel):
    """Admin: adopt/repair an existing organization — set its owner and/or rename.

    Companion to AdminOrganizationCreateRequest, for orgs that ALREADY exist and
    need an owner assigned or a name aligned. The self-service PATCH
    /organizations/{id} requires the caller to be an org admin, and
    transfer-ownership requires the new owner to already be a member plus a
    confirmation password — neither works for an operator adopting an ownerless
    org they are not a member of. This admin path does: the named owner must
    already exist, and is (re)asserted as an `owner`-role member. All fields
    optional; only what is provided is changed.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    owner_email: Optional[EmailStr] = Field(
        None, description="Email of the existing user to make owner."
    )
    owner_id: Optional[str] = Field(
        None, description="UUID of the existing user to make owner (alternative to owner_email)."
    )


class AdminUserCreateRequest(BaseModel):
    """Admin create-user request (parity with Supabase Auth admin.createUser)."""

    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=200)
    # Optional. When omitted, the user is created WITHOUT a usable password and a
    # one-time set-password token is returned (AdminUserCreateResponse.
    # set_password_token). We never invent a guessable default. When provided it
    # must satisfy the same strength policy as self-signup.
    password: Optional[str] = Field(default=None)
    is_admin: bool = Field(default=False)
    email_verified: bool = Field(
        default=False, description="Pre-verify the email (admin vouches for the address)."
    )
    organization_id: Optional[str] = Field(
        default=None, description="Optional org to add the new user to as a member."
    )
    organization_role: str = Field(
        default="member", description="Org-scoped role for the membership (member|admin|owner)."
    )


class AdminUserCreateResponse(BaseModel):
    """Created user. Mirrors UserAdminResponse and NEVER carries the password.

    `set_password_token` is present ONLY when the caller omitted a password: it
    is a one-time PasswordReset token the operator hands to the new user, who
    redeems it at POST /api/v1/auth/password/reset to choose their own password.
    """

    id: str
    email: str
    email_verified: bool
    name: Optional[str]
    status: str
    is_admin: bool
    organization_id: Optional[str] = None
    organization_role: Optional[str] = None
    set_password_token: Optional[str] = None
    created_at: datetime


def check_admin_permission(user: User):
    """Check if user has admin permissions"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get admin statistics"""
    check_admin_permission(current_user)

    # User statistics
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar()

    result = await db.execute(select(func.count(User.id)).where(User.status == UserStatus.ACTIVE))
    active_users = result.scalar()

    result = await db.execute(
        select(func.count(User.id)).where(User.status == UserStatus.SUSPENDED)
    )
    suspended_users = result.scalar()

    result = await db.execute(select(func.count(User.id)).where(User.status == UserStatus.DELETED))
    deleted_users = result.scalar()

    # Organization statistics
    result = await db.execute(select(func.count(Organization.id)))
    total_organizations = result.scalar()

    # Session statistics
    result = await db.execute(select(func.count(UserSession.id)))
    total_sessions = result.scalar()

    result = await db.execute(
        select(func.count(UserSession.id)).where(
            UserSession.revoked_at.is_(None), UserSession.expires_at > datetime.utcnow()
        )
    )
    active_sessions = result.scalar()

    # Security statistics - MFA enabled users count
    result = await db.execute(select(func.count(User.id)).where(User.mfa_enabled.is_(True)))
    mfa_enabled_users = result.scalar() or 0

    # OAuth accounts - table may not exist yet, so skip if query fails
    oauth_accounts = 0  # Default if table doesn't exist
    passkeys_registered = 0  # Default if table doesn't exist

    # We don't query these tables as they may not exist in production yet
    # When oauth_accounts and passkeys tables are created, enable these queries:
    # result = await db.execute(select(func.count(OAuthAccount.id)))
    # oauth_accounts = result.scalar()
    # result = await db.execute(select(func.count(Passkey.id)))
    # passkeys_registered = result.scalar()

    # Recent activity
    last_24h = datetime.utcnow() - timedelta(hours=24)

    result = await db.execute(select(func.count(User.id)).where(User.created_at >= last_24h))
    users_last_24h = result.scalar()

    result = await db.execute(
        select(func.count(UserSession.id)).where(UserSession.created_at >= last_24h)
    )
    sessions_last_24h = result.scalar()

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        deleted_users=deleted_users,
        total_organizations=total_organizations,
        total_sessions=total_sessions,
        active_sessions=active_sessions,
        mfa_enabled_users=mfa_enabled_users,
        oauth_accounts=oauth_accounts,
        passkeys_registered=passkeys_registered,
        users_last_24h=users_last_24h,
        sessions_last_24h=sessions_last_24h,
    )


def _log_health_failure(check: str, error: Exception) -> None:
    """Log a failed admin health check server-side, redacted (J4-002)."""
    import structlog

    from app.services.monitoring import redact_error_text

    structlog.get_logger().warning(
        "admin_health_check_failed",
        check=check,
        error_type=type(error).__name__,
        error=redact_error_text(str(error)),
    )


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get system health status"""
    check_admin_permission(current_user)

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        database_status = "healthy"
    except Exception:
        database_status = "unhealthy"

    # Check cache (Redis in production)
    from app.core.redis import get_redis

    try:
        redis_client = await get_redis()
        await redis_client.ping()
        cache_status = "healthy"
    except Exception as e:
        # Status only in the body (J4-002); the detail goes to the log, redacted.
        _log_health_failure("cache", e)
        cache_status = "unhealthy"

    # Check storage (S3/R2 in production)
    try:
        # Check if storage is configured
        if not settings.STORAGE_ENABLED or not settings.STORAGE_BUCKET_NAME:
            storage_status = "not_configured"
        else:
            # Basic configuration check - actual R2 health check would require boto3
            # For now, validate that required settings are present
            if settings.STORAGE_ACCESS_KEY_ID and settings.STORAGE_SECRET_ACCESS_KEY:
                storage_status = "configured"  # Assume healthy if properly configured
            else:
                storage_status = "misconfigured"
    except Exception as e:
        _log_health_failure("storage", e)
        storage_status = "unhealthy"

    # Check email service
    from app.services.resend_email_service import get_resend_email_service

    try:
        redis_client = await get_redis()
        email_service = get_resend_email_service(redis_client)
        health = await email_service.check_health()
        email_status = health["status"]
    except Exception:
        email_status = "unhealthy"

    # Calculate uptime from application start time
    uptime = time.time() - APPLICATION_START_TIME

    return SystemHealthResponse(
        status="healthy" if database_status == "healthy" else "degraded",
        database=database_status,
        cache=cache_status,
        storage=storage_status,
        email=email_status,
        uptime=uptime,
        version=settings.VERSION or "1.0.0",
        environment=settings.ENVIRONMENT,
    )


@router.get("/users", response_model=List[UserAdminResponse])
async def list_all_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[UserStatus] = None,
    mfa_enabled: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users (admin only)"""
    check_admin_permission(current_user)

    # Build query
    stmt = select(User)

    # Apply filters
    if search:
        stmt = stmt.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
            )
        )

    if status:
        stmt = stmt.where(User.status == status)

    if mfa_enabled is not None:
        stmt = stmt.where(User.mfa_enabled == mfa_enabled)

    if is_admin is not None:
        stmt = stmt.where(User.is_admin == is_admin)

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result_set = await db.execute(stmt)
    users = result_set.scalars().all()

    # Build response
    result = []
    for user in users:
        # Get additional counts
        orgs_result = await db.execute(
            select(func.count(organization_members.c.organization_id)).where(
                organization_members.c.user_id == user.id
            )
        )
        orgs_count = orgs_result.scalar()

        sessions_result = await db.execute(
            select(func.count(UserSession.id)).where(
                UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
            )
        )
        sessions_count = sessions_result.scalar()

        # Query OAuth accounts - table may not exist, handle gracefully
        oauth_providers = []
        try:
            oauth_result = await db.execute(
                select(OAuthAccount.provider).where(OAuthAccount.user_id == user.id)
            )
            oauth_providers = oauth_result.scalars().all()
        except Exception:
            pass  # Table may not exist in production yet

        # Query passkeys - table may not exist, handle gracefully
        passkeys_count = 0
        try:
            passkeys_result = await db.execute(
                select(func.count(Passkey.id)).where(Passkey.user_id == user.id)
            )
            passkeys_count = passkeys_result.scalar() or 0
        except Exception:
            pass  # Table may not exist in production yet

        # Coalesce nullable boolean columns (legacy rows may have NULL).
        # See migration 000_init.py: email_verified, is_admin, mfa_enabled are nullable=True.
        # Without this guard, pydantic raises ValidationError -> 500 on the whole list.
        result.append(
            UserAdminResponse(
                id=str(user.id),
                email=user.email,
                email_verified=bool(user.email_verified),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                status=user.status.value if user.status else UserStatus.ACTIVE.value,
                mfa_enabled=bool(user.mfa_enabled),
                is_admin=bool(user.is_admin),
                organizations_count=orgs_count or 0,
                sessions_count=sessions_count or 0,
                oauth_providers=[
                    p.value if hasattr(p, "value") else str(p) for p in oauth_providers
                ],
                passkeys_count=passkeys_count or 0,
                created_at=user.created_at,
                updated_at=user.updated_at or user.created_at,
                last_sign_in_at=user.last_sign_in_at,
            )
        )

    return result


@router.post("/users", response_model=AdminUserCreateResponse, status_code=201)
async def create_user_admin(
    request: AdminUserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a user directly (admin only).

    Parity with Supabase Auth's admin.createUser: janua previously had no way to
    provision a user outside self-signup or invite acceptance.

    Password handling:
      * password provided -> validated for strength, hashed (bcrypt via
        AuthService — hashing is NOT duplicated here); user is immediately usable.
      * password omitted   -> user created with no usable password_hash and a
        one-time set-password token returned. No default/guessable secret.

    Privilege model: gated by check_admin_permission (platform admins only).
    `is_admin` sets the platform flag; `organization_role` sets an org-scoped role
    and can never grant platform admin (disjoint by construction).
    """
    check_admin_permission(current_user)

    # Validate org role against the allowlist up front (before any writes).
    if request.organization_role not in _ALLOWED_ORG_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid organization_role. Allowed: {sorted(_ALLOWED_ORG_ROLES)}",
        )

    # Resolve org (if requested) before creating anything, so a bad org id fails
    # cleanly instead of orphaning a half-created user.
    org: Optional[Organization] = None
    if request.organization_id is not None:
        try:
            org_uuid = uuid.UUID(request.organization_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization_id")
        org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

    # Reject duplicates within the pool this user will land in. Email is
    # per-tenant since migration 013, and the created row below takes
    # tenant_id = org.id (when an org was given) or a fresh random tenant. So
    # scope the check to org.id when present: a global check would wrongly
    # conflict on another tenant's identical email. With no org the new user gets
    # a unique random tenant and cannot collide, but we still guard against a
    # clashing UNTENANTED (staff) account, preserving the prior reject there.
    dup_scope = org.id if org is not None else None
    if await get_user_by_email(db, request.email, tenant_id=dup_scope):
        raise HTTPException(status_code=409, detail="User with this email already exists")

    # Password: validate + hash when provided; otherwise leave unusable and mint
    # a set-password token afterwards.
    password_hash: Optional[str] = None
    set_password_token: Optional[str] = None
    if request.password is not None:
        valid, message = AuthService.validate_password_strength(request.password)
        if not valid:
            raise HTTPException(status_code=400, detail=message)
        password_hash = AuthService.hash_password(request.password)

    # A tenant_id is required on User; admin-created users get a fresh tenant,
    # matching AuthService.create_user's behaviour for the no-tenant case.
    tenant_id = org.id if org is not None else uuid.uuid4()

    user = User(
        email=request.email,
        password_hash=password_hash,
        first_name=request.name,
        status=UserStatus.ACTIVE,
        is_admin=request.is_admin,
        email_verified=request.email_verified,
        email_verified_at=datetime.utcnow() if request.email_verified else None,
        tenant_id=tenant_id,
    )
    db.add(user)
    await db.flush()  # assign user.id without ending the transaction

    # Optional org membership. ORM constructor with only model-defined columns
    # (organization_id, user_id, role, status, joined_at).
    if org is not None:
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=request.organization_role,
            status="active",
            joined_at=datetime.utcnow(),
        )
        db.add(member)

    # No-password path: issue a one-time PasswordReset token (same vehicle as
    # /password/forgot). 24h window gives the operator time to relay it.
    if password_hash is None:
        set_password_token = secrets.token_urlsafe(32)
        db.add(
            PasswordReset(
                user_id=user.id,
                token=set_password_token,
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
        )

    # Audit-log the creation via the working AuditLogger hash-chain trail — the
    # SAME mechanism the signup/signin handlers use (app.routers.v1.auth.
    # log_audit_event). We deliberately do NOT call AuthService.create_audit_log:
    # that helper references AuditLog columns (tenant_id/current_hash/event_type)
    # that do not exist on the model and raises AttributeError. Records who
    # created whom; never a secret. A failure here must not block creation.
    try:
        audit_logger = AuditLogger(db)
        await audit_logger.log(
            event_type=AuditEventType.USER_CREATE,
            tenant_id=str(tenant_id),
            identity_id=str(current_user.id),
            resource_type="user",
            resource_id=str(user.id),
            organization_id=str(org.id) if org is not None else None,
            details={
                "email": request.email,
                "created_by": str(current_user.id),
                "is_admin": request.is_admin,
                "email_verified": request.email_verified,
                "password_set": password_hash is not None,
                "organization_id": str(org.id) if org is not None else None,
                "organization_role": request.organization_role if org is not None else None,
                "via": "admin.create_user",
            },
            severity="info",
        )
    except Exception:
        # Audit logging failure must not break user provisioning.
        pass

    await db.commit()
    await db.refresh(user)

    return AdminUserCreateResponse(
        id=str(user.id),
        email=user.email,
        email_verified=bool(user.email_verified),
        name=user.name,
        status=user.status.value if user.status else UserStatus.ACTIVE.value,
        is_admin=bool(user.is_admin),
        organization_id=str(org.id) if org is not None else None,
        organization_role=request.organization_role if org is not None else None,
        set_password_token=set_password_token,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}")
async def update_user_admin(
    user_id: str,
    request: AdminUserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user as admin"""
    check_admin_permission(current_user)

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user_result = await db.execute(select(User).where(User.id == user_uuid))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-demotion
    if user.id == current_user.id and request.is_admin == False:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin privileges")

    # Update fields
    if request.status is not None:
        user.status = request.status

        # Revoke sessions if suspending/deleting
        if request.status in [UserStatus.SUSPENDED, UserStatus.DELETED]:
            await db.execute(
                update(UserSession).where(UserSession.user_id == user.id).values(revoked=True)
            )

    if request.is_admin is not None:
        user.is_admin = request.is_admin

    if request.email_verified is not None:
        user.email_verified = request.email_verified
        if request.email_verified:
            user.email_verified_at = datetime.utcnow()

    await db.commit()

    return {"message": "User updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: str,
    permanent: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user as admin"""
    check_admin_permission(current_user)

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user_result = await db.execute(select(User).where(User.id == user_uuid))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    if permanent:
        # Hard delete - remove from database
        db.delete(user)
    else:
        # Soft delete
        user.status = UserStatus.DELETED
        user.email = f"deleted_{user.id}_{user.email}"

        # Revoke all sessions
        await db.execute(
            update(UserSession).where(UserSession.user_id == user.id).values(revoked=True)
        )

    await db.commit()

    return {"message": f"User {'permanently' if permanent else 'soft'} deleted"}


@router.post("/users/{user_id}/unlock")
async def unlock_user_account(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unlock a user account that was locked due to failed login attempts.

    Admin only endpoint to manually unlock accounts before the automatic
    unlock time has passed.
    """
    check_admin_permission(current_user)

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    success = await AccountLockoutService.unlock_account(
        db, user_uuid, admin_user_id=current_user.id
    )

    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User account unlocked successfully"}


@router.get("/users/{user_id}/lockout-status")
async def get_user_lockout_status(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the lockout status for a specific user.

    Admin only endpoint to check if a user account is locked and
    view failed login attempt counts.
    """
    check_admin_permission(current_user)

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    status = await AccountLockoutService.get_lockout_status(db, user_uuid)

    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])

    return status


@router.post("/organizations", response_model=OrganizationAdminResponse, status_code=201)
async def create_organization_admin(
    request: AdminOrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an organization owned by a SPECIFIED existing user (admin only).

    WHY THIS EXISTS. `POST /organizations/` sets owner = the caller, and there is
    no ownership-transfer endpoint (the members/roles sub-routers are not
    mounted). So an operator could not create a customer's canonical org owned by
    the CUSTOMER's master user — the org would be owned by the operator. Tenant
    onboarding (e.g. standing up one canonical org that provisions a client
    across every product slice) needs exactly this. The owner is named
    explicitly, must already exist, and is added as an `owner`-role member.

    Idempotent-friendly: a duplicate slug returns 400 (via validate_unique_slug),
    so re-running after the org exists fails cleanly rather than creating a
    second org — the caller then reads the existing org via GET /organizations.

    Privilege model: gated by check_admin_permission (platform admins only).
    Naming an owner here does NOT grant that user platform admin — org-scoped
    ownership and the platform `is_admin` flag stay disjoint.
    """
    check_admin_permission(current_user)

    if (request.owner_email is None) == (request.owner_id is None):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of owner_email or owner_id.",
        )

    # Resolve the owner FIRST — a bad owner must fail before any write, never
    # orphan a half-created org.
    if request.owner_id is not None:
        try:
            owner_uuid = uuid.UUID(request.owner_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid owner_id")
        owner_result = await db.execute(select(User).where(User.id == owner_uuid))
        owner = owner_result.scalar_one_or_none()
    else:
        # Owner-by-email resolves in the untenanted / staff pool (org owners are
        # platform identities; per-tenant email since 013 → scope to single-row).
        owner = await get_user_by_email(db, request.owner_email, tenant_id=None)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner user not found")

    # Unique slug (raises 400 if taken) — this is also the idempotency guard.
    await validate_unique_slug(db, request.slug)

    org = Organization(
        name=request.name,
        slug=request.slug,
        description=request.description,
        owner_id=owner.id,
        billing_email=request.billing_email or owner.email,
        billing_plan="free",
        settings={},
        org_metadata={},
    )
    db.add(org)
    await db.flush()  # assign org.id without ending the transaction

    # Add the owner as an owner-role member (mirrors create_organization, which
    # adds the creator; here the OWNER is the member, not the calling admin).
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
            joined_at=datetime.utcnow(),
        )
    )

    await db.commit()
    await db.refresh(org)

    return OrganizationAdminResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        owner_id=str(org.owner_id),
        owner_email=owner.email,
        billing_plan=org.billing_plan,
        billing_email=org.billing_email,
        members_count=1,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.patch("/organizations/{org_id}", response_model=OrganizationAdminResponse)
async def update_organization_admin(
    org_id: str,
    request: AdminOrganizationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Adopt/repair an existing organization: set its owner and/or rename it (admin only).

    The self-service `PATCH /organizations/{id}` requires the caller to be an org
    admin, and `POST /organizations/{id}/transfer-ownership` requires the new
    owner to already be a member plus a confirmation password. Neither lets an
    operator assign an owner to an org they are not a member of — the exact case
    of an ownerless org that was provisioned out-of-band and now needs its
    customer's master user as owner. This admin path does it: the named owner
    must already exist and is (re)asserted as an `owner`-role member.

    Only provided fields change. Gated by check_admin_permission.
    """
    check_admin_permission(current_user)

    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Resolve the new owner (if requested) before any write.
    owner: Optional[User] = None
    if request.owner_email is not None or request.owner_id is not None:
        if request.owner_email is not None and request.owner_id is not None:
            raise HTTPException(
                status_code=422, detail="Provide at most one of owner_email or owner_id."
            )
        if request.owner_id is not None:
            try:
                owner_uuid = uuid.UUID(request.owner_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid owner_id")
            r = await db.execute(select(User).where(User.id == owner_uuid))
            owner = r.scalar_one_or_none()
        else:
            # Untenanted / staff pool (see the other owner-by-email resolve).
            owner = await get_user_by_email(db, request.owner_email, tenant_id=None)
        if not owner:
            raise HTTPException(status_code=404, detail="Owner user not found")

    if request.name is not None:
        org.name = request.name
    if owner is not None:
        org.owner_id = owner.id
    org.updated_at = datetime.utcnow()

    # (Re)assert the owner as an owner-role member — idempotent: update an
    # existing membership, else insert one. Mirrors how create adds the owner.
    if owner is not None:
        existing_member = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == owner.id,
            )
        )
        member = existing_member.scalar_one_or_none()
        if member is None:
            db.add(
                OrganizationMember(
                    organization_id=org.id,
                    user_id=owner.id,
                    role="owner",
                    status="active",
                    joined_at=datetime.utcnow(),
                )
            )
        else:
            member.role = "owner"
            member.status = "active"

    await db.commit()
    await db.refresh(org)

    # Resolve owner email for the response (the org may have had an owner already).
    owner_email = None
    if org.owner_id is not None:
        oe = await db.execute(select(User).where(User.id == org.owner_id))
        ou = oe.scalar_one_or_none()
        owner_email = ou.email if ou else ""

    count_result = await db.execute(
        select(func.count(organization_members.c.user_id)).where(
            organization_members.c.organization_id == org.id
        )
    )
    return OrganizationAdminResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        owner_id=str(org.owner_id) if org.owner_id else "",
        owner_email=owner_email or "",
        billing_plan=org.billing_plan,
        billing_email=org.billing_email,
        members_count=count_result.scalar() or 0,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.get("/organizations", response_model=List[OrganizationAdminResponse])
async def list_all_organizations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    billing_plan: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all organizations (admin only)"""
    check_admin_permission(current_user)

    # Build query
    stmt = select(Organization).join(User, Organization.owner_id == User.id)

    # Apply filters
    if search:
        stmt = stmt.where(
            or_(
                Organization.name.ilike(f"%{search}%"),
                Organization.slug.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )

    if billing_plan:
        stmt = stmt.where(Organization.billing_plan == billing_plan)

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result_set = await db.execute(stmt)
    organizations = result_set.scalars().all()

    # Build response
    result = []
    for org in organizations:
        owner_result = await db.execute(select(User).where(User.id == org.owner_id))
        owner = owner_result.scalar_one_or_none()

        members_result = await db.execute(
            select(func.count(organization_members.c.user_id)).where(
                organization_members.c.organization_id == org.id
            )
        )
        members_count = members_result.scalar()

        # Coalesce nullable columns (legacy rows may have NULL billing_plan/owner_id/updated_at).
        # See migration 000_init.py: owner_id and billing_plan are nullable=True.
        result.append(
            OrganizationAdminResponse(
                id=str(org.id),
                name=org.name,
                slug=org.slug,
                owner_id=str(org.owner_id) if org.owner_id else "",
                owner_email=owner.email if owner else "unknown",
                billing_plan=org.billing_plan or "free",
                billing_email=org.billing_email,
                members_count=members_count or 0,
                created_at=org.created_at,
                updated_at=org.updated_at or org.created_at,
            )
        )

    return result


@router.delete("/organizations/{org_id}")
async def delete_organization_admin(
    org_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete organization as admin"""
    check_admin_permission(current_user)

    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Delete organization (cascade will handle related records)
    db.delete(org)
    await db.commit()

    return {"message": "Organization deleted successfully"}


# =============================================================================
# Entitlement Write-API (admin-only)
# =============================================================================
#
# Today the ONLY writer of entitlements is the Dhanam subscription webhook.
# This adds an AUDITED, platform-admin-only surface to grant/revoke product
# entitlements for a USER (user_entitlements rows) or an ORG (product_tiers
# JSONB). Both are auth-system mutations — every call writes an AuditLog row.
#
# product/tier are FREE-TEXT by design: the canonical set lives in
# internal-devops/ecosystem/product-tier-mapping.yaml and Janua deliberately
# does NOT enforce it (new products/tiers ship without a Janua code change).
# We only validate non-empty strings, never the value set.


class AdminUserEntitlementGrantRequest(BaseModel):
    """Grant/upsert a per-user product entitlement (source=admin_grant)."""

    user_id: str = Field(..., description="UUID of the user to grant to.")
    product: str = Field(..., min_length=1, max_length=64, description="Product slug (free-text).")
    tier: str = Field(..., min_length=1, max_length=64, description="Tier within the product.")
    expires_at: Optional[datetime] = Field(
        None, description="Optional expiry. NULL = no expiry (typical for admin grants)."
    )


class AdminUserEntitlementRevokeRequest(BaseModel):
    """Revoke (cancel) a per-user product entitlement."""

    user_id: str = Field(..., description="UUID of the user to revoke from.")
    product: str = Field(..., min_length=1, max_length=64, description="Product slug to revoke.")


class AdminUserEntitlementResponse(BaseModel):
    """A user_entitlements row after a grant/revoke."""

    user_id: str
    product: str
    tier: str
    source: str
    expires_at: Optional[datetime]
    granted_at: Optional[datetime]


class AdminOrgEntitlementGrantRequest(BaseModel):
    """Set one product:tier key on an organization's product_tiers JSONB."""

    org_id: str = Field(..., description="UUID of the organization.")
    product: str = Field(..., min_length=1, max_length=64, description="Product slug (free-text).")
    tier: str = Field(..., min_length=1, max_length=64, description="Tier within the product.")


class AdminOrgEntitlementRevokeRequest(BaseModel):
    """Remove one product key from an organization's product_tiers JSONB."""

    org_id: str = Field(..., description="UUID of the organization.")
    product: str = Field(..., min_length=1, max_length=64, description="Product slug to remove.")


class AdminOrgEntitlementResponse(BaseModel):
    """The organization's product_tiers map after a grant/revoke."""

    org_id: str
    product_tiers: dict


async def _record_entitlement_audit(
    db: Session,
    *,
    event_type: AuditEventType,
    actor: User,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    organization_id: Optional[str],
    details: dict,
) -> None:
    """Write an AuditLog row for an entitlement mutation.

    Same tamper-evident AuditLogger chain the admin create-user handler uses.
    An audit failure must NOT block the mutation (it is best-effort, logged),
    but the mutation itself is committed by the caller. Never records a secret.
    """
    try:
        audit_logger = AuditLogger(db)
        await audit_logger.log(
            event_type=event_type,
            tenant_id=tenant_id,
            identity_id=str(actor.id),
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=organization_id,
            details=details,
            severity="info",
        )
    except Exception:
        # Audit logging failure must not break the entitlement mutation.
        pass


@router.post("/entitlements/user", response_model=AdminUserEntitlementResponse)
async def grant_user_entitlement(
    request: AdminUserEntitlementGrantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant/upsert a per-user product entitlement (admin only, audited).

    Idempotent on the (user_id, product) pair via the service upsert. Source is
    always ADMIN_GRANT — distinguishing operator grants from Dhanam-driven rows.
    Gated by check_admin_permission (platform admins only; org-admin never
    reaches here).
    """
    check_admin_permission(current_user)

    try:
        user_uuid = uuid.UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user_result = await db.execute(select(User).where(User.id == user_uuid))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    row = await upsert_entitlement(
        db,
        user_id=user_uuid,
        product=request.product,
        tier=request.tier,
        source=EntitlementSource.ADMIN_GRANT,
        expires_at=request.expires_at,
    )

    await _record_entitlement_audit(
        db,
        event_type=AuditEventType.ENTITLEMENT_GRANT,
        actor=current_user,
        tenant_id=str(getattr(target_user, "tenant_id", None) or target_user.id),
        resource_type="user_entitlement",
        resource_id=str(user_uuid),
        organization_id=None,
        details={
            "scope": "user",
            "user_id": str(user_uuid),
            "product": request.product,
            "tier": request.tier,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "granted_by": str(current_user.id),
            "source": EntitlementSource.ADMIN_GRANT.value,
            "via": "admin.grant_user_entitlement",
        },
    )

    await db.commit()

    return AdminUserEntitlementResponse(
        user_id=str(row.user_id),
        product=row.product,
        tier=row.tier,
        source=row.source.value if hasattr(row.source, "value") else str(row.source),
        expires_at=row.expires_at,
        granted_at=getattr(row, "granted_at", None),
    )


@router.delete("/entitlements/user", response_model=AdminUserEntitlementResponse)
async def revoke_user_entitlement(
    request: AdminUserEntitlementRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke (cancel) a per-user product entitlement (admin only, audited).

    Cancellation sets expires_at = now (preserving the row for audit history),
    matching the Dhanam webhook's cancel semantics. 404 when the user is unknown;
    404 when the user has no such entitlement row to cancel.
    """
    check_admin_permission(current_user)

    try:
        user_uuid = uuid.UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user_result = await db.execute(select(User).where(User.id == user_uuid))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    row = await cancel_entitlement(db, user_id=user_uuid, product=request.product)
    if row is None:
        raise HTTPException(status_code=404, detail="Entitlement not found")

    await _record_entitlement_audit(
        db,
        event_type=AuditEventType.ENTITLEMENT_REVOKE,
        actor=current_user,
        tenant_id=str(getattr(target_user, "tenant_id", None) or target_user.id),
        resource_type="user_entitlement",
        resource_id=str(user_uuid),
        organization_id=None,
        details={
            "scope": "user",
            "user_id": str(user_uuid),
            "product": request.product,
            "revoked_by": str(current_user.id),
            "via": "admin.revoke_user_entitlement",
        },
    )

    await db.commit()

    return AdminUserEntitlementResponse(
        user_id=str(row.user_id),
        product=row.product,
        tier=row.tier,
        source=row.source.value if hasattr(row.source, "value") else str(row.source),
        expires_at=row.expires_at,
        granted_at=getattr(row, "granted_at", None),
    )


def _sync_sender_policy(org_id: str, product_tiers: Optional[dict]) -> None:
    """Tell the transactional-mail gate what this org's vCTO status now is.

    Best-effort and never fatal: an entitlement grant must not fail because a
    mail-sender cache could not be updated. The gate fails CLOSED on a stale or
    empty cache (the sender falls back to MADFAM's address, keeping the tenant
    display name), so the worst case of a miss here is a message from the
    platform address — never an undelivered sign-in link.

    Only applies to orgs that HAVE a sender binding; every other org has no
    branded sender to gate.
    """
    try:
        from app.services.sender_binding import tenant_for_org_id
        from app.services.sender_policy import (
            product_tiers_grant_vcto,
            refresh_vcto_cache,
        )

        tenant = tenant_for_org_id(org_id)
        if tenant:
            refresh_vcto_cache(tenant, product_tiers_grant_vcto(product_tiers))
    except Exception as exc:  # pragma: no cover - defensive
        # Local import, matching this module's existing convention (there is no
        # module-level logger here).
        import structlog

        structlog.get_logger().warning(
            "admin.sender_policy_sync_failed", error=str(exc), org_id=org_id
        )


@router.post("/entitlements/org", response_model=AdminOrgEntitlementResponse)
async def grant_org_entitlement(
    request: AdminOrgEntitlementGrantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set one product:tier on an org's product_tiers JSONB (admin only, audited).

    Merges (does not clobber other products). Org members inherit this tier at
    JWT-issue time when they have no explicit per-user row.
    """
    check_admin_permission(current_user)

    try:
        org_uuid = uuid.UUID(request.org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid org_id")

    updated = await set_org_product_tier(
        db,
        org_id=org_uuid,
        product=request.product,
        tier=request.tier,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    await _record_entitlement_audit(
        db,
        event_type=AuditEventType.ENTITLEMENT_GRANT,
        actor=current_user,
        tenant_id=str(org_uuid),
        resource_type="org_entitlement",
        resource_id=str(org_uuid),
        organization_id=str(org_uuid),
        details={
            "scope": "org",
            "org_id": str(org_uuid),
            "product": request.product,
            "tier": request.tier,
            "granted_by": str(current_user.id),
            "via": "admin.grant_org_entitlement",
        },
    )

    await db.commit()

    # Propagate to the transactional-mail vCTO gate. The auth mailer runs in a
    # BackgroundTask with no DB session, so it cannot re-read product_tiers at
    # send time; this is the authoritative write telling it what changed. See
    # app/services/sender_policy.py.
    _sync_sender_policy(str(org_uuid), updated)

    return AdminOrgEntitlementResponse(org_id=str(org_uuid), product_tiers=updated)


@router.delete("/entitlements/org", response_model=AdminOrgEntitlementResponse)
async def revoke_org_entitlement(
    request: AdminOrgEntitlementRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove one product from an org's product_tiers JSONB (admin only, audited).

    Idempotent — removing an absent product still returns the current map.
    Other products are preserved.
    """
    check_admin_permission(current_user)

    try:
        org_uuid = uuid.UUID(request.org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid org_id")

    updated = await remove_org_product_tier(
        db,
        org_id=org_uuid,
        product=request.product,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    await _record_entitlement_audit(
        db,
        event_type=AuditEventType.ENTITLEMENT_REVOKE,
        actor=current_user,
        tenant_id=str(org_uuid),
        resource_type="org_entitlement",
        resource_id=str(org_uuid),
        organization_id=str(org_uuid),
        details={
            "scope": "org",
            "org_id": str(org_uuid),
            "product": request.product,
            "revoked_by": str(current_user.id),
            "via": "admin.revoke_org_entitlement",
        },
    )

    await db.commit()

    # Revocation must propagate as fast as a grant, or a concluded engagement
    # keeps sending from a domain MADFAM no longer operates.
    _sync_sender_policy(str(org_uuid), updated)

    return AdminOrgEntitlementResponse(org_id=str(org_uuid), product_tiers=updated)


@router.get("/activity-logs", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get activity logs (admin only)"""
    check_admin_permission(current_user)

    # Build query
    stmt = select(ActivityLog).join(User, ActivityLog.user_id == User.id)

    # Apply filters
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = stmt.where(ActivityLog.user_id == user_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID")

    if action:
        stmt = stmt.where(ActivityLog.action == action)

    if start_date:
        stmt = stmt.where(ActivityLog.created_at >= start_date)

    if end_date:
        stmt = stmt.where(ActivityLog.created_at <= end_date)

    # Order by most recent first
    stmt = stmt.order_by(desc(ActivityLog.created_at))

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result_set = await db.execute(stmt)
    logs = result_set.scalars().all()

    # Build response
    result = []
    for log in logs:
        user_result = await db.execute(select(User).where(User.id == log.user_id))
        user = user_result.scalar_one_or_none()

        result.append(
            ActivityLogResponse(
                id=str(log.id),
                user_id=str(log.user_id),
                user_email=user.email if user else "unknown",
                action=log.action,
                details=getattr(log, "details", None)
                or getattr(log, "activity_metadata", None)
                or {},
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at,
            )
        )

    return result


@router.post("/sessions/revoke-all")
async def revoke_all_sessions_admin(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke all sessions (optionally for specific user)"""
    check_admin_permission(current_user)

    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            result = await db.execute(
                update(UserSession)
                .where(UserSession.user_id == user_uuid, UserSession.revoked == False)
                .values(revoked=True)
            )
            count = result.rowcount
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID")
    else:
        # Revoke all sessions except admin's current session
        # Get current session JTI from the access token
        # Note: We need the request object to extract the token
        # For now, revoke all non-admin sessions to be safe
        result = await db.execute(
            update(UserSession)
            .where(
                UserSession.revoked == False,
                UserSession.user_id != current_user.id,  # Preserve admin's sessions
            )
            .values(revoked=True)
        )
        count = result.rowcount

    await db.commit()

    return {"message": f"Revoked {count} sessions"}


@router.post("/maintenance-mode")
async def toggle_maintenance_mode(
    enabled: bool,
    message: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle maintenance mode"""
    check_admin_permission(current_user)

    # Implement maintenance mode in Redis with indefinite expiry
    import structlog

    from app.core.redis import get_redis

    logger = structlog.get_logger()
    redis_client = await get_redis()

    if enabled:
        # Enable maintenance mode
        maintenance_data = {
            "enabled": True,
            "message": message or "System is under maintenance",
            "enabled_at": datetime.utcnow().isoformat(),
            "enabled_by": str(current_user.id),
        }
        await redis_client.set("maintenance_mode", str(maintenance_data))
        logger.info("Maintenance mode enabled", admin_id=str(current_user.id))
    else:
        # Disable maintenance mode
        await redis_client.delete("maintenance_mode")
        logger.info("Maintenance mode disabled", admin_id=str(current_user.id))

    return {
        "maintenance_mode": enabled,
        "message": message or "System is under maintenance" if enabled else "System is operational",
    }


@router.get("/config")
async def get_system_config(current_user: User = Depends(get_current_user)):
    """Get system configuration (admin only)"""
    check_admin_permission(current_user)

    # Return non-sensitive configuration
    return {
        "environment": settings.ENVIRONMENT,
        "app_name": settings.APP_NAME,
        "domain": settings.DOMAIN,
        "version": settings.VERSION or "1.0.0",
        "features": {
            "mfa_enabled": True,
            "passkeys_enabled": True,
            "oauth_providers": [p.value for p in OAuthProvider],
            "magic_links_enabled": True,
            "organizations_enabled": True,
        },
        "limits": {
            "max_sessions_per_user": 10,
            "session_timeout_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_days": settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "password_reset_expire_minutes": 60,
            "magic_link_expire_minutes": 15,
            "invitation_expire_days": 7,
        },
    }


# =============================================================================
# System Settings Management
# =============================================================================


class CorsOriginCreate(BaseModel):
    """Request to create a new CORS origin"""

    origin: str = Field(..., description="The origin URL (e.g., https://app.example.com)")
    description: Optional[str] = Field(None, description="Human-readable description")
    organization_id: Optional[str] = Field(
        None, description="Organization ID for tenant-specific origins (null for system-level)"
    )


class CorsOriginResponse(BaseModel):
    """CORS origin response"""

    id: str
    origin: str
    organization_id: Optional[str]
    scope: str  # "system" or "organization"
    description: Optional[str]
    is_active: bool
    created_at: Optional[str]


class SystemSettingCreate(BaseModel):
    """Request to create/update a system setting"""

    key: str = Field(..., description="Setting key (e.g., 'oidc.custom_domain')")
    value: Any = Field(..., description="Setting value (string or JSON)")
    category: Optional[str] = Field("features", description="Setting category")
    description: Optional[str] = Field(None, description="Human-readable description")
    is_sensitive: bool = Field(False, description="Hide value in API responses")


class SystemSettingResponse(BaseModel):
    """System setting response"""

    id: str
    key: str
    value: Any
    category: str
    description: Optional[str]
    is_sensitive: bool
    is_readonly: bool
    updated_at: Optional[str]


@router.get("/settings/cors", response_model=List[CorsOriginResponse])
async def list_cors_origins(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    include_inactive: bool = Query(False, description="Include deactivated origins"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all CORS origins.

    System-level origins (organization_id=null) apply globally.
    Organization-level origins apply only to that tenant's white-label setup.
    """
    check_admin_permission(current_user)

    service = SystemSettingsService(db)
    org_uuid = uuid.UUID(organization_id) if organization_id else None

    origins = await service.list_cors_origins(
        organization_id=org_uuid, include_inactive=include_inactive, include_system=True
    )

    return [CorsOriginResponse(**o) for o in origins]


@router.post("/settings/cors", response_model=CorsOriginResponse)
async def add_cors_origin(
    request: CorsOriginCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a new CORS origin.

    - System-level (organization_id=null): Allows requests from this origin to the API
    - Organization-level: Allows requests for that tenant's white-label deployment
    """
    check_admin_permission(current_user)

    service = SystemSettingsService(db)
    org_uuid = uuid.UUID(request.organization_id) if request.organization_id else None

    try:
        cors_origin = await service.add_cors_origin(
            origin=request.origin,
            organization_id=org_uuid,
            description=request.description,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Invalidate global CORS cache
    invalidate_cors_cache()

    return CorsOriginResponse(
        id=str(cors_origin.id),
        origin=cors_origin.origin,
        organization_id=str(cors_origin.organization_id) if cors_origin.organization_id else None,
        scope="organization" if cors_origin.organization_id else "system",
        description=cors_origin.description,
        is_active=cors_origin.is_active,
        created_at=cors_origin.created_at.isoformat() if cors_origin.created_at else None,
    )


@router.delete("/settings/cors/{origin_id}")
async def remove_cors_origin(
    origin_id: str,
    permanent: bool = Query(False, description="Permanently delete instead of deactivating"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a CORS origin (soft delete by default)"""
    check_admin_permission(current_user)

    # Look up the origin by ID
    from app.models.system_settings import AllowedCorsOrigin

    try:
        origin_uuid = uuid.UUID(origin_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid origin ID")

    result = await db.execute(select(AllowedCorsOrigin).where(AllowedCorsOrigin.id == origin_uuid))
    cors_origin = result.scalar_one_or_none()

    if not cors_origin:
        raise HTTPException(status_code=404, detail="CORS origin not found")

    service = SystemSettingsService(db)

    if permanent:
        success = await service.delete_cors_origin(
            cors_origin.origin, organization_id=cors_origin.organization_id
        )
    else:
        success = await service.remove_cors_origin(
            cors_origin.origin, organization_id=cors_origin.organization_id
        )

    if not success:
        raise HTTPException(status_code=404, detail="CORS origin not found")

    # Invalidate global CORS cache
    invalidate_cors_cache()

    return {
        "message": f"CORS origin {'deleted' if permanent else 'deactivated'}",
        "origin": cors_origin.origin,
    }


@router.get("/settings/cors/cache-status")
async def get_cors_cache_status(
    current_user: User = Depends(get_current_user),
):
    """
    Get CORS cache status for debugging.
    Shows cache state, age, and number of cached origins.
    """
    check_admin_permission(current_user)

    try:
        from app.middleware.dynamic_cors import get_cors_cache_status as get_cache_status

        return get_cache_status()
    except ImportError:
        return {"error": "Dynamic CORS middleware not available", "cached": False}


@router.post("/settings/cors/invalidate-cache")
async def invalidate_cors_cache_endpoint(
    current_user: User = Depends(get_current_user),
):
    """
    Manually invalidate the CORS origins cache.
    Use this after making direct database changes to CORS origins.
    """
    check_admin_permission(current_user)

    invalidate_cors_cache()
    return {"message": "CORS cache invalidated successfully"}


@router.get("/settings", response_model=List[SystemSettingResponse])
async def list_system_settings(
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all system settings"""
    check_admin_permission(current_user)

    service = SystemSettingsService(db)
    settings_list = await service.get_all_settings(
        category=category, include_sensitive=False  # Never expose sensitive values
    )

    return [SystemSettingResponse(**s) for s in settings_list]


@router.put("/settings/{key:path}")
async def update_system_setting(
    key: str,
    request: SystemSettingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a system setting"""
    check_admin_permission(current_user)

    service = SystemSettingsService(db)

    # Check if setting is read-only
    existing = await service.get_setting(key)
    if existing and isinstance(existing, dict) and existing.get("is_readonly"):
        raise HTTPException(status_code=403, detail="This setting is read-only")

    setting = await service.set_setting(
        key=key,
        value=request.value,
        category=request.category or "features",
        description=request.description,
        is_sensitive=request.is_sensitive,
        updated_by=current_user.id,
    )

    # Invalidate CORS cache if CORS-related setting
    if key.startswith("cors."):
        invalidate_cors_cache()

    return {
        "message": "Setting updated",
        "key": setting.key,
        "value": setting.get_value() if not setting.is_sensitive else "***REDACTED***",
    }


@router.delete("/settings/{key:path}")
async def delete_system_setting(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a system setting"""
    check_admin_permission(current_user)

    service = SystemSettingsService(db)
    success = await service.delete_setting(key)

    if not success:
        raise HTTPException(status_code=404, detail="Setting not found")

    # Invalidate CORS cache if CORS-related setting
    if key.startswith("cors."):
        invalidate_cors_cache()

    return {"message": "Setting deleted", "key": key}


@router.get("/settings/oidc/custom-domain")
async def get_custom_domain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current custom OIDC issuer domain"""
    check_admin_permission(current_user)

    service = SystemSettingsService(db)
    domain = await service.get_custom_domain()

    return {
        "custom_domain": domain,
        "issuer": f"https://{domain}" if domain else settings.JWT_ISSUER,
        "source": "database" if domain else "config",
    }


@router.put("/settings/oidc/custom-domain")
async def set_custom_domain(
    domain: str = Query(..., description="Custom domain (e.g., auth.madfam.io)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set the custom OIDC issuer domain.

    This allows white-label deployments to issue tokens with a custom issuer
    (e.g., auth.madfam.io instead of api.janua.dev).
    """
    check_admin_permission(current_user)

    service = SystemSettingsService(db)

    try:
        setting = await service.set_custom_domain(domain, updated_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Custom domain updated",
        "custom_domain": setting.value,
        "issuer": f"https://{setting.value}",
    }
