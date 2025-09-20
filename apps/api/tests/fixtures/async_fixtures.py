"""
Centralized async fixtures for consistent testing
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator, Generator


class AsyncDatabaseSession:
    """Mock async database session with all required methods"""
    
    def __init__(self):
        self.session = AsyncMock(spec=AsyncSession)
        self._setup_methods()
        self._setup_query_results()
    
    def _setup_methods(self):
        """Setup all database session methods"""
        self.session.add = MagicMock()
        self.session.commit = AsyncMock()
        self.session.rollback = AsyncMock()
        self.session.refresh = AsyncMock()
        self.session.flush = AsyncMock()
        self.session.close = AsyncMock()
        self.session.get = AsyncMock(return_value=None)
        self.session.merge = AsyncMock()
        self.session.delete = AsyncMock()
        self.session.execute = AsyncMock()
        self.session.scalar = AsyncMock()
        self.session.scalars = AsyncMock()
        
    def _setup_query_results(self):
        """Setup query result mocks"""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        mock_result.scalar_one = AsyncMock()
        mock_result.scalar = AsyncMock(return_value=None)
        mock_result.all = AsyncMock(return_value=[])
        mock_result.first = AsyncMock(return_value=None)
        mock_result.one_or_none = AsyncMock(return_value=None)
        mock_result.one = AsyncMock()
        self.session.execute.return_value = mock_result
        
        # For scalar operations
        mock_scalar_result = AsyncMock()
        mock_scalar_result.all = AsyncMock(return_value=[])
        mock_scalar_result.first = AsyncMock(return_value=None)
        mock_scalar_result.one_or_none = AsyncMock(return_value=None)
        self.session.scalars.return_value = mock_scalar_result


class AsyncRedisClient:
    """Mock async Redis client with all required methods"""
    
    def __init__(self):
        self.client = AsyncMock()
        self._setup_methods()
    
    def _setup_methods(self):
        """Setup all Redis methods"""
        # Basic operations
        self.client.get = AsyncMock(return_value=None)
        self.client.set = AsyncMock(return_value=True)
        self.client.setex = AsyncMock(return_value=True)
        self.client.delete = AsyncMock(return_value=1)
        self.client.exists = AsyncMock(return_value=0)
        self.client.expire = AsyncMock(return_value=True)
        self.client.ttl = AsyncMock(return_value=-2)
        
        # Hash operations
        self.client.hget = AsyncMock(return_value=None)
        self.client.hset = AsyncMock(return_value=1)
        self.client.hdel = AsyncMock(return_value=1)
        self.client.hgetall = AsyncMock(return_value={})
        
        # List operations
        self.client.lpush = AsyncMock(return_value=1)
        self.client.rpush = AsyncMock(return_value=1)
        self.client.lpop = AsyncMock(return_value=None)
        self.client.rpop = AsyncMock(return_value=None)
        self.client.llen = AsyncMock(return_value=0)
        
        # Set operations
        self.client.sadd = AsyncMock(return_value=1)
        self.client.srem = AsyncMock(return_value=1)
        self.client.sismember = AsyncMock(return_value=0)
        self.client.smembers = AsyncMock(return_value=set())
        
        # Utility
        self.client.ping = AsyncMock(return_value=True)
        self.client.close = AsyncMock()
        self.client.flushdb = AsyncMock()


@pytest.fixture
def async_db_session() -> AsyncDatabaseSession:
    """Provides a properly configured async database session mock"""
    return AsyncDatabaseSession()


@pytest.fixture
def async_redis_client() -> AsyncRedisClient:
    """Provides a properly configured async Redis client mock"""
    return AsyncRedisClient()


@pytest.fixture
async def async_http_client():
    """Provides an async HTTP client mock"""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()
    client.head = AsyncMock()
    client.options = AsyncMock()
    
    # Setup default responses
    response = AsyncMock()
    response.status_code = 200
    response.json = AsyncMock(return_value={})
    response.text = AsyncMock(return_value="")
    response.headers = {}
    
    for method in [client.get, client.post, client.put, client.patch, client.delete]:
        method.return_value = response
    
    return client


@pytest.fixture
def mock_jwt_service():
    """Provides a mock JWT service"""
    service = AsyncMock()
    service.create_access_token = MagicMock(return_value="mock_access_token")
    service.create_refresh_token = MagicMock(return_value="mock_refresh_token")
    service.create_token_pair = MagicMock(return_value={
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "token_type": "Bearer"
    })
    service.verify_token = MagicMock(return_value={"user_id": "test_user"})
    service.verify_access_token = MagicMock(return_value={"user_id": "test_user"})
    service.verify_refresh_token = MagicMock(return_value={"user_id": "test_user"})
    service.revoke_token = AsyncMock(return_value=True)
    service.is_token_revoked = AsyncMock(return_value=False)
    service.decode_token = MagicMock(return_value={"user_id": "test_user"})
    return service


@pytest.fixture
def mock_auth_service():
    """Provides a mock authentication service"""
    service = AsyncMock()
    service.create_user = AsyncMock()
    service.authenticate = AsyncMock()
    service.verify_password = MagicMock(return_value=True)
    service.hash_password = MagicMock(return_value="hashed_password")
    service.get_user_by_email = AsyncMock(return_value=None)
    service.get_user_by_id = AsyncMock(return_value=None)
    service.update_user = AsyncMock()
    service.delete_user = AsyncMock()
    service.validate_password_strength = MagicMock(return_value=True)
    return service


@pytest.fixture
async def async_event_loop():
    """Provides a properly configured event loop for async tests"""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield loop
    # Don't close the loop here as pytest-asyncio manages it