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
from .models import User, UserStatus, Organization, OrganizationMember
from app.services.auth_service import AuthService

security = HTTPBearer()


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


async def get_jwt_service():
    """
    Get JWTService instance.

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

    return JWTService()


async def get_audit_service(
    db: AsyncSession = Depends(get_db)
):
    """
    Get AuditService instance with database dependency.

    Args:
        db: Database session

    Returns:
        AuditService: Configured audit service instance

    Example usage in router:
        @router.post("/action")
        async def perform_action(
            audit_service: AuditService = Depends(get_audit_service)
        ):
            await audit_service.log_action(...)
    """
    from app.services.audit_service import AuditService

    return AuditService(db)


async def get_webhook_service(
    db: AsyncSession = Depends(get_db)
):
    """
    Get WebhookService instance with database dependency.

    Args:
        db: Database session

    Returns:
        WebhookService: Configured webhook service instance
    """
    from app.services.webhooks import WebhookService

    return WebhookService(db)


async def get_rbac_service(
    db: AsyncSession = Depends(get_db),
    redis_client: ResilientRedisClient = Depends(get_redis)
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


async def get_sso_service(
    db: AsyncSession = Depends(get_db)
):
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
    redis: ResilientRedisClient = Depends(get_redis)
) -> User:
    """Get current authenticated user from JWT token (cached for 5 minutes)"""
    from app.core.jwt_manager import jwt_manager
    import json

    token = credentials.credentials

    # Decode token using JWT manager
    payload = jwt_manager.verify_token(token, token_type='access')
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get('sub')
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
        # If cache fails, continue with database query
        pass

    # Get user using async session
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.status == UserStatus.ACTIVE
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Cache negative result (shorter TTL to allow for status changes)
        try:
            await redis.set(cache_key, "invalid", ex=60)  # 1 minute
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="User not found")

    # Cache positive result (user exists and is active)
    try:
        await redis.set(cache_key, "valid", ex=300)  # 5 minutes
    except Exception:
        # If caching fails, still return the user
        pass

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current authenticated user from JWT token, returns None if not authenticated"""
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require user to be an admin"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


async def require_org_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require user to be an organization admin"""
    # Check if user has admin role in any organization using async session
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_(['admin', 'owner'])
        )
    )
    org_member = result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(status_code=403, detail="Organization admin privileges required")

    return current_user