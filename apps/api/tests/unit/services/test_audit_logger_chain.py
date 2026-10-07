"""AuditLogger against the real AuditLog model (in-memory SQLite).

What these pin, with no mocks between the service and the table:

- ``log()`` writes exactly one ``audit_logs`` row, with ``action`` and
  ``event_type`` set from the event, the tenant, the hash chain, and
  ``created_at`` as the entry's timestamp.
- Only UUIDs go in ``user_id`` / ``resource_id``; any other reference is kept in
  ``details`` under one key.
- Each tenant has its own chain; ``verify_integrity`` passes on an untouched
  chain and reports the first tampered, reordered or missing entry.
- ``export_logs`` returns the stored rows, with encrypted details decrypted.
- Rows written by other code (``action`` only) are untouched and never read as
  part of a chain.
- Session ownership: over a caller's session ``log()`` never commits, so the
  audit row commits or rolls back with the caller's work; a logger that owns
  its session (``with_own_session``) commits each entry itself.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import event as sa_event
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.config import settings
from app.core.encryption import FieldEncryptor
from app.models import AuditLog, Base, User
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import (
    AUDIT_CONTEXT_KEY,
    AUDIT_STORE_FAILED,
    IDENTITY_REF_KEY,
    RESOURCE_REF_KEY,
    AuditEventType,
    AuditLogger,
    decode_details,
)

TENANT_A = "tenant-a"
# What ``log()`` adds to ``details`` for an entry with default severity.
INFO = {AUDIT_CONTEXT_KEY: {"severity": "info"}}
TENANT_B = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "R2_AUDIT_BUCKET", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


def sqlite_with_real_transactions(engine):
    """Make SQLite transactions and SAVEPOINTs behave as on PostgreSQL.

    The sqlite3 driver only opens a transaction before DML, so a SAVEPOINT
    issued first becomes the outermost transaction and releasing it commits.
    SQLAlchemy's documented fix: turn off the driver's own handling and emit
    BEGIN when SQLAlchemy begins.
    """

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _no_driver_transactions(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @sa_event.listens_for(engine.sync_engine, "begin")
    def _begin(connection):
        connection.exec_driver_sql("BEGIN")

    return engine


@pytest.fixture
async def session():
    engine = sqlite_with_real_transactions(
        create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as db:
            yield db
    finally:
        await engine.dispose()


@pytest.fixture
async def factory(tmp_path):
    """Sessions over one file database, each with its own connection."""
    engine = sqlite_with_real_transactions(
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _count(factory, model, *where) -> int:
    async with factory() as fresh:
        query = select(model)
        for clause in where:
            query = query.where(clause)
        return len((await fresh.execute(query)).scalars().all())


@pytest.fixture
async def user(session) -> User:
    person = User(id=uuid.uuid4(), email="person@example.com")
    session.add(person)
    await session.commit()
    return person


async def _rows(session, tenant=None):
    query = select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)
    if tenant is not None:
        query = query.where(AuditLog.tenant_id == tenant)
    return list((await session.execute(query)).scalars().all())


class TestLogStoresOneRow:
    async def test_columns(self, session, user):
        resource = uuid.uuid4()
        before = datetime.utcnow()

        event_id = await AuditLogger(session).log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id=TENANT_A,
            identity_id=str(user.id),
            resource_type="user",
            resource_id=str(resource).upper(),
            details={"field": "name", "at": before},
            ip_address="192.0.2.10",
            user_agent="pytest",
        )

        rows = await _rows(session)
        assert len(rows) == 1
        row = rows[0]
        assert str(row.id) == event_id
        assert row.action == "user.update"
        assert row.event_type == "user.update"
        assert row.tenant_id == TENANT_A
        assert row.user_id == user.id
        assert row.resource_type == "user"
        assert row.resource_id == resource
        assert row.details == {"field": "name", "at": str(before), **INFO}
        assert row.ip_address == "192.0.2.10"
        assert row.user_agent == "pytest"
        assert row.previous_hash is None
        assert len(row.current_hash) == 64
        assert before <= row.created_at <= datetime.utcnow()

    async def test_plain_string_event_type_is_stored_as_given(self, session):
        await AuditLogger(session).log(event_type="privacy.settings_updated", tenant_id=TENANT_A)

        (row,) = await _rows(session)
        assert row.action == row.event_type == "privacy.settings_updated"

    async def test_non_uuid_resource_goes_to_details(self, session):
        await AuditLogger(session).log(
            event_type=AuditEventType.SOC2_ACCESS_GRANTED,
            tenant_id=TENANT_A,
            resource_type="access_control",
            resource_id="/api/v1/admin",
            details={"action": "granted"},
        )

        (row,) = await _rows(session)
        assert row.resource_id is None
        assert row.details == {"action": "granted", RESOURCE_REF_KEY: "/api/v1/admin", **INFO}

    async def test_non_uuid_identity_goes_to_details(self, session):
        await AuditLogger(session).log(
            event_type=AuditEventType.POLICY_EVALUATE,
            tenant_id=TENANT_A,
            identity_id="service:hcm",
        )

        (row,) = await _rows(session)
        assert row.user_id is None
        assert row.details == {IDENTITY_REF_KEY: "service:hcm", **INFO}

    @pytest.mark.parametrize("severity", ["info", "low", "medium", "high", "critical"])
    async def test_every_severity_is_stored_when_logged(self, session, severity):
        await AuditLogger(session).log(
            event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A, severity=severity
        )

        assert len(await _rows(session)) == 1

    async def test_rows_written_by_other_code_are_untouched(self, session):
        legacy = AuditLog(action="oauth_client.create", resource_type="oauth_client")
        session.add(legacy)
        await session.commit()

        audit = AuditLogger(session)
        await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)

        rows = await _rows(session)
        assert len(rows) == 2
        other = next(r for r in rows if r.id == legacy.id)
        assert other.tenant_id is None and other.current_hash is None
        assert other.action == "oauth_client.create"
        assert (await audit.verify_integrity(TENANT_A))["count"] == 1

    async def test_a_failed_store_raises_is_logged_and_leaves_the_session_usable(
        self, session, monkeypatch
    ):
        errors = []
        monkeypatch.setattr(
            audit_logger_module.logger,
            "error",
            lambda *args, **kwargs: errors.append(kwargs.get("code")),
        )
        await AuditLogger(session).log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
        (first,) = await _rows(session)
        # The caller's own, not yet committed, work.
        pending = User(id=uuid.uuid4(), email="pending@example.com")
        session.add(pending)
        await session.flush()

        # A second entry with the same id violates the primary key.
        monkeypatch.setattr(audit_logger_module.uuid, "uuid4", lambda: first.id)
        with pytest.raises(IntegrityError):
            await AuditLogger(session).log(
                event_type=AuditEventType.AUTH_SIGNOUT, tenant_id=TENANT_A
            )
        monkeypatch.undo()

        assert errors == [AUDIT_STORE_FAILED]
        # Only the SAVEPOINT rolled back: the caller's work and the first entry
        # are still in its transaction and commit with it.
        session.add(User(id=uuid.uuid4(), email="after@example.com"))
        await session.commit()
        assert len(await _rows(session)) == 1
        assert (await session.get(User, pending.id)) is not None


class TestSessionOwnership:
    async def test_a_caller_rollback_discards_the_business_row_and_the_audit_row(self, factory):
        async with factory() as db:
            person = User(id=uuid.uuid4(), email="person@example.com")
            db.add(person)
            await db.flush()
            await AuditLogger(db).log(
                event_type=AuditEventType.USER_CREATE,
                tenant_id=TENANT_A,
                resource_type="user",
                resource_id=str(person.id),
            )
            await db.rollback()

        assert await _count(factory, User) == 0
        assert await _count(factory, AuditLog) == 0

    async def test_b_a_caller_commit_keeps_both_and_the_chain(self, factory):
        people = []
        for i in range(3):
            async with factory() as db:
                person = User(id=uuid.uuid4(), email=f"person{i}@example.com")
                db.add(person)
                await db.flush()
                audit = AuditLogger(db)
                assert audit.owns_session is False
                await audit.log(
                    event_type=AuditEventType.USER_CREATE,
                    tenant_id=TENANT_A,
                    resource_type="user",
                    resource_id=str(person.id),
                )
                await db.commit()
                people.append(person.id)

        assert await _count(factory, User) == 3
        async with factory() as fresh:
            rows = await _rows(fresh, TENANT_A)
            assert [r.resource_id for r in rows] == people
            result = await AuditLogger(fresh).verify_integrity(TENANT_A)
        assert result["valid"] is True and result["count"] == 3

    async def test_nothing_is_committed_for_the_caller(self, factory):
        """Without the caller's commit, closing its session drops the row."""
        async with factory() as db:
            await AuditLogger(db).log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)

        assert await _count(factory, AuditLog) == 0

    async def test_c_a_logger_owned_session_commits_on_its_own(self, factory):
        async with AuditLogger.with_own_session(factory) as audit:
            assert audit.owns_session is True
            await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
            await audit.log(event_type=AuditEventType.AUTH_SIGNOUT, tenant_id=TENANT_A)

        assert await _count(factory, AuditLog) == 2
        async with factory() as fresh:
            assert (await AuditLogger(fresh).verify_integrity(TENANT_A))["valid"] is True

    async def test_a_logger_owned_failure_rolls_back_and_raises(self, factory, monkeypatch):
        errors = []
        monkeypatch.setattr(
            audit_logger_module.logger,
            "error",
            lambda *args, **kwargs: errors.append(kwargs.get("code")),
        )
        async with AuditLogger.with_own_session(factory) as audit:
            monkeypatch.setattr(audit.db, "commit", _raise(RuntimeError("database unavailable")))
            with pytest.raises(RuntimeError):
                await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)

        assert errors == [AUDIT_STORE_FAILED]
        assert await _count(factory, AuditLog) == 0


class TestArchiveWaitsForTheCallersCommit:
    @pytest.fixture
    def r2(self):
        return _CapturingR2({})

    async def test_archived_only_after_the_caller_commits(self, factory, r2):
        with _audit_bucket("example-audit-archive"):
            async with factory() as db:
                audit = AuditLogger(db, r2_client=r2)
                audit._flush_task = object()  # flush by hand below
                await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
                assert audit.buffer == []

                await db.commit()
                assert len(audit.buffer) == 1

                await audit._flush_buffer()
        assert json.loads(r2.captured["Body"])["count"] == 1

    async def test_nothing_is_archived_after_a_rollback(self, factory, r2):
        with _audit_bucket("example-audit-archive"):
            async with factory() as db:
                audit = AuditLogger(db, r2_client=r2)
                audit._flush_task = object()
                await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
                await db.rollback()
                await audit._flush_buffer()

                # A later commit of other work does not bring it back.
                db.add(User(id=uuid.uuid4(), email="later@example.com"))
                await db.commit()
                await audit._flush_buffer()

        assert audit.buffer == [] and audit._awaiting_commit == []
        assert r2.captured == {}

    async def test_a_savepoint_inside_the_caller_does_not_release_entries(self, factory, r2):
        with _audit_bucket("example-audit-archive"):
            async with factory() as db:
                audit = AuditLogger(db, r2_client=r2)
                audit._flush_task = object()
                await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
                # The second log() opens and releases its own SAVEPOINT.
                await audit.log(event_type=AuditEventType.AUTH_SIGNOUT, tenant_id=TENANT_A)
                assert audit.buffer == []
                await db.commit()
                assert len(audit.buffer) == 2

    async def test_the_periodic_flush_waits_for_the_commit(self, factory, r2):
        with _audit_bucket("example-audit-archive"):
            async with factory() as db:
                audit = AuditLogger(db, r2_client=r2)
                audit.flush_interval = 0
                await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
                task = audit._flush_task
                assert task is not None
                await asyncio.sleep(0.05)
                assert r2.captured == {} and not task.done()

                await db.commit()
                await asyncio.wait_for(task, 5)

        assert json.loads(r2.captured["Body"])["count"] == 1
        assert audit._flush_task is None


def _raise(error):
    async def _fail(*args, **kwargs):
        raise error

    return _fail


class TestChain:
    async def test_entries_link_per_tenant(self, session):
        audit = AuditLogger(session)
        for tenant in (TENANT_A, TENANT_B, TENANT_A, TENANT_A, TENANT_B):
            await audit.log(event_type=AuditEventType.USER_UPDATE, tenant_id=tenant)

        for tenant, length in ((TENANT_A, 3), (TENANT_B, 2)):
            rows = await _rows(session, tenant)
            assert len(rows) == length
            assert rows[0].previous_hash is None
            for earlier, later in zip(rows, rows[1:]):
                assert later.previous_hash == earlier.current_hash
                assert later.created_at > earlier.created_at

    async def test_each_logger_continues_the_stored_chain(self, session):
        """Routers build one AuditLogger per request; the chain spans them."""
        for _ in range(3):
            await AuditLogger(session).log(
                event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A
            )

        rows = await _rows(session, TENANT_A)
        assert [r.previous_hash for r in rows[1:]] == [r.current_hash for r in rows[:-1]]

    async def test_created_at_increases_even_when_the_clock_does_not(self, session, monkeypatch):
        frozen = datetime(2026, 9, 30, 12, 0, 0)

        class _Frozen(datetime):
            @classmethod
            def utcnow(cls):
                return frozen

        monkeypatch.setattr(audit_logger_module, "datetime", _Frozen)
        audit = AuditLogger(session)
        for _ in range(3):
            await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_A)
        monkeypatch.undo()

        rows = await _rows(session, TENANT_A)
        assert [r.created_at for r in rows] == [
            frozen,
            frozen + timedelta(microseconds=1),
            frozen + timedelta(microseconds=2),
        ]
        assert (await AuditLogger(session).verify_integrity(TENANT_A))["valid"] is True


class TestVerifyIntegrity:
    @pytest.fixture
    async def chain(self, session, user):
        audit = AuditLogger(session)
        for i in range(4):
            await audit.log(
                event_type=AuditEventType.USER_UPDATE,
                tenant_id=TENANT_A,
                identity_id=str(user.id),
                resource_type="user",
                resource_id=str(uuid.uuid4()),
                details={"step": i},
            )
        await audit.log(event_type=AuditEventType.USER_UPDATE, tenant_id=TENANT_B)
        return audit

    async def test_untouched_chain_is_valid(self, chain):
        result = await chain.verify_integrity(TENANT_A)

        assert result["valid"] is True
        assert result["count"] == 4
        assert result["broken_at"] is None
        assert (await chain.verify_integrity(TENANT_B))["valid"] is True

    async def test_unknown_tenant_has_nothing_to_verify(self, chain):
        result = await chain.verify_integrity("no-such-tenant")

        assert result == {"valid": True, "message": "No logs found for verification", "count": 0}

    @pytest.mark.parametrize(
        "column, value",
        [
            ("event_type", "user.delete"),
            ("resource_type", "organization"),
            ("resource_id", uuid.uuid4()),
            ("user_id", None),
            ("created_at", datetime(2026, 1, 1, 0, 0, 0, 1)),
        ],
    )
    async def test_a_tampered_row_is_reported(self, session, chain, column, value):
        rows = await _rows(session, TENANT_A)
        await session.execute(
            update(AuditLog).where(AuditLog.id == rows[2].id).values({column: value})
        )
        await session.commit()

        result = await chain.verify_integrity(TENANT_A)

        assert result["valid"] is False
        assert result["broken_at"] is not None

    async def test_a_rewritten_hash_breaks_the_next_link(self, session, chain):
        rows = await _rows(session, TENANT_A)
        await session.execute(
            update(AuditLog)
            .where(AuditLog.id == rows[1].id)
            .values(event_type="user.delete", current_hash="0" * 64)
        )
        await session.commit()

        result = await chain.verify_integrity(TENANT_A)

        assert result["valid"] is False
        assert result["broken_at"] == 1

    async def test_a_deleted_row_is_reported(self, session, chain):
        rows = await _rows(session, TENANT_A)
        await session.delete(rows[1])
        await session.commit()

        result = await chain.verify_integrity(TENANT_A)

        assert result["valid"] is False
        assert result["broken_at"] == 1

    async def test_a_deleted_first_row_is_reported(self, session, chain):
        rows = await _rows(session, TENANT_A)
        await session.delete(rows[0])
        await session.commit()

        result = await chain.verify_integrity(TENANT_A)

        assert result["valid"] is False
        assert result["broken_at"] == 0

    async def test_a_window_starting_mid_chain_verifies(self, session, chain):
        rows = await _rows(session, TENANT_A)

        result = await chain.verify_integrity(TENANT_A, start_date=rows[1].created_at)

        assert result["valid"] is True
        assert result["count"] == 3


class TestExport:
    async def test_returns_the_stored_rows(self, session, user):
        audit = AuditLogger(session)
        resource = uuid.uuid4()
        await audit.log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id=TENANT_A,
            identity_id=str(user.id),
            resource_type="user",
            resource_id=str(resource),
            details={"field": "name"},
            ip_address="192.0.2.10",
        )
        await audit.log(
            event_type=AuditEventType.SOC2_ACCESS_GRANTED,
            tenant_id=TENANT_A,
            resource_id="/api/v1/admin",
        )
        await audit.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id=TENANT_B)
        rows = await _rows(session, TENANT_A)

        captured = {}
        audit.r2_client = _CapturingR2(captured)
        settings_bucket = "example-audit-archive"
        with _audit_bucket(settings_bucket):
            url = await audit.export_logs(
                TENANT_A, datetime.utcnow() - timedelta(hours=1), datetime.utcnow()
            )

        assert url == "https://r2.example/presigned"
        exported = json.loads(captured["Body"])
        assert exported["count"] == 2
        first, second = exported["logs"]
        assert first == {
            "event_id": str(rows[0].id),
            "event_type": "user.update",
            "identity_id": str(user.id),
            "resource_type": "user",
            "resource_id": str(resource),
            "details": {"field": "name", **INFO},
            "ip_address": "192.0.2.10",
            "user_agent": None,
            "timestamp": rows[0].created_at.isoformat(),
            "hash": rows[0].current_hash,
            "previous_hash": None,
        }
        assert second["details"] == {RESOURCE_REF_KEY: "/api/v1/admin", **INFO}
        assert second["previous_hash"] == first["hash"]


class TestEncryptedDetails:
    @pytest.fixture
    def encryption(self, monkeypatch):
        key = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", True)
        monkeypatch.setattr(settings, "FIELD_ENCRYPTION_KEY", key, raising=False)
        monkeypatch.setattr(FieldEncryptor, "_instance", None)
        yield
        FieldEncryptor._instance = None

    async def test_stored_encrypted_and_round_trips(self, session, encryption):
        audit = AuditLogger(session)
        await audit.log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id=TENANT_A,
            resource_id="external-42",
            details={"field": "email", "n": 1},
        )

        (row,) = await _rows(session)
        assert set(row.details) == {"encrypted", "ciphertext"}
        assert "email" not in json.dumps(row.details)
        assert decode_details(row.details) == {
            "field": "email",
            "n": 1,
            RESOURCE_REF_KEY: "external-42",
            **INFO,
        }
        assert (await audit.verify_integrity(TENANT_A))["valid"] is True

        with _audit_bucket(None):
            export_id = await audit.export_logs(
                TENANT_A, datetime.utcnow() - timedelta(hours=1), datetime.utcnow()
            )
        assert uuid.UUID(export_id)

    async def test_export_decrypts(self, session, encryption):
        audit = AuditLogger(session)
        await audit.log(
            event_type=AuditEventType.USER_UPDATE, tenant_id=TENANT_A, details={"k": "v"}
        )
        captured = {}
        audit.r2_client = _CapturingR2(captured)

        with _audit_bucket("example-audit-archive"):
            await audit.export_logs(
                TENANT_A, datetime.utcnow() - timedelta(hours=1), datetime.utcnow()
            )

        assert json.loads(captured["Body"])["logs"][0]["details"] == {"k": "v", **INFO}

    def test_other_values_are_returned_unchanged(self):
        for value in (None, {}, {"encrypted": False, "ciphertext": "x"}, {"a": 1}, "text"):
            assert decode_details(value) == value


class _CapturingR2:
    def __init__(self, captured):
        self.captured = captured

    def put_object(self, **kwargs):
        self.captured.update(kwargs)

    def generate_presigned_url(self, *args, **kwargs):
        return "https://r2.example/presigned"


class _audit_bucket:
    """Set R2_AUDIT_BUCKET for the block (the upload bucket stays different)."""

    def __init__(self, bucket):
        self.bucket = bucket

    def __enter__(self):
        self.saved = (settings.R2_AUDIT_BUCKET, settings.CLOUDFLARE_R2_BUCKET)
        settings.R2_AUDIT_BUCKET = self.bucket
        settings.CLOUDFLARE_R2_BUCKET = "example-uploads"

    def __exit__(self, *exc):
        settings.R2_AUDIT_BUCKET, settings.CLOUDFLARE_R2_BUCKET = self.saved
