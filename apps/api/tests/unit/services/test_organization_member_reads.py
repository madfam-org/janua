"""Real AsyncSession regressions for the mounted, profile-free tenant roster."""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Organization, OrganizationMember, User
from app.routers.v1 import organization_members, organizations
from app.routers.v1.organizations.core import list_organizations
from app.routers.v1.organizations.dependencies import get_user_organization_role
from app.services.organization_member_service import OrganizationMemberService


@pytest_asyncio.fixture
async def roster_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[User.__table__, Organization.__table__, OrganizationMember.__table__]
            )
        )
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db
    await engine.dispose()


async def seed(db, caller_status="active", caller_role="member", platform_admin=False):
    user = User(id=uuid4(), email=f"{uuid4()}@example.test", is_admin=platform_admin)
    peer = User(id=uuid4(), email=f"{uuid4()}@example.test", is_service_account=True)
    other = User(id=uuid4(), email=f"{uuid4()}@example.test")
    org = Organization(
        id=uuid4(), name="Example organization", slug=str(uuid4()), owner_id=other.id
    )
    foreign_org = Organization(
        id=uuid4(), name="Other organization", slug=str(uuid4()), owner_id=other.id
    )
    caller = OrganizationMember(
        id=uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=caller_role,
        status=caller_status,
        joined_at=datetime(2026, 1, 1),
    )
    peer_member = OrganizationMember(
        id=uuid4(),
        organization_id=org.id,
        user_id=peer.id,
        role="member",
        status="active",
        joined_at=datetime(2026, 1, 2),
    )
    foreign_member = OrganizationMember(
        id=uuid4(),
        organization_id=foreign_org.id,
        user_id=other.id,
        role="owner",
        status="active",
        joined_at=datetime(2026, 1, 3),
    )
    db.add_all([user, peer, other, org, foreign_org, caller, peer_member, foreign_member])
    await db.commit()
    return user, peer, org, foreign_org, caller


def tenant_app(db, user, redis):
    app = FastAPI()
    app.include_router(organization_members.router, prefix="/api/v1")
    app.dependency_overrides[organization_members.get_db] = lambda: db
    app.dependency_overrides[organization_members.get_current_user] = lambda: user
    app.dependency_overrides[organization_members.get_redis] = lambda: redis
    return app


@pytest.mark.asyncio
async def test_mounted_roster_serializes_real_models_without_profiles_or_schema_metadata(roster_db):
    user, peer, org, foreign_org, caller = await seed(roster_db)
    redis = AsyncMock()
    redis.get.return_value = "true"  # A stale grant/roster must never drive this read.
    app = tenant_app(roster_db, user, redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/organizations/{org.id}/members")
    assert response.status_code == 200
    rows = response.json()
    assert {row["user_id"] for row in rows} == {str(user.id), str(peer.id)}
    assert all(row["organization_id"] == str(org.id) for row in rows)
    assert all(row["metadata"] is None and "email" not in row and "name" not in row for row in rows)
    assert all(isinstance(row["joined_at"], str) for row in rows)
    assert next(row for row in rows if row["user_id"] == str(peer.id))["is_service_account"] is True
    redis.get.assert_not_awaited()
    redis.set.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("membership_status", ["inactive", "pending", "removed"])
async def test_inactive_platform_operator_cannot_read_members_even_with_cached_allow(
    roster_db, membership_status
):
    user, _, org, _, _ = await seed(roster_db, caller_status=membership_status, platform_admin=True)
    redis = AsyncMock()
    redis.get.return_value = "true"
    app = tenant_app(roster_db, user, redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/organizations/{org.id}/members")
    assert response.status_code == 403
    assert response.json() == {"detail": "Active organization membership required"}
    redis.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_nonmember_denied_and_role_demotion_applies_next_read(roster_db):
    user, _, org, foreign_org, caller = await seed(roster_db)
    redis = AsyncMock()
    with pytest.raises(HTTPException) as denied:
        await organization_members.get_members(foreign_org.id, False, roster_db, redis, user)
    assert denied.value.status_code == 403
    assert len(await organization_members.get_members(org.id, False, roster_db, redis, user)) == 2
    caller.status = "removed"
    await roster_db.commit()
    with pytest.raises(HTTPException) as revoked:
        await organization_members.get_members(org.id, False, roster_db, redis, user)
    assert revoked.value.status_code == 403


@pytest.mark.asyncio
async def test_service_filters_current_members_and_never_returns_another_organization(roster_db):
    user, peer, org, _, caller = await seed(roster_db, caller_status="removed")
    service = OrganizationMemberService(roster_db, AsyncMock())
    assert [row.user_id for row in await service.get_members(org.id)] == [peer.id]
    assert {row.user_id for row in await service.get_members(org.id, include_removed=True)} == {
        user.id,
        peer.id,
    }


@pytest.mark.asyncio
async def test_mounted_organization_list_and_role_lookup_exclude_inactive_members(roster_db):
    user, _, org, _, caller = await seed(roster_db, caller_status="removed")
    assert organizations.__file__.endswith("organizations/__init__.py")
    assert await get_user_organization_role(roster_db, user.id, org.id) is None
    listing = await list_organizations(page=1, per_page=20, current_user=user, db=roster_db)
    assert listing.total == 0
    assert listing.organizations == []
    caller.status = "active"
    await roster_db.commit()
    assert await get_user_organization_role(roster_db, user.id, org.id) == "member"
    listing = await list_organizations(page=1, per_page=20, current_user=user, db=roster_db)
    assert listing.total == 1
    assert [row.id for row in listing.organizations] == [str(org.id)]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "admin", "member", "viewer"])
async def test_builtin_membership_roles_retain_org_read(roster_db, role):
    from app.services.rbac_service import RBACService

    user, _, org, _, _ = await seed(roster_db, caller_role=role)
    assert RBACService(roster_db, AsyncMock())._check_role_permission(role, "org:read")
    assert (
        len(await organization_members.get_members(org.id, False, roster_db, AsyncMock(), user))
        == 2
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["custom-role", "super_admin"])
async def test_unrecognized_or_platform_role_in_membership_does_not_grant_tenant_read(
    roster_db, role
):
    user, _, org, _, _ = await seed(roster_db, caller_role=role, platform_admin=True)
    with pytest.raises(HTTPException) as denied:
        await organization_members.get_members(org.id, False, roster_db, AsyncMock(), user)
    assert denied.value.status_code == 403


def test_application_mounts_the_read_handlers_under_test():
    from app.main import app

    routes = {
        (route.path, method): route.endpoint
        for route in app.routes
        for method in getattr(route, "methods", [])
    }
    assert routes[("/api/v1/organizations/", "GET")] is list_organizations
    assert (
        routes[("/api/v1/organizations/{organization_id}/members", "GET")]
        is organization_members.get_members
    )
