"""
Device Management API endpoints

Allows users to manage their trusted devices and active sessions.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.device_verification_service import DeviceVerificationService

router = APIRouter(prefix="/devices", tags=["Device Management"])


# ============================================================================
# Response Models
# ============================================================================


class TrustedDeviceResponse(BaseModel):
    """Response model for trusted device."""

    id: str
    device_name: str
    device_fingerprint: str  # First 8 chars only for security
    last_ip_address: Optional[str] = None
    last_location: Optional[str] = None
    last_used_at: datetime
    trust_expires_at: Optional[datetime] = None
    created_at: datetime
    is_current_device: bool = False


class ActiveSessionResponse(BaseModel):
    """Response model for active session."""

    id: str
    device_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_trusted_device: bool = False
    last_activity: datetime
    created_at: datetime
    is_current_session: bool = False


class TrustDeviceRequest(BaseModel):
    """Request to trust a device."""

    device_name: Optional[str] = Field(None, max_length=255)
    trust_duration_days: Optional[int] = Field(30, ge=1, le=365)


class DeviceListResponse(BaseModel):
    """Response with list of devices and sessions."""

    trusted_devices: List[TrustedDeviceResponse]
    active_sessions: List[ActiveSessionResponse]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/", response_model=DeviceListResponse)
async def list_devices_and_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all trusted devices and active sessions for the current user.

    Returns both trusted devices (that skip MFA) and active sessions
    (currently logged in sessions) so users can manage their security.
    """
    # Get current device fingerprint for comparison
    user_agent = request.headers.get("user-agent")
    current_fingerprint = DeviceVerificationService.generate_device_fingerprint(user_agent)

    # Get trusted devices
    trusted_devices = await DeviceVerificationService.list_trusted_devices(db, current_user.id)
    trusted_responses = [
        TrustedDeviceResponse(
            id=str(device.id),
            device_name=device.device_name or "Unknown Device",
            device_fingerprint=device.device_fingerprint[:8] + "****",
            last_ip_address=device.last_ip_address,
            last_location=device.last_location,
            last_used_at=device.last_used_at,
            trust_expires_at=device.trust_expires_at,
            created_at=device.created_at,
            is_current_device=device.device_fingerprint == current_fingerprint,
        )
        for device in trusted_devices
    ]

    # Get active sessions
    active_sessions = await DeviceVerificationService.list_active_sessions(db, current_user.id)

    # Get current session ID from token if available
    # For now, we'll use fingerprint matching as a proxy
    session_responses = [
        ActiveSessionResponse(
            id=str(session.id),
            device_name=session.device_name or DeviceVerificationService.get_friendly_device_name(
                session.user_agent
            ),
            ip_address=session.ip_address,
            user_agent=session.user_agent[:100] if session.user_agent else None,  # Truncate
            is_trusted_device=session.is_trusted_device or False,
            last_activity=session.last_activity,
            created_at=session.created_at,
            is_current_session=session.device_fingerprint == current_fingerprint if session.device_fingerprint else False,
        )
        for session in active_sessions
    ]

    return DeviceListResponse(
        trusted_devices=trusted_responses,
        active_sessions=session_responses,
    )


@router.post("/trust", response_model=TrustedDeviceResponse)
async def trust_current_device(
    request: Request,
    trust_request: TrustDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trust the current device.

    Trusted devices may skip MFA verification for the specified duration.
    """
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    fingerprint = DeviceVerificationService.generate_device_fingerprint(user_agent)

    trusted_device = await DeviceVerificationService.trust_device(
        db=db,
        user_id=current_user.id,
        device_fingerprint=fingerprint,
        user_agent=user_agent,
        ip_address=ip_address,
        device_name=trust_request.device_name,
        trust_duration_days=trust_request.trust_duration_days,
    )

    return TrustedDeviceResponse(
        id=str(trusted_device.id),
        device_name=trusted_device.device_name or "Unknown Device",
        device_fingerprint=trusted_device.device_fingerprint[:8] + "****",
        last_ip_address=trusted_device.last_ip_address,
        last_location=trusted_device.last_location,
        last_used_at=trusted_device.last_used_at,
        trust_expires_at=trusted_device.trust_expires_at,
        created_at=trusted_device.created_at,
        is_current_device=True,
    )


@router.delete("/trusted/{device_id}")
async def revoke_trusted_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke trust for a specific device.

    The device will need to re-verify (e.g., complete MFA) on next login.
    """
    try:
        device_uuid = UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid device ID")

    success = await DeviceVerificationService.revoke_device_trust(
        db=db,
        user_id=current_user.id,
        device_id=device_uuid,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Device not found")

    return {"message": "Device trust revoked successfully"}


@router.delete("/trusted")
async def revoke_all_trusted_devices(
    request: Request,
    keep_current: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke trust for all devices.

    Optionally keeps the current device trusted.
    """
    current_fingerprint = None
    if keep_current:
        user_agent = request.headers.get("user-agent")
        current_fingerprint = DeviceVerificationService.generate_device_fingerprint(user_agent)

    revoked_count = await DeviceVerificationService.revoke_all_devices(
        db=db,
        user_id=current_user.id,
        except_device_fingerprint=current_fingerprint,
    )

    return {
        "message": f"Revoked trust for {revoked_count} device(s)",
        "revoked_count": revoked_count,
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a specific session, logging out that device.
    """
    from sqlalchemy import select
    from app.models import Session
    from app.core.jwt_manager import jwt_manager

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    # Find the session
    result = await db.execute(
        select(Session).where(
            Session.id == session_uuid,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Revoke the session
    session.is_active = False
    session.revoked_at = datetime.utcnow()
    session.revoked_reason = "user_revoked"

    # Blacklist tokens
    if session.access_token_jti:
        await jwt_manager.blacklist_token(session.access_token_jti, "access")
    if session.refresh_token_jti:
        await jwt_manager.blacklist_token(session.refresh_token_jti, "refresh")

    await db.commit()

    return {"message": "Session revoked successfully"}


@router.delete("/sessions")
async def revoke_all_sessions(
    request: Request,
    keep_current: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke all sessions, logging out all devices.

    Optionally keeps the current session active.
    """

    # Get current session fingerprint if keeping current
    current_fingerprint = None
    if keep_current:
        user_agent = request.headers.get("user-agent")
        current_fingerprint = DeviceVerificationService.generate_device_fingerprint(user_agent)

    # Use the auth service to invalidate sessions
    # We need to exclude current session somehow - for now we'll use fingerprint
    # In a production system, you'd pass the current session ID from the token

    from sqlalchemy import select, and_
    from app.models import Session
    from app.core.jwt_manager import jwt_manager

    query = select(Session).where(
        and_(
            Session.user_id == current_user.id,
            Session.is_active == True,
        )
    )

    result = await db.execute(query)
    sessions = list(result.scalars().all())

    revoked_count = 0
    for session in sessions:
        # Skip current session if requested
        if keep_current and session.device_fingerprint == current_fingerprint:
            continue

        session.is_active = False
        session.revoked_at = datetime.utcnow()
        session.revoked_reason = "user_revoked_all"

        if session.access_token_jti:
            await jwt_manager.blacklist_token(session.access_token_jti, "access")
        if session.refresh_token_jti:
            await jwt_manager.blacklist_token(session.refresh_token_jti, "refresh")

        revoked_count += 1

    await db.commit()

    return {
        "message": f"Revoked {revoked_count} session(s)",
        "revoked_count": revoked_count,
    }


@router.get("/current")
async def get_current_device_info(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get information about the current device.

    Returns device fingerprint status, trust status, and basic info.
    """
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    fingerprint = DeviceVerificationService.generate_device_fingerprint(user_agent)
    friendly_name = DeviceVerificationService.get_friendly_device_name(user_agent)

    is_trusted, trusted_device = await DeviceVerificationService.is_device_trusted(
        db, current_user.id, fingerprint
    )

    is_new = await DeviceVerificationService.is_new_device_for_user(
        db, current_user.id, fingerprint
    )

    return {
        "device_name": friendly_name,
        "device_fingerprint": fingerprint[:8] + "****",
        "ip_address": ip_address,
        "is_trusted": is_trusted,
        "is_new_device": is_new,
        "trust_expires_at": trusted_device.trust_expires_at if trusted_device else None,
    }
