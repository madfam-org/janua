"""Coupler connections API — ConnectedAccount vault and token delegation."""

from __future__ import annotations

import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.consent_purposes import get_purpose
from app.database import get_db
from app.dependencies import get_current_user
from app.models import ActivityLog, User
from app.models.connected_account import ConnectedAccountStatus
from app.services.connected_account_service import (
    ConnectedAccountService,
    ProviderTemporarilyUnavailable,
    ReauthorizationRequired,
    has_active_purpose_grant,
)
from app.services.connections_service_auth import (
    DelegationServicePrincipal,
    current_delegation_client,
    looks_like_jwt,
    verify_delegation_service_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["Connections"])


class ConnectionSummary(BaseModel):
    id: str
    provider_type: str
    provider_name: str
    provider_id: Optional[str] = None
    scopes: list[str] = Field(default_factory=list)
    status: str
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionSummary]
    count: int


class TokenDelegationRequest(BaseModel):
    purpose: str = "tool_execute"
    ttl_seconds: int = Field(default=300, ge=60, le=900)


class TokenDelegationResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: str
    purpose: str
    provider_type: str
    scopes: list[str] = Field(default_factory=list)


#: Providers the legacy static-token (ATP) caller may receive tokens for.
#: Anything else — today, Google — is delegable only for a registered purpose
#: to a Janua service token (see `app/core/consent_purposes.py`).
_LEGACY_STATIC_PROVIDERS = frozenset({"github", "slack"})


@dataclass(frozen=True)
class _DelegationCaller:
    kind: str  # "static" (legacy ATP shared secret) | "service" (RS256 client_credentials)
    service: Optional[DelegationServicePrincipal] = None


def _static_token_matches(candidate: Optional[str], expected: str) -> bool:
    return (
        bool(candidate)
        and bool(expected)
        and hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
    )


def _resolve_delegation_caller(
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    authorization: Optional[str] = Header(None),
) -> _DelegationCaller:
    """Authenticate the caller of the delegation endpoint.

    Two accepted credentials:

    - the legacy static `JANUA_SERVICE_TOKEN` (Coupler/ATP), via
      `X-Service-Token` or `Authorization: Bearer`. Unchanged: when the static
      token is not configured and no service JWT is presented, the endpoint
      answers 404 exactly as before;
    - a Janua RS256 `client_credentials` token (audience `janua-connections`,
      scope `connections:delegate`) via `Authorization: Bearer`.
    """
    expected = getattr(settings, "JANUA_SERVICE_TOKEN", None) or ""
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()

    if x_service_token is not None:
        if _static_token_matches(x_service_token, expected):
            return _DelegationCaller(kind="static")
        if not expected and not bearer:
            raise HTTPException(status_code=404, detail="not found")
        if not bearer:
            raise HTTPException(status_code=401, detail="invalid_service_credentials")

    if bearer:
        if _static_token_matches(bearer, expected):
            return _DelegationCaller(kind="static")
        if looks_like_jwt(bearer):
            return _DelegationCaller(
                kind="service", service=verify_delegation_service_token(bearer)
            )

    if not expected:
        raise HTTPException(status_code=404, detail="not found")
    raise HTTPException(status_code=401, detail="invalid_service_credentials")


def _to_summary(conn) -> ConnectionSummary:
    return ConnectionSummary(
        id=str(conn.id),
        provider_type=conn.provider_type,
        provider_name=conn.provider_name,
        provider_id=conn.provider_id,
        scopes=list(conn.oauth_scopes or []),
        status=conn.status,
        expires_at=conn.oauth_expires_at,
        last_used_at=conn.last_used_at,
        created_at=conn.created_at,
    )


@router.get("", response_model=ConnectionListResponse)
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List delegated SaaS connections for the authenticated user (no secrets)."""
    svc = ConnectedAccountService(db)
    connections = await svc.list_for_user(current_user, sync_oauth=True)
    summaries = [_to_summary(c) for c in connections]
    return ConnectionListResponse(connections=summaries, count=len(summaries))


@router.delete("/{connection_id}")
async def revoke_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ConnectedAccountService(db)
    try:
        cid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_connection_id")
    ended_purposes = await svc.revoke(current_user, cid)
    if ended_purposes is None:
        raise HTTPException(status_code=404, detail="connection_not_found")
    activity = ActivityLog(
        user_id=current_user.id,
        action="connection.revoked",
        resource_type="connected_account",
        resource_id=connection_id,
        activity_metadata={"source": "user", "purposes_ended": ended_purposes},
    )
    db.add(activity)
    for purpose_id in ended_purposes:
        db.add(
            ActivityLog(
                user_id=current_user.id,
                action="consent.purpose.revoked",
                resource_type="connected_account",
                resource_id=connection_id,
                activity_metadata={"purpose": purpose_id, "reason": "connection_revoked"},
            )
        )
    await db.commit()
    return {"revoked": True, "id": connection_id, "purposes_ended": ended_purposes}


@router.post("/{connection_id}/token", response_model=TokenDelegationResponse)
async def delegate_connection_token(
    connection_id: str,
    body: TokenDelegationRequest,
    db: AsyncSession = Depends(get_db),
    x_acting_user_id: str = Header(..., alias="X-Acting-User-Id"),
    caller: _DelegationCaller = Depends(_resolve_delegation_caller),
):
    """Issue a short-lived provider access token for a delegated call.

    Legacy static-token callers (Coupler tool execute) keep their exact
    behaviour for GitHub/Slack. Registered purposes (e.g. a creator's YouTube
    read consent) are delegable only to an allowlisted Janua service client
    holding `connections:delegate`, only when the acting user granted that
    purpose on that connection, and only with a fresh provider token.
    """
    try:
        cid = uuid.UUID(connection_id)
        acting_uid = uuid.UUID(x_acting_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_id")

    if caller.kind == "service":
        return await _delegate_for_purpose(db, caller, cid, acting_uid, body)

    # ---- legacy static-token path (unchanged for GitHub/Slack) -----------------
    if get_purpose(body.purpose) is not None:
        raise HTTPException(status_code=403, detail="purpose_requires_service_token")

    svc = ConnectedAccountService(db)
    connection = await svc.get_by_id(cid)
    if not connection:
        raise HTTPException(status_code=404, detail="connection_not_found")
    if connection.provider_type not in _LEGACY_STATIC_PROVIDERS:
        raise HTTPException(status_code=403, detail="provider_requires_service_token")

    try:
        payload = await svc.delegate_token(
            connection,
            acting_user_id=acting_uid,
            purpose=body.purpose,
            ttl_seconds=body.ttl_seconds,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="acting_user_mismatch")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    activity = ActivityLog(
        user_id=acting_uid,
        action="tool.delegation.issued",
        resource_type="connected_account",
        resource_id=connection_id,
        activity_metadata={
            "purpose": body.purpose,
            "provider_type": connection.provider_type,
            "ttl_seconds": body.ttl_seconds,
            "caller": "static_service_token",
        },
    )
    db.add(activity)
    await db.commit()

    return TokenDelegationResponse(**payload)


def _refuse(status_code: int, reason: str, **context) -> HTTPException:
    logger.warning("Connection delegation refused: %s %s", reason, context)
    return HTTPException(status_code=status_code, detail=reason)


async def _delegate_for_purpose(
    db: AsyncSession,
    caller: _DelegationCaller,
    connection_id: uuid.UUID,
    acting_user_id: uuid.UUID,
    body: TokenDelegationRequest,
) -> TokenDelegationResponse:
    """Service-token path: every rule fails closed with a specific reason."""
    if caller.service is None:  # defensive: the resolver never builds this
        raise _refuse(401, "invalid_service_token")
    client = await current_delegation_client(db, caller.service)

    purpose = get_purpose(body.purpose)
    if purpose is None:
        raise _refuse(403, "unknown_purpose", client=client.name, purpose=body.purpose)
    if client.name not in purpose.allowed_service_clients:
        raise _refuse(
            403, "service_client_not_allowed_for_purpose", client=client.name, purpose=purpose.id
        )

    svc = ConnectedAccountService(db)
    connection = await svc.get_by_id_any_status(connection_id)
    if connection is None:
        raise _refuse(404, "connection_not_found", client=client.name)
    if connection.user_id != acting_user_id:
        raise _refuse(403, "acting_user_mismatch", client=client.name)
    if connection.status == ConnectedAccountStatus.REVOKED.value:
        raise _refuse(403, "connection_revoked", client=client.name, purpose=purpose.id)
    if connection.status == ConnectedAccountStatus.EXPIRED.value:
        raise _refuse(409, "reauthorization_required", client=client.name, purpose=purpose.id)
    if connection.status != ConnectedAccountStatus.ACTIVE.value:
        raise _refuse(403, "connection_not_active", client=client.name)
    if connection.provider_type != purpose.provider:
        raise _refuse(403, "purpose_provider_mismatch", client=client.name, purpose=purpose.id)
    if not has_active_purpose_grant(connection, purpose):
        raise _refuse(403, "purpose_not_granted", client=client.name, purpose=purpose.id)

    try:
        await svc.ensure_fresh_access_token(connection)
    except ReauthorizationRequired:
        raise _refuse(409, "reauthorization_required", client=client.name, purpose=purpose.id)
    except ProviderTemporarilyUnavailable:
        raise _refuse(503, "provider_refresh_unavailable", client=client.name, purpose=purpose.id)

    # A refresh may report a narrower grant (the user removed access at the
    # provider). Re-check before handing anything out.
    if not has_active_purpose_grant(connection, purpose):
        raise _refuse(409, "reauthorization_required", client=client.name, purpose=purpose.id)

    try:
        payload = await svc.delegate_token(
            connection,
            acting_user_id=acting_user_id,
            purpose=purpose.id,
            ttl_seconds=body.ttl_seconds,
        )
    except PermissionError:
        raise _refuse(403, "acting_user_mismatch", client=client.name)
    except ValueError as e:
        raise _refuse(409, "reauthorization_required", client=client.name, cause=str(e))

    db.add(
        ActivityLog(
            user_id=acting_user_id,
            action="tool.delegation.issued",
            resource_type="connected_account",
            resource_id=str(connection_id),
            activity_metadata={
                "purpose": purpose.id,
                "provider_type": connection.provider_type,
                "ttl_seconds": body.ttl_seconds,
                "caller": "service_client",
                "service_client": client.name,
                "service_client_id": client.client_id,
            },
        )
    )
    await db.commit()
    return TokenDelegationResponse(**payload)


@router.post("/sync/{provider}")
async def sync_provider_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly sync a provider connection from linked OAuthAccount."""
    if provider not in ("github", "slack", "google"):
        raise HTTPException(status_code=400, detail="unsupported_provider")
    svc = ConnectedAccountService(db)
    await svc.list_for_user(current_user, sync_oauth=True)
    connections = await svc.list_for_user(current_user, sync_oauth=False)
    matched = [c for c in connections if c.provider_type == provider]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"No {provider} connection. Link {provider} via OAuth first.",
        )
    return {"synced": True, "connection": _to_summary(matched[0])}
