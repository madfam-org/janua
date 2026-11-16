"""Unit tests for the internal primary-organization endpoints
(POST /api/v1/internal/primary-organization/{set,clear}, GET /{user_id}).

Like tests/unit/routers/test_internal_app_roles.py these run against a REAL
SQLite-backed schema, so the response's `token_org_id` / `token_app_roles` are
the shared claims resolver's own answer over real rows, not a mock's.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, Organization, OrganizationMember, User, UserStatus
from app.models.app_role import OrganizationMemberAppRole
from app.routers.v1.internal_app_roles import NO_MEMBERSHIP_DETAIL
from app.routers.v1.internal_primary_organization import NO_USER_DETAIL
from app.services.audit_logger import AuditEventType

INTERNAL_KEY = "test-internal-api-key-primary-org"
SET_URL = "/api/v1/internal/primary-organization/set"
CLEAR_URL = "/api/v1/internal/primary-organization/clear"
READ_URL = "/api/v1/internal/primary-organization/{user_id}"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}
AUDIT_LOG = "app.routers.v1.internal_primary_organization.AuditLogger.log"


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    redis = AsyncMock()
    redis.ping.return_value = True
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    settings.INTERNAL_API_KEY = INTERNAL_KEY

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


async def _seed(factory) -> dict:
    """A staff person ACTIVE in a and b, INACTIVE in c; d unrelated.

    b's membership carries `ops:platform-admin`.
    """
    ids = {key: uuid.uuid4() for key in ("a", "b", "c", "d")}
    user_id = uuid.uuid4()
    async with factory() as session:
        for key, org_id in ids.items():
            session.add(Organization(id=org_id, name=key.upper(), slug=f"org-{key}"))
        session.add(
            User(
                id=user_id,
                email="staff@example.com",
                status=UserStatus.ACTIVE,
                is_admin=False,
                user_metadata={},
            )
        )
        member_b = uuid.uuid4()
        for key, status, member_id in (
            ("a", "active", uuid.uuid4()),
            ("b", "active", member_b),
            ("c", "inactive", uuid.uuid4()),
        ):
            session.add(
                OrganizationMember(
                    id=member_id,
                    organization_id=ids[key],
                    user_id=user_id,
                    role="member",
                    status=status,
                )
            )
        await session.flush()
        session.add(
            OrganizationMemberAppRole(
                organization_member_id=member_b, app="ops", role="platform-admin", granted_by="t"
            )
        )
        await session.commit()
    return {"user_id": str(user_id), **{k: str(v) for k, v in ids.items()}}


async def _stored(factory, user_id: str):
    async with factory() as session:
        value = (
            await session.execute(
                select(User.primary_organization_id).where(User.id == uuid.UUID(user_id))
            )
        ).scalar_one()
    return str(value) if value else None


# --- auth -------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,url,body",
    [
        ("post", SET_URL, {"organization_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4())}),
        ("post", CLEAR_URL, {"user_id": str(uuid.uuid4())}),
        ("get", READ_URL.format(user_id=uuid.uuid4()), None),
    ],
    ids=["set", "clear", "read"],
)
async def test_every_route_requires_the_internal_key(env, method, url, body):
    client, _ = env
    kwargs = {"json": body} if body is not None else {}

    missing = await getattr(client, method)(url, **kwargs)
    wrong = await getattr(client, method)(
        url, headers={"X-Internal-API-Key": "not-the-key"}, **kwargs
    )

    # Missing header is request validation (422); a wrong key is 401 — the
    # same split the sibling internal routers pin.
    assert missing.status_code == 422
    assert wrong.status_code == 401


# --- set --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_stores_the_choice_and_reports_the_resolved_token(env):
    client, factory = env
    ids = await _seed(factory)

    with patch(AUDIT_LOG, AsyncMock(return_value="evt")) as audit:
        response = await client.post(
            SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
        )

    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["primary_organization_id"] == ids["b"]
    assert body["active_membership"] is True
    assert body["token_org_id"] == ids["b"]
    assert body["token_app_roles"] == ["ops:platform-admin"]
    assert await _stored(factory, ids["user_id"]) == ids["b"]

    audit.assert_awaited_once()
    kwargs = audit.await_args.kwargs
    assert kwargs["event_type"] == AuditEventType.PRIMARY_ORGANIZATION_SET
    assert kwargs["tenant_id"] == ids["b"]
    assert kwargs["details"]["previous_organization_id"] is None


@pytest.mark.asyncio
async def test_set_is_idempotent_and_does_not_audit_a_no_op(env):
    client, factory = env
    ids = await _seed(factory)
    payload = {"organization_id": ids["b"], "user_id": ids["user_id"]}

    with patch(AUDIT_LOG, AsyncMock(return_value="evt")) as audit:
        first = await client.post(SET_URL, json=payload, headers=AUTH)
        second = await client.post(SET_URL, json=payload, headers=AUTH)

    assert first.json()["changed"] is True
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert second.json()["token_org_id"] == ids["b"]
    assert audit.await_count == 1


@pytest.mark.asyncio
async def test_set_replaces_a_previous_choice_and_records_it(env):
    client, factory = env
    ids = await _seed(factory)

    with patch(AUDIT_LOG, AsyncMock(return_value="evt")) as audit:
        await client.post(
            SET_URL, json={"organization_id": ids["a"], "user_id": ids["user_id"]}, headers=AUTH
        )
        response = await client.post(
            SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
        )

    assert response.json()["changed"] is True
    assert await _stored(factory, ids["user_id"]) == ids["b"]
    assert audit.await_args.kwargs["details"]["previous_organization_id"] == ids["a"]


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["c", "d", "missing"], ids=["inactive", "non-member", "no-org"])
async def test_set_without_an_active_membership_is_one_404(env, target):
    client, factory = env
    ids = await _seed(factory)
    organization_id = ids[target] if target in ids else str(uuid.uuid4())

    response = await client.post(
        SET_URL, json={"organization_id": organization_id, "user_id": ids["user_id"]}, headers=AUTH
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == NO_MEMBERSHIP_DETAIL
    assert await _stored(factory, ids["user_id"]) is None


@pytest.mark.asyncio
async def test_set_for_an_unknown_user_is_the_same_404(env):
    client, factory = env
    ids = await _seed(factory)

    response = await client.post(
        SET_URL, json={"organization_id": ids["b"], "user_id": str(uuid.uuid4())}, headers=AUTH
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == NO_MEMBERSHIP_DETAIL


@pytest.mark.asyncio
async def test_an_audit_failure_does_not_undo_the_write(env):
    client, factory = env
    ids = await _seed(factory)

    with patch(AUDIT_LOG, AsyncMock(side_effect=RuntimeError("trail down"))):
        response = await client.post(
            SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
        )

    assert response.status_code == 200
    assert await _stored(factory, ids["user_id"]) == ids["b"]


# --- clear ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_removes_the_choice_idempotently_and_deletes_nothing(env):
    client, factory = env
    ids = await _seed(factory)

    with patch(AUDIT_LOG, AsyncMock(return_value="evt")) as audit:
        await client.post(
            SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
        )
        first = await client.post(CLEAR_URL, json={"user_id": ids["user_id"]}, headers=AUTH)
        second = await client.post(CLEAR_URL, json={"user_id": ids["user_id"]}, headers=AUTH)

    assert first.status_code == 200
    assert first.json()["changed"] is True
    assert first.json()["primary_organization_id"] is None
    assert first.json()["token_org_id"] is None
    assert first.json()["token_app_roles"] == []
    assert second.status_code == 200 and second.json()["changed"] is False
    assert await _stored(factory, ids["user_id"]) is None

    events = [call.kwargs["event_type"] for call in audit.await_args_list]
    assert events == [
        AuditEventType.PRIMARY_ORGANIZATION_SET,
        AuditEventType.PRIMARY_ORGANIZATION_CLEAR,
    ]

    # Nothing but the pointer changed: the memberships and the grant remain.
    async with factory() as session:
        assert len((await session.execute(select(OrganizationMember))).scalars().all()) == 3
        assert len((await session.execute(select(OrganizationMemberAppRole))).scalars().all()) == 1
        assert await session.get(User, uuid.UUID(ids["user_id"])) is not None


@pytest.mark.asyncio
async def test_clear_works_after_the_membership_was_removed(env):
    """A pointer left behind by a removed membership must still be removable."""
    client, factory = env
    ids = await _seed(factory)
    await client.post(
        SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
    )
    async with factory() as session:
        member = (
            await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == uuid.UUID(ids["b"])
                )
            )
        ).scalar_one()
        member.status = "inactive"
        await session.commit()

    read = await client.get(READ_URL.format(user_id=ids["user_id"]), headers=AUTH)
    cleared = await client.post(CLEAR_URL, json={"user_id": ids["user_id"]}, headers=AUTH)

    # Stored but not resolving: the read says so instead of hiding it. With b
    # gone, a is the ONLY active membership left, so the token resolves to a by
    # the unchanged single-membership rule — and b's grant is not carried.
    assert read.json()["primary_organization_id"] == ids["b"]
    assert read.json()["active_membership"] is False
    assert read.json()["token_org_id"] == ids["a"]
    assert read.json()["token_app_roles"] == []
    assert cleared.json()["changed"] is True


@pytest.mark.asyncio
async def test_clear_for_an_unknown_user_is_404(env):
    client, _ = env
    response = await client.post(CLEAR_URL, json={"user_id": str(uuid.uuid4())}, headers=AUTH)
    assert response.status_code == 404
    assert response.json()["error"]["message"] == NO_USER_DETAIL


# --- read -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_reports_unset_then_set(env):
    client, factory = env
    ids = await _seed(factory)
    url = READ_URL.format(user_id=ids["user_id"])

    before = await client.get(url, headers=AUTH)
    await client.post(
        SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
    )
    after = await client.get(url, headers=AUTH)

    assert before.status_code == 200
    assert before.json() == {
        "user_id": ids["user_id"],
        "primary_organization_id": None,
        "active_membership": False,
        "token_org_id": None,
        "token_app_roles": [],
        "changed": None,
    }
    assert after.json()["primary_organization_id"] == ids["b"]
    assert after.json()["token_org_id"] == ids["b"]
    assert after.json()["token_app_roles"] == ["ops:platform-admin"]


@pytest.mark.asyncio
async def test_read_shows_tenant_id_taking_precedence(env):
    client, factory = env
    ids = await _seed(factory)
    async with factory() as session:
        user = await session.get(User, uuid.UUID(ids["user_id"]))
        user.tenant_id = uuid.UUID(ids["a"])
        await session.commit()

    response = await client.post(
        SET_URL, json={"organization_id": ids["b"], "user_id": ids["user_id"]}, headers=AUTH
    )

    assert response.json()["primary_organization_id"] == ids["b"]
    assert response.json()["token_org_id"] == ids["a"]
    assert response.json()["token_app_roles"] == []


@pytest.mark.asyncio
async def test_read_for_an_unknown_user_is_404(env):
    client, _ = env
    response = await client.get(READ_URL.format(user_id=uuid.uuid4()), headers=AUTH)
    assert response.status_code == 404
    assert response.json()["error"]["message"] == NO_USER_DETAIL


@pytest.mark.asyncio
async def test_read_with_a_malformed_user_id_is_422(env):
    client, _ = env
    response = await client.get(READ_URL.format(user_id="not-a-uuid"), headers=AUTH)
    assert response.status_code == 422
