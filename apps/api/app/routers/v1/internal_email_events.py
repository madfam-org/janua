"""Per-app email events feed: GET /api/v1/internal/email/events.

THE CONTRACT (sending apps code against this; keep it exact):

    GET /api/v1/internal/email/events?source_app=<app>&after=<cursor>&limit=<1..500>
    Header: X-Internal-API-Key (same dependency as /internal/email/send)

    200 {
      "events": [
        {
          "cursor": 1234,                      # int, strictly increasing
          "provider": "resend",
          "email_id": "4ef9a417-...",          # == message_id Janua returned on send
          "type": "delivered",                 # sent | delivered | delivery_delayed |
                                               # bounced | complained | opened |
                                               # clicked | suppressed
          "occurred_at": "2026-09-23T15:04:05.123000Z",
          "bounce_type": "Permanent",          # only on bounced / suppressed
          "bounce_subtype": "Suppressed",      # only on bounced / suppressed
          "click_link": "https://map.creatumundo.mx/agenda",  # only on clicked
          "source": "first_party",             # only on events Janua measured itself
          "possible_prefetch": true            # only on first-party hits that looked automatic
        }
      ],
      "next_cursor": 1234                      # pass back as `after`
    }

- `source_app` is required and exact (the `source_app` the app sent with).
- `after` defaults to 0 (from the beginning); `limit` defaults to 100.
- Ordered by `cursor` ascending. `next_cursor` is the last cursor on the page,
  or the request's `after` when the page is empty, so a poller can always
  store it and send it back.
- Optional keys are OMITTED, never null.
- Events become visible ~5 s after Janua receives them (see
  `email_events.list_events` for why).
- No recipient, subject, IP or user agent is ever returned: they are never
  stored. The app joins `email_id` to the message it recorded on send.
- First-party events (opens/clicks measured on Janua's own tracking host for
  messages sent with `track_engagement: true`) arrive in the SAME feed with the
  SAME shape, types `opened` / `clicked`, plus `source: "first_party"`. Deduped:
  one open per message and one click per link (and, separately, the first hit
  that looked like a prefetch/scanner, flagged `possible_prefetch: true`).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.services.email_events import feed_page, list_events

router = APIRouter(prefix="/email", tags=["email"])

MAX_LIMIT = 500


class EmailEventItem(BaseModel):
    cursor: int
    provider: str
    email_id: str
    type: str
    occurred_at: datetime
    bounce_type: Optional[str] = None
    bounce_subtype: Optional[str] = None
    click_link: Optional[str] = None
    source: Optional[str] = None
    possible_prefetch: Optional[bool] = None


class EmailEventsPage(BaseModel):
    events: List[EmailEventItem]
    next_cursor: int


@router.get("/events", response_model=EmailEventsPage, response_model_exclude_none=True)
async def email_events_feed(
    source_app: str = Query(..., min_length=1, max_length=64),
    after: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=MAX_LIMIT),
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    rows = await list_events(db, source_app=source_app, after=after, limit=limit)
    return feed_page(list(rows), after)
