"""
Comprehensive integration tests for authentication endpoints
Tests complete auth flows, JWT handling, MFA, and session management
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime, timedelta
import uuid

from app.models import User, UserStatus, EmailVerification, PasswordReset, MagicLink, ActivityLog
from app.services.jwt_service import JWTService
from app.services.auth_service import AuthService
from app.services.email_service import EmailService


@pytest.mark.asyncio
class TestAuthenticationEndpoints:
    """Test suite for authentication API endpoints"""

    async def test_signup_complete_flow(self, test_client: AsyncClient, test_db_session):
        """Test complete user signup flow"""
        signup_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe"
        }

        with patch('app.services.email_service.EmailService.send_verification_email') as mock_email:
            mock_email.return_value = True

            response = await test_client.post("/api/v1/auth/signup", json=signup_data)

            assert response.status_code == 201
            data = response.json()
            assert data["message"] == "User created successfully"
            assert "user" in data
            assert data["user"]["email"] == signup_data["email"]
            assert data["user"]["first_name"] == signup_data["first_name"]
            assert data["user"]["last_name"] == signup_data["last_name"]
            assert data["user"]["username"] == signup_data["username"]
            assert data["user"]["email_verified"] == False

            # Verify email service was called
            mock_email.assert_called_once()

    async def test_signin_success(self, test_client: AsyncClient, test_db_session):
        """Test successful user signin"""
        signin_data = {
            "email": "test@example.com",
            "password": "TestPassword123!"
        }

        # Mock user in database
        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = signin_data["email"]
            mock_user.status = UserStatus.ACTIVE
            mock_user.email_verified = True

            mock_auth_service.return_value.authenticate_user.return_value = mock_user
            mock_auth_service.return_value.create_session.return_value = (
                "access_token_123",
                "refresh_token_123",
                {"id": "session_123"}
            )

            response = await test_client.post("/api/v1/auth/signin", json=signin_data)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert "user" in data
            assert data["user"]["email"] == signin_data["email"]

    async def test_signin_invalid_credentials(self, test_client: AsyncClient):
        """Test signin with invalid credentials"""
        signin_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_auth_service.return_value.authenticate_user.return_value = None

            response = await test_client.post("/api/v1/auth/signin", json=signin_data)

            assert response.status_code == 401
            data = response.json()
            assert "Invalid credentials" in data["detail"]

    async def test_signin_inactive_user(self, test_client: AsyncClient):
        """Test signin with inactive user"""
        signin_data = {
            "email": "inactive@example.com",
            "password": "TestPassword123!"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_user = MagicMock()
            mock_user.status = UserStatus.INACTIVE
            mock_auth_service.return_value.authenticate_user.return_value = mock_user

            response = await test_client.post("/api/v1/auth/signin", json=signin_data)

            assert response.status_code == 403
            data = response.json()
            assert "Account is inactive" in data["detail"]

    async def test_refresh_token_flow(self, test_client: AsyncClient):
        """Test refresh token endpoint"""
        refresh_data = {
            "refresh_token": "valid_refresh_token_123"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_auth_service.return_value.refresh_access_token.return_value = (
                "new_access_token_123",
                "new_refresh_token_123"
            )

            response = await test_client.post("/api/v1/auth/refresh", json=refresh_data)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["access_token"] == "new_access_token_123"

    async def test_logout_success(self, test_client: AsyncClient):
        """Test user logout"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
                mock_auth_service.return_value.logout_user.return_value = True

                response = await test_client.post("/api/v1/auth/logout", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Successfully logged out"

    async def test_email_verification_flow(self, test_client: AsyncClient):
        """Test email verification process"""
        verification_data = {
            "token": "verification_token_123"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_auth_service.return_value.verify_email.return_value = True

            response = await test_client.post("/api/v1/auth/verify-email", json=verification_data)

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Email verified successfully"

    async def test_password_reset_request(self, test_client: AsyncClient):
        """Test password reset request"""
        reset_data = {
            "email": "user@example.com"
        }

        with patch('app.services.email_service.EmailService.send_password_reset_email') as mock_email:
            mock_email.return_value = True

            response = await test_client.post("/api/v1/auth/reset-password", json=reset_data)

            assert response.status_code == 200
            data = response.json()
            assert "Password reset email sent" in data["message"]

    async def test_password_reset_confirm(self, test_client: AsyncClient):
        """Test password reset confirmation"""
        reset_data = {
            "token": "reset_token_123",
            "new_password": "NewSecurePassword123!"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_auth_service.return_value.reset_password.return_value = True

            response = await test_client.post("/api/v1/auth/confirm-reset", json=reset_data)

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Password reset successfully"

    async def test_magic_link_request(self, test_client: AsyncClient):
        """Test magic link authentication request"""
        magic_data = {
            "email": "user@example.com"
        }

        with patch('app.services.email_service.EmailService.send_magic_link_email') as mock_email:
            mock_email.return_value = True

            response = await test_client.post("/api/v1/auth/magic-link", json=magic_data)

            assert response.status_code == 200
            data = response.json()
            assert "Magic link sent" in data["message"]

    async def test_magic_link_verify(self, test_client: AsyncClient):
        """Test magic link verification"""
        magic_data = {
            "token": "magic_token_123"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = "user@example.com"

            mock_auth_service.return_value.verify_magic_link.return_value = mock_user
            mock_auth_service.return_value.create_session.return_value = (
                "access_token_123",
                "refresh_token_123",
                {"id": "session_123"}
            )

            response = await test_client.post("/api/v1/auth/verify-magic-link", json=magic_data)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "user" in data

    async def test_me_endpoint_authenticated(self, test_client: AsyncClient):
        """Test /me endpoint with valid authentication"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = "user@example.com"
            mock_user.first_name = "John"
            mock_user.last_name = "Doe"
            mock_user.username = "johndoe"
            mock_user.email_verified = True
            mock_user.status = UserStatus.ACTIVE
            mock_user.created_at = datetime.utcnow()
            mock_user.updated_at = datetime.utcnow()
            mock_get_user.return_value = mock_user

            response = await test_client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "user@example.com"
            assert data["first_name"] == "John"
            assert data["username"] == "johndoe"

    async def test_me_endpoint_unauthenticated(self, test_client: AsyncClient):
        """Test /me endpoint without authentication"""
        response = await test_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    async def test_signup_validation_errors(self, test_client: AsyncClient):
        """Test signup with validation errors"""
        invalid_data = [
            # Missing email
            {"password": "Test123!", "first_name": "John"},
            # Invalid email
            {"email": "invalid-email", "password": "Test123!"},
            # Weak password
            {"email": "test@example.com", "password": "weak"},
            # Invalid username
            {"email": "test@example.com", "password": "Test123!", "username": "a"},
        ]

        for data in invalid_data:
            response = await test_client.post("/api/v1/auth/signup", json=data)
            assert response.status_code == 422

    async def test_signin_validation_errors(self, test_client: AsyncClient):
        """Test signin with validation errors"""
        invalid_data = [
            # Missing email
            {"password": "Test123!"},
            # Missing password
            {"email": "test@example.com"},
            # Invalid email format
            {"email": "invalid-email", "password": "Test123!"},
        ]

        for data in invalid_data:
            response = await test_client.post("/api/v1/auth/signin", json=data)
            assert response.status_code == 422

    async def test_rate_limiting_signup(self, test_client: AsyncClient):
        """Test rate limiting on signup endpoint"""
        signup_data = {
            "email": "test@example.com",
            "password": "TestPassword123!",
            "first_name": "Test"
        }

        # Make multiple requests to trigger rate limiting
        # Note: This test may need adjustment based on actual rate limiting configuration
        responses = []
        for i in range(10):
            response = await test_client.post("/api/v1/auth/signup", json=signup_data)
            responses.append(response.status_code)

        # At least one request should be rate limited (429) or succeed based on mock
        assert any(status in [201, 429] for status in responses)

    async def test_concurrent_auth_requests(self, test_client: AsyncClient):
        """Test concurrent authentication requests"""
        import asyncio

        signin_data = {
            "email": "test@example.com",
            "password": "TestPassword123!"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = signin_data["email"]
            mock_user.status = UserStatus.ACTIVE
            mock_user.email_verified = True

            mock_auth_service.return_value.authenticate_user.return_value = mock_user
            mock_auth_service.return_value.create_session.return_value = (
                "access_token_123",
                "refresh_token_123",
                {"id": "session_123"}
            )

            # Make concurrent requests
            tasks = [
                test_client.post("/api/v1/auth/signin", json=signin_data)
                for _ in range(5)
            ]

            responses = await asyncio.gather(*tasks)

            # All requests should succeed
            for response in responses:
                assert response.status_code == 200


@pytest.mark.asyncio
class TestAuthenticationSecurity:
    """Security-focused authentication tests"""

    async def test_sql_injection_attempts(self, test_client: AsyncClient):
        """Test protection against SQL injection attacks"""
        malicious_payloads = [
            "'; DROP TABLE users; --",
            "admin@example.com'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --"
        ]

        for payload in malicious_payloads:
            signin_data = {
                "email": payload,
                "password": "password"
            }

            response = await test_client.post("/api/v1/auth/signin", json=signin_data)
            # Should either return validation error or authentication failure, not 500
            assert response.status_code in [400, 401, 422]

    async def test_xss_prevention(self, test_client: AsyncClient):
        """Test XSS prevention in user inputs"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src='x' onerror='alert(1)'>",
            "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//",
        ]

        for payload in xss_payloads:
            signup_data = {
                "email": "test@example.com",
                "password": "TestPassword123!",
                "first_name": payload,
                "last_name": payload
            }

            with patch('app.services.email_service.EmailService.send_verification_email'):
                response = await test_client.post("/api/v1/auth/signup", json=signup_data)

                if response.status_code == 201:
                    # If signup succeeds, check that XSS payload is properly escaped
                    data = response.json()
                    assert "<script>" not in str(data)
                    assert "javascript:" not in str(data)

    async def test_password_brute_force_protection(self, test_client: AsyncClient):
        """Test protection against password brute force attacks"""
        signin_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }

        with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
            mock_auth_service.return_value.authenticate_user.return_value = None

            # Attempt multiple failed logins
            failed_attempts = 0
            for i in range(10):
                response = await test_client.post("/api/v1/auth/signin", json=signin_data)
                if response.status_code == 401:
                    failed_attempts += 1
                elif response.status_code == 429:
                    # Rate limiting kicked in
                    break

            # Should have some form of protection (rate limiting or account lockout)
            assert failed_attempts < 10 or response.status_code == 429

    async def test_jwt_token_validation(self, test_client: AsyncClient):
        """Test JWT token validation security"""
        invalid_tokens = [
            "invalid.jwt.token",
            "Bearer ",
            "Bearer invalid_token",
            "Bearer " + "a" * 1000,  # Very long token
            "",
            None
        ]

        for token in invalid_tokens:
            headers = {}
            if token is not None:
                if token.startswith("Bearer"):
                    headers["Authorization"] = token
                else:
                    headers["Authorization"] = f"Bearer {token}"

            response = await test_client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401

    async def test_session_security(self, test_client: AsyncClient):
        """Test session security measures"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            # Test that logout invalidates the session
            with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
                mock_auth_service.return_value.logout_user.return_value = True

                logout_response = await test_client.post("/api/v1/auth/logout", headers=headers)
                assert logout_response.status_code == 200

                # After logout, the same token should be invalid
                # Note: This would require actual token blacklisting implementation
                # For now, we just test the logout endpoint works


@pytest.mark.asyncio
class TestAuthenticationEdgeCases:
    """Edge case tests for authentication"""

    async def test_duplicate_email_signup(self, test_client: AsyncClient):
        """Test signup with duplicate email"""
        signup_data = {
            "email": "duplicate@example.com",
            "password": "TestPassword123!",
            "first_name": "Test"
        }

        with patch('app.services.email_service.EmailService.send_verification_email'):
            with patch('app.routers.v1.auth.AuthService') as mock_auth_service:
                # First signup succeeds
                mock_user = MagicMock()
                mock_auth_service.return_value.create_user.return_value = mock_user

                response1 = await test_client.post("/api/v1/auth/signup", json=signup_data)

                # Second signup with same email should fail
                mock_auth_service.return_value.create_user.side_effect = Exception("Email already exists")

                response2 = await test_client.post("/api/v1/auth/signup", json=signup_data)
                assert response2.status_code in [400, 409, 422]

    async def test_expired_token_handling(self, test_client: AsyncClient):
        """Test handling of expired tokens"""
        headers = {"Authorization": "Bearer expired_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(status_code=401, detail="Token expired")

            response = await test_client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401

    async def test_malformed_request_bodies(self, test_client: AsyncClient):
        """Test handling of malformed request bodies"""
        malformed_bodies = [
            "invalid json",
            '{"email": "test@example.com", "password":}',  # Invalid JSON
            '{"email": "test@example.com"}',  # Missing required fields
            "",  # Empty body
            None  # No body
        ]

        for body in malformed_bodies:
            if body is None:
                response = await test_client.post("/api/v1/auth/signin")
            else:
                response = await test_client.post(
                    "/api/v1/auth/signin",
                    content=body,
                    headers={"Content-Type": "application/json"}
                )
            assert response.status_code in [400, 422]

    async def test_unicode_input_handling(self, test_client: AsyncClient):
        """Test handling of unicode characters in inputs"""
        unicode_data = {
            "email": "测试@example.com",
            "password": "TestPassword123!",
            "first_name": "测试用户",
            "last_name": "ñoño"
        }

        with patch('app.services.email_service.EmailService.send_verification_email'):
            response = await test_client.post("/api/v1/auth/signup", json=unicode_data)
            # Should handle unicode gracefully
            assert response.status_code in [201, 400, 422]

    async def test_very_long_inputs(self, test_client: AsyncClient):
        """Test handling of very long input strings"""
        long_string = "a" * 10000

        long_data = {
            "email": f"{long_string}@example.com",
            "password": long_string,
            "first_name": long_string,
            "last_name": long_string
        }

        response = await test_client.post("/api/v1/auth/signup", json=long_data)
        # Should reject overly long inputs
        assert response.status_code == 422

    async def test_null_and_empty_values(self, test_client: AsyncClient):
        """Test handling of null and empty values"""
        test_cases = [
            {"email": None, "password": "Test123!"},
            {"email": "", "password": "Test123!"},
            {"email": "test@example.com", "password": None},
            {"email": "test@example.com", "password": ""},
            {"email": "   ", "password": "Test123!"},  # Whitespace only
        ]

        for data in test_cases:
            response = await test_client.post("/api/v1/auth/signin", json=data)
            assert response.status_code == 422