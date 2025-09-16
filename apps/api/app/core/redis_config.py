"""Redis configuration and client setup for the API."""

import os
import redis.asyncio as redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RedisConfig:
    """Redis configuration settings."""
    
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.password = os.getenv('REDIS_PASSWORD')
        self.db = int(os.getenv('REDIS_DB', 0))
        self.ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', 50))
        self.decode_responses = True
        self.socket_timeout = 5
        self.socket_connect_timeout = 5
        self.socket_keepalive = True
        self.socket_keepalive_options = {}
        self.health_check_interval = 30
        
    @property
    def url(self) -> str:
        """Get Redis connection URL."""
        if self.password:
            auth = f":{self.password}@"
        else:
            auth = ""
        
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"

# Global Redis client instance
redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """Get Redis client instance."""
    global redis_client
    
    if redis_client is None:
        config = RedisConfig()
        redis_client = redis.Redis(
            host=config.host,
            port=config.port,
            password=config.password,
            db=config.db,
            decode_responses=config.decode_responses,
            max_connections=config.max_connections,
            socket_timeout=config.socket_timeout,
            socket_connect_timeout=config.socket_connect_timeout,
            socket_keepalive=config.socket_keepalive,
            socket_keepalive_options=config.socket_keepalive_options,
            health_check_interval=config.health_check_interval,
            ssl=config.ssl
        )
        
        # Test connection
        try:
            await redis_client.ping()
            logger.info(f"Connected to Redis at {config.host}:{config.port}")
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
    """Redis service for WebAuthn and MFA operations."""
    
    def __init__(self, client: redis.Redis):
        self.client = client
    
    # WebAuthn Challenge Management
    async def store_webauthn_challenge(
        self,
        user_id: str,
        challenge: str,
        challenge_type: str = 'registration',
        ttl: int = 300
    ) -> None:
        """Store WebAuthn challenge."""
        key = f"webauthn:{challenge_type}:{user_id}"
        await self.client.setex(key, ttl, challenge)
    
    async def get_webauthn_challenge(
        self,
        user_id: str,
        challenge_type: str = 'registration'
    ) -> Optional[str]:
        """Get and delete WebAuthn challenge."""
        key = f"webauthn:{challenge_type}:{user_id}"
        challenge = await self.client.get(key)
        
        if challenge:
            # Delete after retrieval for security
            await self.client.delete(key)
        
        return challenge
    
    # MFA Code Management
    async def store_mfa_code(
        self,
        user_id: str,
        code: str,
        method: str,
        ttl: int = 300
    ) -> None:
        """Store MFA verification code."""
        import json
        key = f"mfa:{method}:{user_id}"
        data = {
            'code': code,
            'attempts': 0,
            'created_at': int(time.time())
        }
        await self.client.setex(key, ttl, json.dumps(data))
    
    async def verify_mfa_code(
        self,
        user_id: str,
        code: str,
        method: str,
        max_attempts: int = 3
    ) -> bool:
        """Verify MFA code."""
        import json
        import time
        
        key = f"mfa:{method}:{user_id}"
        data = await self.client.get(key)
        
        if not data:
            return False
        
        stored = json.loads(data)
        
        # Check attempts
        if stored['attempts'] >= max_attempts:
            await self.client.delete(key)
            return False
        
        # Increment attempts
        stored['attempts'] += 1
        ttl = await self.client.ttl(key)
        await self.client.setex(key, ttl, json.dumps(stored))
        
        if stored['code'] == code:
            # Delete on successful verification
            await self.client.delete(key)
            return True
        
        return False
    
    # Rate Limiting
    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int = 60
    ) -> dict:
        """Check rate limit for an identifier."""
        import time
        
        key = f"ratelimit:{identifier}"
        now = int(time.time())
        window_start = now - window
        
        # Remove old entries
        await self.client.zremrangebyscore(key, '-inf', window_start)
        
        # Count requests in window
        count = await self.client.zcard(key)
        
        if count < limit:
            # Add current request
            await self.client.zadd(key, {f"{now}-{id(self)}": now})
            await self.client.expire(key, window)
            
            return {
                'allowed': True,
                'remaining': limit - count - 1,
                'reset_at': now + window
            }
        
        # Get oldest entry to determine reset time
        oldest = await self.client.zrange(key, 0, 0, withscores=True)
        reset_at = int(oldest[0][1]) + window if oldest else now + window
        
        return {
            'allowed': False,
            'remaining': 0,
            'reset_at': reset_at
        }
    
    # Session Management
    async def store_session(
        self,
        session_id: str,
        data: dict,
        ttl: int = 3600
    ) -> None:
        """Store session data."""
        import json
        key = f"session:{session_id}"
        await self.client.setex(key, ttl, json.dumps(data))
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        import json
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
    
    # Passkey Storage
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
        """Get and delete passkey challenge."""
        key = f"passkey:challenge:{user_id}"
        challenge = await self.client.get(key)
        
        if challenge:
            await self.client.delete(key)
        
        return challenge
    
    # Trusted Device Management
    async def add_trusted_device(
        self,
        user_id: str,
        device_id: str,
        device_info: dict,
        ttl: int = 2592000  # 30 days
    ) -> None:
        """Add trusted device."""
        import json
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
    
    # Backup Codes
    async def store_backup_codes(
        self,
        user_id: str,
        codes: list,
        ttl: Optional[int] = None
    ) -> None:
        """Store backup codes."""
        import json
        key = f"backup_codes:{user_id}"
        data = {
            'codes': [{'code': code, 'used': False} for code in codes],
            'created_at': int(time.time())
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
        """Verify and mark backup code as used."""
        import json
        import time
        
        key = f"backup_codes:{user_id}"
        data = await self.client.get(key)
        
        if not data:
            return False, 0
        
        stored = json.loads(data)
        remaining = 0
        valid = False
        
        for item in stored['codes']:
            if not item['used']:
                if item['code'] == code:
                    item['used'] = True
                    valid = True
                else:
                    remaining += 1
        
        if valid:
            await self.client.set(key, json.dumps(stored))
        
        return valid, remaining

# Dependency for FastAPI
async def get_redis_service() -> RedisService:
    """Get Redis service instance for dependency injection."""
    client = await get_redis()
    return RedisService(client)