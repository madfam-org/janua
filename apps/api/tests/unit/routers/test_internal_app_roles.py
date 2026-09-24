"""Unit tests for the internal application-roles endpoints
(POST /api/v1/internal/app-roles/{grant,revoke}, GET /{org_id}/{user_id}).

These run against a REAL SQLite-backed schema rather than mocks, so they also
exercise the model, the partial unique index, and — in the last section — the
claims resolver reading the actual table. That end-to-end pass is the point:
the unit of value is "a granted role reaches the token", and a mock of the
query cannot fail the way a wrong query would.
"""

from __future__ import annotations

import uuid

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
from app.services.org_claims_service import APP_ROLES_KEY, get_user_org_claims

INTERNAL_KEY = "test-internal-api-key-app-roles"
GRANT_URL = "/api/v1/internal/app-roles/grant"
REVOKE_URL = "/api/v1/internal/app-roles/revoke"

AUTH = {"X-Internal-API-Key": INTERNAL_KEY}


@pytest_asyncio.fixture
async def app_roles_env():
    """SQLite-backed app client plus a session factory for direct row asserts."""
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

    from unittest.mock import AsyncMock

    redis = AsyncMock()
    redis.ping.return_value = True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis

    settings.INTERNAL_API_KEY = INTERNAL_KEY

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


async def _seed_member(
    session_factory,
    *,
    org_slug: str = "crea",
    email: str = "direccion@crea.example.com",
    member_status: str = "active",
    is_service_account: bool = False,
    tenant_id: str | None = None,
) -> tuple[str, str]:
    """Create org + user + membership. Returns (organization_id, user_id)."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(Organization(id=org_id, name=org_slug.upper(), slug=org_slug))
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=None,
                status=UserStatus.ACTIVE,
                is_admin=False,
                user_metadata={},
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                is_service_account=is_service_account,
            )
        )
        session.add(
            OrganizationMember(
                id=uuid.uuid4(),
                organization_id=org_id,
                user_id=user_id,
                role="admin",
                status=member_status,
            )
        )
        await session.commit()

    return str(org_id), str(user_id)


def _payload(org_id: str, user_id: str, app_slug: str = "hcm", role: str = "hr") -> dict:
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "app": app_slug,
        "role": role,
    }


# ---------------------------------------------------------------------------
# Auth — the same trust boundary as the sibling internal routers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_without_the_internal_key_header_is_422(app_roles_env):
    """Missing header is FastAPI validation (the dependency never runs); a
    WRONG key is 401. Same split the sibling internal routers already pin."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.post(GRANT_URL, json=_payload(org_id, user_id))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_grant_with_a_wrong_internal_key_is_401(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.post(
        GRANT_URL,
        json=_payload(org_id, user_id),
        headers={"X-Internal-API-Key": "not-the-key"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Grant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_creates_the_row_and_reports_the_claim_value(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert response.status_code == 201
    body = response.json()
    assert body["changed"] is True
    assert body["claim_value"] == "hcm:hr"
    assert body["revoked_at"] is None

    async with session_factory() as session:
        rows = (await session.execute(select(OrganizationMemberAppRole))).scalars().all()
    assert len(rows) == 1
    assert rows[0].app == "hcm" and rows[0].role == "hr"
    # WHO granted it is durable on the row, not only in the audit trail.
    assert rows[0].granted_by
    assert rows[0].revoked_at is None


@pytest.mark.asyncio
async def test_grant_is_idempotent_and_does_not_refresh_the_original(app_roles_env):
    """A retry must not rewrite when the authority was first given: the answer
    to "when was this person given payroll access" is the FIRST time."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    first = await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)
    second = await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert first.status_code == 201 and first.json()["changed"] is True
    assert second.status_code == 200 and second.json()["changed"] is False
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["granted_at"] == first.json()["granted_at"]

    async with session_factory() as session:
        rows = (await session.execute(select(OrganizationMemberAppRole))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_grant_404s_when_the_user_is_not_an_active_member(app_roles_env):
    """A grant that could never feed a token is an operator error worth
    surfacing — the resolver filters `status == "active"` too."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory, member_status="removed")

    response = await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_grant_404s_for_an_organization_the_user_does_not_belong_to(app_roles_env):
    client, session_factory = app_roles_env
    _org_a, user_id = await _seed_member(session_factory, org_slug="a")
    org_b, _user_b = await _seed_member(
        session_factory, org_slug="b", email="otra@ejemplo.example.com"
    )

    response = await client.post(GRANT_URL, json=_payload(org_b, user_id), headers=AUTH)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_grant_rejects_a_separator_inside_a_component(app_roles_env):
    """The claim is f"{app}:{role}". An app of "hcm:hr" would emit "hcm:hr:x"
    and could FABRICATE a role string the resource server matches."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.post(
        GRANT_URL, json=_payload(org_id, user_id, app_slug="hcm:hr"), headers=AUTH
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_grant_rejects_blank_and_whitespace_components(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    for bad in ("", "   ", "hr admin"):
        response = await client.post(
            GRANT_URL, json=_payload(org_id, user_id, role=bad), headers=AUTH
        )
        assert response.status_code == 422, bad


@pytest.mark.asyncio
async def test_grant_stores_an_opaque_app_janua_has_never_heard_of(app_roles_env):
    """No vocabulary check: a new HCM role must not need a janua deploy."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.post(
        GRANT_URL,
        json=_payload(org_id, user_id, app_slug="cotiza", role="approver"),
        headers=AUTH,
    )

    assert response.status_code == 201
    assert response.json()["claim_value"] == "cotiza:approver"


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_retires_the_row_without_deleting_it(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)
    response = await client.post(REVOKE_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert response.status_code == 200
    assert response.json()["changed"] is True
    assert response.json()["revoked_at"] is not None

    async with session_factory() as session:
        rows = (await session.execute(select(OrganizationMemberAppRole))).scalars().all()
    # The row SURVIVES: destroying it would destroy the evidence that authority
    # over payroll was ever granted, and to whom.
    assert len(rows) == 1
    assert rows[0].revoked_at is not None
    assert rows[0].revoked_by


@pytest.mark.asyncio
async def test_revoke_is_idempotent(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)
    await client.post(REVOKE_URL, json=_payload(org_id, user_id), headers=AUTH)
    again = await client.post(REVOKE_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert again.status_code == 200
    assert again.json()["changed"] is False


@pytest.mark.asyncio
async def test_revoking_a_role_that_was_never_granted_is_success_not_404(app_roles_env):
    """The caller's desired end state is already true — the same rule that
    keeps `reactivate` from erroring on an already-active user."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.post(REVOKE_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert response.status_code == 200
    assert response.json()["changed"] is False


@pytest.mark.asyncio
async def test_regrant_after_revoke_creates_a_new_row_preserving_history(app_roles_env):
    """History is the point: the re-grant must not be an UPDATE that rewrites
    when and by whom the authority was FIRST given."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    first = await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)
    await client.post(REVOKE_URL, json=_payload(org_id, user_id), headers=AUTH)
    second = await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)

    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]

    async with session_factory() as session:
        rows = (await session.execute(select(OrganizationMemberAppRole))).scalars().all()
    assert len(rows) == 2
    assert sum(1 for r in rows if r.revoked_at is None) == 1


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_live_claim_values_and_the_full_history(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    await client.post(GRANT_URL, json=_payload(org_id, user_id, role="hr"), headers=AUTH)
    await client.post(GRANT_URL, json=_payload(org_id, user_id, role="admin"), headers=AUTH)
    await client.post(REVOKE_URL, json=_payload(org_id, user_id, role="admin"), headers=AUTH)

    response = await client.get(
        f"/api/v1/internal/app-roles/{org_id}/{user_id}", headers=AUTH
    )

    assert response.status_code == 200
    body = response.json()
    # Exactly what the next token carries — an operator answers "why can they
    # not see HR?" without decoding a JWT.
    assert body["claim_values"] == ["hcm:hr"]
    # …and the retired grant is still visible, with who took it away.
    assert len(body["grants"]) == 2
    revoked = [g for g in body["grants"] if g["revoked_at"] is not None]
    assert len(revoked) == 1 and revoked[0]["claim_value"] == "hcm:admin"
    assert revoked[0]["revoked_by"]


@pytest.mark.asyncio
async def test_list_never_reports_another_organizations_grants(app_roles_env):
    client, session_factory = app_roles_env
    org_a, user_a = await _seed_member(session_factory, org_slug="a")
    org_b, user_b = await _seed_member(
        session_factory, org_slug="b", email="otra@ejemplo.example.com"
    )

    await client.post(GRANT_URL, json=_payload(org_a, user_a), headers=AUTH)

    response = await client.get(f"/api/v1/internal/app-roles/{org_b}/{user_b}", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["claim_values"] == []


@pytest.mark.asyncio
async def test_list_without_the_internal_key_header_is_422(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.get(f"/api/v1/internal/app-roles/{org_id}/{user_id}")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_with_a_wrong_internal_key_is_401(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    response = await client.get(
        f"/api/v1/internal/app-roles/{org_id}/{user_id}",
        headers={"X-Internal-API-Key": "not-the-key"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# End to end: a granted role reaches the CLAIM, through the real table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_granted_role_is_resolved_into_the_claim_from_the_real_table(app_roles_env):
    """The whole point of J2, against real SQL rather than a mocked query."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == org_id
    assert claims[APP_ROLES_KEY] == ["hcm:hr"]


@pytest.mark.asyncio
async def test_revoked_role_is_gone_from_the_claim_from_the_real_table(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory)

    await client.post(GRANT_URL, json=_payload(org_id, user_id), headers=AUTH)
    await client.post(REVOKE_URL, json=_payload(org_id, user_id), headers=AUTH)

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == org_id
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_another_orgs_grant_never_reaches_the_claim_from_the_real_table(app_roles_env):
    """THE cross-tenant test, against real SQL.

    One user, active in BOTH orgs, granted `hcm:hr` in org A only, with
    `tenant_id` pinning org B. Org A's HR authority must not ride into a
    session scoped to org B.
    """
    client, session_factory = app_roles_env

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    user_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(Organization(id=org_a, name="A", slug="a"))
        session.add(Organization(id=org_b, name="B", slug="b"))
        session.add(
            User(
                id=user_id,
                email="dos-orgs@ejemplo.example.com",
                password_hash=None,
                status=UserStatus.ACTIVE,
                is_admin=False,
                user_metadata={},
                # Pins org B as the primary, so the claim is unambiguous.
                tenant_id=org_b,
                is_service_account=False,
            )
        )
        for org in (org_a, org_b):
            session.add(
                OrganizationMember(
                    id=uuid.uuid4(),
                    organization_id=org,
                    user_id=user_id,
                    role="admin",
                    status="active",
                )
            )
        await session.commit()

    granted = await client.post(
        GRANT_URL, json=_payload(str(org_a), str(user_id)), headers=AUTH
    )
    assert granted.status_code == 201

    async with session_factory() as session:
        user = await session.get(User, user_id)
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == str(org_b)
    # Org A's grant exists, and does not leak into org B's session.
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_service_account_without_a_grant_resolves_no_application_roles(app_roles_env):
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory, is_service_account=True)

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == org_id
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_service_account_with_an_explicit_grant_resolves_it(app_roles_env):
    """A service principal is granted authority on the same terms as a person:
    explicitly. Being a technical login neither confers nor withholds a role."""
    client, session_factory = app_roles_env
    org_id, user_id = await _seed_member(session_factory, is_service_account=True)

    await client.post(
        GRANT_URL,
        json=_payload(org_id, user_id, role="importer"),
        headers=AUTH,
    )

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        claims = await get_user_org_claims(user, session)

    assert claims[APP_ROLES_KEY] == ["hcm:importer"]
