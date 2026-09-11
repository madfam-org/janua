"""Unit tests for GET /api/v1/internal/orgs/{org_id}/entitlements.

Run against a REAL SQLite-backed schema rather than mocks, so they exercise the
model, the router wiring, the internal-key auth boundary, and the response shape
end to end — the unit of value is "an advisor viewing a client resolves the
CLIENT ORG'S tiles, over a service credential", and a mock of the query cannot
fail the way a wrong query would.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import app
from app.models import Base, Organization

INTERNAL_KEY = "test-internal-api-key-org-entitlements"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}


def _url(org_id: str) -> str:
    return f"/api/v1/internal/orgs/{org_id}/entitlements"


@pytest_asyncio.fixture
async def org_entitlements_env():
    """SQLite-backed app client plus a session factory for direct row seeding."""
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

    # The endpoint depends on `app.core.database.get_db` (same as me.py), so that
    # is the object the override must key on.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis

    settings.INTERNAL_API_KEY = INTERNAL_KEY

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


async def _seed_org(session_factory, *, product_tiers) -> str:
    org_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Organization(
                id=org_id,
                name="CREA",
                slug=f"crea-{org_id.hex[:8]}",
                product_tiers=product_tiers,
            )
        )
        await session.commit()
    return str(org_id)


# ---------------------------------------------------------------------------
# Auth — the same trust boundary as the sibling internal routers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_internal_key_header_is_422(org_entitlements_env):
    """A missing header is FastAPI validation (the dependency never runs)."""
    client, _ = org_entitlements_env
    resp = await client.get(_url(str(uuid.uuid4())))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_wrong_internal_key_is_401(org_entitlements_env):
    client, _ = org_entitlements_env
    resp = await client.get(_url(str(uuid.uuid4())), headers={"X-Internal-API-Key": "nope"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# The read — the org's OWN tiles, in the /me/entitlements shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolves_the_org_product_tiers(org_entitlements_env):
    """The core case: the endpoint returns the ORG'S tiles, sorted, as inherited.

    This is what makes the nauta advisor path correct — an advisor viewing this
    workspace resolves THESE tiles, not the advisor's own (empty) set.
    """
    client, session_factory = org_entitlements_env
    org_id = await _seed_org(
        session_factory, product_tiers={"kalya": "team", "karafiel": "contador"}
    )

    resp = await client.get(_url(org_id), headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    # Sorted by slug, mirroring /me/entitlements.
    assert [p["slug"] for p in body["products"]] == ["kalya", "karafiel"]
    assert [p["tier"] for p in body["products"]] == ["team", "contador"]
    # Every row is inherited (an org tier), and the source leaks as a string.
    assert all(p["source"] == "inherited" for p in body["products"])
    # The claim shape matches what the JWT claim / /me endpoint produce.
    assert body["claim_string_form"] == ["kalya:team", "karafiel:contador"]


@pytest.mark.asyncio
async def test_org_with_no_tiers_returns_empty_set(org_entitlements_env):
    """An org that grants nothing is a POSITIVE empty answer, not an error."""
    client, session_factory = org_entitlements_env
    org_id = await _seed_org(session_factory, product_tiers={})

    resp = await client.get(_url(org_id), headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["products"] == []
    assert body["claim_string_form"] == []


@pytest.mark.asyncio
async def test_unknown_org_returns_empty_set(org_entitlements_env):
    """An org id that exists as a well-formed UUID but names no row resolves to
    the empty set — "this org grants nothing" — never a 500."""
    client, _ = org_entitlements_env
    resp = await client.get(_url(str(uuid.uuid4())), headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["products"] == []


@pytest.mark.asyncio
async def test_malformed_org_id_is_422(org_entitlements_env):
    """A non-UUID id is a client error, not an empty set: we cannot claim an org
    grants nothing when we could not parse which org was asked about."""
    client, _ = org_entitlements_env
    resp = await client.get(_url("not-a-uuid"), headers=AUTH)
    assert resp.status_code == 422
