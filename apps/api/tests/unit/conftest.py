"""
Unit test configuration - minimal setup without full app dependencies
"""
import os
import pytest
from unittest.mock import patch

# Set minimal test environment variables
TEST_ENV = {
    'ENVIRONMENT': 'test',
    'DATABASE_URL': 'postgresql://test:test@localhost:5432/plinto_test',
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
    settings.DATABASE_URL = 'postgresql://test:test@localhost:5432/plinto_test'
    settings.JWT_SECRET_KEY = 'test-secret-key'
    settings.REDIS_URL = 'redis://localhost:6379/1'
    return settings