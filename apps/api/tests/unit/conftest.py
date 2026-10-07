"""
Unit test configuration - minimal setup without full app dependencies
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Set minimal test environment variables
TEST_ENV = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "JWT_SECRET_KEY": "test-secret-key-for-testing-only",
    "REDIS_URL": "redis://localhost:6379/1",
    "SECRET_KEY": "test-secret-key",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60",
}


@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables for all unit tests"""
    with patch.dict(os.environ, TEST_ENV):
        yield


@pytest.fixture(autouse=True)
def _isolated_magic_link_limits():
    """Every test starts with empty sign-in-link counters, held in memory.

    `app/auth/magic_link_limits.py` counts in Redis when it can reach one, and
    CI runs a real Redis: without this, counters would carry over between
    tests (5 links per address per hour) and fail unrelated ones. Tests that
    exercise the limits patch `_redis_client` themselves.
    """
    from app.auth import magic_link_limits

    magic_link_limits.reset_memory_counters()
    with patch.object(magic_link_limits, "_redis_client", AsyncMock(return_value=None)):
        yield
    magic_link_limits.reset_memory_counters()


@pytest.fixture
def mock_database():
    """Mock database session"""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def mock_redis():
    """Mock Redis connection"""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def mock_settings():
    """Mock settings object"""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.ENVIRONMENT = "test"
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.JWT_SECRET_KEY = "test-secret-key"
    settings.REDIS_URL = "redis://localhost:6379/1"
    return settings


@pytest.fixture
async def client():
    """Async HTTP client for testing"""
    from app.main import app

    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def test_client():
    """Async HTTP client for testing (alias for client)"""
    from app.main import app

    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Mock async database session"""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.query = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.scalar = AsyncMock()
    mock_session.scalars = AsyncMock()
    return mock_session


@pytest.fixture
def anyio_backend():
    """Specify the async backend for pytest-asyncio"""
    return "asyncio"


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Keep the PostgreSQL job split exact: marker 'database' <=> the test
    reads a PostgreSQL service URL. Runs before '-m' deselects anything, so it
    sees every collected test in both CI jobs."""
    from tests.postgres_service import check_marker_matches_requirement

    check_marker_matches_requirement(items)
