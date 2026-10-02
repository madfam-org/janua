"""A client's `allowed_scopes` bounds every END-USER grant, not only client_credentials.

The client_credentials grant has always refused scopes outside the client's
`allowed_scopes` (`_parse_requested_scopes`). The authorization-code flow now
applies the same allowlist, narrowing per RFC 6749 §3.3:

* `/authorize` (GET and POST) drops unlisted scopes before anything is stored,
  and refuses with `error=invalid_scope` only when nothing requested is allowed;
* the code exchange re-narrows to the client's CURRENT grant (defence in depth);
* a refresh re-narrows too and never widens — the `scope` form parameter is not
  read for that grant;
* a client that requests only what it is registered for gets a byte-identical
  scope string, and client_credentials keeps rejecting instead of narrowing.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers.v1 import oauth_provider as op
from app.routers.v1.oauth_provider import (
    DATA_API_ROLE,
    DATA_API_SCOPE,
    _narrow_to_allowed_scopes,
    _parse_requested_scopes,
    _require_grantable_scope,
)

pytestmark = pytest.mark.asyncio

MOD = "app.routers.v1.oauth_provider"
REDIRECT = "https://app.example/cb"


def _client(
    *,
    allowed_scopes=None,
    name="some-vendor-app",
    is_confidential=True,
    organization_id=None,
):
    return SimpleNamespace(
        client_id="jnc_scope_test",
        name=name,
        is_active=True,
        is_confidential=is_confidential,
        allowed_scopes=allowed_scopes,
        grant_types=None,
        redirect_uris=[REDIRECT],
        audience=None,
        organization_id=organization_id,
        last_used_at=None,
        verify_secret=lambda secret: True,
    )


def _user():
    return SimpleNamespace(
        id=uuid4(),
        email="person@example.com",
        email_verified=True,
        created_at=None,
    )


def _query(resp) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(resp.headers["location"]).query).items()}


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


class TestNarrowToAllowedScopes:
    def test_allowed_request_is_returned_byte_identical(self):
        # Order and spelling preserved — no re-sorting of a compliant request.
        client = _client()  # no stored allowed_scopes → openid profile email
        assert _narrow_to_allowed_scopes("openid profile email", client) == (
            "openid profile email",
            [],
        )
        assert _narrow_to_allowed_scopes("email openid", client) == ("email openid", [])

    def test_unlisted_scopes_dropped_in_request_order(self):
        client = _client(allowed_scopes=["openid", "email", "fh:read"])
        granted, dropped = _narrow_to_allowed_scopes("fh:admin openid fh:read hcm:hr", client)
        assert granted == "openid fh:read"
        assert dropped == ["fh:admin", "hcm:hr"]

    def test_duplicates_removed_when_narrowing(self):
        client = _client(allowed_scopes=["openid"])
        assert _narrow_to_allowed_scopes("openid x:y openid", client) == ("openid", ["x:y"])

    def test_oidc_identity_scopes_always_grantable_on_user_grants(self):
        """A client whose stored list omits them still signs people in: the
        default list has no `offline_access`, and an operator-written list may
        hold only custom scopes."""
        assert _narrow_to_allowed_scopes("openid profile email offline_access", _client()) == (
            "openid profile email offline_access",
            [],
        )
        custom_only = _client(allowed_scopes=["madfam:silent_auth"])
        assert _narrow_to_allowed_scopes("openid email", custom_only) == ("openid email", [])

    def test_non_registrable_scopes_requested_by_clients_are_dropped_not_fatal(self):
        # e.g. `roles`, `organizations`, `groups`: not registrable on a client,
        # so they can only ever be narrowed away, never granted.
        granted, dropped = _narrow_to_allowed_scopes(
            "openid profile email roles organizations", _client()
        )
        assert granted == "openid profile email"
        assert dropped == ["organizations", "roles"]

    def test_empty_request_stays_empty(self):
        assert _narrow_to_allowed_scopes("", _client()) == ("", [])
        assert _narrow_to_allowed_scopes(None, _client()) == ("", [])

    def test_require_refuses_when_nothing_requested_is_allowed(self):
        with pytest.raises(ValueError, match="invalid_scope: admin, hcm:hr"):
            _require_grantable_scope("hcm:hr admin", _client(), grant="authorization_code")

    def test_require_keeps_partial_grant(self):
        assert (
            _require_grantable_scope("openid hcm:hr", _client(), grant="authorization_code")
            == "openid"
        )

    def test_client_credentials_still_rejects_instead_of_narrowing(self):
        """Byte-identical client_credentials behaviour: refuse, sorted output."""
        client = _client(allowed_scopes=["openid", "yantra4d:quote"])
        with pytest.raises(HTTPException) as exc:
            _parse_requested_scopes("openid admin", client)
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_scope: admin"
        assert _parse_requested_scopes("yantra4d:quote openid", client) == "openid yantra4d:quote"
        assert _parse_requested_scopes(None, client) == "openid yantra4d:quote"


# ---------------------------------------------------------------------------
# GET /authorize
# ---------------------------------------------------------------------------


def _authorize_get_kwargs(scope, *, prompt=None):
    return {
        "request": MagicMock(),
        "response_type": "code",
        "client_id": "jnc_scope_test",
        "redirect_uri": REDIRECT,
        "scope": scope,
        "state": "st",
        "nonce": None,
        "code_challenge": "abc",
        "code_challenge_method": "S256",
        "prompt": prompt,
        "login_method": None,
        "db": AsyncMock(),
        "redis": AsyncMock(),
    }


async def _run_authorize_get(client, scope, *, user=None, prompt=None, has_consent=True):
    kwargs = _authorize_get_kwargs(scope, prompt=prompt)
    store = AsyncMock()
    with (
        patch(f"{MOD}.get_user_from_cookie_or_header", AsyncMock(return_value=user)),
        patch(f"{MOD}._get_oauth_client", AsyncMock(return_value=client)),
        patch(f"{MOD}.ConsentService.has_consent", AsyncMock(return_value=has_consent)),
        patch(f"{MOD}._store_auth_code", store),
        patch(f"{MOD}.settings", MagicMock(REQUIRE_EMAIL_VERIFICATION=False)),
    ):
        resp = await op.authorize_get(**kwargs)
    return resp, store, kwargs


class TestAuthorizeGet:
    async def test_unlisted_scope_is_not_stored_in_the_code(self):
        resp, store, _ = await _run_authorize_get(
            _client(), "openid profile email fh:admin", user=_user()
        )
        assert resp.status_code == 302
        assert "code" in _query(resp)
        code_data = store.await_args.args[1]
        assert code_data["scope"] == "openid profile email"

    async def test_nothing_allowed_redirects_invalid_scope(self):
        resp, store, _ = await _run_authorize_get(_client(), "hcm:hr", user=_user())
        q = _query(resp)
        assert resp.status_code == 302
        assert q["error"] == "invalid_scope"
        assert q["state"] == "st"
        assert "code" not in q
        store.assert_not_awaited()

    async def test_narrowed_before_the_pre_login_request_is_stored(self):
        resp, _, kwargs = await _run_authorize_get(_client(), "openid crea-map:payment-mail")
        assert "/api/v1/auth/login" in resp.headers["location"]
        stored = json.loads(kwargs["redis"].setex.await_args.args[2])
        assert stored["scope"] == "openid"

    async def test_consent_is_checked_against_the_narrowed_scope(self):
        client = _client()
        kwargs = _authorize_get_kwargs("openid email fh:write")
        has_consent = AsyncMock(return_value=True)
        with (
            patch(f"{MOD}.get_user_from_cookie_or_header", AsyncMock(return_value=_user())),
            patch(f"{MOD}._get_oauth_client", AsyncMock(return_value=client)),
            patch(f"{MOD}.ConsentService.has_consent", has_consent),
            patch(f"{MOD}._store_auth_code", AsyncMock()),
            patch(f"{MOD}.settings", MagicMock(REQUIRE_EMAIL_VERIFICATION=False)),
        ):
            await op.authorize_get(**kwargs)
        assert has_consent.await_args.args[3] == {"openid", "email"}

    async def test_default_client_request_unchanged(self):
        resp, store, _ = await _run_authorize_get(_client(), "openid profile email", user=_user())
        assert store.await_args.args[1]["scope"] == "openid profile email"
        assert "error" not in _query(resp)

    async def test_listed_custom_scope_is_kept(self):
        client = _client(allowed_scopes=["openid", "profile", "email", "fh:read", "fh:write"])
        _, store, _ = await _run_authorize_get(
            client, "openid profile email fh:read fh:write", user=_user()
        )
        assert store.await_args.args[1]["scope"] == "openid profile email fh:read fh:write"

    async def test_data_api_scope_kept_only_for_a_client_that_lists_it(self):
        opted_in = _client(allowed_scopes=["openid", DATA_API_SCOPE])
        _, store, _ = await _run_authorize_get(opted_in, f"openid {DATA_API_SCOPE}", user=_user())
        assert store.await_args.args[1]["scope"] == f"openid {DATA_API_SCOPE}"

        _, store, _ = await _run_authorize_get(_client(), f"openid {DATA_API_SCOPE}", user=_user())
        assert store.await_args.args[1]["scope"] == "openid"

    async def test_silent_auth_client_unchanged(self):
        """A tenant client trusted via `madfam:silent_auth` keeps issuing codes
        silently for the scopes it lists."""
        client = _client(
            name="MAP · Crea Tu Mundo",
            allowed_scopes=["openid", "profile", "email", "madfam:silent_auth"],
        )
        resp, store, _ = await _run_authorize_get(
            client, "openid profile email", user=_user(), prompt="none", has_consent=False
        )
        q = _query(resp)
        assert "error" not in q
        assert "code" in q
        assert store.await_args.args[1]["scope"] == "openid profile email"

    async def test_silent_auth_with_unlisted_scope_is_narrowed_not_errored(self):
        client = _client(
            name="MAP · Crea Tu Mundo", allowed_scopes=["openid", "madfam:silent_auth"]
        )
        resp, store, _ = await _run_authorize_get(
            client, "openid hcm:hr", user=_user(), prompt="none", has_consent=False
        )
        assert "code" in _query(resp)
        assert store.await_args.args[1]["scope"] == "openid"


# ---------------------------------------------------------------------------
# POST /authorize
# ---------------------------------------------------------------------------


async def _run_authorize_post(client, scope):
    store = AsyncMock()
    db = AsyncMock()
    with (
        patch(f"{MOD}._validate_csrf_token", AsyncMock(return_value=True)),
        patch(f"{MOD}._get_oauth_client", AsyncMock(return_value=client)),
        patch(f"{MOD}._store_auth_code", store),
        patch(f"{MOD}.settings", MagicMock(REQUIRE_EMAIL_VERIFICATION=False)),
    ):
        resp = await op.authorize_post(
            request=MagicMock(),
            response_type="code",
            client_id="jnc_scope_test",
            redirect_uri=REDIRECT,
            scope=scope,
            state="st",
            nonce=None,
            code_challenge="abc",
            code_challenge_method="S256",
            csrf_token="csrf",
            db=db,
            redis=AsyncMock(),
            current_user=_user(),
        )
    return resp, store


class TestAuthorizePost:
    async def test_unlisted_scope_is_not_stored_in_the_code(self):
        resp, store = await _run_authorize_post(_client(), "openid email admin")
        assert "code" in _query(resp)
        assert store.await_args.args[1]["scope"] == "openid email"

    async def test_nothing_allowed_redirects_invalid_scope(self):
        resp, store = await _run_authorize_post(_client(), "admin")
        q = _query(resp)
        assert q["error"] == "invalid_scope"
        assert q["state"] == "st"
        store.assert_not_awaited()

    async def test_default_client_request_unchanged(self):
        _, store = await _run_authorize_post(_client(), "openid profile email")
        assert store.await_args.args[1]["scope"] == "openid profile email"


# ---------------------------------------------------------------------------
# Token endpoint: code exchange and refresh
# ---------------------------------------------------------------------------


def _token_patches(user, *, verify_payload=None):
    """Patch the claim sources so only scope handling is under test."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    patches = [
        patch(
            f"{MOD}._get_user_entitlements",
            AsyncMock(
                return_value={
                    "tier": "community",
                    "roles": [],
                    "sub_status": "inactive",
                    "is_admin": False,
                }
            ),
        ),
        patch(f"{MOD}.get_user_entitlements", AsyncMock(return_value=[])),
        patch(f"{MOD}.entitlements_to_claim", MagicMock(return_value=[])),
        patch(f"{MOD}._get_user_org_claims", AsyncMock(return_value={})),
        patch(f"{MOD}.service_principal_claims", MagicMock(return_value={})),
        patch(f"{MOD}._generate_id_token", MagicMock(return_value="id-token")),
        patch.object(
            op.jwt_manager, "create_access_token", MagicMock(return_value=("at", "j", None))
        ),
        patch.object(
            op.jwt_manager, "create_refresh_token", MagicMock(return_value=("rt", "j", "f", None))
        ),
    ]
    if verify_payload is not None:
        patches.append(patch(f"{MOD}._verify_oauth_token", AsyncMock(return_value=verify_payload)))
    return db, patches


async def _exchange(client, code_scope):
    user = _user()
    code_data = {
        "client_id": client.client_id,
        "user_id": str(user.id),
        "redirect_uri": REDIRECT,
        "scope": code_scope,
        "nonce": None,
        "code_challenge": None,
    }
    db, patches = _token_patches(user)
    with (
        patch(f"{MOD}._get_auth_code", AsyncMock(return_value=code_data)),
        patch(f"{MOD}._delete_auth_code", AsyncMock()),
    ):
        for p in patches:
            p.start()
        try:
            resp = await op._handle_authorization_code_grant(
                code="c",
                redirect_uri=REDIRECT,
                client=client,
                code_verifier=None,
                db=db,
                redis=AsyncMock(),
            )
            claims = op.jwt_manager.create_access_token.call_args.kwargs["additional_claims"]
        finally:
            for p in reversed(patches):
                p.stop()
    return resp, claims


class TestCodeExchange:
    async def test_default_client_token_unchanged(self):
        resp, claims = await _exchange(_client(), "openid profile email")
        assert resp.scope == claims["scope"] == "openid profile email"
        assert resp.id_token == "id-token"

    async def test_scope_removed_from_client_after_authorize_is_not_issued(self):
        """The code was minted while `fh:write` was allowed; it was revoked
        before the exchange."""
        client = _client(allowed_scopes=["openid", "profile", "email", "fh:read"])
        resp, claims = await _exchange(client, "openid fh:read fh:write")
        assert resp.scope == claims["scope"] == "openid fh:read"

    async def test_code_with_nothing_still_allowed_is_refused(self):
        client = _client(allowed_scopes=["openid"])
        with pytest.raises(HTTPException) as exc:
            await _exchange(client, "fh:write")
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_scope: fh:write"

    async def test_data_api_claims_only_when_client_lists_the_scope(self):
        _, claims = await _exchange(_client(), f"openid {DATA_API_SCOPE}")
        assert claims["scope"] == "openid"
        assert "role" not in claims

        opted_in = _client(allowed_scopes=["openid", DATA_API_SCOPE])
        _, claims = await _exchange(opted_in, f"openid {DATA_API_SCOPE}")
        assert claims["scope"] == f"openid {DATA_API_SCOPE}"
        assert claims["role"] == DATA_API_ROLE


async def _token_refresh(client, refresh_payload, *, requested_scope=None):
    user = _user()
    payload = {"sub": str(user.id), "client_id": client.client_id, **refresh_payload}
    db, patches = _token_patches(user, verify_payload=payload)
    request = MagicMock()
    request.headers = {}
    with patch(f"{MOD}._get_oauth_client", AsyncMock(return_value=client)):
        for p in patches:
            p.start()
        try:
            resp = await op.token(
                request=request,
                grant_type="refresh_token",
                code=None,
                redirect_uri=None,
                client_id=client.client_id,
                client_secret="secret",
                refresh_token="rt-in",
                code_verifier=None,
                scope=requested_scope,
                db=db,
                redis=AsyncMock(),
            )
            claims = op.jwt_manager.create_access_token.call_args.kwargs["additional_claims"]
            rotated = op.jwt_manager.create_refresh_token.call_args.kwargs["additional_claims"]
        finally:
            for p in reversed(patches):
                p.stop()
    return resp, claims, rotated


class TestRefreshGrant:
    async def test_requested_scope_cannot_widen_a_refresh(self):
        client = _client(allowed_scopes=["openid", "profile", "email", "fh:read", "fh:write"])
        resp, claims, rotated = await _token_refresh(
            client, {"scope": "openid fh:read"}, requested_scope="openid fh:read fh:write admin"
        )
        assert resp.scope == claims["scope"] == rotated["scope"] == "openid fh:read"

    async def test_refresh_drops_scope_removed_from_client(self):
        client = _client(allowed_scopes=["openid", "fh:read"])
        resp, claims, rotated = await _token_refresh(client, {"scope": "openid fh:read fh:write"})
        assert resp.scope == claims["scope"] == rotated["scope"] == "openid fh:read"

    async def test_refresh_token_without_scope_still_defaults_to_openid(self):
        resp, claims, _ = await _token_refresh(_client(), {})
        assert resp.scope == claims["scope"] == "openid"

    async def test_refresh_with_nothing_still_allowed_is_refused(self):
        client = _client(allowed_scopes=["openid"])
        with pytest.raises(HTTPException) as exc:
            await _token_refresh(client, {"scope": "fh:write"})
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_scope: fh:write"
