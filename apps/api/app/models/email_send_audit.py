"""Durable mail intent/receipt metadata. Never a delivery queue or recipient store."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String

from app.models import Base
from app.models.types import GUID


class EmailSendAudit(Base):
    __tablename__ = "email_send_audits"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','sending','accepted','rejected','unknown','not_issued')",
            name="ck_email_send_audit_state",
        ),
        CheckConstraint(
            "state != 'accepted' OR (provider_message_id IS NOT NULL AND length(trim(provider_message_id)) > 0 AND accepted_at IS NOT NULL)",
            name="ck_email_send_audit_receipt",
        ),
        Index("ix_email_send_audit_source_created", "source_app", "created_at"),
        Index("ix_email_send_audit_upstream", "upstream_audit_id"),
        Index("ix_email_send_audit_provider", "provider_message_id"),
    )
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    magic_link_id = Column(GUID(), ForeignKey("magic_links.id", ondelete="RESTRICT"), nullable=True)
    password_reset_id = Column(
        GUID(), ForeignKey("password_resets.id", ondelete="RESTRICT"), nullable=True
    )
    source_app = Column(String(64), nullable=False)
    message_kind = Column(String(32), nullable=False)
    trigger_kind = Column(String(32), nullable=False)
    provenance = Column(String(40), nullable=False)
    org_id = Column(String(64), nullable=True)
    upstream_audit_id = Column(GUID(), nullable=True)
    state = Column(String(16), nullable=False, default="pending")
    provider_message_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(), nullable=False, default=datetime.utcnow)
    attempted_at = Column(DateTime(), nullable=True)
    accepted_at = Column(DateTime(), nullable=True)
