"""
Invitation management API endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.locale import locale_from_request
from app.database import get_db
from app.dependencies import get_current_user, require_org_admin
from app.models import Organization, OrganizationMember
from app.models.invitation import (
    BulkInvitationCreate,
    BulkInvitationResponse,
    Invitation,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreate,
    InvitationListResponse,
    InvitationResponse,
    InvitationStatus,
    InvitationUpdate,
)
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.invitation_service import InvitationService

router = APIRouter(prefix="/v1/invitations", tags=["invitations"])


def _invite_base_url() -> str:
    """Root for acceptance links.

    The handlers below used to pass `settings.APP_URL`, which is not a setting
    on this application at all -- reading it raised AttributeError before the
    URL could be built.
    """
    return settings.FRONTEND_URL or settings.BASE_URL


def _as_uuid(value: str) -> Optional[uuid.UUID]:
    """Parse an id from the path, or None when it is not a UUID at all.

    The columns being compared are `uuid`, so handing Postgres an arbitrary
    string is a 500 rather than the 404 the caller should see.
    """
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


async def _accessible_org_ids(db: AsyncSession, user: User) -> set:
    """Organizations whose invitations this user may see.

    Scoping is by `organization_id`, the only tenancy this table records.
    The previous filter -- `Invitation.tenant_id == current_user.tenant_id` --
    named a column that does not exist on `invitations`, and the fallback
    branch called `current_user.get_organizations()`, a method `User` does not
    define. Either one raised before a single row could be scoped.
    """
    member_rows = await db.execute(
        select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
    )
    org_ids = set(member_rows.scalars().all())

    owned_rows = await db.execute(select(Organization.id).where(Organization.owner_id == user.id))
    org_ids.update(owned_rows.scalars().all())

    return org_ids


async def _require_org_admin_for(db: AsyncSession, user: User, organization_id) -> None:
    """Assert the caller administers *this* organization.

    `require_org_admin` only proves the caller is an admin or owner of SOME
    organization. Without a per-organization check, an admin of org A could
    mutate org B's invitations. Raises 404 rather than 403 so the endpoint
    does not confirm that an invitation the caller cannot reach exists.
    """
    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one_or_none()

    owner_id = getattr(org, "owner_id", None)
    # Both ids must be present before they can match, so that an ownerless
    # organization and an id-less caller do not compare equal as "None".
    if owner_id and user.id and str(owner_id) == str(user.id):
        return

    membership = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.role.in_(["admin", "owner"]),
            )
        )
    ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")


def _to_response(invitation: Invitation) -> InvitationResponse:
    """Build the API response from columns that exist.

    `role_name`, `invited_by`, `message` and `email_sent` were read here; the
    first two are spelled `role` and `created_by` on the table and the last
    two were not columns at all until this change.
    """
    return InvitationResponse(
        id=str(invitation.id),
        organization_id=str(invitation.organization_id),
        email=invitation.email,
        role=invitation.role or "member",
        status=invitation.status,
        invited_by=str(invitation.created_by),
        message=invitation.message,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        invite_url=invitation.generate_invite_url(_invite_base_url()),
        email_sent=bool(invitation.email_sent),
    )


@router.post("/", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    invitation_data: InvitationCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new invitation for an organization (org admin only).
    """
    service = InvitationService(db)

    try:
        invitation = await service.create_invitation(
            invitation_data=invitation_data,
            invited_by=current_user,
            tenant_id=str(current_user.tenant_id),
        )

        return invitation

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/bulk", response_model=BulkInvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_invitations(
    bulk_data: BulkInvitationCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create multiple invitations at once (org admin only).
    """
    service = InvitationService(db)

    result = await service.create_bulk_invitations(
        emails=bulk_data.emails,
        organization_id=bulk_data.organization_id,
        role=bulk_data.role,
        message=bulk_data.message,
        expires_in=bulk_data.expires_in,
        invited_by=current_user,
        tenant_id=str(current_user.tenant_id),
    )

    return BulkInvitationResponse(**result)


@router.get("/", response_model=InvitationListResponse)
async def list_invitations(
    organization_id: Optional[str] = None,
    status: Optional[InvitationStatus] = None,
    email: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List invitations for organizations the user has access to.
    """
    org_ids = await _accessible_org_ids(db, current_user)

    # An explicit organization narrows the scope; it never widens it.
    if organization_id:
        requested = _as_uuid(organization_id)
        org_ids = {requested} & org_ids if requested else set()

    if not org_ids:
        return InvitationListResponse(invitations=[], total=0)

    scoped = select(Invitation).where(Invitation.organization_id.in_(org_ids))

    if email:
        scoped = scoped.where(Invitation.email.ilike(f"%{email}%"))

    # The status breakdown describes the whole scoped set, so it is counted
    # before the status filter narrows the listing itself.
    async def _count(stmt) -> int:
        result = await db.execute(select(func.count()).select_from(stmt.subquery()))
        return result.scalar() or 0

    pending_count = await _count(scoped.where(Invitation.status == InvitationStatus.PENDING.value))
    accepted_count = await _count(
        scoped.where(Invitation.status == InvitationStatus.ACCEPTED.value)
    )
    expired_count = await _count(scoped.where(Invitation.status == InvitationStatus.EXPIRED.value))

    listing = scoped
    if status:
        listing = listing.where(Invitation.status == status.value)

    total = await _count(listing)

    result = await db.execute(
        listing.order_by(Invitation.created_at.desc()).offset(skip).limit(limit)
    )
    invitations = result.scalars().all()

    return InvitationListResponse(
        invitations=[_to_response(inv) for inv in invitations],
        total=total,
        pending_count=pending_count,
        accepted_count=accepted_count,
        expired_count=expired_count,
    )


async def _load_scoped(db: AsyncSession, invitation_id: str, user: User) -> Invitation:
    """Fetch an invitation the caller is allowed to see, or 404."""
    parsed = _as_uuid(invitation_id)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    invitation = (
        await db.execute(select(Invitation).where(Invitation.id == parsed))
    ).scalar_one_or_none()

    if invitation is None or invitation.organization_id not in await _accessible_org_ids(db, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    return invitation


@router.get("/{invitation_id}", response_model=InvitationResponse)
async def get_invitation(
    invitation_id: str, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get a specific invitation by ID.
    """
    invitation = await _load_scoped(db, invitation_id, current_user)
    return _to_response(invitation)


@router.patch("/{invitation_id}", response_model=InvitationResponse)
async def update_invitation(
    invitation_id: str,
    update_data: InvitationUpdate,
    current_user=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a pending invitation (org admin only).
    """
    invitation = await _load_scoped(db, invitation_id, current_user)
    await _require_org_admin_for(db, current_user, invitation.organization_id)

    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update invitation with status: {invitation.status}",
        )

    # Update fields. `role` was written as `role_name` and `message` was not a
    # column, so both assignments used to land on plain Python attributes: the
    # response echoed the new values back and the database kept the old ones.
    if update_data.role is not None:
        invitation.role = update_data.role

    if update_data.message is not None:
        invitation.message = update_data.message

    if update_data.expires_at is not None:
        invitation.expires_at = update_data.expires_at

    await db.commit()
    await db.refresh(invitation)

    return _to_response(invitation)


@router.post("/{invitation_id}/resend", response_model=InvitationResponse)
async def resend_invitation(
    invitation_id: str,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Resend an invitation email (org admin only).
    """
    # Neither this endpoint nor the service it delegates to checked which
    # organization the invitation belongs to, so any organization admin could
    # act on any organization's invitations by id.
    invitation = await _load_scoped(db, invitation_id, current_user)
    await _require_org_admin_for(db, current_user, invitation.organization_id)

    service = InvitationService(db)

    try:
        invitation = await service.resend_invitation(
            invitation_id=invitation_id, resent_by=current_user
        )

        return invitation

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: str,
    current_user=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a pending invitation (org admin only).
    """
    invitation = await _load_scoped(db, invitation_id, current_user)
    await _require_org_admin_for(db, current_user, invitation.organization_id)

    service = InvitationService(db)

    try:
        await service.revoke_invitation(invitation_id=invitation_id, revoked_by=current_user)

        return None

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/accept", response_model=InvitationAcceptResponse)
async def accept_invitation(
    accept_data: InvitationAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept an invitation using the token.
    """
    service = InvitationService(db)

    try:
        # Get user if user_id provided
        user = None
        if accept_data.user_id:
            result = await db.execute(select(User).where(User.id == accept_data.user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

        # Or create new user if registration data provided
        new_user_data = None
        if accept_data.password and accept_data.name and not user:
            # hash_password is a static method; AuthService takes no arguments.
            password_hash = AuthService.hash_password(accept_data.password)
            new_user_data = {"name": accept_data.name, "password_hash": password_hash}

        # Accept invitation
        result = await service.accept_invitation(
            token=accept_data.token,
            user=user,
            new_user_data=new_user_data,
            locale=locale_from_request(request),
        )

        return InvitationAcceptResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/validate/{token}")
async def validate_invitation_token(token: str, db: AsyncSession = Depends(get_db)):
    """
    Validate an invitation token and get details.
    """
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation token"
        )

    # Check if expired
    if invitation.is_expired:
        return {
            "valid": False,
            "reason": "Invitation has expired",
            "email": invitation.email,
            "organization_id": str(invitation.organization_id),
        }

    # Check if already accepted
    if invitation.status == InvitationStatus.ACCEPTED.value:
        return {
            "valid": False,
            "reason": "Invitation has already been accepted",
            "email": invitation.email,
            "organization_id": str(invitation.organization_id),
        }

    # Check if revoked
    if invitation.status == InvitationStatus.REVOKED.value:
        return {
            "valid": False,
            "reason": "Invitation has been revoked",
            "email": invitation.email,
            "organization_id": str(invitation.organization_id),
        }

    # Get organization details
    org_result = await db.execute(
        select(Organization).where(Organization.id == invitation.organization_id)
    )
    org = org_result.scalar_one_or_none()

    return {
        "valid": True,
        "email": invitation.email,
        "organization_id": str(invitation.organization_id),
        "organization_name": org.name if org else None,
        "role": invitation.role,
        "expires_at": invitation.expires_at.isoformat(),
        "message": invitation.message,
    }


@router.post("/cleanup")
async def cleanup_expired_invitations(
    current_user=Depends(require_org_admin), db: AsyncSession = Depends(get_db)
):
    """
    Clean up expired invitations (org admin only).
    """
    # This used to call `InvitationService.cleanup_expired_invitations`, a
    # synchronous method built on `Session.query`. The session injected here
    # is an AsyncSession, which has no `.query`, so the call raised before it
    # could mark anything -- and it swept every organization's invitations,
    # not just those of the admin making the request. Both are fixed by
    # expiring within the caller's own organizations, in one statement.
    org_ids = await _accessible_org_ids(db, current_user)
    if not org_ids:
        return {"message": "Marked 0 invitations as expired", "count": 0}

    result = await db.execute(
        update(Invitation)
        .where(
            Invitation.organization_id.in_(org_ids),
            Invitation.status == InvitationStatus.PENDING.value,
            Invitation.expires_at < datetime.utcnow(),
        )
        .values(status=InvitationStatus.EXPIRED.value)
    )
    await db.commit()

    count = result.rowcount or 0

    return {"message": f"Marked {count} invitations as expired", "count": count}
