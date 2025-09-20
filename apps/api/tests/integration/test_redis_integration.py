
pytestmark = pytest.mark.asyncio

"""
Integration tests for Redis operations
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
import json
from datetime import datetime

from app.core.redis import init_redis, get_redis, RateLimiter, SessionStore


class TestRedisIntegration:
    """Test Redis integration scenarios."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_redis_connection_lifecycle(self):
        """Test complete Redis connection lifecycle."""
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
    async def test_redis_dependency_injection(self, mock_redis):
        """Test Redis dependency injection."""
        with patch('app.core.redis.redis_client', mock_redis):
            redis = await get_redis()
            assert redis == mock_redis
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self):
        """Test Redis connection error handling."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis connection failed")
        
        with patch('app.core.redis.redis.from_url', return_value=mock_redis), \
             patch('app.core.redis.logger') as mock_logger:
            
            with pytest.raises(Exception, match="Redis connection failed"):
                await init_redis()
            
            mock_logger.error.assert_called_once()


class TestRateLimiterIntegration:
    """Test RateLimiter integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.rate_limiter = RateLimiter(self.mock_redis)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_rate_limiter_full_workflow(self):
        """Test complete rate limiter workflow."""
        # Scenario: New user making requests
        key = "rate_limit:user123:signup"
        limit = 5
        window = 300  # 5 minutes
        
        # First request - should succeed
        self.mock_redis.get.return_value = None
        self.mock_redis.incr.return_value = 1
        self.mock_redis.expire.return_value = True
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(key, limit, window)
        
        assert allowed is True
        assert remaining == 4
        self.mock_redis.get.assert_called_with(key)
        self.mock_redis.incr.assert_called_with(key)
        self.mock_redis.expire.assert_called_with(key, window)
        
        # Subsequent requests - still within limit
        for i in range(2, 5):  # Requests 2-4
            self.mock_redis.get.return_value = str(i - 1)
            self.mock_redis.incr.return_value = i
            
            allowed, remaining = await self.rate_limiter.check_rate_limit(key, limit, window)
            
            assert allowed is True
            assert remaining == limit - i
        
        # Final allowed request
        self.mock_redis.get.return_value = "4"
        self.mock_redis.incr.return_value = 5
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(key, limit, window)
        
        assert allowed is True
        assert remaining == 0
        
        # Rate limit exceeded
        self.mock_redis.get.return_value = "5"
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(key, limit, window)
        
        assert allowed is False
        assert remaining == 0
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_rate_limiter_reset_workflow(self):
        """Test rate limiter reset functionality."""
        key = "rate_limit:user123:signin"
        
        # User hits rate limit
        self.mock_redis.get.return_value = "10"
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(key, 10, 300)
        assert allowed is False
        
        # Admin resets rate limit
        self.mock_redis.delete.return_value = 1
        
        result = await self.rate_limiter.reset_rate_limit(key)
        assert result is True
        
        # User can now make requests again
        self.mock_redis.get.return_value = None
        self.mock_redis.incr.return_value = 1
        self.mock_redis.expire.return_value = True
        
        allowed, remaining = await self.rate_limiter.check_rate_limit(key, 10, 300)
        assert allowed is True
        assert remaining == 9
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_rate_limiter_multiple_users(self):
        """Test rate limiter with multiple users."""
        user1_key = "rate_limit:user1:api"
        user2_key = "rate_limit:user2:api"
        limit = 3
        window = 60
        
        # User 1 makes requests
        self.mock_redis.get.side_effect = lambda key: "2" if key == user1_key else None
        self.mock_redis.incr.side_effect = lambda key: 3 if key == user1_key else 1
        self.mock_redis.expire.return_value = True
        
        # User 1 hits limit
        allowed1, remaining1 = await self.rate_limiter.check_rate_limit(user1_key, limit, window)
        assert allowed1 is True
        assert remaining1 == 0
        
        # User 2 should still be able to make requests
        allowed2, remaining2 = await self.rate_limiter.check_rate_limit(user2_key, limit, window)
        assert allowed2 is True
        assert remaining2 == 2


class TestSessionStoreIntegration:
    """Test SessionStore integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.session_store = SessionStore(self.mock_redis)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        """Test complete session lifecycle."""
        session_id = "session_123"
        session_data = {
            "user_id": "user_456",
            "email": "test@example.com",
            "created_at": datetime.utcnow().isoformat(),
            "permissions": ["read", "write"]
        }
        ttl = 3600
        
        # Store session
        self.mock_redis.setex.return_value = True
        
        result = await self.session_store.store_session(session_id, session_data, ttl)
        assert result is True
        
        # Verify Redis call
        args, kwargs = self.mock_redis.setex.call_args
        assert args[0] == f"session:{session_id}"
        assert args[2] == ttl
        stored_data = json.loads(args[1])
        assert stored_data == session_data
        
        # Retrieve session
        self.mock_redis.get.return_value = json.dumps(session_data)
        
        retrieved_data = await self.session_store.get_session(session_id)
        assert retrieved_data == session_data
        
        # Extend session
        self.mock_redis.expire.return_value = True
        
        result = await self.session_store.extend_session(session_id, 7200)
        assert result is True
        self.mock_redis.expire.assert_called_with(f"session:{session_id}", 7200)
        
        # Delete session
        self.mock_redis.delete.return_value = 1
        
        result = await self.session_store.delete_session(session_id)
        assert result is True
        self.mock_redis.delete.assert_called_with(f"session:{session_id}")
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_session_expiration_handling(self):
        """Test session expiration scenarios."""
        session_id = "expired_session"
        
        # Try to get expired session
        self.mock_redis.get.return_value = None
        
        result = await self.session_store.get_session(session_id)
        assert result is None
        
        # Try to extend non-existent session
        self.mock_redis.expire.return_value = False
        
        result = await self.session_store.extend_session(session_id, 3600)
        assert result is False
        
        # Try to delete non-existent session
        self.mock_redis.delete.return_value = 0
        
        result = await self.session_store.delete_session(session_id)
        assert result is False
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_multi_user_session_management(self):
        """Test session management for multiple users."""
        user1_sessions = ["session_1a", "session_1b"]
        user2_sessions = ["session_2a"]
        
        session_data_template = {
            "email": "user{}@example.com",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Mock keys for all sessions
        all_session_keys = [
            f"session:{sid}" for sid in user1_sessions + user2_sessions
        ]
        
        self.mock_redis.keys.return_value = all_session_keys
        
        # Mock session data for user 1
        user1_data = [
            json.dumps({**session_data_template, "user_id": "user1", "email": "user1@example.com"}),
            json.dumps({**session_data_template, "user_id": "user1", "email": "user1@example.com"})
        ]
        
        # Mock session data for user 2
        user2_data = [
            json.dumps({**session_data_template, "user_id": "user2", "email": "user2@example.com"})
        ]
        
        self.mock_redis.mget.return_value = user1_data + user2_data
        
        # Get all sessions for user 1
        user1_sessions_data = await self.session_store.get_all_user_sessions("user1")
        
        assert len(user1_sessions_data) == 2
        for session in user1_sessions_data:
            assert session["user_id"] == "user1"
            assert session["email"] == "user1@example.com"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test session cleanup functionality."""
        expired_keys = ["session:expired1", "session:expired2", "session:expired3"]
        
        self.mock_redis.keys.return_value = expired_keys
        self.mock_redis.delete.return_value = len(expired_keys)
        
        cleaned_count = await self.session_store.cleanup_expired_sessions()
        
        assert cleaned_count == 3
        self.mock_redis.keys.assert_called_with("session:*")
        self.mock_redis.delete.assert_called_with(*expired_keys)


class TestRedisPerformanceIntegration:
    """Test Redis performance scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.rate_limiter = RateLimiter(self.mock_redis)
        self.session_store = SessionStore(self.mock_redis)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_checks(self):
        """Test concurrent rate limit checking."""
        import asyncio
        
        keys = [f"rate_limit:user{i}:api" for i in range(5)]
        
        # Mock Redis to return different counts for different keys
        def mock_get(key):
            user_num = int(key.split(':')[1][4:])  # Extract user number
            return str(user_num)  # Return user number as count
        
        def mock_incr(key):
            user_num = int(key.split(':')[1][4:])
            return user_num + 1
        
        self.mock_redis.get.side_effect = mock_get
        self.mock_redis.incr.side_effect = mock_incr
        self.mock_redis.expire.return_value = True
        
        # Create concurrent rate limit checks
        tasks = [
            self.rate_limiter.check_rate_limit(key, 10, 60)
            for key in keys
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed but with different remaining counts
        for i, (allowed, remaining) in enumerate(results):
            assert allowed is True
            assert remaining == 10 - (i + 1)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self):
        """Test concurrent session operations."""
        import asyncio
        
        session_ids = [f"session_{i}" for i in range(5)]
        session_data_list = [
            {"user_id": f"user_{i}", "data": f"data_{i}"}
            for i in range(5)
        ]
        
        # Mock successful operations
        self.mock_redis.setex.return_value = True
        self.mock_redis.get.side_effect = lambda key: json.dumps(
            {"user_id": key.split(':')[1], "data": f"data_{key.split(':')[1]}"}
        )
        
        # Create concurrent session operations
        store_tasks = [
            self.session_store.store_session(sid, data, 3600)
            for sid, data in zip(session_ids, session_data_list)
        ]
        
        get_tasks = [
            self.session_store.get_session(sid)
            for sid in session_ids
        ]
        
        # Execute operations concurrently
        store_results = await asyncio.gather(*store_tasks)
        get_results = await asyncio.gather(*get_tasks)
        
        # All store operations should succeed
        assert all(store_results)
        
        # All get operations should return data
        for i, result in enumerate(get_results):
            assert result is not None
            assert result["user_id"] == f"session_{i}"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_high_frequency_operations(self):
        """Test high-frequency Redis operations."""
        import time
        
        # Simulate high-frequency rate limit checks
        key = "high_freq_test"
        
        self.mock_redis.get.return_value = "1"
        self.mock_redis.incr.return_value = 2
        
        start_time = time.time()
        
        # Perform many operations quickly
        for _ in range(100):
            await self.rate_limiter.check_rate_limit(key, 1000, 60)
        
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 5.0  # Within 5 seconds
        
        # Verify Redis was called the expected number of times
        assert self.mock_redis.get.call_count == 100


class TestRedisErrorRecovery:
    """Test Redis error recovery scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.rate_limiter = RateLimiter(self.mock_redis)
        self.session_store = SessionStore(self.mock_redis)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_redis_operation_failure_recovery(self):
        """Test recovery from Redis operation failures."""
        # Test rate limiter with Redis error
        self.mock_redis.get.side_effect = Exception("Redis error")
        
        # Should handle error gracefully
        with pytest.raises(Exception, match="Redis error"):
            await self.rate_limiter.check_rate_limit("test_key", 10, 60)
        
        # Test session store with Redis error
        self.mock_redis.setex.side_effect = Exception("Redis error")
        
        with pytest.raises(Exception, match="Redis error"):
            await self.session_store.store_session("test_session", {"data": "test"}, 3600)
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_partial_operation_failure(self):
        """Test handling of partial operation failures."""
        # Scenario: get succeeds but incr fails
        self.mock_redis.get.return_value = "5"
        self.mock_redis.incr.side_effect = Exception("Incr failed")
        
        with pytest.raises(Exception, match="Incr failed"):
            await self.rate_limiter.check_rate_limit("test_key", 10, 60)
        
        # Scenario: setex succeeds but get fails
        self.mock_redis.setex.return_value = True
        self.mock_redis.get.side_effect = Exception("Get failed")
        
        # Store should succeed
        result = await self.session_store.store_session("test", {"data": "test"}, 3600)
        assert result is True
        
        # But get should fail
        with pytest.raises(Exception, match="Get failed"):
            await self.session_store.get_session("test")