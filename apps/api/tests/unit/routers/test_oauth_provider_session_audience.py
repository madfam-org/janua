"""`/authorize` must accept the session cookie a magic-link login writes (B2).

A magic-link session carries the audience of the product it forwards to
(`_session_audience_for_redirect` in routers/v1/auth.py) — `crea-map`,
`nauta-portal`, not the platform `JWT_AUDIENCE`. `get_user_from_cookie_or_header`
validated against the platform audience only, so without this the cookie B1
writes is silently rejected at `/authorize` and `prompt=none` answers
`login_required` with nothing wrong visible anywhere in the happy path
(sso-map-erp-equivalencia.md findings #11-#13, risk §5.1).

The tolerance mirrors `AuthService.verify_token`: Janua is the ISSUER reading
a token it minted, so it accepts every audience it issues, while signature,
issuer, expiry and token type stay enforced.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.config import settings
from app.core.jwt_manager import jwt_manager
from app.routers.v1.oauth_provider import (
    _verify_own_access_token,
    get_user_from_cookie_or_header,
)

pytestmark = pytest.mark.asyncio


def _token(*, audience, token_type="access", issuer=None, sub=None, expired=False):
    now = int(time.time())
    claims = {
        "sub": sub or str(uuid4()),
        "type": token_type,
        "iss": issuer if issuer is not None else settings.JWT_ISSUER,
        "iat": now,
        "exp": now - 60 if expired else now + 3600,
        "jti": str(uuid4()),
    }
    if audience is not None:
        claims["aud"] = audience
    return jwt_manager.encode_token(claims)


class TestVerifyOwnAccessToken:
    def test_platform_audience_accepted(self):
        payload = _verify_own_access_token(_token(audience=settings.JWT_AUDIENCE))
        assert payload and payload["aud"] == settings.JWT_AUDIENCE

    def test_product_audience_accepted(self):
        """The crea-map case — the whole point of B2."""
        payload = _verify_own_access_token(_token(audience="crea-map"))
        assert payload and payload["aud"] == "crea-map"

    def test_nauta_portal_audience_accepted(self):
        payload = _verify_own_access_token(_token(audience="nauta-portal"))
        assert payload and payload["aud"] == "nauta-portal"

    def test_token_without_audience_rejected(self):
        """Tolerating every audience Janua mints is not the same as tolerating
        none — AuthService refuses this too."""
        assert _verify_own_access_token(_token(audience=None)) is None

    def test_empty_audience_rejected(self):
        assert _verify_own_access_token(_token(audience="")) is None

    def test_wrong_issuer_still_rejected(self):
        assert _verify_own_access_token(_token(audience="crea-map", issuer="https://evil")) is None

    def test_expired_token_still_rejected(self):
        assert _verify_own_access_token(_token(audience="crea-map", expired=True)) is None

    def test_refresh_token_still_rejected(self):
        """Token type is enforced in both passes."""
        assert _verify_own_access_token(_token(audience="crea-map", token_type="refresh")) is None

    def test_bad_signature_rejected(self):
        good = _token(audience="crea-map")
        tampered = good[:-4] + ("aaaa" if not good.endswith("aaaa") else "bbbb")
        assert _verify_own_access_token(tampered) is None


class TestGetUserFromCookieOrHeader:
    def _db_returning(self, user):
        return SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(scalar_one_or_none=lambda: user)
            )
        )

    def _request(self, *, cookie=None, header=None):
        req = MagicMock()
        req.cookies = {"janua_access_token": cookie} if cookie else {}
        req.headers = {"Authorization": f"Bearer {header}"} if header else {}
        return req

    async def test_cookie_with_product_audience_resolves_the_user(self):
        user_id = str(uuid4())
        user = SimpleNamespace(id=user_id)
        resolved = await get_user_from_cookie_or_header(
            self._request(cookie=_token(audience="crea-map", sub=user_id)),
            self._db_returning(user),
        )
        assert resolved is user

    async def test_cookie_with_unknown_audience_still_resolves_when_janua_minted_it(self):
        """A registered product audience Janua does not hard-code is still an
        audience Janua minted — the signature is what proves that."""
        user_id = str(uuid4())
        user = SimpleNamespace(id=user_id)
        resolved = await get_user_from_cookie_or_header(
            self._request(cookie=_token(audience="some-future-product", sub=user_id)),
            self._db_returning(user),
        )
        assert resolved is user

    async def test_cookie_signed_by_someone_else_is_rejected(self):
        forged = pyjwt.encode(
            {
                "sub": str(uuid4()),
                "type": "access",
                "aud": "crea-map",
                "iss": settings.JWT_ISSUER,
                "exp": int(time.time()) + 3600,
            },
            "an-entirely-different-secret",
            algorithm="HS256",
        )
        resolved = await get_user_from_cookie_or_header(
            self._request(cookie=forged), self._db_returning(SimpleNamespace(id="x"))
        )
        assert resolved is None

    async def test_cookie_without_audience_is_rejected(self):
        resolved = await get_user_from_cookie_or_header(
            self._request(cookie=_token(audience=None)),
            self._db_returning(SimpleNamespace(id="x")),
        )
        assert resolved is None

    async def test_bearer_header_gets_the_same_tolerance(self):
        user_id = str(uuid4())
        user = SimpleNamespace(id=user_id)
        resolved = await get_user_from_cookie_or_header(
            self._request(header=_token(audience="nauta-portal", sub=user_id)),
            self._db_returning(user),
        )
        assert resolved is user

    async def test_no_credentials_returns_none(self):
        resolved = await get_user_from_cookie_or_header(
            self._request(), self._db_returning(SimpleNamespace(id="x"))
        )
        assert resolved is None


class TestJwtManagerVerifyAudienceFlag:
    def test_default_still_enforces_the_platform_audience(self):
        """Every pre-existing caller must keep strict validation."""
        assert jwt_manager.verify_token(_token(audience="crea-map"), token_type="access") is None

    def test_flag_off_accepts_a_foreign_audience(self):
        payload = jwt_manager.verify_token(
            _token(audience="crea-map"), token_type="access", verify_audience=False
        )
        assert payload and payload["aud"] == "crea-map"

    def test_flag_off_does_not_relax_the_issuer(self):
        assert (
            jwt_manager.verify_token(
                _token(audience="crea-map", issuer="https://evil"),
                token_type="access",
                verify_audience=False,
            )
            is None
        )
