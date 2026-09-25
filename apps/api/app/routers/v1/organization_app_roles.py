"""Delegated application-role administration — an app's admins manage that app.

``internal_app_roles.py`` is the operator surface: grants made with the shared
``X-Internal-API-Key`` from inside the janua-api pod. That left the person who
OWNS a product unable to manage their own team's access to it without an
operator who has cluster access. This router is the self-service half, for a
signed-in person (``get_current_user``: a janua-audience token, the dashboard's).

The rule, and nothing else
--------------------------
An ACTIVE member of an organization who holds a LIVE ``<app>:admin`` grant in
THAT organization may list, grant and revoke roles OF THAT APP ONLY
(``<app>:<any role>``) for ACTIVE members of THAT SAME organization.

Every property the internal router's docstring states is kept:

1. NOTHING IS IMPLICIT. Organization roles (``owner``/``admin``/``member``) never
   confer app administration — an org owner without ``<app>:admin`` is refused
   like any other member. The only thing that authorizes delegation is a live
   ``<app>:admin`` row, and the first one for each app is still bootstrapped by
   an operator through ``POST /api/v1/internal/app-roles/grant``.
2. A GRANT CANNOT CROSS AN ORGANIZATION. The organization and the app come from
   the PATH; the body names only a member and a role. A caller who is not an
   active member of the path's organization, and a target who is not one, both
   get the SAME 404 (``NO_MEMBERSHIP_DETAIL``), so this surface cannot be used to
   probe who belongs to which organization. An ``email`` is resolved only among
   the organization's active members, never against the global user table.
3. NO DELETE ENDPOINT. Revocation stamps ``revoked_at``; a re-grant is a NEW row.
4. ``app`` and ``role`` stay OPAQUE and are shape-validated only
   (``schemas/app_role.py``).
5. AUDIT names the person. ``granted_by`` / ``revoked_by`` hold the CALLER's user
   id (never ``INTERNAL_API_KEY_PRINCIPAL``), and each write is logged through
   ``AuditLogger`` with the caller as ``identity_id``.

Two safety rules on top
-----------------------
* A caller may not grant or revoke their OWN ``<app>:admin``: another admin must.
  That makes an accidental self-lockout impossible and self-promotion moot.
* A revoke that would leave the organization with zero live ``<app>:admin``
  grants is refused with 409. With the self-change rule this can only be reached
  by two admins revoking each other at the same moment, so the live admin rows
  are read ``FOR UPDATE`` (PostgreSQL) and the second revoke sees the first.

When a change reaches a token
-----------------------------
Grants are resolved into the ``roles`` claim by ``services/org_claims_service.py``
at every token MINT. A new or revoked role therefore reaches a person's token at
their next sign-in or refresh, not instantly — and only for a session whose
primary organization is this one (the resolver emits app roles for the resolved
primary org alone).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import OrganizationMember, User
from app.models.app_role import OrganizationMemberAppRole, format_app_role
from app.routers.v1.internal_app_roles import NO_MEMBERSHIP_DETAIL
from app.schemas.app_role import (
    AppRoleGrantResponse,
    AppRoleMember,
    DelegatedAppRoleGrant,
    DelegatedAppRoleGrantRequest,
    DelegatedAppRoleListResponse,
    DelegatedAppRoleRevokeRequest,
    MyAppRolesResponse,
    validate_app_slug,
)
from app.services.audit_logger import AuditEventType, AuditLogger

logger = structlog.get_logger()

# Same per-route limiter pattern as routers/v1/auth.py; the global middleware
# budget for /api/v1/organizations still applies on top.
limiter = Limiter(key_func=get_remote_address)
MUTATION_RATE_LIMIT = "30/minute"

#: The role whose live grant authorizes administering an app. Opaque like every
#: other role name, except that THIS router gives it meaning within janua.
APP_ADMIN_ROLE = "admin"

SELF_ADMIN_CHANGE_DETAIL = (
    "You cannot change your own admin role for this app; another admin of the app must do it"
)
LAST_ADMIN_DETAIL = "Refused: this would leave the organization with no admin for this app"
AMBIGUOUS_EMAIL_DETAIL = (
    "More than one member of this organization has that email; name the member by user_id"
)

router = APIRouter(
    prefix="/organizations/{org_id}/app-roles",
    tags=["Organization App Roles"],
)


# ------------------------------------------------------------------ helpers


def _app_from_path(app: str) -> str:
    """Shape-check the path's ``app`` exactly as a body ``app`` would be."""
    try:
        return validate_app_slug(app)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _no_membership() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_MEMBERSHIP_DETAIL)


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    if user.display_name:
        return user.display_name
    full = " ".join(p for p in (user.first_name, user.last_name) if p)
    return full or None


async def _active_membership(db: AsyncSession, org_id: UUID, user_id) -> OrganizationMember:
    """The ONE active membership of ``user_id`` in ``org_id``, or the shared 404."""
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    membership = result.scalars().first()
    if membership is None:
        raise _no_membership()
    return membership


async def _live_roles(db: AsyncSession, membership_id, app: str | None = None) -> list:
    stmt = select(OrganizationMemberAppRole).where(
        OrganizationMemberAppRole.organization_member_id == membership_id,
        OrganizationMemberAppRole.revoked_at.is_(None),
    )
    if app is not None:
        stmt = stmt.where(OrganizationMemberAppRole.app == app)
    return list((await db.execute(stmt)).scalars().all())


async def _require_app_admin(
    db: AsyncSession, org_id: UUID, caller: User, app: str
) -> OrganizationMember:
    """Authorize the caller as an administrator of ``app`` in ``org_id``.

    404 (the shared detail) when the caller is not an active member — the same
    answer a nonexistent organization gets. 403 when they are a member without a
    live ``<app>:admin`` grant, whatever their organization role.
    """
    membership = await _active_membership(db, org_id, caller.id)
    roles = await _live_roles(db, membership.id, app)
    if not any(g.role == APP_ADMIN_ROLE for g in roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires the {format_app_role(app, APP_ADMIN_ROLE)} role in this organization",
        )
    return membership


async def _resolve_target_by_email(db: AsyncSession, org_id: UUID, email: str):
    """Resolve an email among the org's ACTIVE members only (never globally)."""
    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            func.lower(User.email) == email.lower(),
        )
    )
    rows = result.all()
    if not rows:
        raise _no_membership()
    if len(rows) > 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=AMBIGUOUS_EMAIL_DETAIL)
    return rows[0][0]


async def _get_live_grant(db: AsyncSession, membership_id, app: str, role: str):
    result = await db.execute(
        select(OrganizationMemberAppRole).where(
            OrganizationMemberAppRole.organization_member_id == membership_id,
            OrganizationMemberAppRole.app == app,
            OrganizationMemberAppRole.role == role,
            OrganizationMemberAppRole.revoked_at.is_(None),
        )
    )
    return result.scalars().first()


async def ensure_not_last_admin(db: AsyncSession, org_id: UUID, app: str, target_member_id) -> None:
    """409 when revoking the target's ``<app>:admin`` would leave zero admins.

    Reads the org's live admin grants of this app on ACTIVE memberships with
    ``FOR UPDATE`` so two concurrent mutual revocations serialize: the second
    one re-reads after the first commits and finds a single admin left.
    """
    result = await db.execute(
        select(OrganizationMemberAppRole)
        .join(
            OrganizationMember,
            OrganizationMember.id == OrganizationMemberAppRole.organization_member_id,
        )
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            OrganizationMemberAppRole.app == app,
            OrganizationMemberAppRole.role == APP_ADMIN_ROLE,
            OrganizationMemberAppRole.revoked_at.is_(None),
        )
        .with_for_update(of=OrganizationMemberAppRole)
    )
    live_admins = result.scalars().all()
    remaining = [g for g in live_admins if g.organization_member_id != target_member_id]
    if not remaining:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=LAST_ADMIN_DETAIL)


async def _audit(
    db: AsyncSession,
    *,
    event_type: AuditEventType,
    org_id: UUID,
    caller: User,
    grant_id: str,
    details: dict,
) -> None:
    """Best-effort audit, attributed to the CALLER (see internal_app_roles._audit)."""
    try:
        await AuditLogger(db).log(
            event_type=event_type,
            tenant_id=str(org_id),
            identity_id=str(caller.id),
            organization_id=str(org_id),
            resource_type="organization_member_app_role",
            resource_id=grant_id,
            details={"actor": str(caller.id), **details},
            severity="info",
        )
    except Exception:
        pass


# --------------------------------------------------------------- the caller


@router.get("", response_model=MyAppRolesResponse)
async def list_my_app_roles(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyAppRolesResponse:
    """The caller's own live application roles in this organization.

    ``administered_apps`` lists every app the caller holds ``<app>:admin`` for
    here — the apps whose roles they may manage. 404 (the shared detail) when the
    caller is not an active member.
    """
    membership = await _active_membership(db, org_id, current_user.id)
    grants = await _live_roles(db, membership.id)
    return MyAppRolesResponse(
        organization_id=str(org_id),
        user_id=str(current_user.id),
        claim_values=sorted({format_app_role(g.app, g.role) for g in grants}),
        administered_apps=sorted({g.app for g in grants if g.role == APP_ADMIN_ROLE}),
    )


# --------------------------------------------------------------------- list


@router.get("/{app}", response_model=DelegatedAppRoleListResponse)
async def list_app_grants(
    org_id: UUID,
    app: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DelegatedAppRoleListResponse:
    """Every LIVE grant of ``app`` in this organization, for an admin of that app.

    Each grant carries the member's user id, email and name. ``caller_roles`` are
    the caller's own live roles for the app; ``members`` is the organization's
    active roster the caller may grant to. Only grants on ACTIVE memberships are
    listed, because only those feed a token.
    """
    app = _app_from_path(app)
    caller_membership = await _require_app_admin(db, org_id, current_user, app)

    grant_rows = (
        await db.execute(
            select(OrganizationMemberAppRole, OrganizationMember, User)
            .join(
                OrganizationMember,
                OrganizationMember.id == OrganizationMemberAppRole.organization_member_id,
            )
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.status == "active",
                OrganizationMemberAppRole.app == app,
                OrganizationMemberAppRole.revoked_at.is_(None),
            )
            .order_by(OrganizationMemberAppRole.role, User.email)
        )
    ).all()

    member_rows = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.status == "active",
            )
            .order_by(User.email)
        )
    ).all()

    return DelegatedAppRoleListResponse(
        organization_id=str(org_id),
        app=app,
        caller_user_id=str(current_user.id),
        caller_roles=sorted({g.role for g, m, _u in grant_rows if m.id == caller_membership.id}),
        grants=[
            DelegatedAppRoleGrant(
                id=str(g.id),
                user_id=str(m.user_id),
                email=u.email,
                name=_display_name(u),
                role=g.role,
                claim_value=format_app_role(g.app, g.role),
                granted_by=g.granted_by,
                granted_at=g.granted_at,
            )
            for g, m, u in grant_rows
        ],
        members=[
            AppRoleMember(user_id=str(m.user_id), email=u.email, name=_display_name(u))
            for m, u in member_rows
        ],
    )


# -------------------------------------------------------------------- grant


@router.post(
    "/{app}/grant",
    response_model=AppRoleGrantResponse,
    # 201 is the declared default (the create case); the handler downgrades to
    # 200 when a live grant already existed, like internal_app_roles.grant.
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(MUTATION_RATE_LIMIT)
async def grant_app_role(
    request: Request,
    org_id: UUID,
    app: str,
    body: DelegatedAppRoleGrantRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppRoleGrantResponse:
    """Grant ``<app>:<role>`` to an active member of this organization. Idempotent.

    201 when this call created the grant, 200 when a live one already existed (it
    is returned untouched). 404 with the shared detail when the target — named by
    ``user_id`` or by ``email`` among this org's active members — is not an
    active member. 403 when the target is the caller and the role is ``admin``.

    ``granted_by`` records the caller's user id. The role reaches the member's
    token at their next sign-in or token refresh.
    """
    app = _app_from_path(app)
    await _require_app_admin(db, org_id, current_user, app)

    if body.user_id is not None:
        target = await _active_membership(db, org_id, body.user_id)
    else:
        target = await _resolve_target_by_email(db, org_id, body.email or "")

    if target.user_id == current_user.id and body.role == APP_ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SELF_ADMIN_CHANGE_DETAIL)

    target_user_id = str(target.user_id)
    claim_value = format_app_role(app, body.role)

    existing = await _get_live_grant(db, target.id, app, body.role)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return AppRoleGrantResponse(
            id=str(existing.id),
            organization_id=str(org_id),
            user_id=target_user_id,
            app=existing.app,
            role=existing.role,
            claim_value=claim_value,
            granted_at=existing.granted_at,
            revoked_at=None,
            changed=False,
        )

    grant = OrganizationMemberAppRole(
        organization_member_id=target.id,
        app=app,
        role=body.role,
        granted_by=str(current_user.id),
        granted_at=datetime.utcnow(),
    )
    db.add(grant)
    await db.flush()

    grant_id = str(grant.id)
    granted_at = grant.granted_at

    await _audit(
        db,
        event_type=AuditEventType.APP_ROLE_GRANT,
        org_id=org_id,
        caller=current_user,
        grant_id=grant_id,
        details={
            "via": "organizations.app_roles.grant",
            "user_id": target_user_id,
            "organization_member_id": str(target.id),
            "app": app,
            "role": body.role,
            "claim_value": claim_value,
        },
    )
    await db.commit()

    logger.info(
        "Granted application role via delegated admin",
        grant_id=grant_id,
        organization_id=str(org_id),
        user_id=target_user_id,
        actor=str(current_user.id),
        claim_value=claim_value,
    )

    return AppRoleGrantResponse(
        id=grant_id,
        organization_id=str(org_id),
        user_id=target_user_id,
        app=app,
        role=body.role,
        claim_value=claim_value,
        granted_at=granted_at,
        revoked_at=None,
        changed=True,
    )


# ------------------------------------------------------------------- revoke


@router.post("/{app}/revoke", response_model=AppRoleGrantResponse)
@limiter.limit(MUTATION_RATE_LIMIT)
async def revoke_app_role(
    request: Request,
    org_id: UUID,
    app: str,
    body: DelegatedAppRoleRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppRoleGrantResponse:
    """Retire ``<app>:<role>`` from an active member. Idempotent; never deletes.

    200 with ``changed: true`` when this call stamped ``revoked_at``, and with
    ``changed: false`` when no live grant existed. 403 when the target is the
    caller and the role is ``admin``; 409 when it would leave the organization
    with no ``<app>:admin``. ``revoked_by`` records the caller's user id. The
    revocation reaches the member's token at their next sign-in or refresh.
    """
    app = _app_from_path(app)
    await _require_app_admin(db, org_id, current_user, app)

    target = await _active_membership(db, org_id, body.user_id)
    if target.user_id == current_user.id and body.role == APP_ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SELF_ADMIN_CHANGE_DETAIL)

    target_user_id = str(target.user_id)
    claim_value = format_app_role(app, body.role)

    grant = await _get_live_grant(db, target.id, app, body.role)
    if grant is None:
        return AppRoleGrantResponse(
            id=None,
            organization_id=str(org_id),
            user_id=target_user_id,
            app=app,
            role=body.role,
            claim_value=claim_value,
            granted_at=None,
            revoked_at=None,
            changed=False,
        )

    if body.role == APP_ADMIN_ROLE:
        await ensure_not_last_admin(db, org_id, app, target.id)

    grant.revoked_at = datetime.utcnow()
    grant.revoked_by = str(current_user.id)

    grant_id = str(grant.id)
    granted_at = grant.granted_at
    revoked_at = grant.revoked_at

    await _audit(
        db,
        event_type=AuditEventType.APP_ROLE_REVOKE,
        org_id=org_id,
        caller=current_user,
        grant_id=grant_id,
        details={
            "via": "organizations.app_roles.revoke",
            "user_id": target_user_id,
            "organization_member_id": str(target.id),
            "app": app,
            "role": body.role,
            "claim_value": claim_value,
        },
    )
    await db.commit()

    logger.info(
        "Revoked application role via delegated admin",
        grant_id=grant_id,
        organization_id=str(org_id),
        user_id=target_user_id,
        actor=str(current_user.id),
        claim_value=claim_value,
    )

    return AppRoleGrantResponse(
        id=grant_id,
        organization_id=str(org_id),
        user_id=target_user_id,
        app=app,
        role=body.role,
        claim_value=claim_value,
        granted_at=granted_at,
        revoked_at=revoked_at,
        changed=True,
    )


__all__ = ["router", "ensure_not_last_admin"]
