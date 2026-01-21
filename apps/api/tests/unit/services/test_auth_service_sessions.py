"""
Auth Service Session Management Tests - Targeting 80%+ Coverage
Tests session validation, refresh, revocation, and multi-device scenarios
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from jose import jwt

from app.config import settings
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


class TestTokenVerification:
    """Test JWT token verification"""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)  # Not blacklisted by default
        return redis

    async def test_verify_token_valid_access(self, mock_redis):
        """Test verifying valid access token"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create a real token
        token, jti, expires = AuthService.create_access_token(user_id, tenant_id)
        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            payload = await AuthService.verify_token(token, token_type="access")

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["tid"] == tenant_id
        assert payload["type"] == "access"

    async def test_verify_token_wrong_type(self, mock_redis):
        """Test verification fails when token type doesn't match"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create access token but verify as refresh
        token, _, _ = AuthService.create_access_token(user_id, tenant_id)

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            payload = await AuthService.verify_token(token, token_type="refresh")

        assert payload is None

    async def test_verify_token_blacklisted(self, mock_redis):
        """Test verification fails for blacklisted token"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        token, jti, _ = AuthService.create_access_token(user_id, tenant_id)

        # Mock Redis to return blacklist entry
        mock_redis.get = AsyncMock(return_value="1")

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            payload = await AuthService.verify_token(token)

        assert payload is None

    async def test_verify_token_invalid_signature(self, mock_redis):
        """Test verification fails for invalid signature"""
        # Create token with wrong secret
        fake_token = jwt.encode(
            {"sub": "user123", "type": "access"}, "wrong-secret-key", algorithm="HS256"
        )

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            payload = await AuthService.verify_token(fake_token)

        assert payload is None

    async def test_verify_token_expired(self, mock_redis):
        """Test verification fails for expired token"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create expired token
        expired_time = datetime.utcnow() - timedelta(hours=1)
        payload_data = {
            "sub": user_id,
            "tid": tenant_id,
            "type": "access",
            "exp": expired_time,
            "iat": datetime.utcnow() - timedelta(hours=2),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        expired_token = jwt.encode(payload_data, settings.JWT_SECRET_KEY, algorithm="HS256")

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            payload = await AuthService.verify_token(expired_token)

        assert payload is None


class TestTokenRefresh:
    """Test token refresh mechanism"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        return redis

    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = uuid4()
        user.tenant_id = uuid4()
        user.is_active = True
        return user

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.id = uuid4()
        session.is_active = True
        session.refresh_token_jti = "test-jti"
        session.refresh_token_family = "test-family"
        session.last_activity_at = None
        session.expires_at = datetime.utcnow() + timedelta(days=1)
        return session

    async def test_refresh_tokens_success(self, mock_db, mock_redis, mock_user, mock_session):
        """Test successful token refresh"""
        # Create refresh token
        refresh_token, jti, family, _ = AuthService.create_refresh_token(
            str(mock_user.id), str(mock_user.tenant_id)
        )
        mock_session.refresh_token_jti = jti

        # Mock database query
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_session)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.get = AsyncMock(return_value=mock_user)
        mock_db.commit = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            result = await AuthService.refresh_tokens(mock_db, refresh_token)

        assert result is not None
        access_token, new_refresh_token = result
        assert isinstance(access_token, str)
        assert isinstance(new_refresh_token, str)
        assert mock_db.commit.called

    async def test_refresh_tokens_invalid_token(self, mock_db, mock_redis):
        """Test refresh fails with invalid token"""
        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            result = await AuthService.refresh_tokens(mock_db, "invalid-token")

        assert result is None

    async def test_refresh_tokens_session_not_found(self, mock_db, mock_redis, mock_user):
        """Test refresh fails when session not in database"""
        refresh_token, _, _, _ = AuthService.create_refresh_token(
            str(mock_user.id), str(mock_user.tenant_id)
        )

        # Mock session not found
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            with patch.object(
                AuthService, "revoke_token_family", new_callable=AsyncMock
            ) as mock_revoke:
                result = await AuthService.refresh_tokens(mock_db, refresh_token)

        assert result is None
        # Verify security measure - family revoked
        mock_revoke.assert_called_once()

    async def test_refresh_tokens_inactive_user(self, mock_db, mock_redis, mock_user, mock_session):
        """Test refresh fails for inactive user"""
        refresh_token, jti, _, _ = AuthService.create_refresh_token(
            str(mock_user.id), str(mock_user.tenant_id)
        )
        mock_session.refresh_token_jti = jti
        mock_user.is_active = False

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_session)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.get = AsyncMock(return_value=mock_user)

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            result = await AuthService.refresh_tokens(mock_db, refresh_token)

        assert result is None


class TestSessionRevocation:
    """Test session revocation mechanisms"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock()
        return redis

    async def test_revoke_token_family(self, mock_db, mock_redis):
        """Test revoking entire token family"""
        family = "test-family"

        # Mock sessions in family
        session1 = Mock()
        session1.access_token_jti = "jti-1"
        session1.refresh_token_jti = "jti-2"
        session1.is_active = True
        session1.revoked_at = None

        session2 = Mock()
        session2.access_token_jti = "jti-3"
        session2.refresh_token_jti = "jti-4"
        session2.is_active = True
        session2.revoked_at = None

        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[session1, session2])))
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            await AuthService.revoke_token_family(mock_db, family)

        # Verify sessions marked inactive
        assert session1.is_active is False
        assert session2.is_active is False
        assert session1.revoked_reason == "family_revoked_security"

        # Verify Redis blacklist calls
        assert mock_redis.set.call_count == 4  # 2 sessions * 2 tokens each

    async def test_logout_success(self, mock_db, mock_redis):
        """Test successful user logout"""
        session_id = uuid4()
        user_id = uuid4()

        # Mock session
        mock_session = Mock()
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session.access_token_jti = "access-jti"
        mock_session.refresh_token_jti = "refresh-jti"
        mock_session.is_active = True
        mock_session.revoked_at = None
        mock_session.user = Mock(tenant_id=uuid4())

        mock_db.get = AsyncMock(return_value=mock_session)
        mock_db.commit = AsyncMock()

        mock_session_store = AsyncMock()
        mock_session_store.delete = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            with patch("app.services.auth_service.SessionStore", return_value=mock_session_store):
                with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
                    result = await AuthService.logout(mock_db, session_id, user_id)

        assert result is True
        assert mock_session.is_active is False
        assert mock_session.revoked_reason == "user_logout"
        assert mock_redis.set.call_count == 2  # Blacklist both tokens

    async def test_logout_session_not_found(self, mock_db, mock_redis):
        """Test logout fails when session not found"""
        mock_db.get = AsyncMock(return_value=None)

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            result = await AuthService.logout(mock_db, uuid4(), uuid4())

        assert result is False

    async def test_logout_wrong_user(self, mock_db, mock_redis):
        """Test logout fails when user doesn't own session"""
        session_id = uuid4()
        user_id = uuid4()
        wrong_user_id = uuid4()

        mock_session = Mock()
        mock_session.user_id = user_id  # Different from wrong_user_id

        mock_db.get = AsyncMock(return_value=mock_session)

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            result = await AuthService.logout(mock_db, session_id, wrong_user_id)

        assert result is False


class TestAuditLog:
    """Test audit log creation and integrity"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = Mock()
        db.execute = AsyncMock()
        return db

    async def test_create_audit_log_first_entry(self, mock_db):
        """Test creating first audit log (genesis)"""
        user_id = uuid4()
        tenant_id = uuid4()

        # Mock no previous log
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        await AuthService.create_audit_log(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            event_type="user_created",
            event_data={"email": "test@example.com"},
        )

        # Verify audit log was added
        assert mock_db.add.called
        added_log = mock_db.add.call_args[0][0]
        assert added_log.event_type == "user_created"
        assert added_log.previous_hash == "genesis"
        assert added_log.current_hash is not None

    async def test_create_audit_log_with_chain(self, mock_db):
        """Test creating audit log with hash chain"""
        user_id = uuid4()
        tenant_id = uuid4()

        # Mock previous log
        previous_log = Mock()
        previous_log.current_hash = "previous-hash-123"

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=previous_log)
        mock_db.execute = AsyncMock(return_value=mock_result)

        await AuthService.create_audit_log(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            event_type="login_success",
            event_data={},
        )

        added_log = mock_db.add.call_args[0][0]
        assert added_log.previous_hash == "previous-hash-123"
        assert added_log.current_hash != "previous-hash-123"  # Should be different

    async def test_create_audit_log_with_metadata(self, mock_db):
        """Test audit log with IP and user agent"""
        user_id = uuid4()
        tenant_id = uuid4()

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        await AuthService.create_audit_log(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            event_type="password_change",
            event_data={"success": True},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        added_log = mock_db.add.call_args[0][0]
        assert added_log.ip_address == "192.168.1.1"
        assert added_log.user_agent == "Mozilla/5.0"


class TestPlaceholderMethods:
    """Test placeholder methods for completeness"""

    def test_update_user(self):
        """Test user update placeholder"""
        mock_db = Mock()
        result = AuthService.update_user(mock_db, "user123", {"name": "Updated"})
        assert result["updated"] is True

    def test_delete_user(self):
        """Test user deletion placeholder"""
        mock_db = Mock()
        result = AuthService.delete_user(mock_db, "user123")
        assert result["deleted"] is True

    def test_get_user_sessions(self):
        """Test get user sessions placeholder"""
        mock_db = Mock()
        result = AuthService.get_user_sessions(mock_db, "user123")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_revoke_session(self):
        """Test revoke session placeholder"""
        mock_db = Mock()
        result = AuthService.revoke_session(mock_db, "session123")
        assert result["revoked"] is True

    def test_create_organization(self):
        """Test create organization placeholder"""
        mock_db = Mock()
        result = AuthService.create_organization(
            mock_db, "user123", {"name": "Test Org", "slug": "test-org"}
        )
        assert result["id"] == "org_123"
        assert result["name"] == "Test Org"

    def test_get_user_organizations(self):
        """Test get user organizations placeholder"""
        mock_db = Mock()
        result = AuthService.get_user_organizations(mock_db, "user123")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_organization(self):
        """Test get organization placeholder"""
        mock_db = Mock()
        result = AuthService.get_organization(mock_db, "org123")
        assert result["id"] == "org123"

    def test_update_organization(self):
        """Test update organization placeholder"""
        mock_db = Mock()
        result = AuthService.update_organization(mock_db, "org123", {"name": "Updated"})
        assert result["updated"] is True

    def test_delete_organization(self):
        """Test delete organization placeholder"""
        mock_db = Mock()
        result = AuthService.delete_organization(mock_db, "org123")
        assert result["deleted"] is True

    def test_get_active_sessions(self):
        """Test get active sessions placeholder"""
        mock_db = Mock()
        result = AuthService.get_active_sessions(mock_db, "user123")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["current"] is True

    def test_revoke_all_sessions(self):
        """Test revoke all sessions placeholder"""
        mock_db = Mock()
        result = AuthService.revoke_all_sessions(mock_db, "user123")
        assert result["revoked_count"] == 3

    def test_extend_session(self):
        """Test extend session placeholder"""
        mock_db = Mock()
        result = AuthService.extend_session(mock_db, "session123", {})
        assert result["extended"] is True
