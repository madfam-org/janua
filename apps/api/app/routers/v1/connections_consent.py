"""User-bound token exchange for registered consent purposes, and the
provider-token issuance shared with the offline delegation path.

`POST /connections/token-exchange` (RFC 8693 shape): a service trades the
user's OWN access token (subject) plus its service token (actor) for a
short-lived provider token. Janua picks the user's connection itself.

Why user-bound: a service holding only `connections:delegate` and asserting
a user id could borrow every consenting user's provider token (a confused
deputy). Requiring the user's own token limits the service's API pod to the
users whose requests it is handling right now, for as long as those user
tokens live. User-absent re-verification uses the separate offline path
(`POST /connections/{id}/token`), open only to the purpose's
`offline_clients`. See docs/service-tokens.md, "Purpose-scoped provider consent".
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.consent_purposes import (
    CONNECTIONS_DELEGATE_SCOPE,
    PURPOSE_STATUS_GRANTED,
    ConsentPurpose,
)
from app.database import get_db
from app.models import ActivityLog, OAuthClient
from app.models.connected_account import ConnectedAccount, ConnectedAccountStatus
from app.services.connected_account_service import (
    ConnectedAccountService,
    ProviderTemporarilyUnavailable,
    ReauthorizationRequired,
    has_active_purpose_grant,
    purpose_grants,
)
from app.services.connections_service_auth import (
    SubjectPrincipal,
    current_service_client,
    require_exchange_client,
    verify_delegation_service_token,
    verify_subject_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["Connections"])

TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


class TokenExchangeResponse(BaseModel):
    access_token: str
    issued_token_type: str = ACCESS_TOKEN_TYPE
    token_type: str = "Bearer"
    expires_in: int
    expires_at: str
    scope: str
    purpose: str
    provider_type: str
    connection_id: str


def _refuse(status_code: int, reason: str, **context) -> HTTPException:
    logger.warning("Connections consent request refused: %s %s", reason, context)
    return HTTPException(status_code=status_code, detail=reason)


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _pick_connection(
    connections: list[ConnectedAccount], purpose: ConsentPurpose
) -> Optional[ConnectedAccount]:
    """The most recently updated ACTIVE connection holding the purpose grant."""
    active = [
        c
        for c in connections
        if c.status == ConnectedAccountStatus.ACTIVE.value and has_active_purpose_grant(c, purpose)
    ]
    active.sort(key=lambda c: c.updated_at or c.created_at or datetime.min, reverse=True)
    return active[0] if active else None


def _grant_status(conn: ConnectedAccount, purpose: ConsentPurpose) -> Optional[str]:
    grant = purpose_grants(conn).get(purpose.id)
    return grant.get("status") if isinstance(grant, dict) else None


async def issue_purpose_token(
    db: AsyncSession,
    connection: ConnectedAccount,
    purpose: ConsentPurpose,
    *,
    user_id: uuid.UUID,
    client: OAuthClient,
    path: str,
    ttl_seconds: int,
    subject: Optional[SubjectPrincipal] = None,
) -> dict:
    """Freshen, re-check and hand out a provider token; audit both identities.

    Shared by the exchange (`path="exchange"`) and offline (`path="offline"`)
    paths. The caller has already authorized the client, the user and the
    connection's grant.
    """
    svc = ConnectedAccountService(db)
    try:
        await svc.ensure_fresh_access_token(connection)
    except ReauthorizationRequired:
        raise _refuse(409, "reauthorization_required", client=client.name, user=str(user_id))
    except ProviderTemporarilyUnavailable:
        raise _refuse(503, "provider_refresh_unavailable", client=client.name)

    # A refresh may report a narrower grant (access removed at the provider).
    if not has_active_purpose_grant(connection, purpose):
        raise _refuse(409, "reauthorization_required", client=client.name, user=str(user_id))

    try:
        payload = await svc.delegate_token(
            connection, acting_user_id=user_id, purpose=purpose.id, ttl_seconds=ttl_seconds
        )
    except PermissionError:
        raise _refuse(403, "acting_user_mismatch", client=client.name)
    except ValueError as e:
        raise _refuse(409, "reauthorization_required", client=client.name, cause=str(e))

    metadata = {
        "purpose": purpose.id,
        "path": path,
        "provider_type": connection.provider_type,
        "ttl_seconds": ttl_seconds,
        "actor_client": client.name,
        "actor_client_id": client.client_id,
        "subject_user_id": str(user_id),
    }
    if subject is not None:
        metadata["subject_audience"] = subject.audience
        metadata["subject_jti"] = subject.jti
    db.add(
        ActivityLog(
            user_id=user_id,
            action="tool.delegation.issued",
            resource_type="connected_account",
            resource_id=str(connection.id),
            activity_metadata=metadata,
        )
    )
    await db.commit()
    return payload


@router.post("/token-exchange", response_model=TokenExchangeResponse)
async def exchange_for_provider_token(
    grant_type: str = Form(...),
    subject_token: str = Form(...),
    subject_token_type: str = Form(...),
    actor_token: str = Form(...),
    actor_token_type: str = Form(...),
    purpose: str = Form(...),
    ttl_seconds: int = Form(300, ge=60, le=900),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a user's access token + a service's token for a provider token.

    Form-encoded, RFC 8693 shape. Every rule fails closed with a reason.
    """
    if grant_type != TOKEN_EXCHANGE_GRANT:
        raise _refuse(400, "unsupported_grant_type")
    if subject_token_type != ACCESS_TOKEN_TYPE or actor_token_type != ACCESS_TOKEN_TYPE:
        raise _refuse(400, "unsupported_token_type")

    # Actor: the service, with a live grant for this purpose.
    actor = verify_delegation_service_token(actor_token, CONNECTIONS_DELEGATE_SCOPE)
    client = await current_service_client(db, actor, CONNECTIONS_DELEGATE_SCOPE)
    consent_purpose = require_exchange_client(client, purpose)

    # Subject: the user, via their own token for an allowlisted audience.
    subject = await verify_subject_token(db, subject_token, consent_purpose)
    user_id = subject.user.id

    candidates = await ConnectedAccountService(db).list_live_for_provider(
        user_id, consent_purpose.provider
    )
    connection = _pick_connection(candidates, consent_purpose)
    if connection is None:
        if any(
            c.status == ConnectedAccountStatus.EXPIRED.value
            and _grant_status(c, consent_purpose) == PURPOSE_STATUS_GRANTED
            for c in candidates
        ):
            raise _refuse(409, "reauthorization_required", client=client.name, user=str(user_id))
        raise _refuse(403, "purpose_not_granted", client=client.name, user=str(user_id))

    payload = await issue_purpose_token(
        db,
        connection,
        consent_purpose,
        user_id=user_id,
        client=client,
        path="exchange",
        ttl_seconds=ttl_seconds,
        subject=subject,
    )

    expires_at = datetime.fromisoformat(payload["expires_at"].rstrip("Z"))
    expires_in = max(0, int((expires_at - datetime.utcnow()).total_seconds()))
    return TokenExchangeResponse(
        access_token=payload["access_token"],
        expires_in=expires_in,
        expires_at=payload["expires_at"],
        scope=" ".join(payload["scopes"]),
        purpose=consent_purpose.id,
        provider_type=connection.provider_type,
        connection_id=str(connection.id),
    )
