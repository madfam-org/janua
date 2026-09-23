"""Mandatory CI PostgreSQL proof; opt in locally with a guarded test-only URL."""

import asyncio
import importlib.util
import os
import uuid
from pathlib import Path
from threading import Event
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import AuditLog, Base, OAuthClient, Organization, PaymentMailDispatch, User
from app.services import payment_mail_dispatch as mail
from app.services.payment_mail_auth import MAIL_AUDIENCE, PAYMENT_MAIL_SCOPE, PaymentMailPrincipal

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


def migration():
    path = Path(__file__).resolve().parents[3] / "alembic/versions/017_payment_mail_dispatch.py"
    spec = importlib.util.spec_from_file_location("mail_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(conn, action):
    with Operations.context(MigrationContext.configure(conn)):
        getattr(migration(), action)()


@pytest_asyncio.fixture
async def pg(monkeypatch):
    raw = os.getenv("JANUA_MAIL_TEST_DATABASE_URL")
    if not raw:
        pytest.skip(
            "Set JANUA_MAIL_TEST_DATABASE_URL and LOCAL_DB=yes for isolated PostgreSQL proof"
        )
    url = make_url(raw)
    if (
        os.getenv("LOCAL_DB") != "yes"
        or url.host not in {"127.0.0.1", "localhost"}
        or not url.database
        or not url.database.endswith("_test")
    ):
        pytest.fail("Mail proof requires LOCAL_DB=yes, loopback, and a dedicated *_test database")
    schema = "mail_fixture_" + uuid.uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            tables = [
                table
                for table in Base.metadata.sorted_tables
                if table.name != "payment_mail_dispatches"
            ]
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
            # Actual upgrade, empty downgrade, fresh upgrade and create_all-safe replay.
            await conn.run_sync(migrate, "upgrade")
            await conn.run_sync(migrate, "downgrade")
            await conn.run_sync(migrate, "upgrade")
            await conn.run_sync(migrate, "upgrade")
        org_id, owner_id, client_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with factory.begin() as db:
            db.add(Organization(id=org_id, name="Synthetic Org", slug="fixture-mail"))
            db.add(User(id=owner_id, email="persona01@example.com"))
            await db.flush()
            db.add(
                OAuthClient(
                    id=client_id,
                    organization_id=org_id,
                    created_by=owner_id,
                    client_id="fixture-map-mail",
                    client_secret_hash="fixture-only",
                    client_secret_prefix="fixture",
                    name="Fixture mail",
                    redirect_uris=[],
                    audience=MAIL_AUDIENCE,
                    allowed_scopes=[PAYMENT_MAIL_SCOPE],
                    grant_types=["client_credentials"],
                    is_active=True,
                    is_confidential=True,
                )
            )
        principal = PaymentMailPrincipal("fixture-map-mail", org_id)
        intent = mail.PaymentNoticeIntent(
            command_id=uuid.uuid4(), recipient="persona02@example.com", year=2026, month=9
        )
        envelope = AsyncMock(
            return_value=({"subject": "fixture"}, "fixture-key", "a" * 64, "b" * 64)
        )
        provider = Mock(return_value={"id": "fixture-provider-id"})
        monkeypatch.setattr(mail, "_envelope", envelope)
        monkeypatch.setattr(mail, "send_on_account", provider)
        yield factory, principal, intent, envelope, provider, engine
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            # This schema was generated above in a dedicated synthetic database.
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def dispatch(pg):
    async with pg[0]() as db:
        return await mail.dispatch_payment_notice(db, pg[1], pg[2])


async def test_concurrent_claims_send_once_and_replay_same_receipt(pg):
    entered, release = Event(), Event()

    def provider(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return {"id": "fixture-provider-id"}

    pg[4].side_effect = provider
    first = asyncio.create_task(dispatch(pg))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        second = await asyncio.wait_for(dispatch(pg), timeout=3)
        assert second.delivery_status == "pending"
    finally:
        release.set()
    accepted = await first
    replay = await dispatch(pg)
    assert accepted == replay and accepted.delivery_status == "accepted"
    assert pg[4].call_count == 1
    async with pg[0]() as db:
        assert len((await db.execute(select(PaymentMailDispatch))).scalars().all()) == 1


async def test_two_first_time_preflights_are_serialized_by_database(pg):
    barrier = asyncio.Barrier(2)

    async def prepare(*_):
        await barrier.wait()
        return {"subject": "fixture"}, "fixture-key", "a" * 64, "b" * 64

    pg[3].side_effect = prepare
    results = await asyncio.wait_for(asyncio.gather(dispatch(pg), dispatch(pg)), timeout=8)
    assert all(r.delivery_status in {"accepted", "pending"} for r in results)
    assert results[0].receipt_id == results[1].receipt_id
    assert pg[4].call_count == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE payment_mail_dispatches SET request_hash = repeat('c', 64)",
        "UPDATE payment_mail_dispatches SET command_id = gen_random_uuid()",
        "UPDATE payment_mail_dispatches SET first_attempt_at = now()",
        "UPDATE payment_mail_dispatches SET state = 'pending'",
        "UPDATE payment_mail_dispatches SET provider_message_id = 'different'",
        "DELETE FROM payment_mail_dispatches",
        "TRUNCATE payment_mail_dispatches",
    ],
)
async def test_receipt_and_identity_cannot_be_rewritten_or_erased(pg, statement):
    accepted = await dispatch(pg)
    with pytest.raises(DBAPIError):
        async with pg[0].begin() as db:
            await db.execute(text(statement))
    assert await dispatch(pg) == accepted


async def test_populated_ledger_refuses_downgrade(pg):
    accepted = await dispatch(pg)
    with pytest.raises(RuntimeError, match="Cannot discard"):
        async with pg[5].begin() as conn:
            await conn.run_sync(migrate, "downgrade")
    assert await dispatch(pg) == accepted


async def test_org_mismatch_refused_by_database_even_without_handler(pg):
    await dispatch(pg)
    async with pg[0].begin() as db:
        foreign = Organization(id=uuid.uuid4(), name="Other synthetic org", slug="other-fixture")
        db.add(foreign)
        foreign_id = foreign.id
    with pytest.raises(DBAPIError, match="organization mismatch"):
        async with pg[0].begin() as db:
            await db.execute(
                text("""INSERT INTO payment_mail_dispatches
                SELECT gen_random_uuid(), :org_id, client_id, gen_random_uuid(),
                request_hash, envelope_hash, binding_hash, credential_fingerprint,
                state, attempts, attempt_id, first_attempt_at, lease_until, next_attempt_at,
                accepted_at, provider_message_id, issue, created_at, updated_at
                FROM payment_mail_dispatches"""),
                {"org_id": foreign_id},
            )


async def test_revocation_between_preflight_and_claim_prevents_send(pg):
    async def revoke(*_):
        async with pg[0].begin() as db:
            await db.execute(text("UPDATE oauth_clients SET allowed_scopes = '[]'::jsonb"))
        return {"subject": "fixture"}, "fixture-key", "a" * 64, "b" * 64

    pg[3].side_effect = revoke
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        await dispatch(pg)
    assert error.value.status_code == 403
    pg[4].assert_not_called()
    async with pg[0]() as db:
        assert (await db.execute(select(PaymentMailDispatch))).scalar_one_or_none() is None


async def test_late_worker_cannot_replace_newer_receipt(pg):
    entered, release = Event(), Event()
    calls = 0

    def provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(10)
        return {"id": "fixture-provider-id"}

    pg[4].side_effect = provider
    first = asyncio.create_task(dispatch(pg))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        async with pg[0].begin() as db:
            await db.execute(
                text("UPDATE payment_mail_dispatches SET lease_until = now() - interval '1 second'")
            )
        newer = await dispatch(pg)
        assert newer.delivery_status == "accepted"
    finally:
        release.set()
    assert await first == newer
    async with pg[0]() as db:
        row = (await db.execute(select(PaymentMailDispatch))).scalar_one()
        assert row.attempts == 2
        audit = (
            await db.execute(
                select(AuditLog.details).where(
                    AuditLog.action == "email.payment_notice.late_receipt"
                )
            )
        ).scalar_one()
        assert audit["message_id"] == "fixture-provider-id"
        assert set(audit) == {"attempt_id", "message_id"}


async def test_rolled_back_claim_never_calls_provider(pg):
    from sqlalchemy import event

    async with pg[0]() as db:
        commits = 0

        def fail_claim(_):
            nonlocal commits
            commits += 1
            if commits == 2:
                raise RuntimeError("synthetic commit failure")

        event.listen(db.sync_session, "before_commit", fail_claim)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            await mail.dispatch_payment_notice(db, pg[1], pg[2])
    pg[4].assert_not_called()
    async with pg[0]() as db:
        assert (await db.execute(select(PaymentMailDispatch))).scalar_one_or_none() is None


async def test_lost_receipt_commit_recovers_with_same_provider_key(pg):
    from sqlalchemy import event

    provider_ledger = {}

    def accept(params, credential, *, idempotency_key, send_before):
        provider_ledger.setdefault(idempotency_key, {"id": "fixture-provider-id"})
        return provider_ledger[idempotency_key]

    pg[4].side_effect = accept
    async with pg[0]() as db:
        commits = 0

        def fail_receipt(_):
            nonlocal commits
            commits += 1
            if commits == 3:
                raise RuntimeError("synthetic receipt commit failure")

        event.listen(db.sync_session, "before_commit", fail_receipt)
        with pytest.raises(RuntimeError, match="synthetic receipt commit failure"):
            await mail.dispatch_payment_notice(db, pg[1], pg[2])
    async with pg[0].begin() as db:
        row = (await db.execute(select(PaymentMailDispatch))).scalar_one()
        assert row.state == "sending" and row.provider_message_id is None
        await db.execute(
            text("UPDATE payment_mail_dispatches SET lease_until = now() - interval '1 second'")
        )
    assert (await dispatch(pg)).delivery_status == "accepted"
    assert pg[4].call_count == 2 and len(provider_ledger) == 1
    assert pg[4].call_args_list[0] == pg[4].call_args_list[1]


async def test_sql_cannot_insert_a_preaccepted_receipt(pg):
    await dispatch(pg)
    with pytest.raises(DBAPIError, match="first sending claim"):
        async with pg[0].begin() as db:
            await db.execute(
                text("""INSERT INTO payment_mail_dispatches
                SELECT gen_random_uuid(), organization_id, client_id, gen_random_uuid(),
                request_hash, envelope_hash, binding_hash, credential_fingerprint,
                state, attempts, attempt_id, first_attempt_at, lease_until, next_attempt_at,
                accepted_at, provider_message_id, issue, created_at, updated_at
                FROM payment_mail_dispatches""")
            )
