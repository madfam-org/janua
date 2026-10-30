"""A magic-link login must leave an issuer-side browser session behind (B1).

Until this landed, `_set_session_cookies` had exactly two callers, both on the
hosted password form (`login_form`, `login_form_mfa`). Nobody on the MAP or the
nauta portal has a password — both products enter by magic link — so no one
ever had a `janua_access_token` cookie on auth.madfam.io, and
`/authorize?prompt=none` (which reads exactly that cookie) could only ever
answer `login_required`. See claudedocs sso-map-erp-equivalencia.md findings
#4-#7.

These tests pin BOTH magic-link doors setting the same cookies the hosted
password form sets, WITHOUT changing either response contract: the POST still
returns the same `SignInResponse` body, the GET still redirects to
`<destination>?token=<access_token>`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Response

from app.routers.v1 import auth as auth_router

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def no_bound_client(monkeypatch):
    # Cookie transport fixtures have no registered product identity pool.
    monkeypatch.setattr(auth_router, "_oauth_client_for_redirect", AsyncMock(return_value=None))


def _user():
    return SimpleNamespace(
        id=uuid4(),
        email="dir@crea.example",
        email_verified=True,
        username="dir",
        first_name="Dir",
        last_name="Eccion",
        profile_image_url=None,
        is_admin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_sign_in_at=None,
        locale="es-MX",
        status="active",
    )


def _magic_link(redirect_url: str | None):
    return SimpleNamespace(
        token="magic-token",
        used_at=None,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        user_id=uuid4(),
        redirect_url=redirect_url,
    )


def _db(magic_link, user):
    """A db whose two `execute` calls return the magic link, then the user."""
    results = [
        SimpleNamespace(scalar_one_or_none=lambda ml=magic_link: ml),
        SimpleNamespace(scalar_one_or_none=lambda u=user: u),
    ]
    db = SimpleNamespace()
    db.execute = AsyncMock(side_effect=results)
    db.commit = AsyncMock()
    return db


def _req():
    req = MagicMock()
    req.client = SimpleNamespace(host="203.0.113.9")
    req.headers = {"user-agent": "pytest"}
    return req


def _cookie_headers(response) -> list[str]:
    return [v for k, v in response.raw_headers if k.lower() == b"set-cookie" for v in [v.decode()]]


class TestVerifyMagicLinkPost:
    async def test_sets_both_session_cookies(self):
        user = _user()
        db = _db(_magic_link("https://crea-map.madfam.io/acceso/verificar"), user)
        response = Response()
        with (
            patch.object(
                auth_router.AuthService,
                "create_session",
                AsyncMock(return_value=("ACCESS-TOK", "REFRESH-TOK", SimpleNamespace())),
            ),
            patch.object(
                auth_router, "_session_audience_for_redirect", AsyncMock(return_value="crea-map")
            ),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch(
                "app.auth.authentication_assurance.user_requires_mfa", AsyncMock(return_value=False)
            ),
        ):
            body = await auth_router.verify_magic_link(
                SimpleNamespace(token="magic-token"), _req(), response, db
            )

        cookies = _cookie_headers(response)
        access = next(c for c in cookies if c.startswith("janua_access_token="))
        refresh = next(c for c in cookies if c.startswith("janua_refresh_token="))
        assert "janua_access_token=ACCESS-TOK" in access
        assert "janua_refresh_token=REFRESH-TOK" in refresh
        # Attributes identical to the hosted password path (auth.py helper).
        assert "HttpOnly" not in access and "Max-Age=3600" in access
        assert "HttpOnly" in refresh and "Max-Age=604800" in refresh
        assert "Secure" in access and "samesite=lax" in access.lower()

        # Response BODY is unchanged: tokens still returned to server callers.
        assert body.tokens.access_token == "ACCESS-TOK"
        assert body.tokens.refresh_token == "REFRESH-TOK"
        assert body.user.email == user.email

    async def test_mfa_interrupt_sets_no_cookies(self):
        """An MFA challenge is not a session — it must not mint one."""
        user = _user()
        db = _db(_magic_link(None), user)
        response = Response()
        with (
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch(
                "app.auth.authentication_assurance.user_requires_mfa", AsyncMock(return_value=True)
            ),
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


class TestMagicLinkCallbackGet:
    async def test_sets_cookies_without_changing_the_redirect(self):
        user = _user()
        db = _db(_magic_link("https://crea-map.madfam.io/acceso/verificar"), user)
        with (
            patch.object(
                auth_router.AuthService,
                "create_session",
                AsyncMock(return_value=("ACCESS-TOK", "REFRESH-TOK", SimpleNamespace())),
            ),
            patch.object(
                auth_router, "_session_audience_for_redirect", AsyncMock(return_value="crea-map")
            ),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(
                auth_router,
                "validate_redirect_url",
                MagicMock(return_value="https://crea-map.madfam.io/acceso/verificar"),
            ),
            patch(
                "app.auth.authentication_assurance.user_requires_mfa", AsyncMock(return_value=False)
            ),
        ):
            resp = await auth_router.magic_link_callback(token="magic-token", req=_req(), db=db)

        # Redirect contract unchanged — products still read ?token= off the URL.
        assert resp.status_code == 302
        assert (
            resp.headers["location"]
            == "https://crea-map.madfam.io/acceso/verificar?token=ACCESS-TOK"
        )

        cookies = _cookie_headers(resp)
        assert any("janua_access_token=ACCESS-TOK" in c for c in cookies)
        assert any("janua_refresh_token=REFRESH-TOK" in c for c in cookies)

    async def test_rejected_destination_still_sets_no_redirect_and_no_cookie(self):
        """When the allowlist rejects the destination we return an HTML page;
        that page is not a session hand-off, so it carries no cookies."""
        user = _user()
        db = _db(_magic_link("https://evil.example/x"), user)
        with (
            patch.object(
                auth_router.AuthService,
                "create_session",
                AsyncMock(return_value=("ACCESS-TOK", "REFRESH-TOK", SimpleNamespace())),
            ),
            patch.object(
                auth_router, "_session_audience_for_redirect", AsyncMock(return_value=None)
            ),
            patch.object(auth_router, "log_activity", AsyncMock()),
            patch.object(auth_router, "validate_redirect_url", MagicMock(return_value=None)),
            patch(
                "app.auth.authentication_assurance.user_requires_mfa", AsyncMock(return_value=False)
            ),
        ):
            resp = await auth_router.magic_link_callback(token="magic-token", req=_req(), db=db)
        assert resp.status_code == 400
        assert _cookie_headers(resp) == []


def test_both_magic_link_paths_call_the_shared_cookie_helper():
    """Source-level pin, mirroring test_magic_link_audience.py: neither door may
    drift back to minting a session without leaving one in the browser."""
    import inspect

    for handler in (auth_router.magic_link_callback, auth_router.verify_magic_link):
        assert "_set_session_cookies" in inspect.getsource(handler), handler.__name__
