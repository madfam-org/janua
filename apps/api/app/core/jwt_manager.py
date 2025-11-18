"""
Enhanced JWT Manager with Refresh Token Rotation
Enterprise-grade JWT handling with security best practices
"""

import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import jwt
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database_manager import get_db_session

logger = structlog.get_logger()


class JWTManager:
    """Centralized JWT token management with refresh token rotation"""

    def __init__(self):
        # Get algorithm from settings, fallback to HS256 for test environment
        self.algorithm = settings.JWT_ALGORITHM

        # For test environment or when JWT_SECRET_KEY is a simple string, use HS256
        # RS256 requires PEM-formatted keys which are not suitable for simple string secrets
        if settings.ENVIRONMENT == "test" or (
            settings.JWT_SECRET_KEY and not settings.JWT_SECRET_KEY.startswith("-----BEGIN")
        ):
            self.algorithm = "HS256"

        self.secret_key = settings.JWT_SECRET_KEY or settings.SECRET_KEY
        self.issuer = settings.JWT_ISSUER
        self.audience = settings.JWT_AUDIENCE

        # Token expiration settings
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(
        self, user_id: str, email: str, additional_claims: Optional[Dict[str, Any]] = None
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
        self, user_id: str, family: Optional[str] = None
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

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
            )

            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(
                    "Token type mismatch",
                    expected=token_type,
                    got=payload.get("type"),
                    jti=payload.get("jti"),
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
        additional_claims: Optional[Dict[str, Any]] = None,
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
        self, refresh_token: str, db: AsyncSession
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

        # Check if refresh token is blacklisted in Redis
        from app.core.database import get_redis

        redis_client = await get_redis()

        # Check blacklist
        is_blacklisted = await redis_client.exists(f"blacklist:refresh:{refresh_jti}")
        if is_blacklisted:
            logger.warning("Attempted use of blacklisted refresh token", jti=refresh_jti)
            return None

        # Check session status in database
        from app.models import Session as UserSession

        session_result = await db.execute(
            select(UserSession).where(
                and_(UserSession.refresh_token_jti == refresh_jti, UserSession.user_id == user_id)
            )
        )
        session = session_result.scalar_one_or_none()

        if not session:
            logger.warning("No session found for refresh token", jti=refresh_jti, user_id=user_id)
            return None

        if session.revoked:
            logger.warning("Attempted use of revoked session", session_id=str(session.id))
            return None

        # Check session expiration
        if session.expires_at and session.expires_at < datetime.utcnow():
            logger.info("Session expired", session_id=str(session.id))
            return None

        # Check for token reuse (security concern)
        # If a refresh token is used twice, it might indicate token theft
        # In production, you'd want to revoke the entire token family

        try:
            # Get user from database for email
            from app.models import User

            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning("User not found during token refresh", user_id=user_id)
                return None

            # Create new token pair
            access_token, new_access_jti, access_expires = self.create_access_token(
                user_id, user.email
            )
            new_refresh_token, new_refresh_jti, _, refresh_expires = self.create_refresh_token(
                user_id,
                family,  # Keep same family for rotation tracking
            )

            # Blacklist old refresh token
            await self.blacklist_token(refresh_jti, "refresh")

            # Update session with new JTIs
            session.access_token_jti = new_access_jti
            session.refresh_token_jti = new_refresh_jti
            session.expires_at = refresh_expires

            await db.commit()

            logger.info(
                "Token pair refreshed",
                user_id=user_id,
                old_refresh_jti=refresh_jti,
                new_refresh_jti=new_refresh_jti,
                family=family,
            )

            return access_token, new_refresh_token

        except Exception as e:
            logger.error("Token refresh failed", error=str(e), user_id=user_id)
            return None

    async def blacklist_token(
        self, jti: str, token_type: str = "refresh", ttl: Optional[int] = None
    ) -> None:
        """
        Blacklist a token in Redis

        Args:
            jti: Token JTI (unique identifier)
            token_type: Type of token (access or refresh)
            ttl: Time to live in seconds (defaults to token expiry)
        """
        from app.core.database import get_redis

        redis_client = await get_redis()

        # Default TTL to remaining token lifetime
        if ttl is None:
            if token_type == "refresh":
                ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
            else:
                ttl = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        await redis_client.setex(f"blacklist:{token_type}:{jti}", ttl, "revoked")

        logger.info("Token blacklisted", jti=jti, token_type=token_type)

    async def revoke_token_family(
        self, family: str, reason: str = "security_revocation", db: Optional[AsyncSession] = None
    ):
        """
        Revoke entire token family for security
        Used when token reuse is detected or user logs out from all devices
        """
        from app.models import Session as UserSession

        if not db:
            return

        # Find all sessions in this token family
        sessions_result = await db.execute(
            select(UserSession).where(UserSession.refresh_token_family == family)
        )
        sessions = sessions_result.scalars().all()

        # Revoke all sessions and blacklist their tokens
        for session in sessions:
            session.revoked = True

            # Blacklist refresh token
            if session.refresh_token_jti:
                await self.blacklist_token(session.refresh_token_jti, "refresh")

            # Blacklist access token (shorter TTL)
            if session.access_token_jti:
                await self.blacklist_token(session.access_token_jti, "access")

        await db.commit()

        logger.warning(
            "Token family revoked", family=family, reason=reason, sessions_revoked=len(sessions)
        )

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
def create_access_token(
    user_id: str, email: str, claims: Optional[Dict] = None
) -> Tuple[str, str, datetime]:
    """Create access token - convenience function"""
    return jwt_manager.create_access_token(user_id, email, claims)


def create_refresh_token(
    user_id: str, family: Optional[str] = None
) -> Tuple[str, str, str, datetime]:
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


async def get_current_user(token: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Get current user from JWT token with database validation
    This is the core function used by FastAPI dependencies
    """
    # Verify the access token
    payload = jwt_manager.verify_token(token, "access")
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        # Import here to avoid circular imports
        from sqlalchemy import select

        from app.models import User, UserStatus

        # Get user from database
        result = await db.execute(
            select(User).where(User.id == user_id, User.status == UserStatus.ACTIVE)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("User not found or inactive", user_id=user_id)
            return None

        # Return user data with token info
        return {
            "user": user,
            "token_payload": payload,
            "user_id": user_id,
            "email": payload.get("email"),
            "jti": payload.get("jti"),
        }

    except Exception as e:
        logger.error("Error getting current user", error=str(e), user_id=user_id)
        return None
