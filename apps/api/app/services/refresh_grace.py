"""Refresh rotation under concurrency: the grace window (roadmap 1.3, D5).

Kept out of `auth_service.py` (the repository's 800-line pre-commit limit);
`AuthService.refresh_tokens` calls it.

REFRESH_REUSE_GRACE_SECONDS is owner decision D5 (edge-case roadmap
2026-11-19; APPROVED 2026-11-20: 30 s, same session only). Set it with the environment
variable of the same name; 0 restores strict single use. It is read here and
not from `app.config.Settings` because config.py is over the 800-line limit
and not part of the split; move it there when config.py is split.
"""

import asyncio
import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select

from app.models import Session
from app.services import token_revocation

logger = structlog.get_logger()

#: Owner decision D5 (APPROVED 2026-11-20: 30 s, same session only). 0 = strict single use, as before.
REFRESH_REUSE_GRACE_SECONDS = max(0, min(120, int(os.getenv("REFRESH_REUSE_GRACE_SECONDS", "30"))))

# REFRESH UNDER CONCURRENCY (edge-case roadmap 1.3, owner decision D5).
# Two tabs, an SSR render plus the browser, or a client retrying on a slow
# network refresh the same session at once. Before, both found the row, both
# rotated (last write won) and the loser's next refresh revoked the whole
# family; one arriving just after the winner committed hit the rotation
# blacklist. Either way the person was signed out «for no reason».
#
# Now the row is read under a lock and rotated with a compare-and-set on the
# refresh JTI, so exactly one request rotates. The rotation records, for
# REFRESH_REUSE_GRACE_SECONDS, the pair it issued under a digest of the
# rotated-away JTI, ENCRYPTED with a key derived from the rotated-away token
# itself: only a holder of that exact token can read it back, and a Redis dump
# holds no usable token. A repeat of that token within the window, while the
# session is live and has not rotated again, gets that same pair. Anything else
# (an older token, another session's, after the window) takes the old path:
# family revocation on reuse.

_REFRESH_GRACE_PREFIX = "auth:refresh:grace:"


def grace_key(jti: Any) -> str:
    return _REFRESH_GRACE_PREFIX + hashlib.sha256(str(jti).encode()).hexdigest()


def _cipher(presented_refresh_token: str):
    import base64

    from cryptography.fernet import Fernet

    digest = hashlib.sha256(b"janua-refresh-grace:" + presented_refresh_token.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


async def remember(
    redis, presented_refresh_token: str, old_jti: Any, record: Dict[str, Any]
) -> None:
    grace = REFRESH_REUSE_GRACE_SECONDS
    if grace <= 0:
        return
    token = _cipher(presented_refresh_token).encrypt(json.dumps(record).encode())
    try:
        await redis.strict_set(grace_key(old_jti), token.decode(), ex=grace)
    except Exception as exc:  # the only loss is the grace answer
        logger.warning("refresh.grace_not_recorded", error_type=type(exc).__name__)


async def _read(redis, presented_refresh_token: str, jti: Any):
    if REFRESH_REUSE_GRACE_SECONDS <= 0 or not jti:
        return None
    from cryptography.fernet import InvalidToken

    try:
        stored = await redis.strict_get(grace_key(jti))
    except Exception as exc:
        logger.warning("refresh.grace_check_unavailable", error_type=type(exc).__name__)
        return None
    if not stored:
        return None
    if isinstance(stored, str):
        stored = stored.encode()
    try:
        return json.loads(_cipher(presented_refresh_token).decrypt(stored))
    except (InvalidToken, ValueError, TypeError):
        return None


async def grace_answer(
    db, refresh_token: str, claims: Optional[Dict[str, Any]], redis, *, wait: bool = False
) -> Optional[Tuple[str, str]]:
    """The pair a rotation of THIS token issued moments ago, or None.

    Only when: the token's claims check out (the caller decodes it: signature,
    issuer, type, expiry); a rotation of exactly this token recorded its pair
    within REFRESH_REUSE_GRACE_SECONDS (readable only with this token); the
    session row is live, in the same family, and still holds the JTI that
    rotation issued (no later rotation). `wait` polls briefly for a rotation
    that is still committing (lost a concurrent compare-and-set).
    """
    if REFRESH_REUSE_GRACE_SECONDS <= 0 or not claims or not claims.get("jti"):
        return None
    record = None
    for _ in range(20 if wait else 1):
        record = await _read(redis, refresh_token, claims["jti"])
        if record is not None or not wait:
            break
        await asyncio.sleep(0.1)
    if record is None or record.get("family") != claims.get("family"):
        return None
    try:
        session_id = UUID(record["session_id"])
    except (KeyError, ValueError, TypeError):
        return None
    result = await db.execute(
        select(Session).where(Session.id == session_id).execution_options(populate_existing=True)
    )
    session = result.scalar_one_or_none()
    if (
        session is None
        or not token_revocation.session_is_live(session)
        or session.refresh_token_jti != record.get("refresh_jti")
    ):
        return None
    logger.info("Refresh repeated within the grace window", session_id=str(session.id))
    return record["access_token"], record["refresh_token"]
