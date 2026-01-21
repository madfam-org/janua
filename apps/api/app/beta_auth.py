"""
Simplified Beta Authentication System
Minimal viable authentication for beta launch while complex system is debugged
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger()

# Secure password hashing context - using bcrypt 2b to avoid passlib wrap bug detection issue
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Strong rounds for security
    bcrypt__ident="2b",  # Use 2b to avoid wrap bug detection
)

# Simple in-memory storage for beta (replace with database later)
BETA_USERS = {}
BETA_SESSIONS = {}

# Simple JWT settings
# Use environment variable for JWT secret
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "beta-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class BetaSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class BetaSignInRequest(BaseModel):
    email: EmailStr
    password: str


class BetaTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class BetaUserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    created_at: str


def hash_password(password: str) -> str:
    """Hash password using bcrypt with salt"""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash"""
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.get("/beta/status")
def beta_auth_status():
    """Beta authentication system status"""
    return {
        "status": "beta auth operational",
        "users_count": len(BETA_USERS),
        "sessions_count": len(BETA_SESSIONS),
        "message": "Simplified authentication for beta launch",
    }


@router.post("/beta/signup", response_model=BetaUserResponse)
@limiter.limit("5/minute")
def beta_signup(request: Request, signup_request: BetaSignUpRequest):
    """Beta user registration"""
    try:
        # Check if user exists
        if signup_request.email in BETA_USERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
            )

        # Simple password validation
        if len(signup_request.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters",
            )

        # Create user
        user_id = secrets.token_hex(16)
        user_data = {
            "id": user_id,
            "email": signup_request.email,
            "name": signup_request.name,
            "password_hash": hash_password(signup_request.password),
            "created_at": datetime.utcnow().isoformat(),
            "email_verified": True,  # Auto-verify for beta
        }

        BETA_USERS[signup_request.email] = user_data

        logger.info(f"Beta user created: {signup_request.email}")

        return BetaUserResponse(
            id=user_id,
            email=signup_request.email,
            name=signup_request.name,
            created_at=user_data["created_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Beta signup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signup failed"
        )


@router.post("/beta/signin", response_model=BetaTokenResponse)
@limiter.limit("10/minute")
def beta_signin(request: Request, signin_request: BetaSignInRequest):
    """Beta user authentication"""
    try:
        # Find user
        user_data = BETA_USERS.get(signin_request.email)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        # Verify password
        if not verify_password(signin_request.password, user_data["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        # Create access token
        token_data = {
            "sub": user_data["id"],
            "email": signin_request.email,
            "name": user_data["name"],
        }
        access_token = create_access_token(token_data)

        # Store session
        session_id = secrets.token_hex(16)
        BETA_SESSIONS[session_id] = {
            "user_id": user_data["id"],
            "email": signin_request.email,
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Beta user signed in: {signin_request.email}")

        return BetaTokenResponse(access_token=access_token, expires_in=3600)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Beta signin failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signin failed"
        )


@router.get("/beta/users")
def beta_list_users():
    """List beta users (admin endpoint)"""
    return {
        "users": [
            {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "created_at": user["created_at"],
            }
            for user in BETA_USERS.values()
        ],
        "total": len(BETA_USERS),
        "total": len(BETA_USERS)
    }
