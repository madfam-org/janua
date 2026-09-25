"""Unit tests for DELEGATED application-role administration
(``/api/v1/organizations/{org_id}/app-roles[/{app}[/grant|/revoke]]``).

Like ``test_internal_app_roles.py`` these run against a REAL SQLite schema, so
the partial unique index, the membership scoping and the claims resolver are all
exercised for real. Only ``get_current_user`` is overridden: it stands in for
"whoever the dashboard's janua-audience token names".
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.redis import get_redis
from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Base, Organization, OrganizationMember, User, UserStatus
from app.models.app_role import OrganizationMemberAppRole
from app.routers.v1.internal_app_roles import NO_MEMBERSHIP_DETAIL
from app.routers.v1.oauth_clients import INTERNAL_API_KEY_PRINCIPAL
from app.routers.v1.organization_app_roles import LAST_ADMIN_DETAIL, ensure_not_last_admin
from app.services.org_claims_service import APP_ROLES_KEY, get_user_org_claims

APP = "creator-census"


def _detail(response) -> str:
    """The refusal text, from janua's error envelope ({"error": {"message"}})."""
    return response.json()["error"]["message"]


def _url(org_id: str, suffix: str = "") -> str:
    return f"/api/v1/organizations/{org_id}/app-roles{suffix}"


class _Env:
    """Client + session factory + a switchable "who is calling"."""

    def __init__(self, client, session_factory):
        self.client = client
        self.sf = session_factory
        self.caller: User | None = None

    def as_user(self, user_id: str) -> _Env:
        self.caller = User(id=uuid.UUID(user_id), email="caller@example.com")
        return self


@pytest_asyncio.fixture
async def env():
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

    redis = AsyncMock()
    redis.ping.return_value = True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        state = _Env(client, session_factory)

        def override_current_user():
            if state.caller is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            return state.caller

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = lambda: redis
        app.dependency_overrides[get_current_user] = override_current_user
        yield state

    app.dependency_overrides.clear()
    await engine.dispose()


async def _org(sf, slug: str) -> str:
    org_id = uuid.uuid4()
    async with sf() as session:
        session.add(Organization(id=org_id, name=slug.upper(), slug=slug))
        await session.commit()
    return str(org_id)


async def _user(sf, email: str, first_name: str | None = None) -> str:
    user_id = uuid.uuid4()
    async with sf() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                first_name=first_name,
                status=UserStatus.ACTIVE,
                is_admin=False,
                user_metadata={},
            )
        )
        await session.commit()
    return str(user_id)


async def _member(sf, org_id: str, user_id: str, role: str = "member", status: str = "active"):
    member_id = uuid.uuid4()
    async with sf() as session:
        session.add(
            OrganizationMember(
                id=member_id,
                organization_id=uuid.UUID(org_id),
                user_id=uuid.UUID(user_id),
                role=role,
                status=status,
            )
        )
        await session.commit()
    return str(member_id)


async def _grant(sf, member_id: str, app: str, role: str) -> None:
    async with sf() as session:
        session.add(
            OrganizationMemberAppRole(
                organization_member_id=uuid.UUID(member_id),
                app=app,
                role=role,
                granted_by=INTERNAL_API_KEY_PRINCIPAL,
            )
        )
        await session.commit()


async def _rows(sf, app: str = APP):
    async with sf() as session:
        result = await session.execute(
            select(OrganizationMemberAppRole)
            .where(OrganizationMemberAppRole.app == app)
            .order_by(OrganizationMemberAppRole.granted_at)
        )
        return result.scalars().all()


@pytest_asyncio.fixture
async def world(env):
    """One org with an app admin (Caro), a colleague and a second app admin."""
    org = await _org(env.sf, "madfam-ecosystem")
    caro = await _user(env.sf, "caro@example.com", first_name="Caro")
    colleague = await _user(env.sf, "colega@example.com", first_name="Colega")
    other_admin = await _user(env.sf, "otra@example.com")
    caro_m = await _member(env.sf, org, caro)
    colleague_m = await _member(env.sf, org, colleague)
    other_m = await _member(env.sf, org, other_admin)
    await _grant(env.sf, caro_m, APP, "admin")
    return {
        "org": org,
        "caro": caro,
        "colleague": colleague,
        "colleague_m": colleague_m,
        "other_admin": other_admin,
        "other_m": other_m,
    }


# ---------------------------------------------------------------------------
# Authorization matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_app_admin_can_list_grant_and_revoke(env, world):
    env.as_user(world["caro"])
    org = world["org"]

    listed = await env.client.get(_url(org, f"/{APP}"))
    assert listed.status_code == 200
    body = listed.json()
    assert body["caller_roles"] == ["admin"]
    assert {g["email"] for g in body["grants"]} == {"caro@example.com"}
    assert body["grants"][0]["name"] == "Caro"
    assert len(body["members"]) == 3

    granted = await env.client.post(
        _url(org, f"/{APP}/grant"), json={"user_id": world["colleague"], "role": "viewer"}
    )
    assert granted.status_code == 201
    assert granted.json()["claim_value"] == "creator-census:viewer"

    revoked = await env.client.post(
        _url(org, f"/{APP}/revoke"), json={"user_id": world["colleague"], "role": "viewer"}
    )
    assert revoked.status_code == 200 and revoked.json()["changed"] is True


@pytest.mark.asyncio
async def test_unauthenticated_is_refused(env, world):
    response = await env.client.get(_url(world["org"], f"/{APP}"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_member_gets_the_shared_404_on_every_route(env, world):
    outsider = await _user(env.sf, "fuera@example.com")
    env.as_user(outsider)
    org = world["org"]
    payload = {"user_id": world["colleague"], "role": "viewer"}

    responses = [
        await env.client.get(_url(org)),
        await env.client.get(_url(org, f"/{APP}")),
        await env.client.post(_url(org, f"/{APP}/grant"), json=payload),
        await env.client.post(_url(org, f"/{APP}/revoke"), json=payload),
    ]
    for response in responses:
        assert response.status_code == 404
        assert _detail(response) == NO_MEMBERSHIP_DETAIL
    assert len(await _rows(env.sf)) == 1


@pytest.mark.asyncio
async def test_unknown_org_answers_exactly_like_a_non_member_org(env, world):
    env.as_user(world["caro"])
    response = await env.client.get(_url(str(uuid.uuid4()), f"/{APP}"))
    assert response.status_code == 404
    assert _detail(response) == NO_MEMBERSHIP_DETAIL


@pytest.mark.asyncio
async def test_member_without_the_app_role_is_403(env, world):
    env.as_user(world["colleague"])
    org = world["org"]
    assert (await env.client.get(_url(org, f"/{APP}"))).status_code == 403
    response = await env.client.post(
        _url(org, f"/{APP}/grant"), json={"user_id": world["colleague"], "role": "admin"}
    )
    assert response.status_code == 403
    assert len(await _rows(env.sf)) == 1


@pytest.mark.parametrize("org_role", ["owner", "admin"])
@pytest.mark.asyncio
async def test_org_owner_or_admin_without_app_admin_is_403(env, world, org_role):
    """NOTHING IS IMPLICIT: org authority over the account is not app authority."""
    boss = await _user(env.sf, f"{org_role}@example.com")
    await _member(env.sf, world["org"], boss, role=org_role)
    env.as_user(boss)

    response = await env.client.post(
        _url(world["org"], f"/{APP}/grant"), json={"user_id": boss, "role": "viewer"}
    )
    assert response.status_code == 403
    assert (await env.client.get(_url(world["org"], f"/{APP}"))).status_code == 403


@pytest.mark.asyncio
async def test_admin_of_a_different_app_is_403(env, world):
    await _grant(env.sf, world["colleague_m"], "hcm", "admin")
    env.as_user(world["colleague"])

    response = await env.client.post(
        _url(world["org"], f"/{APP}/grant"), json={"user_id": world["colleague"], "role": "viewer"}
    )
    assert response.status_code == 403
    # ...while their own app is theirs to administer.
    own = await env.client.post(
        _url(world["org"], "/hcm/grant"), json={"user_id": world["other_admin"], "role": "hr"}
    )
    assert own.status_code == 201


@pytest.mark.asyncio
async def test_same_app_admin_in_another_org_is_the_shared_404(env, world):
    other_org = await _org(env.sf, "otra-org")
    stranger = await _user(env.sf, "admin-otra@example.com")
    stranger_m = await _member(env.sf, other_org, stranger)
    await _grant(env.sf, stranger_m, APP, "admin")
    env.as_user(stranger)

    response = await env.client.post(
        _url(world["org"], f"/{APP}/grant"), json={"user_id": stranger, "role": "admin"}
    )
    assert response.status_code == 404
    assert _detail(response) == NO_MEMBERSHIP_DETAIL


@pytest.mark.asyncio
async def test_admin_cannot_grant_to_a_member_of_another_org(env, world):
    other_org = await _org(env.sf, "otra-org")
    stranger = await _user(env.sf, "fuera@example.com")
    await _member(env.sf, other_org, stranger)
    env.as_user(world["caro"])

    response = await env.client.post(
        _url(world["org"], f"/{APP}/grant"), json={"user_id": stranger, "role": "viewer"}
    )
    assert response.status_code == 404
    assert _detail(response) == NO_MEMBERSHIP_DETAIL


@pytest.mark.asyncio
async def test_removed_admin_membership_confers_nothing(env, world):
    ex = await _user(env.sf, "ex@example.com")
    ex_m = await _member(env.sf, world["org"], ex, status="removed")
    await _grant(env.sf, ex_m, APP, "admin")
    env.as_user(ex)

    response = await env.client.get(_url(world["org"], f"/{APP}"))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Email resolution scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_by_email_resolves_among_this_orgs_active_members(env, world):
    env.as_user(world["caro"])
    response = await env.client.post(
        _url(world["org"], f"/{APP}/grant"),
        json={"email": "  COLEGA@example.com ", "role": "viewer"},
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == world["colleague"]


@pytest.mark.asyncio
async def test_grant_by_email_never_reaches_a_user_outside_the_org(env, world):
    other_org = await _org(env.sf, "otra-org")
    outsider = await _user(env.sf, "fuera@example.com")
    await _member(env.sf, other_org, outsider)
    await _user(env.sf, "sin-org@example.com")
    env.as_user(world["caro"])

    for email in ("fuera@example.com", "sin-org@example.com", "nadie@example.com"):
        response = await env.client.post(
            _url(world["org"], f"/{APP}/grant"), json={"email": email, "role": "viewer"}
        )
        assert response.status_code == 404, email
        assert _detail(response) == NO_MEMBERSHIP_DETAIL
    assert len(await _rows(env.sf)) == 1


@pytest.mark.asyncio
async def test_grant_by_email_skips_inactive_members(env, world):
    gone = await _user(env.sf, "baja@example.com")
    await _member(env.sf, world["org"], gone, status="removed")
    env.as_user(world["caro"])
    response = await env.client.post(
        _url(world["org"], f"/{APP}/grant"), json={"email": "baja@example.com", "role": "viewer"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_grant_names_exactly_one_target(env, world):
    env.as_user(world["caro"])
    both = {"user_id": world["colleague"], "email": "colega@example.com", "role": "viewer"}
    neither = {"role": "viewer"}
    for payload in (both, neither):
        response = await env.client.post(_url(world["org"], f"/{APP}/grant"), json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Self-change refusal and the last-admin guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_caller_cannot_revoke_or_grant_their_own_admin(env, world):
    env.as_user(world["caro"])
    for verb in ("revoke", "grant"):
        response = await env.client.post(
            _url(world["org"], f"/{APP}/{verb}"), json={"user_id": world["caro"], "role": "admin"}
        )
        assert response.status_code == 403, verb
    rows = await _rows(env.sf)
    assert len(rows) == 1 and rows[0].revoked_at is None


@pytest.mark.asyncio
async def test_another_admin_may_revoke_an_admin_when_one_remains(env, world):
    env.as_user(world["caro"])
    org = world["org"]
    await env.client.post(
        _url(org, f"/{APP}/grant"), json={"user_id": world["other_admin"], "role": "admin"}
    )

    env.as_user(world["other_admin"])
    response = await env.client.post(
        _url(org, f"/{APP}/revoke"), json={"user_id": world["caro"], "role": "admin"}
    )
    assert response.status_code == 200 and response.json()["changed"] is True


@pytest.mark.asyncio
async def test_revoking_the_last_admin_is_409(env, world):
    """Reachable through the API only by two admins revoking each other at once
    (self-change is refused), so the guard is exercised directly."""
    async with env.sf() as session:
        caro_m = (
            await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == uuid.UUID(world["caro"])
                )
            )
        ).scalar_one()
        with pytest.raises(HTTPException) as excinfo:
            await ensure_not_last_admin(session, uuid.UUID(world["org"]), APP, caro_m.id)
    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == LAST_ADMIN_DETAIL


@pytest.mark.asyncio
async def test_an_admin_grant_on_a_removed_membership_does_not_count(env, world):
    """A grant on a REMOVED membership feeds no token, so it is not a remaining
    admin: with only such a row left beside Caro, revoking Caro is still 409."""
    ex = await _user(env.sf, "ex@example.com")
    ex_m = await _member(env.sf, world["org"], ex, status="removed")
    await _grant(env.sf, ex_m, APP, "admin")
    async with env.sf() as session:
        caro_m = (
            await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == uuid.UUID(world["caro"])
                )
            )
        ).scalar_one()
        with pytest.raises(HTTPException) as excinfo:
            await ensure_not_last_admin(session, uuid.UUID(world["org"]), APP, caro_m.id)
        # With a second ACTIVE admin, the same revoke is allowed.
        await _grant(env.sf, world["other_m"], APP, "admin")
        await ensure_not_last_admin(session, uuid.UUID(world["org"]), APP, caro_m.id)
    assert excinfo.value.status_code == 409


# ---------------------------------------------------------------------------
# Idempotency, history, audit, shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_is_201_then_200_and_never_refreshes_the_original(env, world):
    env.as_user(world["caro"])
    payload = {"user_id": world["colleague"], "role": "viewer"}
    first = await env.client.post(_url(world["org"], f"/{APP}/grant"), json=payload)
    second = await env.client.post(_url(world["org"], f"/{APP}/grant"), json=payload)

    assert first.status_code == 201 and first.json()["changed"] is True
    assert second.status_code == 200 and second.json()["changed"] is False
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["granted_at"] == first.json()["granted_at"]


@pytest.mark.asyncio
async def test_revoke_stamps_revoked_at_and_regrant_is_a_new_row(env, world):
    env.as_user(world["caro"])
    payload = {"user_id": world["colleague"], "role": "viewer"}
    first = await env.client.post(_url(world["org"], f"/{APP}/grant"), json=payload)
    revoked = await env.client.post(_url(world["org"], f"/{APP}/revoke"), json=payload)
    again = await env.client.post(_url(world["org"], f"/{APP}/revoke"), json=payload)
    second = await env.client.post(_url(world["org"], f"/{APP}/grant"), json=payload)

    assert revoked.json()["revoked_at"] is not None
    assert again.status_code == 200 and again.json()["changed"] is False
    assert second.status_code == 201 and second.json()["id"] != first.json()["id"]

    viewer_rows = [r for r in await _rows(env.sf) if r.role == "viewer"]
    assert len(viewer_rows) == 2
    assert viewer_rows[0].revoked_at is not None and viewer_rows[1].revoked_at is None


@pytest.mark.asyncio
async def test_rows_and_audit_name_the_caller_not_the_internal_principal(env, world):
    env.as_user(world["caro"])
    payload = {"user_id": world["colleague"], "role": "viewer"}
    audit_instance = MagicMock()
    audit_instance.log = AsyncMock(return_value="audit-id")
    with patch("app.routers.v1.organization_app_roles.AuditLogger", return_value=audit_instance):
        await env.client.post(_url(world["org"], f"/{APP}/grant"), json=payload)
        await env.client.post(_url(world["org"], f"/{APP}/revoke"), json=payload)

    row = [r for r in await _rows(env.sf) if r.role == "viewer"][0]
    assert row.granted_by == world["caro"]
    assert row.revoked_by == world["caro"]
    assert INTERNAL_API_KEY_PRINCIPAL not in (row.granted_by, row.revoked_by)

    calls = audit_instance.log.await_args_list
    assert [c.kwargs["event_type"].value for c in calls] == ["app_role.grant", "app_role.revoke"]
    for call in calls:
        assert call.kwargs["identity_id"] == world["caro"]
        assert call.kwargs["details"]["actor"] == world["caro"]
        assert call.kwargs["details"]["user_id"] == world["colleague"]


@pytest.mark.asyncio
async def test_shape_validation_on_path_app_and_body_role(env, world):
    env.as_user(world["caro"])
    org = world["org"]
    bad_role = await env.client.post(
        _url(org, f"/{APP}/grant"), json={"user_id": world["colleague"], "role": "a:b"}
    )
    spaced_role = await env.client.post(
        _url(org, f"/{APP}/grant"), json={"user_id": world["colleague"], "role": "a b"}
    )
    bad_app = await env.client.get(_url(org, "/creator-census:admin"))
    bad_org = await env.client.get("/api/v1/organizations/not-a-uuid/app-roles/x")
    assert bad_role.status_code == 422
    assert spaced_role.status_code == 422
    assert bad_app.status_code == 422
    assert bad_org.status_code == 422


# ---------------------------------------------------------------------------
# The caller's own roles, and the token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_app_roles_lists_administered_apps(env, world):
    env.as_user(world["caro"])
    response = await env.client.get(_url(world["org"]))
    assert response.status_code == 200
    assert response.json()["administered_apps"] == [APP]
    assert response.json()["claim_values"] == ["creator-census:admin"]

    env.as_user(world["colleague"])
    response = await env.client.get(_url(world["org"]))
    assert response.status_code == 200
    assert response.json()["administered_apps"] == []


@pytest.mark.asyncio
async def test_a_delegated_grant_reaches_the_claims_resolver(env, world):
    env.as_user(world["caro"])
    await env.client.post(
        _url(world["org"], f"/{APP}/grant"), json={"user_id": world["colleague"], "role": "viewer"}
    )
    async with env.sf() as session:
        user = (
            await session.execute(select(User).where(User.id == uuid.UUID(world["colleague"])))
        ).scalar_one()
        claims = await get_user_org_claims(user, session)
    assert claims.get(APP_ROLES_KEY) == ["creator-census:viewer"]
