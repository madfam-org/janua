"""
Enhanced JWT Manager with Refresh Token Rotation
Enterprise-grade JWT handling with security best practices
"""

import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import jwt
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import settings
from app.core.database_manager import get_db_session

logger = structlog.get_logger()


class JWTManager:
    """Centralized JWT token management with refresh token rotation"""

    def __init__(self):
        self.algorithm = settings.JWT_ALGORITHM
        self.secret_key = settings.JWT_SECRET_KEY or settings.SECRET_KEY
        self.issuer = settings.JWT_ISSUER
        self.audience = settings.JWT_AUDIENCE

        # Token expiration settings
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(
        self,
        user_id: str,
        email: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, datetime]:
        """Create a new access token with JTI for tracking"""
        jti = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "email": email,
            "jti": jti,
            "iat": now,
            "exp": expires_at,
            "type": "access",
            "iss": self.issuer,
            "aud": self.audience,
        }

        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.info("Access token created", user_id=user_id, jti=jti)
        return token, jti, expires_at

    def create_refresh_token(
        self,
        user_id: str,
        family: Optional[str] = None
    ) -> Tuple[str, str, str, datetime]:
        """Create a new refresh token with rotation family tracking"""
        jti = secrets.token_urlsafe(32)
        family = family or secrets.token_urlsafe(16)  # Create new family if not provided
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "jti": jti,
            "family": family,
            "iat": now,
            "exp": expires_at,
            "type": "refresh",
            "iss": self.issuer,
            "aud": self.audience,
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.info("Refresh token created", user_id=user_id, jti=jti, family=family)
        return token, jti, family, expires_at

    def verify_token(
        self,
        token: str,
        token_type: str = "access"
    ) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience
            )

            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(
                    "Token type mismatch",
                    expected=token_type,
                    got=payload.get("type"),
                    jti=payload.get("jti")
                )
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.info("Token expired", token_type=token_type)
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e), token_type=token_type)
            return None

    async def create_token_pair(
        self,
        user_id: str,
        email: str,
        session_id: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, dict]:
        """Create a matched access/refresh token pair"""
        # Create tokens
        access_token, access_jti, access_expires = self.create_access_token(
            user_id, email, additional_claims
        )
        refresh_token, refresh_jti, family, refresh_expires = self.create_refresh_token(user_id)

        # Token metadata for storage
        token_info = {
            "access_jti": access_jti,
            "refresh_jti": refresh_jti,
            "family": family,
            "access_expires": access_expires,
            "refresh_expires": refresh_expires,
            "session_id": session_id,
        }

        return access_token, refresh_token, token_info

    async def refresh_token_pair(
        self,
        refresh_token: str,
        db: AsyncSession
    ) -> Optional[Tuple[str, str]]:
        """
        Refresh token rotation with security checks
        Returns new access and refresh tokens, or None if invalid
        """
        # Verify the refresh token
        payload = self.verify_token(refresh_token, "refresh")
        if not payload:
            return None

        user_id = payload.get("sub")
        refresh_jti = payload.get("jti")
        family = payload.get("family")

        # TODO: Check if refresh token is blacklisted or session is revoked
        # This would require integration with session storage

        # Check for token reuse (security concern)
        # If a refresh token is used twice, it might indicate token theft
        # In production, you'd want to revoke the entire token family

        try:
            # Create new token pair
            # For now, we'll create new tokens without database integration
            # In full implementation, you'd:
            # 1. Check session validity in database
            # 2. Blacklist old refresh token
            # 3. Update session with new JTIs

            # Get user email (in production, fetch from database)
            user_email = "user@example.com"  # Placeholder

            access_token, new_access_jti, access_expires = self.create_access_token(
                user_id, user_email
            )
            new_refresh_token, new_refresh_jti, _, refresh_expires = self.create_refresh_token(
                user_id, family  # Keep same family for rotation tracking
            )

            logger.info(
                "Token pair refreshed",
                user_id=user_id,
                old_refresh_jti=refresh_jti,
                new_refresh_jti=new_refresh_jti,
                family=family
            )

            return access_token, new_refresh_token

        except Exception as e:
            logger.error("Token refresh failed", error=str(e), user_id=user_id)
            return None

    async def revoke_token_family(self, family: str, reason: str = "security_revocation"):
        """
        Revoke entire token family for security
        Used when token reuse is detected or user logs out from all devices
        """
        # TODO: Implement with session storage
        # Would blacklist all tokens in family and revoke associated sessions
        logger.warning("Token family revoked", family=family, reason=reason)

    def decode_token_unsafe(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token without verification (for debugging/logging only)
        NEVER use for authentication!
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except:
            return None


# Global JWT manager instance
jwt_manager = JWTManager()


# Convenience functions for FastAPI integration
def create_access_token(user_id: str, email: str, claims: Optional[Dict] = None) -> Tuple[str, str, datetime]:
    """Create access token - convenience function"""
    return jwt_manager.create_access_token(user_id, email, claims)


def create_refresh_token(user_id: str, family: Optional[str] = None) -> Tuple[str, str, str, datetime]:
    """Create refresh token - convenience function"""
    return jwt_manager.create_refresh_token(user_id, family)


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify access token - convenience function"""
    return jwt_manager.verify_token(token, "access")


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify refresh token - convenience function"""
    return jwt_manager.verify_token(token, "refresh")


async def refresh_tokens(refresh_token: str, db: AsyncSession) -> Optional[Tuple[str, str]]:
    """Refresh token pair - convenience function"""
    return await jwt_manager.refresh_token_pair(refresh_token, db)