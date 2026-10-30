"""Exact intent → provider receipt → signed event joins, with synthetic data only."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.email_event import EmailEvent
from app.models.email_send_audit import EmailSendAudit
from app.services import email_send_audit as audit
from app.services.email_events import feed_item, parse_event, record_event


@pytest_asyncio.fixture
async def store(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.database.AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


async def row_for(factory, identity):
    async with factory() as session:
        return await session.get(EmailSendAudit, identity)


async def test_provider_call_requires_durable_intent_and_exact_receipt(store):
    upstream = uuid.uuid4()
    called = []

    async def provider():
        current = audit.current_audit()
        row = await row_for(store, current.id)
        assert row.state == "sending" and row.attempted_at is not None
        called.append(current.id)
        assert audit.audit_tags() == [
            {"name": "mail_audit_id", "value": str(current.id)},
            {"name": "message_kind", "value": "notification"},
            {"name": "trigger_kind", "value": "internal_api"},
            {"name": "source_app", "value": "crea-map"},
            {"name": "map_audit_id", "value": str(upstream)},
        ]
        await audit.accepted_receipt("provider-synthetic-001")
        return "accepted"

    assert (
        await audit.audited_internal_send(
            provider, source_app="crea-map", org_id="org-synthetic", upstream_audit_id=str(upstream)
        )
        == "accepted"
    )
    row = await row_for(store, called[0])
    assert row.state == "accepted"
    assert row.provider_message_id == "provider-synthetic-001"
    assert row.accepted_at is not None
    assert row.upstream_audit_id == upstream
    assert audit.current_audit() is None
    async with store() as session:
        event = parse_event(
            {
                "type": "email.delivered",
                "data": {
                    "email_id": row.provider_message_id,
                    "created_at": "2026-10-30T01:00:00Z",
                    "tags": {
                        "source_app": "crea-map",
                        "org_id": "org-synthetic",
                        "mail_audit_id": str(row.id),
                    },
                },
            }
        )
        assert await record_event(session, "ctm", "svix-synthetic-001", event)
        await session.commit()
        stored = (await session.execute(select(EmailEvent))).scalar_one()
        item = feed_item(stored)
        assert item["mail_audit_id"] == str(row.id)
        assert item["map_audit_id"] == str(upstream)
        assert item["message_kind"] == "notification"
        assert item["trigger_kind"] == "internal_api"
        assert not {"to", "email", "subject", "body", "token"}.intersection(item)


async def test_unavailable_audit_store_blocks_map_before_provider(monkeypatch):
    monkeypatch.setattr(
        audit,
        "new_internal_intent",
        AsyncMock(side_effect=RuntimeError("synthetic database refusal")),
    )
    provider = AsyncMock()
    with pytest.raises(RuntimeError, match="synthetic database refusal"):
        await audit.audited_internal_send(provider, source_app="crea-map")
    provider.assert_not_awaited()
    # Other products keep their existing transport contract.
    await audit.audited_internal_send(provider, source_app="another-product")
    provider.assert_awaited_once()


async def test_missing_receipt_is_unknown_and_no_scope_can_resend(store):
    identity = await audit.new_internal_intent(source_app="crea-map")
    async with audit.send_scope(identity):
        with pytest.raises(ValueError, match="acceptance receipt"):
            await audit.accepted_receipt(None)
    row = await row_for(store, identity)
    assert row.state == "unknown" and row.provider_message_id is None
    with pytest.raises(ValueError, match="not pending"):
        async with audit.send_scope(identity):
            pytest.fail("no automatic retry is authorized")


async def test_signed_event_can_repair_missing_post_send_receipt(store):
    identity = await audit.new_internal_intent(
        source_app="crea-map", org_id="org-synthetic", message_kind="notification"
    )
    async with audit.send_scope(identity):
        pass  # lost provider response: durable attempted intent remains
    async with store() as session:
        event = parse_event(
            {
                "type": "email.sent",
                "data": {
                    "email_id": "provider-synthetic-recovered",
                    "created_at": "2026-10-30T01:00:00Z",
                    "tags": {
                        "source_app": "crea-map",
                        "org_id": "org-synthetic",
                        "mail_audit_id": str(identity),
                        "message_kind": "forged-kind",
                    },
                },
            }
        )
        assert await record_event(session, "ctm", "svix-synthetic-recovered", event)
        await session.commit()
    row = await row_for(store, identity)
    assert row.state == "accepted" and row.provider_message_id == "provider-synthetic-recovered"
    async with store() as session:
        stored = (await session.execute(select(EmailEvent))).scalar_one()
        assert stored.message_kind == "notification"  # canonical intent wins


@pytest.mark.parametrize(
    "mismatch", ["unknown-id", "wrong-org", "wrong-app", "different-provider-id", "not-attempted"]
)
async def test_unmatched_tag_metadata_never_claims_a_durable_join(store, mismatch):
    identity = await audit.new_internal_intent(source_app="crea-map", org_id="org-synthetic")
    if mismatch != "not-attempted":
        async with audit.send_scope(identity):
            await audit.accepted_receipt("provider-synthetic-canonical")
    async with store() as session:
        event = parse_event(
            {
                "type": "email.delivered",
                "data": {
                    "email_id": "different-provider-id"
                    if mismatch == "different-provider-id"
                    else "provider-synthetic-canonical",
                    "tags": {
                        "source_app": "other" if mismatch == "wrong-app" else "crea-map",
                        "org_id": "other" if mismatch == "wrong-org" else "org-synthetic",
                        "mail_audit_id": str(
                            uuid.uuid4() if mismatch == "unknown-id" else identity
                        ),
                    },
                },
            }
        )
        await record_event(session, "ctm", "svix-synthetic-mismatch", event)
        await session.commit()
        stored = (await session.execute(select(EmailEvent))).scalar_one()
        assert stored.mail_audit_id is None and stored.message_kind is None


def test_audit_schema_cannot_store_message_or_recipient_content():
    assert not {
        "email",
        "recipient",
        "subject",
        "body",
        "html",
        "text",
        "token",
        "redirect_url",
    }.intersection(EmailSendAudit.__table__.columns.keys())
    assert audit.uuid_metadata("caller text is never a correlation id") is None
    assert not audit.is_map_destination("https://map.creatumundo.mx.attacker.invalid/callback")
    assert not audit.is_map_destination("https://erp.creatumundo.mx/callback")
    assert audit.is_map_destination("https://map.creatumundo.mx/api/auth/magic-verify")


async def test_request_audit_without_issuance_cannot_send(store):
    identity = await audit.new_internal_intent(source_app="crea-map", message_kind="magic_login")
    with pytest.raises(ValueError, match="no durable issuance"):
        async with audit.send_scope(identity):
            pytest.fail("a request audit is not a login issuance")
    assert (await row_for(store, identity)).state == "pending"


async def test_native_payment_event_joins_exact_command_receipt_and_map_attempt(store):
    from app.models import OAuthClient, Organization, User
    from app.models.email_dispatch import PaymentMailDispatch

    receipt, command, organization, upstream, client, owner = [uuid.uuid4() for _ in range(6)]
    async with store() as session:
        session.add(Organization(id=organization, name="Synthetic audit", slug="synthetic-audit"))
        session.add(User(id=owner, email="synthetic-owner@example.com"))
        await session.flush()
        session.add(
            OAuthClient(
                id=client,
                organization_id=organization,
                created_by=owner,
                client_id="synthetic-audit-mail",
                client_secret_hash="synthetic-not-a-secret",
                client_secret_prefix="synthetic",
                name="Synthetic audit mail",
                redirect_uris=[],
                is_active=True,
                is_confidential=True,
            )
        )
        await session.flush()
        session.add(
            PaymentMailDispatch(
                id=receipt,
                command_id=command,
                organization_id=organization,
                client_id=client,
                request_hash="a" * 64,
                envelope_hash="b" * 64,
                binding_hash="c" * 64,
                credential_fingerprint="d" * 64,
                state="accepted",
                attempts=1,
                provider_message_id="provider-native-001",
                accepted_at=datetime.utcnow(),
                map_audit_id=str(upstream),
            )
        )
        await session.commit()
        event = parse_event(
            {
                "type": "email.delivered",
                "data": {
                    "email_id": "provider-native-001",
                    "tags": {
                        "source_app": "crea-map",
                        "org_id": str(organization),
                        "payment_command_id": str(command),
                        "map_audit_id": "untrusted-tag-is-never-authority",
                    },
                },
            }
        )
        await record_event(session, "ctm", "svix-native-001", event)
        await session.commit()
        stored = (await session.execute(select(EmailEvent))).scalar_one()
        item = feed_item(stored)
        assert item["mail_audit_id"] == str(receipt)
        assert item["command_id"] == str(command)
        assert item["map_audit_id"] == str(upstream)
        assert item["message_kind"] == "payment" and item["trigger_kind"] == "payment_command"


async def test_verified_webhook_before_http_receipt_is_idempotent(store):
    identity = await audit.new_internal_intent(source_app="crea-map", org_id="synthetic-org")
    async with audit.send_scope(identity):
        async with store() as session:
            event = parse_event(
                {
                    "type": "email.sent",
                    "data": {
                        "email_id": "provider-webhook-first",
                        "tags": {
                            "source_app": "crea-map",
                            "org_id": "synthetic-org",
                            "mail_audit_id": str(identity),
                        },
                    },
                }
            )
            await record_event(session, "ctm", "svix-webhook-first", event)
            await session.commit()
        await audit.accepted_receipt("provider-webhook-first")
        with pytest.raises(ValueError, match="acceptance could not be persisted"):
            await audit.accepted_receipt("different-provider-id")
    assert (await row_for(store, identity)).provider_message_id == "provider-webhook-first"
