"""Receipt metadata only: the source application owns its minimal mail intent."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.models import Base
from app.models.types import GUID


class PaymentMailDispatch(Base):
    __tablename__ = "payment_mail_dispatches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "client_id", "command_id", name="uq_payment_mail_command"
        ),
        CheckConstraint("attempts >= 0", name="ck_payment_mail_attempts"),
        CheckConstraint(
            "state IN ('pending', 'sending', 'accepted', 'review')", name="ck_payment_mail_state"
        ),
        CheckConstraint(
            "state != 'accepted' OR (provider_message_id IS NOT NULL "
            "AND length(trim(provider_message_id)) > 0 AND accepted_at IS NOT NULL)",
            name="ck_payment_mail_receipt",
        ),
    )
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        GUID(), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    client_id = Column(GUID(), ForeignKey("oauth_clients.id", ondelete="RESTRICT"), nullable=False)
    command_id = Column(GUID(), nullable=False)
    request_hash = Column(String(64), nullable=False)
    envelope_hash = Column(String(64), nullable=False)
    binding_hash = Column(String(64), nullable=False)
    credential_fingerprint = Column(String(64), nullable=False)
    state = Column(String(16), nullable=False, default="pending")
    attempts = Column(Integer(), nullable=False, default=0)
    attempt_id = Column(GUID(), nullable=True)
    first_attempt_at = Column(DateTime(), nullable=True)
    lease_until = Column(DateTime(), nullable=True)
    next_attempt_at = Column(DateTime(), nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    accepted_at = Column(DateTime(), nullable=True)
    issue = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime(), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
