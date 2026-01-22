"""
Main test configuration and shared fixtures for Janua API tests
"""

import asyncio
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

# Set test environment variables before any imports
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-only"

from app.main import app
from app.config import settings
from app.core.database import Base, get_db
from app.core.redis import get_redis


@pytest_asyncio.fixture(scope="session")
async def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(test_db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = False
    mock_redis.expire.return_value = True
    mock_redis.incr.return_value = 1
    mock_redis.decr.return_value = 1
    return mock_redis


@pytest_asyncio.fixture
async def test_client(
    test_db_session: AsyncSession, mock_redis
) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden dependencies."""

    async def override_get_db():
        yield test_db_session

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {"email": "test@example.com", "password": "TestPassword123!", "name": "Test User"}


@pytest.fixture
def sample_signin_data():
    """Sample signin data for testing."""
    return {"email": "test@example.com", "password": "admin123"}  # Using mock password


@pytest.fixture
def auth_headers():
    """Sample authorization headers for testing."""
    return {"Authorization": "Bearer mock_access_token_123"}


@pytest.fixture
def mock_auth_service(monkeypatch):
    """Mock the AuthService for testing."""
    mock_service = AsyncMock()

    # Mock user creation
    mock_user = MagicMock()
    mock_user.id = "user_123"
    mock_user.email = "test@example.com"
    mock_user.name = "Test User"
    mock_user.email_verified = False
    mock_user.created_at = "2024-01-01T00:00:00Z"
    mock_user.updated_at = "2024-01-01T00:00:00Z"

    mock_service.create_user.return_value = mock_user
    mock_service.authenticate_user.return_value = mock_user
    mock_service.create_session.return_value = ("access_token", "refresh_token", "session")

    # Patch the import
    monkeypatch.setattr("app.auth.router.AuthService", mock_service)
    return mock_service


@pytest.fixture
def settings_override():
    """Override settings for testing."""
    original_values = {}

    def _override(**kwargs):
        for key, value in kwargs.items():
            if hasattr(settings, key):
                original_values[key] = getattr(settings, key)
                setattr(settings, key, value)

    yield _override

    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)
