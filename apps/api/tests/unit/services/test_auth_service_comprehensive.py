"""
Comprehensive Auth Service Test Suite - Targeting 80%+ Coverage
Tests user creation, authentication, session management, and security features
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.exceptions import ConflictError
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


class TestPasswordManagement:
    """Test password hashing, verification, and validation"""

    def test_hash_password_creates_unique_hashes(self):
        """Test that same password creates different hashes (salt)"""
        password = "TestPassword123!"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2  # Different salts
        assert hash1 != password
        assert AuthService.verify_password(password, hash1)
        assert AuthService.verify_password(password, hash2)

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "CorrectPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "CorrectPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(wrong_password, hashed) is False

    def test_validate_password_strength_valid(self):
        """Test password validation accepts strong passwords"""
        valid_passwords = ["StrongPass123!", "MyP@ssw0rd2024", "Secur1ty!Rules", "C0mpl3x#P@ssword"]

        for password in valid_passwords:
            is_valid, error = AuthService.validate_password_strength(password)
            assert is_valid is True, f"Password '{password}' should be valid"
            assert error is None

    def test_validate_password_too_short(self):
        """Test password validation rejects short passwords"""
        is_valid, error = AuthService.validate_password_strength("Short1!")
        assert is_valid is False
        assert "12 characters" in error

    def test_validate_password_no_uppercase(self):
        """Test password validation rejects passwords without uppercase"""
        is_valid, error = AuthService.validate_password_strength("lowercase123!")
        assert is_valid is False
        assert "uppercase" in error

    def test_validate_password_no_lowercase(self):
        """Test password validation rejects passwords without lowercase"""
        is_valid, error = AuthService.validate_password_strength("UPPERCASE123!")
        assert is_valid is False
        assert "lowercase" in error

    def test_validate_password_no_number(self):
        """Test password validation rejects passwords without numbers"""
        is_valid, error = AuthService.validate_password_strength("NoNumbers!@#")
        assert is_valid is False
        assert "number" in error

    def test_validate_password_no_special(self):
        """Test password validation rejects passwords without special chars"""
        is_valid, error = AuthService.validate_password_strength("NoSpecial123")
        assert is_valid is False
        assert "special character" in error


class TestUserCreation:
    """Test user creation functionality"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = Mock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    async def test_create_user_success(self, mock_db):
        """Test successful user creation"""
        # Mock no existing user
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            _user = await AuthService.create_user(
                db=mock_db,
                email="newuser@example.com",
                password="StrongPass123!",
                name="New User",
                tenant_id=uuid4(),
            )

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    async def test_create_user_weak_password(self, mock_db):
        """Test user creation fails with weak password"""
        with pytest.raises(ValueError) as exc_info:
            await AuthService.create_user(
                db=mock_db, email="user@example.com", password="weak", name="User"
            )

        assert "12 characters" in str(exc_info.value)

    async def test_create_user_duplicate_email(self, mock_db):
        """Test user creation fails with duplicate email"""
        # Mock existing user found
        mock_existing_user = Mock()
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_existing_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ConflictError) as exc_info:
            await AuthService.create_user(
                db=mock_db, email="existing@example.com", password="StrongPass123!", name="User"
            )

        assert "already exists" in str(exc_info.value)

    async def test_create_user_with_default_tenant(self, mock_db):
        """Test user creation creates default tenant when not provided"""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            _user = await AuthService.create_user(
                db=mock_db,
                email="user@example.com",
                password="StrongPass123!",
                name="User",
                # No tenant_id provided
            )

        assert mock_db.add.called


class TestUserAuthentication:
    """Test user authentication functionality"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.password_hash = AuthService.hash_password("CorrectPass123!")
        user.is_active = True
        user.is_suspended = False
        user.tenant_id = uuid4()
        user.last_login_at = None
        return user

    async def test_authenticate_user_success(self, mock_db, mock_user):
        """Test successful user authentication"""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            result = await AuthService.authenticate_user(
                db=mock_db, email="test@example.com", password="CorrectPass123!"
            )

        assert result is not None
        assert result.id == mock_user.id
        assert mock_db.commit.called

    async def test_authenticate_user_not_found(self, mock_db):
        """Test authentication fails when user not found"""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate_user(
            db=mock_db, email="notfound@example.com", password="AnyPassword123!"
        )

        assert result is None

    async def test_authenticate_user_inactive(self, mock_db, mock_user):
        """Test authentication fails for inactive user"""
        mock_user.is_active = False
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate_user(
            db=mock_db, email="test@example.com", password="CorrectPass123!"
        )

        assert result is None

    async def test_authenticate_user_suspended(self, mock_db, mock_user):
        """Test authentication fails for suspended user"""
        mock_user.is_suspended = True
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate_user(
            db=mock_db, email="test@example.com", password="CorrectPass123!"
        )

        assert result is None

    async def test_authenticate_user_wrong_password(self, mock_db, mock_user):
        """Test authentication fails with wrong password"""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock) as mock_audit:
            result = await AuthService.authenticate_user(
                db=mock_db, email="test@example.com", password="WrongPassword123!"
            )

        assert result is None
        # Verify failed login was logged
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["event_type"] == "login_failed"


class TestTokenCreation:
    """Test JWT token creation"""

    def test_create_access_token(self):
        """Test access token creation"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        token, jti, expires_at = AuthService.create_access_token(
            user_id=user_id, tenant_id=tenant_id
        )

        assert isinstance(token, str)
        assert len(token) > 0
        assert isinstance(jti, str)
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.utcnow()

    def test_create_access_token_with_organization(self):
        """Test access token with organization context"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        org_id = str(uuid4())

        token, jti, expires_at = AuthService.create_access_token(
            user_id=user_id, tenant_id=tenant_id, organization_id=org_id
        )

        assert isinstance(token, str)
        # Decode to verify organization is in payload
        from jose import jwt

        from app.config import settings

        decoded = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_aud": False}
        )
        assert decoded.get("org") == org_id

    def test_create_refresh_token(self):
        """Test refresh token creation"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        token, jti, family, expires_at = AuthService.create_refresh_token(
            user_id=user_id, tenant_id=tenant_id
        )

        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(family, str)
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.utcnow()

    def test_create_refresh_token_with_family(self):
        """Test refresh token with existing family"""
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        existing_family = "existing-family-id"

        token, jti, family, expires_at = AuthService.create_refresh_token(
            user_id=user_id, tenant_id=tenant_id, family=existing_family
        )

        assert family == existing_family


class TestSessionManagement:
    """Test session creation and management"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = Mock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = uuid4()
        user.tenant_id = uuid4()
        user.email = "test@example.com"
        return user

    async def test_create_session_success(self, mock_db, mock_user):
        """Test successful session creation"""
        with patch("app.services.auth_service.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_session_store = AsyncMock()
            mock_session_store.set = AsyncMock()
            mock_get_redis.return_value = mock_redis

            with patch("app.services.auth_service.SessionStore", return_value=mock_session_store):
                access_token, refresh_token, session = await AuthService.create_session(
                    db=mock_db,
                    user=mock_user,
                    ip_address="192.168.1.1",
                    user_agent="Mozilla/5.0",
                    device_name="Chrome on Windows",
                )

        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_session_store.set.called

    async def test_create_session_minimal(self, mock_db, mock_user):
        """Test session creation with minimal parameters"""
        with patch("app.services.auth_service.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_session_store = AsyncMock()
            mock_session_store.set = AsyncMock()
            mock_get_redis.return_value = mock_redis

            with patch("app.services.auth_service.SessionStore", return_value=mock_session_store):
                access_token, refresh_token, session = await AuthService.create_session(
                    db=mock_db,
                    user=mock_user,
                    # No optional parameters
                )

        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)


class TestAuditLogging:
    """Test audit log creation"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = Mock()
        db.commit = AsyncMock()
        return db

    async def test_create_audit_log(self, mock_db):
        """Test audit log creation"""
        user_id = uuid4()
        tenant_id = uuid4()

        # Mock the create_audit_log method to actually work
        with patch("app.services.auth_service.AuditLog") as mock_audit_log_class:
            mock_audit_instance = Mock()
            mock_audit_log_class.return_value = mock_audit_instance

            await AuthService.create_audit_log(
                db=mock_db,
                user_id=user_id,
                tenant_id=tenant_id,
                event_type="test_event",
                event_data={"key": "value"},
            )

        # Verify audit log was added
        assert mock_db.add.called or mock_audit_log_class.called
