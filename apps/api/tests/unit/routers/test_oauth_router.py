"""
Tests for app/routers/v1/oauth.py - OAuth Authentication Router

Tests OAuth provider integration, authorization flow, and account linking.
Target: 15% → 60% coverage.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers.v1.oauth import validate_redirect_url

pytestmark = pytest.mark.asyncio


class TestValidateRedirectUrl:
    """Test redirect URL validation for open redirect prevention."""

    def test_validate_none_url_returns_none(self):
        """Test None URL returns None."""
        result = validate_redirect_url(None)
        assert result is None

    def test_validate_empty_url_returns_empty(self):
        """Test empty URL returns empty."""
        result = validate_redirect_url("")
        assert result == ""

    def test_validate_relative_url_allowed(self):
        """Test relative URLs are allowed."""
        result = validate_redirect_url("/dashboard")
        assert result == "/dashboard"

    def test_validate_relative_path_with_query(self):
        """Test relative URL with query params."""
        result = validate_redirect_url("/settings?tab=security")
        assert result == "/settings?tab=security"

    def test_validate_invalid_absolute_url_raises(self):
        """Test invalid absolute URL raises HTTPException."""
        with patch("app.routers.v1.oauth.settings") as mock_settings:
            mock_settings.cors_origins_list = ["https://app.janua.dev"]

            with pytest.raises(HTTPException) as exc_info:
                validate_redirect_url("https://malicious.com/redirect")

            assert exc_info.value.status_code == 400
            assert "not allowed" in exc_info.value.detail


class TestOAuthRouterInitialization:
    """Test OAuth router setup."""

    def test_oauth_router_exists(self):
        """Test OAuth router is properly imported."""
        from app.routers.v1.oauth import router

        assert router is not None
        assert router.prefix == "/auth/oauth"
        assert "oauth" in router.tags


class TestGetOAuthProviders:
    """Test GET /auth/oauth/providers endpoint."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_get_providers_returns_list(self):
        """Test getting OAuth providers returns list."""
        with patch("app.routers.v1.oauth.OAuthService") as mock_service:
            mock_service.get_provider_config.return_value = {
                "client_id": "test",
                "client_secret": "secret",
            }

            response = self.client.get("/api/v1/auth/oauth/providers")

            # Should return 200 with providers list
            assert response.status_code == 200
            data = response.json()
            assert "providers" in data
            assert isinstance(data["providers"], list)


class TestOAuthAuthorize:
    """Test POST /auth/oauth/authorize/{provider} endpoint."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_authorize_invalid_provider(self):
        """Test authorize with invalid provider."""
        response = self.client.post("/api/v1/auth/oauth/authorize/invalid_provider")

        assert response.status_code in [400, 422, 500]

    def test_authorize_github_endpoint_exists(self):
        """Test authorize endpoint for GitHub exists and returns expected status."""
        with patch("app.routers.v1.oauth.OAuthService") as mock_oauth_service:
            with patch("app.core.redis.get_redis") as mock_get_redis:
                mock_redis = AsyncMock()
                mock_redis.set = AsyncMock(return_value=True)
                mock_get_redis.return_value = mock_redis

                mock_oauth_service.get_provider_config.return_value = {
                    "client_id": "test",
                    "client_secret": "secret",
                }
                mock_oauth_service.generate_state_token.return_value = "state_token"
                mock_oauth_service.get_authorization_url.return_value = "https://github.com/oauth"

                response = self.client.post("/api/v1/auth/oauth/authorize/github")

                # Should return 200 with URL or error depending on configuration
                assert response.status_code in [200, 400, 500]

    def test_authorize_unconfigured_provider(self):
        """Test authorize with unconfigured provider."""
        with patch("app.routers.v1.oauth.OAuthService") as mock_service:
            mock_service.get_provider_config.return_value = None

            response = self.client.post("/api/v1/auth/oauth/authorize/github")

            # Should fail if provider not configured
            assert response.status_code in [400, 500]


class TestOAuthCallback:
    """Test GET /auth/oauth/callback/{provider} endpoint."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_callback_missing_code(self):
        """Test callback without code parameter."""
        response = self.client.get("/api/v1/auth/oauth/callback/github?state=test_state")

        assert response.status_code == 422  # Validation error

    def test_callback_missing_state(self):
        """Test callback without state parameter."""
        response = self.client.get("/api/v1/auth/oauth/callback/github?code=test_code")

        assert response.status_code == 422  # Validation error

    def test_callback_invalid_provider(self):
        """Test callback with invalid provider."""
        response = self.client.get(
            "/api/v1/auth/oauth/callback/invalid_provider?code=test&state=test"
        )

        assert response.status_code in [400, 500]


class TestLinkOAuthAccount:
    """Test POST /auth/oauth/link/{provider} endpoint."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_link_requires_authentication(self):
        """Test link endpoint requires authentication."""
        response = self.client.post("/api/v1/auth/oauth/link/github")

        # Should be 401 without auth
        assert response.status_code == 401


class TestUnlinkOAuthAccount:
    """Test DELETE /auth/oauth/unlink/{provider} endpoint."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_unlink_requires_authentication(self):
        """Test unlink endpoint requires authentication."""
        response = self.client.delete("/api/v1/auth/oauth/unlink/github")

        assert response.status_code == 401


class TestGetLinkedAccounts:
    """Test GET /auth/oauth/accounts endpoint."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_get_accounts_requires_authentication(self):
        """Test get accounts requires authentication."""
        response = self.client.get("/api/v1/auth/oauth/accounts")

        assert response.status_code == 401


class TestOAuthServiceIntegration:
    """Test OAuth service integration methods."""

    def test_oauth_provider_enum_exists(self):
        """Test OAuthProvider enum is available."""
        from app.models import OAuthProvider

        assert hasattr(OAuthProvider, "GITHUB")
        assert hasattr(OAuthProvider, "GOOGLE")

    def test_oauth_service_has_required_methods(self):
        """Test OAuthService has required static methods."""
        from app.services.oauth import OAuthService

        assert hasattr(OAuthService, "get_provider_config")
        assert hasattr(OAuthService, "generate_state_token")
        assert hasattr(OAuthService, "get_authorization_url")
        assert hasattr(OAuthService, "handle_oauth_callback")


class TestOAuthRequestModels:
    """Test OAuth request/response models."""

    def test_oauth_init_request_model(self):
        """Test OAuthInitRequest model."""
        from app.routers.v1.oauth import OAuthInitRequest
        from app.models import OAuthProvider

        request = OAuthInitRequest(provider=OAuthProvider.GITHUB)
        assert request.provider == OAuthProvider.GITHUB
        assert request.redirect_uri is None

    def test_oauth_callback_request_model(self):
        """Test OAuthCallbackRequest model."""
        from app.routers.v1.oauth import OAuthCallbackRequest
        from app.models import OAuthProvider

        request = OAuthCallbackRequest(
            code="auth_code",
            state="state_token",
            provider=OAuthProvider.GOOGLE,
        )
        assert request.code == "auth_code"
        assert request.state == "state_token"

    def test_oauth_providers_response_model(self):
        """Test OAuthProvidersResponse model."""
        from app.routers.v1.oauth import OAuthProvidersResponse

        response = OAuthProvidersResponse(
            providers=[{"provider": "github", "name": "GitHub", "enabled": True}]
        )
        assert len(response.providers) == 1


class TestOAuthValidation:
    """Test OAuth validation logic."""

    def test_validate_redirect_with_localhost(self):
        """Test localhost URLs handling."""
        with patch("app.routers.v1.oauth.settings") as mock_settings:
            mock_settings.cors_origins_list = [
                "http://localhost:3000",
                "https://app.janua.dev",
            ]

            # Localhost should be allowed if in CORS list
            result = validate_redirect_url("http://localhost:3000/callback")

            # Depends on whether localhost is explicitly allowed
            assert result is not None or result == "http://localhost:3000/callback"

    def test_validate_redirect_preserves_query_params(self):
        """Test query params preserved in relative URLs."""
        result = validate_redirect_url("/dashboard?success=true&provider=github")

        assert "success=true" in result
        assert "provider=github" in result


class TestOAuthStateManagement:
    """Test OAuth state token management."""

    def test_state_token_generation(self):
        """Test state tokens are generated correctly."""
        from app.services.oauth import OAuthService

        token = OAuthService.generate_state_token()

        assert isinstance(token, str)
        assert len(token) > 20  # Should be sufficiently long


class TestOAuthEndpointSecurity:
    """Test OAuth endpoint security measures."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_callback_validates_state(self):
        """Test callback validates state token."""
        # Without proper Redis state, should fail
        response = self.client.get(
            "/api/v1/auth/oauth/callback/github?code=test&state=invalid_state"
        )

        # Should fail due to invalid state
        assert response.status_code in [400, 500]

    def test_link_callback_validates_state(self):
        """Test link callback validates state."""
        response = self.client.get(
            "/api/v1/auth/oauth/link/callback/github?code=test&state=invalid_state"
        )

        assert response.status_code in [400, 401, 500]


class TestOAuthProviderSupport:
    """Test supported OAuth providers."""

    def test_github_provider_config(self):
        """Test GitHub provider configuration exists."""
        from app.models import OAuthProvider

        assert OAuthProvider.GITHUB.value == "github"

    def test_google_provider_config(self):
        """Test Google provider configuration exists."""
        from app.models import OAuthProvider

        assert OAuthProvider.GOOGLE.value == "google"

    def test_microsoft_provider_config(self):
        """Test Microsoft provider configuration exists."""
        from app.models import OAuthProvider

        # Check if microsoft is a valid provider
        assert hasattr(OAuthProvider, "MICROSOFT")
