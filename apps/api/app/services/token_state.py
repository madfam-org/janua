"""Online token revocation checks. Cryptographic verification remains separate.

Security state must never use the cache client's permissive outage fallback.
Typed denylist keys are canonical; legacy untyped keys remain readable during
migration. No token, identity, or denylist key is logged here.
"""

import asyncio
import math
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.redis import get_redis
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Session


class SecurityRedis:
    """Bound security-state latency without permissive cached fallbacks."""

    def __init__(self, client):
        self.client = client

    async def get(self, key):
        return await asyncio.wait_for(self.client.get(key), timeout=5)

    async def set(self, key, value, **kwargs):
        return await asyncio.wait_for(self.client.set(key, value, **kwargs), timeout=5)


def security_redis(client):
    if isinstance(client, ResilientRedisClient):
        client = client.redis
    if client is None:
        raise HTTPException(503, "Authentication state unavailable")
    return client if isinstance(client, SecurityRedis) else SecurityRedis(client)


async def _client(client=None):
    return security_redis(client if client is not None else await get_redis())


def token_ttl(payload):
    try:
        return max(1, math.ceil(float(payload["exp"]) - time.time()))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise HTTPException(401, "Invalid token expiration")


async def token_is_revoked(payload, client=None):
    token_ttl(payload)
    jti, kind = payload.get("jti"), payload.get("type")
    if not isinstance(jti, str) or not jti or kind not in {"access", "refresh"}:
        return True
    try:
        redis = await _client(client)
        if await redis.get(f"blacklist:{kind}:{jti}") or await redis.get(f"blacklist:{jti}"):
            return True
        family = payload.get("family")
        return bool(family and await redis.get(f"blacklist:family:{family}"))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Authentication state unavailable") from None


async def blacklist_jti(jti, kind, ttl, client=None):
    if not jti:
        return
    try:
        redis = await _client(client)
        if not await redis.set(f"blacklist:{kind}:{jti}", "revoked", ex=max(1, int(ttl))):
            raise HTTPException(503, "Authentication state unavailable")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Authentication state unavailable") from None


async def consume_refresh(payload, client=None):
    """Atomically consume a refresh JTI; any replay invalidates its family.

    A failed mint after consumption requires reauthentication, never replay.
    The existing signed ``family`` claim links subsequent rotations.
    """
    try:
        redis = await _client(client)
        if not await token_is_revoked(payload, redis):
            claimed = await redis.set(
                f"blacklist:refresh:{payload['jti']}",
                "consumed",
                ex=token_ttl(payload),
                nx=True,
            )
            if claimed:
                return True
        family = payload.get("family")
        if family:
            if not await redis.set(
                f"blacklist:family:{family}",
                "revoked",
                ex=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            ):
                raise HTTPException(503, "Authentication state unavailable")
        return False
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Authentication state unavailable") from None


def session_is_live(session):
    return (
        not session.revoked
        and session.is_active is True
        and session.revoked_at is None
        and session.expires_at is not None
        and session.expires_at > datetime.utcnow()
    )


async def token_session_is_live(payload, db):
    """Check mapped sessions without rejecting legacy sessionless OAuth tokens.

    Password refresh rotates the row's access JTI; callers must denylist the
    previous access JTI before rotation. Legacy OAuth tokens have no session ID.
    """
    column = (
        Session.access_token_jti if payload.get("type") == "access" else Session.refresh_token_jti
    )
    result = await db.execute(select(Session).where(column == payload.get("jti")))
    session = result.scalar_one_or_none()
    return session is None or (
        str(session.user_id) == payload.get("sub") and session_is_live(session)
    )


async def revoke_session_row(session, reason="session_revoked"):
    """Write token denylist entries before callers commit the session change."""
    await blacklist_jti(
        session.access_token_jti, "access", settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    await blacklist_jti(
        session.refresh_token_jti, "refresh", settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    session.revoked = True
    session.is_active = False
    session.revoked_at = datetime.utcnow()
    session.revoked_reason = reason
