"""Completing a data subject access request writes its audit row.

``GET /compliance/data-subject-request/{id}/data`` completes an access request
through ``DataSubjectRightsService.process_access_request``. The request's
creation was audited, its completion was not. It now logs
``DATA_REQUEST_PROCESSED`` in the same transaction as the status change.

Real models on SQLite, the service called as the router calls it.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import AuditLog, Base, User
from app.models.compliance import DataSubjectRequest, DataSubjectRequestType, RequestStatus
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import (
    AUDIT_CONTEXT_KEY,
    RESOURCE_REF_KEY,
    AuditEventType,
    AuditLogger,
)
from app.services.compliance_service import ComplianceService
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
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dsr.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def subject(factory) -> User:
    async with factory() as db:
        person = User(
            id=uuid.uuid4(),
            email="subject@example.com",
            first_name="Data",
            last_name="Subject",
            tenant_id=uuid.uuid4(),
        )
        db.add(person)
        await db.commit()
        return person


async def _create_access_request(factory, subject) -> str:
    async with factory() as db:
        service = ComplianceService(db, AuditLogger(db))
        dsr = await service.data_subject_rights_service.create_request(
            user_id=subject.id,
            request_type=DataSubjectRequestType.ACCESS,
            tenant_id=subject.tenant_id,
        )
        return dsr.request_id


async def _processed_rows(factory):
    async with factory() as fresh:
        result = await fresh.execute(
            select(AuditLog).where(
                AuditLog.event_type == AuditEventType.DATA_REQUEST_PROCESSED.value
            )
        )
        return result.scalars().all()


async def test_completion_is_audited(factory, subject):
    request_id = await _create_access_request(factory, subject)

    # As the router does: a request-scoped session, closed without a commit.
    async with factory() as db:
        service = ComplianceService(db, AuditLogger(db))
        data = await service.data_subject_rights_service.process_access_request(
            request_id=request_id, processor_id=subject.id
        )
    assert data["personal_information"]["email"] == "subject@example.com"

    async with factory() as fresh:
        dsr = (
            await fresh.execute(
                select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
            )
        ).scalar_one()
    assert dsr.status == RequestStatus.COMPLETED

    (row,) = await _processed_rows(factory)
    assert row.action == "gdpr.data_request_processed"
    assert row.tenant_id == str(subject.tenant_id)
    assert row.user_id == subject.id
    assert row.resource_type == "data_subject_request"
    assert row.details[RESOURCE_REF_KEY] == request_id
    assert row.details["request_type"] == "access"
    assert row.details["status"] == "completed"
    context = row.details[AUDIT_CONTEXT_KEY]
    assert context["data_subject_id"] == str(subject.id)
    assert context["compliance_context"]["article"] == "Article 15"
    assert context["compliance_context"]["request_id"] == request_id


async def test_completion_and_its_audit_row_commit_together(factory, subject):
    request_id = await _create_access_request(factory, subject)

    async with factory() as db:
        service = ComplianceService(db, AuditLogger(db))
        original_log = service.audit_logger.log
        logged = []

        async def log_then_arm(*args, **kwargs):
            result = await original_log(*args, **kwargs)
            logged.append(kwargs["event_type"])
            return result

        async def failing_commit():
            raise CommitFailed("forced failure after the audit call")

        service.audit_logger.log = log_then_arm
        db.commit = failing_commit
        with pytest.raises(CommitFailed):
            await service.data_subject_rights_service.process_access_request(
                request_id=request_id, processor_id=subject.id
            )
    assert logged == [AuditEventType.DATA_REQUEST_PROCESSED]

    assert await _processed_rows(factory) == []
    async with factory() as fresh:
        dsr = (
            await fresh.execute(
                select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
            )
        ).scalar_one()
    assert dsr.status == RequestStatus.RECEIVED
