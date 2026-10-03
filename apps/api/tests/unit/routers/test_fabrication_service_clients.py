"""Fabrication edges: pravara-api and asset-shells-api service clients.

Pins the seed definitions (docs/service-tokens.md, "Fabrication edges") and
proves, through POST /api/v1/oauth/token, that an organization-bound client
gets `tenant_id` (= the organization id) and a platform-admin client does not.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import reserved_oauth_boundaries as reserved
from app.core.database import get_db as core_get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, OAuthClient, Organization, User, UserStatus
from scripts.seed_service_clients import (
    ORG_BOUND_SERVICE_CLIENTS,
    SERVICE_CLIENTS,
    org_bound_client,
)

TOKEN_URL = "/api/v1/oauth/token"

# Placeholder credentials for tests only — never real secrets.
INTAKE_CLIENT_ID = "jnc_test_forj_pravara_intake"
INTAKE_SECRET = "jns_test_forj_pravara_placeholder"
TYPES_CLIENT_ID = "jnc_test_y4d_asset_shells_types"
TYPES_SECRET = "jns_test_y4d_types_placeholder"

PLATFORM_EDGES = {
    "pravara-yantra4d-step-reader": ("yantra4d-api", ["yantra4d:render"]),
    "yantra4d-asset-shells-publisher": ("asset-shells-api", ["asset-shells:publish-types"]),
    "fashion-cabinet-asset-shells-publisher": (
        "asset-shells-api",
        ["asset-shells:publish-types"],
    ),
}
ORG_BOUND_EDGES = {
    "pravara-asset-shells-publisher": (
        "asset-shells-api",
        ["asset-shells:publish-instances", "asset-shells:read"],
    ),
    "forj-pravara-intake": ("pravara-api", ["pravara-mes:jobs"]),
    "cotiza-pravara-intake": ("pravara-api", ["pravara-mes:jobs"]),
}


class TestSeedDefinitions:
    @pytest.mark.parametrize("name", sorted(PLATFORM_EDGES))
    def test_platform_admin_edges(self, name):
        entry = next(c for c in SERVICE_CLIENTS if c["name"] == name)
        audience, scopes = PLATFORM_EDGES[name]
        assert entry["audience"] == audience
        assert entry["allowed_scopes"] == scopes
        assert entry["grant_types"] == ["client_credentials"]
        assert entry["redirect_uris"] == []
        assert entry["is_confidential"] is True
        # States its binding, so the seed refuses to re-bind an existing row.
        assert "organization_id" in entry and entry["organization_id"] is None

    @pytest.mark.parametrize("name", sorted(ORG_BOUND_EDGES))
    def test_org_bound_templates(self, name):
        entry = next(c for c in ORG_BOUND_SERVICE_CLIENTS if c["name"] == name)
        audience, scopes = ORG_BOUND_EDGES[name]
        assert entry["audience"] == audience
        assert entry["allowed_scopes"] == scopes
        assert entry["grant_types"] == ["client_credentials"]
        assert "organization_id" not in entry, "templates are never seeded unbound"

    def test_every_new_value_is_reserved(self):
        for audience, scopes in (*PLATFORM_EDGES.values(), *ORG_BOUND_EDGES.values()):
            assert reserved.is_reserved_audience(audience)
            assert all(reserved.is_reserved_scope(s) for s in scopes)

    def test_template_names_do_not_collide_with_platform_clients(self):
        platform = {c["name"] for c in SERVICE_CLIENTS}
        templates = {c["name"] for c in ORG_BOUND_SERVICE_CLIENTS}
        assert not platform & templates
        assert len(platform) == len(SERVICE_CLIENTS)

    def test_org_bound_client_is_named_and_bound_per_organization(self):
        org_a, org_b = str(uuid.uuid4()), str(uuid.uuid4())
        a = org_bound_client("forj-pravara-intake", org_a, "fab-a")
        b = org_bound_client("forj-pravara-intake", org_b, "fab-b")
        assert a["name"] == "forj-pravara-intake.fab-a"
        assert b["name"] == "forj-pravara-intake.fab-b"
        assert a["organization_id"] == org_a and b["organization_id"] == org_b
        assert a["allowed_scopes"] == ["pravara-mes:jobs"]
        # The template itself is untouched.
        template = next(c for c in ORG_BOUND_SERVICE_CLIENTS if c["name"] == "forj-pravara-intake")
        assert "organization_id" not in template

    def test_org_bound_client_refuses_unknown_template_or_missing_org(self):
        with pytest.raises(SystemExit):
            org_bound_client("no-such-edge", str(uuid.uuid4()), "fab")
        with pytest.raises(SystemExit):
            org_bound_client("forj-pravara-intake", "", "fab")


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest_asyncio.fixture
async def fabrication_clients():
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
    redis.get.return_value = None
    redis.set.return_value = True
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis

    admin_id = uuid.uuid4()
    org_id = uuid.uuid4()
    intake = org_bound_client("forj-pravara-intake", str(org_id), "fab-floor")
    types = next(c for c in SERVICE_CLIENTS if c["name"] == "yantra4d-asset-shells-publisher")

    async with session_factory() as session:
        session.add(
            User(
                id=admin_id,
                email="admin-fabrication@janua.test",
                email_verified=True,
                status=UserStatus.ACTIVE,
                is_admin=True,
                is_active=True,
            )
        )
        session.add(Organization(id=org_id, name="Fab floor", slug="fab-floor", owner_id=admin_id))
        for definition, client_id, secret, organization_id in (
            (intake, INTAKE_CLIENT_ID, INTAKE_SECRET, org_id),
            (types, TYPES_CLIENT_ID, TYPES_SECRET, None),
        ):
            session.add(
                OAuthClient(
                    id=uuid.uuid4(),
                    created_by=admin_id,
                    organization_id=organization_id,
                    client_id=client_id,
                    client_secret_hash=_hash(secret),
                    client_secret_prefix=secret[:8],
                    name=definition["name"],
                    redirect_uris=[],
                    allowed_scopes=definition["allowed_scopes"],
                    grant_types=definition["grant_types"],
                    audience=definition["audience"],
                    is_active=True,
                    is_confidential=True,
                )
            )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, str(org_id)

    app.dependency_overrides.clear()
    await engine.dispose()


async def _token(client, client_id, secret, scope):
    return await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
            "scope": scope,
        },
    )


class TestFabricationTokens:
    async def test_org_bound_intake_token_carries_tenant(self, fabrication_clients):
        client, org_id = fabrication_clients
        response = await _token(client, INTAKE_CLIENT_ID, INTAKE_SECRET, "pravara-mes:jobs")
        assert response.status_code == 200, response.text
        claims = jwt_manager.verify_token(
            response.json()["access_token"], token_type="access", audience="pravara-api"
        )
        assert claims is not None
        assert claims["aud"] == "pravara-api"
        assert claims["scope"] == "pravara-mes:jobs"
        assert claims["token_use"] == "client_credentials"
        assert claims["actor_type"] == "service_account"
        assert claims["tenant_id"] == org_id
        assert claims["org_id"] == org_id

    async def test_intake_client_cannot_widen_to_other_pravara_scopes(self, fabrication_clients):
        client, _ = fabrication_clients
        response = await _token(
            client, INTAKE_CLIENT_ID, INTAKE_SECRET, "pravara-mes:jobs pravara-mes:nodes"
        )
        assert response.status_code == 400

    async def test_platform_type_publisher_has_no_tenant(self, fabrication_clients):
        client, _ = fabrication_clients
        response = await _token(client, TYPES_CLIENT_ID, TYPES_SECRET, "asset-shells:publish-types")
        assert response.status_code == 200, response.text
        claims = jwt_manager.verify_token(
            response.json()["access_token"], token_type="access", audience="asset-shells-api"
        )
        assert claims is not None
        assert claims["scope"] == "asset-shells:publish-types"
        assert "tenant_id" not in claims

    async def test_type_publisher_cannot_publish_instances(self, fabrication_clients):
        client, _ = fabrication_clients
        response = await _token(
            client, TYPES_CLIENT_ID, TYPES_SECRET, "asset-shells:publish-instances"
        )
        assert response.status_code == 400
