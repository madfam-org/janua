"""
Authentication router for v1 API
"""

import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.services.auth_service import AuthService
from app.services.email import EmailService
from app.services.account_lockout_service import AccountLockoutService

from ...models import ActivityLog, EmailVerification, MagicLink, PasswordReset, User, UserStatus
from ...models import Session as UserSession

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

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if v and not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v


class SignInRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def validate_credentials(self):
        if not self.username and not self.email:
            raise ValueError("Either email or username must be provided")
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
    is_admin: bool = False
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


async def log_activity(
    db: Session, user_id: str, action: str, details: Dict = None, request: Request = None
):
    """Log user activity"""
    activity = ActivityLog(
        user_id=user_id,
        action=action,
        activity_metadata=details or {},  # Model uses activity_metadata, not details
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(activity)
    await db.commit()


# Authentication endpoints
@router.post("/signup", response_model=SignInResponse)
@limiter.limit("3/minute")  # Strict rate limiting for signup
async def sign_up(
    request: Request,
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new user account"""
    if not settings.ENABLE_SIGNUPS:
        raise HTTPException(status_code=403, detail="Sign ups are currently disabled")

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == signup_data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if username already exists
    if signup_data.username:
        result = await db.execute(select(User).where(User.username == signup_data.username))
        existing_username = result.scalar_one_or_none()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already taken")

    # Validate password
    valid, message = AuthService.validate_password_strength(signup_data.password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Create user
    user = User(
        email=signup_data.email,
        password_hash=AuthService.hash_password(signup_data.password),
        first_name=signup_data.first_name,
        last_name=signup_data.last_name,
        username=signup_data.username,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Log activity
    await log_activity(db, str(user.id), "signup", {"method": "email"}, request)

    # Send verification email in background
    if settings.EMAIL_ENABLED:
        verification_token = secrets.token_urlsafe(32)
        verification = EmailVerification(
            user_id=user.id,
            token=verification_token,
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(hours=48),
        )
        db.add(verification)
        await db.commit()

        background_tasks.add_task(
            EmailService.send_verification_email, user.email, verification_token
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
            is_admin=getattr(user, 'is_admin', False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.post("/signin", response_model=SignInResponse)
@limiter.limit("5/minute")  # Rate limiting for signin attempts
async def sign_in(credentials: SignInRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and get tokens"""
    # Find user - we need to find the user first to check lockout status
    # Note: We look for any user (not just ACTIVE) to check lockout, then verify status
    if credentials.email:
        result = await db.execute(
            select(User).where(User.email == credentials.email)
        )
        user = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(User).where(User.username == credentials.username)
        )
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if account is locked
    is_locked, seconds_remaining = AccountLockoutService.is_account_locked(user)
    if is_locked:
        minutes_remaining = (seconds_remaining or 0) // 60 + 1
        raise HTTPException(
            status_code=423,  # HTTP 423 Locked
            detail=f"Account temporarily locked due to too many failed login attempts. "
                   f"Please try again in {minutes_remaining} minute(s).",
        )

    # Check user status after lockout check
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not user.password_hash or not AuthService.verify_password(
        credentials.password, user.password_hash
    ):
        # Record failed attempt
        ip_address = request.client.host if request.client else None
        is_now_locked, lock_seconds = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=ip_address
        )
        if is_now_locked:
            minutes_remaining = (lock_seconds or 0) // 60 + 1
            raise HTTPException(
                status_code=423,
                detail=f"Account locked due to too many failed login attempts. "
                       f"Please try again in {minutes_remaining} minute(s).",
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Reset failed attempts on successful login
    await AccountLockoutService.reset_failed_attempts(db, user)

    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Log activity
    await log_activity(db, str(user.id), "signin", {"method": "password"}, request)

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, 'is_admin', False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.get("/session")
async def check_session(
    request: Request,
    db: Session = Depends(get_db),
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
    access_token = request.cookies.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="No session cookie found"
        )

    # Validate access token
    payload = AuthService.verify_token(access_token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )

    # Fetch user from database
    from uuid import UUID as PyUUID
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )

    result = await db.execute(
        select(User).where(User.id == PyUUID(user_id), User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive"
        )

    return {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email_verified": user.email_verified,
            "roles": getattr(user, 'roles', []),
            "permissions": getattr(user, 'permissions', []),
            "is_admin": getattr(user, 'is_admin', False),
        },
        "session": {
            "expires_at": payload.get("exp"),
        }
    }


# GET /login - Render login form for OAuth flows
@router.get("/login")
async def login_page(
    request: Request,
    next: Optional[str] = None,
    client_id: Optional[str] = None,
    client_name: Optional[str] = None,
):
    """
    Render login page for OAuth authorization flows.

    This endpoint serves an HTML login form that:
    1. Accepts email/password credentials
    2. POSTs to /api/v1/auth/login
    3. On success, redirects to the 'next' URL (OAuth authorize endpoint)

    Query params:
    - next: URL to redirect to after successful login
    - client_id: OAuth client requesting authorization
    - client_name: Human-readable name of the OAuth client
    """
    from fastapi.responses import HTMLResponse

    # Escape values for HTML safety
    import html
    next_url = html.escape(next or "/")
    app_name = html.escape(client_name or "Application")

    html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo h1 {{
            font-size: 28px;
            color: #333;
            margin-bottom: 8px;
        }}
        .logo p {{
            color: #666;
            font-size: 14px;
        }}
        .app-info {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .app-info span {{
            color: #666;
            font-size: 13px;
        }}
        .app-info strong {{
            color: #333;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        button:disabled {{
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: none;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>🔐 Janua</h1>
            <p>Identity Platform</p>
        </div>

        <div class="app-info">
            <span>Signing in to <strong>{app_name}</strong></span>
        </div>

        <div class="error" id="error"></div>

        <form id="loginForm" method="POST" action="/api/v1/auth/login-form">
            <input type="hidden" name="next" value="{next_url}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required autocomplete="email" autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>
            <button type="submit" id="submitBtn">Sign In</button>
        </form>

        <div class="footer">
            Powered by Janua &bull; Secure Authentication
        </div>
    </div>
</body>
</html>
'''
    return HTMLResponse(content=html_content)


# Form-based login for OAuth flows (handles browser form POST, sets cookies, redirects)
@router.post("/login-form")
@limiter.limit("5/minute")
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    """
    Handle form-based login for OAuth authorization flows.

    This endpoint:
    1. Authenticates the user with email/password
    2. Sets access_token cookie for subsequent requests
    3. Redirects to the 'next' URL (typically OAuth authorize)

    This works without JavaScript, avoiding CSP issues with inline scripts.
    """
    from fastapi.responses import RedirectResponse, HTMLResponse
    import html

    # Helper to return error page
    def make_error_page(error_message: str) -> HTMLResponse:
        error_html = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ font-size: 28px; color: #333; margin-bottom: 8px; }}
        .logo p {{ color: #666; font-size: 14px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 6px; color: #333; font-weight: 500; font-size: 14px; }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
        }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>Identity Platform</p>
        </div>
        <div class="error">{html.escape(error_message)}</div>
        <form method="POST" action="/api/v1/auth/login-form">
            <input type="hidden" name="next" value="{html.escape(next)}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" value="{html.escape(email)}" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    </div>
</body>
</html>
'''
        return HTMLResponse(content=error_html, status_code=401)

    # Find user by email (without status filter to check lockout first)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return make_error_page("Invalid email or password. Please try again.")

    # Check if account is locked
    is_locked, seconds_remaining = AccountLockoutService.is_account_locked(user)
    if is_locked:
        minutes_remaining = (seconds_remaining or 0) // 60 + 1
        return make_error_page(
            f"Account temporarily locked due to too many failed login attempts. "
            f"Please try again in {minutes_remaining} minute(s)."
        )

    # Check user status after lockout check
    if user.status != UserStatus.ACTIVE:
        return make_error_page("Invalid email or password. Please try again.")

    # Verify password
    if not user.password_hash or not AuthService.verify_password(password, user.password_hash):
        # Record failed attempt
        ip_address = request.client.host if request.client else None
        is_now_locked, lock_seconds = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=ip_address
        )
        if is_now_locked:
            minutes_remaining = (lock_seconds or 0) // 60 + 1
            return make_error_page(
                f"Account locked due to too many failed login attempts. "
                f"Please try again in {minutes_remaining} minute(s)."
            )
        return make_error_page("Invalid email or password. Please try again.")

    # Reset failed attempts on successful login
    await AccountLockoutService.reset_failed_attempts(db, user)

    # Create session and tokens
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Create redirect response with cookies
    response = RedirectResponse(url=next, status_code=302)
    response.set_cookie(
        key="janua_access_token",
        value=access_token,
        max_age=3600,  # 1 hour
        httponly=False,  # Allow JS access for API calls
        samesite="lax",
        secure=True,  # HTTPS only
    )
    response.set_cookie(
        key="janua_refresh_token",
        value=refresh_token,
        max_age=604800,  # 7 days
        httponly=True,  # HttpOnly for security
        samesite="lax",
        secure=True,
    )

    return response


# Alias for /signin (tests expect /login)
@router.post("/login", response_model=SignInResponse)
@limiter.limit("5/minute")
async def login(credentials: SignInRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and get tokens (alias for /signin)"""
    return await sign_in(credentials, request, db)


# Alias for /signout (tests expect /logout)
@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Sign out current session (alias for /signout)"""
    return await sign_out(current_user, credentials, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    result = await AuthService.refresh_tokens(db, request.refresh_token)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token, refresh_token = result

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/signout")
async def sign_out(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Sign out current session"""
    token = credentials.credentials
    payload = AuthService.decode_token(token, token_type="access")

    if payload:
        # Find and revoke session
        result = await db.execute(
            select(UserSession).where(UserSession.access_token_jti == payload["jti"])
        )
        session = result.scalar_one_or_none()

        if session:
            AuthService.revoke_session(db, str(session.id))

    # Log activity
    await log_activity(db, str(current_user.id), "signout", {})

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
        is_admin=getattr(current_user, 'is_admin', False),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_sign_in_at=current_user.last_sign_in_at,
    )


@router.post("/password/forgot")
@limiter.limit("3/hour")  # Strict rate limiting for password reset requests
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request password reset email"""
    result = await db.execute(
        select(User).where(User.email == forgot_data.email, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    # Don't reveal if user exists
    if user and settings.EMAIL_ENABLED:
        # Create reset token
        reset_token = secrets.token_urlsafe(32)
        reset = PasswordReset(
            user_id=user.id, token=reset_token, expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db.add(reset)
        await db.commit()

        # Send email in background
        background_tasks.add_task(EmailService.send_password_reset_email, user.email, reset_token)

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/password/reset")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password with token"""
    # Find valid reset token
    result = await db.execute(
        select(PasswordReset).where(
            PasswordReset.token == request.token,
            PasswordReset.used == False,
            PasswordReset.expires_at > datetime.utcnow(),
        )
    )
    reset = result.scalar_one_or_none()

    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Validate new password
    valid, message = AuthService.validate_password(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Update password
    user = await db.get(User, reset.user_id)
    user.password_hash = AuthService.hash_password(request.new_password)

    # Mark token as used
    reset.used = True
    reset.used_at = datetime.utcnow()

    await db.commit()

    # Log activity
    await log_activity(db, str(user.id), "password_reset", {})

    return {"message": "Password successfully reset"}


@router.post("/password/change")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
    await db.commit()

    # Log activity
    await log_activity(db, str(current_user.id), "password_change", {})

    return {"message": "Password successfully changed"}


# Alias for /email/verify (tests expect /verify-email)
@router.post("/verify-email")
async def verify_email_alias(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with token (alias for /email/verify)"""
    return await verify_email(request, db)


@router.post("/email/verify")
async def verify_email(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with token"""
    # Find valid verification token
    result = await db.execute(
        select(EmailVerification).where(
            EmailVerification.token == request.token,
            EmailVerification.verified == False,
            EmailVerification.expires_at > datetime.utcnow(),
        )
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    # Mark email as verified
    user = await db.get(User, verification.user_id)
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()

    # Mark verification as used
    verification.verified = True
    verification.verified_at = datetime.utcnow()

    await db.commit()

    # Log activity
    await log_activity(db, str(user.id), "email_verified", {})

    return {"message": "Email successfully verified"}


@router.post("/email/resend-verification")
@limiter.limit("5/hour")  # Rate limiting for email verification requests
async def resend_verification_email(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        expires_at=datetime.utcnow() + timedelta(hours=48),
    )
    db.add(verification)
    await db.commit()

    # Send email in background
    background_tasks.add_task(
        EmailService.send_verification_email, current_user.email, verification_token
    )

    return {"message": "Verification email sent"}


@router.post("/magic-link")
@limiter.limit("5/hour")  # Rate limiting for magic link requests
async def send_magic_link(
    request: Request,
    magic_link_data: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send magic link for passwordless signin"""
    if not settings.ENABLE_MAGIC_LINKS:
        raise HTTPException(status_code=403, detail="Magic links are disabled")

    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")

    # Find or create user
    result = await db.execute(
        select(User).where(User.email == magic_link_data.email, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create user without password for magic link only
        user = User(
            email=magic_link_data.email,
            email_verified=True,  # Auto-verify for magic link users
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Create magic link token
    magic_token = secrets.token_urlsafe(32)
    magic_link = MagicLink(
        user_id=user.id,
        token=magic_token,
        redirect_url=magic_link_data.redirect_url,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    db.add(magic_link)
    await db.commit()

    # Send email in background
    background_tasks.add_task(
        EmailService.send_magic_link_email, user.email, magic_token, magic_link_data.redirect_url
    )

    return {"message": "Magic link sent to email"}


@router.post("/magic-link/verify", response_model=SignInResponse)
async def verify_magic_link(
    request: VerifyMagicLinkRequest, req: Request, db: Session = Depends(get_db)
):
    """Sign in with magic link token"""
    # Find valid magic link
    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token == request.token,
            MagicLink.used == False,
            MagicLink.expires_at > datetime.utcnow(),
        )
    )
    magic_link = result.scalar_one_or_none()

    if not magic_link:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")

    # Get user
    result = await db.execute(
        select(User).where(User.id == magic_link.user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # Mark magic link as used
    magic_link.used = True
    magic_link.used_at = datetime.utcnow()

    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=req.client.host, user_agent=req.headers.get("user-agent")
    )

    # Log activity
    await log_activity(db, str(user.id), "signin", {"method": "magic_link"}, req)

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, 'is_admin', False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )
