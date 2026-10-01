"""``/v1/audit-logs``: audited export and cleanup, decoded reads.

- Export and cleanup audit themselves with ``AUDIT_EXPORT`` / ``AUDIT_CLEANUP``.
  The request session (``get_db``) closes without committing, so each handler
  commits after its audit call. Cleanup's deletion and its audit row commit
  together.
- Rows written with encrypted details (``AUDIT_LOG_ENCRYPTION``) are returned
  decrypted by the list, get and export endpoints, to the readers each
  endpoint already allows: admins, and a user for their own rows. Who can read
  which row is unchanged.

Real models on SQLite, handlers called directly.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.encryption import FieldEncryptor
from app.models import AuditLog, Base, User
from app.routers.v1.audit_logs import (
    AuditLogExportRequest,
    cleanup_old_audit_logs,
    export_audit_logs,
    get_audit_log,
    list_audit_logs,
)
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import AUDIT_CONTEXT_KEY, AuditEventType, AuditLogger
from tests.unit.services.test_audit_logger_chain import sqlite_with_real_transactions


class CommitFailed(Exception):
    pass


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


@pytest.fixture
def encryption(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", True)
    monkeypatch.setattr(
        settings, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode(), raising=False
    )
    monkeypatch.setattr(FieldEncryptor, "_instance", None)
    yield
    FieldEncryptor._instance = None


@pytest.fixture
async def factory(tmp_path):
    engine = sqlite_with_real_transactions(
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _user(factory, email, *, is_admin=False) -> User:
    async with factory() as db:
        person = User(id=uuid.uuid4(), email=email, is_admin=is_admin)
        db.add(person)
        await db.commit()
        return person


@pytest.fixture
async def admin(factory) -> User:
    return await _user(factory, "admin@example.com", is_admin=True)


@pytest.fixture
async def member(factory) -> User:
    return await _user(factory, "member@example.com")


@pytest.fixture
async def other(factory) -> User:
    return await _user(factory, "other@example.com")


async def _log(factory, user, details) -> str:
    async with factory() as db:
        event_id = await AuditLogger(db).log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id="default",
            identity_id=str(user.id),
            details=details,
        )
        await db.commit()
        return event_id


async def _rows(factory, event_type=None):
    async with factory() as fresh:
        query = select(AuditLog)
        if event_type is not None:
            query = query.where(AuditLog.event_type == event_type.value)
        return (await fresh.execute(query)).scalars().all()


def _list_kwargs(**overrides):
    kwargs = {
        "actor": None,
        "action": None,
        "resource": None,
        "resource_type": None,
        "start_date": None,
        "end_date": None,
        "ip_address": None,
        "limit": 100,
        "cursor": None,
    }
    kwargs.update(overrides)
    return kwargs


class TestExportIsAudited:
    async def test_export_row_persists(self, factory, admin, member):
        await _log(factory, member, {"field": "name"})

        async with factory() as db:
            response = await export_audit_logs(
                AuditLogExportRequest(format="json"),
                BackgroundTasks(),
                current_user=admin,
                db=db,
            )
        assert response.status_code == 200

        (row,) = await _rows(factory, AuditEventType.AUDIT_EXPORT)
        assert row.action == "audit.export"
        assert row.user_id == admin.id
        assert row.resource_type == "audit_logs"
        assert row.details["format"] == "json"
        assert row.details["count"] == 1

    async def test_csv_export_row_persists(self, factory, admin, member):
        await _log(factory, member, {"field": "name"})

        async with factory() as db:
            response = await export_audit_logs(
                AuditLogExportRequest(format="csv"),
                BackgroundTasks(),
                current_user=admin,
                db=db,
            )
        assert response.media_type == "text/csv"
        (row,) = await _rows(factory, AuditEventType.AUDIT_EXPORT)
        assert row.details["format"] == "csv"


class TestCleanupIsAudited:
    async def _old_row(self, factory, user):
        async with factory() as db:
            db.add(
                AuditLog(
                    action="user.update",
                    user_id=user.id,
                    created_at=datetime.utcnow() - timedelta(days=400),
                )
            )
            await db.commit()

    async def test_deletion_and_its_audit_row_persist(self, factory, admin, member):
        await self._old_row(factory, member)
        await _log(factory, member, {"recent": True})

        async with factory() as db:
            result = await cleanup_old_audit_logs(days=90, current_user=admin, db=db)
        assert result["deleted_count"] == 1

        rows = await _rows(factory)
        assert sorted(r.event_type or r.action for r in rows) == ["audit.cleanup", "user.update"]
        (row,) = await _rows(factory, AuditEventType.AUDIT_CLEANUP)
        assert row.user_id == admin.id
        assert row.details["deleted_count"] == 1
        assert row.details["retention_days"] == 90

    async def test_failure_after_the_audit_call_keeps_everything(self, factory, admin, member):
        await self._old_row(factory, member)

        async with factory() as db:
            logged = []
            original_log = AuditLogger.log

            async def failing_commit():
                if logged:
                    raise CommitFailed("forced failure after the audit call")

            async def log_and_record(self, *args, **kwargs):
                result = await original_log(self, *args, **kwargs)
                logged.append(kwargs["event_type"])
                return result

            db.commit = failing_commit
            AuditLogger.log = log_and_record
            try:
                with pytest.raises(CommitFailed):
                    await cleanup_old_audit_logs(days=90, current_user=admin, db=db)
            finally:
                AuditLogger.log = original_log
        assert logged == [AuditEventType.AUDIT_CLEANUP]

        rows = await _rows(factory)
        assert [r.action for r in rows] == ["user.update"]


class TestEncryptedDetailsAreDecoded:
    async def test_list_for_admin(self, factory, admin, member, encryption):
        await _log(factory, member, {"field": "email"})

        async with factory() as db:
            result = await list_audit_logs(**_list_kwargs(), current_user=admin, db=db)
        (log,) = result.logs
        assert log.details == {"field": "email", AUDIT_CONTEXT_KEY: {"severity": "info"}}

    async def test_list_for_the_owner_only(self, factory, member, other, encryption):
        await _log(factory, member, {"field": "email"})
        await _log(factory, other, {"field": "phone"})

        async with factory() as db:
            mine = await list_audit_logs(**_list_kwargs(), current_user=member, db=db)
            # Asking for another user's rows still returns nothing.
            theirs = await list_audit_logs(
                **_list_kwargs(actor=str(other.id)), current_user=member, db=db
            )
        assert [log.details["field"] for log in mine.logs] == ["email"]
        assert theirs.logs == []

    async def test_get_for_the_owner(self, factory, member, encryption):
        event_id = await _log(factory, member, {"field": "email"})

        async with factory() as db:
            log = await get_audit_log(event_id, current_user=member, db=db)
        assert log.details["field"] == "email"

    async def test_get_refused_to_another_user(self, factory, member, other, encryption):
        event_id = await _log(factory, member, {"field": "email"})

        async with factory() as db:
            with pytest.raises(HTTPException) as refused:
                await get_audit_log(event_id, current_user=other, db=db)
        assert refused.value.status_code == 403

    async def test_export(self, factory, admin, member, encryption):
        await _log(factory, member, {"field": "email"})

        async with factory() as db:
            response = await export_audit_logs(
                AuditLogExportRequest(format="json", actions=["user.update"]),
                BackgroundTasks(),
                current_user=admin,
                db=db,
            )
        (exported,) = json.loads(response.body)
        assert exported["details"]["field"] == "email"

    async def test_plain_details_unchanged(self, factory, admin, member):
        await _log(factory, member, {"field": "email"})

        async with factory() as db:
            result = await list_audit_logs(**_list_kwargs(), current_user=admin, db=db)
        assert result.logs[0].details["field"] == "email"
