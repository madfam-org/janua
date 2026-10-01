"""Processor scope of ``DataSubjectRightsService`` on real models (SQLite).

A data subject request may be processed only by its data subject or by a
platform administrator. Any other processor is answered exactly as for an
unknown request id, and the request and the subject's data stay untouched.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, User
from app.models.compliance import DataSubjectRequest, DataSubjectRequestType, RequestStatus
from app.services.compliance_service import DataSubjectRightsService


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed(db_session, request_type: DataSubjectRequestType):
    subject = User(
        id=uuid.uuid4(),
        email=f"subject-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Subject",
        last_name="User",
        created_at=datetime.utcnow(),
    )
    other = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        created_at=datetime.utcnow(),
    )
    db_session.add_all([subject, other])
    await db_session.flush()
    request = DataSubjectRequest(
        request_id=f"DSR-TEST-{uuid.uuid4().hex[:8].upper()}",
        user_id=subject.id,
        request_type=request_type,
        status=RequestStatus.RECEIVED,
        received_at=datetime.utcnow(),
        response_due_date=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(request)
    await db_session.commit()
    return subject, other, request


def _service(db_session) -> DataSubjectRightsService:
    return DataSubjectRightsService(db_session, AsyncMock())


class TestGetRequestForProcessor:
    async def test_subject_gets_request(self, db_session):
        subject, _other, request = await _seed(db_session, DataSubjectRequestType.ACCESS)
        found = await _service(db_session).get_request_for_processor(request.request_id, subject.id)
        assert found is not None and found.id == request.id

    async def test_platform_admin_gets_request(self, db_session):
        _subject, other, request = await _seed(db_session, DataSubjectRequestType.ACCESS)
        found = await _service(db_session).get_request_for_processor(
            request.request_id, other.id, processor_is_admin=True
        )
        assert found is not None and found.id == request.id

    async def test_other_processor_gets_none(self, db_session):
        _subject, other, request = await _seed(db_session, DataSubjectRequestType.ACCESS)
        found = await _service(db_session).get_request_for_processor(request.request_id, other.id)
        assert found is None

    async def test_unknown_id_gets_none(self, db_session):
        subject, _other, _request = await _seed(db_session, DataSubjectRequestType.ACCESS)
        found = await _service(db_session).get_request_for_processor(
            "DSR-00000000-DOESNOTEXIST", subject.id, processor_is_admin=True
        )
        assert found is None


class TestAccessRequestProcessorScope:
    async def test_other_processor_is_rejected_like_unknown_id(self, db_session):
        _subject, other, request = await _seed(db_session, DataSubjectRequestType.ACCESS)
        service = _service(db_session)

        with pytest.raises(ValueError, match="Invalid access request"):
            await service.process_access_request(request.request_id, processor_id=other.id)
        with pytest.raises(ValueError, match="Invalid access request"):
            await service.process_access_request("DSR-00000000-DOESNOTEXIST", processor_id=other.id)

        await db_session.refresh(request)
        assert request.status == RequestStatus.RECEIVED
        assert request.assigned_to is None


class TestErasureRequestProcessorScope:
    async def test_other_processor_is_rejected_and_subject_untouched(self, db_session):
        subject, other, request = await _seed(db_session, DataSubjectRequestType.ERASURE)
        audit_logger = AsyncMock()
        service = DataSubjectRightsService(db_session, audit_logger)

        with pytest.raises(ValueError, match="Invalid erasure request"):
            await service.process_erasure_request(
                request.request_id, processor_id=other.id, deletion_method="hard_delete"
            )

        await db_session.refresh(request)
        assert request.status == RequestStatus.RECEIVED
        assert request.assigned_to is None
        still_there = await db_session.execute(select(User).where(User.id == subject.id))
        assert still_there.scalar_one().email == subject.email
        audit_logger.log.assert_not_called()

    @pytest.mark.parametrize("as_admin", [False, True])
    async def test_subject_or_platform_admin_passes_the_scope_check(self, db_session, as_admin):
        subject, other, request = await _seed(db_session, DataSubjectRequestType.ERASURE)
        audit_logger = AsyncMock()
        service = DataSubjectRightsService(db_session, audit_logger)
        processor = other if as_admin else subject

        # A deletion method outside anonymize/hard_delete changes no user data,
        # so this pins the scope check alone: the request is processed and
        # assigned to the processor.
        assert await service.process_erasure_request(
            request.request_id,
            processor_id=processor.id,
            deletion_method="scope-check-only",
            processor_is_admin=as_admin,
        )

        await db_session.refresh(request)
        assert request.status == RequestStatus.COMPLETED
        assert request.assigned_to == processor.id
        audit_logger.log.assert_called_once()
