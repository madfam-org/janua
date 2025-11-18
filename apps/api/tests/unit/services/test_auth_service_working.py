import pytest

pytestmark = pytest.mark.asyncio


"""
Working tests for AuthService
"""

from unittest.mock import AsyncMock, Mock, patch

import bcrypt
import pytest

from app.services.auth_service import AuthService


class TestAuthServiceWorking:
    """Working auth service tests"""

    @pytest.fixture
    def auth_service(self):
        """Create auth service instance"""
        service = AuthService()
        service.db = AsyncMock()
        service.redis = AsyncMock()
        service.jwt_service = AsyncMock()
        return service

    def test_password_hashing(self, auth_service):
        """Test password hashing works"""
        password = "TestPassword123!"
        hashed = auth_service.hash_password(password)
        assert hashed != password
        assert auth_service.verify_password(password, hashed)

    def test_password_validation(self, auth_service):
        """Test password strength validation"""
        # Valid password
        is_valid, error = auth_service.validate_password_strength("ValidPass123!")
        assert is_valid == True
        assert error is None

        # Invalid passwords
        is_valid, error = auth_service.validate_password_strength("short")
        assert is_valid == False
        assert error is not None

        is_valid, error = auth_service.validate_password_strength("nouppercase123!")
        assert is_valid == False

        is_valid, error = auth_service.validate_password_strength("NOLOWERCASE123!")
        assert is_valid == False

        is_valid, error = auth_service.validate_password_strength("NoNumbers!")
        assert is_valid == False

        is_valid, error = auth_service.validate_password_strength("NoSpecial123")
        assert is_valid == False

    @pytest.mark.asyncio
    async def test_create_user_mock(self, auth_service):
        """Test user creation with mocks"""
        # Mock database response - properly mock the async execute result
        mock_execute_result = Mock()
        mock_execute_result.scalar_one_or_none = Mock(return_value=None)  # No existing user
        auth_service.db.execute = AsyncMock(return_value=mock_execute_result)
        auth_service.db.add = Mock()
        auth_service.db.commit = AsyncMock()
        auth_service.db.refresh = AsyncMock()

        # Mock audit log creation
        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            # Call create user
            result = await auth_service.create_user(
                db=auth_service.db,
                email="test@example.com",
                password="ValidPass123!",
                name="Test User",
            )

        assert result is not None
        assert auth_service.db.execute.called

    @pytest.mark.asyncio
    async def test_authenticate_user_mock(self, auth_service):
        """Test user authentication with mocks"""
        # Mock user data - use Mock not AsyncMock for synchronous attribute access
        mock_user = Mock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.password_hash = AuthService.hash_password("ValidPass123!")
        mock_user.is_active = True
        mock_user.is_suspended = False
        mock_user.tenant_id = "tenant123"

        # Properly mock the async execute result
        mock_execute_result = Mock()
        mock_execute_result.scalar_one_or_none = Mock(return_value=mock_user)
        auth_service.db.execute = AsyncMock(return_value=mock_execute_result)
        auth_service.db.commit = AsyncMock()

        # Mock audit log creation
        with patch.object(AuthService, "create_audit_log", new_callable=AsyncMock):
            # Authenticate
            result = await auth_service.authenticate_user(
                db=auth_service.db, email="test@example.com", password="ValidPass123!"
            )

        assert result is not None
        assert result.id == "user123"
