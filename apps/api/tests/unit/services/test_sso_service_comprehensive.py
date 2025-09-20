import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for SSOService - targeting 100% coverage
This test covers all SSO operations, SAML/OIDC integration, identity provider management
Expected to cover 231 lines in app/services/sso_service.py
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any
import xml.etree.ElementTree as ET

from app.services.sso_service import SSOService


class TestSSOServiceInitialization:
    """Test SSO service initialization and configuration."""

    def test_sso_service_init(self):
        """Test SSO service initializes correctly."""
        service = SSOService()

        assert hasattr(service, 'saml_settings')
        assert hasattr(service, 'oidc_clients')
        assert hasattr(service, 'identity_providers')
        assert hasattr(service, 'redis_client')

    def test_supported_protocols_configuration(self):
        """Test supported SSO protocols configuration."""
        service = SSOService()

        assert 'saml2' in service.supported_protocols
        assert 'oidc' in service.supported_protocols
        assert 'oauth2' in service.supported_protocols

    def test_identity_provider_defaults(self):
        """Test default identity provider configurations."""
        service = SSOService()

        # Common enterprise providers should be pre-configured
        assert 'okta' in service.identity_providers
        assert 'azure_ad' in service.identity_providers
        assert 'google_workspace' in service.identity_providers
        assert 'auth0' in service.identity_providers


class TestSAMLIntegration:
    """Test SAML 2.0 integration functionality."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_initiate_saml_login_success(self):
        """Test successful SAML login initiation."""
        provider_config = {
            "name": "okta",
            "protocol": "saml2",
            "sso_url": "https://dev-123.okta.com/app/plinto/sso/saml",
            "entity_id": "http://www.okta.com/123",
            "x509_cert": "-----BEGIN CERTIFICATE-----\nMIIC...CERTIFICATE...\n-----END CERTIFICATE-----"
        }

        with patch('app.services.sso_service.Saml2Client', create=True) as mock_saml_client:
            mock_client = MagicMock()
            mock_client.prepare_for_authenticate.return_value = (
                "req_123",
                {"RelayState": "state_abc", "SAMLRequest": "base64_encoded_request"}
            )
            mock_saml_client.return_value = mock_client

            result = await self.service.initiate_saml_sso("okta", provider_config)

            assert result["auth_url"] is not None
            assert result["request_id"] == "req_123"
            assert result["protocol"] == "saml2"
            assert "RelayState" in result["params"]

    @pytest.mark.asyncio
    async def test_process_saml_response_success(self):
        """Test successful SAML response processing."""
        saml_response = """
        <saml2p:Response xmlns:saml2p="urn:oasis:names:tc:SAML:2.0:protocol">
            <saml2:Assertion xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion">
                <saml2:AttributeStatement>
                    <saml2:Attribute Name="email">
                        <saml2:AttributeValue>user@company.com</saml2:AttributeValue>
                    </saml2:Attribute>
                    <saml2:Attribute Name="firstName">
                        <saml2:AttributeValue>John</saml2:AttributeValue>
                    </saml2:Attribute>
                    <saml2:Attribute Name="lastName">
                        <saml2:AttributeValue>Doe</saml2:AttributeValue>
                    </saml2:Attribute>
                </saml2:AttributeStatement>
            </saml2:Assertion>
        </saml2p:Response>
        """

        with patch('app.services.sso_service.Saml2Client', create=True) as mock_saml_client:
            mock_client = MagicMock()
            mock_client.parse_authn_request_response.return_value = MagicMock(
                ava={
                    "email": ["user@company.com"],
                    "firstName": ["John"],
                    "lastName": ["Doe"]
                },
                session_id="session_123"
            )
            mock_saml_client.return_value = mock_client

            result = await self.service.process_saml_response(saml_response, "req_123")

            assert result["success"] is True
            assert result["user_attributes"]["email"] == "user@company.com"
            assert result["user_attributes"]["firstName"] == "John"
            assert result["user_attributes"]["lastName"] == "Doe"
            assert result["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_process_saml_response_invalid_signature(self):
        """Test SAML response processing with invalid signature."""
        invalid_saml_response = "<invalid>response</invalid>"

        with patch('app.services.sso_service.Saml2Client', create=True) as mock_saml_client:
            mock_client = MagicMock()
            mock_client.parse_authn_request_response.side_effect = Exception("Invalid signature")
            mock_saml_client.return_value = mock_client

            result = await self.service.process_saml_response(invalid_saml_response, "req_123")

            assert result["success"] is False
            assert "Invalid signature" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_saml_metadata(self):
        """Test SAML metadata generation for service provider."""
        entity_id = "https://plinto.dev/saml/metadata"
        acs_url = "https://plinto.dev/saml/acs"

        result = await self.service.generate_saml_metadata(entity_id, acs_url)

        assert result["metadata_xml"] is not None
        assert entity_id in result["metadata_xml"]
        assert acs_url in result["metadata_xml"]

        # Verify XML is valid
        ET.fromstring(result["metadata_xml"])


class TestOIDCIntegration:
    """Test OpenID Connect integration functionality."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_initiate_oidc_login_success(self):
        """Test successful OIDC login initiation."""
        provider_config = {
            "name": "azure_ad",
            "protocol": "oidc",
            "client_id": "client_123",
            "client_secret": "secret_456",
            "discovery_url": "https://login.microsoftonline.com/tenant/.well-known/openid_configuration",
            "scopes": ["openid", "profile", "email"]
        }

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.json.return_value = {
                "authorization_endpoint": "https://login.microsoftonline.com/oauth2/v2.0/authorize",
                "token_endpoint": "https://login.microsoftonline.com/oauth2/v2.0/token",
                "userinfo_endpoint": "https://graph.microsoft.com/oidc/userinfo"
            }
            mock_get.return_value.status_code = 200

            result = await self.service.initiate_oidc_login("azure_ad", provider_config)

            assert result["auth_url"] is not None
            assert "login.microsoftonline.com" in result["auth_url"]
            assert result["state"] is not None
            assert result["protocol"] == "oidc"

    @pytest.mark.asyncio
    async def test_process_oidc_callback_success(self):
        """Test successful OIDC callback processing."""
        callback_data = {
            "code": "auth_code_123",
            "state": "state_456"
        }

        provider_config = {
            "client_id": "client_123",
            "client_secret": "secret_456",
            "token_endpoint": "https://provider.com/oauth2/token",
            "userinfo_endpoint": "https://provider.com/userinfo"
        }

        with patch('httpx.AsyncClient.post') as mock_post, \
             patch('httpx.AsyncClient.get') as mock_get:

            # Mock token exchange
            mock_post.return_value.json.return_value = {
                "access_token": "access_token_789",
                "id_token": "id_token_abc",
                "token_type": "Bearer",
                "expires_in": 3600
            }
            mock_post.return_value.status_code = 200

            # Mock userinfo request
            mock_get.return_value.json.return_value = {
                "sub": "user_123",
                "email": "user@company.com",
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe"
            }
            mock_get.return_value.status_code = 200

            result = await self.service.process_oidc_callback(callback_data, provider_config, "state_456")

            assert result["success"] is True
            assert result["user_info"]["email"] == "user@company.com"
            assert result["user_info"]["name"] == "John Doe"
            assert result["tokens"]["access_token"] == "access_token_789"

    @pytest.mark.asyncio
    async def test_process_oidc_callback_invalid_state(self):
        """Test OIDC callback processing with invalid state."""
        callback_data = {
            "code": "auth_code_123",
            "state": "invalid_state"
        }

        provider_config = {"client_id": "client_123"}

        result = await self.service.process_oidc_callback(callback_data, provider_config, "expected_state")

        assert result["success"] is False
        assert "Invalid state" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_id_token_success(self):
        """Test successful ID token validation."""
        # Mock JWT with valid structure
        mock_id_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoidXNlckBjb21wYW55LmNvbSJ9.signature"

        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": "user_123",
                "email": "user@company.com",
                "iat": int(datetime.now().timestamp()),
                "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
                "aud": "client_123",
                "iss": "https://provider.com"
            }

            result = await self.service.validate_id_token(mock_id_token, "client_123", "https://provider.com")

            assert result["valid"] is True
            assert result["claims"]["email"] == "user@company.com"
            assert result["claims"]["sub"] == "user_123"

    @pytest.mark.asyncio
    async def test_validate_id_token_expired(self):
        """Test ID token validation with expired token."""
        mock_id_token = "expired.token.signature"

        with patch('jwt.decode') as mock_jwt_decode:
            from jwt.exceptions import ExpiredSignatureError
            mock_jwt_decode.side_effect = ExpiredSignatureError("Token has expired")

            result = await self.service.validate_id_token(mock_id_token, "client_123", "https://provider.com")

            assert result["valid"] is False
            assert "expired" in result["error"].lower()


class TestIdentityProviderManagement:
    """Test identity provider configuration and management."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_add_identity_provider_saml(self):
        """Test adding new SAML identity provider."""
        provider_config = {
            "name": "custom_saml",
            "protocol": "saml2",
            "entity_id": "https://custom.com/saml",
            "sso_url": "https://custom.com/sso",
            "x509_cert": "-----BEGIN CERTIFICATE-----\nCUSTOM_CERT\n-----END CERTIFICATE-----",
            "attribute_mapping": {
                "email": "emailAddress",
                "first_name": "givenName",
                "last_name": "surname"
            }
        }

        result = await self.service.add_identity_provider("custom_saml", provider_config)

        assert result["success"] is True
        assert result["provider_id"] == "custom_saml"
        assert "custom_saml" in self.service.identity_providers

    @pytest.mark.asyncio
    async def test_add_identity_provider_oidc(self):
        """Test adding new OIDC identity provider."""
        provider_config = {
            "name": "custom_oidc",
            "protocol": "oidc",
            "client_id": "custom_client_123",
            "client_secret": "custom_secret_456",
            "discovery_url": "https://custom.com/.well-known/openid_configuration",
            "scopes": ["openid", "profile", "email", "groups"]
        }

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.json.return_value = {
                "authorization_endpoint": "https://custom.com/auth",
                "token_endpoint": "https://custom.com/token",
                "userinfo_endpoint": "https://custom.com/userinfo",
                "jwks_uri": "https://custom.com/jwks"
            }
            mock_get.return_value.status_code = 200

            result = await self.service.add_identity_provider("custom_oidc", provider_config)

            assert result["success"] is True
            assert result["provider_id"] == "custom_oidc"
            assert "custom_oidc" in self.service.identity_providers

    @pytest.mark.asyncio
    async def test_remove_identity_provider(self):
        """Test removing identity provider."""
        # First add a provider
        await self.service.add_identity_provider("temp_provider", {
            "name": "temp_provider",
            "protocol": "saml2"
        })

        result = await self.service.remove_identity_provider("temp_provider")

        assert result["success"] is True
        assert "temp_provider" not in self.service.identity_providers

    @pytest.mark.asyncio
    async def test_list_identity_providers(self):
        """Test listing all configured identity providers."""
        result = await self.service.list_identity_providers()

        assert isinstance(result["providers"], list)
        assert len(result["providers"]) > 0

        # Check default providers are included
        provider_names = [p["name"] for p in result["providers"]]
        assert "okta" in provider_names
        assert "azure_ad" in provider_names

    @pytest.mark.asyncio
    async def test_test_identity_provider_connection(self):
        """Test identity provider connection testing."""
        provider_config = {
            "protocol": "oidc",
            "discovery_url": "https://provider.com/.well-known/openid_configuration"
        }

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.json.return_value = {
                "authorization_endpoint": "https://provider.com/auth"
            }
            mock_get.return_value.status_code = 200

            result = await self.service.test_provider_connection("test_provider", provider_config)

            assert result["success"] is True
            assert result["connection_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_test_identity_provider_connection_failure(self):
        """Test identity provider connection testing with failure."""
        provider_config = {
            "protocol": "oidc",
            "discovery_url": "https://invalid.provider.com/.well-known/openid_configuration"
        }

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            result = await self.service.test_provider_connection("test_provider", provider_config)

            assert result["success"] is False
            assert result["connection_status"] == "failed"
            assert "Connection failed" in result["error"]


class TestUserProvisioning:
    """Test user provisioning and attribute mapping."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_provision_user_from_saml_attributes(self):
        """Test user provisioning from SAML attributes."""
        saml_attributes = {
            "email": ["john.doe@company.com"],
            "firstName": ["John"],
            "lastName": ["Doe"],
            "department": ["Engineering"],
            "title": ["Senior Developer"],
            "groups": ["developers", "admin"]
        }

        attribute_mapping = {
            "email": "email",
            "first_name": "firstName",
            "last_name": "lastName",
            "department": "department",
            "job_title": "title",
            "groups": "groups"
        }

        result = await self.service.provision_user_from_attributes(saml_attributes, attribute_mapping)

        assert result["success"] is True
        assert result["user_data"]["email"] == "john.doe@company.com"
        assert result["user_data"]["first_name"] == "John"
        assert result["user_data"]["last_name"] == "Doe"
        assert "developers" in result["user_data"]["groups"]

    @pytest.mark.asyncio
    async def test_provision_user_from_oidc_userinfo(self):
        """Test user provisioning from OIDC userinfo."""
        oidc_userinfo = {
            "sub": "user_123",
            "email": "jane.smith@company.com",
            "given_name": "Jane",
            "family_name": "Smith",
            "groups": ["marketing", "managers"],
            "department": "Marketing"
        }

        result = await self.service.provision_user_from_oidc(oidc_userinfo)

        assert result["success"] is True
        assert result["user_data"]["email"] == "jane.smith@company.com"
        assert result["user_data"]["first_name"] == "Jane"
        assert result["user_data"]["last_name"] == "Smith"
        assert "marketing" in result["user_data"]["groups"]

    @pytest.mark.asyncio
    async def test_update_user_attributes_from_sso(self):
        """Test updating existing user attributes from SSO."""
        existing_user_id = str(uuid4())
        sso_attributes = {
            "department": "Engineering",
            "title": "Lead Developer",
            "groups": ["developers", "tech_leads"],
            "manager": "john.manager@company.com"
        }

        with patch.object(self.service, '_get_user_by_id') as mock_get_user, \
             patch.object(self.service, '_update_user_attributes') as mock_update:

            mock_get_user.return_value = {
                "id": existing_user_id,
                "email": "user@company.com",
                "first_name": "Test",
                "last_name": "User"
            }

            result = await self.service.update_user_from_sso(existing_user_id, sso_attributes)

            assert result["success"] is True
            mock_update.assert_called_once()


class TestJustInTimeProvisioning:
    """Test Just-In-Time (JIT) user provisioning."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_jit_provisioning_new_user(self):
        """Test JIT provisioning for new user."""
        sso_response = {
            "email": "newuser@company.com",
            "first_name": "New",
            "last_name": "User",
            "groups": ["employees"],
            "provider": "okta"
        }

        with patch.object(self.service, '_user_exists') as mock_exists, \
             patch.object(self.service, '_create_new_user') as mock_create:

            mock_exists.return_value = False
            mock_create.return_value = {
                "id": str(uuid4()),
                "email": "newuser@company.com",
                "provisioned_via": "jit_sso"
            }

            result = await self.service.handle_jit_provisioning(sso_response)

            assert result["action"] == "user_created"
            assert result["user"]["email"] == "newuser@company.com"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_jit_provisioning_existing_user(self):
        """Test JIT provisioning for existing user."""
        sso_response = {
            "email": "existinguser@company.com",
            "first_name": "Existing",
            "last_name": "User",
            "groups": ["employees", "managers"],
            "provider": "azure_ad"
        }

        with patch.object(self.service, '_user_exists') as mock_exists, \
             patch.object(self.service, '_update_user_from_sso') as mock_update:

            mock_exists.return_value = True
            mock_update.return_value = {
                "id": str(uuid4()),
                "email": "existinguser@company.com",
                "updated_attributes": ["groups"]
            }

            result = await self.service.handle_jit_provisioning(sso_response)

            assert result["action"] == "user_updated"
            assert result["user"]["email"] == "existinguser@company.com"
            mock_update.assert_called_once()


class TestSessionManagement:
    """Test SSO session management."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_create_sso_session(self):
        """Test SSO session creation."""
        user_data = {
            "id": str(uuid4()),
            "email": "user@company.com",
            "provider": "okta"
        }

        session_data = {
            "saml_session_id": "saml_session_123",
            "provider_session_id": "provider_session_456"
        }

        result = await self.service.create_sso_session(user_data, session_data)

        assert result["session_id"] is not None
        assert result["user_id"] == user_data["id"]
        assert result["provider"] == "okta"

    @pytest.mark.asyncio
    async def test_validate_sso_session(self):
        """Test SSO session validation."""
        session_id = "sso_session_789"

        with patch.object(self.service, '_get_session_from_redis') as mock_get_session:
            mock_get_session.return_value = {
                "user_id": str(uuid4()),
                "provider": "azure_ad",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=8)).isoformat(),
                "valid": True
            }

            result = await self.service.validate_sso_session(session_id)

            assert result["valid"] is True
            assert result["user_id"] is not None
            assert result["provider"] == "azure_ad"

    @pytest.mark.asyncio
    async def test_invalidate_sso_session(self):
        """Test SSO session invalidation."""
        session_id = "sso_session_to_invalidate"

        with patch.object(self.service, '_remove_session_from_redis') as mock_remove:
            result = await self.service.invalidate_sso_session(session_id)

            assert result["success"] is True
            mock_remove.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_single_logout_initiation(self):
        """Test Single Logout (SLO) initiation."""
        session_id = "sso_session_logout"
        provider_config = {
            "protocol": "saml2",
            "slo_url": "https://provider.com/saml/slo"
        }

        with patch.object(self.service, '_build_saml_logout_request') as mock_logout:
            mock_logout.return_value = {
                "logout_url": "https://provider.com/saml/slo?SAMLRequest=...",
                "logout_id": "logout_123"
            }

            result = await self.service.initiate_single_logout(session_id, provider_config)

            assert result["logout_url"] is not None
            assert result["logout_id"] is not None


class TestErrorHandling:
    """Test error handling scenarios in SSO service."""

    def setup_method(self):
        """Setup for each test."""
        from unittest.mock import Mock, AsyncMock
        
        # Create mock dependencies
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_jwt_service = AsyncMock()
        
        self.service = SSOService(mock_db, mock_cache, mock_jwt_service)

    @pytest.mark.asyncio
    async def test_handle_saml_parsing_error(self):
        """Test handling of SAML parsing errors."""
        invalid_saml = "<invalid>malformed xml"

        result = await self.service.process_saml_response(invalid_saml, "req_123")

        assert result["success"] is False
        assert "parsing" in result["error"].lower() or "xml" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_oidc_discovery_failure(self):
        """Test handling of OIDC discovery failures."""
        provider_config = {
            "discovery_url": "https://invalid.provider.com/.well-known/openid_configuration"
        }

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("Discovery endpoint unreachable")

            result = await self.service.initiate_oidc_login("invalid_provider", provider_config)

            assert result["success"] is False
            assert "discovery" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_certificate_validation_error(self):
        """Test handling of certificate validation errors."""
        provider_config = {
            "x509_cert": "-----BEGIN CERTIFICATE-----\nINVALID_CERT\n-----END CERTIFICATE-----"
        }

        with patch('cryptography.x509.load_pem_x509_certificate') as mock_cert:
            mock_cert.side_effect = Exception("Invalid certificate format")

            result = await self.service.validate_provider_certificate(provider_config)

            assert result["valid"] is False
            assert "certificate" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_redis_connection_failure(self):
        """Test handling of Redis connection failures for session storage."""
        with patch.object(self.service, 'redis_client') as mock_redis:
            mock_redis.set.side_effect = Exception("Redis connection failed")

            user_data = {"id": str(uuid4()), "email": "test@company.com"}
            session_data = {"provider_session_id": "session_123"}

            result = await self.service.create_sso_session(user_data, session_data)

            assert result["success"] is False
            assert "redis" in result["error"].lower() or "session storage" in result["error"].lower()