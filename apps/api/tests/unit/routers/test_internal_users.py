"""
Unit tests for the internal user provisioning + lifecycle endpoints
(POST /api/v1/internal/users/{provision,suspend,reactivate}).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, Organization, OrganizationMember, User, UserStatus
from app.services.org_claims_service import ORG_ROLES_CLAIM, get_user_org_claims

INTERNAL_KEY = "test-internal-api-key-provisioning"
PROVISION_URL = "/api/v1/internal/users/provision"
SUSPEND_URL = "/api/v1/internal/users/suspend"
REACTIVATE_URL = "/api/v1/internal/users/reactivate"

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())

AUTH = {"X-Internal-API-Key": INTERNAL_KEY}


@pytest_asyncio.fixture
async def provisioning_env():
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


@pytest_asyncio.fixture
async def provisioning_client(provisioning_env):
    client, _ = provisioning_env
    return client


def _provision_payload(
    email: str = "integrante@crea.example.com",
    tenant_id: str = TENANT_A,
    first_name: str = "Ana",
    last_name: str | None = "Ruiz",
) -> dict:
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "tenant_id": tenant_id,
    }


async def _get_user(session_factory, user_id: str) -> User:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        return result.scalar_one()


# ---------------------------------------------------------------- provision


@pytest.mark.asyncio
async def test_provision_creates_active_passwordless_user(provisioning_env):
    client, session_factory = provisioning_env
    response = await client.post(PROVISION_URL, json=_provision_payload(), headers=AUTH)

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["email"] == "integrante@crea.example.com"
    assert body["status"] == UserStatus.ACTIVE.value

    user = await _get_user(session_factory, body["id"])
    # Magic-link only: janua must hold no password material for this identity.
    assert user.password_hash is None
    assert user.email_verified is False
    assert user.email_verified_at is None
    assert user.is_admin is False
    assert user.status == UserStatus.ACTIVE
    # Org STAFF live in the PLATFORM pool: the organization binding is the
    # membership row, not a column on `users`. Setting users.tenant_id here is
    # what hid 21 CTM accounts from the magic-link lookup (see ADR-001).
    assert user.tenant_id is None
    assert user.first_name == "Ana"
    assert user.last_name == "Ruiz"
    assert user.user_metadata == {}


@pytest.mark.asyncio
async def test_provision_is_idempotent(provisioning_env):
    client, session_factory = provisioning_env
    payload = _provision_payload(email="idempotent@crea.example.com")

    first = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert first.status_code == 201
    assert first.json()["created"] is True

    second = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]

    # Exactly one row — the second call must not have created a duplicate.
    async with session_factory() as session:
        count = await session.execute(
            select(func.count(User.id)).where(User.email == "idempotent@crea.example.com")
        )
        assert count.scalar() == 1


@pytest.mark.asyncio
async def test_provision_idempotency_is_case_insensitive(provisioning_env):
    client, session_factory = provisioning_env

    first = await client.post(
        PROVISION_URL, json=_provision_payload(email="Foo@Bar.example.com"), headers=AUTH
    )
    assert first.status_code == 201
    # The stored value is folded, not the raw input.
    assert first.json()["email"] == "foo@bar.example.com"

    second = await client.post(
        PROVISION_URL, json=_provision_payload(email="foo@bar.example.com"), headers=AUTH
    )
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]

    async with session_factory() as session:
        count = await session.execute(
            select(func.count(User.id)).where(User.email == "foo@bar.example.com")
        )
        assert count.scalar() == 1


@pytest.mark.asyncio
async def test_provision_same_email_different_tenant_is_a_separate_user(provisioning_env):
    """With identity_pool="tenant", email is unique PER TENANT.

    This is the BaaS end-user shape, now reached explicitly rather than as a
    side effect of naming an organization.

    IMPORTANT — SQLite cannot express migration 013's PARTIAL unique indexes: it
    drops the `WHERE tenant_id IS NULL` predicate from `uq_users_email_global`
    and so enforces an unconditional global UNIQUE(email). Under Postgres the
    second INSERT below is legal; under SQLite it raises IntegrityError. That is
    a harness artifact, NOT router behaviour, so this test asserts the thing the
    router actually decides: that a lookup for the same email in another tenant
    does NOT resolve to tenant A's user, i.e. it takes the create branch.
    """
    client, session_factory = provisioning_env
    email = "shared@crea.example.com"

    in_a = await client.post(
        PROVISION_URL,
        json={**_provision_payload(email=email, tenant_id=TENANT_A), "identity_pool": "tenant"},
        headers=AUTH,
    )
    assert in_a.status_code == 201
    user_a_id = in_a.json()["id"]

    # Pool-scoped lookup must MISS in tenant B even though the address exists in
    # tenant A. If the router had done a bare (non-tenant-scoped) email select it
    # would find tenant A's row and wrongly return 200 / created:false here.
    async with session_factory() as session:
        from app.services.user_lookup import get_user_by_email

        assert await get_user_by_email(session, email, tenant_id=uuid.UUID(TENANT_A)) is not None
        assert await get_user_by_email(session, email, tenant_id=uuid.UUID(TENANT_B)) is None

    user_a = await _get_user(session_factory, user_a_id)
    assert str(user_a.tenant_id) == TENANT_A


@pytest.mark.asyncio
async def test_provision_does_not_mutate_existing_user(provisioning_env):
    """Provisioning is not synchronization: an existing profile is left alone."""
    client, session_factory = provisioning_env
    email = "existing@crea.example.com"

    first = await client.post(
        PROVISION_URL,
        json=_provision_payload(email=email, first_name="Original", last_name="Name"),
        headers=AUTH,
    )
    assert first.status_code == 201

    second = await client.post(
        PROVISION_URL,
        json=_provision_payload(email=email, first_name="Changed", last_name="Different"),
        headers=AUTH,
    )
    assert second.status_code == 200

    user = await _get_user(session_factory, first.json()["id"])
    assert user.first_name == "Original"
    assert user.last_name == "Name"


@pytest.mark.asyncio
async def test_provision_never_returns_password_material(provisioning_client: AsyncClient):
    response = await provisioning_client.post(
        PROVISION_URL, json=_provision_payload(email="nosecrets@crea.example.com"), headers=AUTH
    )
    assert response.status_code == 201
    raw = response.text.lower()
    assert "password" not in raw
    assert "hash" not in raw
    assert "token" not in raw


# ------------------------------------------------------------------ suspend


@pytest.mark.asyncio
async def test_suspend_sets_status_and_is_active_false(provisioning_env):
    client, session_factory = provisioning_env
    email = "suspendme@crea.example.com"
    created = await client.post(PROVISION_URL, json=_provision_payload(email=email), headers=AUTH)
    user_id = created.json()["id"]

    response = await client.post(
        SUSPEND_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["status"] == UserStatus.SUSPENDED.value
    assert body["id"] == user_id

    user = await _get_user(session_factory, user_id)
    assert user.status == UserStatus.SUSPENDED
    assert user.is_active is False
    # Metadata was rebuilt-and-reassigned, so it actually flushed.
    assert user.user_metadata["suspended_at"]
    assert user.user_metadata["suspended_by"] == "internal-api-key"


@pytest.mark.asyncio
async def test_suspend_is_idempotent(provisioning_client: AsyncClient):
    email = "suspendtwice@crea.example.com"
    await provisioning_client.post(
        PROVISION_URL, json=_provision_payload(email=email), headers=AUTH
    )

    first = await provisioning_client.post(
        SUSPEND_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
    )
    assert first.status_code == 200
    assert first.json()["changed"] is True

    second = await provisioning_client.post(
        SUSPEND_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
    )
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert second.json()["status"] == UserStatus.SUSPENDED.value


@pytest.mark.asyncio
async def test_suspend_unknown_email_is_404(provisioning_client: AsyncClient):
    response = await provisioning_client.post(
        SUSPEND_URL, json={"email": "ghost@crea.example.com", "tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_suspend_is_tenant_scoped(provisioning_client: AsyncClient):
    """A user in org A must not be suspendable via org B.

    Staff are platform-pooled (users.tenant_id IS NULL), so this scope check is
    enforced by the ORGANIZATION MEMBERSHIP rather than by the users column —
    see `_resolve_provisioned_user`. The guarantee is unchanged; only the
    mechanism moved.
    """
    email = "scoped@crea.example.com"
    await provisioning_client.post(
        PROVISION_URL, json=_provision_payload(email=email, tenant_id=TENANT_A), headers=AUTH
    )

    response = await provisioning_client.post(
        SUSPEND_URL, json={"email": email, "tenant_id": TENANT_B}, headers=AUTH
    )
    assert response.status_code == 404


# --------------------------------------------------------------- reactivate


@pytest.mark.asyncio
async def test_reactivate_restores_active_and_is_active_true(provisioning_env):
    client, session_factory = provisioning_env
    email = "comeback@crea.example.com"
    created = await client.post(PROVISION_URL, json=_provision_payload(email=email), headers=AUTH)
    user_id = created.json()["id"]

    await client.post(SUSPEND_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH)

    response = await client.post(
        REACTIVATE_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 200
    assert response.json()["changed"] is True
    assert response.json()["status"] == UserStatus.ACTIVE.value

    user = await _get_user(session_factory, user_id)
    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True
    # Suspension keys cleared, reactivation stamped.
    assert "suspended_at" not in user.user_metadata
    assert "suspended_by" not in user.user_metadata
    assert user.user_metadata["reactivated_at"]
    assert user.user_metadata["reactivated_by"] == "internal-api-key"


@pytest.mark.asyncio
async def test_reactivate_already_active_is_success_not_error(provisioning_client: AsyncClient):
    """Already-active is the caller's desired end state, so 200 + changed:false."""
    email = "alreadyactive@crea.example.com"
    await provisioning_client.post(
        PROVISION_URL, json=_provision_payload(email=email), headers=AUTH
    )

    response = await provisioning_client.post(
        REACTIVATE_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 200
    assert response.json()["changed"] is False
    assert response.json()["status"] == UserStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_reactivate_unknown_email_is_404(provisioning_client: AsyncClient):
    response = await provisioning_client.post(
        REACTIVATE_URL,
        json={"email": "ghost@crea.example.com", "tenant_id": TENANT_A},
        headers=AUTH,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------- auth


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [PROVISION_URL, SUSPEND_URL, REACTIVATE_URL])
async def test_missing_internal_key_header_is_422(provisioning_client: AsyncClient, url: str):
    response = await provisioning_client.post(url, json=_provision_payload())
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [PROVISION_URL, SUSPEND_URL, REACTIVATE_URL])
async def test_wrong_internal_key_is_401(provisioning_client: AsyncClient, url: str):
    response = await provisioning_client.post(
        url, json=_provision_payload(), headers={"X-Internal-API-Key": "wrong-key"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [PROVISION_URL, SUSPEND_URL, REACTIVATE_URL])
async def test_unset_internal_key_is_503(provisioning_client: AsyncClient, url: str):
    settings.INTERNAL_API_KEY = None
    try:
        response = await provisioning_client.post(url, json=_provision_payload(), headers=AUTH)
        assert response.status_code == 503
    finally:
        settings.INTERNAL_API_KEY = INTERNAL_KEY


@pytest.mark.asyncio
async def test_tenant_id_is_required(provisioning_client: AsyncClient):
    """Never defaulted: a missing tenant must fail loudly, not pick a pool."""
    response = await provisioning_client.post(
        PROVISION_URL,
        json={"email": "notenant@crea.example.com", "first_name": "Ana"},
        headers=AUTH,
    )
    assert response.status_code == 422


# ------------------------------------------------- provision: org membership
#
# The point of these: writing `tenant_id` on the user row is NOT what grants
# access. `org_claims_service.get_user_org_claims` counts only memberships with
# `status == "active"`, so a user with a tenant_id but no membership gets a
# token WITHOUT `org_id` — and symbiosis-hcm's `TenantRolePermission` rejects a
# token without one. Before this change every identity provisioned from the MAP
# was in exactly that state, so «Mi espacio (RH)» 403'd for the whole CTM team.


async def _memberships(session_factory, user_id: str) -> list[OrganizationMember]:
    async with session_factory() as session:
        result = await session.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == uuid.UUID(user_id))
        )
        return list(result.scalars().all())


async def _seed_org(session_factory, org_id: str, slug: str) -> None:
    """An `organizations` row for `org_id`, so the claims join can resolve it."""
    async with session_factory() as session:
        session.add(Organization(id=uuid.UUID(org_id), name=slug, slug=slug))
        await session.commit()


@pytest.mark.asyncio
async def test_provision_creates_active_org_membership(provisioning_env):
    client, session_factory = provisioning_env
    response = await client.post(
        PROVISION_URL, json=_provision_payload(email="conmembresia@crea.example.com"), headers=AUTH
    )

    assert response.status_code == 201
    body = response.json()
    # Reported in the response so the roster app can verify the person will
    # actually carry `org_id`, without decoding a token.
    assert body["org_role"] == "member"

    rows = await _memberships(session_factory, body["id"])
    assert len(rows) == 1
    assert str(rows[0].organization_id) == TENANT_A
    assert rows[0].status == "active"
    assert rows[0].role == "member"


@pytest.mark.asyncio
async def test_provisioned_user_resolves_org_claims(provisioning_env):
    """The end-to-end assertion this whole change exists for.

    Provision through the internal API, then run the REAL claims resolver over
    the resulting rows: the token must carry `org_id` / `org_slug`. Without the
    membership this returns `{}` and HCM answers 403.
    """
    client, session_factory = provisioning_env
    await _seed_org(session_factory, TENANT_A, "crea-tu-mundo")

    response = await client.post(
        PROVISION_URL, json=_provision_payload(email="claims@crea.example.com"), headers=AUTH
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        ).scalar_one()
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == TENANT_A
    assert claims["tenant_id"] == TENANT_A
    assert claims["org_slug"] == "crea-tu-mundo"
    assert claims[ORG_ROLES_CLAIM] == ["member"]
    assert claims["orgs"] == [{"id": TENANT_A, "slug": "crea-tu-mundo", "role": "member"}]


@pytest.mark.asyncio
async def test_provision_membership_is_idempotent(provisioning_env):
    """A retry must converge on ONE membership, not stack rows."""
    client, session_factory = provisioning_env
    payload = _provision_payload(email="reintento@crea.example.com")

    first = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert first.status_code == 201
    second = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["org_role"] == "member"

    rows = await _memberships(session_factory, first.json()["id"])
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_provision_backfills_membership_for_a_preexisting_user(provisioning_env):
    """The repair path for everyone provisioned BEFORE this change.

    Those identities already exist, so the create branch never runs for them.
    If the 200 path did not reconcile the membership they would stay locked out
    of «Mi espacio (RH)» permanently.
    """
    client, session_factory = provisioning_env
    email = "legacy@crea.example.com"

    # A user row exactly as the old endpoint left it: tenant_id set, no membership.
    async with session_factory() as session:
        legacy = User(
            email=email,
            first_name="Legacy",
            status=UserStatus.ACTIVE,
            tenant_id=uuid.UUID(TENANT_A),
            user_metadata={},
        )
        session.add(legacy)
        await session.commit()
        legacy_id = str(legacy.id)

    assert await _memberships(session_factory, legacy_id) == []

    response = await client.post(PROVISION_URL, json=_provision_payload(email=email), headers=AUTH)
    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["id"] == legacy_id
    assert response.json()["org_role"] == "member"

    rows = await _memberships(session_factory, legacy_id)
    assert len(rows) == 1
    assert rows[0].status == "active"


@pytest.mark.asyncio
async def test_provision_honours_an_explicit_org_role(provisioning_env):
    client, session_factory = provisioning_env
    payload = _provision_payload(email="coordinadora@crea.example.com")
    payload["org_role"] = "admin"

    response = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert response.status_code == 201
    assert response.json()["org_role"] == "admin"

    rows = await _memberships(session_factory, response.json()["id"])
    assert rows[0].role == "admin"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_role", ["owner", "hcm:hr", "superuser", ""])
async def test_provision_rejects_an_unknown_org_role(provisioning_client: AsyncClient, bad_role):
    """`org_role` lands in `madfam_org_roles`, so it must not be a free string.

    `owner` is rejected too, and on purpose: organization ownership is an
    operator decision, not something a roster «Alta de integrante» grants.
    """
    payload = _provision_payload(email=f"rechazado-{bad_role or 'vacio'}@crea.example.com")
    payload["org_role"] = bad_role

    response = await provisioning_client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_provision_does_not_downgrade_an_existing_membership_role(provisioning_env):
    """An operator promotion must survive a roster retry.

    Same rule the user row already follows: a re-provision reconciles EXISTENCE,
    never overwrites a value someone with more authority set in janua.
    """
    client, session_factory = provisioning_env
    payload = _provision_payload(email="promovida@crea.example.com")
    payload["org_role"] = "admin"

    created = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert created.status_code == 201
    user_id = created.json()["id"]

    # Roster retries with its default role; the promotion must stand.
    retry_payload = _provision_payload(email="promovida@crea.example.com")
    retry = await client.post(PROVISION_URL, json=retry_payload, headers=AUTH)
    assert retry.status_code == 200
    assert retry.json()["org_role"] == "admin"

    rows = await _memberships(session_factory, user_id)
    assert len(rows) == 1
    assert rows[0].role == "admin"


@pytest.mark.asyncio
async def test_provision_reactivates_a_removed_membership(provisioning_env):
    """Re-alta: a returning member gets access back, without a duplicate row."""
    client, session_factory = provisioning_env
    payload = _provision_payload(email="realta@crea.example.com")

    created = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    user_id = created.json()["id"]

    async with session_factory() as session:
        row = (
            await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == uuid.UUID(user_id)
                )
            )
        ).scalar_one()
        row.status = "removed"
        await session.commit()

    again = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert again.status_code == 200
    assert again.json()["org_role"] == "member"

    rows = await _memberships(session_factory, user_id)
    assert len(rows) == 1
    assert rows[0].status == "active"


@pytest.mark.asyncio
async def test_provision_membership_is_scoped_to_the_requested_tenant(provisioning_env):
    """The membership goes to the org the caller named — never to another one."""
    client, session_factory = provisioning_env

    response = await client.post(
        PROVISION_URL,
        json=_provision_payload(email="scoped@crea.example.com", tenant_id=TENANT_B),
        headers=AUTH,
    )
    assert response.status_code == 201

    rows = await _memberships(session_factory, response.json()["id"])
    assert len(rows) == 1
    assert str(rows[0].organization_id) == TENANT_B
    assert str(rows[0].organization_id) != TENANT_A


@pytest.mark.asyncio
async def test_service_account_provisioning_still_works_with_membership(provisioning_env):
    """#590's `is_service_account` handling is untouched by the membership write."""
    client, session_factory = provisioning_env
    payload = _provision_payload(email="robot@crea.example.com")
    payload["is_service_account"] = True

    response = await client.post(PROVISION_URL, json=payload, headers=AUTH)
    assert response.status_code == 201
    assert response.json()["is_service_account"] is True
    assert response.json()["org_role"] == "member"

    user = await _get_user(session_factory, response.json()["id"])
    assert user.is_service_account is True

    rows = await _memberships(session_factory, response.json()["id"])
    assert len(rows) == 1
