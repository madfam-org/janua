"""Per-account email quota usage: GET /api/v1/internal/email/usage.

THE CONTRACT (crea-map codes against this; keep it exact):

    GET /api/v1/internal/email/usage?org_id=<uuid>&days=<1..31>
    Header: X-Internal-API-Key (same dependency as /internal/email/send)

    200 {
      "cuenta": "ctm",                       # the Resend account the org sends on
      "window": "utc_day",                   # Resend's daily quota window
      "as_of": "2026-09-28T23:40:00Z",
      "today": 37,                           # accepted since 00:00 UTC today
      "month": 412,                          # accepted since the 1st, 00:00 UTC
      "days": [                              # `days` entries, oldest first, today last
        {"date": "2026-09-15", "sent": 12}
      ]
    }

    404  the org does not send on an account of its own (no binding, or it
         sends on MADFAM's shared account), OR that account's webhook is not
         configured, so there are no events to count. Callers fall back to
         their own ledger. Same body for both.

Read-only, counts only: no recipient, subject, message id or app is returned.
What is counted, and its limits, is in app/services/email_usage.py.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.services.email_usage import (
    MAX_DAYS,
    account_for_org,
    usage_for_account,
    webhook_configured,
)

router = APIRouter(prefix="/email", tags=["email"])


class EmailUsageDay(BaseModel):
    date: str
    sent: int


class EmailUsage(BaseModel):
    cuenta: str
    window: str
    as_of: datetime
    today: int
    month: int
    days: List[EmailUsageDay]


_NOT_AVAILABLE = "No usage available for this organization"


@router.get("/usage", response_model=EmailUsage)
async def email_usage(
    org_id: str = Query(..., min_length=1, max_length=64),
    days: int = Query(14, ge=1, le=MAX_DAYS),
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    cuenta = account_for_org(org_id)
    if cuenta is None or not webhook_configured(cuenta):
        raise HTTPException(status_code=404, detail=_NOT_AVAILABLE)
    usage = await usage_for_account(db, cuenta, days)
    body = usage.as_dict()
    body["as_of"] = usage.as_of.replace(tzinfo=timezone.utc)
    return body
