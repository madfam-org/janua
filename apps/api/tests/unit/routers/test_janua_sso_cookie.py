"""`janua_sso` — the estate cookie that actually reaches the browser (J5/R1).

B1 (#593) made every magic-link path set `janua_access_token` /
`janua_refresh_token`. But the MAP and the nauta ERP portal exchange the magic
link **server-to-server**, so those `Set-Cookie` headers land on a fetch response
inside a Next process and are dropped. A person signed into the MAP was still
asked for a second email at the ERP.

`@madfam/janua-next@0.2.0` relays, byte for byte, any `Set-Cookie` line whose
cookie is named exactly `janua_sso`. These tests pin what Janua must put on that
line, and — the half that matters more — that the cookie is a *revocable session
reference*, never a credential:

* every session-establishing path emits it, with HttpOnly + Secure + Lax + Path=/
* `/authorize` recognises a person from `janua_sso` ALONE, silently and
  interactively
* a revoked or expired session stops authenticating the cookie immediately
* logout revokes the row *and* deletes the cookie with the same Domain/Path
* a failed exchange emits nothing
* the cookie is refused everywhere except the authorize flow
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Response

from app.auth import sso_cookie
from app.auth.sso_cookie import (
    SSO_COOKIE_NAME,
    SSO_TOKEN_TYPE,
    clear_sso_cookie,
    mint_sso_cookie_value,
    resolve_sso_cookie_user,
    set_sso_cookie,
)
from app.core.jwt_manager import jwt_manager
from app.models import UserStatus
from app.routers.v1 import auth as auth_router
from app.routers.v1 import oauth_provider as oauth_provider_router

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# fixtures / builders
# --------------------------------------------------------------------------


def _cookie_headers(response) -> list[str]:
    return [v.decode() for k, v in response.raw_headers if k.lower() == b"set-cookie"]


def _sso_header(response) -> str:
    return next(c for c in _cookie_headers(response) if c.startswith(f"{SSO_COOKIE_NAME}="))


def _user(status=UserStatus.ACTIVE, user_id=None):
    return SimpleNamespace(
        id=user_id or uuid4(),
        email="persona@example.test",
        email_verified=True,
        username="persona",
        first_name="Per",
        last_name="Sona",
        profile_image_url=None,
        is_admin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_sign_in_at=None,
        locale="es-MX",
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


def _lookup_db(*rows):
    """A db whose successive `execute` calls return the given scalar results."""
    db = SimpleNamespace()
    db.execute = AsyncMock(
        side_effect=[SimpleNamespace(scalar_one_or_none=lambda r=r: r) for r in rows]
    )
    db.commit = AsyncMock()
    return db


def _magic_link(redirect_url):
    return SimpleNamespace(
        token="magic-token",
        used_at=None,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        user_id=uuid4(),
        redirect_url=redirect_url,
    )


def _magic_db(magic_link, user):
    db = SimpleNamespace()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one_or_none=lambda ml=magic_link: ml),
            SimpleNamespace(scalar_one_or_none=lambda u=user: u),
        ]
    )
    db.commit = AsyncMock()
    return db


def _req(cookies=None):
    req = MagicMock()
    req.client = SimpleNamespace(host="203.0.113.9")
    req.headers = {"user-agent": "pytest"}
    req.cookies = cookies or {}
    return req


# --------------------------------------------------------------------------
# 1. Cookie attributes — what the relay copies byte for byte
# --------------------------------------------------------------------------


class TestCookieAttributes:
    def test_attributes_match_the_relay_contract(self):
        """The SDK fixture models:
        `janua_sso=<v>; Path=/; Domain=.example.test; HttpOnly; Secure; SameSite=Lax; Max-Age=…`
        """
        user = _user()
        session = _session_row(user.id)
        response = Response()
        with patch.object(sso_cookie.settings, "COOKIE_DOMAIN", ".example.test"):
            assert set_sso_cookie(response, str(user.id), session) is True
            header = _sso_header(response)

        assert "HttpOnly" in header
        assert "Secure" in header
        assert "samesite=lax" in header.lower()
        assert "Path=/" in header
        assert "Domain=.example.test" in header

    def test_max_age_is_the_refresh_session_lifetime(self):
        expected = sso_cookie.settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        assert sso_cookie.sso_cookie_max_age() == expected

        response = Response()
        set_sso_cookie(response, str(uuid4()), _session_row(uuid4()))
        assert f"Max-Age={expected}" in _sso_header(response)

    def test_host_only_when_cookie_domain_is_unset(self):
        """The relay refuses a host-only cookie — estate SSO REQUIRES COOKIE_DOMAIN.
        Janua still emits the cookie (it is a valid issuer-host session); it just
        does not travel. This pins that the absence is the operator's, not a bug.
        """
        response = Response()
        with patch.object(sso_cookie.settings, "COOKIE_DOMAIN", None):
            set_sso_cookie(response, str(uuid4()), _session_row(uuid4()))
        assert "Domain=" not in _sso_header(response)

    def test_no_cookie_without_a_resolvable_session_row(self):
        """Never emit a reference that could not be revoked."""
        response = Response()
        assert set_sso_cookie(response, str(uuid4()), SimpleNamespace()) is False
        assert _cookie_headers(response) == []

    def test_delete_uses_the_same_domain_and_path(self):
        """A deletion differing on Domain or Path clears a DIFFERENT cookie."""
        response = Response()
        with patch.object(sso_cookie.settings, "COOKIE_DOMAIN", ".example.test"):
            clear_sso_cookie(response)
        header = _sso_header(response)
        assert "Domain=.example.test" in header
        assert "Path=/" in header
        assert "Max-Age=0" in header


# --------------------------------------------------------------------------
# 2. Each emitting path
# --------------------------------------------------------------------------


class TestEmittingPaths:
    async def test_verify_magic_link_post_emits_the_cookie(self):
        """The path the MAP and the ERP actually use (server-to-server)."""
        user = _user()
        session = _session_row(user.id)
        db = _magic_db(_magic_link("https://map.example.test/acceso"), user)
        response = Response()
        with (
            patch.object(
                auth_router.AuthService,
                "create_session",
                AsyncMock(return_value=("ACCESS-TOK", "REFRESH-TOK", session)),
            ),
            patch.object(
                auth_router, "_session_audience_for_redirect", AsyncMock(return_value="map")
            ),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch("app.auth.mfa_enforcement.mfa_required_for", MagicMock(return_value=False)),
        ):
            body = await auth_router.verify_magic_link(
                SimpleNamespace(token="magic-token"), _req(), response, db
            )

        header = _sso_header(response)
        assert "HttpOnly" in header and "Secure" in header
        # The body contract #593 pinned is untouched.
        assert body.tokens.access_token == "ACCESS-TOK"

    async def test_magic_link_callback_get_emits_the_cookie(self):
        user = _user()
        session = _session_row(user.id)
        db = _magic_db(_magic_link("https://map.example.test/acceso"), user)
        with (
            patch.object(
                auth_router.AuthService,
                "create_session",
                AsyncMock(return_value=("ACCESS-TOK", "REFRESH-TOK", session)),
            ),
            patch.object(
                auth_router, "_session_audience_for_redirect", AsyncMock(return_value="map")
            ),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(
                auth_router,
                "validate_redirect_url",
                MagicMock(return_value="https://map.example.test/acceso"),
            ),
            patch("app.auth.mfa_enforcement.mfa_required_for", MagicMock(return_value=False)),
        ):
            resp = await auth_router.magic_link_callback(token="magic-token", req=_req(), db=db)

        assert resp.status_code == 302
        assert "?token=ACCESS-TOK" in resp.headers["location"]
        assert "HttpOnly" in _sso_header(resp)

    def test_all_four_session_paths_pass_user_and_session_to_the_helper(self):
        """Source-level pin, mirroring test_magic_link_session_cookie.py. A path
        that mints a session without naming it here silently stops emitting the
        estate cookie — and SSO regresses with nothing visibly broken."""
        import inspect

        for handler in (
            auth_router.login_form,
            auth_router.login_form_mfa,
            auth_router.magic_link_callback,
            auth_router.verify_magic_link,
        ):
            src = inspect.getsource(handler)
            assert "user=user, session=session" in src, handler.__name__

    def test_helper_emits_nothing_when_the_caller_names_no_session(self):
        """`_set_session_cookies` keeps its old two-cookie behaviour for any
        caller that cannot identify the row — additive, never a surprise."""
        response = Response()
        auth_router._set_session_cookies(response, "A", "R")
        names = {c.split("=", 1)[0] for c in _cookie_headers(response)}
        assert names == {"janua_access_token", "janua_refresh_token"}


# --------------------------------------------------------------------------
# 3. A failed exchange sets nothing
# --------------------------------------------------------------------------


class TestFailedExchangeSetsNothing:
    async def test_mfa_interrupt_emits_no_sso_cookie(self):
        user = _user()
        db = _magic_db(_magic_link(None), user)
        response = Response()
        with (
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch("app.auth.mfa_enforcement.mfa_required_for", MagicMock(return_value=True)),
            patch(
                "app.auth.mfa_enforcement.mint_mfa_challenge_token",
                MagicMock(return_value="mfa-tok"),
            ),
        ):
            body = await auth_router.verify_magic_link(
                SimpleNamespace(token="magic-token"), _req(), response, db
            )
        assert body.mfa_required is True
        assert _cookie_headers(response) == []

    async def test_invalid_magic_link_emits_no_sso_cookie(self):
        from fastapi import HTTPException

        db = _lookup_db(None)
        response = Response()
        with pytest.raises(HTTPException):
            await auth_router.verify_magic_link(SimpleNamespace(token="nope"), _req(), response, db)
        assert _cookie_headers(response) == []

    async def test_rejected_destination_emits_no_sso_cookie(self):
        user = _user()
        db = _magic_db(_magic_link("https://evil.example/x"), user)
        with (
            patch.object(
                auth_router.AuthService,
                "create_session",
                AsyncMock(return_value=("A", "R", _session_row(user.id))),
            ),
            patch.object(
                auth_router, "_session_audience_for_redirect", AsyncMock(return_value=None)
            ),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(auth_router, "validate_redirect_url", MagicMock(return_value=None)),
            patch("app.auth.mfa_enforcement.mfa_required_for", MagicMock(return_value=False)),
        ):
            resp = await auth_router.magic_link_callback(token="magic-token", req=_req(), db=db)
        assert resp.status_code == 400
        assert _cookie_headers(resp) == []


# --------------------------------------------------------------------------
# 4. Resolution — revocable by construction
# --------------------------------------------------------------------------


class TestResolution:
    async def test_live_session_resolves_the_user(self):
        user = _user()
        session = _session_row(user.id)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        db = _lookup_db(session, user)
        assert await resolve_sso_cookie_user(value, db) is user

    async def test_revoked_session_stops_authenticating(self):
        """`/signout` and `invalidate_user_sessions` set `revoked = True`."""
        user = _user()
        session = _session_row(user.id, revoked=True)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is None

    async def test_deactivated_session_stops_authenticating(self):
        """`revoke_token_family` sets `is_active = False` on theft detection."""
        user = _user()
        session = _session_row(user.id, is_active=False)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is None

    async def test_session_limit_eviction_stops_authenticating(self):
        """Revocation reaches the cookie even when nobody logged out.

        `AuthService.create_session` enforces MAX_SESSIONS_PER_IDENTITY by setting
        `revoked = True` on the oldest row. Because resolution re-reads the row
        rather than trusting the signature, that eviction invalidates the evicted
        session's cookie too — which is the point of referencing the row instead
        of carrying a self-contained credential.
        """
        user = _user()
        session = _session_row(user.id)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is user

        session.revoked = True  # what the session-limit eviction writes
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is None

    async def test_expired_session_row_stops_authenticating(self):
        user = _user()
        session = _session_row(user.id, expires_in_days=-1)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is None

    async def test_unknown_session_row_is_refused(self):
        user = _user()
        value = mint_sso_cookie_value(str(user.id), str(uuid4()))
        assert await resolve_sso_cookie_user(value, _lookup_db(None)) is None

    async def test_expired_cookie_is_refused(self):
        user = _user()
        session = _session_row(user.id)
        now = datetime.utcnow()
        value = jwt_manager.encode_token(
            {
                "sub": str(user.id),
                "sid": str(session.id),
                "type": SSO_TOKEN_TYPE,
                "iat": now - timedelta(days=30),
                "exp": now - timedelta(minutes=1),
                "iss": jwt_manager.issuer,
                "aud": jwt_manager.audience,
            }
        )
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is None

    async def test_garbage_and_unsigned_values_are_refused(self):
        for value in ("", "not-a-jwt", "a.b.c"):
            assert await resolve_sso_cookie_user(value, _lookup_db()) is None

    async def test_an_access_token_is_not_accepted_as_an_sso_cookie(self):
        """The type gate runs both ways: an access token cannot masquerade as an
        estate session reference either."""
        user = _user()
        access, _jti, _exp = jwt_manager.create_access_token(user_id=str(user.id), email=user.email)
        assert await resolve_sso_cookie_user(access, _lookup_db()) is None

    async def test_non_active_user_is_refused(self):
        user = _user(status=UserStatus.SUSPENDED)
        session = _session_row(user.id)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is None

    async def test_cookie_survives_a_refresh_rotation(self):
        """Why no re-issue on the /authorize response is needed.

        `AuthService.refresh_tokens` rotates `access_token_jti` /
        `refresh_token_jti` on the SAME `sessions` row and leaves `id` alone. The
        cookie references `id`, so a rotation cannot invalidate it — which is
        exactly why it carries `sid` rather than the refresh token itself. If a
        future change starts keying the cookie off a rotating value, this fails.
        """
        user = _user()
        session = _session_row(user.id)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is user

        session.access_token_jti = "rotated-access-jti"
        session.refresh_token_jti = "rotated-refresh-jti"
        session.expires_at = datetime.utcnow() + timedelta(days=7)
        assert await resolve_sso_cookie_user(value, _lookup_db(session, user)) is user

    async def test_sub_must_match_the_session_row(self):
        """Belt and braces behind the signature: never trust the claim over the row."""
        session = _session_row(uuid4())
        value = mint_sso_cookie_value(str(uuid4()), str(session.id))
        assert await resolve_sso_cookie_user(value, _lookup_db(session)) is None


# --------------------------------------------------------------------------
# 5. `janua_sso` is not a bearer credential
# --------------------------------------------------------------------------


class TestNotABearerCredential:
    def test_cookie_value_carries_a_non_access_token_type(self):
        payload = jwt_manager.get_unverified_claims(
            mint_sso_cookie_value(str(uuid4()), str(uuid4()))
        )
        assert payload["type"] == SSO_TOKEN_TYPE != "access"

    def test_verify_own_access_token_refuses_it(self):
        """`/api/v1/auth/me` and every other API verify `token_type="access"`
        (via get_current_user) or go through this helper. Neither accepts the
        estate cookie's value, so it can never stand in for a bearer token."""
        value = mint_sso_cookie_value(str(uuid4()), str(uuid4()))
        assert oauth_provider_router._verify_own_access_token(value) is None

    async def test_bearer_header_carrying_the_sso_value_does_not_authenticate(self):
        request = MagicMock()
        request.headers = {
            "Authorization": f"Bearer {mint_sso_cookie_value(str(uuid4()), str(uuid4()))}"
        }
        request.cookies = {}
        db = SimpleNamespace(execute=AsyncMock())
        assert await oauth_provider_router.get_user_from_cookie_or_header(request, db) is None

    def test_only_the_authorize_flow_reads_the_cookie(self):
        """Source-level pin. `get_user_from_cookie_or_header` is the sole reader,
        and its only callers are `GET /authorize` and its consent continuation
        `POST /consent`. If another endpoint starts calling it, this fails and
        the acceptance scope gets re-argued deliberately."""
        import inspect
        import re

        src = inspect.getsource(oauth_provider_router)
        assert src.count(SSO_COOKIE_NAME) >= 1
        # Exactly one place reads the cookie off a request.
        readers = re.findall(r"cookies\.get\(SSO_COOKIE_NAME\)", src)
        assert len(readers) == 2, readers  # one in resolution, one in end_session revoke

        callers = {
            name
            for name, obj in vars(oauth_provider_router).items()
            if inspect.isfunction(obj)
            and name != "get_user_from_cookie_or_header"  # its own definition
            and "get_user_from_cookie_or_header(" in inspect.getsource(obj)
        }
        assert callers == {"authorize_get", "handle_consent"}, callers


# --------------------------------------------------------------------------
# 6. /authorize recognises the person from janua_sso ALONE
# --------------------------------------------------------------------------


def _oauth_client(name="madfam-erp", allowed_scopes=None):
    return SimpleNamespace(
        client_id=name,
        is_active=True,
        is_confidential=True,
        name=name,
        allowed_scopes=allowed_scopes or ["openid", "profile", "email"],
        redirect_uris=["https://erp.example.test/auth/callback"],
        audience=None,
        last_used_at=None,
    )


class TestAuthorizeAcceptsTheEstateCookie:
    def _kwargs(self, request, prompt):
        return dict(
            request=request,
            response_type="code",
            client_id="madfam-erp",
            redirect_uri="https://erp.example.test/auth/callback",
            scope="openid profile",
            state="csrf-xyz",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt=prompt,
            db=AsyncMock(),
            redis=AsyncMock(),
        )

    def _request_with_only_the_sso_cookie(self, user, session):
        request = MagicMock()
        request.headers = {}
        request.cookies = {SSO_COOKIE_NAME: mint_sso_cookie_value(str(user.id), str(session.id))}
        return request

    async def _run(self, prompt, *, user, session, session_row_for_db=None):
        request = self._request_with_only_the_sso_cookie(user, session)
        kwargs = self._kwargs(request, prompt)
        kwargs["db"].commit = AsyncMock()
        # The db handed to resolution returns the session row, then the user.
        kwargs["db"].execute = AsyncMock(
            side_effect=[
                SimpleNamespace(
                    scalar_one_or_none=lambda r=(
                        session if session_row_for_db is None else session_row_for_db
                    ): r
                ),
                SimpleNamespace(scalar_one_or_none=lambda u=user: u),
            ]
        )
        with (
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=_oauth_client()),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.parse_scopes",
                MagicMock(return_value=["openid", "profile"]),
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.has_consent",
                AsyncMock(return_value=True),
            ),
            patch("app.routers.v1.oauth_provider._store_auth_code", AsyncMock()),
            patch(
                "app.routers.v1.oauth_provider.settings",
                MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
            ),
        ):
            return await oauth_provider_router.authorize_get(**kwargs)

    async def test_prompt_none_with_only_the_sso_cookie_issues_a_code(self):
        """The whole point: no `janua_access_token` anywhere, silent hop succeeds."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run("none", user=user, session=session)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "code=" in loc
        assert "error=" not in loc

    async def test_interactive_with_only_the_sso_cookie_skips_the_login_page(self):
        """A valid estate session must not be asked to sign in again — that IS SSO."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run(None, user=user, session=session)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "code=" in loc
        assert "/auth/login" not in loc and "/login" not in loc

    async def test_revoked_sso_cookie_gives_login_required(self):
        user = _user()
        session = _session_row(user.id)
        revoked = _session_row(user.id, revoked=True, session_id=session.id)
        resp = await self._run("none", user=user, session=session, session_row_for_db=revoked)
        assert resp.status_code == 302
        assert "error=login_required" in resp.headers["location"]

    async def test_expired_session_row_gives_login_required(self):
        user = _user()
        session = _session_row(user.id)
        expired = _session_row(user.id, expires_in_days=-1, session_id=session.id)
        resp = await self._run("none", user=user, session=session, session_row_for_db=expired)
        assert resp.status_code == 302
        assert "error=login_required" in resp.headers["location"]

    async def test_prompt_login_forces_the_login_form_despite_a_live_cookie(self):
        """prompt=login must re-authenticate even with a valid estate session."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run("login", user=user, session=session)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "/api/v1/auth/login" in loc
        # A forced re-auth must NOT hand back a code off the still-valid cookie.
        assert "code=" not in loc
        assert "error=" not in loc

    async def test_prompt_select_account_degrades_to_login_with_one_session(self):
        """With no chooser yet, select_account forces the login form (spec fallback)."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run("select_account", user=user, session=session)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "/api/v1/auth/login" in loc
        assert "code=" not in loc

    async def test_prompt_login_in_a_set_is_honored(self):
        """prompt is a space-delimited set — 'login consent' must still force login."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run("login consent", user=user, session=session)
        assert resp.status_code == 302
        assert "/api/v1/auth/login" in resp.headers["location"]
        assert "code=" not in resp.headers["location"]

    async def test_absent_prompt_still_reuses_the_session(self):
        """Regression: absent prompt is unchanged — a valid cookie issues a code."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run(None, user=user, session=session)
        assert resp.status_code == 302
        assert "code=" in resp.headers["location"]
        assert "/auth/login" not in resp.headers["location"]

    async def test_prompt_none_still_issues_a_code(self):
        """Regression: prompt=none is unchanged — silent hop still succeeds."""
        user = _user()
        session = _session_row(user.id)
        resp = await self._run("none", user=user, session=session)
        assert resp.status_code == 302
        assert "code=" in resp.headers["location"]

    async def test_prompt_login_does_not_issue_a_code_for_an_mfa_user(self):
        """prompt=login must not bypass MFA: no code, back to the login form.

        The forced-login redirect happens before the MFA gate, so the code path
        cannot issue a code off the cookie; MFA is then proven at the login form.
        """
        user = _user()
        session = _session_row(user.id)
        with patch(
            "app.auth.mfa_enforcement.mfa_required_for",
            MagicMock(return_value=True),
        ):
            resp = await self._run("login", user=user, session=session)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "code=" not in loc
        assert "/api/v1/auth/login" in loc


# --------------------------------------------------------------------------
# 7. Logout clears AND revokes
# --------------------------------------------------------------------------


class TestLogout:
    async def test_signout_revokes_the_row_and_clears_the_cookie(self):
        user = _user()
        session = _session_row(user.id)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        response = Response()
        # verify_token → no payload, so the access-token branch is skipped; then
        # the sso revoke branch looks the session row up.
        db = _lookup_db(session)
        with (
            patch.object(auth_router.AuthService, "verify_token", AsyncMock(return_value=None)),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(auth_router, "log_audit_event", AsyncMock()),
        ):
            body = await auth_router.sign_out(
                current_user=user,
                credentials=SimpleNamespace(credentials="access-tok"),
                db=db,
                req=_req({SSO_COOKIE_NAME: value}),
                response=response,
            )

        assert body == {"message": "Successfully signed out"}
        assert session.revoked is True
        assert session.is_active is False
        assert session.revoked_reason == "logout"
        assert "Max-Age=0" in _sso_header(response)

    async def test_signout_without_the_cookie_still_succeeds(self):
        user = _user()
        response = Response()
        with (
            patch.object(auth_router.AuthService, "verify_token", AsyncMock(return_value=None)),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(auth_router, "log_audit_event", AsyncMock()),
        ):
            body = await auth_router.sign_out(
                current_user=user,
                credentials=SimpleNamespace(credentials="access-tok"),
                db=_lookup_db(),
                req=_req({}),
                response=response,
            )
        assert body == {"message": "Successfully signed out"}
        assert "Max-Age=0" in _sso_header(response)

    @pytest.mark.parametrize("path", ["/auth/logout", "/auth/signout"])
    async def test_logout_routes_revoke_through_a_real_http_request(self, path):
        """`sign_out` takes `req`/`response` with None defaults so its existing
        direct callers keep working — which means a missing FastAPI injection
        would silently skip revocation in production while the unit tests above
        still passed. This drives both real ASGI routes.

        `/auth/logout` is the endpoint `@madfam/janua-next` calls, and the
        `Max-Age=0` line it relays back to the browser is what this asserts.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        user = _user()
        session = _session_row(user.id)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: session)),
            commit=AsyncMock(),
        )

        app = FastAPI()
        app.include_router(auth_router.router)
        app.dependency_overrides[auth_router.get_db] = lambda: db
        app.dependency_overrides[auth_router.get_current_user] = lambda: user

        with (
            patch.object(auth_router.AuthService, "verify_token", AsyncMock(return_value=None)),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(auth_router, "log_audit_event", AsyncMock()),
        ):
            http = TestClient(app)
            http.cookies.set(SSO_COOKIE_NAME, mint_sso_cookie_value(str(user.id), str(session.id)))
            resp = http.post(path, headers={"Authorization": "Bearer access-tok"})

        assert resp.status_code == 200
        assert session.revoked is True, "Request was not injected; revocation was skipped"
        set_cookie = resp.headers.get("set-cookie", "")
        assert SSO_COOKIE_NAME in set_cookie and "Max-Age=0" in set_cookie

    async def test_a_forged_cookie_cannot_revoke_someone_elses_session(self):
        """The signature is verified before anything is revoked."""
        session = _session_row(uuid4())
        db = _lookup_db(session)
        assert await sso_cookie.revoke_sso_cookie_session("forged.value.here", db) is False
        assert session.revoked is False

    async def test_oidc_end_session_revokes_and_clears(self):
        user = _user()
        session = _session_row(user.id)
        value = mint_sso_cookie_value(str(user.id), str(session.id))
        db = _lookup_db(session)
        client = SimpleNamespace(is_active=True, redirect_uris=["https://erp.example.test/goodbye"])
        request = MagicMock()
        request.cookies = {SSO_COOKIE_NAME: value}
        with (
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=client),
            ),
            patch(
                "app.routers.v1.oauth_provider.validate_post_logout_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            resp = await oauth_provider_router.oidc_end_session(
                request=request,
                client_id="madfam-erp",
                post_logout_redirect_uri="https://erp.example.test/goodbye",
                state=None,
                db=db,
            )

        assert resp.status_code == 302
        assert session.revoked is True
        assert "Max-Age=0" in _sso_header(resp)

    async def test_end_session_revokes_through_a_real_http_request(self):
        """`request` is declared last and optional so the pre-existing
        keyword-only callers of `oidc_end_session` keep working. That default
        makes it possible for FastAPI to NOT inject the Request on the real
        route — in which case revocation would silently never run in production
        while every unit test still passed. This drives the actual ASGI route to
        prove the injection happens.

        (`Optional[Request] = None` does not work at all — FastAPI rejects it as
        an invalid Pydantic field — so the bare annotation is load-bearing.)
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        user = _user()
        session = _session_row(user.id)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: session)),
            commit=AsyncMock(),
        )

        app = FastAPI()
        app.include_router(oauth_provider_router.logout_router)
        app.dependency_overrides[oauth_provider_router.get_db] = lambda: db

        client_row = SimpleNamespace(
            is_active=True, redirect_uris=["https://erp.example.test/goodbye"]
        )
        with (
            patch.object(
                oauth_provider_router, "_get_oauth_client", AsyncMock(return_value=client_row)
            ),
            patch.object(
                oauth_provider_router,
                "validate_post_logout_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            http = TestClient(app)
            http.cookies.set(SSO_COOKIE_NAME, mint_sso_cookie_value(str(user.id), str(session.id)))
            resp = http.get(
                "/logout",
                params={
                    "client_id": "madfam-erp",
                    "post_logout_redirect_uri": "https://erp.example.test/goodbye",
                },
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert session.revoked is True, "FastAPI did not inject Request; revocation was skipped"
        assert SSO_COOKIE_NAME in resp.headers.get("set-cookie", "")

    def test_oidc_cookie_clearing_includes_the_estate_cookie(self):
        from fastapi.responses import RedirectResponse

        resp = RedirectResponse(url="https://erp.example.test/goodbye", status_code=302)
        oauth_provider_router._clear_janua_session_cookies(resp)
        names = {c.split("=", 1)[0] for c in _cookie_headers(resp)}
        assert SSO_COOKIE_NAME in names
