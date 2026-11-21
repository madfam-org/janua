"""Audit rows for shared devices: enrolment, approval, disabling, clone suspicion.

Each event is an ``AuditLog`` row (``audit_logs``, the table the OAuth client
service writes when a client is created) staged on the SAME transaction as the
change it records. The device's state and the record of who changed it
therefore commit together or not at all: there is no device that was approved
without a row saying by whom.

``details`` names the organization, the device's client identifier and label,
the template, and for a person's act nothing more than the reason they gave.
Never a secret, a hash, a boot identifier or a token.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

DEVICE_ENROLMENT_REQUESTED = "device.enrolment_requested"
DEVICE_ENROLMENT_APPROVED = "device.enrolment_approved"
DEVICE_DISABLED = "device.disabled"
DEVICE_CLONE_SUSPECTED = "device.clone_suspected"

RESOURCE_DEVICE = "device_client"
RESOURCE_ENROLMENT = "device_enrolment"


def stage_device_audit(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    actor_id: Optional[uuid.UUID],
    details: dict[str, Any],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Add the row to ``db``; the caller's commit writes it with the change."""
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )


__all__ = [
    "DEVICE_CLONE_SUSPECTED",
    "DEVICE_DISABLED",
    "DEVICE_ENROLMENT_APPROVED",
    "DEVICE_ENROLMENT_REQUESTED",
    "RESOURCE_DEVICE",
    "RESOURCE_ENROLMENT",
    "stage_device_audit",
]
