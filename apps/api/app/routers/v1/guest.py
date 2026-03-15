"""Guest access token endpoint.

Issues short-lived JWT tokens with the ``guest`` role for unauthenticated
users.  Tokens can be obtained either with an invite link token or by
specifying an ``org_id`` directly (rate-limited more aggressively).
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database_manager import get_db
from app.models import GuestInvite, Organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/guest", tags=["guest-access"])


# -- Request / Response schemas -----------------------------------------------


class GuestTokenRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=50)
    org_id: Optional[str] = None
    invite_token: Optional[str] = None
    ttl_hours: Optional[int] = Field(default=None, ge=1, le=24)


class GuestTokenResponse(BaseModel):
    access_token: str
    expires_at: str
    guest_id: str
    display_name: str
    org_id: str


class InviteValidationResponse(BaseModel):
    valid: bool
    org_name: Optional[str] = None
    room_id: Optional[str] = None
    expires_at: Optional[str] = None


# -- Helpers ------------------------------------------------------------------


def _mint_guest_jwt(
    guest_id: str,
    display_name: str,
    org_id: str,
    ttl_hours: int,
) -> tuple[str, datetime]:
    """Create a signed JWT for a guest user.

    Uses the same JWT infrastructure as regular tokens but with the
    ``guest`` role and ``type=guest_access`` claim.
    """
    from app.core.jwt_manager import jwt_manager

    expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

    token = jwt_manager.create_token(
        data={
            "sub": guest_id,
            "roles": ["guest"],
            "name": display_name,
            "org_id": org_id,
            "type": "guest_access",
        },
        expires_delta=timedelta(hours=ttl_hours),
    )
    return token, expires_at


# -- Endpoints ----------------------------------------------------------------


@router.post("", response_model=GuestTokenResponse)
async def create_guest_token(
    body: GuestTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GuestTokenResponse:
    """Issue a guest access token.

    Two modes:
    1. **Invite token** — validate a ``GuestInvite``, extract org, increment use count.
    2. **Direct org_id** — validate the org exists (rate-limited more aggressively).
    """
    if not settings.ENABLE_GUEST_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest access is disabled",
        )

    display_name = (body.display_name or "Guest").strip()[:50] or "Guest"
    ttl_hours = min(body.ttl_hours or settings.GUEST_DEFAULT_TTL_HOURS, settings.GUEST_MAX_TTL_HOURS)
    org_id: str | None = None

    if body.invite_token:
        # -- Mode 1: Validate invite token ------------------------------------
        result = await db.execute(
            select(GuestInvite).where(GuestInvite.token == body.invite_token)
        )
        invite = result.scalar_one_or_none()

        if invite is None or invite.revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or revoked invite",
            )
        if invite.expires_at and invite.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invite has expired",
            )
        if invite.max_uses > 0 and invite.use_count >= invite.max_uses:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invite has reached maximum uses",
            )

        invite.use_count += 1
        await db.flush()

        org_id = str(invite.organization_id)
        if invite.guest_ttl_hours:
            ttl_hours = min(ttl_hours, invite.guest_ttl_hours)

    elif body.org_id:
        # -- Mode 2: Direct org_id -------------------------------------------
        try:
            org_uuid = uuid.UUID(body.org_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid org_id",
            ) from exc

        org_result = await db.execute(
            select(Organization).where(Organization.id == org_uuid)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        org_id = str(org.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either invite_token or org_id is required",
        )

    guest_id = f"guest-{uuid.uuid4()}"
    access_token, expires_at = _mint_guest_jwt(guest_id, display_name, org_id, ttl_hours)

    logger.info(
        "Guest token issued: guest_id=%s org_id=%s ttl=%dh",
        guest_id,
        org_id,
        ttl_hours,
    )

    return GuestTokenResponse(
        access_token=access_token,
        expires_at=expires_at.isoformat(),
        guest_id=guest_id,
        display_name=display_name,
        org_id=org_id,
    )


@router.get("/validate/{token}", response_model=InviteValidationResponse)
async def validate_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InviteValidationResponse:
    """Public endpoint to validate a guest invite token.

    Returns organization name and room info without issuing a token.
    """
    result = await db.execute(
        select(GuestInvite).where(GuestInvite.token == token)
    )
    invite = result.scalar_one_or_none()

    if invite is None or invite.revoked:
        return InviteValidationResponse(valid=False)

    if invite.expires_at and invite.expires_at < datetime.now(UTC):
        return InviteValidationResponse(valid=False)

    if invite.max_uses > 0 and invite.use_count >= invite.max_uses:
        return InviteValidationResponse(valid=False)

    # Fetch org name
    org_result = await db.execute(
        select(Organization).where(Organization.id == invite.organization_id)
    )
    org = org_result.scalar_one_or_none()

    return InviteValidationResponse(
        valid=True,
        org_name=org.name if org else "Unknown",
        room_id=invite.room_id,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
    )
