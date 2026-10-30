"""Read-only mail audit metadata; authenticated and exact organization/app scope."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.services.email_audit_query import audit_page

router = APIRouter(prefix="/email", tags=["email"])


class MailAuditRecord(BaseModel):
    audit_id: UUID
    map_audit_id: Optional[UUID] = None
    source_app: str
    provenance: str
    message_kind: str
    trigger_kind: str
    state: str
    requested_at: datetime
    attempted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    provider_message_id: Optional[str] = None
    command_id: Optional[UUID] = None
    verified_sent_at: Optional[datetime] = None
    verified_delivered_at: Optional[datetime] = None


class MailAuditSummary(BaseModel):
    total: int
    provider_accepted: int
    verified_sent: int
    verified_delivered: int
    states: dict[str, int]


class ProviderEventsInWindow(BaseModel):
    verified_sent: int
    verified_delivered: int
    events_for_older_intents: int


class MailAuditPage(BaseModel):
    org_id: UUID
    source_app: str
    records: list[MailAuditRecord]
    summary: MailAuditSummary
    provider_events_in_window: ProviderEventsInWindow
    has_more: bool
    coverage: str
    history_complete: bool
    window_applies_to: str
    from_: datetime = Field(alias="from")
    to: datetime
    observed_through: datetime


@router.get("/audit", response_model=MailAuditPage)
async def email_audit(
    org_id: UUID = Query(...),
    source_app: str = Query(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
    start: datetime = Query(..., alias="from"),
    end: datetime = Query(..., alias="to"),
    folio: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
):
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in (start, end)):
        raise HTTPException(422, "from/to must be timezone-aware UTC timestamps")
    if end <= start or end - start > timedelta(days=7):
        raise HTTPException(422, "Audit window must be positive and at most 7 days")
    result = await audit_page(
        db, org_id=org_id, source_app=source_app, start=start, end=end, folio=folio, limit=limit
    )
    # An allowlist of output fields is the privacy boundary, independent of
    # future ORM columns. Never return a raw model or a MagicLink capability.
    result["records"] = [
        MailAuditRecord.model_validate(row).model_dump(mode="json") for row in result["records"]
    ]
    return result
