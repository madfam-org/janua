"""Who may register or reconfigure an OAuth client, and which clients a
service boundary may trust.

Two halves, one registry (`core/reserved_oauth_boundaries.py`):

**Registration** (`authorize_client_registration`, `authorize_client_update`,
`authorize_reserved_client_management`). A platform admin (`User.is_admin`) may
register anything. Everyone else:

- may bind a client to an organization only when they own it or hold an
  ACTIVE ``admin``/``owner`` membership in it;
- may not use a reserved name, audience or scope;
- may not request the ``client_credentials`` grant for a client with no
  organization (a machine identity with no tenant is platform authority);
- may not pin a ``client_id`` (an operator feature for fixed ids across
  environments);
- may not edit, or rotate the secret of, a client that already carries a
  reserved value.

Every refusal is a 403 raised BEFORE anything is written.

**Trust** (`client_registered_by_platform_admin`). A service-auth module that
authorizes a token by re-reading its client row also requires that the row was
registered by a platform admin. All legitimate provisioning paths already do
this: `POST /oauth/clients/register` and `scripts/seed_service_clients.py`
record the bootstrap admin as ``created_by``, and admins creating clients from
the dashboard are admins. It keeps rows written before the registration check
existed from carrying authority. There is no separate "approved boundary" mark
on the model, and adding one would need a migration for the same answer.
"""

from __future__ import annotations

import uuid
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.reserved_oauth_boundaries import client_is_reserved, reserved_fields
from app.models import OAuthClient, Organization, OrganizationMember, User

ORG_ADMIN_ROLES = ("admin", "owner")


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def is_platform_admin(user: Optional[User]) -> bool:
    return bool(user is not None and getattr(user, "is_admin", False))


async def is_org_admin(db: AsyncSession, user: User, organization_id: uuid.UUID) -> bool:
    """Owner of the organization, or an ACTIVE admin/owner member of it."""
    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one_or_none()
    if org is None:
        return False
    owner_id = getattr(org, "owner_id", None)
    if owner_id and user.id and str(owner_id) == str(user.id):
        return True
    membership = (
        await db.execute(
            select(OrganizationMember.id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.role.in_(ORG_ADMIN_ROLES),
                OrganizationMember.status == "active",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return membership is not None


async def _require_org_admin(db: AsyncSession, user: User, organization_id: uuid.UUID) -> None:
    if not await is_org_admin(db, user, organization_id):
        # One answer for "no such organization" and "not an admin of it".
        raise _forbidden("Organization admin privileges required for this organization")


def _refuse_reserved(fields: list[str]) -> None:
    if fields:
        raise _forbidden(
            "Platform admin privileges required for reserved OAuth client values: "
            + ", ".join(fields)
        )


async def authorize_client_registration(
    db: AsyncSession,
    user: User,
    *,
    organization_id: Optional[uuid.UUID],
    name: Optional[str],
    audience: Optional[str],
    scopes: Optional[Iterable[str]],
    grant_types: Optional[Iterable[str]],
    pinned_client_id: Optional[str] = None,
) -> None:
    """Raise 403 unless ``user`` may register a client with these values."""
    if is_platform_admin(user):
        return
    _refuse_reserved(reserved_fields(name=name, audience=audience, scopes=scopes))
    if pinned_client_id:
        raise _forbidden("Platform admin privileges required to pin a client_id")
    if organization_id is not None:
        await _require_org_admin(db, user, organization_id)
    elif "client_credentials" in set(grant_types or []):
        raise _forbidden(
            "client_credentials clients must be bound to an organization you administer"
        )


async def authorize_client_update(
    db: AsyncSession,
    user: User,
    client: OAuthClient,
    changes: dict,
) -> None:
    """Raise 403 unless ``user`` may apply ``changes`` (a partial update) to ``client``.

    Evaluated against the RESULTING row, so an edit can neither introduce a
    reserved value nor touch a client that already holds one.
    """
    if is_platform_admin(user):
        return
    authorize_reserved_client_management(user, client)
    _refuse_reserved(
        reserved_fields(
            name=changes.get("name", client.name),
            audience=changes.get("audience", client.audience),
            scopes=changes.get("allowed_scopes", client.allowed_scopes),
        )
    )
    if not {"audience", "allowed_scopes", "grant_types"}.intersection(changes):
        return
    if client.organization_id is not None:
        await _require_org_admin(db, user, client.organization_id)
    elif "client_credentials" in (changes.get("grant_types", client.grant_types) or []):
        raise _forbidden(
            "client_credentials clients must be bound to an organization you administer"
        )


def authorize_reserved_client_management(user: User, client: OAuthClient) -> None:
    """Editing or rotating a client that holds a reserved value is platform-admin only."""
    if not is_platform_admin(user) and client_is_reserved(client):
        raise _forbidden("Platform admin privileges required to manage this OAuth client")


async def client_registered_by_platform_admin(db: AsyncSession, client: OAuthClient) -> bool:
    """True when the client's ``created_by`` is a platform admin.

    For service-auth modules: call it after the grant checks on the re-read
    client row and refuse when it is False.
    """
    if client is None or client.created_by is None:
        return False
    is_admin = (
        await db.execute(select(User.is_admin).where(User.id == client.created_by))
    ).scalar_one_or_none()
    return bool(is_admin)


__all__ = [
    "authorize_client_registration",
    "authorize_client_update",
    "authorize_reserved_client_management",
    "client_registered_by_platform_admin",
    "is_org_admin",
    "is_platform_admin",
]
