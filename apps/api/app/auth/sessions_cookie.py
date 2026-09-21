"""The `janua_sessions` companion cookie — the set of estate sessions a browser holds.

## Why this exists (multi-account, Layer 3)

`janua_sso` (see `sso_cookie.py`) points at exactly one session — the *fronted*
one, the account `/authorize` recognises. That is what an SSO hop needs, but it
means a browser can only ever hold one estate account: a second sign-in
overwrites the pointer and the first account is gone from the estate's view even
though its `sessions` row is still alive.

`janua_sessions` is the companion that remembers the others. It carries the list
of `sid`s (the `sessions.id`s that `janua_sso` also references) this browser has
signed into. `janua_sso` stays the single pointer to the fronted session; every
existing reader of `janua_sso` is unchanged. Switching accounts is re-pointing
`janua_sso` at another `sid` that `janua_sessions` already vouches for — no
re-authentication, because that session is already proven live.

## Why it carries no credential

The estate's security boundary (documented at length in `sso_cookie.py`) is that
the browser-wide, `Domain=.madfam.io` cookies must never carry a bearer: a live
access token there would be within reach of an XSS on any host in the estate.
`janua_sessions` follows the same rule. It carries **only session-id references**
— the same `sid`s `janua_sso` carries — never an access or refresh token. A `sid`
is useless on its own: `/authorize` and the switch endpoint re-read the
`sessions` row on every use, so a revoked or expired row in the list authenticates
nothing. The list is signed (a JWT, exactly like `janua_sso`) so a browser cannot
inject a `sid` it was never granted, but even a valid-looking `sid` is only ever a
pointer that must survive a live row check.

## Value shape

A signed JWT with `type: "sso_session_set"` — a distinct type from `janua_sso`'s
`"sso_session"`, so neither cookie can be presented in the other's place and
neither can be presented as a bearer (every bearer path verifies
`token_type="access"`). The one extra claim is `sids`: a JSON list of session-id
strings, capped and de-duplicated.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import structlog

from app.auth.sso_cookie import sso_cookie_max_age
from app.config import settings
from app.core.jwt_manager import jwt_manager

logger = structlog.get_logger()

#: Companion cookie name. Not relayed by the SDK the way `janua_sso` is — it is
#: read only by Janua's own switch/chooser endpoints — but it is set with the
#: same estate-wide Domain so it travels with `janua_sso` on the top-level
#: navigations that reach `/authorize`.
SESSIONS_COOKIE_NAME = "janua_sessions"

#: JWT `type` claim. Distinct from `janua_sso`'s `sso_session` and from every
#: bearer's `access`, so this value authenticates nothing but itself.
SESSIONS_TOKEN_TYPE = "sso_session_set"

#: Upper bound on how many accounts a single browser may hold at once. Bounds the
#: cookie size and the chooser length; the oldest entries are dropped first when
#: a new one pushes past the cap.
MAX_HELD_SESSIONS = 10


def sessions_cookie_kwargs() -> dict[str, Any]:
    """`set_cookie` kwargs for `janua_sessions`.

    Mirrors `sso_cookie_kwargs()` exactly — HttpOnly, Secure, SameSite=Lax,
    Path=/, the estate Domain, and the refresh-session lifetime — so the two
    cookies are set, sent, and expire together. Any drift between them would let
    one outlive the other and leave the held-session list disagreeing with the
    fronted pointer.
    """
    kwargs: dict[str, Any] = {
        "httponly": True,
        "secure": True,
        "samesite": "lax",
        "path": "/",
        "max_age": sso_cookie_max_age(),
    }
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    return kwargs


def sessions_cookie_delete_kwargs() -> dict[str, Any]:
    """`delete_cookie` kwargs — Domain/Path must match the set kwargs (RFC 6265).

    Same discipline as `sso_cookie_delete_kwargs()`: a deletion that differs on
    Domain or Path addresses a different cookie and silently leaves the real one
    in the browser.
    """
    kwargs: dict[str, Any] = {
        "path": "/",
        "secure": True,
        "httponly": True,
        "samesite": "lax",
    }
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    return kwargs


def mint_sessions_cookie_value(sids: list[str]) -> str:
    """Mint the signed reference the cookie carries.

    Signs with the same manager and issuer/audience as `janua_sso`, so the same
    key rotation covers both. The payload is only the list of session ids.
    """
    now = datetime.utcnow()
    return jwt_manager.encode_token(
        {
            "sids": [str(s) for s in sids],
            "type": SESSIONS_TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(seconds=sso_cookie_max_age()),
            "iss": jwt_manager.issuer,
            "aud": jwt_manager.audience,
        }
    )


def read_sessions_cookie(cookie_value: Optional[str]) -> list[str]:
    """Return the verified list of session ids a `janua_sessions` cookie carries.

    Signature, issuer, expiry and the token-type gate are enforced by
    `verify_token`; a forged or wrong-typed value yields an empty list, never a
    trusted one. Audience verification is off for the same reason it is off for
    `janua_sso` — Janua reads a token it minted itself. The list is de-duplicated
    while preserving order; every id here is still only a pointer a live row check
    must confirm.
    """
    if not cookie_value:
        return []
    payload = jwt_manager.verify_token(
        cookie_value, token_type=SESSIONS_TOKEN_TYPE, verify_audience=False
    )
    if not payload:
        return []
    raw = payload.get("sids")
    if not isinstance(raw, list):
        logger.warning("janua_sessions cookie carries a non-list sids claim")
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for sid in raw:
        s = str(sid)
        if s and s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def append_sid(existing: list[str], sid: str) -> list[str]:
    """Append `sid` to the held list, most-recent-last, capped and de-duplicated.

    If the sid is already present it is moved to the end (it is the freshest login
    for that account) rather than duplicated. When the list would exceed
    `MAX_HELD_SESSIONS`, the oldest entries are dropped from the front.
    """
    sid = str(sid)
    kept = [s for s in existing if s != sid]
    kept.append(sid)
    if len(kept) > MAX_HELD_SESSIONS:
        kept = kept[-MAX_HELD_SESSIONS:]
    return kept


def remove_sid(existing: list[str], sid: str) -> list[str]:
    """Return the held list with `sid` removed (per-account sign-out)."""
    sid = str(sid)
    return [s for s in existing if s != sid]


def set_sessions_cookie(response: Any, sids: list[str]) -> None:
    """Set `janua_sessions` to `sids`, or clear it when the list is empty.

    An empty list means the browser holds no estate accounts, so the cookie is
    deleted rather than set to an empty value.
    """
    if not sids:
        clear_sessions_cookie(response)
        return
    response.set_cookie(
        key=SESSIONS_COOKIE_NAME,
        value=mint_sessions_cookie_value(sids),
        **sessions_cookie_kwargs(),
    )


def clear_sessions_cookie(response: Any) -> None:
    """Delete `janua_sessions` with the exact Domain/Path it was set with."""
    response.delete_cookie(SESSIONS_COOKIE_NAME, **sessions_cookie_delete_kwargs())
