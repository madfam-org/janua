"""Narrow human-only policy management, separate from arbitrary organization settings."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mfa_enforcement import mfa_enrolled
from app.database import get_db
from app.models import OrganizationMember, User, UserStatus
from app.models.app_role import OrganizationMemberAppRole
from app.services.auth_service import AuthService
from app.services.organization_authentication_policy import (
    SECURITY_POLICY_APP,
    SECURITY_POLICY_ROLE,
    PolicyVersionConflict,
    get_authentication_policy,
    update_authentication_policy,
)

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


async def get_policy_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Issuer-native user authentication with a strict revocation-list read."""
    _require_bearer(credentials)
    payload = await AuthService.verify_token(credentials.credentials)
    try:
        user_id = UUID(payload["sub"]) if payload else None
    except (ValueError, TypeError, KeyError):
        user_id = None
    if user_id is None:
        raise HTTPException(401, "Invalid or expired token")
    user = (
        await db.execute(
            select(User).where(
                User.id == user_id, User.status == UserStatus.ACTIVE, User.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "Invalid or expired token")
    return user


class AuthenticationPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    organization_id: UUID
    mfa_mode: Literal["optional", "required"]
    version: int
    updated_at: datetime | None


class AuthenticationPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mfa_mode: Literal["optional", "required"]
    expected_version: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A reason is required")
        return value.strip()


async def _membership(db: AsyncSession, organization_id: UUID, user: User, *, lock: bool = False):
    query = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == user.id,
        OrganizationMember.status == "active",
    )
    if lock:
        query = query.with_for_update()
    member = (await db.execute(query)).scalar_one_or_none()
    if member is None:
        raise HTTPException(404, "No active membership for this organization")
    return member


def _require_bearer(credentials: HTTPAuthorizationCredentials | None) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            401, "Bearer authentication required", headers={"WWW-Authenticate": "Bearer"}
        )


@router.get("/{org_id}/authentication-policy", response_model=AuthenticationPolicyResponse)
async def read_authentication_policy(
    org_id: UUID,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    current_user: User = Depends(get_policy_user),
    db: AsyncSession = Depends(get_db),
):
    _require_bearer(credentials)
    await _membership(db, org_id, current_user)
    return await get_authentication_policy(db, org_id)


@router.put("/{org_id}/authentication-policy", response_model=AuthenticationPolicyResponse)
async def write_authentication_policy(
    org_id: UUID,
    body: AuthenticationPolicyUpdate,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    current_user: User = Depends(get_policy_user),
    db: AsyncSession = Depends(get_db),
):
    _require_bearer(credentials)
    # Factor disablement takes this same user lock. Hold it before re-reading
    # assurance/enrollment so a concurrent disable cannot strand the actor.
    current_user = (
        await db.execute(
            select(User)
            .where(
                User.id == current_user.id,
                User.status == UserStatus.ACTIVE,
                User.is_active.is_(True),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if current_user is None:
        raise HTTPException(401, "Invalid or expired authentication")
    if getattr(current_user, "is_service_account", False):
        raise HTTPException(403, "A human security administrator is required")
    membership = await _membership(db, org_id, current_user, lock=True)
    grant = (
        await db.execute(
            select(OrganizationMemberAppRole.id)
            .where(
                OrganizationMemberAppRole.organization_member_id == membership.id,
                OrganizationMemberAppRole.app == SECURITY_POLICY_APP,
                OrganizationMemberAppRole.role == SECURITY_POLICY_ROLE,
                OrganizationMemberAppRole.revoked_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if grant is None:
        raise HTTPException(403, "The organization security-policy permission is required")
    from app.auth.authentication_assurance import require_recent_authentication

    await require_recent_authentication(
        request, db, current_user, max_age_seconds=300, require_mfa=True
    )
    if body.mfa_mode == "required" and not mfa_enrolled(current_user):
        raise HTTPException(428, "Set up and verify your second factor before requiring MFA")
    try:
        return await update_authentication_policy(
            db,
            org_id,
            mfa_mode=body.mfa_mode,
            expected_version=body.expected_version,
            actor_id=current_user.id,
            reason=body.reason,
        )
    except PolicyVersionConflict:
        raise HTTPException(409, "The policy changed; reload it before confirming") from None
