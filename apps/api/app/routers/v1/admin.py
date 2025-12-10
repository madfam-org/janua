"""
Admin API endpoints for system management
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers.v1.auth import get_current_user

# Application start time for uptime calculation
APPLICATION_START_TIME = time.time()

from ...models import (
    ActivityLog,
    EmailVerification,
    MagicLink,
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
            UserSession.revoked_at == None, UserSession.expires_at > datetime.utcnow()
        )
    )
    active_sessions = result.scalar()

    # Security statistics - MFA enabled users count
    result = await db.execute(select(func.count(User.id)).where(User.mfa_enabled == True))
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
        cache_status = f"unhealthy: {str(e)}"

    # Check storage (S3/R2 in production)
    try:
        # Check if storage is configured
        if not settings.STORAGE_ENABLED or not settings.STORAGE_BUCKET_NAME:
            storage_status = "not_configured"
        else:
            # Basic configuration check - actual S3/R2 health check would require boto3
            # For now, validate that required settings are present
            if settings.STORAGE_ACCESS_KEY_ID and settings.STORAGE_SECRET_ACCESS_KEY:
                storage_status = "configured"  # Assume healthy if properly configured
            else:
                storage_status = "misconfigured"
    except Exception as e:
        storage_status = f"unhealthy: {str(e)}"

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
                UserSession.user_id == user.id, UserSession.revoked_at == None
            )
        )
        sessions_count = sessions_result.scalar()

        oauth_result = await db.execute(
            select(OAuthAccount.provider).where(OAuthAccount.user_id == user.id)
        )
        oauth_providers = oauth_result.scalars().all()

        passkeys_result = await db.execute(
            select(func.count(Passkey.id)).where(Passkey.user_id == user.id)
        )
        passkeys_count = passkeys_result.scalar()

        result.append(
            UserAdminResponse(
                id=str(user.id),
                email=user.email,
                email_verified=user.email_verified,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                status=user.status.value,
                mfa_enabled=user.mfa_enabled,
                is_admin=user.is_admin,
                organizations_count=orgs_count,
                sessions_count=sessions_count,
                oauth_providers=[p.provider.value for p in oauth_providers],
                passkeys_count=passkeys_count,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_sign_in_at=user.last_sign_in_at,
            )
        )

    return result


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

        result.append(
            OrganizationAdminResponse(
                id=str(org.id),
                name=org.name,
                slug=org.slug,
                owner_id=str(org.owner_id),
                owner_email=owner.email if owner else "unknown",
                billing_plan=org.billing_plan,
                billing_email=org.billing_email,
                members_count=members_count,
                created_at=org.created_at,
                updated_at=org.updated_at,
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
                details=getattr(log, 'details', None) or getattr(log, 'activity_metadata', None) or {},
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
        from fastapi import Request

        from app.routers.v1.auth import get_current_session_jti

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

    from app.core.database import get_redis

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
