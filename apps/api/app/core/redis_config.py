"""Redis configuration and client setup for the API.

Uses centralized pydantic Settings from app.config instead of direct os.getenv() calls.
"""

import time
import json
import logging
from typing import Optional
from urllib.parse import urlparse

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


def parse_redis_url(url: str) -> dict:
    """Parse Redis URL into connection parameters."""
    parsed = urlparse(url)

    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "password": parsed.password,
        "db": int(parsed.path.lstrip("/") or 0),
        "ssl": parsed.scheme == "rediss",
    }


# Global Redis client instance
redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client instance using centralized settings."""
    global redis_client

    if redis_client is None:
        # Parse connection params from URL
        conn_params = parse_redis_url(settings.REDIS_URL)

        # Convert timeout from milliseconds to seconds
        timeout_seconds = settings.REDIS_CONNECTION_TIMEOUT / 1000

        redis_client = redis.Redis(
            host=conn_params["host"],
            port=conn_params["port"],
            password=conn_params["password"],
            db=conn_params["db"],
            ssl=conn_params["ssl"],
            decode_responses=settings.REDIS_DECODE_RESPONSES,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
            socket_keepalive=True,
            health_check_interval=30,
        )

        # Test connection
        try:
            await redis_client.ping()
            logger.info(f"Connected to Redis at {conn_params['host']}:{conn_params['port']}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    return redis_client


async def close_redis():
    """Close Redis connection."""
    global redis_client

    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Closed Redis connection")


class RedisService:
    """Redis service for WebAuthn, MFA, sessions, and rate limiting operations."""

    def __init__(self, client: redis.Redis):
        self.client = client

    # ==========================================
    # WebAuthn Challenge Management
    # ==========================================

    async def store_webauthn_challenge(
        self,
        user_id: str,
        challenge: str,
        challenge_type: str = "registration",
        ttl: int = 300
    ) -> None:
        """Store WebAuthn challenge."""
        key = f"webauthn:{challenge_type}:{user_id}"
        await self.client.setex(key, ttl, challenge)

    async def get_webauthn_challenge(
        self,
        user_id: str,
        challenge_type: str = "registration"
    ) -> Optional[str]:
        """Get and delete WebAuthn challenge (one-time use)."""
        key = f"webauthn:{challenge_type}:{user_id}"
        challenge = await self.client.get(key)

        if challenge:
            await self.client.delete(key)

        return challenge

    # ==========================================
    # MFA Code Management
    # ==========================================

    async def store_mfa_code(
        self,
        user_id: str,
        code: str,
        method: str,
        ttl: int = 300
    ) -> None:
        """Store MFA verification code."""
        key = f"mfa:{method}:{user_id}"
        data = {
            "code": code,
            "attempts": 0,
            "created_at": int(time.time())
        }
        await self.client.setex(key, ttl, json.dumps(data))

    async def verify_mfa_code(
        self,
        user_id: str,
        code: str,
        method: str,
        max_attempts: int = 3
    ) -> bool:
        """Verify MFA code with attempt limiting."""
        key = f"mfa:{method}:{user_id}"
        data = await self.client.get(key)

        if not data:
            return False

        stored = json.loads(data)

        # Check attempts
        if stored["attempts"] >= max_attempts:
            await self.client.delete(key)
            return False

        # Increment attempts
        stored["attempts"] += 1
        ttl = await self.client.ttl(key)
        await self.client.setex(key, ttl, json.dumps(stored))

        if stored["code"] == code:
            await self.client.delete(key)
            return True

        return False

    # ==========================================
    # Rate Limiting
    # ==========================================

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int = 60
    ) -> dict:
        """Check rate limit for an identifier using sliding window."""
        key = f"ratelimit:{identifier}"
        now = int(time.time())
        window_start = now - window

        # Remove old entries
        await self.client.zremrangebyscore(key, "-inf", window_start)

        # Count requests in window
        count = await self.client.zcard(key)

        if count < limit:
            # Add current request
            await self.client.zadd(key, {f"{now}-{id(self)}": now})
            await self.client.expire(key, window)

            return {
                "allowed": True,
                "remaining": limit - count - 1,
                "reset_at": now + window
            }

        # Get oldest entry to determine reset time
        oldest = await self.client.zrange(key, 0, 0, withscores=True)
        reset_at = int(oldest[0][1]) + window if oldest else now + window

        return {
            "allowed": False,
            "remaining": 0,
            "reset_at": reset_at
        }

    # ==========================================
    # Session Management
    # ==========================================

    async def store_session(
        self,
        session_id: str,
        data: dict,
        ttl: int = 3600
    ) -> None:
        """Store session data."""
        key = f"session:{session_id}"
        await self.client.setex(key, ttl, json.dumps(data))

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        key = f"session:{session_id}"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def refresh_session(self, session_id: str, ttl: int = 3600) -> bool:
        """Refresh session TTL."""
        key = f"session:{session_id}"
        return await self.client.expire(key, ttl) == 1

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        key = f"session:{session_id}"
        return await self.client.delete(key) == 1

    # ==========================================
    # Passkey Challenge Storage
    # ==========================================

    async def store_passkey_challenge(
        self,
        user_id: str,
        challenge: str,
        ttl: int = 300
    ) -> None:
        """Store passkey registration/authentication challenge."""
        key = f"passkey:challenge:{user_id}"
        await self.client.setex(key, ttl, challenge)

    async def get_passkey_challenge(self, user_id: str) -> Optional[str]:
        """Get and delete passkey challenge (one-time use)."""
        key = f"passkey:challenge:{user_id}"
        challenge = await self.client.get(key)

        if challenge:
            await self.client.delete(key)

        return challenge

    # ==========================================
    # Trusted Device Management
    # ==========================================

    async def add_trusted_device(
        self,
        user_id: str,
        device_id: str,
        device_info: dict,
        ttl: int = 2592000  # 30 days
    ) -> None:
        """Add trusted device."""
        key = f"trusted_device:{user_id}:{device_id}"
        await self.client.setex(key, ttl, json.dumps(device_info))

    async def is_trusted_device(
        self,
        user_id: str,
        device_id: str
    ) -> bool:
        """Check if device is trusted."""
        key = f"trusted_device:{user_id}:{device_id}"
        return await self.client.exists(key) == 1

    async def revoke_trusted_device(
        self,
        user_id: str,
        device_id: str
    ) -> bool:
        """Revoke trusted device."""
        key = f"trusted_device:{user_id}:{device_id}"
        return await self.client.delete(key) == 1

    # ==========================================
    # Backup Codes
    # ==========================================

    async def store_backup_codes(
        self,
        user_id: str,
        codes: list,
        ttl: Optional[int] = None
    ) -> None:
        """Store backup codes."""
        key = f"backup_codes:{user_id}"
        data = {
            "codes": [{"code": code, "used": False} for code in codes],
            "created_at": int(time.time())
        }

        if ttl:
            await self.client.setex(key, ttl, json.dumps(data))
        else:
            await self.client.set(key, json.dumps(data))

    async def verify_backup_code(
        self,
        user_id: str,
        code: str
    ) -> tuple[bool, int]:
        """Verify and mark backup code as used. Returns (valid, remaining_codes)."""
        key = f"backup_codes:{user_id}"
        data = await self.client.get(key)

        if not data:
            return False, 0

        stored = json.loads(data)
        remaining = 0
        valid = False

        for item in stored["codes"]:
            if not item["used"]:
                if item["code"] == code:
                    item["used"] = True
                    valid = True
                else:
                    remaining += 1

        if valid:
            await self.client.set(key, json.dumps(stored))

        return valid, remaining


# ==========================================
# FastAPI Dependency
# ==========================================

async def get_redis_service() -> RedisService:
    """Get Redis service instance for dependency injection."""
    client = await get_redis()
    return RedisService(client)
