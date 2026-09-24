"""First-party clients are pre-consented at /authorize (B6).

Consent exists so a person can refuse a THIRD party access to their Janua
account. It communicates nothing when the client IS MADFAM, and on the silent
path it is not even askable: `prompt=none` cannot render a screen, so a missing
consent row became `consent_required` and the silent hop failed for a client
nobody would have refused (sso-map-erp-equivalencia.md §3 (B6),
oauth_provider.py consent_required branch).

The predicate is deliberately the same one that gates `prompt=none`, so the set
of clients that skip the screen can never drift wider than the set trusted to
authenticate silently.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.routers.v1.oauth_provider import (
    _is_first_party_preconsented,
    _is_silent_auth_allowed,
    authorize_get,
)

pytestmark = pytest.mark.asyncio


def _client(
    *,
    name="selva-office-prod",
    is_active=True,
    is_confidential=True,
    allowed_scopes=None,
):
    return SimpleNamespace(
        client_id="a-client",
        name=name,
        is_active=is_active,
        is_confidential=is_confidential,
        allowed_scopes=allowed_scopes or ["openid", "profile", "email"],
        redirect_uris=["https://app.example/cb"],
        audience=None,
        last_used_at=None,
    )


class TestIsFirstPartyPreconsented:
    def test_selva_office_preconsented(self):
        assert _is_first_party_preconsented(_client(name="selva-office-prod"))

    def test_madfam_prefixed_preconsented(self):
        assert _is_first_party_preconsented(_client(name="madfam-nauta"))

    def test_operator_granted_silent_auth_scope_preconsented(self):
        """This is how crea-map and the nauta portal qualify: their names
        ("MAP · Crea Tu Mundo") do not match the prefixes, so an operator adds
        `madfam:silent_auth` to allowed_scopes."""
        assert _is_first_party_preconsented(
            _client(name="MAP · Crea Tu Mundo", allowed_scopes=["openid", "madfam:silent_auth"])
        )

    def test_third_party_not_preconsented(self):
        assert not _is_first_party_preconsented(_client(name="some-vendor-app"))

    def test_public_client_not_preconsented(self):
        assert not _is_first_party_preconsented(_client(is_confidential=False))

    def test_inactive_client_not_preconsented(self):
        assert not _is_first_party_preconsented(_client(is_active=False))

    def test_predicate_matches_silent_auth_gate_exactly(self):
        """Pin the invariant, not just today's answers: widening one must never
        quietly widen the other."""
        cases = [
            _client(name="selva-office-prod"),
            _client(name="madfam-nauta"),
            _client(name="MAP · Crea Tu Mundo", allowed_scopes=["madfam:silent_auth"]),
            _client(name="some-vendor-app"),
            _client(is_confidential=False),
            _client(is_active=False),
            _client(name="MAP · Crea Tu Mundo"),
        ]
        for c in cases:
            assert _is_first_party_preconsented(c) is _is_silent_auth_allowed(c), c.name


class TestInteractiveConsentScreen:
    """The interactive path: first party skips the screen, third party sees it."""

    def _kwargs(self, client_id="a-client"):
        return dict(
            request=MagicMock(),
            response_type="code",
            client_id=client_id,
            redirect_uri="https://app.example/cb",
            scope="openid profile",
            state="st",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt=None,
            db=AsyncMock(),
            redis=AsyncMock(),
        )

    async def _run(self, client):
        user = SimpleNamespace(
            id=uuid4(), email="a@madfam.io", email_verified=True, created_at=None
        )
        kwargs = self._kwargs()
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client", AsyncMock(return_value=client)
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri", MagicMock(return_value=True)
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.parse_scopes",
                MagicMock(return_value=["openid", "profile"]),
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.has_consent",
                AsyncMock(return_value=False),
            ),
            patch("app.routers.v1.oauth_provider._store_auth_code", AsyncMock()),
            patch("app.routers.v1.oauth_provider._generate_csrf_token", AsyncMock(return_value="c")),
            patch(
                "app.routers.v1.oauth_provider.settings",
                MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
            ),
        ):
            kwargs["db"].commit = AsyncMock()
            return await authorize_get(**kwargs)

    async def test_first_party_skips_the_screen_and_gets_a_code(self):
        resp = await self._run(_client(name="selva-office-prod"))
        assert resp.status_code == 302
        assert "code=" in resp.headers["location"]

    async def test_third_party_still_sees_the_consent_screen(self):
        """B6 must not weaken consent for anyone outside MADFAM."""
        resp = await self._run(_client(name="some-vendor-app"))
        assert resp.status_code == 200
        assert "location" not in {k.lower() for k in resp.headers}


class TestSilentAuthNoLongerBlockedByConsent:
    async def test_operator_scoped_client_completes_the_silent_hop(self):
        """The crea-map / nauta-portal case end to end: a client whose name does
        not match the prefixes, opted in by an operator with
        `madfam:silent_auth`, now completes prompt=none instead of bouncing on
        consent_required."""
        client = _client(
            name="MAP · Crea Tu Mundo", allowed_scopes=["openid", "madfam:silent_auth"]
        )
        user = SimpleNamespace(
            id=uuid4(), email="dir@crea.example", email_verified=True, created_at=None
        )
        kwargs = dict(
            request=MagicMock(),
            response_type="code",
            client_id="a-client",
            redirect_uri="https://app.example/cb",
            scope="openid profile",
            state="st",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt="none",
            db=AsyncMock(),
            redis=AsyncMock(),
        )
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client", AsyncMock(return_value=client)
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri", MagicMock(return_value=True)
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.parse_scopes",
                MagicMock(return_value=["openid", "profile"]),
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.has_consent",
                AsyncMock(return_value=False),
            ),
            patch("app.routers.v1.oauth_provider._store_auth_code", AsyncMock()),
            patch(
                "app.routers.v1.oauth_provider.settings",
                MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
            ),
        ):
            kwargs["db"].commit = AsyncMock()
            resp = await authorize_get(**kwargs)
        loc = resp.headers["location"]
        assert "code=" in loc
        assert "error=" not in loc

    async def test_third_party_silent_request_still_refused_before_consent(self):
        """A third party never reaches the consent question on prompt=none —
        it is stopped earlier by the silent-auth client gate."""
        client = _client(name="some-vendor-app")
        kwargs = dict(
            request=MagicMock(),
            response_type="code",
            client_id="a-client",
            redirect_uri="https://app.example/cb",
            scope="openid",
            state="st",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt="none",
            db=AsyncMock(),
            redis=AsyncMock(),
        )
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client", AsyncMock(return_value=client)
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri", MagicMock(return_value=True)
            ),
        ):
            resp = await authorize_get(**kwargs)
        assert "error=interaction_required" in resp.headers["location"]
