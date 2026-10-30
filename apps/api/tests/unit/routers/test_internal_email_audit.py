"""Bounded exact-org/source metadata reads, privacy allowlist and verified outcomes."""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.email_event import EmailEvent
from app.models.email_send_audit import EmailSendAudit

URL = "/api/v1/internal/email/audit"
ORG = uuid.uuid4()
OTHER = uuid.uuid4()
KEY = "synthetic-internal-audit-key"
START = datetime(2026, 10, 28)
END = datetime(2026, 10, 30)


@pytest_asyncio.fixture
async def store(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def get_session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = get_session
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", KEY)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield factory, http
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


def params(**changes):
    return {
        "org_id": str(ORG),
        "source_app": "crea-map",
        "from": START.isoformat() + "Z",
        "to": END.isoformat() + "Z",
        **changes,
    }


async def seed(
    factory,
    *,
    organization=ORG,
    source="crea-map",
    upstream=None,
    state="accepted",
    at=START + timedelta(hours=1),
):
    identity = uuid.uuid4()
    provider = "provider-" + str(identity) if state == "accepted" else None
    async with factory() as db:
        db.add(
            EmailSendAudit(
                id=identity,
                org_id=str(organization),
                source_app=source,
                upstream_audit_id=upstream,
                message_kind="magic_login",
                trigger_kind="map_login_request",
                provenance="registered_map_login",
                state=state,
                created_at=at,
                attempted_at=at if provider else None,
                accepted_at=at if provider else None,
                provider_message_id=provider,
            )
        )
        await db.commit()
    return identity, provider


async def test_auth_and_required_scope(store):
    _, http = store
    assert (await http.get(URL, params=params())).status_code == 422
    assert (
        await http.get(URL, params=params(), headers={"X-Internal-API-Key": "wrong"})
    ).status_code == 401
    for missing in ["org_id", "source_app", "from", "to"]:
        p = params()
        p.pop(missing)
        assert (
            await http.get(URL, params=p, headers={"X-Internal-API-Key": KEY})
        ).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"from": "2026-10-28T00:00:00"},
        {"from": "2026-10-28T01:00:00+01:00"},
        {"from": "2026-10-01T00:00:00Z"},
        {"to": "2026-10-27T00:00:00Z"},
        {"limit": 201},
        {"limit": 0},
        {"folio": "not-a-uuid"},
        {"org_id": "not-a-uuid"},
    ],
)
async def test_invalid_unbounded_or_naive_queries_are_refused(store, change):
    _, http = store
    assert (
        await http.get(URL, params=params(**change), headers={"X-Internal-API-Key": KEY})
    ).status_code == 422


async def test_exact_verified_receipts_scope_privacy_and_partial_history(store):
    factory, http = store
    upstream = uuid.uuid4()
    identity, provider = await seed(factory, upstream=upstream)
    await seed(factory, organization=OTHER)
    await seed(factory, source="other-product")
    await seed(factory, at=END)  # exclusive upper bound
    async with factory() as db:
        for kind in ["email.sent", "email.delivered"]:
            db.add(
                EmailEvent(
                    provider="resend",
                    cuenta="ctm",
                    svix_id=str(uuid.uuid4()),
                    email_id=provider,
                    event_type=kind,
                    occurred_at=START + timedelta(hours=2),
                    source_app="crea-map",
                    org_id=str(ORG),
                    mail_audit_id=str(identity),
                    source="webhook",
                )
            )
        await db.commit()
    response = await http.get(URL, params=params(), headers={"X-Internal-API-Key": KEY})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] == {
        "total": 1,
        "provider_accepted": 1,
        "verified_sent": 1,
        "verified_delivered": 1,
        "states": {"accepted": 1},
    }
    assert (
        body["coverage"] == "recorded_intents_only_no_backfill"
        and body["history_complete"] is False
    )
    assert body["org_id"] == str(ORG) and body["source_app"] == "crea-map"
    row = body["records"][0]
    assert row["audit_id"] == str(identity) and row["map_audit_id"] == str(upstream)
    assert row["provider_message_id"] == provider and row["verified_delivered_at"].endswith("Z")
    forbidden = {
        "email",
        "recipient",
        "subject",
        "body",
        "html",
        "text",
        "token",
        "redirect_url",
        "magic_link_id",
        "credential_fingerprint",
    }
    assert not forbidden.intersection(row)
    assert len(body["records"]) == 1
    for folio in [identity, upstream]:
        found = await http.get(
            URL, params=params(folio=str(folio)), headers={"X-Internal-API-Key": KEY}
        )
        assert found.json()["records"][0]["audit_id"] == str(identity)


async def test_limit_is_bounded_but_summary_covers_full_recorded_window(store):
    factory, http = store
    for _ in range(3):
        await seed(factory, state="pending")
    response = await http.get(URL, params=params(limit=1), headers={"X-Internal-API-Key": KEY})
    body = response.json()
    assert len(body["records"]) == 1 and body["has_more"] is True
    assert body["summary"]["total"] == 3
    assert body["summary"]["provider_accepted"] == body["summary"]["verified_delivered"] == 0
    assert body["records"][0]["resolved_at"] is None


async def test_wrong_org_or_unverified_event_does_not_claim_delivery(store):
    factory, http = store
    identity, provider = await seed(factory)
    async with factory() as db:
        db.add(
            EmailEvent(
                provider="resend",
                cuenta="ctm",
                svix_id=str(uuid.uuid4()),
                email_id=provider,
                event_type="email.delivered",
                occurred_at=START,
                source_app="crea-map",
                org_id=str(OTHER),
                mail_audit_id=str(identity),
                source="webhook",
            )
        )
        await db.commit()
    body = (await http.get(URL, params=params(), headers={"X-Internal-API-Key": KEY})).json()
    assert (
        body["summary"]["verified_delivered"] == 0
        and body["records"][0]["verified_delivered_at"] is None
    )


async def test_native_command_lookup_and_org_scope_are_explicit(store):
    from app.models import OAuthClient, Organization, User
    from app.models.email_dispatch import PaymentMailDispatch

    factory, http = store
    receipt, command, upstream, owner, client = [uuid.uuid4() for _ in range(5)]
    async with factory() as db:
        db.add(Organization(id=ORG, name="Synthetic audit", slug="synthetic-audit"))
        db.add(User(id=owner, email="synthetic-owner@example.com"))
        await db.flush()
        db.add(
            OAuthClient(
                id=client,
                organization_id=ORG,
                created_by=owner,
                client_id="synthetic-audit",
                name="Synthetic",
                client_secret_hash="not-a-live-secret",
                client_secret_prefix="synthetic",
                redirect_uris=[],
                is_active=True,
                is_confidential=True,
            )
        )
        await db.flush()
        db.add(
            PaymentMailDispatch(
                id=receipt,
                command_id=command,
                organization_id=ORG,
                client_id=client,
                map_audit_id=str(upstream),
                state="accepted",
                attempts=1,
                created_at=START,
                updated_at=START,
                first_attempt_at=START,
                accepted_at=START,
                provider_message_id="provider-native-synthetic",
                request_hash="a" * 64,
                envelope_hash="b" * 64,
                binding_hash="c" * 64,
                credential_fingerprint="d" * 64,
            )
        )
        await db.commit()
    for folio in [receipt, command, upstream]:
        response = await http.get(
            URL, params=params(folio=str(folio)), headers={"X-Internal-API-Key": KEY}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["summary"]["total"] == 1
        assert body["records"][0]["command_id"] == str(command)
        assert body["records"][0]["provenance"] == "verified_mail_client"
    response = await http.get(
        URL,
        params=params(org_id=str(OTHER), folio=str(command)),
        headers={"X-Internal-API-Key": KEY},
    )
    assert response.json()["records"] == []


async def test_provider_window_includes_delivery_for_older_intent_without_new_request(store):
    factory, http = store
    identity, provider = await seed(factory, at=START - timedelta(days=1))
    async with factory() as db:
        db.add(
            EmailEvent(
                provider="resend",
                cuenta="ctm",
                svix_id=str(uuid.uuid4()),
                email_id=provider,
                event_type="email.sent",
                occurred_at=START - timedelta(hours=1),
                source_app="crea-map",
                org_id=str(ORG),
                mail_audit_id=str(identity),
                source="webhook",
            )
        )
        db.add(
            EmailEvent(
                provider="resend",
                cuenta="ctm",
                svix_id=str(uuid.uuid4()),
                email_id=provider,
                event_type="email.delivered",
                occurred_at=START + timedelta(hours=1),
                source_app="crea-map",
                org_id=str(ORG),
                mail_audit_id=str(identity),
                source="webhook",
            )
        )
        await db.commit()
    for extra in [{}, {"folio": str(identity)}]:
        response = await http.get(URL, params=params(**extra), headers={"X-Internal-API-Key": KEY})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["summary"]["total"] == 0 and body["records"] == []
        assert body["provider_events_in_window"] == {
            "verified_sent": 0,
            "verified_delivered": 1,
            "events_for_older_intents": 1,
        }
