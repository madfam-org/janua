"""Service authority for one organization's white-label branding.

WHY THIS EXISTS
---------------
The branding routes (`/white-label/branding…`) only knew people: reads took any
signed-in user and writes took a platform admin (`User.is_admin`). A platform
that renders a tenant's brand — nauta's ERP portal for Crea Tu Mundo — had no
way to call them except by holding a person's token or a static admin token.
Both are wrong: a static token expires within the hour under janua's service
token policy, and a platform-admin token is authority over every tenant.

This module adds the shape the ecosystem already uses for machine edges
(`payment_mail_auth.py`, `docs/service-tokens.md`): an ORG-BOUND confidential
`client_credentials` client whose short-lived token carries

  - aud `janua-white-label`,
  - scope `white-label:branding`,
  - `org_id` taken from `OAuthClient.organization_id` (never from the caller).

Such a token may read and write the branding of THAT organization only. The
client row is re-read on every call, so deactivating the client, removing the
scope or rebinding the organization takes effect immediately rather than at
token expiry.

HOW IT COEXISTS WITH PEOPLE
---------------------------
The route dependencies below try the service path FIRST and only when the
token verifies against the branding audience. A person's access token carries
the platform audience, so it never verifies here and falls through to the
existing `get_current_user` / `require_admin` checks unchanged. Conversely a
branding service token never verifies against the platform audience, so it can
never be mistaken for a person. Once a token IS addressed to this audience,
every failed check is a 403 — never a fallthrough to the user path.

WHAT THE SERVICE MAY NOT DO
---------------------------
It cannot set `custom_css`. The public `/white-label/css/{org}` endpoint appends
that field verbatim into a stylesheet, so it stays an admin-only field.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Optional, Union
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt_manager import jwt_manager
from app.core.redis import ResilientRedisClient, get_redis
from app.database import get_db
from app.dependencies import get_current_user, require_admin, security
from app.models import OAuthClient, User

BRANDING_AUDIENCE = "janua-white-label"
BRANDING_SCOPE = "white-label:branding"


@dataclass(frozen=True)
class BrandingServicePrincipal:
    client_id: str
    org_id: UUID


BrandingActor = Union[User, BrandingServicePrincipal]


def _denied(code: str = "branding_service_unauthorized") -> HTTPException:
    return HTTPException(status_code=403, detail={"code": code})


def _addressed_to_branding(token: str) -> Optional[dict]:
    """The verified payload when the token is addressed to this authority.

    `None` means "not a branding service token" and sends the caller down the
    person path. RS256 only: this is a service boundary and a symmetric
    runtime must not open it.
    """
    if jwt_manager.algorithm != "RS256":
        return None
    return jwt_manager.verify_token(token, audience=BRANDING_AUDIENCE)


def _principal_from_payload(payload: dict) -> BrandingServicePrincipal:
    client_id = payload.get("client_id")
    issued, expires = payload.get("iat"), payload.get("exp")
    scope = payload.get("scope")
    if (
        payload.get("aud") != BRANDING_AUDIENCE
        or payload.get("token_use") != "client_credentials"
        or payload.get("actor_type") != "service_account"
        or not isinstance(client_id, str)
        or not client_id
        or payload.get("sub") != f"service-account:{client_id}"
        or not isinstance(scope, str)
        or BRANDING_SCOPE not in scope.split()
        or type(issued) not in (int, float)
        or type(expires) not in (int, float)
        or not 0 < expires - issued <= 3600
        or expires <= time()
        or issued > time()
    ):
        raise _denied()
    try:
        org_id = UUID(str(payload.get("org_id")))
    except (ValueError, TypeError, AttributeError) as error:
        raise _denied() from error
    return BrandingServicePrincipal(client_id=client_id, org_id=org_id)


async def _current_grant(db: AsyncSession, principal: BrandingServicePrincipal) -> None:
    """Re-read the client row: a token minted before revocation is not enough."""
    result = await db.execute(
        select(OAuthClient)
        .where(OAuthClient.client_id == principal.client_id)
        .execution_options(populate_existing=True)
    )
    client = result.scalar_one_or_none()
    if (
        client is None
        or not client.is_active
        or not client.is_confidential
        or client.organization_id != principal.org_id
        or client.audience != BRANDING_AUDIENCE
        or BRANDING_SCOPE not in (client.allowed_scopes or [])
        or "client_credentials" not in (client.grant_types or [])
    ):
        raise _denied("branding_service_grant_unavailable")


def _require_same_org(principal: BrandingServicePrincipal, organization_id: str) -> None:
    try:
        target = UUID(str(organization_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise _denied("branding_service_wrong_organization") from error
    if target != principal.org_id:
        raise _denied("branding_service_wrong_organization")


async def _service_principal(
    credentials: HTTPAuthorizationCredentials,
    organization_id: str,
    db: AsyncSession,
) -> Optional[BrandingServicePrincipal]:
    payload = _addressed_to_branding(credentials.credentials)
    if payload is None:
        return None
    principal = _principal_from_payload(payload)
    # Organization first: a wrong-tenant caller learns nothing about whether
    # the target organization or its branding exists.
    _require_same_org(principal, organization_id)
    await _current_grant(db, principal)
    return principal


async def branding_reader(
    organization_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> BrandingActor:
    """Any signed-in person (unchanged), or the org's branding service."""
    principal = await _service_principal(credentials, organization_id, db)
    if principal is not None:
        return principal
    return await get_current_user(credentials, db, redis)


async def branding_writer(
    organization_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> BrandingActor:
    """A platform admin (unchanged), or the org's branding service."""
    principal = await _service_principal(credentials, organization_id, db)
    if principal is not None:
        return principal
    return require_admin(await get_current_user(credentials, db, redis))


def refuse_service_custom_css(actor: BrandingActor, custom_css: Optional[str]) -> None:
    """`custom_css` is appended verbatim to a public stylesheet: admins only."""
    if isinstance(actor, BrandingServicePrincipal) and custom_css is not None:
        raise _denied("branding_service_custom_css_forbidden")


__all__ = [
    "BRANDING_AUDIENCE",
    "BRANDING_SCOPE",
    "BrandingActor",
    "BrandingServicePrincipal",
    "branding_reader",
    "branding_writer",
    "refuse_service_custom_css",
]
