"""
Admin API endpoints for system management
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import uuid

from app.database import get_db
from app.models import (
    User, UserStatus, Organization, OrganizationMember, organization_members,
    Session as UserSession, ActivityLog, OAuthAccount,
    Passkey, MagicLink, PasswordReset, EmailVerification,
    OAuthProvider
)
from app.routers.v1.auth import get_current_user
from app.config import settings

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get admin statistics"""
    check_admin_permission(current_user)
    
    # User statistics
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(
        User.status == UserStatus.ACTIVE
    ).scalar()
    suspended_users = db.query(func.count(User.id)).filter(
        User.status == UserStatus.SUSPENDED
    ).scalar()
    deleted_users = db.query(func.count(User.id)).filter(
        User.status == UserStatus.DELETED
    ).scalar()
    
    # Organization statistics
    total_organizations = db.query(func.count(Organization.id)).scalar()
    
    # Session statistics
    total_sessions = db.query(func.count(UserSession.id)).scalar()
    active_sessions = db.query(func.count(UserSession.id)).filter(
        UserSession.revoked == False,
        UserSession.expires_at > datetime.utcnow()
    ).scalar()
    
    # Security statistics
    mfa_enabled_users = db.query(func.count(User.id)).filter(
        User.mfa_enabled == True
    ).scalar()
    oauth_accounts = db.query(func.count(OAuthAccount.id)).scalar()
    passkeys_registered = db.query(func.count(Passkey.id)).scalar()
    
    # Recent activity
    last_24h = datetime.utcnow() - timedelta(hours=24)
    users_last_24h = db.query(func.count(User.id)).filter(
        User.created_at >= last_24h
    ).scalar()
    sessions_last_24h = db.query(func.count(UserSession.id)).filter(
        UserSession.created_at >= last_24h
    ).scalar()
    
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
        sessions_last_24h=sessions_last_24h
    )


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get system health status"""
    check_admin_permission(current_user)
    
    # Check database
    try:
        db.execute("SELECT 1")
        database_status = "healthy"
    except:
        database_status = "unhealthy"
    
    # Check cache (Redis in production)
    cache_status = "not_configured"  # TODO: Check Redis connection
    
    # Check storage
    storage_status = "healthy"  # TODO: Check S3/storage connection
    
    # Check email service
    email_status = "not_configured"  # TODO: Check email service
    
    # Calculate uptime (in production, track actual start time)
    uptime = 0.0  # TODO: Calculate from application start time
    
    return SystemHealthResponse(
        status="healthy" if database_status == "healthy" else "degraded",
        database=database_status,
        cache=cache_status,
        storage=storage_status,
        email=email_status,
        uptime=uptime,
        version=settings.VERSION or "1.0.0",
        environment=settings.ENVIRONMENT
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
    db: Session = Depends(get_db)
):
    """List all users (admin only)"""
    check_admin_permission(current_user)
    
    query = db.query(User)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    
    if status:
        query = query.filter(User.status == status)
    
    if mfa_enabled is not None:
        query = query.filter(User.mfa_enabled == mfa_enabled)
    
    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    # Build response
    result = []
    for user in users:
        # Get additional counts
        orgs_count = db.query(func.count(organization_members.c.organization_id)).filter(
            organization_members.c.user_id == user.id
        ).scalar()
        
        sessions_count = db.query(func.count(UserSession.id)).filter(
            UserSession.user_id == user.id,
            UserSession.revoked == False
        ).scalar()
        
        oauth_providers = db.query(OAuthAccount.provider).filter(
            OAuthAccount.user_id == user.id
        ).all()
        
        passkeys_count = db.query(func.count(Passkey.id)).filter(
            Passkey.user_id == user.id
        ).scalar()
        
        result.append(UserAdminResponse(
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
            last_sign_in_at=user.last_sign_in_at
        ))
    
    return result


@router.patch("/users/{user_id}")
async def update_user_admin(
    user_id: str,
    request: AdminUserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user as admin"""
    check_admin_permission(current_user)
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    user = db.query(User).filter(User.id == user_uuid).first()
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
            db.query(UserSession).filter(
                UserSession.user_id == user.id
            ).update({"revoked": True})
    
    if request.is_admin is not None:
        user.is_admin = request.is_admin
    
    if request.email_verified is not None:
        user.email_verified = request.email_verified
        if request.email_verified:
            user.email_verified_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "User updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: str,
    permanent: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user as admin"""
    check_admin_permission(current_user)
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    user = db.query(User).filter(User.id == user_uuid).first()
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
        db.query(UserSession).filter(
            UserSession.user_id == user.id
        ).update({"revoked": True})
    
    db.commit()
    
    return {"message": f"User {'permanently' if permanent else 'soft'} deleted"}


@router.get("/organizations", response_model=List[OrganizationAdminResponse])
async def list_all_organizations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    billing_plan: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all organizations (admin only)"""
    check_admin_permission(current_user)
    
    query = db.query(Organization).join(User, Organization.owner_id == User.id)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Organization.name.ilike(f"%{search}%"),
                Organization.slug.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    if billing_plan:
        query = query.filter(Organization.billing_plan == billing_plan)
    
    # Apply pagination
    offset = (page - 1) * per_page
    organizations = query.offset(offset).limit(per_page).all()
    
    # Build response
    result = []
    for org in organizations:
        owner = db.query(User).filter(User.id == org.owner_id).first()
        members_count = db.query(func.count(organization_members.c.user_id)).filter(
            organization_members.c.organization_id == org.id
        ).scalar()
        
        result.append(OrganizationAdminResponse(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            owner_id=str(org.owner_id),
            owner_email=owner.email if owner else "unknown",
            billing_plan=org.billing_plan,
            billing_email=org.billing_email,
            members_count=members_count,
            created_at=org.created_at,
            updated_at=org.updated_at
        ))
    
    return result


@router.delete("/organizations/{org_id}")
async def delete_organization_admin(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete organization as admin"""
    check_admin_permission(current_user)
    
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = db.query(Organization).filter(Organization.id == org_uuid).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Delete organization (cascade will handle related records)
    db.delete(org)
    db.commit()
    
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
    db: Session = Depends(get_db)
):
    """Get activity logs (admin only)"""
    check_admin_permission(current_user)
    
    query = db.query(ActivityLog).join(User, ActivityLog.user_id == User.id)
    
    # Apply filters
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            query = query.filter(ActivityLog.user_id == user_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID")
    
    if action:
        query = query.filter(ActivityLog.action == action)
    
    if start_date:
        query = query.filter(ActivityLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(ActivityLog.created_at <= end_date)
    
    # Order by most recent first
    query = query.order_by(desc(ActivityLog.created_at))
    
    # Apply pagination
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()
    
    # Build response
    result = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first()
        
        result.append(ActivityLogResponse(
            id=str(log.id),
            user_id=str(log.user_id),
            user_email=user.email if user else "unknown",
            action=log.action,
            details=log.details or {},
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at
        ))
    
    return result


@router.post("/sessions/revoke-all")
async def revoke_all_sessions_admin(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke all sessions (optionally for specific user)"""
    check_admin_permission(current_user)
    
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
            count = db.query(UserSession).filter(
                UserSession.user_id == user_uuid,
                UserSession.revoked == False
            ).update({"revoked": True})
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID")
    else:
        # Revoke all sessions except admin's current session
        # TODO: Get current session ID from token
        count = db.query(UserSession).filter(
            UserSession.revoked == False
        ).update({"revoked": True})
    
    db.commit()
    
    return {"message": f"Revoked {count} sessions"}


@router.post("/maintenance-mode")
async def toggle_maintenance_mode(
    enabled: bool,
    message: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle maintenance mode"""
    check_admin_permission(current_user)
    
    # TODO: Implement maintenance mode in Redis/cache
    # For now, we'll return a placeholder response
    
    return {
        "maintenance_mode": enabled,
        "message": message or "System is under maintenance",
        "note": "Maintenance mode not fully implemented yet"
    }


@router.get("/config")
async def get_system_config(
    current_user: User = Depends(get_current_user)
):
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
            "organizations_enabled": True
        },
        "limits": {
            "max_sessions_per_user": 10,
            "session_timeout_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_days": settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "password_reset_expire_minutes": 60,
            "magic_link_expire_minutes": 15,
            "invitation_expire_days": 7
        }
    }