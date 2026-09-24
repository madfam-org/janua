"""Service-token authority for delegated provider tokens (`/connections/{id}/token`).

Per the cross-service auth decision (`docs/service-tokens.md`), a service that
borrows a user's provider credential authenticates with a Janua-issued RS256
`client_credentials` token — audience `janua-connections`, scope
`connections:delegate` — not with a shared static secret. This module verifies
such a token and then re-checks the client's *current* grant in the database,
so a client that was deactivated or had the scope removed after minting is
refused even while its token is still unexpired.

Every refusal names its reason. Nothing here falls back to HS256, an omitted
audience, or the legacy static token.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import time
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.consent_purposes import (
    CONNECTIONS_AUDIENCE,
    CONNECTIONS_DELEGATE_SCOPE,
    ConsentPurpose,
    get_purpose,
)
from app.core.jwt_manager import jwt_manager
from app.models import OAuthClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DelegationServicePrincipal:
    """A verified service token. `client_id` is the opaque `jnc_...` id."""

    client_id: str


def looks_like_jwt(token: Optional[str]) -> bool:
    return bool(token) and token.count(".") == 2


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(status_code=401, detail=reason)


def _forbidden(reason: str) -> HTTPException:
    return HTTPException(status_code=403, detail=reason)


def verify_delegation_service_token(token: str) -> DelegationServicePrincipal:
    """Verify signature, issuer, audience, expiry, token shape and scope."""
    if jwt_manager.algorithm != "RS256":
        # A symmetric key would let anything holding the HS secret mint
        # service identities. This boundary is RS256-only, including in tests.
        raise _unauthorized("service_token_requires_rs256")
    payload = jwt_manager.verify_token(token, audience=CONNECTIONS_AUDIENCE)
    if not payload:
        raise _unauthorized("invalid_service_token")

    client_id = payload.get("client_id")
    issued, expires = payload.get("iat"), payload.get("exp")
    now = time()
    if (
        payload.get("aud") != CONNECTIONS_AUDIENCE
        or payload.get("token_use") != "client_credentials"
        or payload.get("actor_type") != "service_account"
        or not isinstance(client_id, str)
        or not client_id
        or payload.get("sub") != f"service-account:{client_id}"
        or type(issued) not in (int, float)
        or type(expires) not in (int, float)
        or not 0 < expires - issued <= 3600
        or expires <= now
        or issued > now + 60
    ):
        raise _unauthorized("invalid_service_token")

    scope = payload.get("scope")
    if not isinstance(scope, str) or CONNECTIONS_DELEGATE_SCOPE not in scope.split():
        raise _forbidden("service_token_missing_scope")

    return DelegationServicePrincipal(client_id=client_id)


async def current_delegation_client(
    db: AsyncSession, principal: DelegationServicePrincipal
) -> OAuthClient:
    """Re-check the client's live grant; a revoked grant beats a live token."""
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
        or client.audience != CONNECTIONS_AUDIENCE
        or CONNECTIONS_DELEGATE_SCOPE not in (client.allowed_scopes or [])
        or "client_credentials" not in (client.grant_types or [])
    ):
        raise _forbidden("service_client_grant_unavailable")
    return client


def require_purpose_for_client(client: OAuthClient, purpose_id: Optional[str]) -> ConsentPurpose:
    """The purpose must be registered and allowlist this client (by name)."""
    purpose = get_purpose(purpose_id)
    if purpose is None:
        logger.warning("Service client %s refused: unknown_purpose %r", client.name, purpose_id)
        raise _forbidden("unknown_purpose")
    if client.name not in purpose.allowed_service_clients:
        logger.warning(
            "Service client %s refused: not allowed for purpose %s", client.name, purpose.id
        )
        raise _forbidden("service_client_not_allowed_for_purpose")
    return purpose


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


__all__ = [
    "DelegationServicePrincipal",
    "bearer_token",
    "require_purpose_for_client",
    "current_delegation_client",
    "looks_like_jwt",
    "verify_delegation_service_token",
]
