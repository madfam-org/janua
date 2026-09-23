"""Bounded provider deduplication with durable, tenant-bound acceptance receipts.

The caller's outbox owns the minimal intent. This ledger stores no recipient or
body and never repeats an unknown outcome beyond the provider's key window.
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from email.utils import formataddr
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, PaymentMailDispatch
from app.services.payment_mail_auth import PaymentMailPrincipal, current_mail_client
from app.services.resend_transport import send_on_account

TEMPLATE = "map/pago-confirmado"
SAFE_WINDOW = timedelta(hours=23)
LEASE = timedelta(minutes=3)
MAX_ATTEMPTS = 10
MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


class PaymentNoticeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: uuid.UUID
    recipient: EmailStr
    year: int = Field(ge=2000, le=2100, strict=True)
    month: int = Field(ge=1, le=12, strict=True)
    sessions: int | None = Field(default=None, ge=0, le=100000, strict=True)


class PaymentNoticeReceipt(BaseModel):
    command_id: uuid.UUID
    receipt_id: uuid.UUID
    delivery_status: Literal["accepted", "pending", "review"]
    message_id: str | None = None
    retry_after: datetime | None = None
    issue: str = ""


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _refuse(code, status=409):
    return HTTPException(status_code=status, detail={"code": code})


def _key(principal, intent):
    return "janua-payment/" + _hash(
        [str(principal.org_id), principal.client_id, str(intent.command_id)]
    )


def _result(row):
    retry = row.lease_until if row.state == "sending" else row.next_attempt_at
    return PaymentNoticeReceipt(
        command_id=row.command_id,
        receipt_id=row.id,
        delivery_status="accepted"
        if row.state == "accepted"
        else "review"
        if row.state == "review"
        else "pending",
        message_id=row.provider_message_id if row.state == "accepted" else None,
        retry_after=retry.replace(tzinfo=timezone.utc) if retry else None,
        issue=row.issue,
    )


async def _row(db, client, principal, intent):
    result = await db.execute(
        select(PaymentMailDispatch)
        .where(
            PaymentMailDispatch.organization_id == principal.org_id,
            PaymentMailDispatch.client_id == client.id,
            PaymentMailDispatch.command_id == intent.command_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


def _known(row, digest, now):
    if row is None:
        return None
    if row.request_hash != digest:
        raise _refuse("mail_command_content_changed")
    if row.state in {"accepted", "review"}:
        return _result(row)
    if row.first_attempt_at and now >= row.first_attempt_at + SAFE_WINDOW:
        row.state, row.issue, row.lease_until = "review", "provider_key_window_expired", None
        row.next_attempt_at = None
        return _result(row)
    if row.state == "sending" and row.lease_until and row.lease_until > now:
        return _result(row)
    if row.attempts >= MAX_ATTEMPTS:
        row.state, row.issue, row.lease_until = "review", "attempt_limit_reached", None
        row.next_attempt_at = None
        return _result(row)
    if row.next_attempt_at and row.next_attempt_at > now:
        return _result(row)
    return None


async def _envelope(principal, intent):
    # Imports are local to keep the existing legacy router independent of this
    # optional durable path; legacy authentication mail keeps its own policy.
    from app.routers.v1.email import EMAIL_TEMPLATES, _get_safe_template_path, render_template
    from app.services.email_sender import sender_for_address
    from app.services.sender_binding import PROVIDER_RESEND, resolve_binding, tenant_for_org_id
    from app.services.sender_credentials import resolve_bound_credential

    if not settings.EMAIL_ENABLED or settings.ENVIRONMENT == "development":
        raise _refuse("mail_transport_inactive", 503)
    binding = resolve_binding(tenant_for_org_id(principal.org_id))
    if binding.org_id != str(principal.org_id) or binding.provider != PROVIDER_RESEND:
        raise _refuse("mail_sender_binding_unavailable", 503)
    sender_name, sender_address, reply = sender_for_address(None, org_id=str(principal.org_id))
    if sender_address != binding.from_address or sender_name != binding.display_name:
        raise _refuse("mail_tenant_sender_unavailable", 503)
    try:
        credential = await resolve_bound_credential(binding)
    except Exception as error:
        raise _refuse("mail_credential_unavailable", 503) from error
    if not credential:
        raise _refuse("mail_credential_unavailable", 503)
    if not Path(_get_safe_template_path(TEMPLATE)).is_file():
        raise _refuse("mail_template_unavailable", 503)
    variables = {"periodo": f"{MONTHS[intent.month - 1]} de {intent.year}"}
    if intent.sessions:
        variables["sesiones"] = intent.sessions
    params = {
        "from": formataddr((sender_name, sender_address)),
        "to": [str(intent.recipient)],
        "subject": EMAIL_TEMPLATES[TEMPLATE]["subject"],
        "html": await render_template(TEMPLATE, variables),
        "headers": {"X-Message-ID": _key(principal, intent)},
        "tags": [
            {"name": "source_app", "value": "crea-map"},
            {"name": "source_type", "value": "payment"},
            {"name": "template", "value": TEMPLATE.replace("/", "_")},
        ],
    }
    if reply:
        params["reply_to"] = reply
    # No secret value is stored/logged. A credential change after an ambiguous
    # send requires review even if it was intended to be a same-account rotation.
    fingerprint = hmac.new(
        settings.SECRET_KEY.encode(), credential.encode(), hashlib.sha256
    ).hexdigest()
    return params, credential, _hash(asdict(binding)), fingerprint


async def dispatch_payment_notice(
    db: AsyncSession, principal: PaymentMailPrincipal, intent: PaymentNoticeIntent
):
    digest = _hash(intent.model_dump(mode="json"))
    # Exact accepted replay must work during a provider/credential outage.
    async with db.begin():
        client = await current_mail_client(db, principal)
        row = await _row(db, client, principal, intent)
        result = _known(row, digest, datetime.utcnow())
        if result:
            return result
    params, credential, binding_hash, credential_fingerprint = await _envelope(principal, intent)
    envelope_hash = _hash(params)
    async with db.begin():
        client = await current_mail_client(db, principal)
        if db.bind.dialect.name == "postgresql":
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": _key(principal, intent)},
            )
        row = await _row(db, client, principal, intent)
        now = datetime.utcnow()
        result = _known(row, digest, now)
        if result:
            return result
        if row is None:
            row = PaymentMailDispatch(
                id=uuid.uuid4(),
                organization_id=principal.org_id,
                client_id=client.id,
                command_id=intent.command_id,
                request_hash=digest,
                envelope_hash=envelope_hash,
                binding_hash=binding_hash,
                credential_fingerprint=credential_fingerprint,
                attempts=0,
                state="pending",
                issue="",
            )
            db.add(row)
        elif (
            row.envelope_hash != envelope_hash
            or row.binding_hash != binding_hash
            or row.credential_fingerprint != credential_fingerprint
        ):
            row.state, row.issue = "review", "mail_envelope_or_account_changed"
            row.lease_until, row.next_attempt_at = None, None
            return _result(row)
        row.attempts += 1
        row.attempt_id = uuid.uuid4()
        row.state, row.issue = "sending", ""
        row.first_attempt_at = row.first_attempt_at or now
        row.lease_until, row.next_attempt_at = now + LEASE, None
        row_id, attempt_id, attempts = row.id, row.attempt_id, row.attempts
        send_before = row.first_attempt_at + SAFE_WINDOW
    # Provider I/O is outside the transaction and off the FastAPI event loop.
    message_id = None
    try:
        response = await asyncio.to_thread(
            send_on_account,
            params,
            credential,
            idempotency_key=_key(principal, intent),
            send_before=send_before,
        )
        candidate = response.get("id")
        if not isinstance(candidate, str) or not 1 <= len(candidate.strip()) <= 255:
            raise ValueError("Invalid acceptance receipt")
        message_id = candidate.strip()
    except Exception:
        pass  # No recipient, body, provider exception, or credential in logs.
    async with db.begin():
        now = datetime.utcnow()
        values = (
            {
                "state": "accepted",
                "provider_message_id": message_id,
                "accepted_at": now,
                "issue": "",
                "next_attempt_at": None,
            }
            if message_id
            else {
                "state": "review" if now >= send_before else "pending",
                "issue": "provider_key_window_expired"
                if now >= send_before
                else "provider_outcome_unknown",
                "next_attempt_at": None
                if now >= send_before
                else now + timedelta(seconds=min(60 * 2 ** (attempts - 1), 900)),
            }
        )
        result = await db.execute(
            update(PaymentMailDispatch)
            .where(
                PaymentMailDispatch.id == row_id,
                PaymentMailDispatch.attempt_id == attempt_id,
                PaymentMailDispatch.state == "sending",
            )
            .values(**values, lease_until=None, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0 and message_id:
            # Preserve a stale worker's observed acceptance for manual review;
            # it may not overwrite the newer lease/state.
            db.add(
                AuditLog(
                    action="email.payment_notice.late_receipt",
                    resource_type="payment_mail_dispatch",
                    resource_id=row_id,
                    details={"attempt_id": str(attempt_id), "message_id": message_id},
                )
            )
        db.expire_all()
        row = await db.get(PaymentMailDispatch, row_id)
        return _result(row)
