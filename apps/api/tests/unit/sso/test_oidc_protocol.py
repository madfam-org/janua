"""
Comprehensive OIDC Protocol Test Suite
Tests OpenID Connect authentication flow, token handling, and validation.
"""

import base64
import secrets
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


class TestOIDCProtocolConfiguration:
    """Test OIDC protocol configuration validation"""

    @pytest.fixture
    def cache_service(self):
        """Mock cache service"""
        service = AsyncMock()
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def attribute_mapper(self):
        """Mock attribute mapper"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    @pytest.fixture
    def oidc_protocol(self, cache_service, attribute_mapper):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        return OIDCProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    def test_get_protocol_name(self, oidc_protocol):
        """Should return correct protocol name"""
        assert oidc_protocol.get_protocol_name() == "oidc"

    def test_get_required_config_fields(self, oidc_protocol):
        """Should return required configuration fields"""
        required = oidc_protocol.get_required_config_fields()

        assert "issuer" in required
        assert "client_id" in required
        assert "client_secret" in required
        assert "authorization_endpoint" in required
        assert "token_endpoint" in required
        assert "redirect_uri" in required

    async def test_validate_valid_configuration(self, oidc_protocol):
        """Should validate correct OIDC configuration"""
        config = {
            "issuer": "https://idp.example.com",
            "client_id": "client_123",
            "client_secret": "secret_456",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
        }

        result = await oidc_protocol.validate_configuration(config)
        assert result is True

    async def test_validate_missing_issuer(self, oidc_protocol):
        """Should reject configuration missing issuer"""
        from app.sso.exceptions import ValidationError

        config = {
            "client_id": "client_123",
            "client_secret": "secret_456",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
        }

        with pytest.raises(ValidationError) as exc_info:
            await oidc_protocol.validate_configuration(config)

        assert "issuer" in str(exc_info.value)

    async def test_validate_missing_client_id(self, oidc_protocol):
        """Should reject configuration missing client_id"""
        from app.sso.exceptions import ValidationError

        config = {
            "issuer": "https://idp.example.com",
            "client_secret": "secret_456",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
        }

        with pytest.raises(ValidationError) as exc_info:
            await oidc_protocol.validate_configuration(config)

        assert "client_id" in str(exc_info.value)

    async def test_validate_invalid_authorization_endpoint(self, oidc_protocol):
        """Should reject invalid authorization endpoint URL"""
        from app.sso.exceptions import ValidationError

        config = {
            "issuer": "https://idp.example.com",
            "client_id": "client_123",
            "client_secret": "secret_456",
            "authorization_endpoint": "not-a-url",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
        }

        with pytest.raises(ValidationError) as exc_info:
            await oidc_protocol.validate_configuration(config)

        assert "authorization_endpoint" in str(exc_info.value)

    async def test_validate_invalid_issuer_format(self, oidc_protocol):
        """Should reject invalid issuer URL format"""
        from app.sso.exceptions import ValidationError

        config = {
            "issuer": "not-a-url",
            "client_id": "client_123",
            "client_secret": "secret_456",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
        }

        with pytest.raises(ValidationError) as exc_info:
            await oidc_protocol.validate_configuration(config)

        assert "issuer" in str(exc_info.value).lower()


class TestOIDCAuthentication:
    """Test OIDC authentication initiation"""

    @pytest.fixture
    def cache_service(self):
        """Mock cache service"""
        service = AsyncMock()
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def attribute_mapper(self):
        """Mock attribute mapper"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    @pytest.fixture
    def oidc_protocol(self, cache_service, attribute_mapper):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        return OIDCProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    @pytest.fixture
    def valid_config(self):
        """Valid OIDC configuration"""
        return {
            "issuer": "https://idp.example.com",
            "client_id": "client_123",
            "client_secret": "secret_456",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
            "scopes": ["openid", "profile", "email"],
        }

    async def test_initiate_authentication_success(
        self, oidc_protocol, valid_config, cache_service
    ):
        """Should initiate OIDC authentication successfully"""
        result = await oidc_protocol.initiate_authentication(
            organization_id="org_123",
            return_url="https://app.example.com/dashboard",
            config=valid_config,
        )

        assert "auth_url" in result
        assert valid_config["authorization_endpoint"] in result["auth_url"]
        assert result["protocol"] == "oidc"
        assert "state" in result
        assert "nonce" in result
        assert len(result["state"]) > 20  # Cryptographic random

        # Verify state was stored
        cache_service.set.assert_called_once()

    async def test_initiate_authentication_includes_required_params(
        self, oidc_protocol, valid_config
    ):
        """Should include all required OAuth parameters"""
        result = await oidc_protocol.initiate_authentication(
            organization_id="org_123",
            config=valid_config,
        )

        assert "params" in result
        params = result["params"]
        assert params["response_type"] == "code"
        assert params["client_id"] == valid_config["client_id"]
        assert params["redirect_uri"] == valid_config["redirect_uri"]
        assert "openid" in params["scope"]
        assert "state" in params
        assert "nonce" in params

    async def test_initiate_authentication_with_custom_scopes(
        self, oidc_protocol, valid_config
    ):
        """Should include custom scopes"""
        valid_config["scopes"] = ["openid", "profile", "email", "custom_scope"]

        result = await oidc_protocol.initiate_authentication(
            organization_id="org_123",
            config=valid_config,
        )

        assert "custom_scope" in result["params"]["scope"]

    async def test_initiate_authentication_with_prompt(self, oidc_protocol, valid_config):
        """Should include prompt parameter when configured"""
        valid_config["prompt"] = "consent"

        result = await oidc_protocol.initiate_authentication(
            organization_id="org_123",
            config=valid_config,
        )

        assert result["params"]["prompt"] == "consent"

    async def test_initiate_authentication_with_max_age(self, oidc_protocol, valid_config):
        """Should include max_age parameter when configured"""
        valid_config["max_age"] = 3600

        result = await oidc_protocol.initiate_authentication(
            organization_id="org_123",
            config=valid_config,
        )

        assert result["params"]["max_age"] == 3600

    async def test_initiate_authentication_without_config(self, oidc_protocol):
        """Should raise error when config is missing"""
        from app.sso.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            await oidc_protocol.initiate_authentication(
                organization_id="org_123",
                config=None,
            )

        assert "configuration is required" in str(exc_info.value)

    async def test_initiate_authentication_stores_state(
        self, oidc_protocol, valid_config, cache_service
    ):
        """Should store state with correct data"""
        result = await oidc_protocol.initiate_authentication(
            organization_id="org_123",
            return_url="https://app.example.com/callback",
            config=valid_config,
        )

        # Verify cache was called with correct key prefix
        call_args = cache_service.set.call_args
        assert call_args[0][0].startswith("oidc_state:")
        stored_state = call_args[0][1]
        assert stored_state["organization_id"] == "org_123"
        assert stored_state["nonce"] == result["nonce"]


class TestOIDCCallback:
    """Test OIDC callback handling"""

    @pytest.fixture
    def cache_service(self):
        """Mock cache service"""
        service = AsyncMock()
        return service

    @pytest.fixture
    def attribute_mapper(self):
        """Mock attribute mapper"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper
        from app.sso.domain.protocols.base import UserProvisioningData

        mapper = AttributeMapper()
        mapper.map_oidc_claims = MagicMock(
            return_value=UserProvisioningData(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                attributes={},
            )
        )
        return mapper

    @pytest.fixture
    def oidc_protocol(self, cache_service, attribute_mapper):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        return OIDCProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    async def test_handle_callback_with_error(self, oidc_protocol):
        """Should handle OAuth error response"""
        from app.sso.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError) as exc_info:
            await oidc_protocol.handle_callback(
                {
                    "error": "access_denied",
                    "error_description": "User denied the request",
                }
            )

        assert "access_denied" in str(exc_info.value)
        assert "User denied" in str(exc_info.value)

    async def test_handle_callback_missing_code(self, oidc_protocol):
        """Should reject callback without authorization code"""
        from app.sso.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError) as exc_info:
            await oidc_protocol.handle_callback({"state": "state_123"})

        assert "Missing authorization code" in str(exc_info.value)

    async def test_handle_callback_missing_state(self, oidc_protocol):
        """Should reject callback without state"""
        from app.sso.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError) as exc_info:
            await oidc_protocol.handle_callback({"code": "auth_code_123"})

        assert "Missing authorization code or state" in str(exc_info.value)

    async def test_handle_callback_invalid_state(self, oidc_protocol, cache_service):
        """Should reject callback with invalid/expired state"""
        from app.sso.exceptions import AuthenticationError

        cache_service.get = AsyncMock(return_value=None)

        with pytest.raises(AuthenticationError) as exc_info:
            await oidc_protocol.handle_callback(
                {"code": "auth_code_123", "state": "invalid_state"}
            )

        assert "Invalid or expired state" in str(exc_info.value)


class TestOIDCTokenOperations:
    """Test OIDC token operations"""

    @pytest.fixture
    def oidc_protocol(self):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        return OIDCProtocol(cache_service=AsyncMock(), attribute_mapper=MagicMock())

    @pytest.fixture
    def valid_config(self):
        """Valid OIDC configuration"""
        return {
            "issuer": "https://idp.example.com",
            "client_id": "client_123",
            "client_secret": "secret_456",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "redirect_uri": "https://app.example.com/callback",
            "revocation_endpoint": "https://idp.example.com/revoke",
        }

    async def test_refresh_tokens_success(self, oidc_protocol, valid_config):
        """Should refresh tokens successfully"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await oidc_protocol.refresh_tokens("old_refresh_token", valid_config)

        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"

    async def test_refresh_tokens_failure(self, oidc_protocol, valid_config):
        """Should raise error on refresh failure"""
        from app.sso.exceptions import AuthenticationError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError) as exc_info:
                await oidc_protocol.refresh_tokens("invalid_refresh_token", valid_config)

            assert "refresh failed" in str(exc_info.value)

    async def test_revoke_token_success(self, oidc_protocol, valid_config):
        """Should revoke token successfully"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await oidc_protocol.revoke_token("access_token", valid_config)

        assert result is True

    async def test_revoke_token_no_endpoint(self, oidc_protocol, valid_config):
        """Should return True when no revocation endpoint is configured"""
        del valid_config["revocation_endpoint"]

        result = await oidc_protocol.revoke_token("access_token", valid_config)

        assert result is True


class TestOIDCBase64URLDecode:
    """Test base64url decoding"""

    @pytest.fixture
    def oidc_protocol(self):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        return OIDCProtocol(cache_service=AsyncMock(), attribute_mapper=MagicMock())

    def test_decode_standard_base64url(self, oidc_protocol):
        """Should decode standard base64url data"""
        data = base64.urlsafe_b64encode(b"test data").decode().rstrip("=")
        result = oidc_protocol._base64url_decode(data)
        assert result == b"test data"

    def test_decode_with_padding_needed(self, oidc_protocol):
        """Should handle data that needs padding"""
        # Create data that when base64 encoded needs padding
        data = "dGVzdA"  # "test" without padding
        result = oidc_protocol._base64url_decode(data)
        assert result == b"test"

    def test_decode_no_padding_needed(self, oidc_protocol):
        """Should handle data that doesn't need padding"""
        data = base64.urlsafe_b64encode(b"test").decode()
        result = oidc_protocol._base64url_decode(data)
        assert result == b"test"


class TestOIDCJWKConversion:
    """Test JWK to PEM conversion"""

    @pytest.fixture
    def oidc_protocol(self):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        return OIDCProtocol(cache_service=AsyncMock(), attribute_mapper=MagicMock())

    def test_jwk_to_pem_unsupported_key_type(self, oidc_protocol):
        """Should reject non-RSA key types"""
        from app.sso.exceptions import AuthenticationError

        jwk = {
            "kty": "EC",
            "crv": "P-256",
            "x": "abc",
            "y": "def",
        }

        with pytest.raises(AuthenticationError) as exc_info:
            oidc_protocol._jwk_to_pem(jwk)

        assert "Only RSA keys are supported" in str(exc_info.value)


class TestOIDCSigningKey:
    """Test signing key retrieval"""

    @pytest.fixture
    def oidc_protocol(self):
        """Create OIDC protocol instance"""
        from app.sso.domain.protocols.oidc import OIDCProtocol

        protocol = OIDCProtocol(cache_service=AsyncMock(), attribute_mapper=MagicMock())
        protocol._jwks_cache = {}
        return protocol

    async def test_get_signing_key_without_jwks_uri(self, oidc_protocol):
        """Should use client secret when no JWKS URI"""
        config = {
            "issuer": "https://idp.example.com",
            "client_secret": "my_secret",
        }

        result = await oidc_protocol._get_signing_key(None, config)
        assert result == "my_secret"

    async def test_get_signing_key_not_found(self, oidc_protocol):
        """Should raise error when key not found in JWKS"""
        from app.sso.exceptions import AuthenticationError

        config = {
            "issuer": "https://idp.example.com",
            "jwks_uri": "https://idp.example.com/.well-known/jwks.json",
        }

        # Mock JWKS response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"keys": [{"kid": "other_key", "kty": "RSA"}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError) as exc_info:
                await oidc_protocol._get_signing_key("missing_kid", config)

            assert "Unable to find signing key" in str(exc_info.value)
