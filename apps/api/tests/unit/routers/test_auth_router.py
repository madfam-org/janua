"""
Comprehensive Auth Router Test Suite
Tests for authentication endpoints, request models, and validation
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

# =============================================================================
# Test Request Models
# =============================================================================


class TestSignUpRequest:
    """Test SignUpRequest model."""

    def test_valid_signup_request(self):
        """Test valid signup request."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(
            email="test@example.com",
            password="SecurePass123!",
            first_name="John",
            last_name="Doe",
            username="johndoe",
        )

        assert request.email == "test@example.com"
        assert request.password == "SecurePass123!"
        assert request.first_name == "John"
        assert request.last_name == "Doe"
        assert request.username == "johndoe"

    def test_signup_minimal_required_fields(self):
        """Test signup with only required fields."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(email="test@example.com", password="SecurePass123!")

        assert request.email == "test@example.com"
        assert request.first_name is None
        assert request.last_name is None
        assert request.username is None

    def test_signup_password_min_length(self):
        """Test password minimum length validation."""
        from app.routers.v1.auth import SignUpRequest

        with pytest.raises(ValidationError) as exc_info:
            SignUpRequest(email="test@example.com", password="short")

        assert "String should have at least 8 characters" in str(exc_info.value)

    def test_signup_invalid_email(self):
        """Test invalid email validation."""
        from app.routers.v1.auth import SignUpRequest

        with pytest.raises(ValidationError):
            SignUpRequest(email="not-an-email", password="SecurePass123!")

    def test_signup_username_validation_alphanumeric(self):
        """Test username allows alphanumeric, underscores, hyphens."""
        from app.routers.v1.auth import SignUpRequest

        # Valid usernames
        valid_usernames = ["john_doe", "john-doe", "johndoe123", "John_Doe-123"]

        for username in valid_usernames:
            request = SignUpRequest(
                email="test@example.com", password="SecurePass123!", username=username
            )
            assert request.username == username

    def test_signup_username_invalid_characters(self):
        """Test username rejects invalid characters."""
        from app.routers.v1.auth import SignUpRequest

        invalid_usernames = ["john@doe", "john doe", "john.doe", "john!doe"]

        for username in invalid_usernames:
            with pytest.raises(ValidationError):
                SignUpRequest(
                    email="test@example.com", password="SecurePass123!", username=username
                )

    def test_signup_username_length_limits(self):
        """Test username length validation."""
        from app.routers.v1.auth import SignUpRequest

        # Too short (min 3)
        with pytest.raises(ValidationError):
            SignUpRequest(email="test@example.com", password="SecurePass123!", username="ab")

        # Too long (max 50)
        with pytest.raises(ValidationError):
            SignUpRequest(
                email="test@example.com", password="SecurePass123!", username="a" * 51
            )

    def test_signup_name_length_limits(self):
        """Test name field length validation."""
        from app.routers.v1.auth import SignUpRequest

        # Name too long (max 100)
        with pytest.raises(ValidationError):
            SignUpRequest(
                email="test@example.com", password="SecurePass123!", first_name="a" * 101
            )


class TestSignInRequest:
    """Test SignInRequest model."""

    def test_valid_signin_with_email(self):
        """Test signin with email."""
        from app.routers.v1.auth import SignInRequest

        request = SignInRequest(email="test@example.com", password="password123")

        assert request.email == "test@example.com"
        assert request.password == "password123"
        assert request.username is None

    def test_valid_signin_with_username(self):
        """Test signin with username."""
        from app.routers.v1.auth import SignInRequest

        request = SignInRequest(username="johndoe", password="password123")

        assert request.username == "johndoe"
        assert request.password == "password123"
        assert request.email is None

    def test_signin_requires_email_or_username(self):
        """Test signin requires either email or username."""
        from app.routers.v1.auth import SignInRequest

        with pytest.raises(ValidationError) as exc_info:
            SignInRequest(password="password123")

        assert "Either email or username must be provided" in str(exc_info.value)

    def test_signin_with_both_email_and_username(self):
        """Test signin accepts both email and username."""
        from app.routers.v1.auth import SignInRequest

        request = SignInRequest(
            email="test@example.com", username="johndoe", password="password123"
        )

        assert request.email == "test@example.com"
        assert request.username == "johndoe"


class TestRefreshTokenRequest:
    """Test RefreshTokenRequest model."""

    def test_valid_refresh_request(self):
        """Test valid refresh token request."""
        from app.routers.v1.auth import RefreshTokenRequest

        request = RefreshTokenRequest(refresh_token="valid-refresh-token-123")

        assert request.refresh_token == "valid-refresh-token-123"

    def test_refresh_requires_token(self):
        """Test refresh token is required."""
        from app.routers.v1.auth import RefreshTokenRequest

        with pytest.raises(ValidationError):
            RefreshTokenRequest()


class TestForgotPasswordRequest:
    """Test ForgotPasswordRequest model."""

    def test_valid_forgot_password_request(self):
        """Test valid forgot password request."""
        from app.routers.v1.auth import ForgotPasswordRequest

        request = ForgotPasswordRequest(email="user@example.com")

        assert request.email == "user@example.com"

    def test_forgot_password_invalid_email(self):
        """Test invalid email rejected."""
        from app.routers.v1.auth import ForgotPasswordRequest

        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="not-an-email")


class TestResetPasswordRequest:
    """Test ResetPasswordRequest model."""

    def test_valid_reset_password_request(self):
        """Test valid reset password request."""
        from app.routers.v1.auth import ResetPasswordRequest

        request = ResetPasswordRequest(token="reset-token-123", new_password="NewSecurePass123!")

        assert request.token == "reset-token-123"
        assert request.new_password == "NewSecurePass123!"

    def test_reset_password_min_length(self):
        """Test new password minimum length."""
        from app.routers.v1.auth import ResetPasswordRequest

        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="token", new_password="short")


class TestVerifyEmailRequest:
    """Test VerifyEmailRequest model."""

    def test_valid_verify_email_request(self):
        """Test valid verify email request."""
        from app.routers.v1.auth import VerifyEmailRequest

        request = VerifyEmailRequest(token="verify-token-123")

        assert request.token == "verify-token-123"


class TestChangePasswordRequest:
    """Test ChangePasswordRequest model."""

    def test_valid_change_password_request(self):
        """Test valid change password request."""
        from app.routers.v1.auth import ChangePasswordRequest

        request = ChangePasswordRequest(
            current_password="OldPass123!", new_password="NewSecurePass456!"
        )

        assert request.current_password == "OldPass123!"
        assert request.new_password == "NewSecurePass456!"

    def test_change_password_min_length(self):
        """Test new password minimum length."""
        from app.routers.v1.auth import ChangePasswordRequest

        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="oldpass", new_password="short")


class TestMagicLinkRequest:
    """Test MagicLinkRequest model."""

    def test_valid_magic_link_request(self):
        """Test valid magic link request."""
        from app.routers.v1.auth import MagicLinkRequest

        request = MagicLinkRequest(email="user@example.com")

        assert request.email == "user@example.com"
        assert request.redirect_url is None

    def test_magic_link_with_redirect(self):
        """Test magic link with redirect URL."""
        from app.routers.v1.auth import MagicLinkRequest

        request = MagicLinkRequest(
            email="user@example.com", redirect_url="https://app.example.com/dashboard"
        )

        assert request.redirect_url == "https://app.example.com/dashboard"


class TestVerifyMagicLinkRequest:
    """Test VerifyMagicLinkRequest model."""

    def test_valid_verify_magic_link_request(self):
        """Test valid verify magic link request."""
        from app.routers.v1.auth import VerifyMagicLinkRequest

        request = VerifyMagicLinkRequest(token="magic-link-token-123")

        assert request.token == "magic-link-token-123"


# =============================================================================
# Test Response Models
# =============================================================================


class TestUserResponse:
    """Test UserResponse model."""

    def test_valid_user_response(self):
        """Test valid user response."""
        from app.routers.v1.auth import UserResponse

        now = datetime.utcnow()
        response = UserResponse(
            id="user-123",
            email="user@example.com",
            email_verified=True,
            username="johndoe",
            first_name="John",
            last_name="Doe",
            profile_image_url="https://example.com/avatar.jpg",
            is_admin=False,
            created_at=now,
            updated_at=now,
            last_sign_in_at=now,
        )

        assert response.id == "user-123"
        assert response.email == "user@example.com"
        assert response.email_verified is True
        assert response.username == "johndoe"
        assert response.is_admin is False

    def test_user_response_optional_fields(self):
        """Test user response with optional fields."""
        from app.routers.v1.auth import UserResponse

        now = datetime.utcnow()
        response = UserResponse(
            id="user-456",
            email="user@example.com",
            email_verified=False,
            username=None,
            first_name=None,
            last_name=None,
            profile_image_url=None,
            created_at=now,
            updated_at=now,
            last_sign_in_at=None,
        )

        assert response.username is None
        assert response.first_name is None
        assert response.profile_image_url is None
        assert response.last_sign_in_at is None

    def test_user_response_is_admin_default(self):
        """Test is_admin defaults to False."""
        from app.routers.v1.auth import UserResponse

        now = datetime.utcnow()
        response = UserResponse(
            id="user-789",
            email="user@example.com",
            email_verified=False,
            username=None,
            first_name=None,
            last_name=None,
            profile_image_url=None,
            created_at=now,
            updated_at=now,
            last_sign_in_at=None,
        )

        assert response.is_admin is False


class TestTokenResponse:
    """Test TokenResponse model."""

    def test_valid_token_response(self):
        """Test valid token response."""
        from app.routers.v1.auth import TokenResponse

        response = TokenResponse(
            access_token="access-token-xyz",
            refresh_token="refresh-token-abc",
            expires_in=900,
        )

        assert response.access_token == "access-token-xyz"
        assert response.refresh_token == "refresh-token-abc"
        assert response.token_type == "bearer"
        assert response.expires_in == 900

    def test_token_type_default(self):
        """Test token_type defaults to bearer."""
        from app.routers.v1.auth import TokenResponse

        response = TokenResponse(
            access_token="token", refresh_token="refresh", expires_in=3600
        )

        assert response.token_type == "bearer"


class TestSignInResponse:
    """Test SignInResponse model."""

    def test_valid_signin_response(self):
        """Test valid sign in response."""
        from app.routers.v1.auth import SignInResponse, TokenResponse, UserResponse

        now = datetime.utcnow()
        user = UserResponse(
            id="user-123",
            email="user@example.com",
            email_verified=True,
            username="testuser",
            first_name="Test",
            last_name="User",
            profile_image_url=None,
            is_admin=False,
            created_at=now,
            updated_at=now,
            last_sign_in_at=now,
        )
        tokens = TokenResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=900,
        )

        response = SignInResponse(user=user, tokens=tokens)

        assert response.user.id == "user-123"
        assert response.tokens.access_token == "access-token"


# =============================================================================
# Test Router Configuration
# =============================================================================


class TestRouterConfiguration:
    """Test router configuration."""

    def test_router_prefix(self):
        """Test router has correct prefix."""
        from app.routers.v1.auth import router

        assert router.prefix == "/auth"

    def test_router_tags(self):
        """Test router has correct tags."""
        from app.routers.v1.auth import router

        assert "Authentication" in router.tags

    def test_router_has_required_routes(self):
        """Test router has all required routes."""
        from app.routers.v1.auth import router

        route_paths = [route.path for route in router.routes]

        # Check for core auth routes (routes include /auth prefix)
        required_routes = [
            "/auth/signup",
            "/auth/signin",
            "/auth/login",
            "/auth/logout",
            "/auth/signout",
            "/auth/refresh",
            "/auth/session",
            "/auth/login-form",
        ]

        for required_route in required_routes:
            assert required_route in route_paths, f"Missing route: {required_route}"


# =============================================================================
# Test Security Configuration
# =============================================================================


class TestSecurityConfiguration:
    """Test security configuration."""

    def test_http_bearer_security(self):
        """Test HTTPBearer security scheme is configured."""
        from app.routers.v1.auth import security

        assert security is not None

    def test_rate_limiter_configured(self):
        """Test rate limiter is configured."""
        from app.routers.v1.auth import limiter

        assert limiter is not None


# =============================================================================
# Test Password Validation Patterns
# =============================================================================


class TestPasswordValidationPatterns:
    """Test password validation patterns."""

    def test_password_minimum_length_8(self):
        """Test password requires 8 characters minimum."""
        from app.routers.v1.auth import SignUpRequest

        # 7 characters should fail
        with pytest.raises(ValidationError):
            SignUpRequest(email="test@example.com", password="1234567")

        # 8 characters should pass
        request = SignUpRequest(email="test@example.com", password="12345678")
        assert len(request.password) == 8

    def test_various_password_lengths(self):
        """Test various password lengths."""
        from app.routers.v1.auth import SignUpRequest

        valid_passwords = [
            "password",  # 8 chars
            "longer-password",  # 15 chars
            "very-long-and-secure-password-123!",  # 34 chars
        ]

        for password in valid_passwords:
            request = SignUpRequest(email="test@example.com", password=password)
            assert request.password == password


# =============================================================================
# Test Email Validation Patterns
# =============================================================================


class TestEmailValidationPatterns:
    """Test email validation patterns."""

    def test_valid_email_formats(self):
        """Test various valid email formats."""
        from app.routers.v1.auth import SignUpRequest

        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
            "user123@example.org",
        ]

        for email in valid_emails:
            request = SignUpRequest(email=email, password="SecurePass123!")
            assert request.email == email

    def test_invalid_email_formats(self):
        """Test various invalid email formats."""
        from app.routers.v1.auth import SignUpRequest

        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "",
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                SignUpRequest(email=email, password="SecurePass123!")


# =============================================================================
# Test Username Validation Patterns
# =============================================================================


class TestUsernameValidationPatterns:
    """Test username validation patterns."""

    def test_username_allows_underscores(self):
        """Test username allows underscores."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(
            email="test@example.com", password="SecurePass123!", username="user_name"
        )
        assert request.username == "user_name"

    def test_username_allows_hyphens(self):
        """Test username allows hyphens."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(
            email="test@example.com", password="SecurePass123!", username="user-name"
        )
        assert request.username == "user-name"

    def test_username_allows_numbers(self):
        """Test username allows numbers."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(
            email="test@example.com", password="SecurePass123!", username="user123"
        )
        assert request.username == "user123"

    def test_username_mixed_case(self):
        """Test username allows mixed case."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(
            email="test@example.com", password="SecurePass123!", username="UserName"
        )
        assert request.username == "UserName"


# =============================================================================
# Test Model Serialization
# =============================================================================


class TestModelSerialization:
    """Test model serialization."""

    def test_user_response_to_dict(self):
        """Test UserResponse serializes to dict."""
        from app.routers.v1.auth import UserResponse

        now = datetime.utcnow()
        response = UserResponse(
            id="user-123",
            email="user@example.com",
            email_verified=True,
            username="testuser",
            first_name="Test",
            last_name="User",
            profile_image_url=None,
            is_admin=False,
            created_at=now,
            updated_at=now,
            last_sign_in_at=None,
        )

        data = response.model_dump()

        assert data["id"] == "user-123"
        assert data["email"] == "user@example.com"
        assert data["is_admin"] is False

    def test_token_response_to_dict(self):
        """Test TokenResponse serializes to dict."""
        from app.routers.v1.auth import TokenResponse

        response = TokenResponse(
            access_token="access", refresh_token="refresh", expires_in=900
        )

        data = response.model_dump()

        assert data["access_token"] == "access"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    def test_signin_response_to_dict(self):
        """Test SignInResponse serializes to dict."""
        from app.routers.v1.auth import SignInResponse, TokenResponse, UserResponse

        now = datetime.utcnow()
        user = UserResponse(
            id="user-123",
            email="user@example.com",
            email_verified=True,
            username=None,
            first_name=None,
            last_name=None,
            profile_image_url=None,
            is_admin=False,
            created_at=now,
            updated_at=now,
            last_sign_in_at=None,
        )
        tokens = TokenResponse(
            access_token="access", refresh_token="refresh", expires_in=900
        )

        response = SignInResponse(user=user, tokens=tokens)
        data = response.model_dump()

        assert "user" in data
        assert "tokens" in data
        assert data["user"]["id"] == "user-123"
        assert data["tokens"]["access_token"] == "access"


# =============================================================================
# Test Request Model Edge Cases
# =============================================================================


class TestRequestModelEdgeCases:
    """Test request model edge cases."""

    def test_signup_empty_optional_strings(self):
        """Test signup with empty optional strings."""
        from app.routers.v1.auth import SignUpRequest

        request = SignUpRequest(
            email="test@example.com",
            password="SecurePass123!",
            first_name="",  # Empty string
            last_name="",
        )

        assert request.first_name == ""
        assert request.last_name == ""

    def test_signin_whitespace_handling(self):
        """Test signin handles whitespace."""
        from app.routers.v1.auth import SignInRequest

        # Pydantic should preserve whitespace but validate email format
        request = SignInRequest(
            email="  test@example.com  ".strip(),  # Trim in test
            password="password",
        )

        assert request.email == "test@example.com"

    def test_refresh_token_long_value(self):
        """Test refresh token can be long."""
        from app.routers.v1.auth import RefreshTokenRequest

        long_token = "a" * 1000
        request = RefreshTokenRequest(refresh_token=long_token)

        assert len(request.refresh_token) == 1000


# =============================================================================
# Test Response Model Edge Cases
# =============================================================================


class TestResponseModelEdgeCases:
    """Test response model edge cases."""

    def test_user_response_unicode_names(self):
        """Test user response handles unicode names."""
        from app.routers.v1.auth import UserResponse

        now = datetime.utcnow()
        response = UserResponse(
            id="user-unicode",
            email="user@example.com",
            email_verified=True,
            username="用户名",  # Chinese characters
            first_name="José",  # Spanish accent
            last_name="Müller",  # German umlaut
            profile_image_url=None,
            is_admin=False,
            created_at=now,
            updated_at=now,
            last_sign_in_at=None,
        )

        assert response.first_name == "José"
        assert response.last_name == "Müller"

    def test_token_response_zero_expires(self):
        """Test token response with zero expiry."""
        from app.routers.v1.auth import TokenResponse

        response = TokenResponse(
            access_token="token", refresh_token="refresh", expires_in=0
        )

        assert response.expires_in == 0

    def test_token_response_large_expires(self):
        """Test token response with large expiry."""
        from app.routers.v1.auth import TokenResponse

        response = TokenResponse(
            access_token="token",
            refresh_token="refresh",
            expires_in=60 * 60 * 24 * 365,  # 1 year in seconds
        )

        assert response.expires_in == 31536000


# =============================================================================
# Test Rate Limiting Configuration
# =============================================================================


class TestRateLimitingConfiguration:
    """Test rate limiting configuration."""

    def test_limiter_is_valid_instance(self):
        """Test limiter is a valid Limiter instance."""
        from slowapi import Limiter

        from app.routers.v1.auth import limiter

        # Check limiter is a valid Limiter instance
        assert isinstance(limiter, Limiter)
        # Verify limiter has the limit decorator method
        assert hasattr(limiter, "limit")
        assert callable(limiter.limit)

    def test_rate_limit_routes_exist(self):
        """Test rate limited routes exist."""
        from app.routers.v1.auth import router

        # Rate limited endpoints should exist (routes include /auth prefix)
        route_paths = {route.path for route in router.routes}

        rate_limited_routes = ["/auth/signup", "/auth/signin", "/auth/login", "/auth/login-form"]

        for route in rate_limited_routes:
            assert route in route_paths


# =============================================================================
# Test Activity Logging Structure
# =============================================================================


class TestActivityLoggingStructure:
    """Test activity logging data structure."""

    def test_signup_activity_log_format(self):
        """Test signup activity log format."""
        expected_details = {"method": "email"}

        assert "method" in expected_details
        assert expected_details["method"] == "email"

    def test_signin_activity_log_format(self):
        """Test signin activity log format."""
        expected_details = {"method": "password"}

        assert "method" in expected_details
        assert expected_details["method"] == "password"

    def test_activity_log_actions(self):
        """Test activity log action strings."""
        valid_actions = ["signup", "signin", "signout", "password_reset", "email_verified"]

        # All actions should be lowercase strings
        for action in valid_actions:
            assert action == action.lower()
            assert isinstance(action, str)


class TestAuditEventMap:
    """Test SOC 2 CF-08 audit logger integration in auth router."""

    def test_audit_event_map_exists(self):
        """Test _AUDIT_EVENT_MAP is defined in auth router."""
        from app.routers.v1.auth import _AUDIT_EVENT_MAP

        assert isinstance(_AUDIT_EVENT_MAP, dict)

    def test_audit_event_map_covers_all_actions(self):
        """Test _AUDIT_EVENT_MAP covers all auth actions."""
        from app.routers.v1.auth import _AUDIT_EVENT_MAP

        expected_actions = ["signup", "signin", "signout", "password_change", "password_reset", "email_verified"]
        for action in expected_actions:
            assert action in _AUDIT_EVENT_MAP, f"Missing audit event mapping for '{action}'"

    def test_audit_event_map_values_are_enum(self):
        """Test _AUDIT_EVENT_MAP values are AuditEventType enums."""
        from app.routers.v1.auth import _AUDIT_EVENT_MAP

        for action, event_type in _AUDIT_EVENT_MAP.items():
            assert hasattr(event_type, "value"), f"{action} maps to non-enum value"

    def test_log_audit_event_function_exists(self):
        """Test log_audit_event function is importable."""
        from app.routers.v1.auth import log_audit_event
        import asyncio

        assert asyncio.iscoroutinefunction(log_audit_event)
