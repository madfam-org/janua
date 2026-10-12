"""The auth handlers' audit helper persists its row and never breaks the flow.

``log_audit_event`` runs after the auth handlers' own commits (sign-up, sign-in,
sign-out, password reset and change, email verification). The audit logger only
flushes into the caller's session, so the helper commits; the request's session
is then closed without a commit, as ``app.database.get_db`` does. If the audit
write fails, the helper rolls back (nothing of the caller's is pending by then)
so the rest of the request can still use the session.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import AuditLog, Base, User
from app.routers.v1.auth import log_audit_event
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import AuditLogger
from tests.unit.services.test_audit_logger_chain import sqlite_with_real_transactions


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


@pytest.fixture
async def factory(tmp_path):
    engine = sqlite_with_real_transactions(
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_the_audit_row_persists_after_the_session_closes(factory):
    user_id = uuid.uuid4()
    async with factory() as db:
        db.add(User(id=user_id, email="person@example.com"))
        await db.commit()
        await log_audit_event(db, str(user_id), "signin", {"method": "password"})

    async with factory() as fresh:
        (row,) = (await fresh.execute(select(AuditLog))).scalars().all()
    assert row.action == "auth.signin"
    assert row.user_id == user_id
    assert row.tenant_id == "default"


async def test_an_audit_failure_leaves_the_session_usable(factory, monkeypatch):
    async def fail(self, *args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(AuditLogger, "log", fail)
    user_id = uuid.uuid4()
    async with factory() as db:
        await log_audit_event(db, str(user_id), "signup", {"method": "email"})
        db.add(User(id=user_id, email="person@example.com"))
        await db.commit()

    async with factory() as fresh:
        assert (await fresh.get(User, user_id)) is not None
        assert (await fresh.execute(select(AuditLog))).scalars().all() == []
