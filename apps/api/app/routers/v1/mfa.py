"""
Multi-Factor Authentication (MFA/TOTP) endpoints
"""

import base64
import io
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import jwt as pyjwt
import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers.v1.auth import get_current_user, SignInResponse, UserResponse, TokenResponse
from app.services.account_lockout_service import AccountLockoutService
from app.services.auth_service import AuthService

from ...models import ActivityLog, User, UserStatus
from ...services.user_lookup import get_user_by_email

router = APIRouter(prefix="/mfa", tags=["mfa"])


class MFAChallengeVerifyRequest(BaseModel):
    """MFA challenge verification request (during sign-in)"""

    mfa_token: str
    # TOTP is 6 digits; a formatted backup code is XXXX-XXXX (9 chars). max_length
    # was 8, which rejected every formatted backup code at validation before it
    # reached consume_backup_code — so backup codes could never complete a sign-in
    # challenge. Allow up to 9 (the normalizer strips the dash on compare).
    code: str = Field(..., min_length=6, max_length=9)


class MFAEnableRequest(BaseModel):
    """MFA enable request"""

    password: str  # Require password for security


class MFAEnableResponse(BaseModel):
    """MFA enable response"""

    secret: str
    qr_code: str  # Base64 encoded QR code image
    backup_codes: List[str]
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    """MFA verification request"""

    code: str = Field(..., min_length=6, max_length=6)


class MFADisableRequest(BaseModel):
    """MFA disable request"""

    password: str  # Require password for security
    code: Optional[str] = Field(
        None, min_length=6, max_length=6
    )  # Current TOTP code or backup code


class MFAStatusResponse(BaseModel):
    """MFA status response"""

    enabled: bool
    verified: bool
    backup_codes_remaining: int
    last_used_at: Optional[datetime]


class MFARecoveryRequest(BaseModel):
    """MFA recovery request"""

    email: str
    backup_code: str


class MFABackupCodesResponse(BaseModel):
    """MFA backup codes response"""

    backup_codes: List[str]
    generated_at: datetime


def generate_backup_codes(count: int = 10) -> List[str]:
    """Generate backup codes"""
    codes = []
    for _ in range(count):
        # Generate 8-character alphanumeric codes
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        # Format as XXXX-XXXX for readability
        formatted_code = f"{code[:4]}-{code[4:]}"
        codes.append(formatted_code)
    return codes


# ── Backup-code hashing (2026-08-23 security fix) ──────────────────────────────
# Backup codes were stored PLAINTEXT in mfa_backup_codes (a P0). They are secrets
# equivalent to a second factor, so they are now hashed at rest with the same
# bcrypt primitive the platform uses for passwords, and compared in constant time.
# A dedicated context here keeps this independent of the legacy beta_auth module.
_backup_code_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _normalize_backup_code(code: str) -> str:
    """Canonical form for hashing/compare: strip dashes, uppercase, trim."""
    return code.replace("-", "").strip().upper()


def hash_backup_code(code: str) -> str:
    """Hash a backup code for at-rest storage (bcrypt over the normalized form)."""
    return _backup_code_context.hash(_normalize_backup_code(code))


def _entry_matches_code(entry: dict, code: str) -> bool:
    """Constant-time-ish match of a submitted code against ONE stored entry.

    Backward compatible: new entries carry {"hash": ...}; legacy rows may still
    carry {"code": <plaintext>} (or a bare string). Both are accepted so existing
    users are not locked out; the legacy plaintext path is removed as codes are
    regenerated. Does NOT consult the `used` flag — callers do (see
    consume_backup_code) so the "used" policy is enforced in exactly one place.
    """
    normalized = _normalize_backup_code(code)
    if isinstance(entry, dict):
        stored_hash = entry.get("hash")
        if stored_hash:
            try:
                return _backup_code_context.verify(normalized, stored_hash)
            except Exception:
                return False
        # Legacy plaintext entry (pre-2026-08-23) — compare normalized forms.
        legacy = entry.get("code")
        if legacy is not None:
            return secrets.compare_digest(_normalize_backup_code(legacy), normalized)
        return False
    # Bare-string legacy entry.
    return secrets.compare_digest(_normalize_backup_code(str(entry)), normalized)


def consume_backup_code(user: "User", code: str) -> bool:
    """Verify a backup code against the user's UNUSED codes and consume it.

    Returns True and marks the matching entry used (mutating user.mfa_backup_codes
    in place) if a valid, not-yet-used code is found; False otherwise. This is the
    ONE place backup codes are validated for login/verify, so the single-use and
    hashing rules cannot drift between call sites (the prior code re-implemented
    this 4× and one site — disable_mfa — ignored the `used` flag entirely).
    """
    entries = user.mfa_backup_codes
    if not entries or not isinstance(entries, list):
        return False
    for i, entry in enumerate(entries):
        is_used = entry.get("used", False) if isinstance(entry, dict) else False
        if is_used:
            continue
        if _entry_matches_code(entry, code):
            # Normalize the entry to the current dict shape and mark consumed.
            user.mfa_backup_codes[i] = {
                **(entry if isinstance(entry, dict) else {}),
                "used": True,
                "used_at": datetime.utcnow().isoformat(),
            }
            # Drop any lingering plaintext from a legacy entry now that it's spent.
            user.mfa_backup_codes[i].pop("code", None)
            return True
    return False


def generate_qr_code(provisioning_uri: str) -> str:
    """Generate QR code as base64 encoded image"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get MFA status for current user"""
    backup_codes_remaining = 0
    if current_user.mfa_backup_codes:
        # Count unused backup codes (those without 'used' flag)
        backup_codes_remaining = (
            sum(
                1
                for code in current_user.mfa_backup_codes
                if isinstance(code, dict) and not code.get("used", False)
            )
            if isinstance(current_user.mfa_backup_codes, list)
            else len(current_user.mfa_backup_codes)
        )

    # Get last MFA usage from activity logs
    result = await db.execute(
        select(ActivityLog)
        .where(
            ActivityLog.user_id == current_user.id,
            ActivityLog.action.in_(["mfa_verify", "mfa_backup_code_used"]),
        )
        .order_by(ActivityLog.created_at.desc())
    )
    last_mfa_activity = result.scalars().first()

    return MFAStatusResponse(
        enabled=current_user.mfa_enabled,
        verified=current_user.mfa_enabled and current_user.mfa_secret is not None,
        backup_codes_remaining=backup_codes_remaining,
        last_used_at=last_mfa_activity.created_at if last_mfa_activity else None,
    )


@router.post("/enable", response_model=MFAEnableResponse)
async def enable_mfa(
    request: MFAEnableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable MFA for current user"""
    # Verify password
    if not AuthService.verify_password(request.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")

    # Check if MFA is already enabled
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    # Generate TOTP secret
    secret = pyotp.random_base32()

    # Generate backup codes
    backup_codes = generate_backup_codes()

    # Store backup codes HASHED (2026-08-23 security fix) — the plaintext is
    # returned to the user ONCE in the response below and never persisted.
    backup_codes_data = [
        {"hash": hash_backup_code(code), "used": False, "created_at": datetime.utcnow().isoformat()}
        for code in backup_codes
    ]

    # Create provisioning URI for QR code
    issuer_name = settings.APP_NAME or "Janua"
    account_name = current_user.email
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_name, issuer_name=issuer_name
    )

    # Generate QR code
    qr_code = generate_qr_code(provisioning_uri)

    # Store secret and backup codes (but don't enable yet - need verification)
    current_user.mfa_secret = secret
    current_user.mfa_backup_codes = backup_codes_data

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id, action="mfa_setup_initiated", activity_metadata={"method": "totp"}
    )
    db.add(activity)

    await db.commit()

    return MFAEnableResponse(
        secret=secret, qr_code=qr_code, backup_codes=backup_codes, provisioning_uri=provisioning_uri
    )


@router.post("/verify")
async def verify_mfa(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify MFA setup with TOTP code"""
    # Check if MFA secret exists
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA setup not initiated")

    # Verify TOTP code
    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Enable MFA
    current_user.mfa_enabled = True

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id, action="mfa_enabled", activity_metadata={"method": "totp"}
    )
    db.add(activity)

    await db.commit()

    return {"message": "MFA successfully enabled"}


@router.post("/disable")
async def disable_mfa(
    request: MFADisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable MFA for current user"""
    # Check if MFA is enabled
    if not current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is not enabled")

    # Verify password
    if not AuthService.verify_password(request.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")

    # Verify TOTP code or backup code if provided
    if request.code:
        # Try TOTP first
        totp = pyotp.TOTP(current_user.mfa_secret)
        totp_valid = totp.verify(request.code, valid_window=1)

        if not totp_valid:
            # Try backup code — hashed compare + single-use enforced via the one
            # shared helper (the prior inline check here ignored the `used` flag,
            # so a spent backup code could still disable MFA — 2026-08-23 fix).
            if not consume_backup_code(current_user, request.code):
                raise HTTPException(status_code=400, detail="Invalid verification code")

    # Disable MFA
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_backup_codes = []

    # Log activity
    activity = ActivityLog(user_id=current_user.id, action="mfa_disabled", activity_metadata={})
    db.add(activity)

    await db.commit()

    return {"message": "MFA successfully disabled"}


@router.post("/regenerate-backup-codes", response_model=MFABackupCodesResponse)
async def regenerate_backup_codes(
    password: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Regenerate backup codes"""
    # Check if MFA is enabled
    if not current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is not enabled")

    # Verify password
    if not AuthService.verify_password(password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")

    # Generate new backup codes
    backup_codes = generate_backup_codes()

    # Store HASHED (2026-08-23 security fix); plaintext returned once below.
    backup_codes_data = [
        {"hash": hash_backup_code(code), "used": False, "created_at": datetime.utcnow().isoformat()}
        for code in backup_codes
    ]

    current_user.mfa_backup_codes = backup_codes_data

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="mfa_backup_codes_regenerated",
        activity_metadata={"count": len(backup_codes)},
    )
    db.add(activity)

    await db.commit()

    return MFABackupCodesResponse(backup_codes=backup_codes, generated_at=datetime.utcnow())


@router.post("/validate-code")
async def validate_mfa_code(
    code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Validate an MFA code (for testing/verification)"""
    # Check if MFA is enabled
    if not current_user.mfa_enabled or not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not enabled")

    # Verify TOTP code
    totp = pyotp.TOTP(current_user.mfa_secret)
    if totp.verify(code, valid_window=1):
        # Log successful validation
        activity = ActivityLog(
            user_id=current_user.id, action="mfa_verify", activity_metadata={"method": "totp"}
        )
        db.add(activity)
        await db.commit()

        return {"valid": True, "message": "Code is valid"}

    # Try backup code — hashed compare + single-use via the one shared helper.
    if consume_backup_code(current_user, code):
        activity = ActivityLog(
            user_id=current_user.id,
            action="mfa_backup_code_used",
            activity_metadata={"context": "validate-code"},
        )
        db.add(activity)
        await db.commit()
        return {"valid": True, "message": "Backup code is valid (now consumed)"}

    return {"valid": False, "message": "Invalid code"}


@router.get("/recovery-options")
async def get_recovery_options(email: str, db: Session = Depends(get_db)):
    """Get MFA recovery options for a user (public endpoint)"""
    # Find user by email — untenanted / staff pool (platform MFA recovery; email
    # is per-tenant since migration 013, so scope to keep this single-row).
    user = await get_user_by_email(db, email, tenant_id=None, active_only=True)

    if not user:
        # Don't reveal if user exists
        return {"recovery_available": False}

    if not user.mfa_enabled:
        return {"recovery_available": False}

    # Check if user has backup codes
    has_backup_codes = False
    if user.mfa_backup_codes:
        # Count unused backup codes
        unused_codes = (
            sum(
                1
                for code in user.mfa_backup_codes
                if isinstance(code, dict) and not code.get("used", False)
            )
            if isinstance(user.mfa_backup_codes, list)
            else len(user.mfa_backup_codes)
        )
        has_backup_codes = unused_codes > 0

    return {
        "recovery_available": True,
        "methods": {
            "backup_codes": has_backup_codes,
            "email_recovery": True,  # Always available as fallback
        },
    }


@router.post("/initiate-recovery")
async def initiate_mfa_recovery(email: str, db: Session = Depends(get_db)):
    """Initiate MFA recovery process"""
    # Find user by email — untenanted / staff pool (see get_recovery_options).
    user = await get_user_by_email(db, email, tenant_id=None, active_only=True)

    if not user or not user.mfa_enabled:
        # Don't reveal if user exists or has MFA
        return {"message": "If MFA is enabled, recovery instructions have been sent"}

    # Generate recovery token (stored for future recovery link feature)
    from app.core.jwt_manager import create_access_token

    # Recovery token created for potential future use in recovery link feature
    create_access_token(
        data={"sub": str(user.id), "purpose": "mfa_recovery"},
        expires_delta=timedelta(hours=1),  # Short-lived recovery token
    )

    # Send recovery email with backup codes
    from app.core.redis import get_redis
    from app.services.resend_email_service import get_resend_email_service

    redis_client = await get_redis()
    email_service = get_resend_email_service(redis_client)

    # Extract plain backup codes from stored data
    backup_codes = (
        [
            code_data["code"]
            for code_data in user.mfa_backup_codes
            if not code_data.get("used", False)
        ]
        if isinstance(user.mfa_backup_codes, list)
        else []
    )

    await email_service.send_mfa_recovery_email(
        to_email=user.email, user_name=user.full_name or user.email, backup_codes=backup_codes
    )

    # Log recovery attempt
    activity = ActivityLog(
        user_id=user.id, action="mfa_recovery_initiated", activity_metadata={"method": "email"}
    )
    db.add(activity)
    await db.commit()

    return {"message": "If MFA is enabled, recovery instructions have been sent"}


@router.get("/supported-methods")
async def get_supported_mfa_methods():
    """Get list of supported MFA methods"""
    return {
        "methods": [
            {
                "type": "totp",
                "name": "Authenticator App",
                "description": "Use an authenticator app like Google Authenticator or Authy",
                "enabled": True,
            },
            {
                "type": "sms",
                "name": "SMS",
                "description": "Receive codes via text message",
                "enabled": False,  # Not implemented yet
                "coming_soon": True,
            },
            {
                "type": "email",
                "name": "Email",
                "description": "Receive codes via email",
                "enabled": False,  # Not implemented yet
                "coming_soon": True,
            },
            {
                "type": "webauthn",
                "name": "Security Key",
                "description": "Use a hardware security key",
                "enabled": False,  # Implemented separately in passkeys
                "coming_soon": True,
            },
        ]
    }


@router.post("/challenge/verify", response_model=SignInResponse)
async def verify_mfa_challenge(
    request_data: MFAChallengeVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Verify MFA code during sign-in and issue session tokens.

    SECURITY: This endpoint completes the second factor of authentication.
    The mfa_token is a short-lived (5min) challenge token issued after
    successful password verification. It cannot be used as an access token.
    """
    # Decode and validate the MFA challenge token
    try:
        payload = pyjwt.decode(
            request_data.mfa_token,
            settings.JWT_SECRET_KEY or "development-secret-key",
            algorithms=["HS256"],
            options={"require": ["sub", "type", "exp"]},
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="MFA challenge expired. Please sign in again.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid MFA challenge token")

    # Verify this is an MFA challenge token, not a session token
    if payload.get("type") != "mfa_challenge":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Get the user
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == UUID(user_id), User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=401, detail="Invalid MFA challenge")

    # Wrong codes count against the same per-account lockout as passwords, so a
    # challenge token cannot be used for unbounded guessing.
    is_locked, _ = AccountLockoutService.is_account_locked(user)
    if is_locked:
        raise HTTPException(status_code=401, detail="Too many failed attempts. Sign in again later.")

    # Verify TOTP code
    totp = pyotp.TOTP(user.mfa_secret)
    code_valid = totp.verify(request_data.code, valid_window=1)

    # If TOTP failed, try backup codes — hashed compare + single-use via the one
    # shared helper (2026-08-23 fix; was an inline plaintext loop).
    if not code_valid and consume_backup_code(user, request_data.code):
        activity = ActivityLog(
            user_id=user.id,
            action="mfa_backup_code_used",
            activity_metadata={"context": "signin"},
        )
        db.add(activity)
        code_valid = True

    if not code_valid:
        is_now_locked, _ = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=request.client.host if request.client else None
        )
        if is_now_locked:
            raise HTTPException(
                status_code=401, detail="Too many failed attempts. Sign in again later."
            )
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    await AccountLockoutService.reset_failed_attempts(db, user)

    # MFA verified — issue real session tokens
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Log successful MFA sign-in
    activity = ActivityLog(
        user_id=user.id,
        action="mfa_verify",
        activity_metadata={"method": "totp", "context": "signin"},
    )
    db.add(activity)
    await db.commit()

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, "is_admin", False),
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
