"""Public first-party tracking endpoints: the open pixel and the click redirect.

    GET|HEAD /e/o/{token}.gif      -> 200, the same 1x1 GIF, always
    GET|HEAD /e/c/{token}/{index}  -> 302 to the STORED target, or to the
                                      host's default site when unresolvable

Mounted at the root (no /api prefix) and served on the tenant's tracking host
(`CTM_TRACKING_HOST`, e.g. enlaces.creatumundo.mx) routed to janua-api. No auth,
no session, no cookies, not in the OpenAPI schema. See
app/services/email_engagement.py for the rules and what is stored.

THE GUARANTEES, and where each one lives:

- Constant answers. The pixel returns the same bytes and headers for every
  token, valid or not, and even if the database fails. The click redirect for
  an unknown token, a bad index or a database failure is the SAME fallback,
  chosen from the request Host alone (`fallback_site`), so nothing in the
  response says whether a token exists.
- No open redirect. The Location of a click is only ever a target read from
  `email_tracking_links` by (token hash, index), and only http(s); nothing in
  the request can name where it goes. Path parameters are plain strings
  validated here, so a malformed index is the fallback, not a 422.
- No write for unknown input. A token that does not match the format never
  reaches the database; one that matches but is unknown is a single read.
- Minimal events. No IP, no user agent: the request is read in memory only
  to set `possible_prefetch`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.email_engagement import (
    PIXEL_GIF,
    fallback_site,
    find_link,
    possible_prefetch,
    record_hit,
    stored_target,
)

logger = structlog.get_logger()

router = APIRouter(tags=["email-engagement"], include_in_schema=False)

NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, private",
    "Pragma": "no-cache",
    "X-Robots-Tag": "noindex, nofollow",
}


def _prefetch(request: Request, created_at: Optional[datetime]) -> bool:
    seconds = (datetime.utcnow() - created_at).total_seconds() if created_at else None
    return possible_prefetch(
        method=request.method,
        user_agent=request.headers.get("user-agent"),
        purpose=request.headers.get("sec-purpose") or request.headers.get("purpose"),
        seconds_since_send=seconds,
    )


@router.api_route("/e/o/{token}.gif", methods=["GET", "HEAD"])
async def engagement_open(
    token: str, request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    try:
        link = await find_link(db, token)
        if link is not None:
            await record_hit(
                db,
                link,
                kind="o",
                index=None,
                prefetch=_prefetch(request, link.created_at),  # type: ignore[arg-type]
            )
    except Exception as exc:  # the pixel is the same no matter what
        logger.error("email.engagement_open_failed", error_type=type(exc).__name__)
    return Response(content=PIXEL_GIF, media_type="image/gif", headers=dict(NO_STORE_HEADERS))


@router.api_route("/e/c/{token}/{index}", methods=["GET", "HEAD"])
async def engagement_click(
    token: str, index: str, request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    target: Optional[str] = None
    try:
        link = await find_link(db, token)
        target = stored_target(link, index) if link is not None else None
        if link is not None and target is not None:
            try:
                await record_hit(
                    db,
                    link,
                    kind="c",
                    index=int(index),
                    prefetch=_prefetch(request, link.created_at),  # type: ignore[arg-type]
                    target=target,
                )
            except Exception as exc:  # measuring failed; the reader still gets there
                logger.error("email.engagement_click_record_failed", error_type=type(exc).__name__)
    except Exception as exc:
        logger.error("email.engagement_click_lookup_failed", error_type=type(exc).__name__)
        target = None
    location = target or fallback_site(request.headers.get("host"))
    return RedirectResponse(location, status_code=302, headers=dict(NO_STORE_HEADERS))
