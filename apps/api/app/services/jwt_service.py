"""
JWT Token Management Service
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, Tuple
from uuid import uuid4

import structlog
from jose import jwt, JWTError, jwk
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.config import settings
from app.models.token import TokenClaims, TokenPair
from app.exceptions import AuthenticationError, TokenError


logger = structlog.get_logger()


class JWTService:
    """
    Service for JWT token creation and verification
    """
    
    def __init__(self, db, redis):
        self.db = db
        self.redis = redis
        self._private_key = None
        self._public_key = None
        self._kid = None
    
    async def initialize(self):
        """
        Initialize JWT service with keys
        """
        # Load or generate keys
        await self._load_or_generate_keys()
    
    async def _load_or_generate_keys(self):
        """
        Load existing keys or generate new ones
        """
        # Try to load from database
        key_data = await self.db.fetchrow(
            """
            SELECT kid, private_key, public_key 
            FROM jwk_keys 
            WHERE tenant_id IS NULL 
            AND status = 'active'
            ORDER BY created_at DESC 
            LIMIT 1
            """
        )
        
        if key_data:
            self._kid = key_data['kid']
            self._private_key = key_data['private_key']
            self._public_key = key_data['public_key']
        else:
            # Generate new keys
            await self._generate_new_keys()
    
    async def _generate_new_keys(self):
        """
        Generate new RSA key pair
        """
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Generate key ID
        kid = str(uuid4())
        
        # Store in database
        await self.db.execute(
            """
            INSERT INTO jwk_keys (kid, private_key, public_key, status, created_at)
            VALUES ($1, $2, $3, 'active', $4)
            """,
            kid, private_pem, public_pem, datetime.utcnow()
        )
        
        self._kid = kid
        self._private_key = private_pem
        self._public_key = public_pem
        
        logger.info("Generated new JWT keys", kid=kid)
    
    async def create_tokens(
        self,
        identity_id: str,
        tenant_id: str,
        organization_id: Optional[str] = None,
        custom_claims: Optional[Dict[str, Any]] = None
    ) -> TokenPair:
        """
        Create access and refresh token pair
        """
        # Generate JTIs
        access_jti = str(uuid4())
        refresh_jti = str(uuid4())
        
        # Create access token claims
        now = datetime.now(timezone.utc)
        access_claims = {
            "sub": identity_id,
            "tid": tenant_id,
            "oid": organization_id,
            "iat": now,
            "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "nbf": now,
            "jti": access_jti,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "type": "access"
        }
        
        # Add custom claims
        if custom_claims:
            access_claims.update(custom_claims)
        
        # Create refresh token claims
        refresh_claims = {
            "sub": identity_id,
            "tid": tenant_id,
            "iat": now,
            "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            "jti": refresh_jti,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "type": "refresh"
        }
        
        # Sign tokens
        access_token = jwt.encode(
            access_claims,
            self._private_key,
            algorithm=settings.JWT_ALGORITHM,
            headers={"kid": self._kid}
        )
        
        refresh_token = jwt.encode(
            refresh_claims,
            self._private_key,
            algorithm=settings.JWT_ALGORITHM,
            headers={"kid": self._kid}
        )
        
        # Store JTIs in Redis for revocation checking
        await self.redis.setex(
            f"jti:access:{access_jti}",
            settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "1"
        )
        
        await self.redis.setex(
            f"jti:refresh:{refresh_jti}",
            settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            "1"
        )
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            token_type="Bearer"
        )
    
    async def verify_token(
        self,
        token: str,
        token_type: str = "access",
        verify_exp: bool = True
    ) -> TokenClaims:
        """
        Verify and decode JWT token
        """
        try:
            # Decode token
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
                options={"verify_exp": verify_exp}
            )
            
            # Verify token type
            if claims.get("type") != token_type:
                raise TokenError(f"Invalid token type: expected {token_type}")
            
            # Check if token is revoked
            jti = claims.get("jti")
            if jti:
                revoked = await self.redis.get(f"revoked:{jti}")
                if revoked:
                    raise TokenError("Token has been revoked")
                
                # Check if JTI exists (not expired)
                exists = await self.redis.get(f"jti:{token_type}:{jti}")
                if not exists:
                    raise TokenError("Token JTI not found or expired")
            
            return TokenClaims(**claims)
            
        except JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            raise AuthenticationError(f"Invalid token: {str(e)}")
    
    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """
        Refresh access token using refresh token
        """
        # Verify refresh token
        claims = await self.verify_token(refresh_token, token_type="refresh")
        
        # Check if refresh token was already used (rotation)
        used_key = f"used:refresh:{claims.jti}"
        if await self.redis.get(used_key):
            # Token reuse detected - revoke all tokens for this identity
            await self.revoke_all_tokens(claims.sub)
            raise AuthenticationError("Refresh token reuse detected")
        
        # Mark refresh token as used
        await self.redis.setex(
            used_key,
            settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            "1"
        )
        
        # Create new token pair
        return await self.create_tokens(
            identity_id=claims.sub,
            tenant_id=claims.tid,
            organization_id=claims.oid
        )
    
    async def revoke_token(self, jti: str, exp: datetime):
        """
        Revoke a token by JTI
        """
        # Calculate TTL until expiration
        ttl = int((exp - datetime.now(timezone.utc)).total_seconds())
        
        if ttl > 0:
            await self.redis.setex(f"revoked:{jti}", ttl, "1")
            logger.info("Token revoked", jti=jti)
    
    async def revoke_all_tokens(self, identity_id: str):
        """
        Revoke all tokens for an identity
        """
        # Get all sessions for the identity
        sessions = await self.db.fetch(
            """
            SELECT access_token_jti, refresh_token_hash, expires_at
            FROM sessions
            WHERE identity_id = $1 AND revoked_at IS NULL
            """,
            identity_id
        )
        
        # Revoke all tokens
        for session in sessions:
            if session['access_token_jti']:
                ttl = int((session['expires_at'] - datetime.now(timezone.utc)).total_seconds())
                if ttl > 0:
                    await self.redis.setex(
                        f"revoked:{session['access_token_jti']}",
                        ttl,
                        "1"
                    )
        
        # Mark sessions as revoked in database
        await self.db.execute(
            """
            UPDATE sessions 
            SET revoked_at = $1, revocation_reason = 'all_tokens_revoked'
            WHERE identity_id = $2 AND revoked_at IS NULL
            """,
            datetime.utcnow(), identity_id
        )
        
        logger.info("All tokens revoked for identity", identity_id=identity_id)
    
    async def get_public_jwks(self) -> Dict:
        """
        Get public keys in JWKS format
        """
        # Get all active public keys
        keys = await self.db.fetch(
            """
            SELECT kid, public_key, alg
            FROM jwk_keys
            WHERE status IN ('active', 'next')
            """
        )
        
        jwks = []
        for key in keys:
            # Convert PEM to JWK
            public_key = serialization.load_pem_public_key(
                key['public_key'].encode('utf-8'),
                backend=default_backend()
            )
            
            # Get public numbers
            numbers = public_key.public_numbers()
            
            # Create JWK
            jwk_data = {
                "kty": "RSA",
                "use": "sig",
                "kid": key['kid'],
                "alg": key['alg'] or "RS256",
                "n": self._encode_int(numbers.n),
                "e": self._encode_int(numbers.e)
            }
            
            jwks.append(jwk_data)
        
        return {"keys": jwks}
    
    @staticmethod
    def _encode_int(num: int) -> str:
        """
        Encode integer as base64url string
        """
        import base64
        
        # Convert to bytes
        num_bytes = num.to_bytes((num.bit_length() + 7) // 8, 'big')
        
        # Encode as base64url
        return base64.urlsafe_b64encode(num_bytes).decode('ascii').rstrip('=')
    
    async def rotate_keys(self):
        """
        Rotate JWT signing keys
        """
        # Generate new keys
        await self._generate_new_keys()
        
        # Mark old keys as 'next' (overlap period)
        await self.db.execute(
            """
            UPDATE jwk_keys 
            SET status = 'next', activated_at = $1
            WHERE status = 'active' AND kid != $2
            """,
            datetime.utcnow(), self._kid
        )
        
        # Schedule old key retirement (after overlap period)
        # This would typically be handled by a background job
        
        logger.info("JWT keys rotated", new_kid=self._kid)