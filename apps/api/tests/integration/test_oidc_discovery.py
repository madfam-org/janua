"""
Integration tests for OIDC Discovery functionality.

Tests OIDC discovery protocol and provider configuration.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from app.sso.domain.services.oidc_discovery import OIDCDiscoveryService


class TestOIDCDiscoveryService:
    """Test OIDC discovery service functionality."""

    @pytest.fixture
    def mock_discovery_response(self):
        """Mock OIDC discovery document."""
        return {
            "issuer": "https://example.com",
            "authorization_endpoint": "https://example.com/oauth/authorize",
            "token_endpoint": "https://example.com/oauth/token",
            "userinfo_endpoint": "https://example.com/userinfo",
            "jwks_uri": "https://example.com/.well-known/jwks.json",
            "revocation_endpoint": "https://example.com/oauth/revoke",
            "end_session_endpoint": "https://example.com/logout",
            "response_types_supported": ["code", "token", "id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email"],
            "claims_supported": ["sub", "name", "email", "email_verified"],
        }

    @pytest.mark.asyncio
    async def test_discover_configuration_success(self, mock_discovery_response):
        """Test successful OIDC discovery."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_discovery_response

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Discover configuration
            config = await service.discover_configuration("https://example.com")

            # Verify configuration
            assert config["issuer"] == "https://example.com"
            assert config["authorization_endpoint"] == "https://example.com/oauth/authorize"
            assert config["token_endpoint"] == "https://example.com/oauth/token"
            assert config["jwks_uri"] == "https://example.com/.well-known/jwks.json"

    @pytest.mark.asyncio
    async def test_discover_from_url(self, mock_discovery_response):
        """Test discovery from explicit URL."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_discovery_response

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            config = await service.discover_from_url(
                "https://example.com/.well-known/openid-configuration"
            )

            assert config["issuer"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_discover_caching(self, mock_discovery_response):
        """Test discovery configuration caching."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_discovery_response

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # First call - should fetch
            config1 = await service.discover_configuration("https://example.com")

            # Second call - should use cache
            config2 = await service.discover_configuration("https://example.com")

            # Should have called HTTP only once
            assert mock_client.return_value.__aenter__.return_value.get.call_count == 1

            # Configs should match
            assert config1 == config2

    @pytest.mark.asyncio
    async def test_discover_force_refresh(self, mock_discovery_response):
        """Test force refresh bypasses cache."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_discovery_response

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # First call
            await service.discover_configuration("https://example.com")

            # Second call with force_refresh
            await service.discover_configuration("https://example.com", force_refresh=True)

            # Should have called HTTP twice
            assert mock_client.return_value.__aenter__.return_value.get.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_issuer(self):
        """Test validation of invalid issuer."""
        service = OIDCDiscoveryService()

        with pytest.raises(ValueError, match="Issuer must be a valid HTTPS URL"):
            await service.discover_configuration("not-a-url")

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """Test validation of incomplete discovery document."""
        service = OIDCDiscoveryService()

        incomplete_config = {
            "issuer": "https://example.com",
            # Missing required fields
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = incomplete_config

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ValueError, match="missing required fields"):
                await service.discover_configuration("https://example.com")

    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test handling of HTTP errors."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ValueError, match="returned 404"):
                await service.discover_configuration("https://example.com")

    def test_extract_provider_config(self, mock_discovery_response):
        """Test extracting provider configuration."""
        service = OIDCDiscoveryService()

        provider_config = service.extract_provider_config(
            discovery_config=mock_discovery_response,
            client_id="test-client-id",
            client_secret="test-secret",
            redirect_uri="https://app.example.com/callback",
            scopes=["openid", "profile", "email"],
        )

        # Verify required fields
        assert provider_config["issuer"] == "https://example.com"
        assert provider_config["client_id"] == "test-client-id"
        assert provider_config["client_secret"] == "test-secret"
        assert provider_config["redirect_uri"] == "https://app.example.com/callback"
        assert provider_config["authorization_endpoint"] == "https://example.com/oauth/authorize"
        assert provider_config["token_endpoint"] == "https://example.com/oauth/token"
        assert provider_config["scopes"] == ["openid", "profile", "email"]

        # Verify optional fields
        assert provider_config["userinfo_endpoint"] == "https://example.com/userinfo"
        assert provider_config["jwks_uri"] == "https://example.com/.well-known/jwks.json"

    @pytest.mark.asyncio
    async def test_clear_cache(self, mock_discovery_response):
        """Test clearing discovery cache."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_discovery_response

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Fetch and cache
            await service.discover_configuration("https://example.com")

            # Clear cache
            await service.clear_cache("https://example.com")

            # Fetch again - should make HTTP call
            await service.discover_configuration("https://example.com")

            # Should have called HTTP twice (once before clear, once after)
            assert mock_client.return_value.__aenter__.return_value.get.call_count == 2


class TestOIDCDiscoveryIntegration:
    """Integration tests with real OIDC providers."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Skip by default - requires internet
        reason="Integration test requires internet connection",
    )
    async def test_google_discovery(self):
        """Test discovery with Google's OIDC provider."""
        service = OIDCDiscoveryService()

        config = await service.discover_configuration("https://accounts.google.com")

        # Verify Google's configuration
        assert config["issuer"] == "https://accounts.google.com"
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config
        assert "jwks_uri" in config
        assert "RS256" in config["id_token_signing_alg_values_supported"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Skip by default - requires internet
        reason="Integration test requires internet connection",
    )
    async def test_microsoft_discovery(self):
        """Test discovery with Microsoft's OIDC provider."""
        service = OIDCDiscoveryService()

        config = await service.discover_configuration(
            "https://login.microsoftonline.com/common/v2.0"
        )

        # Verify Microsoft's configuration
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config
        assert "jwks_uri" in config


class TestOIDCDiscoveryEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_issuer_with_trailing_slash(self, mock_discovery_response):
        """Test issuer with trailing slash is normalized."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_discovery_response

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            await service.discover_configuration("https://example.com/")

            # Should have normalized to remove trailing slash
            call_url = mock_client.return_value.__aenter__.return_value.get.call_args[0][0]
            assert not call_url.endswith("//.well-known")

    @pytest.mark.asyncio
    async def test_http_issuer_warning(self, mock_discovery_response):
        """Test warning for HTTP (non-HTTPS) issuer."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                **mock_discovery_response,
                "issuer": "http://example.com",
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Should issue warning for HTTP (but still work for localhost)
            with pytest.warns(UserWarning, match="Using HTTP for OIDC discovery"):
                await service.discover_configuration("http://example.com")

    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        """Test handling of malformed JSON response."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ValueError, match="Error parsing discovery document"):
                await service.discover_configuration("https://example.com")

    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeout."""
        service = OIDCDiscoveryService()

        with patch("httpx.AsyncClient") as mock_client:
            import httpx

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            with pytest.raises(ValueError, match="Failed to fetch discovery document"):
                await service.discover_configuration("https://example.com")
