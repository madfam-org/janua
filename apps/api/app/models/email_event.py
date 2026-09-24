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
"""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, UniqueConstraint

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
