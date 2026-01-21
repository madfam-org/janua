"""
Multi-Factor Authentication (MFA/TOTP) endpoints
"""

import base64
import io
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers.v1.auth import get_current_user
from app.services.auth_service import AuthService

from ...models import ActivityLog, User, UserStatus

router = APIRouter(prefix="/mfa", tags=["mfa"])


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

    # Store backup codes with metadata
    backup_codes_data = [
        {"code": code, "used": False, "created_at": datetime.utcnow().isoformat()}
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
        user_id=current_user.id, action="mfa_setup_initiated", details={"method": "totp"}
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
        user_id=current_user.id, action="mfa_enabled", details={"method": "totp"}
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
            # Try backup code
            backup_valid = False
            if current_user.mfa_backup_codes:
                for i, backup_data in enumerate(current_user.mfa_backup_codes):
                    if isinstance(backup_data, dict):
                        stored_code = backup_data.get("code", "")
                    else:
                        stored_code = backup_data

                    # Remove dashes for comparison
                    if stored_code.replace("-", "") == request.code.replace("-", ""):
                        backup_valid = True
                        break

            if not backup_valid:
                raise HTTPException(status_code=400, detail="Invalid verification code")

    # Disable MFA
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_backup_codes = []

    # Log activity
    activity = ActivityLog(user_id=current_user.id, action="mfa_disabled", details={})
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

    # Store backup codes with metadata
    backup_codes_data = [
        {"code": code, "used": False, "created_at": datetime.utcnow().isoformat()}
        for code in backup_codes
    ]

    current_user.mfa_backup_codes = backup_codes_data

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="mfa_backup_codes_regenerated",
        details={"count": len(backup_codes)},
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
            user_id=current_user.id, action="mfa_verify", details={"method": "totp"}
        )
        db.add(activity)
        await db.commit()

        return {"valid": True, "message": "Code is valid"}

    # Try backup code
    if current_user.mfa_backup_codes:
        for i, backup_data in enumerate(current_user.mfa_backup_codes):
            if isinstance(backup_data, dict):
                stored_code = backup_data.get("code", "")
                is_used = backup_data.get("used", False)
            else:
                stored_code = backup_data
                is_used = False

            # Remove dashes for comparison
            if not is_used and stored_code.replace("-", "") == code.replace("-", ""):
                # Mark backup code as used
                if isinstance(backup_data, dict):
                    current_user.mfa_backup_codes[i]["used"] = True
                    current_user.mfa_backup_codes[i]["used_at"] = datetime.utcnow().isoformat()
                else:
                    # Convert to dict format
                    current_user.mfa_backup_codes[i] = {
                        "code": stored_code,
                        "used": True,
                        "used_at": datetime.utcnow().isoformat(),
                    }

                # Log backup code usage
                activity = ActivityLog(
                    user_id=current_user.id,
                    action="mfa_backup_code_used",
                    details={"code_index": i},
                )
                db.add(activity)
                await db.commit()

                return {"valid": True, "message": "Backup code is valid (now consumed)"}

    return {"valid": False, "message": "Invalid code"}


@router.get("/recovery-options")
async def get_recovery_options(email: str, db: Session = Depends(get_db)):
    """Get MFA recovery options for a user (public endpoint)"""
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == email, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

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
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == email, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user or not user.mfa_enabled:
        # Don't reveal if user exists or has MFA
        return {"message": "If MFA is enabled, recovery instructions have been sent"}

    # Generate recovery token (stored for future recovery link feature)
    from app.core.jwt_manager import create_access_token

    _recovery_token = create_access_token(
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
        user_id=user.id, action="mfa_recovery_initiated", details={"method": "email"}
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
