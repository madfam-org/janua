"""
Unit tests for authentication router
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.router import (
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
        data = {"email": "test@example.com", "password": "SecurePassword123!", "name": "Test User"}

        request = SignUpRequest(**data)

        assert request.email == "test@example.com"
        assert request.password == "SecurePassword123!"
        assert request.name == "Test User"
        assert request.tenant_id is None

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
        """Test valid signin request."""
        data = {"email": "test@example.com", "password": "password123"}

        request = SignInRequest(**data)

        assert request.email == "test@example.com"
        assert request.password == "password123"
        assert request.tenant_id is None

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
            "name": "Test User",
            "email_verified": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        response = UserResponse(**data)

        assert response.id == "user_123"
        assert response.email == "test@example.com"
        assert response.name == "Test User"
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
    """Test authentication endpoints."""

    async def test_auth_status_endpoint(self, test_client: AsyncClient):
        """Test auth status endpoint."""
        response = await test_client.get("/api/v1/auth/status")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "auth router working"
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
        assert "signup" in data["endpoints"]
        assert "signin" in data["endpoints"]

    async def test_signup_endpoint_success(self, test_client: AsyncClient, mock_redis):
        """Test successful user signup."""
        # Mock rate limiting
        mock_redis.get.return_value = None  # No existing rate limit
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        signup_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "name": "New User",
        }

        response = await test_client.post("/api/v1/auth/signup", json=signup_data)

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert data["email_verified"] is False
        assert "id" in data

    async def test_signup_rate_limited(self, test_client: AsyncClient, mock_redis):
        """Test signup with rate limiting."""
        # Mock rate limit exceeded
        mock_redis.get.return_value = "10"  # At limit

        signup_data = {"email": "test@example.com", "password": "SecurePassword123!"}

        response = await test_client.post("/api/v1/auth/signup", json=signup_data)

        assert response.status_code == 429
        data = response.json()
        assert "Too many signup attempts" in data["detail"]

    async def test_signin_endpoint_success(self, test_client: AsyncClient, mock_redis):
        """Test successful user signin."""
        # Mock rate limiting
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        signin_data = {"email": "test@example.com", "password": "admin123"}  # Mock password

        response = await test_client.post("/api/v1/auth/signin", json=signin_data)

        assert response.status_code == 200
        data = response.json()

        assert data["access_token"] == "mock_access_token_123"
        assert data["refresh_token"] == "mock_refresh_token_456"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_signin_invalid_password(self, test_client: AsyncClient, mock_redis):
        """Test signin with invalid password."""
        # Mock rate limiting
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        signin_data = {"email": "test@example.com", "password": "wrong_password"}

        response = await test_client.post("/api/v1/auth/signin", json=signin_data)

        assert response.status_code == 401
        data = response.json()
        assert "Invalid email or password" in data["detail"]

    async def test_signin_rate_limited(self, test_client: AsyncClient, mock_redis):
        """Test signin with rate limiting."""
        # Mock rate limit exceeded
        mock_redis.get.return_value = "15"  # Over limit

        signin_data = {"email": "test@example.com", "password": "admin123"}

        response = await test_client.post("/api/v1/auth/signin", json=signin_data)

        assert response.status_code == 429
        data = response.json()
        assert "Too many signin attempts" in data["detail"]

    async def test_signout_endpoint(self, test_client: AsyncClient, auth_headers):
        """Test user signout."""
        response = await test_client.post("/api/v1/auth/signout", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "Successfully signed out" in data["message"]

    async def test_refresh_token_endpoint(self, test_client: AsyncClient, mock_redis):
        """Test token refresh."""
        refresh_data = {"refresh_token": "mock_refresh_token"}

        response = await test_client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_get_current_user_endpoint(self, test_client: AsyncClient, auth_headers):
        """Test get current user."""
        response = await test_client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert "email" in data
        assert "name" in data
        assert "email_verified" in data

    async def test_verify_email_endpoint(self, test_client: AsyncClient):
        """Test email verification."""
        verify_data = {"token": "verification_token_123"}

        response = await test_client.post("/api/v1/auth/verify-email", json=verify_data)

        assert response.status_code == 200
        data = response.json()
        assert "Email verified successfully" in data["message"]

    async def test_forgot_password_endpoint(self, test_client: AsyncClient, mock_redis):
        """Test forgot password."""
        # Mock rate limiting
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        forgot_data = {"email": "user@example.com"}

        response = await test_client.post("/api/v1/auth/forgot-password", json=forgot_data)

        assert response.status_code == 200
        data = response.json()
        assert "Password reset email sent" in data["message"]

    async def test_forgot_password_rate_limited(self, test_client: AsyncClient, mock_redis):
        """Test forgot password with rate limiting."""
        # Mock rate limit exceeded
        mock_redis.get.return_value = "5"  # Over limit

        forgot_data = {"email": "user@example.com"}

        response = await test_client.post("/api/v1/auth/forgot-password", json=forgot_data)

        assert response.status_code == 429
        data = response.json()
        assert "Too many password reset requests" in data["detail"]

    async def test_reset_password_endpoint(self, test_client: AsyncClient):
        """Test password reset."""
        reset_data = {"token": "reset_token_123", "new_password": "NewSecurePassword123!"}

        response = await test_client.post("/api/v1/auth/reset-password", json=reset_data)

        assert response.status_code == 200
        data = response.json()
        assert "Password reset successfully" in data["message"]


class TestPasskeyEndpoints:
    """Test WebAuthn/Passkey endpoints."""

    async def test_passkey_register_options(self, test_client: AsyncClient, auth_headers):
        """Test passkey registration options."""
        response = await test_client.post(
            "/api/v1/auth/passkeys/register/options", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "challenge" in data
        assert "rp" in data
        assert "user" in data
        assert "timeout" in data

    async def test_passkey_register(self, test_client: AsyncClient, auth_headers):
        """Test passkey registration."""
        credential_data = {
            "id": "credential_id",
            "type": "public-key",
            "response": {
                "clientDataJSON": "mock_client_data",
                "attestationObject": "mock_attestation",
            },
        }

        response = await test_client.post(
            "/api/v1/auth/passkeys/register", json=credential_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "Passkey registered successfully" in data["message"]


class TestAuthValidation:
    """Test authentication validation logic."""

    async def test_missing_authorization_header(self, test_client: AsyncClient):
        """Test endpoint access without authorization header."""
        response = await test_client.get("/api/v1/auth/me")

        assert response.status_code == 403
        data = response.json()
        assert "Not authenticated" in data["detail"]

    async def test_invalid_json_payload(self, test_client: AsyncClient):
        """Test endpoint with invalid JSON."""
        response = await test_client.post(
            "/api/v1/auth/signup",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    async def test_missing_required_fields(self, test_client: AsyncClient):
        """Test endpoint with missing required fields."""
        # Missing password field
        incomplete_data = {"email": "test@example.com"}

        response = await test_client.post("/api/v1/auth/signup", json=incomplete_data)

        assert response.status_code == 422
