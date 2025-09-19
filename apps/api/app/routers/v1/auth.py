"""
Authentication router for v1 API
"""

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets

from sqlalchemy.orm import Session
from sqlalchemy import or_

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from ...models import User, UserStatus, EmailVerification, PasswordReset, MagicLink, ActivityLog, Session as UserSession
from app.services.auth import AuthService
from app.services.email import EmailService
from app.config import settings
from app.dependencies import get_current_user

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

# Include OAuth sub-router
from app.routers.v1 import oauth
router.include_router(oauth.router)


# Request/Response Models
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v


class SignInRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str
    
    @model_validator(mode='after')
    def validate_credentials(self):
        if not self.username and not self.email:
            raise ValueError('Either email or username must be provided')
        return self


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class MagicLinkRequest(BaseModel):
    email: EmailStr
    redirect_url: Optional[str] = None


class VerifyMagicLinkRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignInResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


# Helper functions (get_current_user moved to app.dependencies)


def log_activity(db: Session, user_id: str, action: str, details: Dict = None, request: Request = None):
    """Log user activity"""
    activity = ActivityLog(
        user_id=user_id,
        action=action,
        details=details or {},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get('user-agent') if request else None
    )
    db.add(activity)
    db.commit()


# Authentication endpoints
@router.post("/signup", response_model=SignInResponse)
@limiter.limit("3/minute")  # Strict rate limiting for signup
async def sign_up(
    request: SignUpRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new user account"""
    if not settings.ENABLE_SIGNUPS:
        raise HTTPException(status_code=403, detail="Sign ups are currently disabled")
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    if request.username:
        existing_username = db.query(User).filter(User.username == request.username).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already taken")
    
    # Validate password
    valid, message = AuthService.validate_password_strength(request.password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    # Create user
    user = User(
        email=request.email,
        password_hash=AuthService.hash_password(request.password),
        first_name=request.first_name,
        last_name=request.last_name,
        username=request.username,
        status=UserStatus.ACTIVE
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user,
        ip_address=req.client.host,
        user_agent=req.headers.get('user-agent')
    )
    
    # Log activity
    log_activity(db, str(user.id), "signup", {"method": "email"}, req)
    
    # Send verification email in background
    if settings.EMAIL_ENABLED:
        verification_token = secrets.token_urlsafe(32)
        verification = EmailVerification(
            user_id=user.id,
            token=verification_token,
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(hours=48)
        )
        db.add(verification)
        db.commit()
        
        background_tasks.add_task(
            EmailService.send_verification_email,
            user.email,
            verification_token
        )
    
    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


@router.post("/signin", response_model=SignInResponse)
@limiter.limit("5/minute")  # Rate limiting for signin attempts
async def sign_in(
    request: SignInRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user and get tokens"""
    # Find user
    if request.email:
        user = db.query(User).filter(
            User.email == request.email,
            User.status == UserStatus.ACTIVE
        ).first()
    else:
        user = db.query(User).filter(
            User.username == request.username,
            User.status == UserStatus.ACTIVE
        ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not user.password_hash or not AuthService.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user,
        ip_address=req.client.host,
        user_agent=req.headers.get('user-agent')
    )
    
    # Log activity
    log_activity(db, str(user.id), "signin", {"method": "password"}, req)
    
    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    result = AuthService.refresh_access_token(db, request.refresh_token)
    
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    access_token, refresh_token = result
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/signout")
async def sign_out(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Sign out current session"""
    token = credentials.credentials
    payload = AuthService.decode_token(token, token_type='access')
    
    if payload:
        # Find and revoke session
        session = db.query(UserSession).filter(
            UserSession.access_token_jti == payload['jti']
        ).first()
        
        if session:
            AuthService.revoke_session(db, str(session.id))
    
    # Log activity
    log_activity(db, str(current_user.id), "signout", {})
    
    return {"message": "Successfully signed out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        email_verified=current_user.email_verified,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        profile_image_url=current_user.profile_image_url,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_sign_in_at=current_user.last_sign_in_at
    )


@router.post("/password/forgot")
@limiter.limit("3/hour")  # Strict rate limiting for password reset requests
async def forgot_password(
    req: Request,
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request password reset email"""
    user = db.query(User).filter(
        User.email == request.email,
        User.status == UserStatus.ACTIVE
    ).first()
    
    # Don't reveal if user exists
    if user and settings.EMAIL_ENABLED:
        # Create reset token
        reset_token = secrets.token_urlsafe(32)
        reset = PasswordReset(
            user_id=user.id,
            token=reset_token,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db.add(reset)
        db.commit()
        
        # Send email in background
        background_tasks.add_task(
            EmailService.send_password_reset_email,
            user.email,
            reset_token
        )
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/password/reset")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password with token"""
    # Find valid reset token
    reset = db.query(PasswordReset).filter(
        PasswordReset.token == request.token,
        PasswordReset.used == False,
        PasswordReset.expires_at > datetime.utcnow()
    ).first()
    
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Validate new password
    valid, message = AuthService.validate_password(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    # Update password
    user = db.query(User).filter(User.id == reset.user_id).first()
    user.password_hash = AuthService.hash_password(request.new_password)
    
    # Mark token as used
    reset.used = True
    reset.used_at = datetime.utcnow()
    
    db.commit()
    
    # Log activity
    log_activity(db, str(user.id), "password_reset", {})
    
    return {"message": "Password successfully reset"}


@router.post("/password/change")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password for authenticated user"""
    # Verify current password
    if not AuthService.verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    valid, message = AuthService.validate_password(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    # Update password
    current_user.password_hash = AuthService.hash_password(request.new_password)
    db.commit()
    
    # Log activity
    log_activity(db, str(current_user.id), "password_change", {})
    
    return {"message": "Password successfully changed"}


@router.post("/email/verify")
async def verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """Verify email with token"""
    # Find valid verification token
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == request.token,
        EmailVerification.verified == False,
        EmailVerification.expires_at > datetime.utcnow()
    ).first()
    
    if not verification:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
    # Mark email as verified
    user = db.query(User).filter(User.id == verification.user_id).first()
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    
    # Mark verification as used
    verification.verified = True
    verification.verified_at = datetime.utcnow()
    
    db.commit()
    
    # Log activity
    log_activity(db, str(user.id), "email_verified", {})
    
    return {"message": "Email successfully verified"}


@router.post("/email/resend-verification")
@limiter.limit("5/hour")  # Rate limiting for email verification requests
async def resend_verification_email(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resend verification email"""
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")
    
    # Create new verification token
    verification_token = secrets.token_urlsafe(32)
    verification = EmailVerification(
        user_id=current_user.id,
        token=verification_token,
        email=current_user.email,
        expires_at=datetime.utcnow() + timedelta(hours=48)
    )
    db.add(verification)
    db.commit()
    
    # Send email in background
    background_tasks.add_task(
        EmailService.send_verification_email,
        current_user.email,
        verification_token
    )
    
    return {"message": "Verification email sent"}


@router.post("/magic-link")
@limiter.limit("5/hour")  # Rate limiting for magic link requests
async def send_magic_link(
    req: Request,
    request: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Send magic link for passwordless signin"""
    if not settings.ENABLE_MAGIC_LINKS:
        raise HTTPException(status_code=403, detail="Magic links are disabled")
    
    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")
    
    # Find or create user
    user = db.query(User).filter(
        User.email == request.email,
        User.status == UserStatus.ACTIVE
    ).first()
    
    if not user:
        # Create user without password for magic link only
        user = User(
            email=request.email,
            email_verified=True,  # Auto-verify for magic link users
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create magic link token
    magic_token = secrets.token_urlsafe(32)
    magic_link = MagicLink(
        user_id=user.id,
        token=magic_token,
        redirect_url=request.redirect_url,
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db.add(magic_link)
    db.commit()
    
    # Send email in background
    background_tasks.add_task(
        EmailService.send_magic_link_email,
        user.email,
        magic_token,
        request.redirect_url
    )
    
    return {"message": "Magic link sent to email"}


@router.post("/magic-link/verify", response_model=SignInResponse)
async def verify_magic_link(
    request: VerifyMagicLinkRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """Sign in with magic link token"""
    # Find valid magic link
    magic_link = db.query(MagicLink).filter(
        MagicLink.token == request.token,
        MagicLink.used == False,
        MagicLink.expires_at > datetime.utcnow()
    ).first()
    
    if not magic_link:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")
    
    # Get user
    user = db.query(User).filter(
        User.id == magic_link.user_id,
        User.status == UserStatus.ACTIVE
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    
    # Mark magic link as used
    magic_link.used = True
    magic_link.used_at = datetime.utcnow()
    
    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user,
        ip_address=req.client.host,
        user_agent=req.headers.get('user-agent')
    )
    
    # Log activity
    log_activity(db, str(user.id), "signin", {"method": "magic_link"}, req)
    
    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )