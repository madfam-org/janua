"""Coupler connections API — ConnectedAccount vault and token delegation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import ActivityLog, User
from app.services.connected_account_service import ConnectedAccountService

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


def _require_atp_service(
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    authorization: Optional[str] = Header(None),
) -> None:
    expected = getattr(settings, "JANUA_SERVICE_TOKEN", None) or ""
    if not expected:
        raise HTTPException(status_code=404, detail="not found")
    candidate = x_service_token
    if not candidate and authorization and authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()
    if not candidate or candidate != expected:
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
    if not await svc.revoke(current_user, cid):
        raise HTTPException(status_code=404, detail="connection_not_found")
    activity = ActivityLog(
        user_id=current_user.id,
        action="connection.revoked",
        resource_type="connected_account",
        resource_id=connection_id,
        activity_metadata={"source": "user"},
    )
    db.add(activity)
    await db.commit()
    return {"revoked": True, "id": connection_id}


@router.post("/{connection_id}/token", response_model=TokenDelegationResponse)
async def delegate_connection_token(
    connection_id: str,
    body: TokenDelegationRequest,
    db: AsyncSession = Depends(get_db),
    x_acting_user_id: str = Header(..., alias="X-Acting-User-Id"),
    _: None = Depends(_require_atp_service),
):
    """Issue a short-lived access token for Coupler tool execute (ATP service only)."""
    svc = ConnectedAccountService(db)
    try:
        cid = uuid.UUID(connection_id)
        acting_uid = uuid.UUID(x_acting_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_id")

    connection = await svc.get_by_id(cid)
    if not connection:
        raise HTTPException(status_code=404, detail="connection_not_found")

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
        },
    )
    db.add(activity)
    await db.commit()

    return TokenDelegationResponse(**payload)


@router.post("/sync/{provider}")
async def sync_provider_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly sync a provider connection from linked OAuthAccount."""
    if provider not in ("github", "slack"):
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
