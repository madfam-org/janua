import pytest
pytestmark = pytest.mark.asyncio


"""
Working unit tests for AuthService - matches actual implementation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from app.services.auth_service import AuthService
from app.models import User, Session, AuditLog


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for auth service tests."""
    with patch('app.services.auth_service.settings') as mock_settings:
        mock_settings.JWT_SECRET_KEY = "test_secret_key"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = "test_issuer"
        mock_settings.JWT_AUDIENCE = "test_audience"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        yield mock_settings


class TestPasswordHandling:
    """Test password hashing and validation."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert len(hashed) > 50  # bcrypt hash length
        assert hashed.startswith("$2b$")

    def test_verify_password_success(self):
        """Test password verification success."""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        """Test password verification failure."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(wrong_password, hashed) is False

    def test_validate_password_strength_success(self):
        """Test password strength validation success."""
        strong_password = "StrongPassword123!"

        is_valid, error_msg = AuthService.validate_password_strength(strong_password)

        assert is_valid is True
        assert error_msg is None

    def test_validate_password_strength_too_short(self):
        """Test password strength validation - too short."""
        short_password = "Test123!"

        is_valid, error_msg = AuthService.validate_password_strength(short_password)

        assert is_valid is False
        assert "at least 12 characters" in error_msg

    def test_validate_password_strength_no_uppercase(self):
        """Test password strength validation - no uppercase."""
        no_upper = "testpassword123!"

        is_valid, error_msg = AuthService.validate_password_strength(no_upper)

        assert is_valid is False
        assert "uppercase letter" in error_msg

    def test_validate_password_strength_no_lowercase(self):
        """Test password strength validation - no lowercase."""
        no_lower = "TESTPASSWORD123!"

        is_valid, error_msg = AuthService.validate_password_strength(no_lower)

        assert is_valid is False
        assert "lowercase letter" in error_msg

    def test_validate_password_strength_no_number(self):
        """Test password strength validation - no number."""
        no_number = "TestPassword!"

        is_valid, error_msg = AuthService.validate_password_strength(no_number)

        assert is_valid is False
        assert "one number" in error_msg

    def test_validate_password_strength_no_special(self):
        """Test password strength validation - no special character."""
        no_special = "TestPassword123"

        is_valid, error_msg = AuthService.validate_password_strength(no_special)

        assert is_valid is False
        assert "special character" in error_msg


class TestUserCreation:
    """Test user creation functionality."""

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """Test successful user creation."""
        mock_db = AsyncMock()

        # Mock database execute result for user existence check
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user
        mock_db.execute.return_value = mock_result

        # Mock user creation
        with patch.object(AuthService, 'create_audit_log') as mock_audit:
            user = await AuthService.create_user(
                db=mock_db,
                email="test@example.com",
                password="TestPassword123!",
                name="Test User"
            )

            # Verify user was created
            mock_db.add.assert_called()
            mock_db.commit.assert_called()
            mock_db.refresh.assert_called()
            mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_weak_password(self):
        """Test user creation with weak password."""
        mock_db = AsyncMock()

        with pytest.raises(ValueError, match="at least 12 characters"):
            await AuthService.create_user(
                db=mock_db,
                email="test@example.com",
                password="weak",
                name="Test User"
            )

    @pytest.mark.asyncio
    async def test_create_user_existing_email(self):
        """Test user creation with existing email."""
        mock_db = AsyncMock()

        # Mock existing user
        existing_user = Mock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = existing_user  # User exists
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.exceptions import ConflictError

        with pytest.raises(ConflictError, match="already exists"):
            await AuthService.create_user(
                db=mock_db,
                email="test@example.com",
                password="TestPassword123!",
                name="Test User"
            )

    @pytest.mark.asyncio
    async def test_create_user_with_tenant_id(self):
        """Test user creation with specific tenant ID."""
        mock_db = AsyncMock()

        # Mock no existing user
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        tenant_id = uuid4()

        with patch.object(AuthService, 'create_audit_log') as mock_audit:
            user = await AuthService.create_user(
                db=mock_db,
                email="test@example.com",
                password="TestPassword123!",
                name="Test User",
                tenant_id=tenant_id
            )

            # Should not query for tenant
            mock_db.add.assert_called()
            mock_audit.assert_called_once()


class TestUserAuthentication:
    """Test user authentication functionality."""

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self):
        """Test successful user authentication."""
        mock_db = AsyncMock()

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = uuid4()
        mock_user.tenant_id = uuid4()
        mock_user.is_active = True
        mock_user.is_suspended = False
        mock_user.password_hash = AuthService.hash_password("TestPassword123!")

        # Mock database execute result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch.object(AuthService, 'create_audit_log') as mock_audit:
            result = await AuthService.authenticate_user(
                db=mock_db,
                email="test@example.com",
                password="TestPassword123!"
            )

            assert result == mock_user
            assert mock_user.last_login_at is not None
            mock_audit.assert_called_once()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self):
        """Test authentication with non-existent user."""
        mock_db = AsyncMock()

        # Mock no user found
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await AuthService.authenticate_user(
            db=mock_db,
            email="test@example.com",
            password="TestPassword123!"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self):
        """Test authentication with inactive user."""
        mock_db = AsyncMock()

        # Mock inactive user
        mock_user = AsyncMock()
        mock_user.is_active = False
        mock_user.is_suspended = False

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await AuthService.authenticate_user(
            db=mock_db,
            email="test@example.com",
            password="TestPassword123!"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_suspended(self):
        """Test authentication with suspended user."""
        mock_db = AsyncMock()

        # Mock suspended user
        mock_user = AsyncMock()
        mock_user.is_active = True
        mock_user.is_suspended = True

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await AuthService.authenticate_user(
            db=mock_db,
            email="test@example.com",
            password="TestPassword123!"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password."""
        mock_db = AsyncMock()

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = uuid4()
        mock_user.tenant_id = uuid4()
        mock_user.is_active = True
        mock_user.is_suspended = False
        mock_user.password_hash = AuthService.hash_password("CorrectPassword123!")

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch.object(AuthService, 'create_audit_log') as mock_audit:
            result = await AuthService.authenticate_user(
                db=mock_db,
                email="test@example.com",
                password="WrongPassword123!"
            )

            assert result is None
            # Should log failed attempt
            mock_audit.assert_called_once()
            args, kwargs = mock_audit.call_args
            assert kwargs["event_type"] == "login_failed"


class TestTokenCreation:
    """Test JWT token creation."""

    def test_create_access_token(self):
        """Test access token creation."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long
        assert isinstance(jti, str)
        assert len(jti) > 20  # URL-safe token
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.utcnow()

    def test_create_access_token_with_organization(self):
        """Test access token creation with organization ID."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        org_id = str(uuid4())

        token, jti, expires_at = AuthService.create_access_token(
            user_id, tenant_id, org_id
        )

        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(expires_at, datetime)

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        token, jti, family, expires_at = AuthService.create_refresh_token(user_id, tenant_id)

        assert isinstance(token, str)
        assert len(token) > 50
        assert isinstance(jti, str)
        assert len(jti) > 20
        assert isinstance(family, str)
        assert len(family) > 20
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.utcnow()

    def test_create_refresh_token_with_family(self):
        """Test refresh token creation with existing family."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        existing_family = "existing_family_id"

        token, jti, family, expires_at = AuthService.create_refresh_token(
            user_id, tenant_id, existing_family
        )

        assert family == existing_family
        assert isinstance(token, str)
        assert isinstance(jti, str)


class TestSessionManagement:
    """Test session management functionality."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation."""
        mock_db = AsyncMock()

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = uuid4()
        mock_user.tenant_id = uuid4()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_session_store = AsyncMock()

        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch('app.services.auth_service.SessionStore', return_value=mock_session_store):

            access_token, refresh_token, session = await AuthService.create_session(
                db=mock_db,
                user=mock_user,
                ip_address="127.0.0.1",
                user_agent="Test Agent",
                device_name="Test Device"
            )

            assert isinstance(access_token, str)
            assert isinstance(refresh_token, str)
            assert isinstance(session, Session)

            # Verify database operations
            mock_db.add.assert_called()
            mock_db.commit.assert_called()
            mock_db.refresh.assert_called()

            # Verify Redis operations
            mock_session_store.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Test successful token verification."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create a token
        token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Not blacklisted

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            payload = await AuthService.verify_token(token, "access")

            assert payload is not None
            assert payload["sub"] == user_id
            assert payload["tid"] == tenant_id
            assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_verify_token_blacklisted(self):
        """Test token verification with blacklisted token."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create a token
        token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        # Mock Redis - token is blacklisted
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "1"  # Blacklisted

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            payload = await AuthService.verify_token(token, "access")

            assert payload is None

    @pytest.mark.asyncio
    async def test_verify_token_wrong_type(self):
        """Test token verification with wrong token type."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create an access token
        token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            payload = await AuthService.verify_token(token, "refresh")  # Wrong type

            assert payload is None

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        invalid_token = "invalid.jwt.token"

        # Mock Redis
        mock_redis = AsyncMock()

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            payload = await AuthService.verify_token(invalid_token, "access")

            assert payload is None


class TestTokenRefresh:
    """Test token refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self):
        """Test successful token refresh."""
        mock_db = AsyncMock()

        # Create a refresh token
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        refresh_token, refresh_jti, family, expires_at = AuthService.create_refresh_token(
            user_id, tenant_id
        )

        # Mock session
        mock_session = AsyncMock()
        mock_session.refresh_token_jti = refresh_jti
        mock_session.is_active = True

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = UUID(user_id)
        mock_user.tenant_id = UUID(tenant_id)
        mock_user.is_active = True

        mock_db.get.return_value = mock_user

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Not blacklisted

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            result = await AuthService.refresh_tokens(mock_db, refresh_token)

            assert result is not None
            new_access_token, new_refresh_token = result
            assert isinstance(new_access_token, str)
            assert isinstance(new_refresh_token, str)
            assert new_access_token != new_refresh_token

            # Verify database updates
            mock_db.commit.assert_called()
            # Verify old token blacklisted
            mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_refresh_tokens_invalid_token(self):
        """Test token refresh with invalid refresh token."""
        mock_db = AsyncMock()
        invalid_token = "invalid.refresh.token"

        # Mock Redis
        mock_redis = AsyncMock()

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            result = await AuthService.refresh_tokens(mock_db, invalid_token)

            assert result is None

    @pytest.mark.asyncio
    async def test_refresh_tokens_session_not_found(self):
        """Test token refresh with session not found."""
        mock_db = AsyncMock()

        # Create a refresh token
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        refresh_token, refresh_jti, family, expires_at = AuthService.create_refresh_token(
            user_id, tenant_id
        )

        # Mock no session found
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, 'revoke_token_family') as mock_revoke:

            result = await AuthService.refresh_tokens(mock_db, refresh_token)

            assert result is None
            # Should revoke entire family on potential reuse
            mock_revoke.assert_called_once_with(mock_db, family)


class TestLogout:
    """Test logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_success(self):
        """Test successful logout."""
        mock_db = AsyncMock()

        session_id = uuid4()
        user_id = uuid4()

        # Mock session
        mock_session = AsyncMock()
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session.access_token_jti = "access_jti"
        mock_session.refresh_token_jti = "refresh_jti"
        mock_session.user.tenant_id = uuid4()

        mock_db.get.return_value = mock_session

        # Mock Redis and session store
        mock_redis = AsyncMock()
        mock_session_store = AsyncMock()

        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch('app.services.auth_service.SessionStore', return_value=mock_session_store), \
             patch.object(AuthService, 'create_audit_log') as mock_audit:

            result = await AuthService.logout(mock_db, session_id, user_id)

            assert result is True
            assert mock_session.is_active is False
            assert mock_session.revoked_reason == "user_logout"

            # Verify Redis operations
            assert mock_redis.set.call_count == 2  # Blacklist both tokens
            mock_session_store.delete.assert_called_once()

            # Verify audit log
            mock_audit.assert_called_once()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_logout_session_not_found(self):
        """Test logout with session not found."""
        mock_db = AsyncMock()

        session_id = uuid4()
        user_id = uuid4()

        # Mock no session found
        mock_db.get.return_value = None

        result = await AuthService.logout(mock_db, session_id, user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_logout_wrong_user(self):
        """Test logout with wrong user ID."""
        mock_db = AsyncMock()

        session_id = uuid4()
        user_id = uuid4()
        wrong_user_id = uuid4()

        # Mock session with different user
        mock_session = AsyncMock()
        mock_session.user_id = wrong_user_id

        mock_db.get.return_value = mock_session

        result = await AuthService.logout(mock_db, session_id, user_id)

        assert result is False


class TestAuditLogging:
    """Test audit logging functionality."""

    @pytest.mark.asyncio
    async def test_create_audit_log_first_entry(self):
        """Test creating first audit log entry."""
        mock_db = AsyncMock()

        user_id = uuid4()
        tenant_id = uuid4()

        # Mock no previous log
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        await AuthService.create_audit_log(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            event_type="test_event",
            event_data={"test": "data"},
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )

        # Verify audit log created
        mock_db.add.assert_called_once()
        log_instance = mock_db.add.call_args[0][0]
        assert isinstance(log_instance, AuditLog)
        assert log_instance.user_id == user_id
        assert log_instance.tenant_id == tenant_id
        assert log_instance.event_type == "test_event"
        assert log_instance.previous_hash == "genesis"
        assert log_instance.current_hash is not None

    @pytest.mark.asyncio
    async def test_create_audit_log_with_chain(self):
        """Test creating audit log entry with previous hash."""
        mock_db = AsyncMock()

        user_id = uuid4()
        tenant_id = uuid4()

        # Mock previous log
        mock_previous_log = AsyncMock()
        mock_previous_log.current_hash = "previous_hash_123"

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_previous_log
        mock_db.execute.return_value = mock_result

        await AuthService.create_audit_log(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            event_type="test_event",
            event_data={"test": "data"}
        )

        # Verify audit log created with chain
        mock_db.add.assert_called_once()
        log_instance = mock_db.add.call_args[0][0]
        assert log_instance.previous_hash == "previous_hash_123"
        assert log_instance.current_hash is not None
        assert log_instance.current_hash != "previous_hash_123"


class TestTokenFamilyRevocation:
    """Test token family revocation functionality."""

    @pytest.mark.asyncio
    async def test_revoke_token_family(self):
        """Test revoking entire token family."""
        mock_db = AsyncMock()

        family = "test_family_123"

        # Mock sessions in family
        session1 = Mock()
        session1.access_token_jti = "access_jti_1"
        session1.refresh_token_jti = "refresh_jti_1"

        session2 = Mock()
        session2.access_token_jti = "access_jti_2"
        session2.refresh_token_jti = "refresh_jti_2"

        # Mock database execute result for sessions query
        mock_scalars = AsyncMock()
        mock_scalars.all.return_value = [session1, session2]
        mock_result = AsyncMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Mock Redis
        mock_redis = AsyncMock()

        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            await AuthService.revoke_token_family(mock_db, family)

            # Verify sessions revoked
            assert session1.is_active is False
            assert session1.revoked_reason == "family_revoked_security"
            assert session2.is_active is False
            assert session2.revoked_reason == "family_revoked_security"

            # Verify tokens blacklisted
            assert mock_redis.set.call_count == 4  # 2 sessions × 2 tokens each

            mock_db.commit.assert_called()


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_create_user_database_error(self):
        """Test user creation with database error."""
        mock_db = AsyncMock()

        # Mock database error
        mock_db.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            await AuthService.create_user(
                db=mock_db,
                email="test@example.com",
                password="TestPassword123!",
                name="Test User"
            )

    @pytest.mark.asyncio
    async def test_authenticate_user_database_error(self):
        """Test authentication with database error."""
        mock_db = AsyncMock()

        # Mock database error
        mock_db.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            await AuthService.authenticate_user(
                db=mock_db,
                email="test@example.com",
                password="TestPassword123!"
            )

    @pytest.mark.asyncio
    async def test_create_session_redis_error(self):
        """Test session creation with Redis error."""
        mock_db = AsyncMock()

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = uuid4()
        mock_user.tenant_id = uuid4()

        # Mock Redis error
        with patch('app.services.auth_service.get_redis', side_effect=Exception("Redis error")):
            with pytest.raises(Exception):
                await AuthService.create_session(
                    db=mock_db,
                    user=mock_user
                )