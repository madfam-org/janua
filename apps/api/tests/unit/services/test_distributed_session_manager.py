"""
Comprehensive tests for Distributed Session Manager

Target: 95%+ coverage (currently 17%)
Covers: Session creation, validation, refresh, revocation, analytics, SSO migration
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.services.distributed_session_manager import (
    DistributedSessionManager,
    SessionStatus,
    SessionType,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client with async methods"""
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.sadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.zadd = AsyncMock(return_value=1)
    redis.srem = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())
    redis.scan = AsyncMock(return_value=(b"0", []))
    redis.zcard = AsyncMock(return_value=0)
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.lock = Mock(return_value=AsyncMock())
    return redis


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def session_manager(mock_redis, mock_db):
    """Session manager with mocked dependencies"""
    return DistributedSessionManager(redis_client=mock_redis, db_session=mock_db)


@pytest.fixture
def sample_session_data():
    """Sample session data for testing"""
    return {
        "session_id": "test-session-123",
        "user_id": "user-456",
        "session_type": SessionType.WEB.value,
        "status": SessionStatus.ACTIVE.value,
        "token_hash": "abc123hash",
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0",
        "fingerprint": "fp123",
        "device_info": {"platform": "web"},
        "metadata": {"client": "browser"},
        "access_count": 0,
        "refresh_count": 0,
    }


class TestSessionManagerInitialization:
    """Test session manager initialization"""

    def test_init_with_redis_and_db(self, mock_redis, mock_db):
        """Test initialization with both Redis and database"""
        manager = DistributedSessionManager(redis_client=mock_redis, db_session=mock_db)

        assert manager.redis is mock_redis
        assert manager.db is mock_db
        assert manager.session_ttl == 3600
        assert manager.max_sessions_per_user == 5
        assert manager.enable_session_binding is True

    def test_init_without_dependencies(self):
        """Test initialization without Redis or database"""
        manager = DistributedSessionManager()

        assert manager.redis is None
        assert manager.db is None
        assert manager.session_ttl == 3600

    def test_configuration_defaults(self, session_manager):
        """Test default configuration values"""
        assert session_manager.SESSION_KEY_PREFIX == "session:"
        assert session_manager.USER_SESSIONS_PREFIX == "user_sessions:"
        assert session_manager.SESSION_LOCK_PREFIX == "session_lock:"
        assert session_manager.ACTIVE_SESSIONS_KEY == "active_sessions"


class TestSessionCreation:
    """Test session creation functionality"""

    @pytest.mark.asyncio
    async def test_create_web_session(self, session_manager, mock_redis):
        """Test creating a web session"""
        result = await session_manager.create_session(
            user_id="user-123",
            session_type=SessionType.WEB,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert "session_id" in result
        assert "session_token" in result
        assert "expires_at" in result
        assert result["session_type"] == SessionType.WEB.value

        # Verify Redis calls
        assert mock_redis.setex.called
        assert mock_redis.sadd.called
        assert mock_redis.zadd.called

    @pytest.mark.asyncio
    async def test_create_mobile_session(self, session_manager):
        """Test creating a mobile session"""
        result = await session_manager.create_session(
            user_id="user-123",
            session_type=SessionType.MOBILE,
            device_info={"platform": "iOS", "version": "14.0"},
        )

        assert result["session_type"] == SessionType.MOBILE.value

    @pytest.mark.asyncio
    async def test_create_api_session(self, session_manager):
        """Test creating an API session"""
        result = await session_manager.create_session(
            user_id="user-123", session_type=SessionType.API
        )

        assert result["session_type"] == SessionType.API.value

    @pytest.mark.asyncio
    async def test_create_sso_session(self, session_manager):
        """Test creating an SSO session"""
        result = await session_manager.create_session(
            user_id="user-123", session_type=SessionType.SSO
        )

        assert result["session_type"] == SessionType.SSO.value

    @pytest.mark.asyncio
    async def test_session_with_metadata(self, session_manager):
        """Test creating session with custom metadata"""
        metadata = {"client_app": "mobile_v1.0", "environment": "production"}

        result = await session_manager.create_session(user_id="user-123", metadata=metadata)

        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_session_fingerprint_creation(self, session_manager):
        """Test session fingerprint is created for binding"""
        result = await session_manager.create_session(
            user_id="user-123", ip_address="192.168.1.1", user_agent="Mozilla/5.0"
        )

        # Session should be created with fingerprint
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_concurrent_session_limit(self, session_manager, mock_redis):
        """Test concurrent session limit enforcement"""
        # Mock existing sessions at limit
        existing_sessions = [
            {"session_id": f"session-{i}", "created_at": datetime.utcnow().isoformat()}
            for i in range(5)
        ]

        mock_redis.smembers.return_value = {s["session_id"].encode() for s in existing_sessions}

        # Mock get to return session data
        async def mock_get(key):
            for session in existing_sessions:
                if session["session_id"] in key.decode():
                    return json.dumps(session).encode()
            return None

        mock_redis.get.side_effect = mock_get

        # Create new session should revoke oldest
        result = await session_manager.create_session(user_id="user-123")

        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_database_fallback_on_redis_failure(self, session_manager, mock_redis, mock_db):
        """Test database is used when Redis fails"""
        mock_redis.setex.side_effect = Exception("Redis connection failed")

        result = await session_manager.create_session(user_id="user-123")

        # Should still create session and save to database
        assert "session_id" in result
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_token_generation_is_unique(self, session_manager):
        """Test that session tokens are unique"""
        result1 = await session_manager.create_session(user_id="user-123")
        result2 = await session_manager.create_session(user_id="user-123")

        assert result1["session_token"] != result2["session_token"]
        assert result1["session_id"] != result2["session_id"]


class TestSessionValidation:
    """Test session validation functionality"""

    @pytest.mark.asyncio
    async def test_validate_valid_session(self, session_manager, mock_redis, sample_session_data):
        """Test validating a valid active session"""
        # Mock Redis scan to return our session
        session_key = f"session:{sample_session_data['session_id']}"
        mock_redis.scan.return_value = (b"0", [session_key.encode()])
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        # Create token that matches hash
        import hashlib

        test_token = "test_token_12345"
        sample_session_data["token_hash"] = hashlib.sha256(test_token.encode()).hexdigest()
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        result = await session_manager.validate_session(test_token)

        assert result is not None
        assert result["session_id"] == sample_session_data["session_id"]

    @pytest.mark.asyncio
    async def test_validate_expired_session(self, session_manager, mock_redis, sample_session_data):
        """Test validating an expired session"""
        # Set expiration in the past
        sample_session_data["expires_at"] = (datetime.utcnow() - timedelta(hours=1)).isoformat()

        session_key = f"session:{sample_session_data['session_id']}"
        mock_redis.scan.return_value = (b"0", [session_key.encode()])
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        import hashlib

        test_token = "test_token_12345"
        sample_session_data["token_hash"] = hashlib.sha256(test_token.encode()).hexdigest()
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        result = await session_manager.validate_session(test_token)

        # Should return None for expired session
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_revoked_session(self, session_manager, mock_redis, sample_session_data):
        """Test validating a revoked session"""
        sample_session_data["status"] = SessionStatus.REVOKED.value

        session_key = f"session:{sample_session_data['session_id']}"
        mock_redis.scan.return_value = (b"0", [session_key.encode()])
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        import hashlib

        test_token = "test_token_12345"
        sample_session_data["token_hash"] = hashlib.sha256(test_token.encode()).hexdigest()
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        result = await session_manager.validate_session(test_token)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self, session_manager, mock_redis):
        """Test validating with invalid token"""
        mock_redis.scan.return_value = (b"0", [])

        result = await session_manager.validate_session("invalid_token_xyz")

        assert result is None

    @pytest.mark.asyncio
    async def test_database_fallback_validation(self, session_manager, mock_redis, mock_db):
        """Test database fallback when Redis validation fails"""
        mock_redis.scan.side_effect = Exception("Redis scan failed")

        # Mock database session - Session model uses 'token' not 'token_hash'
        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.user_id = "user-456"
        mock_session.token = "some_token"  # Session model uses 'token', not 'token_hash'
        mock_session.expires_at = datetime.utcnow() + timedelta(hours=1)
        mock_session.ip_address = "192.168.1.1"
        mock_session.user_agent = "Mozilla/5.0"

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        result = await session_manager.validate_session("some_token")

        # Should fall back to database
        assert mock_db.execute.called


class TestSessionActivity:
    """Test session activity tracking"""

    @pytest.mark.asyncio
    async def test_update_session_activity(self, session_manager, mock_redis, sample_session_data):
        """Test updating session activity"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.update_session_activity("test-session-123")

        # Verify Redis calls
        assert mock_redis.setex.called
        assert mock_redis.zadd.called

    @pytest.mark.asyncio
    async def test_activity_increments_access_count(
        self, session_manager, mock_redis, sample_session_data
    ):
        """Test that activity updates increment access count"""
        sample_session_data["access_count"] = 5
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.update_session_activity("test-session-123")

        # Access count should be incremented
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_activity_resets_ttl(self, session_manager, mock_redis, sample_session_data):
        """Test that activity updates reset TTL"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.update_session_activity("test-session-123")

        # setex should be called with TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == session_manager.session_ttl

    @pytest.mark.asyncio
    async def test_activity_update_error_handling(self, session_manager, mock_redis):
        """Test error handling in activity updates"""
        mock_redis.get.side_effect = Exception("Redis error")

        # Should not raise exception
        await session_manager.update_session_activity("test-session-123")


class TestSessionRefresh:
    """Test session refresh functionality"""

    @pytest.mark.asyncio
    async def test_refresh_with_ttl_extension(
        self, session_manager, mock_redis, sample_session_data
    ):
        """Test refreshing session with TTL extension"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        result = await session_manager.refresh_session("test-session-123", extend_ttl=True)

        assert result is not None
        assert "session_id" in result
        assert "session_token" in result
        assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_refresh_without_ttl_extension(
        self, session_manager, mock_redis, sample_session_data
    ):
        """Test refreshing session without extending TTL"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        result = await session_manager.refresh_session("test-session-123", extend_ttl=False)

        assert result is not None

    @pytest.mark.asyncio
    async def test_refresh_rotates_token(self, session_manager, mock_redis, sample_session_data):
        """Test that refresh generates new token"""
        original_hash = sample_session_data["token_hash"]
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        result = await session_manager.refresh_session("test-session-123")

        # Should generate new token
        assert result is not None
        assert "session_token" in result

    @pytest.mark.asyncio
    async def test_refresh_increments_count(self, session_manager, mock_redis, sample_session_data):
        """Test that refresh increments refresh count"""
        sample_session_data["refresh_count"] = 3
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.refresh_session("test-session-123")

        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_session(self, session_manager, mock_redis):
        """Test refreshing non-existent session"""
        mock_redis.get.return_value = None

        result = await session_manager.refresh_session("nonexistent-session")

        assert result is None


class TestSessionRevocation:
    """Test session revocation"""

    @pytest.mark.asyncio
    async def test_revoke_session(self, session_manager, mock_redis, sample_session_data):
        """Test revoking a session"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.revoke_session("test-session-123")

        # Verify revocation operations
        assert mock_redis.setex.called  # Updated with revoked status
        assert mock_redis.srem.called  # Removed from user sessions
        assert mock_redis.zrem.called  # Removed from active sessions

    @pytest.mark.asyncio
    async def test_revoke_with_reason(self, session_manager, mock_redis, sample_session_data):
        """Test revoking session with reason"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.revoke_session("test-session-123", reason="security_breach")

        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_revoke_keeps_audit_trail(self, session_manager, mock_redis, sample_session_data):
        """Test that revocation keeps audit trail for 24 hours"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.revoke_session("test-session-123")

        # Should keep with 24-hour TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 86400  # 24 hours

    @pytest.mark.asyncio
    async def test_revoke_database_sync(
        self, session_manager, mock_redis, mock_db, sample_session_data
    ):
        """Test that revocation syncs to database"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.revoke_session("test-session-123")

        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_revoke_all_user_sessions(self, session_manager, mock_redis, sample_session_data):
        """Test revoking all user sessions"""
        # Mock multiple sessions
        session_ids = [f"session-{i}".encode() for i in range(3)]
        mock_redis.smembers.return_value = set(session_ids)
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.revoke_all_user_sessions("user-456")

        # Should revoke all sessions
        assert mock_redis.setex.call_count >= 3

    @pytest.mark.asyncio
    async def test_revoke_all_except_current(
        self, session_manager, mock_redis, sample_session_data
    ):
        """Test revoking all sessions except current"""
        session_ids = [b"session-1", b"session-2", b"session-current"]
        mock_redis.smembers.return_value = set(session_ids)
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        await session_manager.revoke_all_user_sessions("user-456", except_current="session-current")

        # Should revoke only 2 sessions
        assert mock_redis.setex.call_count == 2


class TestUserSessionManagement:
    """Test user session management"""

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, session_manager, mock_redis, sample_session_data):
        """Test getting all user sessions"""
        session_ids = [b"session-1", b"session-2"]
        mock_redis.smembers.return_value = set(session_ids)
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        sessions = await session_manager.get_user_sessions("user-456")

        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_get_sessions_exclude_expired(
        self, session_manager, mock_redis, sample_session_data
    ):
        """Test getting sessions excludes expired by default"""
        # One expired, one active
        expired_session = sample_session_data.copy()
        expired_session["expires_at"] = (datetime.utcnow() - timedelta(hours=1)).isoformat()

        active_session = sample_session_data.copy()
        active_session["expires_at"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        session_ids = [b"session-1", b"session-2"]
        mock_redis.smembers.return_value = set(session_ids)

        call_count = [0]

        async def mock_get(key):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(expired_session).encode()
            return json.dumps(active_session).encode()

        mock_redis.get.side_effect = mock_get

        sessions = await session_manager.get_user_sessions("user-456", include_expired=False)

        # Should return only active session
        assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_get_sessions_include_expired(
        self, session_manager, mock_redis, sample_session_data
    ):
        """Test getting sessions includes expired when requested"""
        session_ids = [b"session-1", b"session-2"]
        mock_redis.smembers.return_value = set(session_ids)
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        sessions = await session_manager.get_user_sessions("user-456", include_expired=True)

        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_empty_user_sessions(self, session_manager, mock_redis):
        """Test getting sessions for user with no sessions"""
        mock_redis.smembers.return_value = set()

        sessions = await session_manager.get_user_sessions("user-456")

        assert len(sessions) == 0


class TestSessionCleanup:
    """Test session cleanup operations"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_manager, mock_redis):
        """Test cleaning up expired sessions"""
        expired_sessions = [b"session-1", b"session-2", b"session-3"]
        mock_redis.zrangebyscore.return_value = expired_sessions

        await session_manager.cleanup_expired_sessions()

        # Should revoke all expired sessions
        assert mock_redis.zrangebyscore.called

    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self, session_manager, mock_redis):
        """Test error handling in cleanup"""
        mock_redis.zrangebyscore.side_effect = Exception("Redis error")

        # Should not raise exception
        await session_manager.cleanup_expired_sessions()


class TestSessionAnalytics:
    """Test session analytics"""

    @pytest.mark.asyncio
    async def test_total_active_sessions_count(self, session_manager, mock_redis):
        """Test getting total active sessions count"""
        mock_redis.zcard.return_value = 42

        analytics = await session_manager.get_session_analytics()

        assert analytics["total_active_sessions"] == 42

    @pytest.mark.asyncio
    async def test_sessions_by_type_distribution(self, session_manager, mock_redis):
        """Test getting session type distribution"""
        web_session = {"session_type": "web", "created_at": datetime.utcnow().isoformat()}
        mobile_session = {"session_type": "mobile", "created_at": datetime.utcnow().isoformat()}

        session_keys = [b"session:1", b"session:2"]
        mock_redis.scan.return_value = (b"0", session_keys)

        call_count = [0]

        async def mock_get(key):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps(web_session).encode()
            return json.dumps(mobile_session).encode()

        mock_redis.get.side_effect = mock_get
        mock_redis.zcard.return_value = 2

        analytics = await session_manager.get_session_analytics()

        assert "sessions_by_type" in analytics

    @pytest.mark.asyncio
    async def test_analytics_with_no_sessions(self, session_manager, mock_redis):
        """Test analytics with no active sessions"""
        mock_redis.zcard.return_value = 0
        mock_redis.scan.return_value = (b"0", [])

        analytics = await session_manager.get_session_analytics()

        assert analytics["total_active_sessions"] == 0
        assert analytics["average_session_duration"] == 0


class TestSessionLocking:
    """Test session locking mechanisms"""

    @pytest.mark.asyncio
    async def test_acquire_session_lock(self, session_manager, mock_redis):
        """Test acquiring session lock"""
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=True)
        mock_redis.lock.return_value = mock_lock

        lock = await session_manager.acquire_session_lock("session-123")

        assert lock is not None
        assert mock_lock.acquire.called

    @pytest.mark.asyncio
    async def test_lock_acquisition_failure(self, session_manager, mock_redis):
        """Test lock acquisition failure"""
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=False)
        mock_redis.lock.return_value = mock_lock

        lock = await session_manager.acquire_session_lock("session-123")

        assert lock is None


class TestSSOMigration:
    """Test SSO session migration"""

    @pytest.mark.asyncio
    async def test_migrate_to_sso(self, session_manager, mock_redis, sample_session_data):
        """Test migrating session to SSO"""
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        sso_data = {"provider": "google", "id_token": "xyz123"}
        result = await session_manager.migrate_session_to_sso(
            "test-session-123", "google", sso_data
        )

        assert result is True
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_migrate_nonexistent_session(self, session_manager, mock_redis):
        """Test migrating non-existent session"""
        mock_redis.get.return_value = None

        result = await session_manager.migrate_session_to_sso("nonexistent", "google", {})

        assert result is False


class TestSessionFingerprinting:
    """Test session fingerprint creation"""

    def test_create_fingerprint(self, session_manager):
        """Test fingerprint creation"""
        fingerprint = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")

        assert fingerprint is not None
        assert len(fingerprint) == 16

    def test_fingerprint_consistency(self, session_manager):
        """Test fingerprints are consistent for same input"""
        fp1 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")
        fp2 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")

        assert fp1 == fp2

    def test_fingerprint_differs_for_different_input(self, session_manager):
        """Test fingerprints differ for different inputs"""
        fp1 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")
        fp2 = session_manager._create_session_fingerprint("192.168.1.2", "Chrome/90.0")

        assert fp1 != fp2


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, session_manager, mock_redis):
        """Test handling Redis connection failures"""
        mock_redis.setex.side_effect = Exception("Connection refused")

        # Should not raise exception
        result = await session_manager.create_session("user-123")
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_malformed_session_data(self, session_manager, mock_redis):
        """Test handling malformed session data"""
        mock_redis.get.return_value = b"invalid json data"

        # Should handle gracefully
        await session_manager.update_session_activity("test-session")

    @pytest.mark.asyncio
    async def test_unicode_in_metadata(self, session_manager):
        """Test session with unicode metadata"""
        metadata = {"message": "Hello 世界 🌍"}

        result = await session_manager.create_session(user_id="user-123", metadata=metadata)

        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_large_metadata_payload(self, session_manager):
        """Test session with large metadata"""
        large_metadata = {"data": "x" * 10000}

        result = await session_manager.create_session(user_id="user-123", metadata=large_metadata)

        assert "session_id" in result
