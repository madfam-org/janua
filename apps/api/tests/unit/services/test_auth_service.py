import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for AuthService
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from app.services.auth_service import AuthService
from app.models import User, Session, Organization
from app.exceptions import AuthenticationError, ValidationError


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
            "name": "Test User"
        }

        # Mock database to return no existing user
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.add = MagicMock()  # add() is synchronous in AsyncSession
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, 'create_audit_log', new_callable=AsyncMock) as mock_audit:

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
            "name": "Test User"
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
        
        user_data = {
            "email": "test@example.com",
            "password": "weak",
            "name": "Test User"
        }
        
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
        with patch.object(AuthService, 'create_audit_log', new_callable=AsyncMock):
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
        with patch.object(AuthService, 'create_audit_log', new_callable=AsyncMock):
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

        # Mock Session model
        mock_session = MagicMock()
        mock_session.id = UUID("12345678-1234-5678-9012-123456789012")

        # Mock the dependencies
        with patch('app.services.auth_service.get_redis', new_callable=AsyncMock) as mock_get_redis, \
             patch('app.services.auth_service.Session') as mock_session_class, \
             patch('app.services.auth_service.SessionStore') as mock_session_store_class, \
             patch.object(AuthService, 'create_access_token') as mock_create_access, \
             patch.object(AuthService, 'create_refresh_token') as mock_create_refresh:

            mock_get_redis.return_value = mock_redis
            mock_session_class.return_value = mock_session
            mock_session_store = MagicMock()
            mock_session_store.set = AsyncMock()
            mock_session_store_class.return_value = mock_session_store

            # Mock token creation
            mock_create_access.return_value = ("access_token_123", "access_jti_123", datetime.utcnow() + timedelta(hours=1))
            mock_create_refresh.return_value = ("refresh_token_123", "refresh_jti_123", "family_123", datetime.utcnow() + timedelta(days=30))

            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            access_token, refresh_token, session = await AuthService.create_session(
                mock_db, mock_user, ip_address="127.0.0.1", user_agent="test-agent"
            )

            assert access_token == "access_token_123"
            assert refresh_token == "refresh_token_123"
            assert session == mock_session
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_session_success(self):
        """Test successful session refresh."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        refresh_token = "valid_refresh_token"
        
        mock_session = MagicMock()
        mock_session.id = "session_123"
        mock_session.user_id = "user_123"
        mock_session.is_active = True
        mock_session.expires_at = datetime.utcnow() + timedelta(days=1)
        
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.is_active = True
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_get_session_by_refresh_token', return_value=mock_session), \
             patch.object(AuthService, '_get_user_by_id', return_value=mock_user), \
             patch.object(AuthService, '_generate_tokens') as mock_generate:
            
            mock_generate.return_value = ("new_access_token", "new_refresh_token")
            
            mock_db.commit = AsyncMock()
            
            access_token, refresh_token_result, session = await AuthService.refresh_session(mock_db, refresh_token)
            
            assert access_token == "new_access_token"
            assert refresh_token_result == "new_refresh_token"
            assert session == mock_session
    
    @pytest.mark.asyncio
    async def test_refresh_session_invalid_token(self):
        """Test session refresh with invalid token."""
        mock_db = AsyncMock()
        
        with patch.object(AuthService, '_get_session_by_refresh_token', return_value=None):
            with pytest.raises(AuthenticationError, match="Invalid refresh token"):
                await AuthService.refresh_session(mock_db, "invalid_token")
    
    @pytest.mark.asyncio
    async def test_revoke_session_success(self):
        """Test successful session revocation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        session_id = "session_123"
        
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.is_active = True
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_get_session_by_id', return_value=mock_session):
            
            mock_db.commit = AsyncMock()
            mock_redis.delete = AsyncMock()
            
            await AuthService.revoke_session(mock_db, session_id)
            
            assert mock_session.is_active is False
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_revoke_session_not_found(self):
        """Test session revocation with non-existent session."""
        mock_db = AsyncMock()
        
        with patch.object(AuthService, '_get_session_by_id', return_value=None):
            with pytest.raises(AuthenticationError, match="Session not found"):
                await AuthService.revoke_session(mock_db, "nonexistent_session")


class TestTokenGeneration:
    """Test token generation and validation."""
    
    def test_generate_access_token(self):
        """Test access token generation."""
        user_data = {
            "user_id": "user_123",
            "tenant_id": "tenant_123",
            "email": "test@example.com"
        }
        
        with patch('app.services.auth_service.jwt.encode') as mock_encode:
            mock_encode.return_value = "access_token_123"
            
            token = AuthService._generate_access_token(user_data)
            
            assert token == "access_token_123"
            mock_encode.assert_called_once()
            
            # Check that the payload includes required fields
            call_args = mock_encode.call_args[0]
            payload = call_args[0]
            
            assert payload["user_id"] == user_data["user_id"]
            assert payload["tenant_id"] == user_data["tenant_id"]
            assert payload["email"] == user_data["email"]
            assert "exp" in payload
            assert "iat" in payload
            assert "sub" in payload
    
    def test_generate_refresh_token(self):
        """Test refresh token generation."""
        token = AuthService._generate_refresh_token()
        
        assert isinstance(token, str)
        assert len(token) >= 32  # Should be sufficiently long
    
    def test_validate_access_token_valid(self):
        """Test access token validation with valid token."""
        token = "valid.jwt.token"
        expected_payload = {
            "user_id": "user_123",
            "tenant_id": "tenant_123",
            "email": "test@example.com",
            "exp": (datetime.utcnow() + timedelta(minutes=15)).timestamp()
        }
        
        with patch('app.services.auth_service.jwt.decode', return_value=expected_payload):
            payload = AuthService.validate_access_token(token)
            
            assert payload == expected_payload
    
    def test_validate_access_token_invalid(self):
        """Test access token validation with invalid token."""
        token = "invalid.jwt.token"
        
        with patch('app.services.auth_service.jwt.decode', side_effect=JWTError("Invalid token")):
            with pytest.raises(AuthenticationError, match="Invalid token"):
                AuthService.validate_access_token(token)
    
    def test_validate_access_token_expired(self):
        """Test access token validation with expired token."""
        token = "expired.jwt.token"
        
        with patch('app.services.auth_service.jwt.decode', side_effect=JWTError("Token has expired")):
            with pytest.raises(AuthenticationError, match="Token has expired"):
                AuthService.validate_access_token(token)


class TestEmailVerification:
    """Test email verification functionality."""
    
    @pytest.mark.asyncio
    async def test_send_verification_email_success(self):
        """Test successful verification email sending."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_generate_verification_token') as mock_gen_token, \
             patch.object(AuthService, '_send_email') as mock_send:
            
            mock_gen_token.return_value = "verification_token_123"
            mock_redis.setex = AsyncMock()
            
            await AuthService.send_verification_email(mock_db, mock_user)
            
            mock_gen_token.assert_called_once_with(mock_user.id)
            mock_redis.setex.assert_called_once()
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_email_success(self):
        """Test successful email verification."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        token = "valid_verification_token"
        user_id = "user_123"
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email_verified = False
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_decode_verification_token', return_value=user_id), \
             patch.object(AuthService, '_get_user_by_id', return_value=mock_user):
            
            mock_redis.get = AsyncMock(return_value=token.encode())
            mock_redis.delete = AsyncMock()
            mock_db.commit = AsyncMock()
            
            await AuthService.verify_email(mock_db, token)
            
            assert mock_user.email_verified is True
            mock_db.commit.assert_called_once()
            mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self):
        """Test email verification with invalid token."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        token = "invalid_token"
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            
            with pytest.raises(ValidationError, match="Invalid or expired verification token"):
                await AuthService.verify_email(mock_db, token)
    
    @pytest.mark.asyncio
    async def test_verify_email_already_verified(self):
        """Test email verification with already verified user."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        token = "valid_verification_token"
        user_id = "user_123"
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email_verified = True
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_decode_verification_token', return_value=user_id), \
             patch.object(AuthService, '_get_user_by_id', return_value=mock_user):
            
            mock_redis.get = AsyncMock(return_value=token.encode())
            
            with pytest.raises(ValidationError, match="Email already verified"):
                await AuthService.verify_email(mock_db, token)


class TestPasswordReset:
    """Test password reset functionality."""
    
    @pytest.mark.asyncio
    async def test_initiate_password_reset_success(self):
        """Test successful password reset initiation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        email = "test@example.com"
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.email = email
        mock_user.name = "Test User"
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_get_user_by_email', return_value=mock_user), \
             patch.object(AuthService, '_generate_reset_token') as mock_gen_token, \
             patch.object(AuthService, '_send_email') as mock_send:
            
            mock_gen_token.return_value = "reset_token_123"
            mock_redis.setex = AsyncMock()
            
            await AuthService.initiate_password_reset(mock_db, email)
            
            mock_gen_token.assert_called_once_with(mock_user.id)
            mock_redis.setex.assert_called_once()
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initiate_password_reset_user_not_found(self):
        """Test password reset initiation with non-existent user."""
        mock_db = AsyncMock()
        
        email = "nonexistent@example.com"
        
        with patch.object(AuthService, '_get_user_by_email', return_value=None):
            # Should not raise an error for security reasons
            await AuthService.initiate_password_reset(mock_db, email)
    
    @pytest.mark.asyncio
    async def test_reset_password_success(self):
        """Test successful password reset."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        token = "valid_reset_token"
        new_password = "NewValidPassword123!"
        user_id = "user_123"
        
        mock_user = MagicMock()
        mock_user.id = user_id
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_decode_reset_token', return_value=user_id), \
             patch.object(AuthService, '_get_user_by_id', return_value=mock_user), \
             patch.object(AuthService, 'hash_password') as mock_hash:
            
            mock_redis.get = AsyncMock(return_value=token.encode())
            mock_redis.delete = AsyncMock()
            mock_hash.return_value = "hashed_new_password"
            mock_db.commit = AsyncMock()
            
            await AuthService.reset_password(mock_db, token, new_password)
            
            assert mock_user.password_hash == "hashed_new_password"
            mock_db.commit.assert_called_once()
            mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self):
        """Test password reset with invalid token."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        token = "invalid_token"
        new_password = "NewValidPassword123!"
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis):
            mock_redis.get = AsyncMock(return_value=None)
            
            with pytest.raises(ValidationError, match="Invalid or expired reset token"):
                await AuthService.reset_password(mock_db, token, new_password)
    
    @pytest.mark.asyncio
    async def test_reset_password_weak_password(self):
        """Test password reset with weak password."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        token = "valid_reset_token"
        weak_password = "weak"
        user_id = "user_123"
        
        with patch('app.services.auth_service.get_redis', return_value=mock_redis), \
             patch.object(AuthService, '_decode_reset_token', return_value=user_id):
            
            mock_redis.get = AsyncMock(return_value=token.encode())
            
            with pytest.raises(ValidationError, match="Password must be"):
                await AuthService.reset_password(mock_db, token, weak_password)


class TestHelperMethods:
    """Test private helper methods."""
    
    @pytest.mark.asyncio
    async def test_check_email_exists_true(self):
        """Test email existence check when email exists."""
        mock_db = AsyncMock()
        email = "existing@example.com"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # User exists
        mock_db.execute.return_value = mock_result
        
        result = await AuthService._check_email_exists(mock_db, email)
        
        assert result is True
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_email_exists_false(self):
        """Test email existence check when email doesn't exist."""
        mock_db = AsyncMock()
        email = "nonexistent@example.com"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await AuthService._check_email_exists(mock_db, email)
        
        assert result is False
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self):
        """Test getting user by email when user exists."""
        mock_db = AsyncMock()
        email = "test@example.com"
        
        mock_user = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        result = await AuthService._get_user_by_email(mock_db, email)
        
        assert result == mock_user
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self):
        """Test getting user by email when user doesn't exist."""
        mock_db = AsyncMock()
        email = "nonexistent@example.com"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await AuthService._get_user_by_email(mock_db, email)
        
        assert result is None
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_tenant_success(self):
        """Test tenant creation."""
        mock_db = AsyncMock()
        
        mock_tenant = MagicMock()
        mock_tenant.id = "tenant_123"
        
        with patch('app.services.auth_service.Tenant', return_value=mock_tenant):
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            
            result = await AuthService._create_tenant(mock_db)
            
            assert result == mock_tenant
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()