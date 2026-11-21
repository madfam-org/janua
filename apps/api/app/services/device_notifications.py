"""Telling an organization's administrators that one of its devices was flagged.

When a device's token requests alternate between boot identifiers
(`core/device_clients.observe_boot_id`), Janua flags the device and tells the
people who can act: the organization's owner and its active ``owner`` /
``admin`` members. Janua does not disable the device; a person does, with one
action, if the device is not where it should be.

Recipients are read inside the request (one query) and the mail goes out after
the response, so the token request never waits on a mail provider. Sending is
best-effort: a failure is logged and changes nothing else, because the flag on
the device record is the durable signal and the list route shows it.

The message carries the device's label and client identifier and the
organization's name. Never a secret, a boot identifier or a token.
"""

from __future__ import annotations

import html
import uuid
from dataclasses import dataclass
from typing import Optional

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, OrganizationMember, User, UserStatus

logger = structlog.get_logger()

ORGANIZATION_ADMIN_ROLES = ("owner", "admin")


@dataclass(frozen=True)
class CloneSuspicionNotice:
    recipients: tuple[str, ...]
    subject: str
    text: str
    html: str


async def organization_admin_emails(db: AsyncSession, organization_id: uuid.UUID) -> list[str]:
    """Emails of the organization's owner and active owner/admin members (people only)."""
    owner_id = (
        await db.execute(select(Organization.owner_id).where(Organization.id == organization_id))
    ).scalar_one_or_none()
    admin_ids = select(OrganizationMember.user_id).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.status == "active",
        OrganizationMember.role.in_(ORGANIZATION_ADMIN_ROLES),
    )
    conditions = [User.id.in_(admin_ids)]
    if owner_id is not None:
        conditions.append(User.id == owner_id)
    rows = (
        await db.execute(
            select(User.email, User.is_service_account).where(
                or_(*conditions), User.status == UserStatus.ACTIVE
            )
        )
    ).all()
    emails = sorted({email for email, is_service in rows if email and not is_service})
    return emails


def build_clone_suspicion_notice(
    *,
    recipients: list[str],
    organization_name: Optional[str],
    device_label: str,
    client_id: str,
) -> CloneSuspicionNotice:
    organization = organization_name or "your organization"
    subject = f"Janua: device «{device_label}» may have been copied"
    lines = [
        f"Janua flagged the device «{device_label}» ({client_id}) of {organization}.",
        "",
        "Its token requests alternate between two start-up identifiers. One device that",
        "restarts never goes back to an earlier identifier; two holders of the same device",
        "credential do, each time they take turns. That usually means the device's storage",
        "was copied.",
        "",
        "Janua has NOT disabled the device. If it is not in your hands, or you cannot account",
        "for a second copy, disable it in Janua: it then receives no new token, and a token it",
        "already holds expires within fifteen minutes. The device can be enrolled again",
        "afterwards, with the device in hand.",
        "",
        "This is an automated notice sent to the organization's administrators.",
    ]
    text = "\n".join(lines)
    body = "".join(f"<p>{html.escape(line)}</p>" if line else "" for line in lines)
    return CloneSuspicionNotice(recipients=tuple(recipients), subject=subject, text=text, html=body)


async def send_clone_suspicion_notice(notice: CloneSuspicionNotice) -> None:
    """Send the notice to each recipient. Never raises."""
    if not notice.recipients:
        logger.warning("Device flagged; the organization has no administrator to notify")
        return
    try:
        from app.services.enhanced_email_service import EmailPriority, enhanced_email_service
    except Exception as exc:  # pragma: no cover - import guard
        logger.error("Device notice not sent: mail service unavailable", error=type(exc).__name__)
        return
    for recipient in notice.recipients:
        try:
            await enhanced_email_service.send_email_with_failover(
                to_email=recipient,
                subject=notice.subject,
                html_content=notice.html,
                text_content=notice.text,
                priority=EmailPriority.HIGH,
                metadata={"type": "device_clone_suspected"},
            )
        except Exception as exc:
            logger.error("Device notice not sent", error=type(exc).__name__)


__all__ = [
    "CloneSuspicionNotice",
    "build_clone_suspicion_notice",
    "organization_admin_emails",
    "send_clone_suspicion_notice",
]
