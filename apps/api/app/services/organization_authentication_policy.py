"""A missing policy is optional; an unreadable policy never means optional."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization_authentication_policy import (
    OrganizationAuthenticationPolicy,
    OrganizationAuthenticationPolicyChange,
)

MfaMode = Literal["optional", "required"]
SECURITY_POLICY_APP = "crea-map"
SECURITY_POLICY_ROLE = "security-policy-admin"
TECHNICAL_MFA_ROLE = "mfa-required"


@dataclass(frozen=True)
class AuthenticationPolicy:
    organization_id: UUID
    mfa_mode: MfaMode = "optional"
    version: int = 0
    updated_at: datetime | None = None


class PolicyVersionConflict(Exception):
    """The caller reviewed an obsolete policy version."""


async def get_authentication_policy(
    db: AsyncSession, organization_id: UUID
) -> AuthenticationPolicy:
    row = (
        await db.execute(
            select(OrganizationAuthenticationPolicy).where(
                OrganizationAuthenticationPolicy.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return AuthenticationPolicy(organization_id=organization_id)
    if row.mfa_mode not in ("optional", "required"):
        raise ValueError("Invalid persisted authentication policy")
    return AuthenticationPolicy(organization_id, row.mfa_mode, row.version, row.updated_at)


async def organization_requires_mfa(db: AsyncSession, organization_id: UUID | None) -> bool:
    if organization_id is None:
        return False
    return (await get_authentication_policy(db, organization_id)).mfa_mode == "required"


async def member_requires_mfa(db: AsyncSession, user_id: UUID, organization_id: UUID) -> bool:
    """Live product-owned MFA floor, independent of the optional team policy.

    MAP synchronizes this reserved requirement from its real technical-direction
    roster. Never infer it from email, org ownership, a browser parameter, or a
    stale token's roles. An unreadable grant/policy fails closed.
    """
    if await organization_requires_mfa(db, organization_id):
        return True
    from app.models import OrganizationMember
    from app.models.app_role import OrganizationMemberAppRole

    grant = await db.execute(
        select(OrganizationMemberAppRole.id)
        .join(OrganizationMember,
              OrganizationMember.id == OrganizationMemberAppRole.organization_member_id)
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == "active",
            OrganizationMemberAppRole.app == SECURITY_POLICY_APP,
            OrganizationMemberAppRole.role == TECHNICAL_MFA_ROLE,
            OrganizationMemberAppRole.revoked_at.is_(None),
        ).limit(1)
    )
    return grant.scalar_one_or_none() is not None


async def update_authentication_policy(
    db: AsyncSession,
    organization_id: UUID,
    *,
    mfa_mode: MfaMode,
    expected_version: int,
    actor_id: UUID,
    reason: str,
) -> AuthenticationPolicy:
    """Atomically compare-and-swap policy plus journal; never mutate other settings."""
    if mfa_mode not in ("optional", "required") or expected_version < 0:
        raise ValueError("Invalid authentication policy update")
    reason = reason.strip()
    if not 1 <= len(reason) <= 300:
        raise ValueError("A bounded reason is required")
    now = datetime.utcnow()
    current = await get_authentication_policy(db, organization_id)
    if current.version != expected_version:
        raise PolicyVersionConflict()
    version = expected_version + 1
    if expected_version == 0:
        db.add(
            OrganizationAuthenticationPolicy(
                organization_id=organization_id,
                mfa_mode=mfa_mode,
                version=version,
                updated_by=actor_id,
                updated_at=now,
            )
        )
    else:
        result = await db.execute(
            update(OrganizationAuthenticationPolicy)
            .where(
                OrganizationAuthenticationPolicy.organization_id == organization_id,
                OrganizationAuthenticationPolicy.version == expected_version,
            )
            .values(
                mfa_mode=mfa_mode,
                version=version,
                updated_by=actor_id,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            await db.rollback()
            raise PolicyVersionConflict()
    db.add(
        OrganizationAuthenticationPolicyChange(
            organization_id=organization_id,
            version=version,
            previous_mode=current.mfa_mode,
            mfa_mode=mfa_mode,
            actor_id=actor_id,
            reason=reason,
            created_at=now,
        )
    )
    try:
        await db.commit()
    except IntegrityError as error:
        # A concurrent first save/version race must not produce two winners.
        await db.rollback()
        raise PolicyVersionConflict() from error
    return AuthenticationPolicy(organization_id, mfa_mode, version, now)
