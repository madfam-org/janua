"""
Shared dependencies for FastAPI routes and services

Ensures proper module structure for Railway deployment and dependency injection
"""

from fastapi import Depends, HTTPException
from typing import Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.redis import get_redis, ResilientRedisClient
from .models import User, UserStatus, OrganizationMember

security = HTTPBearer()
# Optional security scheme for endpoints that work with or without authentication
# auto_error=False prevents 403 when no Authorization header is present
security_optional = HTTPBearer(auto_error=False)


# ============================================================================
# Service Dependencies
# ============================================================================
# These factory functions enable dependency injection for services, making
# them easier to test, mock, and configure across the application.
# ============================================================================


async def get_email_service():
    """
    Get EmailService instance with Redis dependency.

    Returns:
        EmailService: Configured email service instance

    Example usage in router:
        @router.post("/send-email")
        async def send_email(
            email_service: EmailService = Depends(get_email_service)
        ):
            await email_service.send_verification_email(...)
    """
    from app.services.email_service import EmailService

    redis_client = await get_redis()
    return EmailService(redis_client=redis_client)


async def get_jwt_service(
    db: AsyncSession = Depends(get_db), redis: ResilientRedisClient = Depends(get_redis)
):
    """
    Get JWTService instance with database and redis dependencies.

    Args:
        db: Database session
        redis: Redis client

    Returns:
        JWTService: Configured JWT service instance

    Example usage in router:
        @router.post("/token")
        async def create_token(
            jwt_service: JWTService = Depends(get_jwt_service)
        ):
            return jwt_service.create_token(...)
    """
    from app.services.jwt_service import JWTService

    return JWTService(db, redis)


async def get_audit_service():
    """
    Get AuditService instance.

    Returns:
        AuditService: Configured audit service instance

    Example usage in router:
        @router.post("/action")
        async def perform_action(
            audit_service: AuditService = Depends(get_audit_service),
            db: AsyncSession = Depends(get_db)
        ):
            await audit_service.log_action(db, ...)
    """
    from app.services.audit_service import AuditService

    return AuditService()


async def get_webhook_service():
    """
    Get WebhookService instance.

    Returns:
        WebhookService: Configured webhook service instance
    """
    from app.services.webhooks import WebhookService

    return WebhookService()


async def get_rbac_service(
    db: AsyncSession = Depends(get_db), redis_client: ResilientRedisClient = Depends(get_redis)
):
    """
    Get RBACService instance with dependencies.

    Args:
        db: Database session
        redis_client: Redis client for caching

    Returns:
        RBACService: Configured RBAC service instance

    Example usage in router:
        @router.get("/permissions")
        async def check_permissions(
            rbac_service: RBACService = Depends(get_rbac_service),
            current_user: User = Depends(get_current_user)
        ):
            return await rbac_service.check_permission(current_user, "read:users")
    """
    from app.services.rbac_service import RBACService

    return RBACService(db, redis_client)


async def get_sso_service(db: AsyncSession = Depends(get_db)):
    """
    Get SSOService instance with database dependency.

    Args:
        db: Database session

    Returns:
        SSOService: Configured SSO service instance
    """
    from app.services.sso_service import SSOService

    return SSOService(db)


# ============================================================================
# Authentication & Authorization Dependencies (existing)
# ============================================================================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> User:
    """Get current authenticated user from JWT token (cached for 5 minutes)"""
    from app.core.jwt_manager import jwt_manager

    token = credentials.credentials

    # Decode token using JWT manager
    payload = jwt_manager.verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Check cache for user validity (existence + active status)
    # This prevents DB queries for deleted/non-existent users
    cache_key = f"user:valid:{user_id}"
    try:
        cached_status = await redis.get(cache_key)
        if cached_status == "invalid":
            # User was previously checked and found invalid
            raise HTTPException(status_code=401, detail="User not found")
    except HTTPException:
        raise
    except Exception:
        pass  # Intentionally ignoring - cache failure is non-critical, continue with database query

    # Get user using async session
    result = await db.execute(
        select(User).where(User.id == user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Cache negative result (shorter TTL to allow for status changes)
        try:
            await redis.set(cache_key, "invalid", ex=60)  # 1 minute
        except Exception:
            pass  # Intentionally ignoring - caching negative result is optional optimization
        raise HTTPException(status_code=401, detail="User not found")

    # Cache positive result (user exists and is active)
    try:
        await redis.set(cache_key, "valid", ex=300)  # 5 minutes
    except Exception:
        pass  # Intentionally ignoring - caching is optional optimization, user authentication succeeded

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> Optional[User]:
    """Get current authenticated user from JWT token, returns None if not authenticated.

    Uses security_optional (auto_error=False) to allow unauthenticated requests
    to proceed without raising 403. This is critical for OAuth authorize endpoint
    which needs to redirect unauthenticated users to login instead of blocking them.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db, redis)
    except HTTPException:
        return None


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require user to be an admin"""
    if not hasattr(current_user, "is_admin") or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


def require_verified_email(current_user: User = Depends(get_current_user)) -> User:
    """
    Require user to have verified their email address.

    This dependency should be used on sensitive endpoints like:
    - OAuth/OIDC authorization (issuing tokens to third parties)
    - Creating organizations
    - Sensitive account changes
    - Admin operations

    Raises:
        HTTPException: 403 if email is not verified (or within grace period for new accounts)
    """
    from datetime import datetime, timedelta
    from app.config import settings

    if not settings.REQUIRE_EMAIL_VERIFICATION:
        return current_user

    if getattr(current_user, "email_verified", False):
        return current_user

    # Check if within grace period for new accounts
    if current_user.created_at:
        grace_period = timedelta(hours=settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
        grace_deadline = current_user.created_at + grace_period
        if datetime.utcnow() < grace_deadline:
            return current_user

    raise HTTPException(
        status_code=403,
        detail="Email verification required. Please verify your email address to continue.",
    )


async def require_org_admin(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    """Require user to be an organization admin"""
    # Check if user has admin role in any organization using async session
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_(["admin", "owner"]),
        )
    )
    org_member = result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(status_code=403, detail="Organization admin privileges required")

    return current_user
