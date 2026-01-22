import pytest

pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for AuthService
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.auth_service import AuthService


class TestPasswordHandling:
    """Test password hashing and validation."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt format
        assert len(hashed) > 50  # Reasonable length for bcrypt hash

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(wrong_password, hashed) is False

    def test_validate_password_strength_valid(self):
        """Test password strength validation with valid password."""
        password = "ValidPassword123!@#"
        is_valid, error = AuthService.validate_password_strength(password)

        assert is_valid is True
        assert error is None

    def test_validate_password_strength_too_short(self):
        """Test password strength validation with too short password."""
        password = "Short1!"
        is_valid, error = AuthService.validate_password_strength(password)

        assert is_valid is False
        assert "at least 12 characters" in error

    def test_validate_password_strength_no_uppercase(self):
        """Test password strength validation without uppercase."""
        password = "validpassword123!"
        is_valid, error = AuthService.validate_password_strength(password)

        assert is_valid is False
        assert "uppercase letter" in error

    def test_validate_password_strength_no_lowercase(self):
        """Test password strength validation without lowercase."""
        password = "VALIDPASSWORD123!"
        is_valid, error = AuthService.validate_password_strength(password)

        assert is_valid is False
        assert "lowercase letter" in error

    def test_validate_password_strength_no_number(self):
        """Test password strength validation without number."""
        password = "ValidPassword!@#"
        is_valid, error = AuthService.validate_password_strength(password)

        assert is_valid is False
        assert "number" in error

    def test_validate_password_strength_no_special(self):
        """Test password strength validation without special character."""
        password = "ValidPassword123"
        is_valid, error = AuthService.validate_password_strength(password)

        assert is_valid is False
        assert "special character" in error


class TestUserManagement:
    """Test user creation and management."""

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """Test successful user creation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        user_data = {
            "email": "test@example.com",
            "password": "ValidPassword123!",
            "name": "Test User",
        }

        # Mock database to return no existing user
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.add = MagicMock()  # add() is synchronous in AsyncSession
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            patch.object(AuthService, "create_audit_log", new_callable=AsyncMock) as mock_audit,
        ):
            result = await AuthService.create_user(mock_db, **user_data)

            # Verify user was created successfully
            assert result is not None
            assert result.email == user_data["email"]
            assert result.first_name == user_data["name"]

            # Verify database operations
            mock_db.execute.assert_called_once()
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
            mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_email_exists(self):
        """Test user creation with existing email."""
        mock_db = AsyncMock()

        user_data = {
            "email": "existing@example.com",
            "password": "ValidPassword123!",
            "name": "Test User",
        }

        # Mock database to return existing user
        mock_existing_user = MagicMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_existing_user
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        # Import the actual exception type
        from app.exceptions import ConflictError

        with pytest.raises(ConflictError, match="User with this email already exists"):
            await AuthService.create_user(mock_db, **user_data)

    @pytest.mark.asyncio
    async def test_create_user_weak_password(self):
        """Test user creation with weak password."""
        mock_db = AsyncMock()

        user_data = {"email": "test@example.com", "password": "weak", "name": "Test User"}

        with pytest.raises(ValueError, match="Password must be"):
            await AuthService.create_user(mock_db, **user_data)

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self):
        """Test successful user authentication."""
        mock_db = AsyncMock()

        email = "test@example.com"
        password = "ValidPassword123!"
        hashed_password = AuthService.hash_password(password)

        mock_user = MagicMock()
        mock_user.email = email
        mock_user.password_hash = hashed_password
        mock_user.is_active = True
        mock_user.is_suspended = False
        mock_user.id = "user_123"
        mock_user.tenant_id = "tenant_123"

        # Mock database to return the user
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.commit = AsyncMock()

        # Mock the audit log creation
        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            result = await AuthService.authenticate_user(mock_db, email, password)

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self):
        """Test authentication with non-existent user."""
        mock_db = AsyncMock()

        # Mock database to return no user
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        result = await AuthService.authenticate_user(mock_db, "nonexistent@example.com", "password")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password."""
        mock_db = AsyncMock()

        email = "test@example.com"
        correct_password = "ValidPassword123!"
        wrong_password = "WrongPassword123!"
        hashed_password = AuthService.hash_password(correct_password)

        mock_user = MagicMock()
        mock_user.email = email
        mock_user.password_hash = hashed_password
        mock_user.is_active = True
        mock_user.is_suspended = False
        mock_user.id = "user_123"
        mock_user.tenant_id = "tenant_123"

        # Mock database to return the user
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        # Mock the audit log creation
        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            result = await AuthService.authenticate_user(mock_db, email, wrong_password)
            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self):
        """Test authentication with inactive user."""
        mock_db = AsyncMock()

        email = "test@example.com"
        password = "ValidPassword123!"
        hashed_password = AuthService.hash_password(password)

        mock_user = MagicMock()
        mock_user.email = email
        mock_user.password_hash = hashed_password
        mock_user.is_active = False
        mock_user.is_suspended = False
        mock_user.id = "user_123"
        mock_user.tenant_id = "tenant_123"

        # Mock database to return the user
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        result = await AuthService.authenticate_user(mock_db, email, password)
        assert result is None


class TestSessionManagement:
    """Test session creation and management."""

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = UUID("12345678-1234-5678-9012-123456789abc")
        mock_user.tenant_id = UUID("87654321-4321-8765-2109-876543210def")

        # Mock db.execute to return empty session list (no existing sessions)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []  # No existing sessions
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        # Track what gets added to db
        added_session = None

        def capture_add(obj):
            nonlocal added_session
            added_session = obj

        mock_db.add = MagicMock(side_effect=capture_add)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock the dependencies (don't mock Session class - let it be created normally)
        with (
            patch("app.services.auth_service.get_redis", new_callable=AsyncMock) as mock_get_redis,
            patch("app.services.auth_service.SessionStore") as mock_session_store_class,
            patch.object(AuthService, "create_access_token") as mock_create_access,
            patch.object(AuthService, "create_refresh_token") as mock_create_refresh,
        ):
            mock_get_redis.return_value = mock_redis
            mock_session_store = MagicMock()
            mock_session_store.set = AsyncMock()
            mock_session_store_class.return_value = mock_session_store

            # Mock token creation
            mock_create_access.return_value = (
                "access_token_123",
                "access_jti_123",
                datetime.utcnow() + timedelta(hours=1),
            )
            mock_create_refresh.return_value = (
                "refresh_token_123",
                "refresh_jti_123",
                "family_123",
                datetime.utcnow() + timedelta(days=30),
            )

            access_token, refresh_token, session = await AuthService.create_session(
                mock_db, mock_user, ip_address="127.0.0.1", user_agent="test-agent"
            )

            assert access_token == "access_token_123"
            assert refresh_token == "refresh_token_123"
            assert session is not None
            assert session.user_id == mock_user.id
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_session_success(self):
        """Test successful session refresh."""
        # Create mock objects
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Create test data
        user_id = uuid4()
        tenant_id = uuid4()
        refresh_token = "valid_refresh_token"
        refresh_jti = "refresh_jti_123"
        family = "family_123"

        # Mock token payload from verify_token
        token_payload = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "jti": refresh_jti,
            "family": family,
            "type": "refresh",
        }

        # Mock session from database
        mock_session = MagicMock()
        mock_session.id = uuid4()
        mock_session.refresh_token_jti = refresh_jti
        mock_session.is_active = True
        mock_session.user_id = user_id

        # Mock user from database
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.tenant_id = tenant_id
        mock_user.is_active = True

        # Mock db.execute() for session lookup
        # db.execute() returns an awaitable that has .scalar_one_or_none() method
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_execute_result

        # Mock db.get() for user lookup
        mock_db.get.return_value = mock_user

        # Mock new token creation
        new_access_expires = datetime.utcnow() + timedelta(hours=1)
        new_refresh_expires = datetime.utcnow() + timedelta(days=30)

        with (
            patch.object(AuthService, "verify_token", new=AsyncMock(return_value=token_payload)),
            patch.object(
                AuthService,
                "create_access_token",
                return_value=("new_access_token", "new_access_jti", new_access_expires),
            ),
            patch.object(
                AuthService,
                "create_refresh_token",
                return_value=("new_refresh_token", "new_refresh_jti", family, new_refresh_expires),
            ),
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
        ):
            # Execute refresh
            result = await AuthService.refresh_tokens(mock_db, refresh_token)

            # Verify results
            assert result is not None
            assert result[0] == "new_access_token"
            assert result[1] == "new_refresh_token"

            # Verify session was updated
            assert mock_session.access_token_jti == "new_access_jti"
            assert mock_session.refresh_token_jti == "new_refresh_jti"

            # Verify old token was blacklisted
            mock_redis.set.assert_called_once()

            # Verify database commit
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_session_invalid_token(self):
        """Test session refresh with invalid token."""
        mock_db = AsyncMock()

        # Mock verify_token returning None for invalid token
        with patch.object(AuthService, "verify_token", new=AsyncMock(return_value=None)):
            result = await AuthService.refresh_tokens(mock_db, "invalid_token")

            # Should return None for invalid token
            assert result is None

    @pytest.mark.asyncio
    async def test_revoke_session_success(self):
        """Test successful session revocation (logout)."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        session_id = uuid4()
        user_id = uuid4()

        # Mock session with user relationship
        mock_user = MagicMock()
        mock_user.tenant_id = uuid4()

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session.is_active = True
        mock_session.access_token_jti = "access_jti"
        mock_session.refresh_token_jti = "refresh_jti"
        mock_session.user = mock_user

        # Mock db.get() for session lookup
        mock_db.get.return_value = mock_session

        # Mock Redis and SessionStore
        mock_session_store = AsyncMock()

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            patch("app.services.auth_service.SessionStore", return_value=mock_session_store),
            patch.object(AuthService, "create_audit_log", new=AsyncMock()),
        ):
            result = await AuthService.logout(mock_db, session_id, user_id)

            assert result is True
            assert mock_session.is_active is False
            assert mock_session.revoked_reason == "user_logout"

            # Verify Redis blacklisting
            assert mock_redis.set.call_count == 2

            # Verify session store deletion
            mock_session_store.delete.assert_called_once_with(str(session_id))

            # Verify database commit
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(self):
        """Test session revocation with non-existent session."""
        mock_db = AsyncMock()

        session_id = uuid4()
        user_id = uuid4()

        # Mock db.get() returning None (session not found)
        mock_db.get.return_value = None

        result = await AuthService.logout(mock_db, session_id, user_id)

        # Should return False when session not found
        assert result is False


class TestTokenGeneration:
    """Test token generation and validation."""

    def test_generate_access_token(self):
        """Test access token generation."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Call actual method (no mocking needed - pure function)
        token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        # Verify return types
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(expires_at, datetime)

        # Verify token is valid JWT
        assert len(token.split(".")) == 3  # JWT has 3 parts

        # Verify JTI is sufficiently long
        assert len(jti) >= 32

        # Verify expiration is in the future
        assert expires_at > datetime.utcnow()

    def test_generate_refresh_token(self):
        """Test refresh token generation."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Call actual method (no mocking needed - pure function)
        token, jti, family, expires_at = AuthService.create_refresh_token(user_id, tenant_id)

        # Verify return types
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(family, str)
        assert isinstance(expires_at, datetime)

        # Verify token is valid JWT
        assert len(token.split(".")) == 3  # JWT has 3 parts

        # Verify JTI and family are sufficiently long
        assert len(jti) >= 32
        assert len(family) >= 32

        # Verify expiration is in the future
        assert expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_validate_access_token_valid(self):
        """Test access token validation with valid token."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create a real token
        token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        # Mock Redis (needed for blacklist check)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Not blacklisted

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            # Verify the token we just created
            payload = await AuthService.verify_token(token, token_type="access")

            assert payload is not None
            assert payload["sub"] == user_id
            assert payload["tid"] == tenant_id
            assert payload["type"] == "access"
            assert payload["jti"] == jti

    @pytest.mark.asyncio
    async def test_validate_access_token_invalid(self):
        """Test access token validation with invalid token."""
        token = "completely.invalid.token"

        # Mock Redis
        mock_redis = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            # Invalid token should return None (not raise exception)
            payload = await AuthService.verify_token(token, token_type="access")

            assert payload is None

    @pytest.mark.asyncio
    async def test_validate_access_token_expired(self):
        """Test access token validation with expired token."""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Create a token that's already expired
        with patch("app.services.auth_service.settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES", -1):
            token, jti, expires_at = AuthService.create_access_token(user_id, tenant_id)

        # Mock Redis
        mock_redis = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            # Expired token should return None
            payload = await AuthService.verify_token(token, token_type="access")

            assert payload is None
