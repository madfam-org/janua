"""Native service authority for a narrow, money-light CTM payment notice."""

from dataclasses import dataclass
from time import time
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt_manager import jwt_manager
from app.models import OAuthClient

MAIL_AUDIENCE = "janua-email"
PAYMENT_MAIL_SCOPE = "crea-map:payment-mail"
_security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class PaymentMailPrincipal:
    client_id: str
    org_id: UUID


def _denied(code="mail_service_unauthorized"):
    return HTTPException(status_code=403, detail={"code": code})


async def payment_mail_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> PaymentMailPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _denied()
    # This is a service boundary, including in local fixtures. No symmetric
    # fallback, audience omission, or shared internal-key authority here.
    if jwt_manager.algorithm != "RS256":
        raise _denied()
    payload = jwt_manager.verify_token(credentials.credentials, audience=MAIL_AUDIENCE)
    if not payload:
        raise _denied()
    client_id = payload.get("client_id")
    issued, expires = payload.get("iat"), payload.get("exp")
    if (
        payload.get("aud") != MAIL_AUDIENCE
        or payload.get("token_use") != "client_credentials"
        or payload.get("actor_type") != "service_account"
        or not isinstance(client_id, str)
        or not client_id
        or payload.get("sub") != f"service-account:{client_id}"
        or not isinstance(payload.get("scope"), str)
        or PAYMENT_MAIL_SCOPE not in payload["scope"].split()
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
    return PaymentMailPrincipal(client_id=client_id, org_id=org_id)


async def current_mail_client(db: AsyncSession, principal: PaymentMailPrincipal) -> OAuthClient:
    """Check the native grant under the same transaction that claims dispatch.

    A token minted before scope revocation is not enough. The shared row lock
    orders a claim against client deactivation, rebinding and scope changes.
    Revocation cannot recall an already authorized in-flight provider operation.
    """
    result = await db.execute(
        select(OAuthClient)
        .where(OAuthClient.client_id == principal.client_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    client = result.scalar_one_or_none()
    if (
        client is None
        or not client.is_active
        or not client.is_confidential
        or client.organization_id != principal.org_id
        or client.audience != MAIL_AUDIENCE
        or PAYMENT_MAIL_SCOPE not in (client.allowed_scopes or [])
        or "client_credentials" not in (client.grant_types or [])
    ):
        raise _denied("mail_service_grant_unavailable")
    return client
