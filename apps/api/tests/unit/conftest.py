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
    'ENVIRONMENT': 'test',
    'DATABASE_URL': 'sqlite+aiosqlite:///:memory:',
    'JWT_SECRET_KEY': 'test-secret-key-for-testing-only',
    'REDIS_URL': 'redis://localhost:6379/1',
    'SECRET_KEY': 'test-secret-key',
    'JWT_ALGORITHM': 'HS256',
    'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': '60'
}

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables for all unit tests"""
    with patch.dict(os.environ, TEST_ENV):
        yield

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
    settings.ENVIRONMENT = 'test'
    settings.DATABASE_URL = 'sqlite+aiosqlite:///:memory:'
    settings.JWT_SECRET_KEY = 'test-secret-key'
    settings.REDIS_URL = 'redis://localhost:6379/1'
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
    return 'asyncio'