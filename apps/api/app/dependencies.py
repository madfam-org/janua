"""
Shared dependencies for FastAPI routes and services

Ensures proper module structure for Railway deployment and dependency injection
"""

from typing import Optional

import structlog
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import ResilientRedisClient, get_redis
from app.database import get_db

from .models import OrganizationMember, User, UserStatus

logger = structlog.get_logger()

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
# Internal Service-to-Service Authentication
# ============================================================================


async def verify_internal_api_key(
    x_internal_api_key: str = Header(..., alias="X-Internal-API-Key"),
) -> bool:
    """Verify internal API key for service-to-service communication."""
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=503, detail="Internal API not configured"
        )
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ============================================================================
# Authentication & Authorization Dependencies (existing)
# ============================================================================


async def _authenticate_bearer(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
    redis: ResilientRedisClient,
    *,
    revocation: str = "strict",
) -> User:
    """The user a bearer access token names, after signature, expiry and revocation.

    The revocation list (sign-out, session revocation, password change,
    `POST /oauth/revoke`; see `app.services.token_revocation`) is read with
    one strict `EXISTS`. `revocation` says what a refusal or an outage means:

    - "strict" (every endpoint by default): a revoked token is 401; when Redis
      cannot answer this raises `RedisUnavailableError` (503 + Retry-After),
      the fail-closed policy of 2026-10-04.
    - "outage_ok" (endpoints that revoke sessions): a revoked token is 401,
      but while Redis cannot answer the signature-checked token is accepted.
    - "skip" (sign-out only): the list is not read. Signing out with a token
      that is already revoked only revokes again, so sign-out stays
      idempotent and keeps clearing cookies.
    """
    from app.core.jwt_manager import jwt_manager
    from app.core.redis_circuit_breaker import RedisUnavailableError
    from app.services import token_revocation

    token = credentials.credentials

    # Decode token using JWT manager
    payload = jwt_manager.verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    revoked = False
    if revocation != "skip":
        try:
            revoked = await token_revocation.is_revoked(redis, payload, "access")
        except RedisUnavailableError:
            if revocation != "outage_ok":
                raise
            logger.warning(
                "Revocation list unavailable; accepting a signature-checked token "
                "for a session-revoking request"
            )
    if revoked:
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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> User:
    """Get current authenticated user from JWT token (cached for 5 minutes).

    Refuses (401) a token on the revocation list; 503 when Redis cannot say.
    """
    return await _authenticate_bearer(credentials, db, redis, revocation="strict")


async def get_current_user_for_revocation(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> User:
    """`get_current_user` for endpoints that only revoke sessions.

    Identical while Redis is healthy: a revoked token is refused. While Redis
    cannot answer, the signature-checked token is accepted instead of a 503,
    so a person can still revoke sessions during an outage (owner decision
    2026-10-04: revocation keeps working on the session row). The most such a
    request can do is revoke sessions, never read or change anything else.
    """
    return await _authenticate_bearer(credentials, db, redis, revocation="outage_ok")


async def get_current_user_for_sign_out(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> User:
    """`get_current_user` for `/auth/signout` and `/auth/logout` only.

    Does not read the revocation list: sign-out ends the presenting token's own
    session (and the browser's estate cookie), so accepting an already-revoked
    token only revokes it again. Signature, expiry and an active user are still
    required. This keeps sign-out idempotent and available during an outage.
    """
    return await _authenticate_bearer(credentials, db, redis, revocation="skip")


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
            OrganizationMember.status == "active",
        ).limit(1)
    )
    org_member = result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(status_code=403, detail="Organization admin privileges required")

    return current_user
