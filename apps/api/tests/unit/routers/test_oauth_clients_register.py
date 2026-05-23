"""
Unit tests for POST /api/v1/oauth/clients/register and internal name lookup.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.core.redis import get_redis
from app.main import app
from app.models import Base, User, UserStatus

INTERNAL_KEY = "test-internal-api-key-register"
REGISTER_URL = "/api/v1/oauth/clients/register"
LOOKUP_URL = "/api/v1/oauth/clients/internal/by-name"


@pytest_asyncio.fixture
async def oauth_register_client():
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

    admin = User(
        id=uuid.uuid4(),
        email="admin-bootstrap@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_admin=True,
        is_active=True,
    )
    async with session_factory() as session:
        session.add(admin)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


def _client_payload(name: str = "test-consumer-app") -> dict:
    return {
        "name": name,
        "redirect_uris": [
            "https://app.example.com/api/auth/callback",
            "http://localhost:3000/api/auth/callback",
        ],
        "audience": "test-consumer-api",
        "allowed_scopes": ["openid", "profile", "email"],
        "grant_types": ["authorization_code", "refresh_token"],
        "is_confidential": True,
    }


@pytest.mark.asyncio
async def test_register_creates_client_with_secret(oauth_register_client: AsyncClient):
    payload = _client_payload("register-create-once")
    response = await oauth_register_client.post(
        REGISTER_URL,
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == payload["name"]
    assert body["client_id"].startswith("jnc_")
    assert body["client_secret"] is not None
    assert body["client_secret"].startswith("jns_")


@pytest.mark.asyncio
async def test_register_is_idempotent_without_secret(oauth_register_client: AsyncClient):
    payload = _client_payload("register-idempotent")
    first = await oauth_register_client.post(
        REGISTER_URL,
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert first.status_code == 201
    created_id = first.json()["client_id"]

    second = await oauth_register_client.post(
        REGISTER_URL,
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["client_id"] == created_id
    assert body["client_secret"] is None


@pytest.mark.asyncio
async def test_register_rejects_invalid_internal_key(oauth_register_client: AsyncClient):
    response = await oauth_register_client.post(
        REGISTER_URL,
        json=_client_payload("register-bad-key"),
        headers={"X-Internal-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_requires_internal_key_header(oauth_register_client: AsyncClient):
    response = await oauth_register_client.post(
        REGISTER_URL,
        json=_client_payload("register-missing-key"),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_validates_redirect_uri_https(oauth_register_client: AsyncClient):
    payload = _client_payload("register-bad-redirect")
    payload["redirect_uris"] = ["http://evil.example.com/callback"]
    response = await oauth_register_client.post(
        REGISTER_URL,
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_allows_machine_client_without_redirects(
    oauth_register_client: AsyncClient,
):
    payload = {
        "name": "register-machine-probe",
        "redirect_uris": [],
        "grant_types": ["client_credentials"],
        "allowed_scopes": ["openid", "yantra4d:quote"],
        "is_confidential": True,
    }
    response = await oauth_register_client.post(
        REGISTER_URL,
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert response.status_code == 201
    assert response.json()["redirect_uris"] == []


@pytest.mark.asyncio
async def test_internal_lookup_by_name(oauth_register_client: AsyncClient):
    name = "register-lookup-by-name"
    created = await oauth_register_client.post(
        REGISTER_URL,
        json=_client_payload(name),
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert created.status_code == 201

    lookup = await oauth_register_client.get(
        f"{LOOKUP_URL}/{name}",
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert lookup.status_code == 200
    assert lookup.json()["client_id"] == created.json()["client_id"]
    assert lookup.json()["client_secret"] is None


@pytest.mark.asyncio
async def test_register_returns_503_without_admin_user():
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
    from app.database import get_db as database_get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[database_get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: AsyncMock()
    settings.INTERNAL_API_KEY = INTERNAL_KEY

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            REGISTER_URL,
            json=_client_payload("register-no-admin"),
            headers={"X-Internal-API-Key": INTERNAL_KEY},
        )
        assert response.status_code == 503

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()
