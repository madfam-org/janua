"""
SAML 2.0 protocol implementation
"""

import base64
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    SAML_AVAILABLE = True
except ImportError:
    SAML_AVAILABLE = False
    OneLogin_Saml2_Auth = None

from .base import SSOProtocol
from ...exceptions import AuthenticationError, ValidationError


class SAMLProtocol(SSOProtocol):
    """SAML 2.0 protocol implementation"""
    
    def __init__(self, cache_service, attribute_mapper):
        self.cache_service = cache_service
        self.attribute_mapper = attribute_mapper
    
    def get_protocol_name(self) -> str:
        return "saml2"
    
    def get_required_config_fields(self) -> list[str]:
        return [
            "entity_id",
            "sso_url", 
            "certificate",
            "acs_url"
        ]
    
    async def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate SAML configuration"""
        required_fields = self.get_required_config_fields()
        
        # Check required fields
        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required SAML field: {field}")
        
        # Validate certificate format
        certificate = config.get("certificate", "")
        if not self._validate_certificate(certificate):
            raise ValidationError("Invalid certificate format")
        
        # Validate URLs
        sso_url = config.get("sso_url", "")
        if not sso_url.startswith(("http://", "https://")):
            raise ValidationError("Invalid SSO URL format")
        
        return True
    
    async def initiate_authentication(
        self,
        organization_id: str,
        return_url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Initiate SAML authentication flow"""
        
        if not config:
            raise ValidationError("SAML configuration is required")
        
        # Validate configuration
        await self.validate_configuration(config)
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Create SAML request
        if SAML_AVAILABLE:
            saml_settings = self._build_saml_settings(config)
            auth = OneLogin_Saml2_Auth({}, saml_settings)
            saml_request = auth.login(return_to=return_url)
        else:
            # Mock for testing environments
            saml_request = base64.b64encode(
                f"<samlp:AuthnRequest ID='{request_id}' />".encode()
            ).decode()
        
        # Store request state
        request_state = {
            "organization_id": organization_id,
            "return_url": return_url,
            "timestamp": datetime.utcnow().isoformat(),
            "config": config
        }
        
        if self.cache_service:
            await self.cache_service.set(
                f"saml_request:{request_id}",
                request_state,
                ttl=600  # 10 minutes
            )
        
        return {
            "auth_url": config["sso_url"],
            "protocol": self.get_protocol_name(),
            "request_id": request_id,
            "saml_request": saml_request,
            "relay_state": request_id,
            "params": {
                "SAMLRequest": saml_request,
                "RelayState": request_id
            }
        }
    
    async def handle_callback(
        self,
        callback_data: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Handle SAML response callback"""
        
        saml_response = callback_data.get("SAMLResponse")
        relay_state = callback_data.get("RelayState")
        
        if not saml_response or not relay_state:
            raise AuthenticationError("Missing SAML response or relay state")
        
        # Retrieve request state
        request_state = await self.cache_service.get(f"saml_request:{relay_state}")
        if not request_state:
            raise AuthenticationError("Invalid or expired SAML request")
        
        config = request_state["config"]
        
        # Process SAML response
        if SAML_AVAILABLE:
            saml_settings = self._build_saml_settings(config)
            auth = OneLogin_Saml2_Auth(
                {"SAMLResponse": saml_response}, 
                saml_settings
            )
            auth.process_response()
            
            if not auth.is_authenticated():
                errors = auth.get_errors()
                raise AuthenticationError(f"SAML authentication failed: {errors}")
            
            # Extract user data
            attributes = auth.get_attributes()
            name_id = auth.get_nameid()
            session_index = auth.get_session_index()
            
        else:
            # Mock response for testing
            attributes = {
                "email": ["test@example.com"],
                "firstName": ["Test"],
                "lastName": ["User"]
            }
            name_id = "test@example.com"
            session_index = str(uuid.uuid4())
        
        # Map attributes to user data
        user_data = self.attribute_mapper.map_saml_attributes(
            attributes,
            config.get("attribute_mapping", {})
        )
        
        # Clean up request state
        await self.cache_service.delete(f"saml_request:{relay_state}")
        
        return {
            "user_data": user_data,
            "session_data": {
                "name_id": name_id,
                "session_index": session_index,
                "attributes": attributes,
                "protocol": self.get_protocol_name()
            },
            "return_url": request_state.get("return_url"),
            "organization_id": request_state["organization_id"]
        }
    
    async def initiate_logout(
        self,
        session_data: Dict[str, Any],
        config: Dict[str, Any],
        return_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate SAML Single Logout (SLO)"""
        
        if not config.get("slo_url"):
            raise ValidationError("SLO URL not configured")
        
        if SAML_AVAILABLE:
            saml_settings = self._build_saml_settings(config)
            auth = OneLogin_Saml2_Auth({}, saml_settings)
            
            slo_request = auth.logout(
                return_to=return_url,
                name_id=session_data.get("name_id"),
                session_index=session_data.get("session_index")
            )
        else:
            # Mock for testing
            slo_request = base64.b64encode(
                f"<samlp:LogoutRequest />".encode()
            ).decode()
        
        return {
            "logout_url": config["slo_url"],
            "saml_request": slo_request,
            "params": {
                "SAMLRequest": slo_request
            }
        }
    
    def _build_saml_settings(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build SAML settings for OneLogin library"""
        
        return {
            "sp": {
                "entityId": config.get("sp_entity_id", "https://api.janua.dev"),
                "assertionConsumerService": {
                    "url": config["acs_url"],
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                },
                "singleLogoutService": {
                    "url": config.get("sp_slo_url", ""),
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "NameIDFormat": config.get(
                    "name_id_format", 
                    "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
                )
            },
            "idp": {
                "entityId": config["entity_id"],
                "singleSignOnService": {
                    "url": config["sso_url"],
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "singleLogoutService": {
                    "url": config.get("slo_url", ""),
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "x509cert": config["certificate"]
            },
            "security": {
                "nameIdEncrypted": False,
                "authnRequestsSigned": config.get("sign_request", False),
                "logoutRequestSigned": config.get("sign_logout_request", False),
                "logoutResponseSigned": config.get("sign_logout_response", False),
                "signMetadata": False,
                "wantAssertionsSigned": config.get("want_assertions_signed", True),
                "wantNameId": True,
                "wantAssertionsEncrypted": config.get("encrypt_assertion", False),
                "wantNameIdEncrypted": False,
                "requestedAuthnContext": True,
                "signatureAlgorithm": "http://www.w3.org/2000/09/xmldsig#rsa-sha1",
                "digestAlgorithm": "http://www.w3.org/2000/09/xmldsig#sha1"
            }
        }
    
    def _validate_certificate(self, certificate: str) -> bool:
        """Validate X.509 certificate format"""
        if not certificate:
            return False
        
        try:
            # Remove headers and whitespace
            cert_content = certificate.replace("-----BEGIN CERTIFICATE-----", "")
            cert_content = cert_content.replace("-----END CERTIFICATE-----", "")
            cert_content = cert_content.replace("\n", "").replace("\r", "").replace(" ", "")
            
            # Try to decode base64
            base64.b64decode(cert_content)
            return True
        except Exception:
            return False