"""Admin writes and their audit rows commit together, or not at all.

Create-user and the user entitlement grant/revoke handlers log to the audit
trail BEFORE their own ``db.commit()``. The audit logger writes through the
handler's session and never commits it, so when the handler fails after the
audit call, the database holds neither the change nor its audit row: no user
without its membership, no entitlement change without its record, and no audit
record of a change that did not happen.

Real models on SQLite, handlers called directly. The forced failure is the
handler's own ``db.commit()``, armed only once the audit call has returned.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import AuditLog, Base, EntitlementSource, User, UserEntitlement
from app.routers.v1.admin import (
    AdminUserCreateRequest,
    AdminUserEntitlementGrantRequest,
    AdminUserEntitlementRevokeRequest,
    create_user_admin,
    grant_user_entitlement,
    revoke_user_entitlement,
)
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import AuditLogger
from app.services.entitlements_service import upsert_entitlement
from tests.unit.services.test_audit_logger_chain import sqlite_with_real_transactions


class CommitFailed(Exception):
    pass


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


@pytest.fixture
async def factory(tmp_path):
    engine = sqlite_with_real_transactions(
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def admin(factory) -> User:
    async with factory() as db:
        person = User(id=uuid.uuid4(), email="admin@example.com", is_admin=True)
        db.add(person)
        await db.commit()
        return person


@pytest.fixture
async def target(factory) -> User:
    async with factory() as db:
        person = User(id=uuid.uuid4(), email="member@example.com", tenant_id=uuid.uuid4())
        db.add(person)
        await db.commit()
        return person


@pytest.fixture
def fail_commit_after_audit(monkeypatch):
    """Make the handler's next ``commit()`` raise, once ``log()`` has returned."""
    original_log = AuditLogger.log
    armed = []

    async def log_then_arm(self, *args, **kwargs):
        result = await original_log(self, *args, **kwargs)
        armed.append(self.db)
        return result

    monkeypatch.setattr(AuditLogger, "log", log_then_arm)

    def arm(db):
        original_commit = db.commit

        async def commit():
            if db in armed:
                raise CommitFailed("forced failure after the audit call")
            await original_commit()

        db.commit = commit

    return arm, armed


async def _run_and_fail(factory, fail_commit_after_audit, handler, request, admin):
    arm, armed = fail_commit_after_audit
    async with factory() as db:
        arm(db)
        with pytest.raises(CommitFailed):
            await handler(request, current_user=admin, db=db)
        # The request's session is closed without a commit, as get_db does.
    assert armed, "the handler never reached its audit call"


async def _audit_rows(factory):
    async with factory() as fresh:
        return (await fresh.execute(select(AuditLog))).scalars().all()


async def test_create_user_leaves_no_user_and_no_audit_row(factory, admin, fail_commit_after_audit):
    await _run_and_fail(
        factory,
        fail_commit_after_audit,
        create_user_admin,
        AdminUserCreateRequest(email="new@example.com", password="Correct-Horse-9-Battery"),
        admin,
    )

    async with factory() as fresh:
        created = await fresh.execute(select(User).where(User.email == "new@example.com"))
        assert created.scalar_one_or_none() is None
    assert await _audit_rows(factory) == []


async def test_grant_leaves_no_entitlement_and_no_audit_row(
    factory, admin, target, fail_commit_after_audit
):
    await _run_and_fail(
        factory,
        fail_commit_after_audit,
        grant_user_entitlement,
        AdminUserEntitlementGrantRequest(user_id=str(target.id), product="kalya", tier="pro"),
        admin,
    )

    async with factory() as fresh:
        rows = (await fresh.execute(select(UserEntitlement))).scalars().all()
    assert rows == []
    assert await _audit_rows(factory) == []


async def test_revoke_leaves_the_entitlement_active_and_no_audit_row(
    factory, admin, target, fail_commit_after_audit
):
    async with factory() as db:
        await upsert_entitlement(
            db,
            user_id=target.id,
            product="kalya",
            tier="pro",
            source=EntitlementSource.ADMIN_GRANT,
            expires_at=None,
        )
        await db.commit()

    await _run_and_fail(
        factory,
        fail_commit_after_audit,
        revoke_user_entitlement,
        AdminUserEntitlementRevokeRequest(user_id=str(target.id), product="kalya"),
        admin,
    )

    async with factory() as fresh:
        (row,) = (await fresh.execute(select(UserEntitlement))).scalars().all()
    assert row.expires_at is None or row.expires_at > datetime.utcnow()
    assert await _audit_rows(factory) == []


async def test_without_a_failure_the_change_and_its_audit_row_commit_together(
    factory, admin, target
):
    async with factory() as db:
        await grant_user_entitlement(
            AdminUserEntitlementGrantRequest(user_id=str(target.id), product="kalya", tier="pro"),
            current_user=admin,
            db=db,
        )

    async with factory() as fresh:
        assert len((await fresh.execute(select(UserEntitlement))).scalars().all()) == 1
    (audit,) = await _audit_rows(factory)
    assert audit.action == "entitlement.grant"
    assert audit.resource_id == target.id
