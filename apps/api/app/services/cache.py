"""
Redis cache service for session management and caching
"""

import json
import logging
from typing import Optional, Any, Dict, List
import redis.asyncio as redis
import pickle

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis cache service for session management and general caching
    """

    _instance = None
    _redis_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # We'll handle encoding/decoding
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._redis_client

    async def close(self):
        """Close Redis connection"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

    async def set(
        self, key: str, value: Any, expire: Optional[int] = None, namespace: Optional[str] = None
    ) -> bool:
        """
        Set a value in cache

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: Expiration time in seconds
            namespace: Optional namespace prefix
        """
        try:
            client = await self.get_client()

            # Add namespace if provided
            if namespace:
                key = f"{namespace}:{key}"

            # Serialize value
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            elif isinstance(value, (str, int, float, bool)):
                serialized = str(value)
            else:
                # Use pickle for complex objects
                serialized = pickle.dumps(value)

            # Set with optional expiration
            if expire:
                await client.setex(key, expire, serialized)
            else:
                await client.set(key, serialized)

            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def get(self, key: str, namespace: Optional[str] = None, default: Any = None) -> Any:
        """
        Get a value from cache

        Args:
            key: Cache key
            namespace: Optional namespace prefix
            default: Default value if key not found
        """
        try:
            client = await self.get_client()

            # Add namespace if provided
            if namespace:
                key = f"{namespace}:{key}"

            value = await client.get(key)

            if value is None:
                return default

            # Try to deserialize
            try:
                # Try JSON first
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                try:
                    # Try as string
                    return value.decode("utf-8")
                except Exception:
                    # Try pickle for complex objects
                    try:
                        return pickle.loads(value)
                    except Exception:
                        return value

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default

    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete a key from cache"""
        try:
            client = await self.get_client()

            if namespace:
                key = f"{namespace}:{key}"

            await client.delete(key)
            return True

        except Exception as e:
            # SECURITY: Use parameterized logging to prevent log injection
            logger.error("Cache delete error", key=key, error=str(e))
            return False

    async def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """Check if key exists in cache"""
        try:
            client = await self.get_client()

            if namespace:
                key = f"{namespace}:{key}"

            return await client.exists(key) > 0

        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def expire(self, key: str, seconds: int, namespace: Optional[str] = None) -> bool:
        """Set expiration time for a key"""
        try:
            client = await self.get_client()

            if namespace:
                key = f"{namespace}:{key}"

            return await client.expire(key, seconds)

        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False

    async def get_all_keys(self, pattern: str = "*", namespace: Optional[str] = None) -> List[str]:
        """Get all keys matching pattern"""
        try:
            client = await self.get_client()

            if namespace:
                pattern = f"{namespace}:{pattern}"

            keys = await client.keys(pattern)
            return [k.decode("utf-8") if isinstance(k, bytes) else k for k in keys]

        except Exception as e:
            logger.error(f"Cache keys error for pattern {pattern}: {e}")
            return []

    # Session-specific methods

    async def store_session(
        self, session_id: str, user_id: str, data: Dict[str, Any], expire_minutes: int = None
    ) -> bool:
        """Store user session data"""
        expire = (
            expire_minutes * 60 if expire_minutes else settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

        session_data = {"user_id": user_id, "session_id": session_id, **data}

        return await self.set(
            key=session_id, value=session_data, expire=expire, namespace="session"
        )

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return await self.get(key=session_id, namespace="session")

    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        return await self.delete(key=session_id, namespace="session")

    async def extend_session(self, session_id: str, expire_minutes: int = None) -> bool:
        """Extend session expiration"""
        expire = (
            expire_minutes * 60 if expire_minutes else settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return await self.expire(key=session_id, seconds=expire, namespace="session")

    # Rate limiting methods

    async def check_rate_limit(
        self, identifier: str, limit: int, window_seconds: int, namespace: str = "rate_limit"
    ) -> tuple[bool, int]:
        """
        Check if rate limit is exceeded

        Returns:
            tuple: (is_allowed, remaining_requests)
        """
        try:
            client = await self.get_client()
            key = f"{namespace}:{identifier}"

            # Use Redis pipeline for atomic operations
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

            current_count = results[0]

            if current_count > limit:
                return False, 0

            return True, limit - current_count

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow the request
            return True, limit

    # Token blacklist methods

    async def blacklist_token(self, jti: str, expire_seconds: int) -> bool:
        """Add token to blacklist"""
        return await self.set(
            key=jti, value="blacklisted", expire=expire_seconds, namespace="token_blacklist"
        )

    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        return await self.exists(key=jti, namespace="token_blacklist")

    # Email verification codes

    async def store_verification_code(
        self, email: str, code: str, expire_minutes: int = 15
    ) -> bool:
        """Store email verification code"""
        return await self.set(
            key=email, value=code, expire=expire_minutes * 60, namespace="email_verification"
        )

    async def get_verification_code(self, email: str) -> Optional[str]:
        """Get email verification code"""
        return await self.get(key=email, namespace="email_verification")

    async def delete_verification_code(self, email: str) -> bool:
        """Delete verification code"""
        return await self.delete(key=email, namespace="email_verification")

    # OAuth state management

    async def store_oauth_state(
        self, state: str, data: Dict[str, Any], expire_minutes: int = 10
    ) -> bool:
        """Store OAuth state data"""
        return await self.set(
            key=state, value=data, expire=expire_minutes * 60, namespace="oauth_state"
        )

    async def get_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Get OAuth state data"""
        return await self.get(key=state, namespace="oauth_state")

    async def delete_oauth_state(self, state: str) -> bool:
        """Delete OAuth state"""
        return await self.delete(key=state, namespace="oauth_state")

    # WebAuthn challenge management

    async def store_webauthn_challenge(
        self, user_id: str, challenge: str, expire_minutes: int = 5
    ) -> bool:
        """Store WebAuthn challenge"""
        return await self.set(
            key=user_id, value=challenge, expire=expire_minutes * 60, namespace="webauthn_challenge"
        )

    async def get_webauthn_challenge(self, user_id: str) -> Optional[str]:
        """Get WebAuthn challenge"""
        return await self.get(key=user_id, namespace="webauthn_challenge")

    async def delete_webauthn_challenge(self, user_id: str) -> bool:
        """Delete WebAuthn challenge"""
        return await self.delete(key=user_id, namespace="webauthn_challenge")


# Create singleton instance
cache_service = CacheService()
