"""Provider email events (delivered / opened / clicked / bounced ...), minimized.

One row per VERIFIED provider webhook delivery, keyed by the provider's own
delivery id (`svix_id`) so a redelivery is a no-op. The row carries only what a
sending application needs to say "this message reached / was opened by / bounced
for its recipient": the provider's message id, the event, when it happened, the
app and tenant the send was tagged with, the bounce classification and a
sanitized click target.

DELIBERATELY ABSENT: recipient and sender addresses, subject, body, IP address,
user agent and the bounce diagnostic message (which quotes the address). The
sending app already knows who it wrote to: it joins on `email_id`, which is the
`message_id` Janua returned on send. See app/services/email_events.py.

`id` is the feed cursor of GET /api/v1/internal/email/events. BIGINT on
PostgreSQL; plain INTEGER on SQLite, the only integer primary key SQLite
auto-increments (the unit tests run there).

TWO SOURCES (019_email_first_party_engagement). `source = 'webhook'` rows come
from Resend's signed webhooks, as above. `source = 'first_party'` rows are
opens and clicks Janua measured ITSELF on its tracking hosts (see
app/services/email_engagement.py): `email.opened` / `email.clicked` only,
`provider` still names the provider that carried the message, and `svix_id`
holds a deterministic `fp:` key that makes each (message, kind, link) insert
once — the same append-only ON CONFLICT DO NOTHING the webhook path uses.
`possible_prefetch` is a coarse flag computed in memory from the request (an
image proxy prefetch or a link scanner); the request itself is never stored.

`EmailTrackingLink` is the other half: one row per instrumented message, keyed
by the SHA-256 of its opaque token, holding the ORIGINAL link targets so a
click redirect is always read from storage by index, never from the request.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.models import Base

CURSOR_TYPE = BigInteger().with_variant(Integer(), "sqlite")


class EmailEvent(Base):
    __tablename__ = "email_events"
    __table_args__ = (
        UniqueConstraint("svix_id", name="uq_email_events_svix_id"),
        Index("ix_email_events_email_id", "email_id"),
        Index("ix_email_events_source_app_id", "source_app", "id"),
    )

    id = Column(CURSOR_TYPE, primary_key=True, autoincrement=True)
    provider = Column(String(16), nullable=False, default="resend", server_default="resend")
    cuenta = Column(String(32), nullable=False)
    svix_id = Column(String(255), nullable=False)
    email_id = Column(String(255), nullable=False)
    event_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(), nullable=False)
    source_app = Column(String(64), nullable=True)
    org_id = Column(String(64), nullable=True)
    bounce_type = Column(String(64), nullable=True)
    bounce_subtype = Column(String(64), nullable=True)
    click_link = Column(String(2048), nullable=True)
    received_at = Column(DateTime(), nullable=False, default=datetime.utcnow)
    #: `webhook` (Resend) or `first_party` (Janua's own tracking host).
    source = Column(String(16), nullable=False, default="webhook", server_default="webhook")
    #: First-party only: the hit looked like a prefetch or a link scanner.
    possible_prefetch = Column(Boolean(), nullable=True)


class EmailTrackingLink(Base):
    """One instrumented message: its hashed token, its links, and its binding."""

    __tablename__ = "email_tracking_links"
    __table_args__ = (Index("ix_email_tracking_links_email_id", "email_id"),)

    #: SHA-256 hex of the opaque token in the message's tracking URLs.
    token_hash = Column(String(64), primary_key=True)
    #: Which Resend account carried it (`ctm` / `platform`), like email_events.
    cuenta = Column(String(32), nullable=False)
    source_app = Column(String(64), nullable=True)
    org_id = Column(String(64), nullable=True)
    #: Resend's id for the message, bound right after the send is accepted.
    email_id = Column(String(255), nullable=True)
    #: JSON array of the ORIGINAL http(s) link targets, index = link number.
    links = Column(Text(), nullable=False)
    created_at = Column(DateTime(), nullable=False, default=datetime.utcnow)
