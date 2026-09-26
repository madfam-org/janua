"""Resend webhook ingestion: verify, minimize, store once, serve per app.

VERIFICATION (Svix scheme, which Resend uses). Each delivery carries
`svix-id`, `svix-timestamp` and `svix-signature`. The signed content is
`"{svix_id}.{svix_timestamp}.{raw_body}"`, HMAC-SHA256 keyed with the
base64-decoded part of the endpoint's `whsec_...` secret; the signature header
holds space-separated `v1,<base64>` entries, any one of which may match (Svix
sends several during a secret rotation). Stdlib only: `hmac`, `hashlib`,
`base64`, and `secrets.compare_digest` for the comparison. A timestamp more
than five minutes from now in either direction is refused, which bounds
replay of a captured delivery to that window; the UNIQUE `svix_id` closes it.

MINIMIZATION. From the whole payload only these survive: the Resend message
id, the event type, when it happened, the `source_app` / `org_id` tags Janua
put on the send, the bounce (or suppression) type and subtype, and for clicks
the link reduced to scheme + host + path. Never stored: recipient or sender
addresses, subject, IP address, user agent, the bounce diagnostic message
(it quotes the address), the query string and fragment of a clicked link
(tokens live there), and long opaque path segments (so do some tokens).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Mapping, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.email_event import EmailEvent
from app.services.email_tags import tag_value

PROVIDER = "resend"

#: Svix's documented replay tolerance.
TIMESTAMP_TOLERANCE_SECONDS = 5 * 60

#: Resend account slug in the URL -> the settings field holding its secret.
WEBHOOK_SECRET_SETTINGS = {
    "ctm": "RESEND_WEBHOOK_SECRET_CTM",
    "platform": "RESEND_WEBHOOK_SECRET_PLATFORM",
}

#: Every event type stored. Anything else is acknowledged and ignored.
EVENT_TYPES = frozenset(
    {
        "email.sent",
        "email.delivered",
        "email.delivery_delayed",
        "email.bounced",
        "email.complained",
        "email.opened",
        "email.clicked",
        "email.suppressed",
    }
)

_SVIX_ID = re.compile(r"^[A-Za-z0-9_\-]{1,255}$")
#: A path segment this long made only of token characters is treated as a
#: credential or an identifier and redacted (UUIDs included, deliberately).
_OPAQUE_SEGMENT = re.compile(r"^[A-Za-z0-9_\-.~=%]{32,}$")
REDACTED_SEGMENT = "{redacted}"


class WebhookVerificationError(Exception):
    """The delivery is not provably from Resend. The reason is for logs only."""


def secret_for(cuenta: str) -> Optional[str]:
    """The signing secret of a Resend account, or None if unknown/unset."""
    field = WEBHOOK_SECRET_SETTINGS.get(cuenta)
    if field is None:
        return None
    value = getattr(settings, field, None)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _secret_bytes(secret: str) -> bytes:
    raw = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WebhookVerificationError("signing secret is not valid base64") from exc


def sign(secret: str, svix_id: str, svix_timestamp: str, body: bytes) -> str:
    """The base64 v1 signature for one delivery (also used by the tests)."""
    signed = f"{svix_id}.{svix_timestamp}.".encode() + body
    digest = hmac.new(_secret_bytes(secret), signed, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_signature(
    secret: str,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
    body: bytes,
    now: Optional[float] = None,
) -> None:
    """Raise WebhookVerificationError unless the delivery is authentic and fresh."""
    if not svix_id or not svix_timestamp or not svix_signature:
        raise WebhookVerificationError("missing svix headers")
    if not _SVIX_ID.match(svix_id):
        raise WebhookVerificationError("malformed svix-id")
    try:
        timestamp = int(svix_timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("malformed svix-timestamp") from exc
    current = time.time() if now is None else now
    if abs(current - timestamp) > TIMESTAMP_TOLERANCE_SECONDS:
        raise WebhookVerificationError("svix-timestamp outside tolerance")
    expected = sign(secret, svix_id, svix_timestamp, body).encode()
    for entry in svix_signature.split():
        version, _, candidate = entry.partition(",")
        if version == "v1" and candidate and secrets.compare_digest(expected, candidate.encode()):
            return
    raise WebhookVerificationError("no matching v1 signature")


def sanitize_click_link(url: object) -> Optional[str]:
    """scheme://host/path of a clicked link; query, fragment, userinfo, port dropped.

    Only http(s). Path segments that look like opaque tokens are replaced by
    `{redacted}`. Returns None when nothing safe is left.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
    except ValueError:
        return None
    scheme = (parts.scheme or "").lower()
    if scheme not in {"http", "https"} or not host:
        return None
    segments = [
        REDACTED_SEGMENT if _OPAQUE_SEGMENT.match(segment) else segment
        for segment in parts.path.split("/")
    ]
    path = "/".join(segments)
    return urlunsplit((scheme, host.lower(), path, "", ""))[:2048]


def _parse_time(value: object) -> Optional[datetime]:
    """An ISO-8601-ish provider timestamp as naive UTC (the repo's convention)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace(" ", "T", 1)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if re.search(r"[+-]\d\d$", text):  # PostgreSQL-style "+00"
        text += ":00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _short(value: object, limit: int = 64) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()[:limit]
    return text or None


@dataclass(frozen=True)
class ParsedEvent:
    email_id: str
    event_type: str
    occurred_at: datetime
    source_app: Optional[str]
    org_id: Optional[str]
    bounce_type: Optional[str] = None
    bounce_subtype: Optional[str] = None
    click_link: Optional[str] = None


class MalformedEvent(Exception):
    """A verified delivery of a known type that lacks what we need to store it."""


def parse_event(payload: object) -> Optional[ParsedEvent]:
    """The minimized event, or None for a type we do not store."""
    if not isinstance(payload, Mapping):
        raise MalformedEvent("payload is not an object")
    event_type = payload.get("type")
    if event_type not in EVENT_TYPES:
        return None
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise MalformedEvent("data is not an object")
    email_id = _short(data.get("email_id"), 255)
    if not email_id:
        raise MalformedEvent("data.email_id missing")

    click_raw = data.get("click")
    click: Mapping[str, Any] = click_raw if isinstance(click_raw, Mapping) else {}
    occurred = (
        (_parse_time(click.get("timestamp")) if event_type == "email.clicked" else None)
        or _parse_time(data.get("created_at"))
        or _parse_time(payload.get("created_at"))
        or datetime.utcnow()
    )

    bounce_type = bounce_subtype = None
    if event_type == "email.bounced" and isinstance(data.get("bounce"), Mapping):
        bounce = data["bounce"]
        bounce_type = _short(bounce.get("type"))
        bounce_subtype = _short(bounce.get("subType") or bounce.get("subtype"))
    elif event_type == "email.suppressed" and isinstance(data.get("suppressed"), Mapping):
        suppressed = data["suppressed"]
        bounce_type = _short(suppressed.get("type"))
        bounce_subtype = _short(suppressed.get("subType") or suppressed.get("subtype"))

    tags = data.get("tags")
    return ParsedEvent(
        email_id=email_id,
        event_type=str(event_type),
        occurred_at=occurred,
        source_app=tag_value(tags, "source_app"),
        org_id=tag_value(tags, "org_id"),
        bounce_type=bounce_type,
        bounce_subtype=bounce_subtype,
        click_link=(
            sanitize_click_link(click.get("link")) if event_type == "email.clicked" else None
        ),
    )


async def record_event(
    db: AsyncSession,
    cuenta: str,
    svix_id: str,
    event: ParsedEvent,
    *,
    source: str = "webhook",
    possible_prefetch: Optional[bool] = None,
) -> bool:
    """Insert once per svix_id. True if stored now, False if it was a redelivery.

    `source='first_party'` rows (app/services/email_engagement.py) use the same
    insert with a deterministic `fp:` key in `svix_id`, which is what dedupes
    them; `possible_prefetch` is only ever set on those.
    """
    values = {
        "provider": PROVIDER,
        "cuenta": cuenta,
        "svix_id": svix_id,
        "email_id": event.email_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "source_app": event.source_app,
        "org_id": event.org_id,
        "bounce_type": event.bounce_type,
        "bounce_subtype": event.bounce_subtype,
        "click_link": event.click_link,
        "received_at": datetime.utcnow(),
        "source": source,
        "possible_prefetch": possible_prefetch,
    }
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert  # type: ignore[assignment]
    else:  # pragma: no cover - only PostgreSQL (prod) and SQLite (tests) exist
        raise RuntimeError(f"email_events: unsupported dialect {dialect!r}")
    statement = (
        dialect_insert(EmailEvent)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["svix_id"])
        .returning(EmailEvent.id)
    )
    result = await db.execute(statement)
    inserted = result.scalar_one_or_none() is not None
    await db.commit()
    return inserted


async def list_events(
    db: AsyncSession, source_app: str, after: int, limit: int, settle_seconds: int = 5
) -> Sequence[EmailEvent]:
    """Events for one app with cursor > after, oldest first.

    Rows younger than `settle_seconds` are held back. A cursor is a sequence
    value taken at INSERT, and two concurrent inserts can commit out of order;
    without the hold a poller could read id N+1, advance past N, and never see
    N once it commits. Each insert is one short statement, so a few seconds is
    far longer than the window it closes.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=settle_seconds)
    result = await db.execute(
        select(EmailEvent)
        .where(
            EmailEvent.source_app == source_app,
            EmailEvent.id > after,
            EmailEvent.received_at <= cutoff,
        )
        .order_by(EmailEvent.id)
        .limit(limit)
    )
    return list(result.scalars().all())


def feed_item(row: EmailEvent) -> dict[str, Any]:
    """One event in the feed contract shape (optional keys omitted when empty)."""
    item: dict[str, Any] = {
        "cursor": int(row.id),
        "provider": row.provider,
        "email_id": row.email_id,
        "type": row.event_type.removeprefix("email."),
        "occurred_at": row.occurred_at.replace(tzinfo=timezone.utc),
    }
    for key in ("bounce_type", "bounce_subtype", "click_link"):
        value = getattr(row, key)
        if value:
            item[key] = value
    # First-party rows (Janua's own tracking host) say so; webhook rows are
    # byte-identical to before. `provider` stays the provider that carried the
    # message, so a consumer that checks it (MAP) keeps accepting the event.
    if getattr(row, "source", None) == "first_party":
        item["source"] = "first_party"
        if row.possible_prefetch:
            item["possible_prefetch"] = True
    return item


def feed_page(rows: List[EmailEvent], after: int) -> dict[str, Any]:
    return {
        "events": [feed_item(row) for row in rows],
        "next_cursor": int(rows[-1].id) if rows else after,
    }
