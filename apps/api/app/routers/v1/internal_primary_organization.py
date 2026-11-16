"""Internal primary-organization endpoints — set / clear / read.

A **primary organization** is the ONE organization a person's tokens speak for
when they hold several active memberships. Without one, the claims resolver
(``services/org_claims_service.py``) emits ``orgs`` and nothing else for such a
person — no ``org_id``, no ``madfam_org_roles`` and no application roles — so a
staff account with several organization memberships can never pass a resource
server that gates on an application role, however many grants it holds.

Why not ``tenant_id``
---------------------
``users.tenant_id`` already disambiguates, and it must not be used for this. It
is the email-uniqueness pool the identity lives in (see the docstring of
``internal_users.py``): pointing it at an organization for staff once made
magic link and password reset unable to find them. The primary organization is
a separate table (``user_primary_organizations``, migration 022, one row per
user) with no identity-pool meaning, and ``tenant_id`` still wins when it names
an active membership. It is a table and not a ``users`` column so that the
``User`` model, read on every login, does not depend on the migration.

Rules the handlers hold
-----------------------
1. CHOSEN, NEVER GUESSED. The resolver refuses to pick a primary organization
   for a multi-org user; this surface is where an operator picks one, and the
   audit trail records who (the internal-key principal), when and what it
   replaced. Nothing here derives a choice from roles, join dates or order.
2. ONLY AN ACTIVE MEMBERSHIP. ``set`` answers 404 — with exactly the
   ``NO_MEMBERSHIP_DETAIL`` the app-role grant uses — when the user holds no
   ACTIVE membership in the organization. The resolver re-checks at every mint,
   so a membership removed later stops the pointer from resolving (fail
   closed) without anyone having to clear it.
3. NOTHING IS DELETED. ``clear`` sets the row's ``organization_id`` to NULL
   (recording who and when on the row); no row is removed, and the history of
   choices lives on the AuditLogger trail. Both writes are
   idempotent and report ``changed``.

Auth is ``verify_internal_api_key``, the same swappable seam as
``internal_app_roles.py``. There is deliberately no user-facing self-service
path: which organization's authority a token carries is an operator decision.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.models import OrganizationMember, User
from app.models.user_primary_organization import UserPrimaryOrganization
from app.routers.v1.internal_app_roles import NO_MEMBERSHIP_DETAIL, _get_active_membership
from app.routers.v1.oauth_clients import INTERNAL_API_KEY_PRINCIPAL
from app.schemas.primary_organization import (
    PrimaryOrganizationClearRequest,
    PrimaryOrganizationResponse,
    PrimaryOrganizationSetRequest,
)
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.org_claims_service import APP_ROLES_KEY, get_user_org_claims

logger = structlog.get_logger()

router = APIRouter(prefix="/primary-organization", tags=["internal"])

# One message for "no such user" on the user-addressed routes (clear, read).
# `set` answers with NO_MEMBERSHIP_DETAIL instead, exactly like the app-role
# grant, so it cannot be used to probe who belongs to which organization.
NO_USER_DETAIL = "No janua user for that id"

__all__ = ["NO_MEMBERSHIP_DETAIL", "NO_USER_DETAIL", "router"]


async def _get_user(db: AsyncSession, user_id) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_USER_DETAIL)
    return user


async def _get_pointer(db: AsyncSession, user_id) -> UserPrimaryOrganization | None:
    return await db.get(UserPrimaryOrganization, user_id)


async def _has_active_membership(db: AsyncSession, user_id, organization_id) -> bool:
    if organization_id is None:
        return False
    result = await db.execute(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    return result.first() is not None


async def _describe(
    db: AsyncSession, user: User, *, changed: bool | None
) -> PrimaryOrganizationResponse:
    """The stored value plus the resolver's own answer for the next token.

    Calls the SAME resolver every minting seam calls, so what an operator reads
    here cannot drift from what a token carries.
    """
    pointer = await _get_pointer(db, user.id)
    stored = pointer.organization_id if pointer is not None else None
    claims = await get_user_org_claims(user, db)
    return PrimaryOrganizationResponse(
        user_id=str(user.id),
        primary_organization_id=str(stored) if stored else None,
        active_membership=await _has_active_membership(db, user.id, stored),
        token_org_id=claims.get("org_id"),
        token_app_roles=list(claims.get(APP_ROLES_KEY) or []),
        changed=changed,
    )


async def _audit(
    db: AsyncSession,
    *,
    event_type: AuditEventType,
    organization_id,
    user_id,
    details: dict,
) -> None:
    """Best-effort audit on the AuditLogger trail, as ``internal_app_roles._audit``.

    Swallowed: a failure in the trail must not roll back the write the operator
    asked for.
    """
    try:
        await AuditLogger(db).log(
            event_type=event_type,
            tenant_id=str(organization_id),
            identity_id=None,
            resource_type="user_primary_organization",
            resource_id=str(user_id),
            details={"actor": INTERNAL_API_KEY_PRINCIPAL, **details},
            severity="info",
        )
    except Exception:
        pass


@router.post("/set", response_model=PrimaryOrganizationResponse)
async def set_primary_organization(
    body: PrimaryOrganizationSetRequest,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> PrimaryOrganizationResponse:
    """Make ``organization_id`` the person's primary organization. Idempotent.

    404 (``NO_MEMBERSHIP_DETAIL``) when the user holds no ACTIVE membership
    there: a primary organization that could never resolve is an operator error
    worth surfacing, not a value to store. Re-setting the stored value is a
    no-op with ``changed: false`` and writes no audit entry. Replacing another
    value is allowed and records the previous one on the audit trail.
    """
    membership = await _get_active_membership(db, body.organization_id, body.user_id)
    user = await _get_user(db, body.user_id)

    pointer = await _get_pointer(db, body.user_id)
    previous = pointer.organization_id if pointer is not None else None
    if previous is not None and str(previous) == str(body.organization_id):
        return await _describe(db, user, changed=False)

    if pointer is None:
        pointer = UserPrimaryOrganization(user_id=body.user_id)
        db.add(pointer)
    pointer.organization_id = body.organization_id
    pointer.set_by = INTERNAL_API_KEY_PRINCIPAL
    pointer.set_at = datetime.utcnow()
    await _audit(
        db,
        event_type=AuditEventType.PRIMARY_ORGANIZATION_SET,
        organization_id=body.organization_id,
        user_id=body.user_id,
        details={
            "via": "internal.primary_organization.set",
            "user_id": str(body.user_id),
            "organization_id": str(body.organization_id),
            "organization_member_id": str(membership.id),
            "previous_organization_id": str(previous) if previous else None,
        },
    )
    await db.commit()
    await db.refresh(user)

    logger.info(
        "Set primary organization via internal API",
        user_id=str(body.user_id),
        organization_id=str(body.organization_id),
        replaced=previous is not None,
    )
    return await _describe(db, user, changed=True)


@router.post("/clear", response_model=PrimaryOrganizationResponse)
async def clear_primary_organization(
    body: PrimaryOrganizationClearRequest,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> PrimaryOrganizationResponse:
    """Remove the person's primary organization. Idempotent; deletes nothing.

    Always 200 for an existing user: ``changed`` says whether THIS call cleared
    a value. Clearing does not require a membership — a pointer left behind by
    a removed membership must still be removable.
    """
    user = await _get_user(db, body.user_id)

    pointer = await _get_pointer(db, body.user_id)
    previous = pointer.organization_id if pointer is not None else None
    if previous is None:
        return await _describe(db, user, changed=False)

    # An UPDATE to NULL, never a DELETE: the row keeps who cleared it and when.
    pointer.organization_id = None
    pointer.set_by = INTERNAL_API_KEY_PRINCIPAL
    pointer.set_at = datetime.utcnow()
    await _audit(
        db,
        event_type=AuditEventType.PRIMARY_ORGANIZATION_CLEAR,
        organization_id=previous,
        user_id=body.user_id,
        details={
            "via": "internal.primary_organization.clear",
            "user_id": str(body.user_id),
            "previous_organization_id": str(previous),
        },
    )
    await db.commit()
    await db.refresh(user)

    logger.info(
        "Cleared primary organization via internal API",
        user_id=str(body.user_id),
        previous_organization_id=str(previous),
    )
    return await _describe(db, user, changed=True)


@router.get("/{user_id}", response_model=PrimaryOrganizationResponse)
async def read_primary_organization(
    user_id: UUID,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> PrimaryOrganizationResponse:
    """The stored primary organization and what the next token resolves to."""
    user = await _get_user(db, user_id)
    return await _describe(db, user, changed=None)
