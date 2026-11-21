"""Shared devices: the device record and its pending enrolments.

A shared device (a shop-floor terminal that several people use) is a
confidential OAuth client of kind ``device`` (``core/device_clients.py``).
Janua holds its identity, its credential and its state; a product that serves
the device keeps only an operational row keyed by the device's ``client_id``.

``device_clients`` — the device record
--------------------------------------
One row per device client: the organization it belongs to, the template it was
created from, the label it sent (unverified text), its state (``active`` or
``disabled``), who approved it and when, who disabled it, when it last asked
for a token, and the clone signal: its recent boot identifiers (truncated
SHA-256 digests, never the values), how many times an older one came back, and
when Janua first flagged it. The credential itself is the bcrypt hash on the
``oauth_clients`` row, like every other client's.

``device_enrolments`` — a pending enrolment
-------------------------------------------
The device sends its secret once; Janua stores a bcrypt hash here, answers
with an eight-letter code, and keeps the row for a short time. An organization
administrator approves the code; Janua then creates (or, for a re-enrolment,
rotates) the device's client and clears ``secret_hash``. An approved or expired
row keeps no hash.

Why separate tables and not a column on ``oauth_clients``
---------------------------------------------------------
``oauth_clients`` is read on every token request. A new column there would make
any image that carries it fail every client's token request on a database
where the migration has not been applied. These tables are read only for a
device client (recognized by its ``client_id`` prefix) and by the enrolment
routes, so the code and the schema can ship in either order.

Kept in its own module, outside ``app/models/__init__.py``. It is registered
on ``Base.metadata`` wherever it is imported: the token endpoint and the
enrolment router both import it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.models import Base
from app.models.types import GUID as UUID

DEVICE_CLIENTS_TABLE = "device_clients"
DEVICE_ENROLMENTS_TABLE = "device_enrolments"

DEVICE_STATUS_ACTIVE = "active"
DEVICE_STATUS_DISABLED = "disabled"

ENROLMENT_STATUS_PENDING = "pending"
ENROLMENT_STATUS_APPROVED = "approved"


class DeviceClient(Base):
    """The identity record of one shared device."""

    __tablename__ = DEVICE_CLIENTS_TABLE
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_device_clients"),
        sa.UniqueConstraint("oauth_client_id", name="uq_device_clients_oauth_client_id"),
        sa.Index("ix_device_clients_organization_id", "organization_id"),
    )

    id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    oauth_client_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "oauth_clients.id",
            ondelete="CASCADE",
            name="fk_device_clients_oauth_client_id_oauth_clients",
        ),
        nullable=False,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_device_clients_organization_id_organizations",
        ),
        nullable=False,
    )
    template = Column(String(64), nullable=False)
    label = Column(String(100), nullable=False)
    status = Column(String(16), nullable=False)

    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_device_clients_approved_by_users"),
        nullable=True,
    )
    approved_at = Column(DateTime, nullable=False)
    disabled_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_device_clients_disabled_by_users"),
        nullable=True,
    )
    disabled_at = Column(DateTime, nullable=True)
    disabled_reason = Column(String(300), nullable=True)

    last_token_at = Column(DateTime, nullable=True)
    # Space-separated truncated SHA-256 digests, oldest first; the last one is
    # the current boot. See core/device_clients.observe_boot_id.
    recent_boot_ids = Column(String(400), nullable=True)
    boot_alternations = Column(Integer, nullable=False, default=0, server_default=sa.text("0"))
    clone_suspected_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeviceEnrolment(Base):
    """A device's request to be enrolled, waiting for a person to approve it."""

    __tablename__ = DEVICE_ENROLMENTS_TABLE
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_device_enrolments"),
        sa.UniqueConstraint("user_code", name="uq_device_enrolments_user_code"),
        sa.Index("ix_device_enrolments_organization_id_status", "organization_id", "status"),
    )

    id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_device_enrolments_organization_id_organizations",
        ),
        nullable=False,
    )
    template = Column(String(64), nullable=False)
    label = Column(String(100), nullable=False)
    user_code = Column(String(9), nullable=False)
    # bcrypt hash of the secret the device generated; NULL once approved or expired.
    secret_hash = Column(String(255), nullable=True)
    status = Column(String(16), nullable=False)
    # A re-enrolment names the device whose credential the approval rotates.
    replaces_device_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "device_clients.id",
            ondelete="SET NULL",
            name="fk_device_enrolments_replaces_device_id_device_clients",
        ),
        nullable=True,
    )
    # Where the request came from, shown to the approving administrator as
    # information. Never a check: any address can reach the public route.
    requested_ip = Column(String(64), nullable=True)
    requested_user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_device_enrolments_approved_by_users"),
        nullable=True,
    )
    approved_at = Column(DateTime, nullable=True)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "device_clients.id",
            ondelete="SET NULL",
            name="fk_device_enrolments_device_id_device_clients",
        ),
        nullable=True,
    )


__all__ = [
    "DEVICE_CLIENTS_TABLE",
    "DEVICE_ENROLMENTS_TABLE",
    "DEVICE_STATUS_ACTIVE",
    "DEVICE_STATUS_DISABLED",
    "ENROLMENT_STATUS_APPROVED",
    "ENROLMENT_STATUS_PENDING",
    "DeviceClient",
    "DeviceEnrolment",
]
