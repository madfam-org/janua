"""The `janua_sso` estate cookie — the one browser session that reaches the estate.

## Why this exists (J5 / R1)

B1 (#593) made every magic-link path call `_set_session_cookies`, so `/authorize`
would have a session to recognise. But the products that actually sign people in
— the MAP (`crea-map.madfam.io`) and the nauta ERP portal
(`crea-erp.madfam.io`) — exchange the magic link **server-to-server**
(`POST /api/v1/auth/magic-link/verify` from their Next process). Node reads the
`Set-Cookie` headers off that fetch response and drops them. They never reach a
browser. So a person signed into the MAP was still asked for a second email at
the ERP: the estate had two sessions and no shared one.

`@madfam/janua-next@0.2.0` closes that by relaying, byte for byte, any
`Set-Cookie` line whose cookie is named exactly `janua_sso` and whose `Domain`
covers the app's public host, appending it to the 303 it returns to the browser.
This module mints what it relays.

## Why a separate cookie rather than widening `janua_access_token`

`docs/architecture/SILENT_SSO_SESSION.md` weighed three options and recommended
this one. `janua_access_token` is deliberately **not** HttpOnly — the browser SDK
reads it — so pushing it to `Domain=.madfam.io` would put a live bearer token
within reach of an XSS on any host in the estate. `janua_sso` is HttpOnly, is
useless as a bearer credential (see the token-type gate below), and is read at
exactly one place: the OAuth authorize flow.

## The value

A signed JWT with `type: "sso_session"`. That type is the security boundary:
every bearer path in Janua verifies `token_type="access"`, and
`_verify_own_access_token` (oauth_provider.py) does the same, so presenting this
cookie's value as `Authorization: Bearer …` fails verification everywhere. It is
a *session reference*, not a credential.

## Revocation, without a migration

Production is frozen behind a migration-drift guard, so this adds no table and no
column. The cookie carries `sid` — the id of the existing `sessions` row that
`AuthService.create_session` already writes — and resolution re-reads that row on
every use. A session that is revoked (`revoked = True`, as `/signout` and
`invalidate_user_sessions` set), deactivated (`is_active = False`, as
`revoke_token_family` sets on theft detection), or past `expires_at` stops
authenticating the cookie immediately. Deleting the cookie is the cosmetic half
of logout; revoking the row is the half that matters, and it is the same row the
rest of Janua already revokes — so every existing revocation path revokes this
cookie too, for free.

Refresh rotation mutates `refresh_token_jti` on that same row and leaves
`session.id` alone, so a rotation does not invalidate the cookie and nothing has
to be re-issued on the `/authorize` response.

## Precedence at `/authorize` (J9)

This cookie is resolved **before** `janua_access_token`, not after it. A browser
that once completed a hosted login on the issuer host keeps that cookie, no other
host in the estate can delete it, and `/signout` does not clear it — so ranking
it first meant a stale hosted login silently outranked the estate login that had
just happened, and the ERP's silent hop got a code for the wrong person. See
`get_user_from_cookie_or_header` in `routers/v1/oauth_provider.py` for the rule
and how a disagreement between two valid cookies is decided.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.jwt_manager import jwt_manager
from app.models import Session as UserSession
from app.models import User, UserStatus

logger = structlog.get_logger()

#: The cookie name `@madfam/janua-next` (and nauta) relays verbatim. Changing it
#: breaks the relay on every consumer — it is a published contract, not a detail.
SSO_COOKIE_NAME = "janua_sso"

#: JWT `type` claim. Deliberately NOT "access": every bearer path in Janua
#: verifies `token_type="access"`, so this value cannot be used as a credential.
SSO_TOKEN_TYPE = "sso_session"


def sso_cookie_max_age() -> int:
    """Cookie lifetime in seconds: the refresh-session lifetime.

    The cookie references a `sessions` row whose own `expires_at` is the refresh
    expiry, so a longer cookie would only ever carry a dead reference.
    """
    return settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def sso_cookie_kwargs() -> dict[str, Any]:
    """`set_cookie` kwargs for `janua_sso`.

    HttpOnly and Secure because this cookie is estate-wide: it is readable on
    every host under `COOKIE_DOMAIN`, so no script anywhere in the estate may
    read it. SameSite=Lax so the top-level GET navigation to `/authorize` — which
    is how every silent hop arrives — still sends it.

    `secure=True` mirrors `_set_session_cookies`, which hardcodes it for both
    existing cookies; local dev over http keeps working the same way it does for
    those (browsers accept Secure cookies on http://localhost).
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


def sso_cookie_delete_kwargs() -> dict[str, Any]:
    """`delete_cookie` kwargs.

    Domain and Path MUST match the ones the cookie was set with — a deletion that
    differs on either attribute addresses a different cookie and silently leaves
    the real one in the browser. (Cookie identity is `(name, domain, path)` per
    RFC 6265; `Secure`/`HttpOnly` are not part of it, but they are mirrored here
    anyway so the deletion line is the set line with `Max-Age=0` — which is what
    the SDK relays, and the easiest shape to eyeball in a network trace.)
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


def mint_sso_cookie_value(user_id: str, session_id: str) -> str:
    """Mint the signed reference the cookie carries."""
    now = datetime.utcnow()
    return jwt_manager.encode_token(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "type": SSO_TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(seconds=sso_cookie_max_age()),
            "iss": jwt_manager.issuer,
            "aud": jwt_manager.audience,
        }
    )


def _session_id_from_session(session: Any) -> Optional[str]:
    """The `sessions.id` of a freshly created session, if there is one.

    `AuthService.create_session` returns the ORM row. Callers that mock it (and
    the MFA-challenge path, which builds its own) may hand back something without
    an id — in that case there is no row to reference, so no cookie is emitted
    rather than one that would never resolve.
    """
    session_id = getattr(session, "id", None)
    return str(session_id) if session_id else None


def set_sso_cookie(response: Any, user_id: str, session: Any) -> bool:
    """Set `janua_sso` on `response` for a just-established session.

    Returns whether the cookie was set. A caller with no resolvable session row
    gets `False` and no cookie — never a cookie that cannot be revoked.
    """
    session_id = _session_id_from_session(session)
    if not session_id:
        logger.warning("No session id available; skipping janua_sso cookie")
        return False

    response.set_cookie(
        key=SSO_COOKIE_NAME,
        value=mint_sso_cookie_value(user_id, session_id),
        **sso_cookie_kwargs(),
    )
    return True


def clear_sso_cookie(response: Any) -> None:
    """Delete `janua_sso`, with the exact Domain/Path it was set with."""
    response.delete_cookie(SSO_COOKIE_NAME, **sso_cookie_delete_kwargs())


def _session_is_live(session: Any) -> bool:
    """Whether a `sessions` row still authenticates.

    Janua revokes through two different flags depending on the path — `/signout`
    and `invalidate_user_sessions` set `revoked = True`, `revoke_token_family`
    sets `is_active = False` — so both are checked, plus the row's own expiry.
    """
    if getattr(session, "revoked", False):
        return False
    if getattr(session, "is_active", True) is False:
        return False
    expires_at = getattr(session, "expires_at", None)
    if expires_at is not None and expires_at <= datetime.utcnow():
        return False
    return True


async def resolve_sso_cookie_session(
    cookie_value: str, db: AsyncSession
) -> tuple[Optional[User], Optional[Any]]:
    """Resolve the person behind a `janua_sso` cookie **and the row it names**.

    Signature, issuer and expiry are enforced by `verify_token`; the token type
    gate means an access or refresh token presented here is refused. Audience
    verification is off for the same reason it is off in
    `_verify_own_access_token` (B2): Janua is the issuer reading a token it minted
    itself, and this cookie is not audience-scoped to any product.

    Everything after signature verification is a live read of the `sessions` row,
    which is what makes the cookie revocable.

    Returns `(user, session_row)` — both `None` when the cookie does not
    authenticate. The row comes back because `/authorize` needs its `created_at`
    to break a disagreement with a stale `janua_access_token` (J9); it is the
    row this function already loaded, not a second query. `resolve_sso_cookie_user`
    is the historical, user-only face of exactly this logic.
    """
    payload = jwt_manager.verify_token(
        cookie_value, token_type=SSO_TOKEN_TYPE, verify_audience=False
    )
    if not payload:
        return None, None

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        logger.warning("janua_sso cookie missing sub/sid")
        return None, None

    try:
        session_uuid = UUID(str(session_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning("janua_sso cookie carries an unparseable sid")
        return None, None

    result = await db.execute(select(UserSession).where(UserSession.id == session_uuid))
    session = result.scalar_one_or_none()
    if session is None:
        logger.info("janua_sso cookie references an unknown session")
        return None, None

    if not _session_is_live(session):
        logger.info("janua_sso cookie references a revoked or expired session")
        return None, None

    if str(getattr(session, "user_id", "")) != str(user_id):
        # The signature makes this unreachable short of a key compromise; refuse
        # rather than trust the claim over the row.
        logger.warning("janua_sso cookie sub does not match its session row")
        return None, None

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        return None, None

    status = getattr(user, "status", None)
    if status is not None and status != UserStatus.ACTIVE:
        logger.info("janua_sso cookie references a non-active user")
        return None, None

    return user, session


async def resolve_session_by_id(
    session_id: Any, db: AsyncSession
) -> tuple[Optional[User], Optional[Any]]:
    """Resolve `(user, session_row)` for a raw session id, or `(None, None)`.

    The row-and-user half of `resolve_sso_cookie_session`, addressed by a plain
    `sid` rather than a signed cookie. Used by account switching: the `sid` a
    caller asks to front is validated to still be a live, active session of an
    active user — the same live-row check every other estate-cookie path makes —
    before `janua_sso` is re-pointed at it. The `sid` itself proves nothing; this
    live read is what authorises the switch, so a revoked or expired row is
    refused exactly as it is at `/authorize`.
    """
    try:
        session_uuid = UUID(str(session_id))
    except (ValueError, AttributeError, TypeError):
        return None, None

    result = await db.execute(select(UserSession).where(UserSession.id == session_uuid))
    session = result.scalar_one_or_none()
    if session is None:
        return None, None
    if not _session_is_live(session):
        return None, None

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user: Optional[User] = user_result.scalar_one_or_none()
    if user is None:
        return None, None
    status = getattr(user, "status", None)
    if status is not None and status != UserStatus.ACTIVE:
        return None, None
    return user, session


async def resolve_sso_cookie_user(cookie_value: str, db: AsyncSession) -> Optional[User]:
    """Resolve the person behind a `janua_sso` cookie, or `None`.

    The user-only face of `resolve_sso_cookie_session`; every rule and every
    refusal lives there. Kept because it is the published shape callers and tests
    address.
    """
    user, _session = await resolve_sso_cookie_session(cookie_value, db)
    return user


async def revoke_sso_session(session_id: Any, db: AsyncSession) -> bool:
    """Revoke the `sessions` row a `janua_sso` cookie references.

    Used by logout paths that hold the session id. Returns whether a row was
    revoked. Best-effort by design: logout must never fail because revocation
    could not complete.
    """
    try:
        session_uuid = UUID(str(session_id))
    except (ValueError, AttributeError, TypeError):
        return False

    result = await db.execute(select(UserSession).where(UserSession.id == session_uuid))
    session = result.scalar_one_or_none()
    if session is None:
        return False

    session.revoked = True
    session.is_active = False
    session.revoked_at = datetime.utcnow()
    session.revoked_reason = "logout"
    return True


async def revoke_sso_cookie_session(cookie_value: Optional[str], db: AsyncSession) -> bool:
    """Revoke whatever a `janua_sso` cookie carries, without trusting it blindly.

    The cookie's signature is verified first, so a forged value cannot revoke
    someone else's session.
    """
    if not cookie_value:
        return False
    payload = jwt_manager.verify_token(
        cookie_value, token_type=SSO_TOKEN_TYPE, verify_audience=False
    )
    if not payload:
        return False
    session_id = payload.get("sid")
    if not session_id:
        return False
    return await revoke_sso_session(session_id, db)
