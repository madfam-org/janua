from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

# Initialize logger first
logger = structlog.get_logger(__name__)

from app.config import settings
from app.core.database import get_db
from app.core.redis import RateLimiter, SessionStore, get_redis

# Import services with error handling for production stability
try:
    from app.services.auth_service import AuthService

    AUTH_SERVICE_AVAILABLE = True
except Exception as e:
    logger.error("Failed to import AuthService", error_type=type(e).__name__)
    AUTH_SERVICE_AVAILABLE = False

try:
    from app.services.resend_email_service import get_resend_email_service

    EMAIL_SERVICE_AVAILABLE = True
except Exception as e:
    logger.error("Failed to import ResendEmailService", error_type=type(e).__name__)
    EMAIL_SERVICE_AVAILABLE = False
from app.models.user import User

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()


def _redact_email(email: str) -> str:
    """Redact email address for logging (shows first 2 chars and domain)."""
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


# Simple status endpoint to verify router is working
@router.get("/status")
async def auth_status():
    """Simple auth router status check"""
    return {
        "status": "auth router working",
        "endpoints": ["signup", "signin", "signout", "refresh", "me"],
        "router_name": "auth",
        "auth_service": "available" if AUTH_SERVICE_AVAILABLE else "unavailable",
        "email_service": "available" if EMAIL_SERVICE_AVAILABLE else "unavailable",
    }


# Request/Response models
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12)
    name: Optional[str] = None
    tenant_id: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    email_verified: bool
    created_at: str
    updated_at: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., description="Verification token")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8)


# Auth endpoints
@router.post("/signup", response_model=UserResponse)
async def signup(
    request: SignUpRequest, response: Response, db=Depends(get_db), redis=Depends(get_redis)
):
    """Register a new user"""
    # Check if AuthService is available
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )
    # Check rate limit
    limiter = RateLimiter(redis)
    allowed, remaining = await limiter.check_rate_limit(
        f"signup:{request.email}",
        limit=5,
        window=3600,  # 5 signups per hour per email
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many signup attempts"
        )

    try:
        # Create user with real implementation
        from uuid import UUID

        tenant_id = UUID(request.tenant_id) if request.tenant_id else None
        user = await AuthService.create_user(
            db=db,
            email=request.email,
            password=request.password,
            name=request.name,
            tenant_id=tenant_id,
        )

        # Send verification email (optional for beta)
        if EMAIL_SERVICE_AVAILABLE:
            try:
                email_service = get_resend_email_service(redis)
                verification_url = (
                    f"{settings.BASE_URL}/auth/verify-email?token=temp-token-{user.id}"
                )
                await email_service.send_verification_email(
                    to_email=user.email, user_name=user.name, verification_url=verification_url
                )
                logger.info("Verification email sent", email=_redact_email(user.email))
            except Exception as e:
                logger.error("Failed to send verification email", error_type=type(e).__name__)
                # Continue with signup even if email fails for beta
        else:
            logger.warning("Email service unavailable - skipping verification email")

        return UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            email_verified=user.email_verified,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Signup failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed"
        )


@router.post("/signin", response_model=TokenResponse)
async def signin(
    request: SignInRequest,
    response: Response,
    req: Request,
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Sign in with email and password"""
    # Check if AuthService is available
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )
    # Check rate limit
    limiter = RateLimiter(redis)
    allowed, remaining = await limiter.check_rate_limit(
        f"signin:{request.email}",
        limit=10,
        window=300,  # 10 attempts per 5 minutes
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many signin attempts"
        )

    # Authenticate user with real implementation
    user = await AuthService.authenticate_user(
        db=db, email=request.email, password=request.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Create real session with JWT tokens
    access_token, refresh_token, session = await AuthService.create_session(
        db=db,
        user=user,
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("user-agent"),
    )

    # Set secure cookies for web apps (with optional cross-subdomain SSO)
    if settings.SECURE_COOKIES:
        cookie_kwargs = {
            "httponly": True,
            "secure": True,
            "samesite": "lax",  # Use lax for cross-subdomain SSO compatibility
            "max_age": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
        if settings.COOKIE_DOMAIN:
            cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

        refresh_cookie_kwargs = {
            "httponly": True,
            "secure": True,
            "samesite": "lax",
            "max_age": settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        }
        if settings.COOKIE_DOMAIN:
            refresh_cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

        response.set_cookie(key="access_token", value=access_token, **cookie_kwargs)
        response.set_cookie(key="refresh_token", value=refresh_token, **refresh_cookie_kwargs)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/signout")
async def signout(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis=Depends(get_redis),
):
    """Sign out and invalidate session"""
    try:
        token = credentials.credentials

        # Extract user ID from token (assuming JWT format)
        try:
            import jwt

            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("sub")
        except (jwt.InvalidTokenError, jwt.DecodeError, Exception) as e:
            # If token parsing fails, still proceed with cleanup
            logger.debug("Token parsing failed during logout", error_type=type(e).__name__)
            user_id = None

        # Create session store instance
        session_store = SessionStore(redis)

        # Delete session from Redis if user ID available
        if user_id:
            await session_store.delete_session(user_id)

        # Add token to blacklist with expiration
        blacklist_key = f"blacklist:{token}"
        await redis.setex(blacklist_key, 86400, "1")  # 24 hour blacklist

        # Clear authentication cookies (with domain if configured for SSO)
        delete_kwargs = {}
        if settings.COOKIE_DOMAIN:
            delete_kwargs["domain"] = settings.COOKIE_DOMAIN
        response.delete_cookie("access_token", **delete_kwargs)
        response.delete_cookie("refresh_token", **delete_kwargs)

        logger.info("User signed out successfully", user_id=user_id)
        return {"message": "Successfully signed out"}

    except Exception as e:
        logger.error("Signout failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signout failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db=Depends(get_db), redis=Depends(get_redis)):
    """Refresh access token using refresh token"""
    # Refresh tokens with real implementation
    tokens = await AuthService.refresh_tokens(db=db, refresh_token=request.refresh_token)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )

    access_token, refresh_token = tokens

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db=Depends(get_db)
):
    """Get current user information"""
    # Validate access token
    payload = await AuthService.verify_token(credentials.credentials, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    # Fetch user from database
    from uuid import UUID

    user = await db.get(User, UUID(payload.get("sub")))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        email_verified=user.email_verified,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.get("/session")
async def check_session(
    req: Request,
    db=Depends(get_db),
):
    """
    Check if the user has an active session via cookies.

    This endpoint is used for silent authentication / SSO across subdomains.
    It reads the access_token from HTTP-only cookies (set with COOKIE_DOMAIN)
    and returns user info if valid.

    Returns:
        - 200 with user info if session is valid
        - 401 if no session or invalid token
    """
    # Try to get access token from cookies
    access_token = req.cookies.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No session cookie found"
        )

    # Validate access token
    payload = await AuthService.verify_token(access_token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        )

    # Fetch user from database
    from uuid import UUID

    user = await db.get(User, UUID(payload.get("sub")))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )

    return {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "email_verified": user.email_verified,
            "is_admin": getattr(user, "is_admin", False),
        },
        "session": {
            "expires_at": payload.get("exp"),
        },
    }


@router.post("/verify-email")
async def verify_email(request: VerifyEmailRequest, db=Depends(get_db), redis=Depends(get_redis)):
    """Verify email address with token"""
    try:
        # Validate verification token
        email_service = get_email_service(redis)
        token_info = await email_service.verify_email_token(request.token)

        # Update user email_verified status in database
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.email == token_info["email"]))
        user = result.scalar_one_or_none()

        if user:
            user.email_verified = True
            await db.commit()
            logger.info("Email verified", user_id=str(user.id))

        # Send welcome email after verification
        try:
            email_service = get_resend_email_service(redis)
            await email_service.send_welcome_email(
                to_email=token_info["email"], user_name=token_info.get("user_name")
            )
        except Exception as e:
            logger.error("Failed to send welcome email", error_type=type(e).__name__)
            # Continue even if welcome email fails

        logger.info("Email verification successful", email=_redact_email(token_info["email"]))

        return {
            "message": "Email verified successfully",
            "email": token_info["email"],
            "verified_at": token_info["created_at"],
        }

    except Exception as e:
        logger.error("Email verification failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token"
        )


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, redis=Depends(get_redis)):
    """Request password reset"""
    # Check rate limit
    limiter = RateLimiter(redis)
    allowed, remaining = await limiter.check_rate_limit(
        f"forgot_password:{request.email}",
        limit=3,
        window=3600,  # 3 requests per hour
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many password reset requests"
        )

    # Send password reset email (regardless of user existence for security)
    email_service = get_resend_email_service(redis)
    try:
        reset_url = f"{settings.BASE_URL}/auth/reset-password?token=temp-reset-token"
        await email_service.send_password_reset_email(
            to_email=request.email,
            user_name=request.email.split("@")[0],  # Use email prefix as name
            reset_url=reset_url,
        )
        logger.info("Password reset email sent", email=_redact_email(request.email))
    except Exception as e:
        logger.error("Failed to send password reset email", error_type=type(e).__name__)
        # Always return success for security (don't reveal if email exists)

    return {"message": "Password reset email sent if account exists"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db=Depends(get_db)):
    """Reset password with token"""
    try:
        # Validate reset token from Redis
        redis_client = get_redis()
        stored_email = await redis_client.get(f"reset_token:{request.token}")

        if not stored_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
            )

        # Get user by email
        user = db.query(User).filter(User.email == stored_email.decode()).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Hash new password
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__ident="2b")
        hashed_password = pwd_context.hash(request.new_password)

        # Update user password
        user.password_hash = hashed_password
        await db.commit()

        # SECURITY: Invalidate ALL sessions when password changes
        # This prevents any compromised sessions from remaining valid
        from app.services.auth_service import AuthService

        revoked_count = await AuthService.invalidate_user_sessions(db, user.id)
        logger.info(
            "Invalidated sessions on password reset",
            user_id=str(user.id),
            sessions_revoked=revoked_count,
        )

        # Remove the reset token
        await redis_client.delete(f"reset_token:{request.token}")

        logger.info("Password reset successfully", user_id=str(user.id))
        return {"message": "Password reset successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password reset failed", error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password reset failed"
        )


# WebAuthn/Passkeys endpoints
# Note: Full WebAuthn implementation is in /v1/passkeys router
# These are legacy endpoints - redirect to the v1 implementation


@router.post("/passkeys/register/options")
async def passkey_register_options(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get WebAuthn registration options

    Delegates to /v1/passkeys/register/options for full implementation
    """
    from webauthn.helpers import bytes_to_base64url

    from app.routers.v1.passkeys import generate_registration_options as webauthn_generate

    # Generate WebAuthn registration options
    options = webauthn_generate(
        rp_id=settings.WEBAUTHN_RP_ID or "localhost",
        rp_name=settings.WEBAUTHN_RP_NAME or "Janua",
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.full_name or current_user.email,
        authenticator_selection={
            "authenticator_attachment": "cross-platform",
            "require_resident_key": False,
            "user_verification": "preferred",
        },
        timeout=settings.WEBAUTHN_TIMEOUT or 60000,
    )

    # Store challenge in Redis with 5-minute expiry
    from app.core.redis import get_redis

    challenge = bytes_to_base64url(options.challenge)
    redis_client = await get_redis()
    await redis_client.setex(
        f"passkey_challenge:{current_user.id}",
        300,  # 5 minutes
        challenge,
    )

    # Convert to JSON-serializable format
    return {
        "challenge": challenge,
        "rp": {"id": options.rp.id, "name": options.rp.name},
        "user": {
            "id": bytes_to_base64url(options.user.id),
            "name": options.user.name,
            "displayName": options.user.display_name,
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},  # ES256
            {"type": "public-key", "alg": -257},  # RS256
        ],
        "timeout": options.timeout,
        "authenticatorSelection": {
            "authenticatorAttachment": "cross-platform",
            "requireResidentKey": False,
            "userVerification": "preferred",
        },
    }


@router.post("/passkeys/register")
async def passkey_register(
    credential: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new passkey

    Delegates to /v1/passkeys/register/verify for full implementation
    """
    from datetime import datetime

    import structlog
    from webauthn.helpers import base64url_to_bytes

    from app.core.redis import get_redis
    from app.models import Passkey
    from app.routers.v1.passkeys import verify_registration_response as webauthn_verify

    logger = structlog.get_logger()

    # Retrieve challenge from Redis
    redis_client = await get_redis()
    stored_challenge = await redis_client.get(f"passkey_challenge:{current_user.id}")

    if not stored_challenge:
        raise HTTPException(status_code=400, detail="Challenge not found or expired")

    # Verify WebAuthn registration
    try:
        verification = webauthn_verify(
            credential=credential,
            expected_challenge=base64url_to_bytes(stored_challenge),
            expected_origin=settings.WEBAUTHN_ORIGIN or "http://localhost:3000",
            expected_rp_id=settings.WEBAUTHN_RP_ID or "localhost",
        )

        if not verification.verified:
            raise HTTPException(status_code=400, detail="Registration verification failed")

        # Store passkey in database
        from webauthn.helpers import bytes_to_base64url

        passkey = Passkey(
            user_id=current_user.id,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
            name=f"Passkey {datetime.utcnow().strftime('%Y-%m-%d')}",
            authenticator_attachment=credential.get("authenticatorAttachment"),
            created_at=datetime.utcnow(),
        )

        db.add(passkey)
        await db.commit()
        await db.refresh(passkey)

        # Clean up challenge
        await redis_client.delete(f"passkey_challenge:{current_user.id}")

        logger.info("Passkey registered", user_id=str(current_user.id), passkey_id=str(passkey.id))

        return {
            "message": "Passkey registered successfully",
            "passkey_id": str(passkey.id),
            "name": passkey.name,
        }

    except Exception as e:
        logger.error(
            "Passkey registration failed", error_type=type(e).__name__, user_id=str(current_user.id)
        )
        raise HTTPException(status_code=400, detail=f"Registration verification failed: {str(e)}")
