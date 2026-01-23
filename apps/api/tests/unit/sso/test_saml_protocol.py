"""
Comprehensive SAML Protocol Test Suite
Tests SAML 2.0 authentication flow, configuration validation, and callback handling.
"""

import base64
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the saml module so we can patch it
from app.sso.domain.protocols import saml as saml_module

pytestmark = pytest.mark.asyncio


class TestSAMLProtocolConfiguration:
    """Test SAML protocol configuration validation"""

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
    def saml_protocol(self, cache_service, attribute_mapper):
        """Create SAML protocol instance"""
        from app.sso.domain.protocols.saml import SAMLProtocol

        return SAMLProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    def test_get_protocol_name(self, saml_protocol):
        """Should return correct protocol name"""
        assert saml_protocol.get_protocol_name() == "saml2"

    def test_get_required_config_fields(self, saml_protocol):
        """Should return required configuration fields"""
        required = saml_protocol.get_required_config_fields()

        assert "entity_id" in required
        assert "sso_url" in required
        assert "certificate" in required
        assert "acs_url" in required

    async def test_validate_valid_configuration(self, saml_protocol):
        """Should validate correct SAML configuration"""
        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "certificate": "-----BEGIN CERTIFICATE-----\nMIIDXTCC...\n-----END CERTIFICATE-----",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        # Mock certificate validation
        with patch.object(saml_protocol, "_validate_certificate", return_value=True):
            result = await saml_protocol.validate_configuration(config)
            assert result is True

    async def test_validate_missing_entity_id(self, saml_protocol):
        """Should reject configuration missing entity_id"""
        from app.sso.exceptions import ValidationError

        config = {
            "sso_url": "https://idp.example.com/sso",
            "certificate": "cert",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        with pytest.raises(ValidationError) as exc_info:
            await saml_protocol.validate_configuration(config)

        assert "entity_id" in str(exc_info.value)

    async def test_validate_missing_sso_url(self, saml_protocol):
        """Should reject configuration missing sso_url"""
        from app.sso.exceptions import ValidationError

        config = {
            "entity_id": "https://idp.example.com",
            "certificate": "cert",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        with pytest.raises(ValidationError) as exc_info:
            await saml_protocol.validate_configuration(config)

        assert "sso_url" in str(exc_info.value)

    async def test_validate_invalid_sso_url_format(self, saml_protocol):
        """Should reject invalid SSO URL format"""
        from app.sso.exceptions import ValidationError

        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "not-a-url",
            "certificate": "cert",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        with patch.object(saml_protocol, "_validate_certificate", return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                await saml_protocol.validate_configuration(config)

            assert "SSO URL" in str(exc_info.value)

    async def test_validate_invalid_certificate(self, saml_protocol):
        """Should reject invalid certificate format"""
        from app.sso.exceptions import ValidationError

        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "certificate": "invalid-certificate",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        with pytest.raises(ValidationError) as exc_info:
            await saml_protocol.validate_configuration(config)

        assert "certificate" in str(exc_info.value).lower()


class TestSAMLAuthentication:
    """Test SAML authentication initiation"""

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
    def saml_protocol(self, cache_service, attribute_mapper):
        """Create SAML protocol instance"""
        from app.sso.domain.protocols.saml import SAMLProtocol

        return SAMLProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    @pytest.fixture
    def valid_config(self):
        """Valid SAML configuration"""
        return {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "certificate": base64.b64encode(b"fake-cert-data").decode(),
            "acs_url": "https://sp.example.com/saml/acs",
        }

    async def test_initiate_authentication_success(self, saml_protocol, valid_config, cache_service):
        """Should initiate SAML authentication successfully"""
        with patch.object(saml_protocol, "_validate_certificate", return_value=True):
            result = await saml_protocol.initiate_authentication(
                organization_id="org_123",
                return_url="https://app.example.com/callback",
                config=valid_config,
            )

        assert "auth_url" in result
        assert result["auth_url"] == valid_config["sso_url"]
        assert result["protocol"] == "saml2"
        assert "request_id" in result
        assert "saml_request" in result
        assert "relay_state" in result

        # Verify state was stored in cache
        cache_service.set.assert_called_once()

    async def test_initiate_authentication_stores_request_state(
        self, saml_protocol, valid_config, cache_service
    ):
        """Should store request state in cache"""
        with patch.object(saml_protocol, "_validate_certificate", return_value=True):
            result = await saml_protocol.initiate_authentication(
                organization_id="org_123",
                return_url="https://app.example.com/callback",
                config=valid_config,
            )

        # Verify cache was called with correct key prefix
        call_args = cache_service.set.call_args
        assert call_args[0][0].startswith("saml_request:")
        stored_state = call_args[0][1]
        assert stored_state["organization_id"] == "org_123"
        assert stored_state["return_url"] == "https://app.example.com/callback"

    async def test_initiate_authentication_without_config(self, saml_protocol):
        """Should raise error when config is missing"""
        from app.sso.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            await saml_protocol.initiate_authentication(
                organization_id="org_123",
                config=None,
            )

        assert "configuration is required" in str(exc_info.value)

    async def test_initiate_authentication_returns_params(
        self, saml_protocol, valid_config
    ):
        """Should return SAML request parameters"""
        with patch.object(saml_protocol, "_validate_certificate", return_value=True):
            # Mock SAML_AVAILABLE to False so it uses mock SAML request generation
            with patch.object(saml_module, "SAML_AVAILABLE", False):
                result = await saml_protocol.initiate_authentication(
                    organization_id="org_123",
                    config=valid_config,
                )

        assert "params" in result
        assert "SAMLRequest" in result["params"]
        assert "RelayState" in result["params"]


class TestSAMLCallback:
    """Test SAML callback handling"""

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
        mapper.map_saml_attributes = MagicMock(
            return_value=UserProvisioningData(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                attributes={},
            )
        )
        return mapper

    @pytest.fixture
    def saml_protocol(self, cache_service, attribute_mapper):
        """Create SAML protocol instance"""
        from app.sso.domain.protocols.saml import SAMLProtocol

        return SAMLProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    async def test_handle_callback_missing_response(self, saml_protocol):
        """Should reject callback without SAML response"""
        from app.sso.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError) as exc_info:
            await saml_protocol.handle_callback({"RelayState": "state_123"})

        assert "Missing SAML response" in str(exc_info.value)

    async def test_handle_callback_missing_relay_state(self, saml_protocol):
        """Should reject callback without relay state"""
        from app.sso.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError) as exc_info:
            await saml_protocol.handle_callback(
                {"SAMLResponse": base64.b64encode(b"<Response/>").decode()}
            )

        assert "Missing SAML response or relay state" in str(exc_info.value)

    async def test_handle_callback_invalid_state(self, saml_protocol, cache_service):
        """Should reject callback with invalid/expired state"""
        from app.sso.exceptions import AuthenticationError

        cache_service.get = AsyncMock(return_value=None)

        with pytest.raises(AuthenticationError) as exc_info:
            await saml_protocol.handle_callback(
                {
                    "SAMLResponse": base64.b64encode(b"<Response/>").decode(),
                    "RelayState": "invalid_state",
                }
            )

        assert "Invalid or expired" in str(exc_info.value)

    async def test_handle_callback_success_mock_mode(
        self, saml_protocol, cache_service, attribute_mapper
    ):
        """Should handle callback successfully in mock mode"""
        # Setup cache to return valid request state with full config
        request_state = {
            "organization_id": "org_123",
            "return_url": "https://app.example.com/callback",
            "config": {
                "entity_id": "https://idp.example.com",
                "sso_url": "https://idp.example.com/sso",
                "certificate": "cert-data",
                "acs_url": "https://sp.example.com/saml/acs",
                "attribute_mapping": {},
            },
        }
        cache_service.get = AsyncMock(return_value=request_state)
        cache_service.delete = AsyncMock(return_value=True)

        # Mock SAML_AVAILABLE to False so it uses mock response processing
        with patch.object(saml_module, "SAML_AVAILABLE", False):
            result = await saml_protocol.handle_callback(
                {
                    "SAMLResponse": base64.b64encode(b"<Response/>").decode(),
                    "RelayState": "valid_state",
                }
            )

        assert "user_data" in result
        assert "session_data" in result
        assert result["organization_id"] == "org_123"
        assert result["return_url"] == "https://app.example.com/callback"

        # Verify state was cleaned up
        cache_service.delete.assert_called_once()


class TestSAMLLogout:
    """Test SAML Single Logout (SLO)"""

    @pytest.fixture
    def cache_service(self):
        """Mock cache service"""
        return AsyncMock()

    @pytest.fixture
    def attribute_mapper(self):
        """Mock attribute mapper"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    @pytest.fixture
    def saml_protocol(self, cache_service, attribute_mapper):
        """Create SAML protocol instance"""
        from app.sso.domain.protocols.saml import SAMLProtocol

        return SAMLProtocol(cache_service=cache_service, attribute_mapper=attribute_mapper)

    async def test_initiate_logout_without_slo_url(self, saml_protocol):
        """Should raise error when SLO URL not configured"""
        from app.sso.exceptions import ValidationError

        config = {"entity_id": "https://idp.example.com"}
        session_data = {"name_id": "user@example.com", "session_index": "session_123"}

        with pytest.raises(ValidationError) as exc_info:
            await saml_protocol.initiate_logout(session_data, config)

        assert "SLO URL not configured" in str(exc_info.value)

    async def test_initiate_logout_success(self, saml_protocol):
        """Should initiate logout successfully"""
        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "slo_url": "https://idp.example.com/slo",
            "certificate": "cert",
            "acs_url": "https://sp.example.com/saml/acs",
        }
        session_data = {"name_id": "user@example.com", "session_index": "session_123"}

        # Mock SAML_AVAILABLE to False so it uses mock logout request generation
        with patch.object(saml_module, "SAML_AVAILABLE", False):
            result = await saml_protocol.initiate_logout(
                session_data, config, return_url="https://app.example.com"
            )

        assert "logout_url" in result
        assert result["logout_url"] == config["slo_url"]
        assert "saml_request" in result
        assert "params" in result


class TestCertificateValidation:
    """Test certificate validation"""

    @pytest.fixture
    def saml_protocol(self):
        """Create SAML protocol instance"""
        from app.sso.domain.protocols.saml import SAMLProtocol

        return SAMLProtocol(cache_service=AsyncMock(), attribute_mapper=MagicMock())

    def test_validate_valid_certificate_with_headers(self, saml_protocol):
        """Should validate certificate with PEM headers"""
        cert = """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKg5tqDZ
-----END CERTIFICATE-----"""

        result = saml_protocol._validate_certificate(cert)
        assert result is True

    def test_validate_valid_certificate_without_headers(self, saml_protocol):
        """Should validate certificate without PEM headers"""
        # Valid base64 encoded certificate data
        cert = "MIIDXTCCAkWgAwIBAgIJAKg5tqDZ"

        result = saml_protocol._validate_certificate(cert)
        assert result is True

    def test_validate_empty_certificate(self, saml_protocol):
        """Should reject empty certificate"""
        result = saml_protocol._validate_certificate("")
        assert result is False

    def test_validate_invalid_base64_certificate(self, saml_protocol):
        """Should reject invalid base64 data"""
        result = saml_protocol._validate_certificate("not-valid-base64!!!")
        assert result is False


class TestSAMLSettingsBuilder:
    """Test SAML settings builder"""

    @pytest.fixture
    def saml_protocol(self):
        """Create SAML protocol instance"""
        from app.sso.domain.protocols.saml import SAMLProtocol

        return SAMLProtocol(cache_service=AsyncMock(), attribute_mapper=MagicMock())

    def test_build_saml_settings_basic(self, saml_protocol):
        """Should build basic SAML settings"""
        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "certificate": "cert-data",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        settings = saml_protocol._build_saml_settings(config)

        assert "sp" in settings
        assert "idp" in settings
        assert settings["idp"]["entityId"] == config["entity_id"]
        assert settings["idp"]["singleSignOnService"]["url"] == config["sso_url"]
        assert settings["idp"]["x509cert"] == config["certificate"]
        assert settings["sp"]["assertionConsumerService"]["url"] == config["acs_url"]

    def test_build_saml_settings_with_slo(self, saml_protocol):
        """Should include SLO settings when configured"""
        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "slo_url": "https://idp.example.com/slo",
            "certificate": "cert-data",
            "acs_url": "https://sp.example.com/saml/acs",
        }

        settings = saml_protocol._build_saml_settings(config)

        assert settings["idp"]["singleLogoutService"]["url"] == config["slo_url"]

    def test_build_saml_settings_security_options(self, saml_protocol):
        """Should include security options"""
        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "certificate": "cert-data",
            "acs_url": "https://sp.example.com/saml/acs",
            "sign_request": True,
            "want_assertions_signed": True,
            "encrypt_assertion": True,
        }

        settings = saml_protocol._build_saml_settings(config)

        assert settings["security"]["authnRequestsSigned"] is True
        assert settings["security"]["wantAssertionsSigned"] is True
        assert settings["security"]["wantAssertionsEncrypted"] is True

    def test_build_saml_settings_custom_name_id_format(self, saml_protocol):
        """Should use custom NameID format"""
        config = {
            "entity_id": "https://idp.example.com",
            "sso_url": "https://idp.example.com/sso",
            "certificate": "cert-data",
            "acs_url": "https://sp.example.com/saml/acs",
            "name_id_format": "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
        }

        settings = saml_protocol._build_saml_settings(config)

        assert settings["sp"]["NameIDFormat"] == config["name_id_format"]
