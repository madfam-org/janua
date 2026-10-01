"""Access scope of data-subject requests on the compliance router.

``GET /api/v1/compliance/data-subject-request/{request_id}/data`` returns the
personal-data export of the request's subject. It is available only to:

* the request's data subject, and
* platform administrators (``User.is_admin``).

Every other caller receives the same 404 as an unknown request id, so the
response does not reveal whether a request exists. Exercised against the real
router and models on SQLite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database_manager import get_db as get_db_manager
from app.core.redis import get_redis
from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Base, Organization, OrganizationMember, User
from app.models.compliance import DataSubjectRequest, DataSubjectRequestType, RequestStatus


def _data_url(request_id: str) -> str:
    return f"/api/v1/compliance/data-subject-request/{request_id}/data"


@pytest_asyncio.fixture
async def dsr_env():
    """SQLite-backed app client, a session factory, and a settable caller."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    redis = AsyncMock()
    redis.ping.return_value = True

    actors: dict = {"current": None}

    async def override_get_current_user():
        return actors["current"]

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_manager] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory, actors

    app.dependency_overrides.clear()
    await engine.dispose()


def _user(**overrides) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="User",
        created_at=datetime.utcnow(),
        **overrides,
    )


async def _seed(session_factory):
    """A subject with an access request, another user, a platform admin, and an
    admin of the subject's organization who is not a platform admin."""
    subject = _user()
    other = _user()
    platform_admin = _user(is_admin=True)
    org_admin = _user()
    org = Organization(id=uuid.uuid4(), name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")

    request = DataSubjectRequest(
        request_id=f"DSR-TEST-{uuid.uuid4().hex[:8].upper()}",
        user_id=subject.id,
        request_type=DataSubjectRequestType.ACCESS,
        status=RequestStatus.RECEIVED,
        received_at=datetime.utcnow(),
        response_due_date=datetime.utcnow() + timedelta(days=30),
    )

    async with session_factory() as session:
        session.add_all([subject, other, platform_admin, org_admin, org])
        await session.flush()
        session.add_all(
            [
                OrganizationMember(
                    organization_id=org.id, user_id=subject.id, role="member", status="active"
                ),
                OrganizationMember(
                    organization_id=org.id, user_id=org_admin.id, role="admin", status="active"
                ),
            ]
        )
        request.organization_id = org.id
        session.add(request)
        await session.commit()

    return {
        "subject": subject,
        "other": other,
        "platform_admin": platform_admin,
        "org_admin": org_admin,
        "request": request,
    }


def _without_per_call_fields(body: dict) -> dict:
    """The error envelope carries a per-call request id and timestamp."""
    error = dict(body.get("error", {}))
    error.pop("request_id", None)
    error.pop("timestamp", None)
    return {**body, "error": error}


async def _stored_request(session_factory, request_id: str) -> DataSubjectRequest:
    async with session_factory() as session:
        result = await session.execute(
            select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
        )
        return result.scalar_one()


class TestDataSubjectRequestExportScope:
    async def test_subject_receives_own_export(self, dsr_env):
        client, session_factory, actors = dsr_env
        seeded = await _seed(session_factory)
        actors["current"] = seeded["subject"]

        response = await client.get(_data_url(seeded["request"].request_id))

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["personal_information"]["id"] == str(seeded["subject"].id)

        stored = await _stored_request(session_factory, seeded["request"].request_id)
        assert stored.status == RequestStatus.COMPLETED
        assert stored.assigned_to == seeded["subject"].id

    async def test_other_user_gets_not_found(self, dsr_env):
        client, session_factory, actors = dsr_env
        seeded = await _seed(session_factory)
        actors["current"] = seeded["other"]

        response = await client.get(_data_url(seeded["request"].request_id))

        assert response.status_code == 404
        assert "personal_information" not in response.text
        assert seeded["subject"].email not in response.text

        # The request is left untouched for its subject.
        stored = await _stored_request(session_factory, seeded["request"].request_id)
        assert stored.status == RequestStatus.RECEIVED
        assert stored.assigned_to is None
        assert stored.completed_at is None

    async def test_other_user_response_matches_unknown_id(self, dsr_env):
        client, session_factory, actors = dsr_env
        seeded = await _seed(session_factory)
        actors["current"] = seeded["other"]

        denied = await client.get(_data_url(seeded["request"].request_id))
        unknown = await client.get(_data_url("DSR-00000000-DOESNOTEXIST"))

        assert denied.status_code == unknown.status_code == 404
        assert _without_per_call_fields(denied.json()) == _without_per_call_fields(unknown.json())

    async def test_unknown_id_gets_not_found_for_subject(self, dsr_env):
        client, session_factory, actors = dsr_env
        seeded = await _seed(session_factory)
        actors["current"] = seeded["subject"]

        response = await client.get(_data_url("DSR-00000000-DOESNOTEXIST"))

        assert response.status_code == 404

    async def test_platform_admin_receives_export(self, dsr_env):
        client, session_factory, actors = dsr_env
        seeded = await _seed(session_factory)
        actors["current"] = seeded["platform_admin"]

        response = await client.get(_data_url(seeded["request"].request_id))

        assert response.status_code == 200
        assert response.json()["data"]["personal_information"]["id"] == str(seeded["subject"].id)
        stored = await _stored_request(session_factory, seeded["request"].request_id)
        assert stored.assigned_to == seeded["platform_admin"].id

    async def test_organization_admin_without_platform_admin_gets_not_found(self, dsr_env):
        # No organization-level compliance permission exists, so an admin of
        # the subject's organization is treated like any other user.
        client, session_factory, actors = dsr_env
        seeded = await _seed(session_factory)
        actors["current"] = seeded["org_admin"]

        response = await client.get(_data_url(seeded["request"].request_id))

        assert response.status_code == 404
        stored = await _stored_request(session_factory, seeded["request"].request_id)
        assert stored.status == RequestStatus.RECEIVED
