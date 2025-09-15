"""
Passkeys/WebAuthn authentication endpoints
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json
import base64
import secrets
import hashlib
import uuid
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json
)
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url
)

from app.database import get_db
from app.models import User, Passkey, Session as UserSession, ActivityLog
from app.routers.v1.auth import get_current_user
from app.services.auth import AuthService
from app.config import settings

router = APIRouter(prefix="/passkeys", tags=["passkeys"])


class PasskeyRegisterOptionsRequest(BaseModel):
    """Passkey registration options request"""
    authenticator_attachment: Optional[str] = Field(None, pattern="^(platform|cross-platform)$")


class PasskeyRegisterRequest(BaseModel):
    """Passkey registration verification request"""
    credential: Dict[str, Any]
    name: Optional[str] = Field(None, max_length=100)


class PasskeyAuthOptionsRequest(BaseModel):
    """Passkey authentication options request"""
    email: Optional[str] = None  # For passwordless login


class PasskeyAuthRequest(BaseModel):
    """Passkey authentication verification request"""
    email: Optional[str] = None  # For passwordless login
    credential: Dict[str, Any]


class PasskeyResponse(BaseModel):
    """Passkey response model"""
    id: str
    name: Optional[str]
    authenticator_attachment: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]
    sign_count: int


class PasskeyUpdateRequest(BaseModel):
    """Passkey update request"""
    name: str = Field(..., min_length=1, max_length=100)


def get_rp_id() -> str:
    """Get Relying Party ID (domain)"""
    # In production, this should be your domain
    return settings.DOMAIN or "localhost"


def get_rp_name() -> str:
    """Get Relying Party Name"""
    return settings.APP_NAME or "Plinto"


def get_origin() -> str:
    """Get expected origin"""
    if settings.FRONTEND_URL:
        return settings.FRONTEND_URL
    return f"https://{get_rp_id()}" if settings.ENVIRONMENT == "production" else f"http://{get_rp_id()}:3000"


@router.post("/register/options")
async def get_registration_options(
    request: PasskeyRegisterOptionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get WebAuthn registration options"""
    # Get existing passkeys to exclude
    existing_passkeys = db.query(Passkey).filter(
        Passkey.user_id == current_user.id
    ).all()
    
    exclude_credentials = []
    for passkey in existing_passkeys:
        exclude_credentials.append({
            "id": base64.b64decode(passkey.credential_id),
            "type": "public-key"
        })
    
    # Generate registration options
    options = generate_registration_options(
        rp_id=get_rp_id(),
        rp_name=get_rp_name(),
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.display_name or current_user.email,
        exclude_credentials=exclude_credentials,
        authenticator_selection={
            "authenticator_attachment": request.authenticator_attachment if request.authenticator_attachment else "cross-platform",
            "require_resident_key": False,
            "user_verification": "preferred"
        },
        timeout=60000  # 60 seconds
    )
    
    # Store challenge in session/cache for verification
    # TODO: Store in Redis with expiry
    challenge = bytes_to_base64url(options.challenge)
    
    # For now, store in user metadata (temporary solution)
    if not current_user.user_metadata:
        current_user.user_metadata = {}
    current_user.user_metadata["webauthn_challenge"] = challenge
    db.commit()
    
    # Convert to JSON-serializable format
    return {
        "challenge": challenge,
        "rp": {
            "id": options.rp.id,
            "name": options.rp.name
        },
        "user": {
            "id": bytes_to_base64url(options.user.id),
            "name": options.user.name,
            "displayName": options.user.display_name
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257}  # RS256
        ],
        "timeout": options.timeout,
        "excludeCredentials": [
            {
                "id": bytes_to_base64url(cred["id"]),
                "type": cred["type"]
            }
            for cred in exclude_credentials
        ],
        "authenticatorSelection": options.authenticator_selection,
        "attestation": "none"
    }


@router.post("/register/verify")
async def verify_registration(
    request: PasskeyRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify WebAuthn registration"""
    # Get stored challenge
    if not current_user.user_metadata or "webauthn_challenge" not in current_user.user_metadata:
        raise HTTPException(status_code=400, detail="No registration in progress")
    
    expected_challenge = base64url_to_bytes(current_user.user_metadata["webauthn_challenge"])
    
    # Verify registration
    try:
        verification = verify_registration_response(
            credential=request.credential,
            expected_challenge=expected_challenge,
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration verification failed: {str(e)}")
    
    if not verification.verified:
        raise HTTPException(status_code=400, detail="Registration verification failed")
    
    # Store passkey
    credential_id = bytes_to_base64url(verification.credential_id)
    public_key = bytes_to_base64url(verification.credential_public_key)
    
    # Check if credential already exists
    existing = db.query(Passkey).filter(
        Passkey.credential_id == credential_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="This passkey is already registered")
    
    # Create passkey
    passkey = Passkey(
        user_id=current_user.id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=verification.sign_count,
        name=request.name or f"Passkey {datetime.utcnow().strftime('%Y-%m-%d')}",
        authenticator_attachment=request.credential.get("authenticatorAttachment")
    )
    
    db.add(passkey)
    
    # Clear challenge
    del current_user.user_metadata["webauthn_challenge"]
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="passkey_registered",
        details={
            "passkey_id": str(passkey.id),
            "name": passkey.name
        }
    )
    db.add(activity)
    
    db.commit()
    
    return {
        "verified": True,
        "passkey_id": str(passkey.id),
        "message": "Passkey successfully registered"
    }


@router.post("/authenticate/options")
async def get_authentication_options(
    request: PasskeyAuthOptionsRequest,
    db: Session = Depends(get_db)
):
    """Get WebAuthn authentication options"""
    allow_credentials = []
    
    if request.email:
        # Passwordless login - get user's passkeys
        user = db.query(User).filter(User.email == request.email).first()
        if user:
            passkeys = db.query(Passkey).filter(Passkey.user_id == user.id).all()
            for passkey in passkeys:
                allow_credentials.append({
                    "id": base64.b64decode(passkey.credential_id),
                    "type": "public-key"
                })
    
    # Generate authentication options
    options = generate_authentication_options(
        rp_id=get_rp_id(),
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification="preferred",
        timeout=60000
    )
    
    # Store challenge
    challenge = bytes_to_base64url(options.challenge)
    
    # TODO: Store in Redis with session ID
    # For now, we'll include it in the response and expect it back
    
    return {
        "challenge": challenge,
        "rpId": options.rp_id,
        "timeout": options.timeout,
        "allowCredentials": [
            {
                "id": bytes_to_base64url(cred["id"]),
                "type": cred["type"]
            }
            for cred in allow_credentials
        ] if allow_credentials else [],
        "userVerification": options.user_verification
    }


@router.post("/authenticate/verify")
async def verify_authentication(
    request: PasskeyAuthRequest,
    challenge: str,  # In production, get from session/Redis
    db: Session = Depends(get_db)
):
    """Verify WebAuthn authentication"""
    # Get credential ID from response
    credential_id = request.credential.get("id")
    if not credential_id:
        raise HTTPException(status_code=400, detail="Missing credential ID")
    
    # Find passkey
    passkey = db.query(Passkey).filter(
        Passkey.credential_id == credential_id
    ).first()
    
    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")
    
    # Get user
    user = db.query(User).filter(User.id == passkey.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify authentication
    try:
        verification = verify_authentication_response(
            credential=request.credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication verification failed: {str(e)}")
    
    if not verification.verified:
        raise HTTPException(status_code=400, detail="Authentication verification failed")
    
    # Update sign count
    passkey.sign_count = verification.new_sign_count
    passkey.last_used_at = datetime.utcnow()
    
    # Create session and tokens
    session_id = str(secrets.token_urlsafe(32))
    access_token_jti = str(secrets.token_urlsafe(32))
    refresh_token_jti = str(secrets.token_urlsafe(32))
    
    tokens = AuthService.create_tokens(user, access_token_jti, refresh_token_jti)
    
    # Create session record
    user_session = UserSession(
        user_id=user.id,
        access_token_jti=access_token_jti,
        refresh_token_jti=refresh_token_jti,
        ip_address=None,  # TODO: Get from request
        user_agent="Passkey Authentication",
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(user_session)
    
    # Update user last sign in
    user.last_sign_in_at = datetime.utcnow()
    
    # Log activity
    activity = ActivityLog(
        user_id=user.id,
        action="passkey_authentication",
        details={
            "passkey_id": str(passkey.id),
            "session_id": str(user_session.id)
        }
    )
    db.add(activity)
    
    db.commit()
    
    return {
        "verified": True,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }


@router.get("/", response_model=List[PasskeyResponse])
async def list_passkeys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's passkeys"""
    passkeys = db.query(Passkey).filter(
        Passkey.user_id == current_user.id
    ).order_by(Passkey.created_at.desc()).all()
    
    return [
        PasskeyResponse(
            id=str(passkey.id),
            name=passkey.name,
            authenticator_attachment=passkey.authenticator_attachment,
            created_at=passkey.created_at,
            last_used_at=passkey.last_used_at,
            sign_count=passkey.sign_count
        )
        for passkey in passkeys
    ]


@router.patch("/{passkey_id}", response_model=PasskeyResponse)
async def update_passkey(
    passkey_id: str,
    request: PasskeyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update passkey name"""
    try:
        passkey_uuid = uuid.UUID(passkey_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid passkey ID")
    
    passkey = db.query(Passkey).filter(
        Passkey.id == passkey_uuid,
        Passkey.user_id == current_user.id
    ).first()
    
    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")
    
    passkey.name = request.name
    db.commit()
    db.refresh(passkey)
    
    return PasskeyResponse(
        id=str(passkey.id),
        name=passkey.name,
        authenticator_attachment=passkey.authenticator_attachment,
        created_at=passkey.created_at,
        last_used_at=passkey.last_used_at,
        sign_count=passkey.sign_count
    )


@router.delete("/{passkey_id}")
async def delete_passkey(
    passkey_id: str,
    password: str,  # Require password for security
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a passkey"""
    # Verify password
    if not AuthService.verify_password(password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")
    
    try:
        passkey_uuid = uuid.UUID(passkey_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid passkey ID")
    
    passkey = db.query(Passkey).filter(
        Passkey.id == passkey_uuid,
        Passkey.user_id == current_user.id
    ).first()
    
    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="passkey_deleted",
        details={
            "passkey_name": passkey.name
        }
    )
    db.add(activity)
    
    db.delete(passkey)
    db.commit()
    
    return {"message": "Passkey deleted successfully"}


@router.get("/availability")
async def check_webauthn_availability():
    """Check if WebAuthn is available/supported"""
    return {
        "available": True,
        "platform_authenticator": True,  # Platform authenticator (Touch ID, Face ID, Windows Hello)
        "roaming_authenticator": True,   # USB security keys
        "conditional_mediation": True,   # Autofill UI for passkeys
        "user_verifying_platform_authenticator": True
    }