"""
Unit tests for Redis module
"""

from unittest.mock import AsyncMock

import pytest

from app.core.redis import SessionStore

pytestmark = pytest.mark.asyncio


class TestSessionStore:
    """Test SessionStore class."""

    def setup_method(self):
        self.mock_redis = AsyncMock()
        self.session_store = SessionStore(self.mock_redis)

    async def test_set_session(self):
        """Test storing session data."""
        session_data = {"user_id": "user_123", "email": "test@example.com"}
        await self.session_store.set("session_id", session_data, ttl=3600)

        self.mock_redis.hset.assert_called_once_with(
            "session:session_id", mapping=session_data
        )
        self.mock_redis.expire.assert_called_once_with("session:session_id", 3600)

    async def test_get_session(self):
        """Test retrieving session data."""
        self.mock_redis.hgetall.return_value = {"user_id": "user_123"}

        result = await self.session_store.get("session_id")
        assert result == {"user_id": "user_123"}
        self.mock_redis.hgetall.assert_called_once_with("session:session_id")

    async def test_get_session_not_found(self):
        """Test retrieving non-existent session."""
        self.mock_redis.hgetall.return_value = {}

        result = await self.session_store.get("session_id")
        assert result is None

    async def test_delete_session(self):
        """Test deleting a session."""
        await self.session_store.delete("session_id")
        self.mock_redis.delete.assert_called_once_with("session:session_id")

    async def test_extend_session(self):
        """Test extending session TTL."""
        await self.session_store.extend("session_id", ttl=7200)
        self.mock_redis.expire.assert_called_once_with("session:session_id", 7200)

    async def test_set_session_default_ttl(self):
        """Test storing session with default TTL."""
        session_data = {"user_id": "user_123"}
        await self.session_store.set("sid", session_data)
        # Default is 24 hours = 86400
        self.mock_redis.expire.assert_called_once_with("session:sid", 86400)
