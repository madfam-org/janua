"""POST /api/v1/email/webhooks/resend/{cuenta}: Svix verification, idempotency,
minimization.

Every delivery here is signed the way Resend signs it (Svix v1: HMAC-SHA256 of
"{svix_id}.{svix_timestamp}.{raw_body}" keyed with the base64-decoded part of a
`whsec_` secret), with a synthetic secret generated per test run. No network,
no real secret, no real recipient. Rows are asserted directly on a SQLite
database, because the row -- what was and was NOT stored -- is the guarantee.
"""

from __future__ import annotations

import base64
import json
import secrets as pysecrets
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.email_event import EmailEvent
from app.services import email_events
from app.services.email_events import sanitize_click_link, sign

CTM_URL = "/api/v1/email/webhooks/resend/ctm"
PLATFORM_URL = "/api/v1/email/webhooks/resend/platform"

SECRET_CTM = "whsec_" + base64.b64encode(pysecrets.token_bytes(24)).decode()
SECRET_PLATFORM = "whsec_" + base64.b64encode(pysecrets.token_bytes(24)).decode()

RECIPIENT = "persona.ficticia@example.test"
SENDER = "Crea Tu Mundo <hola@creatumundo.mx>"
SUBJECT = "Asunto con dato sensible"
IP = "203.0.113.77"
USER_AGENT = "Mozilla/5.0 (Macintosh; Ficticio)"
ORG_ID = "e6cbd51d-0000-4000-8000-000000000001"


@pytest_asyncio.fixture
async def env(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET_CTM", SECRET_CTM, raising=False)
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET_PLATFORM", None, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


def _payload(event_type: str, **data: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "email_id": "4ef9a417-02e9-4d39-ad75-9611e0fcc33c",
        "created_at": "2026-09-23T15:04:05.123456+00:00",
        "from": SENDER,
        "to": [RECIPIENT],
        "subject": SUBJECT,
        "tags": {"source_app": "crea-map", "org_id": ORG_ID, "source_type": "notification"},
    }
    body.update(data)
    return {"type": event_type, "created_at": "2026-09-23T15:04:06.000Z", "data": body}


def _signed(
    payload: Any,
    secret: str = SECRET_CTM,
    svix_id: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> tuple[bytes, Dict[str, str]]:
    raw = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
    svix_id = svix_id or f"msg_{pysecrets.token_hex(12)}"
    ts = str(timestamp if timestamp is not None else int(time.time()))
    headers = {
        "content-type": "application/json",
        "svix-id": svix_id,
        "svix-timestamp": ts,
        "svix-signature": f"v1,{sign(secret, svix_id, ts, raw)}",
    }
    return raw, headers


async def _rows(factory) -> list[EmailEvent]:
    async with factory() as session:
        return list((await session.execute(select(EmailEvent).order_by(EmailEvent.id))).scalars())


# --------------------------------------------------------------------------
# Signature verification
# --------------------------------------------------------------------------


async def test_valid_signature_is_stored(env):
    client, factory = env
    raw, headers = _signed(_payload("email.delivered"))
    response = await client.post(CTM_URL, content=raw, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "stored"}
    rows = await _rows(factory)
    assert len(rows) == 1
    row = rows[0]
    assert (row.provider, row.cuenta, row.svix_id) == ("resend", "ctm", headers["svix-id"])
    assert row.email_id == "4ef9a417-02e9-4d39-ad75-9611e0fcc33c"
    assert row.event_type == "email.delivered"
    assert row.source_app == "crea-map"
    assert row.org_id == ORG_ID
    assert row.occurred_at == datetime(2026, 9, 23, 15, 4, 5, 123456)


async def test_any_matching_signature_among_several_is_accepted(env):
    """Svix sends several space-separated signatures during a secret rotation."""
    client, factory = env
    raw, headers = _signed(_payload("email.sent"))
    other = "v1," + base64.b64encode(b"x" * 32).decode()
    headers["svix-signature"] = f"{other} v2,ignored {headers['svix-signature']}"
    assert (await client.post(CTM_URL, content=raw, headers=headers)).status_code == 200
    assert len(await _rows(factory)) == 1


async def test_bad_signature_is_401_and_stores_nothing(env):
    client, factory = env
    raw, headers = _signed(_payload("email.delivered"), secret=SECRET_PLATFORM)
    response = await client.post(CTM_URL, content=raw, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid webhook signature"}
    assert await _rows(factory) == []


async def test_tampered_body_is_401(env):
    client, factory = env
    raw, headers = _signed(_payload("email.delivered"))
    tampered = raw.replace(b"crea-map", b"crea-mop")
    assert (await client.post(CTM_URL, content=tampered, headers=headers)).status_code == 401
    assert await _rows(factory) == []


# Margins of 10 s either side of the 300 s tolerance: `int(time.time())` floors
# and the request takes time, so an offset of exactly 301 can land at 300.x.
@pytest.mark.parametrize("offset", [-310, 310, -3600])
async def test_stale_or_future_timestamp_is_401(env, offset):
    client, factory = env
    raw, headers = _signed(_payload("email.delivered"), timestamp=int(time.time()) + offset)
    response = await client.post(CTM_URL, content=raw, headers=headers)
    assert response.status_code == 401
    assert await _rows(factory) == []


@pytest.mark.parametrize("offset", [-290, 290])
async def test_timestamp_inside_tolerance_is_accepted(env, offset):
    client, _ = env
    raw, headers = _signed(_payload("email.delivered"), timestamp=int(time.time()) + offset)
    assert (await client.post(CTM_URL, content=raw, headers=headers)).status_code == 200


@pytest.mark.parametrize("missing", ["svix-id", "svix-timestamp", "svix-signature"])
async def test_missing_header_is_401(env, missing):
    client, factory = env
    raw, headers = _signed(_payload("email.delivered"))
    del headers[missing]
    response = await client.post(CTM_URL, content=raw, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid webhook signature"}
    assert await _rows(factory) == []


async def test_malformed_timestamp_is_401(env):
    client, _ = env
    raw, headers = _signed(_payload("email.delivered"))
    headers["svix-timestamp"] = "yesterday"
    assert (await client.post(CTM_URL, content=raw, headers=headers)).status_code == 401


async def test_unknown_and_unconfigured_accounts_are_indistinguishable_404s(env):
    """`platform` is a real account with no secret configured in this test;
    `nope` does not exist. A caller must not be able to tell them apart."""
    client, factory = env
    raw, headers = _signed(_payload("email.delivered"))
    unconfigured = await client.post(PLATFORM_URL, content=raw, headers=headers)
    unknown = await client.post("/api/v1/email/webhooks/resend/nope", content=raw, headers=headers)
    assert unconfigured.status_code == unknown.status_code == 404
    assert unconfigured.json() == unknown.json()
    assert await _rows(factory) == []


async def test_each_account_verifies_with_its_own_secret(env, monkeypatch):
    client, factory = env
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET_PLATFORM", SECRET_PLATFORM)
    raw, headers = _signed(_payload("email.delivered"), secret=SECRET_PLATFORM)
    assert (await client.post(PLATFORM_URL, content=raw, headers=headers)).status_code == 200
    assert (await client.post(CTM_URL, content=raw, headers=headers)).status_code == 401
    rows = await _rows(factory)
    assert [r.cuenta for r in rows] == ["platform"]


async def test_oversized_body_is_413(env):
    client, _ = env
    raw, headers = _signed(b"{" + b" " * (1024 * 1024) + b"}")
    assert (await client.post(CTM_URL, content=raw, headers=headers)).status_code == 413


def test_verify_signature_rejects_a_non_base64_secret():
    with pytest.raises(email_events.WebhookVerificationError):
        email_events.verify_signature("whsec_***", "msg_1", str(int(time.time())), "v1,x", b"{}")


# --------------------------------------------------------------------------
# Idempotency and unknown types
# --------------------------------------------------------------------------


async def test_duplicate_svix_id_is_200_without_a_second_row(env):
    client, factory = env
    raw, headers = _signed(_payload("email.opened"), svix_id="msg_duplicate_1")
    first = await client.post(CTM_URL, content=raw, headers=headers)
    second = await client.post(CTM_URL, content=raw, headers=headers)
    assert first.json() == {"status": "stored"}
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate"}
    assert len(await _rows(factory)) == 1


@pytest.mark.parametrize("event_type", ["contact.created", "domain.updated", "email.unknown", 7])
async def test_unknown_event_type_is_acknowledged_and_ignored(env, event_type):
    client, factory = env
    raw, headers = _signed(_payload("email.sent") | {"type": event_type})
    response = await client.post(CTM_URL, content=raw, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert await _rows(factory) == []


@pytest.mark.parametrize(
    "payload",
    [b"not json", b"[1, 2]", json.dumps({"type": "email.sent", "data": {}}).encode()],
)
async def test_verified_but_malformed_event_is_acknowledged_not_stored(env, payload):
    client, factory = env
    raw, headers = _signed(payload)
    response = await client.post(CTM_URL, content=raw, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert await _rows(factory) == []


# --------------------------------------------------------------------------
# Every event type parses to the right row
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event_type", "extra", "expected"),
    [
        ("email.sent", {}, {}),
        ("email.delivered", {}, {}),
        ("email.delivery_delayed", {}, {}),
        ("email.complained", {}, {}),
        ("email.opened", {}, {}),
        (
            "email.bounced",
            {
                "bounce": {
                    "message": f"550 5.1.1 <{RECIPIENT}>: user unknown",
                    "type": "Permanent",
                    "subType": "General",
                }
            },
            {"bounce_type": "Permanent", "bounce_subtype": "General"},
        ),
        (
            "email.suppressed",
            {
                "suppressed": {
                    "message": f"{RECIPIENT} is suppressed",
                    "type": "OnAccountSuppressionList",
                }
            },
            {"bounce_type": "OnAccountSuppressionList", "bounce_subtype": None},
        ),
        (
            "email.clicked",
            {
                "click": {
                    "ipAddress": IP,
                    "link": "https://map.creatumundo.mx/agenda?token=SECRET123#frag",
                    "timestamp": "2026-09-23T16:00:00.000Z",
                    "userAgent": USER_AGENT,
                }
            },
            {"click_link": "https://map.creatumundo.mx/agenda"},
        ),
    ],
)
async def test_each_event_type_is_parsed(env, event_type, extra, expected):
    client, factory = env
    raw, headers = _signed(_payload(event_type, **extra))
    assert (await client.post(CTM_URL, content=raw, headers=headers)).json() == {"status": "stored"}
    (row,) = await _rows(factory)
    assert row.event_type == event_type
    for column in ("bounce_type", "bounce_subtype", "click_link"):
        assert getattr(row, column) == expected.get(column)
    if event_type == "email.clicked":
        # A click happens at click.timestamp, not when the email was created.
        assert row.occurred_at == datetime(2026, 9, 23, 16, 0, 0)
    else:
        assert row.occurred_at == datetime(2026, 9, 23, 15, 4, 5, 123456)


async def test_tags_as_a_name_value_list_are_read_too(env):
    client, factory = env
    tags = [{"name": "source_app", "value": "crea-map"}, {"name": "org_id", "value": ORG_ID}]
    raw, headers = _signed(_payload("email.delivered", tags=tags))
    await client.post(CTM_URL, content=raw, headers=headers)
    (row,) = await _rows(factory)
    assert (row.source_app, row.org_id) == ("crea-map", ORG_ID)


async def test_untagged_event_is_stored_without_scope(env):
    client, factory = env
    payload = _payload("email.delivered")
    del payload["data"]["tags"]
    raw, headers = _signed(payload)
    await client.post(CTM_URL, content=raw, headers=headers)
    (row,) = await _rows(factory)
    assert row.source_app is None and row.org_id is None


# --------------------------------------------------------------------------
# Data minimization
# --------------------------------------------------------------------------


async def test_no_pii_is_stored_for_any_event(env):
    """Recipient, sender, subject, IP, user agent, bounce message, the click's
    query/fragment: none of it may reach any column of any row."""
    client, factory = env
    for event_type, extra in [
        ("email.delivered", {}),
        (
            "email.bounced",
            {
                "bounce": {
                    "message": f"<{RECIPIENT}> unknown",
                    "type": "Permanent",
                    "subType": "General",
                }
            },
        ),
        (
            "email.clicked",
            {
                "click": {
                    "ipAddress": IP,
                    "link": f"https://map.creatumundo.mx/x?email={RECIPIENT}&token=SECRET123",
                    "timestamp": "2026-09-23T16:00:00Z",
                    "userAgent": USER_AGENT,
                }
            },
        ),
        ("email.opened", {"open": {"ipAddress": IP, "userAgent": USER_AGENT}}),
    ]:
        raw, headers = _signed(_payload(event_type, **extra))
        assert (await client.post(CTM_URL, content=raw, headers=headers)).status_code == 200

    rows = await _rows(factory)
    assert len(rows) == 4
    stored = " ".join(
        str(getattr(row, column.name)) for row in rows for column in EmailEvent.__table__.columns
    )
    for needle in (
        RECIPIENT,
        "persona.ficticia",
        "hola@creatumundo.mx",
        SUBJECT,
        IP,
        USER_AGENT,
        "Ficticio",
        "SECRET123",
        "token=",
        "unknown",
    ):
        assert needle not in stored, needle


def test_the_table_has_no_column_that_could_hold_pii():
    """Schema-level guard: adding a recipient/subject/ip column is a decision,
    not an accident."""
    assert {c.name for c in EmailEvent.__table__.columns} == {
        "id",
        "provider",
        "cuenta",
        "svix_id",
        "email_id",
        "event_type",
        "occurred_at",
        "source_app",
        "org_id",
        "bounce_type",
        "bounce_subtype",
        "click_link",
        "received_at",
        # 019 (first-party measurement), decided: who observed the event
        # (`webhook` / `first_party`) and a coarse boolean computed in memory.
        # Neither can hold PII; the request's IP and user agent are never stored.
        "source",
        "possible_prefetch",
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://map.creatumundo.mx/agenda?token=abc#x", "https://map.creatumundo.mx/agenda"),
        ("HTTPS://Map.CreaTuMundo.MX/Agenda", "https://map.creatumundo.mx/Agenda"),
        ("https://user:pass@map.creatumundo.mx:8443/a/b?c=d", "https://map.creatumundo.mx/a/b"),
        ("https://map.creatumundo.mx", "https://map.creatumundo.mx"),
        (
            "https://auth.madfam.io/api/v1/auth/magic-link/callback?token=abc&next=/",
            "https://auth.madfam.io/api/v1/auth/magic-link/callback",
        ),
        (
            "https://map.creatumundo.mx/alta/0123456789abcdefABCDEF_-0123456789/confirmar",
            "https://map.creatumundo.mx/alta/{redacted}/confirmar",
        ),
        (
            "https://x.test/p/e6cbd51d-0000-4000-8000-000000000001",
            "https://x.test/p/{redacted}",
        ),
        ("mailto:hola@creatumundo.mx", None),
        ("javascript:alert(1)", None),
        ("", None),
        (None, None),
        ("not a url", None),
    ],
)
def test_click_link_sanitization(raw, expected):
    assert sanitize_click_link(raw) == expected
