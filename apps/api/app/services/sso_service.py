"""
SSO/SAML service for enterprise authentication
"""

import base64
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from urllib.parse import urlencode, quote

import httpx
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.sso import SSOConfiguration, SSOSession, IDPMetadata, SSOProvider, SSOStatus
from ..models import User, Organization
from ..exceptions import AuthenticationError, ValidationError
from .jwt_service import JWTService
from .cache import CacheService


class SSOService:
    """Service for handling SSO/SAML authentication"""
    
    def __init__(self, db: AsyncSession, cache: CacheService, jwt_service: JWTService):
        self.db = db
        self.cache = cache
        self.jwt_service = jwt_service
        
    async def configure_sso(
        self,
        organization_id: str,
        provider: SSOProvider,
        config: Dict[str, Any]
    ) -> SSOConfiguration:
        """Configure SSO for an organization"""
        
        # Check if configuration already exists
        stmt = select(SSOConfiguration).where(
            SSOConfiguration.organization_id == organization_id
        )
        existing = await self.db.execute(stmt)
        sso_config = existing.scalar_one_or_none()
        
        if not sso_config:
            sso_config = SSOConfiguration(
                organization_id=organization_id,
                provider=provider
            )
            self.db.add(sso_config)
        
        # Update configuration based on provider
        if provider == SSOProvider.SAML:
            await self._configure_saml(sso_config, config)
        elif provider == SSOProvider.OIDC:
            await self._configure_oidc(sso_config, config)
        else:
            raise ValidationError(f"Unsupported SSO provider: {provider}")
        
        # Common settings
        sso_config.jit_provisioning = config.get('jit_provisioning', True)
        sso_config.default_role = config.get('default_role', 'member')
        sso_config.attribute_mapping = config.get('attribute_mapping', {})
        sso_config.allowed_domains = config.get('allowed_domains', [])
        sso_config.status = SSOStatus.ACTIVE
        sso_config.enabled = True
        
        await self.db.commit()
        await self.db.refresh(sso_config)
        
        return sso_config
    
    async def _configure_saml(self, sso_config: SSOConfiguration, config: Dict[str, Any]):
        """Configure SAML-specific settings"""
        
        # If metadata URL provided, fetch and parse it
        if config.get('idp_metadata_url'):
            metadata = await self._fetch_idp_metadata(config['idp_metadata_url'])
            parsed = self._parse_saml_metadata(metadata)
            
            sso_config.saml_metadata_url = config['idp_metadata_url']
            sso_config.saml_metadata_xml = metadata
            sso_config.saml_sso_url = parsed['sso_url']
            sso_config.saml_slo_url = parsed.get('slo_url')
            sso_config.saml_certificate = parsed['certificate']
            sso_config.saml_entity_id = parsed['entity_id']
        else:
            # Manual configuration
            sso_config.saml_sso_url = config['sso_url']
            sso_config.saml_slo_url = config.get('slo_url')
            sso_config.saml_certificate = config['certificate']
            sso_config.saml_entity_id = config.get('entity_id')
        
        # SP configuration
        sso_config.saml_acs_url = config.get('acs_url', f"https://api.plinto.dev/v1/sso/saml/callback")
        
        # Security settings
        sso_config.sign_request = config.get('sign_request', True)
        sso_config.encrypt_assertion = config.get('encrypt_assertion', False)
    
    async def _configure_oidc(self, sso_config: SSOConfiguration, config: Dict[str, Any]):
        """Configure OIDC-specific settings"""
        
        sso_config.oidc_issuer = config['issuer']
        sso_config.oidc_client_id = config['client_id']
        sso_config.oidc_client_secret = self._encrypt_secret(config['client_secret'])
        
        # If discovery URL provided, fetch endpoints
        if config.get('discovery_url'):
            discovery = await self._fetch_oidc_discovery(config['discovery_url'])
            sso_config.oidc_discovery_url = config['discovery_url']
            sso_config.oidc_authorization_url = discovery['authorization_endpoint']
            sso_config.oidc_token_url = discovery['token_endpoint']
            sso_config.oidc_userinfo_url = discovery['userinfo_endpoint']
            sso_config.oidc_jwks_url = discovery['jwks_uri']
        else:
            # Manual configuration
            sso_config.oidc_authorization_url = config['authorization_url']
            sso_config.oidc_token_url = config['token_url']
            sso_config.oidc_userinfo_url = config.get('userinfo_url')
            sso_config.oidc_jwks_url = config.get('jwks_url')
        
        sso_config.oidc_scopes = config.get('scopes', ['openid', 'profile', 'email'])
    
    async def initiate_saml_sso(
        self,
        organization_id: str,
        return_url: Optional[str] = None
    ) -> Dict[str, str]:
        """Initiate SAML SSO flow"""
        
        # Get SSO configuration
        sso_config = await self._get_sso_config(organization_id)
        if not sso_config or sso_config.provider != SSOProvider.SAML:
            raise ValidationError("SAML SSO not configured for this organization")
        
        # Create SAML request
        saml_settings = self._get_saml_settings(sso_config)
        auth = OneLogin_Saml2_Auth({}, saml_settings)
        
        # Generate SAML AuthnRequest
        saml_request = auth.login(return_to=return_url)
        
        # Store request ID for validation
        request_id = str(uuid.uuid4())
        await self.cache.set(
            f"saml_request:{request_id}",
            {
                'organization_id': organization_id,
                'return_url': return_url,
                'timestamp': datetime.utcnow().isoformat()
            },
            ttl=600  # 10 minutes
        )
        
        return {
            'sso_url': sso_config.saml_sso_url,
            'saml_request': saml_request,
            'relay_state': request_id
        }
    
    async def handle_saml_response(
        self,
        saml_response: str,
        relay_state: str
    ) -> Dict[str, Any]:
        """Handle SAML response and create user session"""
        
        # Get stored request data
        request_data = await self.cache.get(f"saml_request:{relay_state}")
        if not request_data:
            raise AuthenticationError("Invalid or expired SAML request")
        
        organization_id = request_data['organization_id']
        
        # Get SSO configuration
        sso_config = await self._get_sso_config(organization_id)
        
        # Validate SAML response
        saml_settings = self._get_saml_settings(sso_config)
        auth = OneLogin_Saml2_Auth({'SAMLResponse': saml_response}, saml_settings)
        
        auth.process_response()
        
        if not auth.is_authenticated():
            errors = auth.get_errors()
            raise AuthenticationError(f"SAML authentication failed: {errors}")
        
        # Extract attributes
        attributes = auth.get_attributes()
        name_id = auth.get_nameid()
        session_index = auth.get_session_index()
        
        # Map attributes to user data
        user_data = self._map_saml_attributes(attributes, sso_config.attribute_mapping)
        
        # Create or update user (JIT provisioning)
        user = await self._provision_user(
            email=user_data['email'],
            attributes=user_data,
            organization_id=organization_id,
            sso_config=sso_config
        )
        
        # Create SSO session
        sso_session = SSOSession(
            user_id=user.id,
            sso_configuration_id=sso_config.id,
            session_index=session_index,
            name_id=name_id,
            attributes=attributes,
            expires_at=datetime.utcnow() + timedelta(hours=8)
        )
        self.db.add(sso_session)
        await self.db.commit()
        
        # Generate JWT token
        token = self.jwt_service.create_token(user.id)
        
        # Clean up cache
        await self.cache.delete(f"saml_request:{relay_state}")
        
        return {
            'user': user,
            'token': token,
            'return_url': request_data.get('return_url')
        }
    
    async def initiate_oidc_sso(
        self,
        organization_id: str,
        return_url: Optional[str] = None
    ) -> Dict[str, str]:
        """Initiate OIDC SSO flow"""
        
        # Get SSO configuration
        sso_config = await self._get_sso_config(organization_id)
        if not sso_config or sso_config.provider != SSOProvider.OIDC:
            raise ValidationError("OIDC SSO not configured for this organization")
        
        # Generate state and nonce
        state = str(uuid.uuid4())
        nonce = str(uuid.uuid4())
        
        # Store state for validation
        await self.cache.set(
            f"oidc_state:{state}",
            {
                'organization_id': organization_id,
                'nonce': nonce,
                'return_url': return_url,
                'timestamp': datetime.utcnow().isoformat()
            },
            ttl=600  # 10 minutes
        )
        
        # Build authorization URL
        params = {
            'client_id': sso_config.oidc_client_id,
            'response_type': 'code',
            'redirect_uri': f"https://api.plinto.dev/v1/sso/oidc/callback",
            'scope': ' '.join(sso_config.oidc_scopes),
            'state': state,
            'nonce': nonce
        }
        
        auth_url = f"{sso_config.oidc_authorization_url}?{urlencode(params)}"
        
        return {
            'auth_url': auth_url,
            'state': state
        }
    
    async def handle_oidc_callback(
        self,
        code: str,
        state: str
    ) -> Dict[str, Any]:
        """Handle OIDC callback and exchange code for tokens"""
        
        # Validate state
        state_data = await self.cache.get(f"oidc_state:{state}")
        if not state_data:
            raise AuthenticationError("Invalid or expired state")
        
        organization_id = state_data['organization_id']
        nonce = state_data['nonce']
        
        # Get SSO configuration
        sso_config = await self._get_sso_config(organization_id)
        
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                sso_config.oidc_token_url,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': f"https://api.plinto.dev/v1/sso/oidc/callback",
                    'client_id': sso_config.oidc_client_id,
                    'client_secret': self._decrypt_secret(sso_config.oidc_client_secret)
                }
            )
            
            if response.status_code != 200:
                raise AuthenticationError("Failed to exchange code for tokens")
            
            tokens = response.json()
        
        # Validate ID token
        id_token_claims = await self._validate_id_token(
            tokens['id_token'],
            sso_config,
            nonce
        )
        
        # Get user info if endpoint available
        user_info = {}
        if sso_config.oidc_userinfo_url and 'access_token' in tokens:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    sso_config.oidc_userinfo_url,
                    headers={'Authorization': f"Bearer {tokens['access_token']}"}
                )
                if response.status_code == 200:
                    user_info = response.json()
        
        # Merge claims
        attributes = {**id_token_claims, **user_info}
        
        # Map attributes to user data
        user_data = self._map_oidc_attributes(attributes, sso_config.attribute_mapping)
        
        # Create or update user (JIT provisioning)
        user = await self._provision_user(
            email=user_data['email'],
            attributes=user_data,
            organization_id=organization_id,
            sso_config=sso_config
        )
        
        # Create SSO session
        sso_session = SSOSession(
            user_id=user.id,
            sso_configuration_id=sso_config.id,
            idp_session_id=id_token_claims.get('sid'),
            attributes=attributes,
            expires_at=datetime.utcnow() + timedelta(hours=8)
        )
        self.db.add(sso_session)
        await self.db.commit()
        
        # Generate JWT token
        token = self.jwt_service.create_token(user.id)
        
        # Clean up cache
        await self.cache.delete(f"oidc_state:{state}")
        
        return {
            'user': user,
            'token': token,
            'return_url': state_data.get('return_url')
        }
    
    async def _provision_user(
        self,
        email: str,
        attributes: Dict[str, Any],
        organization_id: str,
        sso_config: SSOConfiguration
    ) -> User:
        """Create or update user via JIT provisioning"""
        
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user and sso_config.jit_provisioning:
            # Create new user
            user = User(
                email=email,
                email_verified=True,
                first_name=attributes.get('first_name'),
                last_name=attributes.get('last_name'),
                display_name=attributes.get('display_name'),
                user_metadata={
                    'sso': True,
                    'sso_provider': sso_config.provider.value,
                    'organization_id': organization_id
                }
            )
            self.db.add(user)
            
            # TODO: Add user to organization with default role
            
        elif user:
            # Update existing user attributes
            if attributes.get('first_name'):
                user.first_name = attributes['first_name']
            if attributes.get('last_name'):
                user.last_name = attributes['last_name']
            if attributes.get('display_name'):
                user.display_name = attributes['display_name']
            
            user.last_sign_in_at = datetime.utcnow()
        
        else:
            raise AuthenticationError("User provisioning disabled")
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def _get_sso_config(self, organization_id: str) -> Optional[SSOConfiguration]:
        """Get SSO configuration for organization"""
        
        stmt = select(SSOConfiguration).where(
            SSOConfiguration.organization_id == organization_id,
            SSOConfiguration.enabled == True,
            SSOConfiguration.status == SSOStatus.ACTIVE
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _fetch_idp_metadata(self, metadata_url: str) -> str:
        """Fetch IDP metadata from URL"""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(metadata_url)
            response.raise_for_status()
            return response.text
    
    async def _fetch_oidc_discovery(self, discovery_url: str) -> Dict[str, Any]:
        """Fetch OIDC discovery document"""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            return response.json()
    
    def _parse_saml_metadata(self, metadata_xml: str) -> Dict[str, Any]:
        """Parse SAML metadata XML"""
        
        # Parse XML
        root = etree.fromstring(metadata_xml.encode())
        
        # Extract values (simplified - real implementation would be more robust)
        ns = {'md': 'urn:oasis:names:tc:SAML:2.0:metadata'}
        
        entity_id = root.get('entityID')
        sso_service = root.find('.//md:SingleSignOnService', ns)
        slo_service = root.find('.//md:SingleLogoutService', ns)
        cert_elem = root.find('.//md:KeyDescriptor//ds:X509Certificate', 
                             {'md': ns['md'], 'ds': 'http://www.w3.org/2000/09/xmldsig#'})
        
        return {
            'entity_id': entity_id,
            'sso_url': sso_service.get('Location') if sso_service is not None else None,
            'slo_url': slo_service.get('Location') if slo_service is not None else None,
            'certificate': cert_elem.text if cert_elem is not None else None
        }
    
    def _get_saml_settings(self, sso_config: SSOConfiguration) -> Dict[str, Any]:
        """Build SAML settings for OneLogin library"""
        
        return {
            'sp': {
                'entityId': f"https://api.plinto.dev/saml/metadata",
                'assertionConsumerService': {
                    'url': sso_config.saml_acs_url,
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
                }
            },
            'idp': {
                'entityId': sso_config.saml_entity_id,
                'singleSignOnService': {
                    'url': sso_config.saml_sso_url,
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
                },
                'x509cert': sso_config.saml_certificate
            }
        }
    
    def _map_saml_attributes(
        self,
        attributes: Dict[str, List[str]],
        mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Map SAML attributes to user data"""
        
        result = {}
        
        # Default mappings
        default_mapping = {
            'email': ['http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress', 'email'],
            'first_name': ['http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname', 'firstName'],
            'last_name': ['http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname', 'lastName']
        }
        
        # Merge with custom mapping
        mapping = {**default_mapping, **mapping}
        
        for key, saml_attrs in mapping.items():
            if not isinstance(saml_attrs, list):
                saml_attrs = [saml_attrs]
            
            for attr in saml_attrs:
                if attr in attributes:
                    values = attributes[attr]
                    result[key] = values[0] if values else None
                    break
        
        return result
    
    def _map_oidc_attributes(
        self,
        claims: Dict[str, Any],
        mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Map OIDC claims to user data"""
        
        result = {}
        
        # Default mappings
        default_mapping = {
            'email': 'email',
            'first_name': 'given_name',
            'last_name': 'family_name',
            'display_name': 'name'
        }
        
        # Merge with custom mapping
        mapping = {**default_mapping, **mapping}
        
        for key, claim_name in mapping.items():
            if claim_name in claims:
                result[key] = claims[claim_name]
        
        return result
    
    async def _validate_id_token(
        self,
        id_token: str,
        sso_config: SSOConfiguration,
        nonce: str
    ) -> Dict[str, Any]:
        """Validate OIDC ID token"""
        
        # This is simplified - real implementation would use proper JWT validation
        # with JWKS endpoint and signature verification
        
        import jwt
        
        # Decode without verification for now (NOT FOR PRODUCTION)
        claims = jwt.decode(id_token, options={"verify_signature": False})
        
        # Validate claims
        if claims.get('nonce') != nonce:
            raise AuthenticationError("Invalid nonce")
        
        if claims.get('iss') != sso_config.oidc_issuer:
            raise AuthenticationError("Invalid issuer")
        
        if claims.get('aud') != sso_config.oidc_client_id:
            raise AuthenticationError("Invalid audience")
        
        # Check expiration
        if claims.get('exp', 0) < datetime.utcnow().timestamp():
            raise AuthenticationError("ID token expired")
        
        return claims
    
    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt sensitive data"""
        # Simplified - real implementation would use proper encryption
        return base64.b64encode(secret.encode()).decode()
    
    def _decrypt_secret(self, encrypted: str) -> str:
        """Decrypt sensitive data"""
        # Simplified - real implementation would use proper decryption
        return base64.b64decode(encrypted).decode()