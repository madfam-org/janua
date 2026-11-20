"""Same-browser replay of a hosted form POST (roadmap 1.1 and 1.2, rules R2/R3).

The magic-link callback has done this since 2026-10-07: a second press from the
browser that spent a link, within a short window, finishes the hand-off again
instead of answering «already used». This module gives the other single-use
hosted POSTs the same two pieces:

- A REPLAY GRANT, written when a POST claims its single-use state and BEFORE
  anything commits, so a concurrent press waiting on the same row lock finds it
  the moment it gets the row. It holds what the replay needs to land where the
  first press went, plus a digest of the browser binding. It lives
  `HOSTED_REPLAY_GRACE_SECONDS` and is deleted again if the first press fails
  before its commit (consume after commit, R3).
- A BROWSER BINDING: a random value in an HttpOnly cookie, compared by digest.
  It identifies a browser, not a person, and carries nothing else. A replay
  from any other browser, without the cookie, or after the window gets the
  honest page instead.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

#: How long after a hosted POST succeeds the SAME browser may repeat it and
#: still land where the first one went. Same order as the magic-link window
#: (MAGIC_LINK_REPLAY_GRACE_SECONDS, 120 s): long enough for a double press, a
#: refresh of the result or Back-then-submit, short enough that a copied form
#: is useless soon after.
HOSTED_REPLAY_GRACE_SECONDS = 120


#: The general hosted browser binding (consent, second-factor form, reset). The
#: hosted second-factor flow keeps its own `__Host-janua_factor_flow` value.
BROWSER_COOKIE = "__Host-janua_browser"
_BROWSER_COOKIE_MAX_AGE = 86400
_BROWSER_VALUE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def browser_binding_hash(request) -> Optional[str]:
    """Digest of this browser's binding cookie, or None (absent / not ours)."""
    try:
        value = request.cookies.get(BROWSER_COOKIE)
    except Exception:
        return None
    if isinstance(value, str) and _BROWSER_VALUE.match(value):
        return binding_digest(value)
    return None


def ensure_browser_cookie(request, response) -> None:
    """Give this browser a binding value on the page whose form it will post."""
    if browser_binding_hash(request) is not None:
        return
    response.set_cookie(
        key=BROWSER_COOKIE,
        value=secrets.token_urlsafe(32),
        max_age=_BROWSER_COOKIE_MAX_AGE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def binding_digest(binding: str) -> str:
    return hashlib.sha256(binding.encode()).hexdigest()


def _key(kind: str, state_id: str) -> str:
    return f"auth:replay:{kind}:{hashlib.sha256(state_id.encode()).hexdigest()}"


async def grant_replay(
    redis,
    kind: str,
    state_id: str,
    *,
    binding_hash: Optional[str],
    payload: dict,
    only_if_absent: bool = False,
) -> bool:
    """Record that this browser claimed `state_id`; False when nothing was stored.

    `binding_hash` is the digest of the browser binding (never the raw value).
    Without one there is no replay: a repeat gets the honest page.
    `only_if_absent` is for a grant written BEFORE the claim is known to be
    this request's (password reset): a later press never overwrites the first.
    """
    if not binding_hash or HOSTED_REPLAY_GRACE_SECONDS <= 0:
        return False
    record = json.dumps({"binding": binding_hash, "payload": payload})
    try:
        if only_if_absent:
            return bool(
                await redis.strict_set_nx(
                    _key(kind, state_id), record, ex=HOSTED_REPLAY_GRACE_SECONDS
                )
            )
        await redis.strict_set(_key(kind, state_id), record, ex=HOSTED_REPLAY_GRACE_SECONDS)
        return True
    except Exception as exc:
        # The only loss is the replay; the first press itself is unaffected.
        logger.warning("auth.replay.grant_not_recorded", kind=kind, error_type=type(exc).__name__)
        return False


async def update_replay(redis, kind: str, state_id: str, **fields: Any) -> None:
    """Add fields to a live grant (e.g. the session the first press created)."""
    try:
        raw = await redis.strict_get(_key(kind, state_id))
        if not raw:
            return
        record = json.loads(raw)
        record["payload"].update(fields)
        await redis.strict_set(
            _key(kind, state_id), json.dumps(record), ex=HOSTED_REPLAY_GRACE_SECONDS
        )
    except Exception as exc:
        logger.warning("auth.replay.update_failed", kind=kind, error_type=type(exc).__name__)


async def revoke_replay(redis, kind: str, state_id: str) -> None:
    """Drop a grant: the first press failed before its commit."""
    try:
        await redis.strict_delete(_key(kind, state_id))
    except Exception as exc:
        logger.warning("auth.replay.revoke_failed", kind=kind, error_type=type(exc).__name__)


async def replay_payload(
    redis, kind: str, state_id: str, *, binding_hash: Optional[str]
) -> Optional[dict]:
    """The grant's payload when THIS browser claimed `state_id` moments ago.

    Any doubt (no binding, no grant, a digest mismatch, Redis unreachable)
    answers None, which means the honest page.
    """
    if not binding_hash:
        return None
    try:
        raw = await redis.strict_get(_key(kind, state_id))
    except Exception as exc:
        logger.warning("auth.replay.check_unavailable", kind=kind, error_type=type(exc).__name__)
        return None
    if not raw:
        return None
    try:
        record = json.loads(raw)
    except (TypeError, ValueError):
        return None
    stored = record.get("binding")
    if not isinstance(stored, str) or not hmac.compare_digest(stored, binding_hash):
        return None
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else None


async def wait_for_replay(
    redis, kind: str, state_id: str, *, binding_hash: Optional[str], field: str, attempts: int = 30
) -> Optional[dict]:
    """`replay_payload`, waiting (up to `attempts` x 100 ms) for the first press
    to fill `field` when it is still finishing (two presses at once)."""
    import asyncio

    for _ in range(max(1, attempts)):
        payload = await replay_payload(redis, kind, state_id, binding_hash=binding_hash)
        if payload is None:
            return None
        if payload.get(field):
            return payload
        await asyncio.sleep(0.1)
    return None
