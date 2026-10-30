"""Organization-scoped authentication policy and its immutable change journal."""

from __future__ import annotations

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
from app.models.types import GUID as UUID


class OrganizationAuthenticationPolicy(Base):
    __tablename__ = "organization_authentication_policies"
    __table_args__ = (
        CheckConstraint("mfa_mode IN ('optional', 'required')", name="ck_org_auth_policy_mfa_mode"),
        CheckConstraint("version >= 1", name="ck_org_auth_policy_version"),
    )

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True)
    mfa_mode = Column(String(16), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OrganizationAuthenticationPolicyChange(Base):
    __tablename__ = "organization_authentication_policy_changes"
    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="uq_org_auth_policy_change_version"),
        CheckConstraint("mfa_mode IN ('optional', 'required')", name="ck_org_auth_change_mfa_mode"),
        CheckConstraint(
            "previous_mode IN ('optional', 'required')", name="ck_org_auth_change_previous_mode"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    version = Column(Integer, nullable=False)
    previous_mode = Column(String(16), nullable=False)
    mfa_mode = Column(String(16), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(String(300), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
