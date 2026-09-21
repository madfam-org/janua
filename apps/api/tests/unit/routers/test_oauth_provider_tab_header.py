"""Per-tab session override (`X-Janua-Session`) at `/authorize` — two-tab focus.

## What this pins (Layer 3 follow-on, lane TWO-TAB)

Cookies are per-browser, not per-tab, so `janua_sso` alone cannot front two
identities at once. The follow-on lets a tab send one held `sid` in the
`X-Janua-Session` header; the resolver honors it — ahead of the shared
`janua_sso` cookie — ONLY when that sid is both vouched for by the browser's
signed `janua_sessions` held-set AND still a live `sessions` row.

## The invariant these tests defend

The header is a session-id *reference*, never a bearer. A header a browser
cannot back with a matching `janua_sessions` held-set MUST be ignored (fall
through to `janua_sso`), never honored — that is what makes a stolen or forged
header non-escalating. These tests are what keep that true.

Precedence: Bearer > X-Janua-Session (held + live) > janua_sso > janua_access_token.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.auth.sessions_cookie import (
    SESSIONS_COOKIE_NAME,
    TAB_SESSION_HEADER,
    mint_sessions_cookie_value,
)
from app.auth.sso_cookie import SSO_COOKIE_NAME, mint_sso_cookie_value
from app.config import settings
from app.core.jwt_manager import jwt_manager
from app.models import UserStatus
from app.routers.v1.oauth_provider import get_user_from_cookie_or_header

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# builders (same shapes as test_oauth_provider_cookie_precedence.py)
# --------------------------------------------------------------------------


def _user(user_id=None, email="persona@example.test", status=UserStatus.ACTIVE):
    return SimpleNamespace(
        id=user_id or uuid4(),
        email=email,
        email_verified=True,
        username="persona",
        first_name="Per",
        last_name="Sona",
        profile_image_url=None,
        is_admin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_sign_in_at=None,
        status=status,
    )


def _session_row(user_id, *, created_at=None, revoked=False, is_active=True, jti=None):
    started = created_at or datetime.utcnow()
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        revoked=revoked,
        is_active=is_active,
        expires_at=datetime.utcnow() + timedelta(days=7),
        revoked_at=None,
        revoked_reason=None,
        created_at=started,
        last_activity=started,
        access_token_jti=jti,
    )


def _hosted_cookie(user, *, jti=None, audience=None):
    now = int(time.time())
    return jwt_manager.encode_token(
        {
            "sub": str(user.id),
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "aud": audience or settings.JWT_AUDIENCE,
            "iat": now,
            "exp": now + 3600,
            "jti": jti or str(uuid4()),
        }
    )


def _request(cookies, headers=None):
    request = MagicMock()
    request.headers = headers or {}
    request.cookies = cookies
    return request


def _db(*, sessions=None, users=None):
    """A db answering the two query shapes resolution issues (see precedence test)."""
    sessions = list(sessions or [])
    users = list(users or [])

    async def execute(statement):
        entity = statement.column_descriptions[0]["entity"]
        name = getattr(entity, "__name__", "")
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if name == "Session":
            match = next(
                (
                    s
                    for s in sessions
                    if str(s.id) in compiled
                    or (s.access_token_jti and f"'{s.access_token_jti}'" in compiled)
                ),
                None,
            )
        else:
            match = next((u for u in users if str(u.id) in compiled), None)
        return SimpleNamespace(scalar_one_or_none=lambda m=match: m)

    return SimpleNamespace(execute=AsyncMock(side_effect=execute), commit=AsyncMock())


def _two_accounts():
    """A browser holding two live estate accounts, `aldo` fronted, `admin` held.

    Returns (aldo, admin, aldo_session, admin_session, cookies) where `cookies`
    fronts `aldo` via `janua_sso` and vouches for BOTH via `janua_sessions`.
    """
    aldo = _user(email="aldo@example.test")
    admin = _user(email="admin@example.test")
    aldo_session = _session_row(aldo.id)
    admin_session = _session_row(admin.id)
    cookies = {
        SSO_COOKIE_NAME: mint_sso_cookie_value(str(aldo.id), str(aldo_session.id)),
        SESSIONS_COOKIE_NAME: mint_sessions_cookie_value(
            [str(aldo_session.id), str(admin_session.id)]
        ),
    }
    return aldo, admin, aldo_session, admin_session, cookies


# --------------------------------------------------------------------------
# (a) the header does its job: front a held account in this tab
# --------------------------------------------------------------------------


class TestHeaderFrontsHeldAccount:
    async def test_header_selects_the_held_admin_over_fronted_aldo(self):
        """The point of the feature: this tab is `admin@` though `janua_sso` = `aldo@`."""
        aldo, admin, aldo_session, admin_session, cookies = _two_accounts()
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(admin_session.id)}),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is admin

    async def test_no_header_still_fronts_the_cookie_account(self):
        """A tab with no header follows `janua_sso`, byte-for-byte as today."""
        aldo, admin, aldo_session, admin_session, cookies = _two_accounts()
        resolved = await get_user_from_cookie_or_header(
            _request(cookies),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is aldo

    async def test_header_naming_the_fronted_account_is_a_no_op(self):
        """Header == the fronted sid resolves the same person, not a contradiction."""
        aldo, admin, aldo_session, admin_session, cookies = _two_accounts()
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(aldo_session.id)}),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is aldo


# --------------------------------------------------------------------------
# (b) the invariant: an un-vouched or dead header is IGNORED, never honored
# --------------------------------------------------------------------------


class TestHeaderCannotEscalate:
    async def test_header_sid_not_in_held_set_is_ignored(self):
        """A sid the `janua_sessions` cookie does not vouch for cannot be fronted.

        This is the core non-escalation case: a forged/stolen header naming a
        real session that this browser was never granted falls through to
        `janua_sso` — it never fronts the stranger.
        """
        aldo = _user(email="aldo@example.test")
        stranger = _user(email="stranger@example.test")
        aldo_session = _session_row(aldo.id)
        stranger_session = _session_row(stranger.id)  # live, but NOT held
        cookies = {
            SSO_COOKIE_NAME: mint_sso_cookie_value(str(aldo.id), str(aldo_session.id)),
            SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([str(aldo_session.id)]),
        }
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(stranger_session.id)}),
            _db(sessions=[aldo_session, stranger_session], users=[aldo, stranger]),
        )
        assert resolved is aldo  # fell through to janua_sso, did NOT escalate

    async def test_header_with_no_sessions_cookie_is_ignored(self):
        """No `janua_sessions` cookie ⇒ empty held-set ⇒ header vouches for nothing."""
        aldo = _user(email="aldo@example.test")
        admin = _user(email="admin@example.test")
        aldo_session = _session_row(aldo.id)
        admin_session = _session_row(admin.id)
        cookies = {
            SSO_COOKIE_NAME: mint_sso_cookie_value(str(aldo.id), str(aldo_session.id)),
        }
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(admin_session.id)}),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is aldo

    async def test_header_naming_a_held_but_revoked_session_is_ignored(self):
        """Even a HELD sid falls through if its row is no longer live."""
        aldo = _user(email="aldo@example.test")
        admin = _user(email="admin@example.test")
        aldo_session = _session_row(aldo.id)
        admin_session = _session_row(admin.id, revoked=True)  # held but dead
        cookies = {
            SSO_COOKIE_NAME: mint_sso_cookie_value(str(aldo.id), str(aldo_session.id)),
            SESSIONS_COOKIE_NAME: mint_sessions_cookie_value(
                [str(aldo_session.id), str(admin_session.id)]
            ),
        }
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(admin_session.id)}),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is aldo

    async def test_header_naming_a_held_session_of_a_suspended_user_is_ignored(self):
        """A live row of a non-active user is refused, same as every estate path."""
        aldo = _user(email="aldo@example.test")
        admin = _user(email="admin@example.test", status=UserStatus.SUSPENDED)
        aldo_session = _session_row(aldo.id)
        admin_session = _session_row(admin.id)
        cookies = {
            SSO_COOKIE_NAME: mint_sso_cookie_value(str(aldo.id), str(aldo_session.id)),
            SESSIONS_COOKIE_NAME: mint_sessions_cookie_value(
                [str(aldo_session.id), str(admin_session.id)]
            ),
        }
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(admin_session.id)}),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is aldo

    async def test_forged_sessions_cookie_does_not_vouch(self):
        """A `janua_sessions` value that is not a valid signed set vouches for nobody.

        `read_sessions_cookie` returns an empty list for an unsigned/garbage
        value, so a browser cannot hand-craft a held-set to admit a header.
        """
        aldo = _user(email="aldo@example.test")
        admin = _user(email="admin@example.test")
        aldo_session = _session_row(aldo.id)
        admin_session = _session_row(admin.id)
        cookies = {
            SSO_COOKIE_NAME: mint_sso_cookie_value(str(aldo.id), str(aldo_session.id)),
            SESSIONS_COOKIE_NAME: "not-a-signed-jwt",
        }
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(admin_session.id)}),
            _db(sessions=[aldo_session, admin_session], users=[aldo, admin]),
        )
        assert resolved is aldo


# --------------------------------------------------------------------------
# (c) an explicit Bearer still outranks the per-tab header
# --------------------------------------------------------------------------


class TestBearerOutranksHeader:
    async def test_bearer_wins_over_a_valid_tab_header(self):
        """A bearer names the identity per request explicitly; it stays first."""
        aldo, admin, aldo_session, admin_session, cookies = _two_accounts()
        api_user = _user(email="api@example.test")
        headers = {
            "Authorization": f"Bearer {_hosted_cookie(api_user)}",
            TAB_SESSION_HEADER: str(admin_session.id),
        }
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers=headers),
            _db(
                sessions=[aldo_session, admin_session],
                users=[aldo, admin, api_user],
            ),
        )
        assert resolved is api_user


# --------------------------------------------------------------------------
# (d) header overrides even a disagreeing hosted cookie — it is above both
# --------------------------------------------------------------------------


class TestHeaderAboveCookies:
    async def test_held_header_beats_a_hosted_cookie_naming_someone_else(self):
        """The tab header sits above janua_sso AND janua_access_token."""
        aldo, admin, aldo_session, admin_session, cookies = _two_accounts()
        operator = _user(email="operator@example.test")
        operator_jti = str(uuid4())
        operator_session = _session_row(operator.id, jti=operator_jti)
        cookies["janua_access_token"] = _hosted_cookie(operator, jti=operator_jti)
        resolved = await get_user_from_cookie_or_header(
            _request(cookies, headers={TAB_SESSION_HEADER: str(admin_session.id)}),
            _db(
                sessions=[aldo_session, admin_session, operator_session],
                users=[aldo, admin, operator],
            ),
        )
        assert resolved is admin
