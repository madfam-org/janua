"""
Unit tests for authentication router (v1 API)

Tests the endpoints defined in app.routers.v1.auth
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

# Import models from the correct v1 auth router module
from app.routers.v1.auth import (
    SignUpRequest,
    SignInRequest,
    RefreshTokenRequest,
    VerifyEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
    TokenResponse,
)

pytestmark = pytest.mark.asyncio


class TestRequestModels:
    """Test Pydantic request models."""

    def test_signup_request_valid(self):
        """Test valid signup request."""
        data = {
            "email": "test@example.com",
            "password": "SecurePassword123!",
            "first_name": "Test",
            "last_name": "User",
        }

        request = SignUpRequest(**data)

        assert request.email == "test@example.com"
        assert request.password == "SecurePassword123!"
        assert request.first_name == "Test"
        assert request.last_name == "User"

    def test_signup_request_invalid_email(self):
        """Test signup request with invalid email."""
        data = {"email": "invalid-email", "password": "SecurePassword123!"}

        with pytest.raises(ValueError):
            SignUpRequest(**data)

    def test_signup_request_short_password(self):
        """Test signup request with too short password."""
        data = {"email": "test@example.com", "password": "short"}

        with pytest.raises(ValueError):
            SignUpRequest(**data)

    def test_signin_request_valid(self):
        """Test valid signin request with email."""
        data = {"email": "test@example.com", "password": "password123"}

        request = SignInRequest(**data)

        assert request.email == "test@example.com"
        assert request.password == "password123"

    def test_signin_request_with_username(self):
        """Test valid signin request with username."""
        data = {"username": "testuser", "password": "password123"}

        request = SignInRequest(**data)

        assert request.username == "testuser"
        assert request.password == "password123"

    def test_signin_request_no_identifier(self):
        """Test signin request without email or username fails."""
        data = {"password": "password123"}

        with pytest.raises(ValueError):
            SignInRequest(**data)

    def test_refresh_token_request(self):
        """Test refresh token request."""
        data = {"refresh_token": "mock_refresh_token"}

        request = RefreshTokenRequest(**data)

        assert request.refresh_token == "mock_refresh_token"

    def test_verify_email_request(self):
        """Test verify email request."""
        data = {"token": "verification_token_123"}

        request = VerifyEmailRequest(**data)

        assert request.token == "verification_token_123"

    def test_forgot_password_request(self):
        """Test forgot password request."""
        data = {"email": "user@example.com"}

        request = ForgotPasswordRequest(**data)

        assert request.email == "user@example.com"

    def test_reset_password_request(self):
        """Test reset password request."""
        data = {"token": "reset_token_123", "new_password": "NewPassword123!"}

        request = ResetPasswordRequest(**data)

        assert request.token == "reset_token_123"
        assert request.new_password == "NewPassword123!"


class TestResponseModels:
    """Test Pydantic response models."""

    def test_user_response(self):
        """Test user response model."""
        data = {
            "id": "user_123",
            "email": "test@example.com",
            "email_verified": True,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "profile_image_url": None,
            "is_admin": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_sign_in_at": None,
        }

        response = UserResponse(**data)

        assert response.id == "user_123"
        assert response.email == "test@example.com"
        assert response.email_verified is True

    def test_token_response(self):
        """Test token response model."""
        data = {"access_token": "access_123", "refresh_token": "refresh_456", "expires_in": 3600}

        response = TokenResponse(**data)

        assert response.access_token == "access_123"
        assert response.refresh_token == "refresh_456"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600


class TestAuthEndpoints:
    """Test authentication endpoints with proper mocking."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user object."""
        user = MagicMock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.email_verified = True
        user.username = "testuser"
        user.first_name = "Test"
        user.last_name = "User"
        user.profile_image_url = None
        user.is_admin = False
        user.status = "ACTIVE"
        user.password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYuP7ZF.8Qi"
        user.created_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        user.last_sign_in_at = None
        return user

    @pytest.fixture
    def mock_tokens(self):
        """Mock token data."""
        return {
            "access_token": "mock_access_token_123",
            "refresh_token": "mock_refresh_token_456",
            "expires_in": 3600,
        }

    async def test_signup_endpoint_validation(self, test_client):
        """Test signup endpoint validates input correctly."""
        # Test with invalid email
        response = await test_client.post(
            "/api/v1/auth/signup",
            json={"email": "invalid", "password": "SecurePassword123!"},
        )
        assert response.status_code == 422

    async def test_signin_endpoint_validation(self, test_client):
        """Test signin endpoint validates input correctly."""
        # Test with missing credentials
        response = await test_client.post(
            "/api/v1/auth/signin",
            json={"password": "password123"},  # Missing email/username
        )
        assert response.status_code == 422

    async def test_refresh_endpoint_validation(self, test_client):
        """Test refresh endpoint validates input correctly."""
        # Test with missing refresh token
        response = await test_client.post(
            "/api/v1/auth/refresh",
            json={},
        )
        assert response.status_code == 422

    async def test_me_endpoint_requires_auth(self, test_client):
        """Test /me endpoint requires authentication."""
        response = await test_client.get("/api/v1/auth/me")

        # HTTPBearer returns 401 when no Authorization header
        assert response.status_code == 401

    async def test_signout_endpoint_requires_auth(self, test_client):
        """Test /signout endpoint requires authentication."""
        response = await test_client.post("/api/v1/auth/signout")

        # HTTPBearer returns 401 when no Authorization header
        assert response.status_code == 401

    async def test_password_forgot_validation(self, test_client):
        """Test password forgot endpoint validates email."""
        response = await test_client.post(
            "/api/v1/auth/password/forgot",
            json={"email": "invalid-email"},
        )
        assert response.status_code == 422

    async def test_password_reset_validation(self, test_client):
        """Test password reset endpoint validates input."""
        # Test with short password
        response = await test_client.post(
            "/api/v1/auth/password/reset",
            json={"token": "test", "new_password": "short"},
        )
        assert response.status_code == 422


class TestPasskeyEndpoints:
    """Test WebAuthn/Passkey endpoints (at /api/v1/passkeys)."""

    async def test_passkey_register_options_requires_auth(self, test_client):
        """Test passkey registration options requires authentication."""
        response = await test_client.post("/api/v1/passkeys/register/options")

        # HTTPBearer returns 401 when no Authorization header
        assert response.status_code == 401

    async def test_passkey_list_requires_auth(self, test_client):
        """Test passkey list requires authentication."""
        response = await test_client.get("/api/v1/passkeys/")

        # HTTPBearer returns 401 when no Authorization header
        assert response.status_code == 401


class TestAuthValidation:
    """Test authentication validation logic."""

    async def test_missing_authorization_header(self, test_client):
        """Test endpoint access without authorization header."""
        response = await test_client.get("/api/v1/auth/me")

        # HTTPBearer returns 401 for missing auth header
        assert response.status_code == 401

    async def test_invalid_json_payload(self, test_client):
        """Test endpoint with invalid JSON."""
        response = await test_client.post(
            "/api/v1/auth/signup",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    async def test_missing_required_fields(self, test_client):
        """Test endpoint with missing required fields."""
        # Missing password field
        incomplete_data = {"email": "test@example.com"}

        response = await test_client.post("/api/v1/auth/signup", json=incomplete_data)

        assert response.status_code == 422


class TestMagicLinkEndpoints:
    """Test magic link authentication endpoints."""

    async def test_magic_link_request_validation(self, test_client):
        """Test magic link request validates email."""
        response = await test_client.post(
            "/api/v1/auth/magic-link",
            json={"email": "invalid-email"},
        )
        assert response.status_code == 422

    async def test_magic_link_verify_validation(self, test_client):
        """Test magic link verify requires token."""
        response = await test_client.post(
            "/api/v1/auth/magic-link/verify",
            json={},
        )
        assert response.status_code == 422
