"""`janua_sessions` — the companion cookie that holds several estate accounts (Layer 3).

`janua_sso` points at ONE fronted session. `janua_sessions` remembers the whole
set a browser has signed into, so a second account can be added without evicting
the first and the fronted one can be switched with no re-authentication.

These tests pin:
* the cookie mirrors janua_sso's attributes and carries only session-id
  references — never a bearer, and a distinct token type so it authenticates
  nothing but itself
* a completed login APPENDS its sid to the held set (does not replace)
* POST /switch-session re-points janua_sso to a held+live sid, and refuses an
  unheld or non-live sid
* per-account sign-out removes one sid, revokes its row, and re-fronts another
* sign-out-all clears both cookies and revokes every held row
* prompt=select_account renders a chooser over the held sessions
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from app.auth import sessions_cookie
from app.auth.sessions_cookie import (
    SESSIONS_COOKIE_NAME,
    SESSIONS_TOKEN_TYPE,
    append_sid,
    mint_sessions_cookie_value,
    read_sessions_cookie,
    remove_sid,
    set_sessions_cookie,
)
from app.auth.sso_cookie import SSO_COOKIE_NAME, SSO_TOKEN_TYPE, mint_sso_cookie_value
from app.core.jwt_manager import jwt_manager
from app.models import UserStatus
from app.routers.v1 import auth as auth_router
from app.routers.v1 import oauth_provider as oauth_provider_router

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------


def _cookie_headers(response) -> list[str]:
    return [v.decode() for k, v in response.raw_headers if k.lower() == b"set-cookie"]


def _header_for(response, name) -> str:
    return next(c for c in _cookie_headers(response) if c.startswith(f"{name}="))


def _user(status=UserStatus.ACTIVE, user_id=None, email="persona@example.test"):
    return SimpleNamespace(
        id=user_id or uuid4(),
        email=email,
        username="persona",
        status=status,
    )


def _session_row(user_id, *, revoked=False, is_active=True, expires_in_days=7, session_id=None):
    return SimpleNamespace(
        id=session_id or uuid4(),
        user_id=user_id,
        revoked=revoked,
        is_active=is_active,
        expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
        revoked_at=None,
        revoked_reason=None,
    )


def _req(cookies=None):
    req = MagicMock()
    req.cookies = cookies or {}
    return req


# --------------------------------------------------------------------------
# 1. cookie value: references only, distinct type, no bearer
# --------------------------------------------------------------------------


class TestCookieValue:
    def test_round_trips_the_sid_list(self):
        sids = [str(uuid4()), str(uuid4())]
        value = mint_sessions_cookie_value(sids)
        assert read_sessions_cookie(value) == sids

    def test_carries_the_companion_token_type_not_the_sso_one(self):
        value = mint_sessions_cookie_value([str(uuid4())])
        payload = jwt_manager.verify_token(
            value, token_type=SESSIONS_TOKEN_TYPE, verify_audience=False
        )
        assert payload is not None
        # An sso_session token must NOT be readable as a sessions-set cookie.
        assert read_sessions_cookie(mint_sso_cookie_value(str(uuid4()), str(uuid4()))) == []

    def test_a_sessions_cookie_is_not_an_access_bearer(self):
        value = mint_sessions_cookie_value([str(uuid4())])
        # Every bearer path verifies token_type="access"; this value cannot pass.
        assert jwt_manager.verify_token(value, token_type="access") is None

    def test_garbage_and_empty_are_refused(self):
        assert read_sessions_cookie(None) == []
        assert read_sessions_cookie("") == []
        assert read_sessions_cookie("not.a.jwt") == []

    def test_attributes_mirror_the_sso_cookie(self):
        kwargs = sessions_cookie.sessions_cookie_kwargs()
        assert kwargs["httponly"] is True
        assert kwargs["secure"] is True
        assert kwargs["samesite"] == "lax"
        assert kwargs["path"] == "/"

    def test_dedup_preserves_order(self):
        a, b = str(uuid4()), str(uuid4())
        assert read_sessions_cookie(mint_sessions_cookie_value([a, b, a])) == [a, b]


# --------------------------------------------------------------------------
# 2. list ops
# --------------------------------------------------------------------------


class TestListOps:
    def test_append_adds_and_dedupes_to_the_end(self):
        a, b = "sid-a", "sid-b"
        assert append_sid([a], b) == [a, b]
        # re-adding moves it to the freshest position, no duplicate
        assert append_sid([a, b], a) == [b, a]

    def test_append_caps_the_list(self):
        existing = [f"sid-{i}" for i in range(sessions_cookie.MAX_HELD_SESSIONS)]
        result = append_sid(existing, "new")
        assert len(result) == sessions_cookie.MAX_HELD_SESSIONS
        assert result[-1] == "new"
        assert existing[0] not in result  # oldest dropped

    def test_remove(self):
        assert remove_sid(["a", "b", "c"], "b") == ["a", "c"]

    def test_set_empty_clears_the_cookie(self):
        resp = Response()
        set_sessions_cookie(resp, [])
        header = _header_for(resp, SESSIONS_COOKIE_NAME)
        assert "Max-Age=0" in header or "max-age=0" in header


# --------------------------------------------------------------------------
# 3. append on a completed login
# --------------------------------------------------------------------------


class TestAppendOnLogin:
    def test_set_session_cookies_appends_the_new_sid(self):
        user = _user()
        first = str(uuid4())
        session = _session_row(user.id)
        request = _req({SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([first])})
        response = Response()

        auth_router._set_session_cookies(
            response, "acc", "ref", user=user, session=session, request=request
        )

        # janua_sso points at the NEW session; janua_sessions holds both.
        held = read_sessions_cookie(
            _header_for(response, SESSIONS_COOKIE_NAME).split("=", 1)[1].split(";", 1)[0]
        )
        assert held == [first, str(session.id)]

    def test_without_request_only_sets_sso(self):
        """Backward compatible: a caller with no request emits no janua_sessions."""
        user = _user()
        session = _session_row(user.id)
        response = Response()
        auth_router._set_session_cookies(response, "acc", "ref", user=user, session=session)
        names = [c.split("=", 1)[0] for c in _cookie_headers(response)]
        assert SSO_COOKIE_NAME in names
        assert SESSIONS_COOKIE_NAME not in names


# --------------------------------------------------------------------------
# 4. switch-session
# --------------------------------------------------------------------------


class TestSwitchSession:
    async def test_switches_to_a_held_live_session(self):
        user = _user()
        target = _session_row(user.id)
        held_value = mint_sessions_cookie_value([str(target.id)])
        req = _req({SESSIONS_COOKIE_NAME: held_value})
        body = auth_router.SwitchSessionRequest(sid=str(target.id), next="/")

        with patch(
            "app.routers.v1.auth.resolve_session_by_id",
            AsyncMock(return_value=(user, target)),
        ):
            resp = await auth_router.switch_session(body, req, Response(), db=AsyncMock())

        assert resp.status_code == 302
        # janua_sso re-pointed at the chosen sid.
        sso_header = _header_for(resp, SSO_COOKIE_NAME)
        value = sso_header.split("=", 1)[1].split(";", 1)[0]
        payload = jwt_manager.verify_token(value, token_type=SSO_TOKEN_TYPE, verify_audience=False)
        assert payload["sid"] == str(target.id)

    async def test_default_next_carries_no_sid_fragment(self):
        """Byte-for-byte #624: without return_sid the target has no fragment."""
        user = _user()
        target = _session_row(user.id)
        req = _req({SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([str(target.id)])})
        body = auth_router.SwitchSessionRequest(sid=str(target.id), next="/")
        with patch(
            "app.routers.v1.auth.resolve_session_by_id",
            AsyncMock(return_value=(user, target)),
        ):
            resp = await auth_router.switch_session(body, req, Response(), db=AsyncMock())
        assert "#" not in resp.headers["location"]

    async def test_return_sid_appends_the_sid_as_a_fragment(self):
        """Two-tab opt-in: the chosen sid rides back as a URL fragment.

        A fragment is never sent to a server, so the sid leaks to no host log; the
        tab reads it client-side and asserts it per-tab via X-Janua-Session.
        """
        user = _user()
        target = _session_row(user.id)
        req = _req({SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([str(target.id)])})
        body = auth_router.SwitchSessionRequest(
            sid=str(target.id), next="/", return_sid=True
        )
        with patch(
            "app.routers.v1.auth.resolve_session_by_id",
            AsyncMock(return_value=(user, target)),
        ):
            resp = await auth_router.switch_session(body, req, Response(), db=AsyncMock())
        assert resp.headers["location"].endswith(f"#janua_sid={target.id}")

    async def test_rejects_an_unheld_sid(self):
        req = _req({SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([str(uuid4())])})
        body = auth_router.SwitchSessionRequest(sid=str(uuid4()), next="/")
        with pytest.raises(HTTPException) as exc:
            await auth_router.switch_session(body, req, Response(), db=AsyncMock())
        assert exc.value.status_code == 400
        assert "not held" in exc.value.detail

    async def test_rejects_a_held_but_dead_sid(self):
        dead = str(uuid4())
        req = _req({SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([dead])})
        body = auth_router.SwitchSessionRequest(sid=dead, next="/")
        with patch(
            "app.routers.v1.auth.resolve_session_by_id",
            AsyncMock(return_value=(None, None)),
        ):
            with pytest.raises(HTTPException) as exc:
                await auth_router.switch_session(body, req, Response(), db=AsyncMock())
        assert exc.value.status_code == 400
        assert "not active" in exc.value.detail


# --------------------------------------------------------------------------
# 5. per-account and all sign-out
# --------------------------------------------------------------------------


class TestSignOut:
    async def test_sign_out_one_removes_the_sid_and_refronts(self):
        user = _user()
        stay = _session_row(user.id)
        gone_sid = str(uuid4())
        held = [gone_sid, str(stay.id)]
        # fronted cookie points at the one we sign out
        req = _req(
            {
                SESSIONS_COOKIE_NAME: mint_sessions_cookie_value(held),
                SSO_COOKIE_NAME: mint_sso_cookie_value(str(user.id), gone_sid),
            }
        )
        response = Response()
        body = auth_router.SwitchSessionRequest(sid=gone_sid)
        db = AsyncMock()
        with (
            patch("app.routers.v1.auth.revoke_sso_session", AsyncMock(return_value=True)),
            patch(
                "app.routers.v1.auth.resolve_session_by_id",
                AsyncMock(return_value=(user, stay)),
            ),
        ):
            result = await auth_router.sign_out_one_account(body, req, response, db=db)

        assert result["remaining"] == 1
        held_after = read_sessions_cookie(
            _header_for(response, SESSIONS_COOKIE_NAME).split("=", 1)[1].split(";", 1)[0]
        )
        assert held_after == [str(stay.id)]
        # janua_sso re-fronted to the surviving account.
        sso_value = _header_for(response, SSO_COOKIE_NAME).split("=", 1)[1].split(";", 1)[0]
        payload = jwt_manager.verify_token(
            sso_value, token_type=SSO_TOKEN_TYPE, verify_audience=False
        )
        assert payload["sid"] == str(stay.id)

    async def test_sign_out_one_rejects_unheld(self):
        req = _req({SESSIONS_COOKIE_NAME: mint_sessions_cookie_value([str(uuid4())])})
        body = auth_router.SwitchSessionRequest(sid=str(uuid4()))
        with pytest.raises(HTTPException) as exc:
            await auth_router.sign_out_one_account(body, req, Response(), db=AsyncMock())
        assert exc.value.status_code == 400

    async def test_sign_out_all_clears_both_cookies(self):
        user = _user()
        held = [str(uuid4()), str(uuid4())]
        req = _req(
            {
                SESSIONS_COOKIE_NAME: mint_sessions_cookie_value(held),
                SSO_COOKIE_NAME: mint_sso_cookie_value(str(user.id), held[0]),
            }
        )
        response = Response()
        revoke = AsyncMock(return_value=True)
        with patch("app.routers.v1.auth.revoke_sso_session", revoke):
            result = await auth_router.sign_out_all_accounts(req, response, db=AsyncMock())

        assert result["revoked"] == 2
        for name in (SSO_COOKIE_NAME, SESSIONS_COOKIE_NAME):
            header = _header_for(response, name)
            assert "Max-Age=0" in header or "max-age=0" in header
        # every held row was asked to revoke
        assert revoke.await_count == 2


# --------------------------------------------------------------------------
# 6. prompt=select_account chooser
# --------------------------------------------------------------------------


class TestSelectAccountChooser:
    def _authorize_kwargs(self, request):
        return dict(
            request=request,
            response_type="code",
            client_id="madfam-erp",
            redirect_uri="https://erp.example.test/auth/callback",
            scope="openid profile",
            state="csrf",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt="select_account",
            db=AsyncMock(),
            redis=AsyncMock(),
        )

    def _client(self):
        return SimpleNamespace(
            id="c1",
            client_id="madfam-erp",
            is_active=True,
            is_confidential=True,
            name="MADFAM ERP",
            redirect_uris=["https://erp.example.test/auth/callback"],
        )

    async def test_renders_a_chooser_over_held_sessions(self):
        user_a = _user(email="a@example.test")
        user_b = _user(email="b@example.test")
        sess_a = _session_row(user_a.id)
        sess_b = _session_row(user_b.id)
        held = mint_sessions_cookie_value([str(sess_a.id), str(sess_b.id)])
        request = MagicMock()
        request.headers = {}
        request.cookies = {SESSIONS_COOKIE_NAME: held}
        kwargs = self._authorize_kwargs(request)

        async def _resolve(sid, db):
            if sid == str(sess_a.id):
                return user_a, sess_a
            if sid == str(sess_b.id):
                return user_b, sess_b
            return None, None

        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=self._client()),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
            patch(
                "app.routers.v1.oauth_provider.resolve_session_by_id",
                AsyncMock(side_effect=_resolve),
            ),
        ):
            resp = await oauth_provider_router.authorize_get(**kwargs)

        body = resp.body.decode()
        assert "Choose an account" in body
        assert "a@example.test" in body
        assert "b@example.test" in body
        assert "/api/v1/auth/switch-session" in body

    async def test_degrades_to_login_with_no_held_session(self):
        request = MagicMock()
        request.headers = {}
        request.cookies = {}  # no janua_sessions
        kwargs = self._authorize_kwargs(request)
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=self._client()),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            resp = await oauth_provider_router.authorize_get(**kwargs)

        assert resp.status_code == 302
        assert "/api/v1/auth/login" in resp.headers["location"]
