"""What "revoked" means for a Janua-minted JWT, in one place.

Janua grew two spellings of its revocation list. `AuthService` wrote and read
`blacklist:<jti>`; `JWTManager.blacklist_token` (used by sign-out, password
change and session-limit eviction) wrote `blacklist:<type>:<jti>`. Nothing read
the typed form on `/auth/refresh`, so a signed-out refresh token kept
refreshing. Every reader now goes through `is_revoked`, which checks all the
spellings, plus the refresh-token family key.

Keys (all expire on their own; nothing here is permanent state):

- `blacklist:<jti>`: one token (access or refresh) is revoked.
- `blacklist:<type>:<jti>`: the same, as `JWTManager.blacklist_token` writes it.
- `revoked_family:<family>`: every refresh token of one rotation family is
  revoked, including tokens minted from it later. Refresh tokens carry a
  `family` claim that survives rotation, so this is how a single revocation
  reaches the whole chain (RFC 7009 §2.1, RFC 6819 §5.2.2.3).

Reads are strict (`ResilientRedisClient.strict_exists`): when Redis cannot
answer they raise `RedisUnavailableError`, which the API answers with 503 +
Retry-After. They never answer "not revoked" from a fallback.

Writes come in two kinds:

- best-effort (`strict=False`): sign-out, password change, session-limit
  eviction and session deletion. These flows also mark the `sessions` row
  revoked, and `/auth/refresh` refuses a refresh token whose row is not live,
  so the row is the durable record. A write Redis did not take is logged as an
  error rather than ignored.
- strict (`strict=True`): `POST /oauth/revoke`. OAuth tokens have no
  `sessions` row, so the Redis key is the only record; the endpoint answers
  503 instead of claiming a revocation it could not store.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Mapping, Optional

import structlog

from app.config import settings
from app.core.redis_circuit_breaker import ResilientRedisClient

logger = structlog.get_logger()

FAMILY_KEY_PREFIX = "revoked_family:"


def jti_keys(jti: Any, token_type: Optional[str] = None) -> list[str]:
    """Every revocation-list key that can mark this JTI revoked."""
    if not jti:
        return []
    keys = [f"blacklist:{jti}"]
    if token_type:
        keys.append(f"blacklist:{token_type}:{jti}")
    return keys


def family_key(family: Any) -> Optional[str]:
    return f"{FAMILY_KEY_PREFIX}{family}" if family else None


def revocation_keys(payload: Mapping[str, Any], token_type: str) -> list[str]:
    """Keys whose presence means this token is revoked."""
    keys = jti_keys(payload.get("jti"), token_type)
    if token_type == "refresh":
        key = family_key(payload.get("family"))
        if key:
            keys.append(key)
    return keys


async def is_revoked(
    redis: ResilientRedisClient, payload: Mapping[str, Any], token_type: str
) -> bool:
    """Whether the token these claims came from is revoked. Strict read.

    Raises `RedisUnavailableError` when Redis cannot answer.
    """
    keys = revocation_keys(payload, token_type)
    if not keys:
        return False
    return await redis.strict_exists(*keys) > 0


def seconds_until(expires_at: Any, default: int) -> int:
    """Seconds from now until `expires_at` (a datetime or a JWT `exp`), at least 1.

    Falls back to `default` when the expiry is missing or unreadable, so a
    revocation entry never outlives the token by less than its full lifetime.
    """
    try:
        if isinstance(expires_at, datetime):
            # Janua stores naive UTC datetimes (`datetime.utcnow()`).
            remaining = (expires_at - datetime.utcnow()).total_seconds()
        elif isinstance(expires_at, (int, float)) and not isinstance(expires_at, bool):
            # A JWT `exp` is a UTC epoch.
            remaining = float(expires_at) - time.time()
        else:
            return default
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, int(remaining))


def access_token_ttl() -> int:
    return int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES) * 60


def refresh_token_ttl() -> int:
    return int(settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS) * 86400


async def _write(
    redis: ResilientRedisClient, key: str, ttl: int, *, strict: bool, reason: str
) -> None:
    if strict:
        await redis.strict_set(key, "1", ex=ttl)
        return
    if not await redis.set(key, "1", ex=ttl):
        logger.error(
            "Revocation write not acknowledged by Redis; the database row is the "
            "only record of this revocation",
            key_kind=key.split(":", 1)[0],
            reason=reason,
        )


async def revoke_jti(
    redis: ResilientRedisClient,
    jti: Any,
    ttl: int,
    *,
    reason: str,
    strict: bool = False,
) -> None:
    """Put one JTI on the revocation list for `ttl` seconds."""
    if not jti:
        return
    await _write(redis, f"blacklist:{jti}", max(1, int(ttl)), strict=strict, reason=reason)


async def revoke_family(
    redis: ResilientRedisClient,
    family: Any,
    ttl: Optional[int] = None,
    *,
    reason: str,
    strict: bool = False,
) -> None:
    """Revoke every refresh token of one rotation family.

    The default TTL is the full refresh-token lifetime: once the family is
    revoked no new token can be minted from it, so no token of the family
    outlives that.
    """
    key = family_key(family)
    if not key:
        return
    await _write(redis, key, max(1, int(ttl or refresh_token_ttl())), strict=strict, reason=reason)


def session_is_live(session: Any) -> bool:
    """Whether a `sessions` row still authenticates.

    Janua marks a row revoked through more than one flag depending on the path:
    bulk admin and account-deletion updates set only `revoked = True`, device
    revocation sets only `is_active = False` (with `revoked_at`), and
    `AuthService.revoke_sessions` sets both. Both flags are checked, plus the
    row's own expiry. (Every writer of `revoked_at` also clears `is_active`.)
    """
    if getattr(session, "revoked", False):
        return False
    if getattr(session, "is_active", True) is False:
        return False
    expires_at = getattr(session, "expires_at", None)
    if expires_at is not None and expires_at <= datetime.utcnow():
        return False
    return True
