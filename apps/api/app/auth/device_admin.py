"""Who may administer an organization's shared devices: a person, never a machine.

Used by the administrators' routes in `routers/v1/device_enrolment.py`
(approve, list, disable). The caller must present a Janua access token for a
PERSON: signature, issuer, Janua's own audience, expiry and the revocation list
are checked (strictly: 503 when Redis cannot say), the subject must be an active
user who is not a service account, and the token may carry no machine marker
(``token_use``, ``actor_type``, ``client_kind``, ``is_service_account``, or a
``service-account:`` subject). API keys, service tokens and device tokens are
therefore refused.

The person must own the organization or hold an active ``owner``/``admin``
membership in it. A person with no active membership gets the same 404 as an
organization that does not exist.
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import ResilientRedisClient, get_redis
from app.models import Organization, OrganizationMember, User, UserStatus

bearer = HTTPBearer(auto_error=False)

NO_MEMBERSHIP_DETAIL = "Organization not found"
NOT_ADMIN_DETAIL = "Requires the owner or admin role in this organization"
PERSON_REQUIRED_DETAIL = "A person's own sign-in is required"


def _is_machine_payload(payload: dict) -> bool:
    return bool(
        payload.get("token_use")
        or payload.get("actor_type")
        or payload.get("client_kind")
        or payload.get("is_service_account") is True
        or str(payload.get("sub", "")).startswith("service-account:")
    )


async def require_person(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> User:
    """A person, signed in to Janua with their own access token. Never a machine.

    Signature, issuer, Janua's own audience, expiry and the revocation list are
    checked (strictly: 503 when Redis cannot say). A token with any machine
    marker, and a user flagged as a service account, are refused with 403.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = await jwt_manager.verify_unrevoked_token(
        credentials.credentials, token_type="access", redis=redis
    )
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if _is_machine_payload(payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, PERSON_REQUIRED_DETAIL)
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = (
        await db.execute(
            select(User).where(
                User.id == user_id, User.status == UserStatus.ACTIVE, User.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if getattr(user, "is_service_account", False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, PERSON_REQUIRED_DETAIL)
    return user


async def require_org_admin(db: AsyncSession, org_id: uuid.UUID, user: User) -> Organization:
    """The organization, when ``user`` owns it or is an active owner/admin member.

    404 for a person with no active membership (the answer a missing
    organization gets too), 403 for a member without the role.
    """
    organization = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_MEMBERSHIP_DETAIL)
    if organization.owner_id == user.id:
        return organization
    membership = (
        (
            await db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.status == "active",
                )
            )
        )
        .scalars()
        .first()
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_MEMBERSHIP_DETAIL)
    if membership.role not in ("owner", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_ADMIN_DETAIL)
    return organization


__all__ = [
    "NO_MEMBERSHIP_DETAIL",
    "NOT_ADMIN_DETAIL",
    "PERSON_REQUIRED_DETAIL",
    "require_org_admin",
    "require_person",
]
