"""
OpenID Connect (OIDC) protocol implementation
"""

import base64
import secrets
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives import serialization

from .base import SSOProtocol
from ...exceptions import AuthenticationError, ValidationError


class OIDCProtocol(SSOProtocol):
    """OpenID Connect protocol implementation"""
    
    def __init__(self, cache_service, attribute_mapper):
        self.cache_service = cache_service
        self.attribute_mapper = attribute_mapper
        self._jwks_cache = {}
    
    def get_protocol_name(self) -> str:
        return "oidc"
    
    def get_required_config_fields(self) -> list[str]:
        return [
            "issuer",
            "client_id",
            "client_secret",
            "authorization_endpoint",
            "token_endpoint",
            "redirect_uri"
        ]
    
    async def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate OIDC configuration"""
        required_fields = self.get_required_config_fields()
        
        # Check required fields
        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required OIDC field: {field}")
        
        # Validate URLs
        for url_field in ["authorization_endpoint", "token_endpoint", "redirect_uri"]:
            url = config.get(url_field, "")
            if not url.startswith(("http://", "https://")):
                raise ValidationError(f"Invalid URL format for {url_field}")
        
        # Validate issuer
        issuer = config.get("issuer", "")
        if not issuer.startswith(("http://", "https://")):
            raise ValidationError("Invalid issuer URL format")
        
        return True
    
    async def initiate_authentication(
        self,
        organization_id: str,
        return_url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Initiate OIDC authentication flow"""
        
        if not config:
            raise ValidationError("OIDC configuration is required")
        
        # Validate configuration
        await self.validate_configuration(config)
        
        # Generate state and nonce for security
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        
        # Store state and request data
        request_state = {
            "organization_id": organization_id,
            "return_url": return_url,
            "nonce": nonce,
            "timestamp": datetime.utcnow().isoformat(),
            "config": config
        }
        
        if self.cache_service:
            await self.cache_service.set(
                f"oidc_state:{state}",
                request_state,
                ttl=600  # 10 minutes
            )
        
        # Build authorization URL
        auth_params = {
            "response_type": "code",
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": " ".join(config.get("scopes", ["openid", "profile", "email"])),
            "state": state,
            "nonce": nonce
        }
        
        # Add optional parameters
        if config.get("prompt"):
            auth_params["prompt"] = config["prompt"]
        
        if config.get("max_age"):
            auth_params["max_age"] = config["max_age"]
        
        auth_url = f"{config['authorization_endpoint']}?{urlencode(auth_params)}"
        
        return {
            "auth_url": auth_url,
            "protocol": self.get_protocol_name(),
            "state": state,
            "nonce": nonce,
            "params": auth_params
        }
    
    async def handle_callback(
        self,
        callback_data: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Handle OIDC authorization callback"""
        
        code = callback_data.get("code")
        state = callback_data.get("state")
        error = callback_data.get("error")
        
        if error:
            error_description = callback_data.get("error_description", "Unknown error")
            raise AuthenticationError(f"OIDC error: {error} - {error_description}")
        
        if not code or not state:
            raise AuthenticationError("Missing authorization code or state")
        
        # Retrieve and validate state
        request_state = await self.cache_service.get(f"oidc_state:{state}")
        if not request_state:
            raise AuthenticationError("Invalid or expired state parameter")
        
        config = request_state["config"]
        
        # Exchange code for tokens
        tokens = await self._exchange_authorization_code(code, config)
        
        # Validate and decode ID token
        id_token_payload = await self._validate_id_token(
            tokens["id_token"],
            config,
            request_state["nonce"]
        )
        
        # Get user info if userinfo endpoint available
        user_info = {}
        if config.get("userinfo_endpoint") and tokens.get("access_token"):
            user_info = await self._fetch_user_info(
                tokens["access_token"],
                config["userinfo_endpoint"]
            )
        
        # Combine claims from ID token and userinfo
        user_claims = {**id_token_payload, **user_info}
        
        # Map claims to user data
        user_data = self.attribute_mapper.map_oidc_claims(
            user_claims,
            config.get("attribute_mapping", {})
        )
        
        # Clean up state
        await self.cache_service.delete(f"oidc_state:{state}")
        
        return {
            "user_data": user_data,
            "session_data": {
                "tokens": tokens,
                "claims": user_claims,
                "protocol": self.get_protocol_name()
            },
            "return_url": request_state.get("return_url"),
            "organization_id": request_state["organization_id"]
        }
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        
        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_endpoint"],
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                raise AuthenticationError(f"Token refresh failed: {response.text}")
            
            return response.json()
    
    async def revoke_token(
        self,
        token: str,
        config: Dict[str, Any],
        token_type: str = "access_token"
    ) -> bool:
        """Revoke access or refresh token"""
        
        if not config.get("revocation_endpoint"):
            return True  # No revocation endpoint available
        
        revoke_data = {
            "token": token,
            "token_type_hint": token_type,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["revocation_endpoint"],
                data=revoke_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # RFC 7009: successful revocation returns 200 or 200-level response
            return 200 <= response.status_code < 300
    
    async def _exchange_authorization_code(
        self,
        code: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "client_id": config["client_id"],
            "client_secret": config["client_secret"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_endpoint"],
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                raise AuthenticationError(f"Token exchange failed: {response.text}")
            
            return response.json()
    
    async def _validate_id_token(
        self,
        id_token: str,
        config: Dict[str, Any],
        expected_nonce: str
    ) -> Dict[str, Any]:
        """Validate and decode ID token"""
        
        try:
            # Decode without verification first to get header
            header = jwt.get_unverified_header(id_token)
            
            # Get signing key
            signing_key = await self._get_signing_key(header.get("kid"), config)
            
            # Verify and decode token
            payload = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256", "HS256"],
                audience=config["client_id"],
                issuer=config["issuer"]
            )
            
            # Validate nonce
            if payload.get("nonce") != expected_nonce:
                raise AuthenticationError("Invalid nonce in ID token")
            
            # Validate expiration
            if payload.get("exp", 0) < datetime.utcnow().timestamp():
                raise AuthenticationError("ID token has expired")
            
            return payload
            
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid ID token: {str(e)}")
    
    async def _get_signing_key(
        self,
        kid: Optional[str],
        config: Dict[str, Any]
    ) -> str:
        """Get signing key for token validation"""
        
        jwks_uri = config.get("jwks_uri")
        if not jwks_uri:
            # Use client secret for HS256
            return config["client_secret"]
        
        # Fetch JWKS if not cached
        cache_key = f"jwks:{config['issuer']}"
        jwks = self._jwks_cache.get(cache_key)
        
        if not jwks:
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                jwks = response.json()
                self._jwks_cache[cache_key] = jwks
        
        # Find key by kid
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                # Convert JWK to PEM format
                return self._jwk_to_pem(key)
        
        raise AuthenticationError(f"Unable to find signing key with kid: {kid}")
    
    def _jwk_to_pem(self, jwk: Dict[str, Any]) -> str:
        """Convert JWK to PEM format"""
        
        if jwk.get("kty") != "RSA":
            raise AuthenticationError("Only RSA keys are supported")
        
        try:
            # Decode base64url-encoded values
            n = self._base64url_decode(jwk["n"])
            e = self._base64url_decode(jwk["e"])
            
            # Create RSA public key
            from cryptography.hazmat.primitives.asymmetric import rsa
            public_numbers = rsa.RSAPublicNumbers(
                int.from_bytes(e, "big"),
                int.from_bytes(n, "big")
            )
            public_key = public_numbers.public_key()
            
            # Convert to PEM
            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return pem.decode()
            
        except Exception as e:
            raise AuthenticationError(f"Failed to convert JWK to PEM: {str(e)}")
    
    def _base64url_decode(self, data: str) -> bytes:
        """Decode base64url-encoded data"""
        # Add padding if necessary
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        
        return base64.urlsafe_b64decode(data)
    
    async def _fetch_user_info(
        self,
        access_token: str,
        userinfo_endpoint: str
    ) -> Dict[str, Any]:
        """Fetch user information from userinfo endpoint"""
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(userinfo_endpoint, headers=headers)
            
            if response.status_code != 200:
                raise AuthenticationError(f"Failed to fetch user info: {response.text}")
            
            return response.json()