"""
Enterprise-Grade Distributed Session Management
Handles session state across multiple instances with Redis backend
"""

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as redis
from redis.asyncio.lock import Lock
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import logger
from app.models import Session as DBSession
from app.models import User

logger = logging.getLogger(__name__)


class SessionType(Enum):
    """Types of sessions supported"""

    WEB = "web"
    MOBILE = "mobile"
    API = "api"
    SERVICE = "service"
    SSO = "sso"


class SessionStatus(Enum):
    """Session lifecycle states"""

    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"
    REVOKED = "revoked"
    LOCKED = "locked"


class DistributedSessionManager:
    """
    Manages user sessions across distributed instances
    Features:
    - Redis-backed session storage for horizontal scaling
    - Session replication and failover
    - Concurrent session limits
    - Session activity tracking
    - Automatic cleanup and expiration
    - Cross-device session management
    - Session fixation prevention
    """

    def __init__(
        self, redis_client: Optional[redis.Redis] = None, db_session: Optional[AsyncSession] = None
    ):
        self.redis = redis_client
        self.db = db_session

        # Configuration
        self.session_ttl = (
            settings.SESSION_TTL if hasattr(settings, "SESSION_TTL") else 3600
        )  # 1 hour default
        self.max_sessions_per_user = (
            settings.MAX_SESSIONS_PER_USER if hasattr(settings, "MAX_SESSIONS_PER_USER") else 5
        )
        self.session_idle_timeout = (
            settings.SESSION_IDLE_TIMEOUT if hasattr(settings, "SESSION_IDLE_TIMEOUT") else 1800
        )  # 30 minutes
        self.enable_session_binding = True  # Bind sessions to IP/User-Agent
        self.enable_concurrent_limit = True

        # Redis key prefixes
        self.SESSION_KEY_PREFIX = "session:"
        self.USER_SESSIONS_PREFIX = "user_sessions:"
        self.SESSION_LOCK_PREFIX = "session_lock:"
        self.ACTIVE_SESSIONS_KEY = "active_sessions"

    async def create_session(
        self,
        user_id: str,
        session_type: SessionType = SessionType.WEB,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new distributed session

        Returns:
            Session data including token and metadata
        """

        # Check concurrent session limit
        if self.enable_concurrent_limit:
            existing_sessions = await self.get_user_sessions(user_id)
            if len(existing_sessions) >= self.max_sessions_per_user:
                # Revoke oldest session
                oldest = min(
                    existing_sessions, key=lambda x: x.get("created_at", datetime.utcnow())
                )
                await self.revoke_session(oldest["session_id"], reason="max_sessions_exceeded")

        # Generate secure session token
        session_id = str(uuid.uuid4())
        session_token = secrets.token_urlsafe(64)

        # Create session fingerprint for binding
        fingerprint = None
        if self.enable_session_binding:
            fingerprint = self._create_session_fingerprint(ip_address, user_agent)

        # Session data structure
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "session_type": session_type.value,
            "status": SessionStatus.ACTIVE.value,
            "token_hash": hashlib.sha256(session_token.encode()).hexdigest(),
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=self.session_ttl)).isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "fingerprint": fingerprint,
            "device_info": device_info or {},
            "metadata": metadata or {},
            "access_count": 0,
            "refresh_count": 0,
        }

        # Store in Redis with TTL
        if self.redis:
            try:
                # Store session data
                session_key = f"{self.SESSION_KEY_PREFIX}{session_id}"
                await self.redis.setex(session_key, self.session_ttl, json.dumps(session_data))

                # Add to user's session set
                user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
                await self.redis.sadd(user_sessions_key, session_id)
                await self.redis.expire(user_sessions_key, self.session_ttl * 2)

                # Track in global active sessions
                await self.redis.zadd(
                    self.ACTIVE_SESSIONS_KEY, {session_id: datetime.utcnow().timestamp()}
                )

                logger.info(f"Created distributed session {session_id} for user {user_id}")

            except Exception as e:
                logger.error(f"Redis session creation failed: {e}")
                # Fall back to database storage

        # Also persist to database for durability
        if self.db:
            try:
                db_session = DBSession(
                    id=session_id,
                    user_id=user_id,
                    token=session_token,  # Session model uses 'token', not 'token_hash'
                    ip_address=ip_address,
                    user_agent=user_agent,
                    expires_at=datetime.utcnow() + timedelta(seconds=self.session_ttl),
                    # Note: Session model doesn't have metadata field
                )
                self.db.add(db_session)
                await self.db.commit()
            except Exception as e:
                logger.error(f"Database session creation failed: {e}")

        return {
            "session_id": session_id,
            "session_token": session_token,
            "expires_at": session_data["expires_at"],
            "session_type": session_type.value,
        }

    async def validate_session(
        self, session_token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validate and retrieve session data

        Returns:
            Session data if valid, None otherwise
        """

        # Hash the token for comparison
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()

        # Try Redis first
        if self.redis:
            try:
                # Search for session by token hash
                cursor = b"0"
                while cursor:
                    cursor, keys = await self.redis.scan(
                        cursor=cursor, match=f"{self.SESSION_KEY_PREFIX}*", count=100
                    )

                    for key in keys:
                        session_data = await self.redis.get(key)
                        if session_data:
                            data = json.loads(session_data)
                            if data.get("token_hash") == token_hash:
                                # Found the session
                                return await self._validate_session_security(
                                    data, ip_address, user_agent
                                )
            except Exception as e:
                logger.error(f"Redis session validation failed: {e}")

        # Fall back to database
        if self.db:
            try:
                # Session model uses 'token' field, not 'token_hash'
                result = await self.db.execute(
                    select(DBSession).where(DBSession.token == session_token)
                )
                db_session = result.scalar_one_or_none()

                if db_session:
                    # Check if expired
                    if db_session.expires_at < datetime.utcnow():
                        await self.revoke_session(str(db_session.id), reason="expired")
                        return None

                    # Convert to dict format
                    session_data = {
                        "session_id": str(db_session.id),
                        "user_id": str(db_session.user_id),
                        "status": SessionStatus.ACTIVE.value,
                        "expires_at": db_session.expires_at.isoformat(),
                        "ip_address": db_session.ip_address,
                        "user_agent": db_session.user_agent,
                    }

                    return await self._validate_session_security(
                        session_data, ip_address, user_agent
                    )
            except Exception as e:
                logger.error(f"Database session validation failed: {e}")

        return None

    async def _validate_session_security(
        self,
        session_data: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Validate session security constraints"""

        # Check if session is active
        if session_data.get("status") != SessionStatus.ACTIVE.value:
            logger.warning(f"Session {session_data['session_id']} is not active")
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if expires_at < datetime.utcnow():
            await self.revoke_session(session_data["session_id"], reason="expired")
            return None

        # Validate session binding if enabled
        if self.enable_session_binding and session_data.get("fingerprint"):
            current_fingerprint = self._create_session_fingerprint(ip_address, user_agent)
            if current_fingerprint != session_data["fingerprint"]:
                logger.warning(f"Session fingerprint mismatch for {session_data['session_id']}")
                # Could be stricter and revoke, but for now just log
                # await self.revoke_session(session_data['session_id'], reason="fingerprint_mismatch")
                # return None

        # Update last activity
        await self.update_session_activity(session_data["session_id"])

        return session_data

    async def update_session_activity(self, session_id: str):
        """Update session last activity timestamp"""

        if self.redis:
            try:
                session_key = f"{self.SESSION_KEY_PREFIX}{session_id}"
                session_data = await self.redis.get(session_key)

                if session_data:
                    data = json.loads(session_data)
                    data["last_activity"] = datetime.utcnow().isoformat()
                    data["access_count"] = data.get("access_count", 0) + 1

                    # Reset TTL
                    await self.redis.setex(session_key, self.session_ttl, json.dumps(data))

                    # Update in active sessions sorted set
                    await self.redis.zadd(
                        self.ACTIVE_SESSIONS_KEY, {session_id: datetime.utcnow().timestamp()}
                    )
            except Exception as e:
                logger.error(f"Failed to update session activity: {e}")

    async def refresh_session(
        self, session_id: str, extend_ttl: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh session and optionally extend TTL

        Returns:
            Updated session data
        """

        if self.redis:
            try:
                session_key = f"{self.SESSION_KEY_PREFIX}{session_id}"
                session_data = await self.redis.get(session_key)

                if session_data:
                    data = json.loads(session_data)
                    data["last_activity"] = datetime.utcnow().isoformat()
                    data["refresh_count"] = data.get("refresh_count", 0) + 1

                    if extend_ttl:
                        data["expires_at"] = (
                            datetime.utcnow() + timedelta(seconds=self.session_ttl)
                        ).isoformat()

                    # Generate new token for security
                    new_token = secrets.token_urlsafe(64)
                    data["token_hash"] = hashlib.sha256(new_token.encode()).hexdigest()

                    # Save updated session
                    await self.redis.setex(session_key, self.session_ttl, json.dumps(data))

                    return {
                        "session_id": session_id,
                        "session_token": new_token,
                        "expires_at": data["expires_at"],
                    }
            except Exception as e:
                logger.error(f"Failed to refresh session: {e}")

        return None

    async def revoke_session(self, session_id: str, reason: str = "manual_revocation"):
        """Revoke a session"""

        if self.redis:
            try:
                session_key = f"{self.SESSION_KEY_PREFIX}{session_id}"
                session_data = await self.redis.get(session_key)

                if session_data:
                    data = json.loads(session_data)
                    data["status"] = SessionStatus.REVOKED.value
                    data["revoked_at"] = datetime.utcnow().isoformat()
                    data["revocation_reason"] = reason

                    # Keep for audit trail but with short TTL
                    await self.redis.setex(session_key, 86400, json.dumps(data))  # 24 hours

                    # Remove from user sessions set
                    user_id = data.get("user_id")
                    if user_id:
                        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
                        await self.redis.srem(user_sessions_key, session_id)

                    # Remove from active sessions
                    await self.redis.zrem(self.ACTIVE_SESSIONS_KEY, session_id)

                    logger.info(f"Revoked session {session_id}: {reason}")
            except Exception as e:
                logger.error(f"Failed to revoke session: {e}")

        # Also update in database
        if self.db:
            try:
                await self.db.execute(
                    update(DBSession)
                    .where(DBSession.id == session_id)
                    .values(revoked_at=datetime.utcnow())
                )
                await self.db.commit()
            except Exception as e:
                logger.error(f"Failed to revoke session in database: {e}")

    async def get_user_sessions(
        self, user_id: str, include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all sessions for a user"""

        sessions = []

        if self.redis:
            try:
                user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
                session_ids = await self.redis.smembers(user_sessions_key)

                for session_id in session_ids:
                    session_key = f"{self.SESSION_KEY_PREFIX}{session_id}"
                    session_data = await self.redis.get(session_key)

                    if session_data:
                        data = json.loads(session_data)

                        # Filter expired if requested
                        if not include_expired:
                            expires_at = datetime.fromisoformat(data["expires_at"])
                            if expires_at < datetime.utcnow():
                                continue

                        sessions.append(data)
            except Exception as e:
                logger.error(f"Failed to get user sessions: {e}")

        return sessions

    async def revoke_all_user_sessions(self, user_id: str, except_current: Optional[str] = None):
        """Revoke all sessions for a user, optionally keeping current"""

        sessions = await self.get_user_sessions(user_id)

        for session in sessions:
            if session["session_id"] != except_current:
                await self.revoke_session(session["session_id"], reason="bulk_revocation")

    async def cleanup_expired_sessions(self):
        """Background task to cleanup expired sessions"""

        if self.redis:
            try:
                # Get all active sessions
                current_time = datetime.utcnow().timestamp()
                expired_cutoff = current_time - self.session_ttl

                # Get expired sessions from sorted set
                expired = await self.redis.zrangebyscore(
                    self.ACTIVE_SESSIONS_KEY, 0, expired_cutoff
                )

                for session_id in expired:
                    await self.revoke_session(session_id, reason="expired")

                logger.info(f"Cleaned up {len(expired)} expired sessions")
            except Exception as e:
                logger.error(f"Failed to cleanup sessions: {e}")

    async def get_session_analytics(self) -> Dict[str, Any]:
        """Get session analytics and metrics"""

        analytics = {
            "total_active_sessions": 0,
            "sessions_by_type": {},
            "average_session_duration": 0,
            "peak_concurrent_sessions": 0,
            "session_creation_rate": 0,
        }

        if self.redis:
            try:
                # Count active sessions
                analytics["total_active_sessions"] = await self.redis.zcard(
                    self.ACTIVE_SESSIONS_KEY
                )

                # Get session type distribution
                cursor = b"0"
                session_types = {}
                total_duration = 0
                session_count = 0

                while cursor:
                    cursor, keys = await self.redis.scan(
                        cursor=cursor, match=f"{self.SESSION_KEY_PREFIX}*", count=100
                    )

                    for key in keys:
                        session_data = await self.redis.get(key)
                        if session_data:
                            data = json.loads(session_data)
                            session_type = data.get("session_type", "unknown")
                            session_types[session_type] = session_types.get(session_type, 0) + 1

                            # Calculate duration
                            created = datetime.fromisoformat(data["created_at"])
                            duration = (datetime.utcnow() - created).total_seconds()
                            total_duration += duration
                            session_count += 1

                analytics["sessions_by_type"] = session_types

                if session_count > 0:
                    analytics["average_session_duration"] = total_duration / session_count

            except Exception as e:
                logger.error(f"Failed to get session analytics: {e}")

        return analytics

    def _create_session_fingerprint(
        self, ip_address: Optional[str], user_agent: Optional[str]
    ) -> str:
        """Create a session fingerprint for binding"""

        fingerprint_data = f"{ip_address or 'unknown'}:{user_agent or 'unknown'}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    async def acquire_session_lock(self, session_id: str, timeout: int = 5) -> Optional[Lock]:
        """Acquire distributed lock for session operations"""

        if self.redis:
            try:
                lock_key = f"{self.SESSION_LOCK_PREFIX}{session_id}"
                lock = self.redis.lock(lock_key, timeout=timeout)

                if await lock.acquire(blocking=False):
                    return lock
            except Exception as e:
                logger.error(f"Failed to acquire session lock: {e}")

        return None

    async def migrate_session_to_sso(
        self, session_id: str, sso_provider: str, sso_session_data: Dict[str, Any]
    ) -> bool:
        """Migrate a regular session to SSO session"""

        if self.redis:
            try:
                session_key = f"{self.SESSION_KEY_PREFIX}{session_id}"
                session_data = await self.redis.get(session_key)

                if session_data:
                    data = json.loads(session_data)
                    data["session_type"] = SessionType.SSO.value
                    data["sso_provider"] = sso_provider
                    data["sso_data"] = sso_session_data

                    await self.redis.setex(session_key, self.session_ttl, json.dumps(data))

                    logger.info(f"Migrated session {session_id} to SSO ({sso_provider})")
                    return True
            except Exception as e:
                logger.error(f"Failed to migrate session to SSO: {e}")

        return False
