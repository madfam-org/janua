"""One write-ahead receipt per actual send; no retry worker and no message content.

Only server-derived provenance classifies a MAP login. Upstream UUID headers
are diagnostic join keys, never caller identity or authorization.
"""

import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import update

from app.models.email_send_audit import EmailSendAudit

MAP_HOSTS = frozenset(
    {"map.creatumundo.mx", "crea-map.madfam.io", "ensayo-map.madfam.io", "staging-map.madfam.io"}
)
CORRELATION_HEADER = "X-Janua-Mail-Correlation-ID"
UPSTREAM_HEADER = "X-MAP-Mail-Audit-ID"


@dataclass(frozen=True)
class SendAudit:
    id: uuid.UUID
    source_app: str
    message_kind: str
    trigger_kind: str
    provenance: str
    org_id: str | None
    upstream_audit_id: uuid.UUID | None


_current: ContextVar[SendAudit | None] = ContextVar("email_send_audit", default=None)


def uuid_metadata(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except (ValueError, TypeError, AttributeError):
        return None


def require_map_attempt(source_app: str, value: object) -> uuid.UUID | None:
    """A MAP attempt join is mandatory metadata, never human authorization."""
    identity = uuid_metadata(value)
    if source_app == "crea-map" and identity is None:
        raise HTTPException(422, detail={"code": "map_mail_audit_id_required"})
    return identity


def is_map_destination(redirect_url: str | None) -> bool:
    try:
        return urlparse(redirect_url or "").hostname in MAP_HOSTS
    except ValueError:
        return False


def current_audit() -> SendAudit | None:
    return _current.get()


def audit_tags() -> list[dict[str, str]]:
    audit = current_audit()
    if audit is None:
        return []
    values = {
        "mail_audit_id": str(audit.id),
        "message_kind": audit.message_kind,
        "trigger_kind": audit.trigger_kind,
        "source_app": audit.source_app,
    }
    if audit.org_id is not None:
        values["org_id"] = audit.org_id
    if audit.upstream_audit_id is not None:
        values["map_audit_id"] = str(audit.upstream_audit_id)
    return [{"name": name, "value": value} for name, value in values.items()]


def merge_audit_tags(tags):
    canonical = audit_tags()
    names = {"mail_audit_id", "map_audit_id", "message_kind", "trigger_kind"}
    names.update(tag["name"] for tag in canonical)
    return [tag for tag in tags if tag.get("name") not in names] + canonical


async def add_intent(
    db,
    *,
    audit_id=None,
    magic_link_id=None,
    source_app: str,
    message_kind: str,
    trigger_kind: str,
    provenance: str,
    org_id: str | None = None,
    upstream_audit_id=None,
) -> uuid.UUID:
    identity = audit_id or uuid.uuid4()
    db.add(
        EmailSendAudit(
            id=identity,
            magic_link_id=magic_link_id,
            source_app=source_app,
            message_kind=message_kind,
            trigger_kind=trigger_kind,
            provenance=provenance,
            org_id=org_id,
            upstream_audit_id=uuid_metadata(upstream_audit_id),
            state="pending",
        )
    )
    # The caller commits this together with the magic link, or before entering
    # send_scope. Any failure happens before a provider call can be scheduled.
    await db.flush()
    return identity


async def attach_issuance(
    db, audit_id, magic_link_id=None, *, password_reset_id=None, not_issued=False
):
    values = (
        {"state": "not_issued"} if not_issued
        else {"password_reset_id": password_reset_id} if password_reset_id is not None
        else {"magic_link_id": magic_link_id}
    )
    changed = await db.execute(
        update(EmailSendAudit)
        .where(EmailSendAudit.id == audit_id, EmailSendAudit.state == "pending")
        .values(**values)
    )
    if changed.rowcount != 1:
        raise ValueError("Login mail intent unavailable")


async def new_internal_intent(
    *, upstream_audit_id=None, source_app: str, org_id=None, message_kind="notification"
) -> uuid.UUID:
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        async with db.begin():
            return await add_intent(
                db,
                source_app=source_app,
                org_id=org_id,
                message_kind=message_kind,
                trigger_kind="internal_api",
                provenance="authenticated_internal_claim",
                upstream_audit_id=upstream_audit_id,
            )


@asynccontextmanager
async def send_scope(audit_id):
    from app.database import AsyncSessionLocal

    identity = uuid_metadata(audit_id)
    if identity is None:
        raise ValueError("Mail audit identifier unavailable")
    async with AsyncSessionLocal() as db:
        async with db.begin():
            changed = await db.execute(
                update(EmailSendAudit)
                .where(EmailSendAudit.id == identity, EmailSendAudit.state == "pending")
                .values(state="sending", attempted_at=datetime.utcnow())
            )
            if changed.rowcount != 1:
                raise ValueError("Mail audit is not pending")
            row = await db.get(EmailSendAudit, identity)
            if (row.message_kind == "magic_login" and row.magic_link_id is None) or (
                row.message_kind == "password_recovery" and row.password_reset_id is None
            ):
                raise ValueError("Auth mail has no durable issuance")
            audit = SendAudit(
                row.id,
                row.source_app,
                row.message_kind,
                row.trigger_kind,
                row.provenance,
                row.org_id,
                row.upstream_audit_id,
            )
    token = _current.set(audit)
    try:
        yield audit
    finally:
        _current.reset(token)
        # A network exception or failed receipt write is ambiguous; never mark
        # it accepted and never resend it autonomously. Verified tags still
        # join the eventual webhook to the durable pre-send intent.
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await db.execute(
                    update(EmailSendAudit)
                    .where(EmailSendAudit.id == identity, EmailSendAudit.state == "sending")
                    .values(state="unknown")
                )


async def accepted_receipt(message_id: object) -> None:
    audit = current_audit()
    if audit is None:
        return
    if not isinstance(message_id, str) or not message_id.strip() or len(message_id) > 255:
        raise ValueError("Mail provider acceptance receipt unavailable")
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        async with db.begin():
            changed = await db.execute(
                update(EmailSendAudit)
                .where(EmailSendAudit.id == audit.id, EmailSendAudit.state == "sending")
                .values(
                    state="accepted",
                    provider_message_id=message_id.strip(),
                    accepted_at=datetime.utcnow(),
                )
            )
            if changed.rowcount != 1:
                # A signed webhook may have committed the same receipt before
                # the HTTP response returned. Matching proof is idempotent.
                known = await db.get(EmailSendAudit, audit.id)
                if (
                    known is None
                    or known.state != "accepted"
                    or known.provider_message_id != message_id.strip()
                ):
                    raise ValueError("Mail audit acceptance could not be persisted")


async def rejected_receipt() -> None:
    audit = current_audit()
    if audit is None:
        return
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await db.execute(
                update(EmailSendAudit)
                .where(EmailSendAudit.id == audit.id, EmailSendAudit.state == "sending")
                .values(state="rejected")
            )


async def audited_internal_send(
    enviar, *, source_app: str, org_id=None, message_kind="notification", upstream_audit_id=None
):
    if source_app != "crea-map":
        return await enviar()
    upstream_audit_id = require_map_attempt(source_app, upstream_audit_id)
    kind = (
        message_kind
        if message_kind
        in {"notification", "billing", "payment", "auth", "transactional", "prueba-direccion"}
        else "notification"
    )
    identity = await new_internal_intent(
        source_app=source_app, org_id=org_id, message_kind=kind, upstream_audit_id=upstream_audit_id
    )
    async with send_scope(identity):
        return await enviar()
