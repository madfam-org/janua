"""
Authentication Router - Complete Implementation
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from app.core.database import get_db
from app.core.redis import get_redis, SessionStore
from app.models.user import User, Session
from app.services.auth_service import AuthService
from app.exceptions import AuthenticationError, ValidationError
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = structlog.get_logger()
security = HTTPBearer()


def _redact_email(email: str) -> str:
    """Redact email address for logging (shows first 2 chars and domain)."""
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


# Request/Response Models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str
    tenant_id: Optional[str] = None


class SigninRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    email_verified: bool
    created_at: datetime


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class EmailVerificationRequest(BaseModel):
    token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: SignupRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = await db.scalar(select(User).where(User.email == request.email))
        if existing_user:
            raise ValidationError("Email already registered")

        # Create new user
        user = await AuthService.create_user(
            db=db,
            email=request.email,
            password=request.password,
            name=request.name,
            tenant_id=request.tenant_id,
        )

        # Create session and tokens
        access_token, refresh_token, session = await AuthService.create_session(db=db, user=user)

        # Send verification email
        verification_token = str(uuid4())
        await redis.setex(f"email_verify:{verification_token}", 86400, str(user.id))  # 24 hours

        # In production, send actual email here
        # Note: Log email redacted, token not logged for security
        logger.info("Verification email queued", email=_redact_email(user.email))

        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except Exception as e:
        await db.rollback()
        logger.error("Signup failed", error_type=type(e).__name__)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/signin", response_model=TokenResponse)
async def signin(
    request: SigninRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    """Sign in with email and password"""
    try:
        # Authenticate user
        user = await AuthService.authenticate_user(
            db=db, email=request.email, password=request.password
        )

        if not user:
            raise AuthenticationError("Invalid credentials")

        # Create session and tokens
        access_token, refresh_token, session = await AuthService.create_session(db=db, user=user)

        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error("Signin failed", error_type=type(e).__name__)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/signout")
async def signout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Sign out and invalidate session"""
    try:
        # Verify and decode token
        claims = AuthService.verify_access_token(credentials.credentials)

        # Get session JTI from token
        jti = claims.get("jti")
        if jti:
            # Add token to blacklist
            ttl = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
            await redis.setex(f"blacklist:{jti}", ttl, "1")

            # Find and invalidate session
            session = await db.scalar(select(Session).where(Session.access_token_jti == jti))

            if session:
                session.is_active = False
                session.updated_at = datetime.now(timezone.utc)
                await db.commit()

                # Delete session from Redis if using session store
                session_store = SessionStore(redis)
                await session_store.delete(str(session.id))

        return {"message": "Successfully signed out"}

    except Exception as e:
        logger.error("Signout failed", error_type=type(e).__name__)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to sign out")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        claims = AuthService.verify_refresh_token(request.refresh_token)

        # Check if refresh token is blacklisted
        jti = claims.get("jti")
        if jti:
            blacklisted = await redis.get(f"blacklist:{jti}")
            if blacklisted:
                raise AuthenticationError("Refresh token has been revoked")

        # Get user
        user_id = claims.get("sub")
        user = await db.scalar(select(User).where(User.id == user_id))

        if not user:
            raise AuthenticationError("User not found")

        # Create new tokens
        access_token, refresh_token, session = await AuthService.create_session(db=db, user=user)

        # Optionally blacklist old refresh token (token rotation)
        if jti:
            ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
            await redis.setex(f"blacklist:{jti}", ttl, "1")

        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error("Token refresh failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Get current user information"""
    try:
        # Verify access token
        claims = AuthService.verify_access_token(credentials.credentials)

        # Get user from database
        user_id = claims.get("sub")
        user = await db.scalar(select(User).where(User.id == user_id))

        if not user:
            raise AuthenticationError("User not found")

        return UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name or "",
            email_verified=user.email_verified,
            created_at=user.created_at,
        )

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error("Failed to get user", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve user information"
        )


@router.post("/verify-email")
async def verify_email(
    request: EmailVerificationRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    """Verify email address with token"""
    try:
        # Get user ID from token
        user_id = await redis.get(f"email_verify:{request.token}")

        if not user_id:
            raise ValidationError("Invalid or expired verification token")

        # Update user's email verification status
        user = await db.scalar(select(User).where(User.id == user_id))

        if not user:
            raise ValidationError("User not found")

        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)

        # Delete verification token
        await redis.delete(f"email_verify:{request.token}")

        await db.commit()

        return {"message": "Email verified successfully"}

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error("Email verification failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to verify email"
        )


@router.post("/request-password-reset")
async def request_password_reset(
    request: PasswordResetRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    """Request password reset link"""
    try:
        # Check if user exists
        user = await db.scalar(select(User).where(User.email == request.email))

        # Always return success even if user doesn't exist (security)
        if user:
            # Generate reset token
            reset_token = str(uuid4())
            await redis.setex(f"password_reset:{reset_token}", 3600, str(user.id))  # 1 hour

            # In production, send actual email here
            # Note: Log only redacted email, never log tokens
            logger.info("Password reset email queued", email=_redact_email(user.email))

        return {"message": "If the email exists, a password reset link has been sent"}

    except Exception as e:
        logger.error("Password reset request failed", error_type=type(e).__name__)
        # Still return success for security
        return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    """Reset password with token"""
    try:
        # Get user ID from token
        user_id = await redis.get(f"password_reset:{request.token}")

        if not user_id:
            raise ValidationError("Invalid or expired reset token")

        # Update user's password
        user = await db.scalar(select(User).where(User.id == user_id))

        if not user:
            raise ValidationError("User not found")

        # Hash new password
        user.password_hash = AuthService.hash_password(request.new_password)
        user.updated_at = datetime.now(timezone.utc)

        # Delete reset token
        await redis.delete(f"password_reset:{request.token}")

        # Invalidate all existing sessions for security
        await db.execute(
            update(Session)
            .where(Session.user_id == user.id)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )

        await db.commit()

        return {"message": "Password reset successfully"}

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error("Password reset failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to reset password"
        )


# WebAuthn endpoints placeholder
@router.post("/passkeys/register/options")
async def passkey_register_options(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Generate WebAuthn registration options"""
    # This requires webauthn library implementation
    return {
        "message": "WebAuthn registration options would be generated here",
        "challenge": str(uuid4()),
        "rp": {"name": "Janua", "id": "janua.dev"},
        "user": {"id": str(uuid4()), "name": "user@example.com", "displayName": "User"},
    }


@router.post("/passkeys/register")
async def passkey_register(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Register WebAuthn credential"""
    # This requires webauthn library implementation
    return {"message": "WebAuthn credential would be registered here"}
