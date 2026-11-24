"""A device-only scope reaches a client only through an approved device enrolment.

``pravara-mes:terminal`` is the scope of a shared terminal's own token
(`core/device_clients.DEVICE_ONLY_SCOPES`). No ordinary client path may put it
on a client, platform admins and the internal key included, and the token
endpoint never grants it to a client that is not of kind ``device``, even when
the client's row already holds it. Revoking it stays possible.
"""

from __future__ import annotations

import uuid

import bcrypt
import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import dependencies
from app.config import settings
from app.core import redis as core_redis
from app.core.database import get_db as core_get_db
from app.core.device_clients import DEVICE_ONLY_SCOPES, DEVICE_TEMPLATES
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.database import get_db
from app.main import app
from app.models import Base, OAuthClient, Organization, User, UserStatus
from app.routers.v1 import oauth_provider_shared
from app.schemas.oauth_client import OAuthClientCreate, OAuthClientUpdate
from scripts.seed_service_clients import ORG_BOUND_SERVICE_CLIENTS, SERVICE_CLIENTS

TERMINAL = "pravara-mes:terminal"
INTERNAL_KEY = "test-internal-api-key-device-only-scopes"
SERVICE_CLIENT_ID = "jnc_test_pravara_reader"


def test_the_terminal_scope_is_device_only_and_every_template_scope_is():
    assert TERMINAL in DEVICE_ONLY_SCOPES
    for template in DEVICE_TEMPLATES.values():
        assert template.scopes <= DEVICE_ONLY_SCOPES


@pytest.mark.parametrize("scopes", [[TERMINAL], ["pravara-mes:read", TERMINAL], [f" {TERMINAL}"]])
def test_client_schemas_refuse_a_device_only_scope(scopes):
    with pytest.raises(ValidationError, match="device enrolment"):
        OAuthClientCreate(
            name="test-client",
            allowed_scopes=scopes,
            grant_types=["client_credentials"],
            audience="pravara-api",
        )
    with pytest.raises(ValidationError, match="device enrolment"):
        OAuthClientUpdate(allowed_scopes=scopes)
    # Other Pravara scopes are untouched.
    assert OAuthClientUpdate(allowed_scopes=["pravara-mes:read"]).allowed_scopes == [
        "pravara-mes:read"
    ]


def test_no_seeded_service_client_carries_a_device_only_scope():
    for client in [*SERVICE_CLIENTS, *ORG_BOUND_SERVICE_CLIENTS]:
        assert not set(client.get("allowed_scopes") or []) & DEVICE_ONLY_SCOPES, client["name"]


@pytest_asyncio.fixture
async def env(monkeypatch):
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

    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    for dependency in {
        get_redis,
        core_redis.get_redis,
        dependencies.get_redis,
        oauth_provider_shared.get_redis,
    }:
        app.dependency_overrides[dependency] = lambda: redis
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)

    admin_id, org_id = uuid.uuid4(), uuid.uuid4()
    secret = "jns_test_placeholder_" + uuid.uuid4().hex
    async with session_factory() as session:
        session.add(
            User(
                id=admin_id,
                email=f"{admin_id}@janua.test",
                email_verified=True,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_admin=True,
            )
        )
        session.add(Organization(id=org_id, name="Floor", slug=f"floor-{org_id.hex[:8]}"))
        await session.flush()
        # An ordinary Pravara machine client whose row ALREADY holds the
        # terminal scope (written straight to the database, past every API).
        session.add(
            OAuthClient(
                id=uuid.uuid4(),
                organization_id=org_id,
                created_by=admin_id,
                client_id=SERVICE_CLIENT_ID,
                client_secret_hash=bcrypt.hashpw(secret.encode(), bcrypt.gensalt(4)).decode(),
                client_secret_prefix="jns_test",
                name="test-pravara-reader",
                redirect_uris=[],
                allowed_scopes=["pravara-mes:read", TERMINAL],
                grant_types=["client_credentials"],
                audience="pravara-api",
                is_active=True,
                is_confidential=True,
            )
        )
        await session.commit()

    token, _, _ = jwt_manager.create_access_token(
        user_id=str(admin_id), email=f"{admin_id}@janua.test"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield {
            "client": client,
            "session_factory": session_factory,
            "secret": secret,
            "org_id": org_id,
            "admin_headers": {"Authorization": f"Bearer {token}"},
        }
    app.dependency_overrides.clear()
    await engine.dispose()


async def _service_token(env, **extra):
    data = {
        "grant_type": "client_credentials",
        "client_id": SERVICE_CLIENT_ID,
        "client_secret": env["secret"],
    }
    data.update(extra)
    return await env["client"].post("/api/v1/oauth/token", data=data)


async def test_an_ordinary_client_is_never_granted_the_terminal_scope(env):
    refused = await _service_token(env, scope=TERMINAL)
    assert refused.status_code == 400
    assert TERMINAL in refused.text

    default = await _service_token(env)
    assert default.status_code == 200, default.text
    assert default.json()["scope"] == "pravara-mes:read"
    claims = jwt_manager.decode_verified(
        default.json()["access_token"], issuer=jwt_manager.issuer, audience="pravara-api"
    )
    assert TERMINAL not in claims["scope"].split()
    assert TERMINAL not in claims["roles"]


async def test_a_platform_admin_cannot_register_a_client_with_it(env):
    created = await env["client"].post(
        f"/api/v1/oauth/clients?organization_id={env['org_id']}",
        json={
            "name": "test-terminal-lookalike",
            "allowed_scopes": [TERMINAL],
            "grant_types": ["client_credentials"],
            "audience": "pravara-api",
        },
        headers=env["admin_headers"],
    )
    assert created.status_code == 422


async def test_the_internal_key_cannot_register_or_grant_it_but_can_revoke_it(env):
    headers = {"X-Internal-API-Key": INTERNAL_KEY}
    registered = await env["client"].post(
        "/api/v1/oauth/clients/register",
        json={
            "name": "test-terminal-lookalike",
            "allowed_scopes": [TERMINAL],
            "grant_types": ["client_credentials"],
            "audience": "pravara-api",
        },
        headers=headers,
    )
    assert registered.status_code == 422

    granted = await env["client"].post(
        f"/api/v1/internal/oauth-clients/{SERVICE_CLIENT_ID}/scopes",
        json={"scope": TERMINAL},
        headers=headers,
    )
    assert granted.status_code == 422

    revoked = await env["client"].post(
        f"/api/v1/internal/oauth-clients/{SERVICE_CLIENT_ID}/scopes/revoke",
        json={"scope": TERMINAL},
        headers=headers,
    )
    assert revoked.status_code == 200, revoked.text
    async with env["session_factory"]() as session:
        client = (
            await session.execute(
                select(OAuthClient).where(OAuthClient.client_id == SERVICE_CLIENT_ID)
            )
        ).scalar_one()
    assert TERMINAL not in client.allowed_scopes
