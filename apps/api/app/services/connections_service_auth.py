"""Token verification for purpose-scoped provider-token delegation.

Two kinds of credential meet here:

- the **actor**: a Janua-issued RS256 `client_credentials` service token
  (audience `janua-connections`, scope `connections:delegate`). The purpose
  registry then decides which path the client may use: user-bound token
  exchange (`exchange_clients`) or user-absent offline delegation
  (`offline_clients`). After the signature
  checks, the client's *current* registration is re-read, so a client that was
  deactivated or lost the scope is refused while its token is still unexpired;
- the **subject**: the user's OWN Janua RS256 access token, issued to the
  service's user-facing API (an audience the purpose registry allowlists). It
  binds a delegation to a request the user is actually making, so a service
  that holds only its own credential cannot borrow tokens for absent users.

Every refusal names its reason. Nothing here falls back to HS256, an omitted
audience, or the legacy static token.
"""

from __future__ import annotations

import logging
import uuid
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
from app.models import OAuthClient, User, UserStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DelegationServicePrincipal:
    """A verified service token. `client_id` is the opaque `jnc_...` id."""

    client_id: str


@dataclass(frozen=True)
class SubjectPrincipal:
    """A verified user access token presented as a token-exchange subject."""

    user: User
    audience: str
    jti: Optional[str]


def looks_like_jwt(token: Optional[str]) -> bool:
    return bool(token) and token.count(".") == 2


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(status_code=401, detail=reason)


def _forbidden(reason: str) -> HTTPException:
    return HTTPException(status_code=403, detail=reason)


def _require_rs256() -> None:
    if jwt_manager.algorithm != "RS256":
        # A symmetric key would let anything holding the HS secret mint
        # identities. This boundary is RS256-only, including in tests.
        raise _unauthorized("service_token_requires_rs256")


def _lifetime_ok(payload: dict) -> bool:
    issued, expires = payload.get("iat"), payload.get("exp")
    now = time()
    return (
        type(issued) in (int, float)
        and type(expires) in (int, float)
        and expires > now
        and issued <= now + 60
        and expires > issued
    )


def verify_delegation_service_token(
    token: Optional[str], required_scope: str = CONNECTIONS_DELEGATE_SCOPE
) -> DelegationServicePrincipal:
    """Verify an actor token: signature, issuer, audience, expiry, shape, scope."""
    _require_rs256()
    if not looks_like_jwt(token):
        raise _unauthorized("invalid_service_token")
    payload = jwt_manager.verify_token(token, audience=CONNECTIONS_AUDIENCE)
    if not payload:
        raise _unauthorized("invalid_service_token")

    client_id = payload.get("client_id")
    if (
        payload.get("aud") != CONNECTIONS_AUDIENCE
        or payload.get("token_use") != "client_credentials"
        or payload.get("actor_type") != "service_account"
        or not isinstance(client_id, str)
        or not client_id
        or payload.get("sub") != f"service-account:{client_id}"
        or not _lifetime_ok(payload)
        or payload["exp"] - payload["iat"] > 3600
    ):
        raise _unauthorized("invalid_service_token")

    scope = payload.get("scope")
    if not isinstance(scope, str) or required_scope not in scope.split():
        raise _forbidden("service_token_missing_scope")

    return DelegationServicePrincipal(client_id=client_id)


async def current_service_client(
    db: AsyncSession,
    principal: DelegationServicePrincipal,
    required_scope: str = CONNECTIONS_DELEGATE_SCOPE,
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
        or required_scope not in (client.allowed_scopes or [])
        or "client_credentials" not in (client.grant_types or [])
    ):
        raise _forbidden("service_client_grant_unavailable")
    return client


# Backwards-compatible name for the delegate scope check.
async def current_delegation_client(
    db: AsyncSession, principal: DelegationServicePrincipal
) -> OAuthClient:
    return await current_service_client(db, principal, CONNECTIONS_DELEGATE_SCOPE)


def require_purpose(purpose_id: Optional[str]) -> ConsentPurpose:
    purpose = get_purpose(purpose_id)
    if purpose is None:
        logger.warning("Connections request refused: unknown_purpose %r", purpose_id)
        raise _forbidden("unknown_purpose")
    return purpose


def require_exchange_client(client: OAuthClient, purpose_id: Optional[str]) -> ConsentPurpose:
    """Registered purpose whose `exchange_clients` names this client."""
    purpose = require_purpose(purpose_id)
    if client.name not in purpose.exchange_clients:
        logger.warning("Client %s refused token exchange for purpose %s", client.name, purpose.id)
        raise _forbidden("client_not_permitted")
    return purpose


def require_offline_client(client: OAuthClient, purpose: ConsentPurpose) -> None:
    """Header-only (user-absent) delegation is for `offline_clients` only."""
    if client.name not in purpose.offline_clients:
        logger.warning(
            "Client %s refused offline delegation for purpose %s", client.name, purpose.id
        )
        raise _forbidden("user_binding_required")


async def verify_subject_token(
    db: AsyncSession, token: Optional[str], purpose: ConsentPurpose
) -> SubjectPrincipal:
    """Verify the user's own access token presented as the exchange subject.

    Accepts only an RS256 Janua access token for a real, active person whose
    audience the purpose allowlists. Every refusal uses ONE reason,
    ``invalid_subject_token`` (a wire contract consumers branch on): 401 when
    the token itself does not verify (malformed, signature, issuer, expiry,
    audience outside the allowlist, bad ``sub``), 403 when it verifies but
    names no eligible person (a service token, a service principal, an
    inactive user). The log line carries the precise cause.
    """
    _require_rs256()
    if not looks_like_jwt(token):
        raise _unauthorized("invalid_subject_token")
    allowed = sorted(purpose.allowed_subject_audiences)
    if not allowed:
        logger.warning("Subject refused: purpose %s allowlists no audience", purpose.id)
        raise _forbidden("invalid_subject_token")
    payload = jwt_manager.verify_token(token, token_type="access", audience=allowed)
    if not payload or not _lifetime_ok(payload):
        # Signature, issuer, expiry, type — or an audience outside the allowlist.
        raise _unauthorized("invalid_subject_token")

    audiences = payload.get("aud")
    audience_list = audiences if isinstance(audiences, list) else [audiences]
    matched = [a for a in audience_list if a in purpose.allowed_subject_audiences]
    if not matched:
        logger.warning("Subject refused: audience %r not allowlisted", audiences)
        raise _unauthorized("invalid_subject_token")

    if (
        payload.get("token_use") == "client_credentials"
        or payload.get("actor_type") == "service_account"
        or payload.get("is_service_account") is True
        or str(payload.get("sub", "")).startswith("service-account:")
    ):
        logger.warning("Subject refused: service token presented as subject")
        raise _forbidden("invalid_subject_token")

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError:
        raise _unauthorized("invalid_subject_token")

    result = await db.execute(
        select(User).where(User.id == user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    if user is None or getattr(user, "is_service_account", False):
        logger.warning("Subject refused: user %s inactive or a service principal", user_id)
        raise _forbidden("invalid_subject_token")

    return SubjectPrincipal(user=user, audience=matched[0], jti=payload.get("jti"))


__all__ = [
    "DelegationServicePrincipal",
    "SubjectPrincipal",
    "bearer_token",
    "current_delegation_client",
    "current_service_client",
    "looks_like_jwt",
    "require_purpose",
    "require_exchange_client",
    "require_offline_client",
    "verify_delegation_service_token",
    "verify_subject_token",
]
