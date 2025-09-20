import pytest
pytestmark = pytest.mark.asyncio


"""
Unit tests for Redis module
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.core.redis import init_redis, get_redis, RateLimiter, SessionStore


class TestRedisInitialization:
    """Test Redis initialization functions."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_init_redis_success(self):
        """Test successful Redis initialization."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        
        with patch('app.core.redis.redis.from_url', return_value=mock_redis) as mock_from_url, \
             patch('app.core.redis.settings') as mock_settings:
            
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_settings.REDIS_DECODE_RESPONSES = True
            mock_settings.REDIS_POOL_SIZE = 10
            
            await init_redis()
            
            mock_from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )
            mock_redis.ping.assert_called_once()
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_init_redis_connection_error(self):
        """Test Redis initialization with connection error."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        with patch('app.core.redis.redis.from_url', return_value=mock_redis), \
             patch('app.core.redis.logger') as mock_logger:
            
            with pytest.raises(Exception, match="Connection failed"):
                await init_redis()
            
            mock_logger.error.assert_called_once()
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_get_redis(self):
        """Test get_redis dependency function."""
        mock_redis = AsyncMock()
        
        with patch('app.core.redis.redis_client', mock_redis):
            result = await get_redis()
            assert result == mock_redis


class TestRateLimiter:
    """Test RateLimiter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.rate_limiter = RateLimiter(self.mock_redis)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_check_rate_limit_within_limit(self):
        """Test rate limiting when within limit."""
        # Mock Redis responses
        self.mock_redis.get.return_value = None  # No existing count
        self.mock_redis.incr.return_value = 1
        self.mock_redis.expire.return_value = True
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(
            "test:key", limit=10, window=60
        )
        
        assert allowed is True
        assert remaining == 9
        
        self.mock_redis.get.assert_called_once_with("test:key")
        self.mock_redis.incr.assert_called_once_with("test:key")
        self.mock_redis.expire.assert_called_once_with("test:key", 60)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_check_rate_limit_at_limit(self):
        """Test rate limiting when at the limit."""
        self.mock_redis.get.return_value = "10"  # At limit
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(
            "test:key", limit=10, window=60
        )
        
        assert allowed is False
        assert remaining == 0
        
        # Should not increment when at limit
        self.mock_redis.incr.assert_not_called()
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_check_rate_limit_existing_count(self):
        """Test rate limiting with existing count."""
        self.mock_redis.get.return_value = "5"  # Existing count
        self.mock_redis.incr.return_value = 6
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(
            "test:key", limit=10, window=60
        )
        
        assert allowed is True
        assert remaining == 4
        
        self.mock_redis.incr.assert_called_once_with("test:key")
        # Should not set expiry for existing key
        self.mock_redis.expire.assert_not_called()
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_reset_rate_limit(self):
        """Test resetting rate limit."""
        self.mock_redis.delete.return_value = 1
        
        result = await self.rate_limiter.reset_rate_limit("test:key")
        
        assert result is True
        self.mock_redis.delete.assert_called_once_with("test:key")
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_get_remaining_attempts(self):
        """Test getting remaining attempts."""
        self.mock_redis.get.return_value = "3"
        
        remaining = await self.rate_limiter.get_remaining_attempts("test:key", limit=10)
        
        assert remaining == 7
        self.mock_redis.get.assert_called_once_with("test:key")
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_get_remaining_attempts_no_key(self):
        """Test getting remaining attempts for non-existent key."""
        self.mock_redis.get.return_value = None
        
        remaining = await self.rate_limiter.get_remaining_attempts("test:key", limit=10)
        
        assert remaining == 10


class TestSessionStore:
    """Test SessionStore class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.session_store = SessionStore(self.mock_redis)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_store_session(self):
        """Test storing a session."""
        session_data = {
            "user_id": "user_123",
            "email": "test@example.com",
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.mock_redis.setex.return_value = True
        
        result = await self.session_store.store_session(
            "session_id", session_data, ttl=3600
        )
        
        assert result is True
        
        # Verify Redis call
        args, kwargs = self.mock_redis.setex.call_args
        assert args[0] == "session:session_id"
        assert args[2] == 3600
        # Verify JSON serialization
        import json
        stored_data = json.loads(args[1])
        assert stored_data == session_data
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test retrieving a session."""
        session_data = {
            "user_id": "user_123",
            "email": "test@example.com"
        }
        
        import json
        self.mock_redis.get.return_value = json.dumps(session_data)
        
        result = await self.session_store.get_session("session_id")
        
        assert result == session_data
        self.mock_redis.get.assert_called_once_with("session:session_id")
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test retrieving non-existent session."""
        self.mock_redis.get.return_value = None
        
        result = await self.session_store.get_session("session_id")
        
        assert result is None
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting a session."""
        self.mock_redis.delete.return_value = 1
        
        result = await self.session_store.delete_session("session_id")
        
        assert result is True
        self.mock_redis.delete.assert_called_once_with("session:session_id")
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_delete_session_not_found(self):
        """Test deleting non-existent session."""
        self.mock_redis.delete.return_value = 0
        
        result = await self.session_store.delete_session("session_id")
        
        assert result is False
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_extend_session(self):
        """Test extending session TTL."""
        self.mock_redis.expire.return_value = True
        
        result = await self.session_store.extend_session("session_id", ttl=7200)
        
        assert result is True
        self.mock_redis.expire.assert_called_once_with("session:session_id", 7200)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_get_all_user_sessions(self):
        """Test getting all sessions for a user."""
        keys = ["session:session1", "session:session2"]
        session_data = {"user_id": "user_123"}
        
        self.mock_redis.keys.return_value = keys
        self.mock_redis.mget.return_value = [
            json.dumps(session_data),
            json.dumps(session_data)
        ]
        
        import json
        result = await self.session_store.get_all_user_sessions("user_123")
        
        assert len(result) == 2
        assert all(session["user_id"] == "user_123" for session in result)
        
        self.mock_redis.keys.assert_called_once_with("session:*")
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        # Mock expired session keys
        keys = ["session:expired1", "session:expired2"]
        self.mock_redis.keys.return_value = keys
        self.mock_redis.delete.return_value = 2
        
        result = await self.session_store.cleanup_expired_sessions()
        
        assert result == 2
        self.mock_redis.keys.assert_called_once_with("session:*")
        self.mock_redis.delete.assert_called_once_with(*keys)