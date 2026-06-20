"""ConnectedAccount model — Universal Keyring (ADR-002, Coupler P1)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models import Base
from app.models.types import GUID as UUID
from app.models.types import JSON as JSONB
from app.models.types import EncryptedString


class ConnectedAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"


class ProviderType(Base):
    __tablename__ = "provider_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_code = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="integration")
    supports_oauth = Column(String(5), default="true")  # stored as string for sqlite compat in tests
    is_active = Column(String(5), default="true")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConnectedAccount(Base):
    """Vault-backed delegated SaaS connection for Coupler execute."""

    __tablename__ = "connected_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    provider_type = Column(String(50), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False)
    provider_id = Column(String(255), nullable=True)

    access_token_encrypted = Column(EncryptedString())
    refresh_token_encrypted = Column(EncryptedString())
    oauth_scopes = Column(JSONB, default=list)
    oauth_expires_at = Column(DateTime, nullable=True)

    status = Column(String(20), default=ConnectedAccountStatus.ACTIVE.value)
    account_metadata = Column("metadata", JSONB, default=dict)
    last_used_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
