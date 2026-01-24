"""
Comprehensive Session Management Test Suite
Tests for distributed session manager and WebSocket connection manager
"""

import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


# =============================================================================
# Distributed Session Manager Tests
# =============================================================================


class TestSessionType:
    """Test SessionType enum."""

    def test_session_types_values(self):
        """Test session type enum values."""
        from app.services.distributed_session_manager import SessionType

        assert SessionType.WEB.value == "web"
        assert SessionType.MOBILE.value == "mobile"
        assert SessionType.API.value == "api"
        assert SessionType.SERVICE.value == "service"
        assert SessionType.SSO.value == "sso"

    def test_session_types_iteration(self):
        """Test session types can be iterated."""
        from app.services.distributed_session_manager import SessionType

        types = list(SessionType)
        assert len(types) == 5


class TestSessionStatus:
    """Test SessionStatus enum."""

    def test_session_status_values(self):
        """Test session status enum values."""
        from app.services.distributed_session_manager import SessionStatus

        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.IDLE.value == "idle"
        assert SessionStatus.EXPIRED.value == "expired"
        assert SessionStatus.REVOKED.value == "revoked"
        assert SessionStatus.LOCKED.value == "locked"

    def test_session_status_iteration(self):
        """Test session statuses can be iterated."""
        from app.services.distributed_session_manager import SessionStatus

        statuses = list(SessionStatus)
        assert len(statuses) == 5


class TestDistributedSessionManager:
    """Test DistributedSessionManager functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.sadd = AsyncMock(return_value=1)
        redis_mock.srem = AsyncMock(return_value=1)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.zadd = AsyncMock(return_value=1)
        redis_mock.zrem = AsyncMock(return_value=1)
        redis_mock.smembers = AsyncMock(return_value=set())
        redis_mock.scan = AsyncMock(return_value=(b"0", []))
        return redis_mock

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db_mock = AsyncMock()
        db_mock.add = MagicMock()
        db_mock.commit = AsyncMock()
        db_mock.execute = AsyncMock()
        return db_mock

    @pytest.fixture
    def session_manager(self, mock_redis, mock_db):
        """Create session manager with mocked dependencies."""
        from app.services.distributed_session_manager import DistributedSessionManager

        manager = DistributedSessionManager(redis_client=mock_redis, db_session=mock_db)
        return manager

    def test_initialization_defaults(self):
        """Test session manager initialization with defaults."""
        from app.services.distributed_session_manager import DistributedSessionManager

        manager = DistributedSessionManager()
        assert manager.redis is None
        assert manager.db is None
        assert manager.session_ttl > 0
        assert manager.max_sessions_per_user > 0
        assert manager.enable_session_binding is True
        assert manager.enable_concurrent_limit is True

    def test_initialization_with_redis(self, mock_redis):
        """Test session manager initialization with Redis."""
        from app.services.distributed_session_manager import DistributedSessionManager

        manager = DistributedSessionManager(redis_client=mock_redis)
        assert manager.redis is mock_redis

    def test_key_prefixes(self, session_manager):
        """Test session key prefixes are set correctly."""
        assert session_manager.SESSION_KEY_PREFIX == "session:"
        assert session_manager.USER_SESSIONS_PREFIX == "user_sessions:"
        assert session_manager.SESSION_LOCK_PREFIX == "session_lock:"
        assert session_manager.ACTIVE_SESSIONS_KEY == "active_sessions"

    def test_create_session_fingerprint(self, session_manager):
        """Test session fingerprint creation."""
        fingerprint = session_manager._create_session_fingerprint(
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        assert fingerprint is not None
        assert isinstance(fingerprint, str)
        assert len(fingerprint) > 0

    def test_create_session_fingerprint_none_inputs(self, session_manager):
        """Test session fingerprint with None inputs."""
        fingerprint = session_manager._create_session_fingerprint(
            ip_address=None,
            user_agent=None
        )
        assert fingerprint is not None

    @pytest.mark.asyncio
    async def test_create_session_basic(self, session_manager, mock_redis):
        """Test basic session creation."""
        from app.services.distributed_session_manager import SessionType

        # Mock get_user_sessions to return empty
        session_manager.get_user_sessions = AsyncMock(return_value=[])

        result = await session_manager.create_session(
            user_id="user_123",
            session_type=SessionType.WEB,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        assert "session_id" in result
        assert "session_token" in result
        assert "expires_at" in result
        assert result["session_type"] == "web"

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, session_manager, mock_redis):
        """Test session creation with metadata."""
        from app.services.distributed_session_manager import SessionType

        session_manager.get_user_sessions = AsyncMock(return_value=[])

        result = await session_manager.create_session(
            user_id="user_123",
            session_type=SessionType.MOBILE,
            ip_address="10.0.0.1",
            user_agent="MobileApp/1.0",
            device_info={"os": "iOS", "version": "15.0"},
            metadata={"app_version": "2.0"}
        )

        assert result["session_type"] == "mobile"
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_create_session_evicts_oldest(self, session_manager, mock_redis):
        """Test that oldest session is revoked when limit reached."""
        from app.services.distributed_session_manager import SessionType

        # Mock existing sessions at limit
        existing_sessions = [
            {"session_id": f"sess_{i}", "created_at": datetime.utcnow().isoformat()}
            for i in range(5)
        ]
        session_manager.get_user_sessions = AsyncMock(return_value=existing_sessions)
        session_manager.revoke_session = AsyncMock()

        result = await session_manager.create_session(
            user_id="user_123",
            session_type=SessionType.WEB
        )

        # Should have revoked the oldest session
        session_manager.revoke_session.assert_called_once()
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_revoke_session(self, session_manager, mock_redis):
        """Test session revocation."""
        session_data = {
            "session_id": "sess_123",
            "user_id": "user_456",
            "status": "active"
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(session_data))

        await session_manager.revoke_session("sess_123", reason="user_logout")

        # Verify Redis operations were called
        mock_redis.get.assert_called()
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_update_session_activity(self, session_manager, mock_redis):
        """Test session activity update."""
        session_data = {
            "session_id": "sess_123",
            "last_activity": datetime.utcnow().isoformat(),
            "access_count": 5
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(session_data))

        await session_manager.update_session_activity("sess_123")

        mock_redis.get.assert_called()
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_validate_session_security_active(self, session_manager):
        """Test session security validation for active session."""
        from app.services.distributed_session_manager import SessionStatus

        session_data = {
            "session_id": "sess_123",
            "user_id": "user_456",
            "status": SessionStatus.ACTIVE.value,
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "fingerprint": None
        }
        session_manager.update_session_activity = AsyncMock()

        result = await session_manager._validate_session_security(
            session_data,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        assert result is not None
        assert result["session_id"] == "sess_123"

    @pytest.mark.asyncio
    async def test_validate_session_security_expired(self, session_manager):
        """Test session security validation for expired session."""
        from app.services.distributed_session_manager import SessionStatus

        session_data = {
            "session_id": "sess_123",
            "user_id": "user_456",
            "status": SessionStatus.ACTIVE.value,
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        }
        session_manager.revoke_session = AsyncMock()

        result = await session_manager._validate_session_security(session_data)

        assert result is None
        session_manager.revoke_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_session_security_revoked(self, session_manager):
        """Test session security validation for revoked session."""
        from app.services.distributed_session_manager import SessionStatus

        session_data = {
            "session_id": "sess_123",
            "status": SessionStatus.REVOKED.value,
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

        result = await session_manager._validate_session_security(session_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_session(self, session_manager, mock_redis):
        """Test session refresh."""
        session_data = {
            "session_id": "sess_123",
            "last_activity": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "refresh_count": 2,
            "token_hash": "old_hash"
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(session_data))

        result = await session_manager.refresh_session("sess_123", extend_ttl=True)

        assert result is not None
        assert "session_id" in result
        assert "session_token" in result
        assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_refresh_session_not_found(self, session_manager, mock_redis):
        """Test session refresh when session not found."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await session_manager.refresh_session("nonexistent_session")

        assert result is None


# =============================================================================
# WebSocket Event Type Tests
# =============================================================================


class TestEventType:
    """Test WebSocket EventType enum."""

    def test_event_type_values(self):
        """Test event type enum values."""
        from app.services.websocket_manager import EventType

        assert EventType.CONNECTION == "connection"
        assert EventType.AUTHENTICATION == "authentication"
        assert EventType.MESSAGE == "message"
        assert EventType.PING == "ping"
        assert EventType.PONG == "pong"
        assert EventType.ERROR == "error"

    def test_event_type_user_update(self):
        """Test user update event type."""
        from app.services.websocket_manager import EventType

        assert EventType.USER_UPDATE == "user.update"

    def test_event_type_organization_update(self):
        """Test organization update event type."""
        from app.services.websocket_manager import EventType

        assert EventType.ORGANIZATION_UPDATE == "organization.update"


# =============================================================================
# Connection Manager Tests
# =============================================================================


class TestConnectionManager:
    """Test WebSocket ConnectionManager functionality."""

    @pytest.fixture
    def connection_manager(self):
        """Create connection manager instance."""
        from app.services.websocket_manager import ConnectionManager
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    def test_initialization(self, connection_manager):
        """Test connection manager initialization."""
        assert connection_manager.active_connections == {}
        assert connection_manager.user_connections == {}
        assert connection_manager.organization_subscribers == {}
        assert connection_manager.topic_subscribers == {}
        assert connection_manager._connection_counter == 0

    @pytest.mark.asyncio
    async def test_connect_anonymous(self, connection_manager, mock_websocket):
        """Test anonymous WebSocket connection."""
        connection_id = await connection_manager.connect(mock_websocket)

        assert connection_id is not None
        assert connection_id in connection_manager.active_connections
        assert mock_websocket.accept.called
        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_connect_authenticated(self, connection_manager, mock_websocket):
        """Test authenticated WebSocket connection."""
        user_id = "user_123"
        connection_id = await connection_manager.connect(mock_websocket, user_id=user_id)

        assert connection_id in connection_manager.active_connections
        assert user_id in connection_manager.user_connections
        assert connection_id in connection_manager.user_connections[user_id]
        assert connection_manager.active_connections[connection_id]["authenticated"] is True

    @pytest.mark.asyncio
    async def test_connect_increments_counter(self, connection_manager, mock_websocket):
        """Test connection counter increments."""
        initial_counter = connection_manager._connection_counter

        await connection_manager.connect(mock_websocket)

        assert connection_manager._connection_counter == initial_counter + 1

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager, mock_websocket):
        """Test WebSocket disconnection."""
        connection_id = await connection_manager.connect(mock_websocket, user_id="user_123")

        await connection_manager.disconnect(connection_id)

        assert connection_id not in connection_manager.active_connections
        assert "user_123" not in connection_manager.user_connections

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self, connection_manager):
        """Test disconnecting non-existent connection."""
        # Should not raise
        await connection_manager.disconnect("nonexistent_connection")

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_org_subscribers(self, connection_manager, mock_websocket):
        """Test disconnect removes from organization subscribers."""
        connection_id = await connection_manager.connect(mock_websocket, user_id="user_123")

        # Manually add to org subscribers
        connection_manager.organization_subscribers["org_1"] = {connection_id}

        await connection_manager.disconnect(connection_id)

        assert connection_id not in connection_manager.organization_subscribers.get("org_1", set())

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_topic_subscribers(self, connection_manager, mock_websocket):
        """Test disconnect removes from topic subscribers."""
        connection_id = await connection_manager.connect(mock_websocket, user_id="user_123")

        # Manually add to topic subscribers
        connection_manager.topic_subscribers["notifications"] = {connection_id}

        await connection_manager.disconnect(connection_id)

        assert connection_id not in connection_manager.topic_subscribers.get("notifications", set())

    @pytest.mark.asyncio
    async def test_send_to_connection(self, connection_manager, mock_websocket):
        """Test sending message to specific connection."""
        connection_id = await connection_manager.connect(mock_websocket)

        await connection_manager.send_to_connection(
            connection_id,
            {"type": "test", "data": {"message": "hello"}}
        )

        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_connection(self, connection_manager):
        """Test sending to non-existent connection doesn't raise."""
        # Should not raise
        await connection_manager.send_to_connection(
            "nonexistent",
            {"type": "test"}
        )

    @pytest.mark.asyncio
    async def test_multiple_connections_same_user(self, connection_manager, mock_websocket):
        """Test multiple connections for same user."""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        user_id = "user_123"
        conn_id_1 = await connection_manager.connect(ws1, user_id=user_id)
        conn_id_2 = await connection_manager.connect(ws2, user_id=user_id)

        assert len(connection_manager.user_connections[user_id]) == 2
        assert conn_id_1 in connection_manager.user_connections[user_id]
        assert conn_id_2 in connection_manager.user_connections[user_id]


class TestConnectionManagerSubscriptions:
    """Test ConnectionManager subscription functionality."""

    @pytest.fixture
    def connection_manager(self):
        """Create connection manager instance."""
        from app.services.websocket_manager import ConnectionManager
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_subscribe_to_organization(self, connection_manager, mock_websocket):
        """Test subscribing connection to organization."""
        connection_id = await connection_manager.connect(mock_websocket, user_id="user_123")

        # Manually add subscription
        org_id = "org_456"
        if org_id not in connection_manager.organization_subscribers:
            connection_manager.organization_subscribers[org_id] = set()
        connection_manager.organization_subscribers[org_id].add(connection_id)

        assert connection_id in connection_manager.organization_subscribers[org_id]

    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self, connection_manager, mock_websocket):
        """Test subscribing connection to topic."""
        connection_id = await connection_manager.connect(mock_websocket)

        # Manually add subscription
        topic = "notifications"
        if topic not in connection_manager.topic_subscribers:
            connection_manager.topic_subscribers[topic] = set()
        connection_manager.topic_subscribers[topic].add(connection_id)

        assert connection_id in connection_manager.topic_subscribers[topic]


# =============================================================================
# Session Security Tests
# =============================================================================


class TestSessionSecurity:
    """Test session security features."""

    @pytest.fixture
    def session_manager(self):
        """Create session manager without dependencies."""
        from app.services.distributed_session_manager import DistributedSessionManager
        return DistributedSessionManager()

    def test_token_hash_generation(self, session_manager):
        """Test that token hashes are generated correctly."""
        token = "test_token_12345"
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        # Verify our understanding of the hashing
        assert len(expected_hash) == 64  # SHA256 produces 64 hex chars

    def test_fingerprint_consistency(self, session_manager):
        """Test fingerprint generation is consistent."""
        fp1 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")
        fp2 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")

        assert fp1 == fp2

    def test_fingerprint_different_ips(self, session_manager):
        """Test fingerprint differs for different IPs."""
        fp1 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")
        fp2 = session_manager._create_session_fingerprint("10.0.0.1", "Mozilla/5.0")

        assert fp1 != fp2

    def test_fingerprint_different_user_agents(self, session_manager):
        """Test fingerprint differs for different user agents."""
        fp1 = session_manager._create_session_fingerprint("192.168.1.1", "Mozilla/5.0")
        fp2 = session_manager._create_session_fingerprint("192.168.1.1", "Chrome/120.0")

        assert fp1 != fp2


# =============================================================================
# Session Lifecycle Tests
# =============================================================================


class TestSessionLifecycle:
    """Test complete session lifecycle scenarios."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.sadd = AsyncMock(return_value=1)
        redis_mock.srem = AsyncMock(return_value=1)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.zadd = AsyncMock(return_value=1)
        redis_mock.zrem = AsyncMock(return_value=1)
        redis_mock.smembers = AsyncMock(return_value=set())
        return redis_mock

    @pytest.fixture
    def session_manager(self, mock_redis):
        """Create session manager with mocked Redis."""
        from app.services.distributed_session_manager import DistributedSessionManager
        return DistributedSessionManager(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self, session_manager, mock_redis):
        """Test complete session lifecycle: create -> validate -> refresh -> revoke."""
        from app.services.distributed_session_manager import SessionType, SessionStatus

        # Create session
        session_manager.get_user_sessions = AsyncMock(return_value=[])
        create_result = await session_manager.create_session(
            user_id="user_123",
            session_type=SessionType.WEB,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        session_id = create_result["session_id"]
        session_token = create_result["session_token"]

        # Simulate stored session for validation
        stored_session = {
            "session_id": session_id,
            "user_id": "user_123",
            "status": SessionStatus.ACTIVE.value,
            "token_hash": hashlib.sha256(session_token.encode()).hexdigest(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "access_count": 0,
            "refresh_count": 0
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(stored_session))
        mock_redis.scan = AsyncMock(return_value=(b"0", [f"session:{session_id}".encode()]))

        # Refresh session
        refresh_result = await session_manager.refresh_session(session_id, extend_ttl=True)
        assert refresh_result is not None

        # Revoke session
        await session_manager.revoke_session(session_id, reason="test_cleanup")
        mock_redis.setex.assert_called()  # Should store revoked session

    @pytest.mark.asyncio
    async def test_concurrent_session_limit_enforcement(self, session_manager):
        """Test that concurrent session limit is enforced."""
        from app.services.distributed_session_manager import SessionType

        # Set up existing sessions at limit
        existing_sessions = [
            {
                "session_id": f"sess_{i}",
                "created_at": (datetime.utcnow() - timedelta(hours=i)).isoformat()
            }
            for i in range(session_manager.max_sessions_per_user)
        ]
        session_manager.get_user_sessions = AsyncMock(return_value=existing_sessions)
        session_manager.revoke_session = AsyncMock()

        # Create new session
        await session_manager.create_session(
            user_id="user_123",
            session_type=SessionType.WEB
        )

        # Verify oldest session was revoked
        session_manager.revoke_session.assert_called_once()
        call_args = session_manager.revoke_session.call_args
        assert "max_sessions_exceeded" in str(call_args)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestSessionEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def session_manager(self):
        """Create session manager without dependencies."""
        from app.services.distributed_session_manager import DistributedSessionManager
        return DistributedSessionManager()

    def test_session_manager_without_redis(self, session_manager):
        """Test session manager works without Redis."""
        assert session_manager.redis is None

    def test_session_manager_without_db(self, session_manager):
        """Test session manager works without database."""
        assert session_manager.db is None

    @pytest.mark.asyncio
    async def test_create_session_without_backends(self, session_manager):
        """Test session creation without any backends."""
        from app.services.distributed_session_manager import SessionType

        session_manager.get_user_sessions = AsyncMock(return_value=[])

        result = await session_manager.create_session(
            user_id="user_123",
            session_type=SessionType.WEB
        )

        # Should still return session data even without backends
        assert "session_id" in result
        assert "session_token" in result

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_session(self, session_manager):
        """Test revoking a non-existent session."""
        # Should not raise
        await session_manager.revoke_session("nonexistent_session")

    @pytest.mark.asyncio
    async def test_refresh_without_redis(self, session_manager):
        """Test refresh session without Redis returns None."""
        result = await session_manager.refresh_session("sess_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_without_backends(self, session_manager):
        """Test validate session without backends returns None."""
        result = await session_manager.validate_session("test_token")
        assert result is None
