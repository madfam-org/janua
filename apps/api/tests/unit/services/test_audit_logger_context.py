"""The audit entry's context that has no column of its own is stored.

``AuditLogger.log()`` takes ``severity``, ``organization_id`` and the compliance
fields (``compliance_context``, ``data_subject_id``, ``legal_basis``,
``retention_period``). ``audit_logs`` has no column for any of them, so they
are stored in ``details`` under ``AUDIT_CONTEXT_KEY``: ``severity`` always, the
others when they are set. Real model, SQLite.
"""

from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.encryption import FieldEncryptor
from app.models import AuditLog, Base
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import (
    AUDIT_CONTEXT_KEY,
    AuditEventType,
    AuditLogger,
    AuditMiddleware,
    decode_details,
)
from tests.unit.services.test_audit_logger_chain import sqlite_with_real_transactions


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "R2_AUDIT_BUCKET", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


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
        await conn.run_sync(Base.metadata.create_all, tables=[AuditLog.__table__])
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as db:
            yield db
    finally:
        await engine.dispose()


async def _only_row(session) -> AuditLog:
    rows = (await session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    return rows[0]


class TestStoredContext:
    async def test_all_fields(self, session):
        org = str(uuid.uuid4())
        subject = str(uuid.uuid4())
        await AuditLogger(session).log(
            event_type=AuditEventType.GDPR_DATA_DELETION,
            tenant_id=org,
            organization_id=org,
            details={"request_id": "DSR-1"},
            severity="high",
            compliance_context={"framework": "GDPR", "article": "Article 17"},
            data_subject_id=subject,
            legal_basis="legal_obligation",
            retention_period=2555,
        )
        row = await _only_row(session)
        assert row.details == {
            "request_id": "DSR-1",
            AUDIT_CONTEXT_KEY: {
                "severity": "high",
                "organization_id": org,
                "compliance_context": {"framework": "GDPR", "article": "Article 17"},
                "data_subject_id": subject,
                "legal_basis": "legal_obligation",
                "retention_period": 2555,
            },
        }

    async def test_severity_alone_by_default(self, session):
        await AuditLogger(session).log(
            event_type=AuditEventType.USER_UPDATE, tenant_id="t", details={"k": "v"}
        )
        row = await _only_row(session)
        assert row.details == {"k": "v", AUDIT_CONTEXT_KEY: {"severity": "info"}}

    async def test_caller_value_under_the_key_is_replaced(self, session):
        await AuditLogger(session).log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id="t",
            details={AUDIT_CONTEXT_KEY: {"severity": "none"}},
            severity="medium",
        )
        row = await _only_row(session)
        assert row.details == {AUDIT_CONTEXT_KEY: {"severity": "medium"}}

    async def test_organization_differs_from_tenant(self, session):
        # admin.create_user logs tenant_id = the user's tenant and
        # organization_id = the organization joined; both are kept.
        tenant, org = str(uuid.uuid4()), str(uuid.uuid4())
        await AuditLogger(session).log(
            event_type=AuditEventType.USER_CREATE,
            tenant_id=tenant,
            organization_id=org,
        )
        row = await _only_row(session)
        assert row.tenant_id == tenant
        assert row.details[AUDIT_CONTEXT_KEY]["organization_id"] == org

    async def test_compliance_helper(self, session):
        # A helper built on log() passes the compliance fields through.
        user = str(uuid.uuid4())
        middleware = AuditMiddleware(AuditLogger(session))
        await middleware.log_gdpr_consent(
            user_id=user, consent_type="marketing", purpose="newsletter", action="given"
        )
        context = (await _only_row(session)).details[AUDIT_CONTEXT_KEY]
        assert context["data_subject_id"] == user
        assert context["legal_basis"] == "consent"
        assert context["compliance_context"]["framework"] == "GDPR"

    async def test_encrypted_with_the_rest_of_details(self, session, monkeypatch):
        monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", True)
        monkeypatch.setattr(
            settings, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode(), raising=False
        )
        monkeypatch.setattr(FieldEncryptor, "_instance", None)
        await AuditLogger(session).log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id="t",
            data_subject_id="subject-1",
            severity="high",
        )
        row = await _only_row(session)
        assert set(row.details) == {"encrypted", "ciphertext"}
        assert decode_details(row.details)[AUDIT_CONTEXT_KEY] == {
            "severity": "high",
            "data_subject_id": "subject-1",
        }
