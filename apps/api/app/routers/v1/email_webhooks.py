"""Public receiver for Resend webhooks: POST /api/v1/email/webhooks/resend/{cuenta}.

Resend calls this with no cookie, session or bearer token; the Svix signature
IS the authentication, so nothing here reads a request identity and nothing is
written before the signature verifies. `{cuenta}` names the Resend ACCOUNT the
webhook belongs to (`ctm`, `platform`), because each account signs with its own
secret. See app/services/email_events.py for the scheme and what is stored.

Status codes, and what Resend does with them (it retries any non-2xx):

    404  unknown account, OR a known account whose secret is not configured.
         Same body for both, so the endpoint does not reveal which accounts exist.
    413  body larger than 1 MiB (a real event is a few hundred bytes).
    401  missing/malformed svix headers, stale timestamp, or bad signature.
         Same body for all of them.
    200  stored; OR a redelivery of a stored svix-id; OR a verified event of a
         type we do not store; OR a verified but malformed event (logged as an
         error so it is visible, acknowledged so Resend stops retrying a
         payload that will never parse).

No middleware in the stack blocks this route: there is no CSRF middleware,
ApiKeyAuthMiddleware only acts on X-API-Key / `Bearer sk_live_*`, TenantMiddleware
only reads optional tenant hints, and main.py's input-validation and global
rate-limit factories construct their middleware without registering it.
"""

import json
from typing import List

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.email_events import (
    MalformedEvent,
    WebhookVerificationError,
    parse_event,
    record_event,
    secret_for,
    verify_signature,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/email/webhooks", tags=["email"])

MAX_BODY_BYTES = 1024 * 1024

_NOT_FOUND = {"detail": "Not found"}
_UNAUTHORIZED = {"detail": "Invalid webhook signature"}


@router.post("/resend/{cuenta}", include_in_schema=False)
async def receive_resend_webhook(
    cuenta: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    secret = secret_for(cuenta)
    if secret is None:
        return JSONResponse(status_code=404, content=_NOT_FOUND)

    # Read with a cap instead of buffering whatever arrives: the route is public.
    chunks: List[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Payload too large"})
        chunks.append(chunk)
    body = b"".join(chunks)

    svix_id = request.headers.get("svix-id")
    try:
        verify_signature(
            secret,
            svix_id,
            request.headers.get("svix-timestamp"),
            request.headers.get("svix-signature"),
            body,
        )
    except WebhookVerificationError as exc:
        # The reason is safe to log (no secret, no body); the caller gets one
        # undifferentiated answer.
        logger.warning("email_webhook.rejected", cuenta=cuenta, reason=str(exc))
        return JSONResponse(status_code=401, content=_UNAUTHORIZED)
    if not svix_id:  # unreachable: verify_signature refuses a missing id
        return JSONResponse(status_code=401, content=_UNAUTHORIZED)

    try:
        event = parse_event(json.loads(body))
    except (ValueError, MalformedEvent) as exc:
        logger.error(
            "email_webhook.malformed_event",
            cuenta=cuenta,
            svix_id=svix_id,
            error_type=type(exc).__name__,
        )
        return JSONResponse(status_code=200, content={"status": "ignored"})

    if event is None:
        return JSONResponse(status_code=200, content={"status": "ignored"})

    stored = await record_event(db, cuenta, svix_id, event)
    logger.info(
        "email_webhook.event",
        cuenta=cuenta,
        event_type=event.event_type,
        email_id=event.email_id,
        source_app=event.source_app,
        duplicate=not stored,
    )
    return JSONResponse(status_code=200, content={"status": "stored" if stored else "duplicate"})
