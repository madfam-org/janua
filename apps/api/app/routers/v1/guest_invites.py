"""Admin CRUD for guest invite link management.

Follows the same patterns as ``invitations.py`` for consistency.
All endpoints require admin role via ``require_admin()`` dependency.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database_manager import get_db
from app.dependencies import get_current_user
from app.models import GuestInvite, User

router = APIRouter(
    prefix="/organizations/{org_id}/guest-invites",
    tags=["guest-invites"],
)


# -- Request / Response schemas ------------------------------------------------


class CreateGuestInviteRequest(BaseModel):
    label: str = Field(default="", max_length=255)
    max_uses: int = Field(default=0, ge=0, description="0 = unlimited")
    guest_ttl_hours: int = Field(default=4, ge=1, le=24)
    room_id: Optional[str] = None
    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=720)


class GuestInviteResponse(BaseModel):
    id: str
    token: str
    label: str
    max_uses: int
    use_count: int
    guest_ttl_hours: int
    room_id: Optional[str]
    expires_at: Optional[str]
    revoked: bool
    created_at: str
    invite_url: str


class GuestInviteListResponse(BaseModel):
    invites: list[GuestInviteResponse]
    total: int


# -- Helpers -------------------------------------------------------------------


def _invite_to_response(invite: GuestInvite) -> GuestInviteResponse:
    base_url = settings.BASE_URL.rstrip("/")
    return GuestInviteResponse(
        id=str(invite.id),
        token=invite.token,
        label=invite.label or "",
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        guest_ttl_hours=invite.guest_ttl_hours,
        room_id=invite.room_id,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        revoked=invite.revoked,
        created_at=invite.created_at.isoformat() if invite.created_at else "",
        invite_url=f"{base_url}/guest?invite={invite.token}",
    )


# -- Endpoints ----------------------------------------------------------------


@router.post("", response_model=GuestInviteResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_invite(
    org_id: str,
    body: CreateGuestInviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GuestInviteResponse:
    """Create a new guest invite link.

    Requires authenticated user (admin recommended).
    """
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid org_id"
        ) from exc

    token = secrets.token_urlsafe(32)
    expires_at = None
    if body.expires_in_hours:
        expires_at = datetime.now(UTC) + timedelta(hours=body.expires_in_hours)

    invite = GuestInvite(
        organization_id=org_uuid,
        created_by=current_user.id,
        token=token,
        label=body.label,
        max_uses=body.max_uses,
        guest_ttl_hours=body.guest_ttl_hours,
        room_id=body.room_id,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()
    await db.refresh(invite)
    return _invite_to_response(invite)


@router.get("", response_model=GuestInviteListResponse)
async def list_guest_invites(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GuestInviteListResponse:
    """List guest invites for an organization."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid org_id"
        ) from exc

    result = await db.execute(
        select(GuestInvite)
        .where(GuestInvite.organization_id == org_uuid)
        .order_by(GuestInvite.created_at.desc())
    )
    invites = result.scalars().all()
    return GuestInviteListResponse(
        invites=[_invite_to_response(i) for i in invites],
        total=len(invites),
    )


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_guest_invite(
    org_id: str,
    invite_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Revoke a guest invite link."""
    try:
        org_uuid = uuid.UUID(org_id)
        invite_uuid = uuid.UUID(invite_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID"
        ) from exc

    result = await db.execute(
        select(GuestInvite)
        .where(GuestInvite.id == invite_uuid)
        .where(GuestInvite.organization_id == org_uuid)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Guest invite not found"
        )

    invite.revoked = True
    await db.flush()
