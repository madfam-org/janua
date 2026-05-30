"""
Unit tests for OAuth `prompt=none` silent-auth handling.

Tests target the helpers introduced in the Selva-unified SSO Phase 1 PR:
- _is_silent_auth_allowed: client gating
- _redirect_with_oauth_error: OAuth-spec error redirect builder
- authorize_get with prompt=none in three scenarios:
    * no session → login_required
    * untrusted client → interaction_required
    * session present + consent missing → consent_required
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.routers.v1.oauth_provider import (
    _build_safe_callback_url,
    _is_silent_auth_allowed,
    _redirect_with_oauth_error,
    authorize_get,
)

pytestmark = pytest.mark.asyncio


def _client(
    *,
    is_active: bool = True,
    is_confidential: bool = True,
    name: str = "selva-office-prod",
    allowed_scopes: list[str] | None = None,
    redirect_uris: list[str] | None = None,
    audience: str | None = None,
):
    return SimpleNamespace(
        client_id="selva-office-prod",
        is_active=is_active,
        is_confidential=is_confidential,
        name=name,
        allowed_scopes=allowed_scopes or ["openid", "profile", "email"],
        redirect_uris=redirect_uris or ["https://selva.town/auth/callback"],
        audience=audience,
        last_used_at=None,
    )


class TestIsSilentAuthAllowed:
    def test_first_party_selva_office_allowed(self):
        assert _is_silent_auth_allowed(_client(name="selva-office-prod"))

    def test_madfam_prefixed_clients_allowed(self):
        assert _is_silent_auth_allowed(_client(name="madfam-internal"))

    def test_inactive_client_rejected(self):
        assert not _is_silent_auth_allowed(_client(is_active=False))

    def test_public_client_rejected(self):
        assert not _is_silent_auth_allowed(_client(is_confidential=False))

    def test_third_party_client_rejected(self):
        assert not _is_silent_auth_allowed(_client(name="random-third-party"))

    def test_explicit_opt_in_via_scope_allowed(self):
        assert _is_silent_auth_allowed(
            _client(
                name="random-tenant-xyz",
                allowed_scopes=["openid", "madfam:silent_auth"],
            )
        )


class TestRedirectWithOauthError:
    def test_includes_error_and_state(self):
        resp = _redirect_with_oauth_error(
            "https://selva.town/cb",
            error="login_required",
            error_description="No session",
            state="xyz",
            client_validated=True,
        )
        assert resp.status_code == 302
        assert "error=login_required" in resp.headers["location"]
        assert "state=xyz" in resp.headers["location"]

    def test_omits_state_when_absent(self):
        resp = _redirect_with_oauth_error(
            "https://selva.town/cb",
            error="consent_required",
            error_description="x",
            state=None,
            client_validated=True,
        )
        assert "state=" not in resp.headers["location"]


class TestAuthorizeGetSilentAuth:
    """End-to-end of the prompt=none code path inside authorize_get.

    We mock out: client lookup, redirect-URI validation, user resolution,
    consent service, settings, and email-verification gating.
    """

    @pytest.fixture
    def base_kwargs(self):
        return dict(
            request=MagicMock(),
            response_type="code",
            client_id="selva-office-prod",
            redirect_uri="https://selva.town/auth/callback",
            scope="openid profile",
            state="csrf-xyz",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            prompt="none",
            db=AsyncMock(),
            redis=AsyncMock(),
        )

    async def test_no_session_emits_login_required(self, base_kwargs):
        client = _client()
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=client),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            resp = await authorize_get(**base_kwargs)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "error=login_required" in loc
        assert "state=csrf-xyz" in loc

    async def test_untrusted_client_emits_interaction_required(self, base_kwargs):
        third_party = _client(name="random-thirdparty")
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=third_party),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            resp = await authorize_get(**base_kwargs)
        assert resp.status_code == 302
        assert "error=interaction_required" in resp.headers["location"]

    async def test_consent_missing_emits_consent_required(self, base_kwargs):
        client = _client()
        user = SimpleNamespace(
            id=uuid4(),
            email="user@madfam.io",
            email_verified=True,
            created_at=None,
        )
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=client),
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
                AsyncMock(return_value=False),
            ),
            patch(
                "app.routers.v1.oauth_provider.settings",
                MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
            ),
        ):
            resp = await authorize_get(**base_kwargs)
        assert resp.status_code == 302
        assert "error=consent_required" in resp.headers["location"]

    async def test_session_and_consent_present_issues_code(self, base_kwargs):
        """Happy path — silent auth succeeds when both session + consent exist."""
        client = _client()
        user = SimpleNamespace(
            id=uuid4(),
            email="user@madfam.io",
            email_verified=True,
            created_at=None,
        )
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=client),
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
            patch(
                "app.routers.v1.oauth_provider._store_auth_code",
                AsyncMock(),
            ),
            patch(
                "app.routers.v1.oauth_provider.settings",
                MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
            ),
        ):
            base_kwargs["db"].commit = AsyncMock()
            resp = await authorize_get(**base_kwargs)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "code=" in loc
        assert "state=csrf-xyz" in loc
        # No `error` parameter when silent auth succeeds.
        assert "error=" not in loc

    async def test_default_path_unchanged_without_prompt_param(self, base_kwargs):
        """Sanity check: prompt=None must keep the existing interactive flow."""
        base_kwargs["prompt"] = None
        with (
            patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=_client()),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            base_kwargs["redis"].setex = AsyncMock(return_value=True)
            resp = await authorize_get(**base_kwargs)
        # Falls through to the login redirect, NOT an OAuth error redirect.
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "/api/v1/auth/login" in loc
        assert "error=login_required" not in loc
