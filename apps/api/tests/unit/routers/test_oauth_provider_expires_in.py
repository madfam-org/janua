"""`expires_in` says when the access token really expires (RFC 6749 §5.1).

The code exchange and the refresh grant answered a literal `expires_in=3600`
while the token they minted carried `exp = iat + JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
(480 minutes by default). A client that trusts the advertised value, as the
Enclii CLI does, stopped using a token with seven valid hours left; whenever
its refresh was refused, the person had to sign in again after one hour.

These tests mint REAL tokens (only the claim sources are patched) and compare
the answer with the token's own `exp`, so the two cannot drift apart again.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.routers.v1 import oauth_provider as op
from app.routers.v1 import oauth_provider_grants as grants
from app.routers.v1 import oauth_provider_shared

pytestmark = pytest.mark.asyncio

REDIRECT = "https://app.example/cb"


@pytest.fixture(autouse=True)
def policy_free_session(monkeypatch):
    # Session binding and MFA proof have their own tests; here only the
    # advertised lifetime is under test.
    monkeypatch.setattr(oauth_provider_shared, "user_requires_mfa", AsyncMock(return_value=False))


def _client():
    return SimpleNamespace(
        client_id="jnc_expires_in_test",
        name="some-cli",
        is_active=True,
        is_confidential=False,
        allowed_scopes=None,
        grant_types=None,
        redirect_uris=[REDIRECT],
        audience=None,
        organization_id=None,
        last_used_at=None,
    )


def _user():
    return SimpleNamespace(
        id=uuid4(), email="person@example.com", email_verified=True, created_at=None
    )


def _claim_source_patches(user, *, verify_payload=None):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    shared = "app.routers.v1.oauth_provider_shared."
    own = "app.routers.v1.oauth_provider_grants."
    patches = [
        patch(
            shared + "_get_user_entitlements",
            AsyncMock(
                return_value={
                    "tier": "community",
                    "roles": [],
                    "sub_status": "inactive",
                    "is_admin": False,
                }
            ),
        ),
        patch(own + "get_user_entitlements", AsyncMock(return_value=[])),
        patch(own + "entitlements_to_claim", MagicMock(return_value=[])),
        patch(own + "get_product_tier_claims", AsyncMock(return_value={})),
        patch(own + "_require_invited_access", AsyncMock()),
        patch(own + "service_principal_claims", MagicMock(return_value={})),
        patch(own + "spanish_formality_claims", MagicMock(return_value={})),
        patch(shared + "_get_user_org_claims", AsyncMock(return_value={})),
        patch(shared + "_generate_id_token", MagicMock(return_value="id-token")),
        patch("app.auth.tenant_login_context.require_client_membership", AsyncMock()),
        patch.object(grants.token_revocation, "is_revoked", AsyncMock(return_value=False)),
    ]
    if verify_payload is not None:
        patches.append(
            patch(shared + "_verify_oauth_token", AsyncMock(return_value=verify_payload))
        )
    return db, patches


def _assert_matches_exp(resp, minutes):
    claims = op.jwt_manager.get_unverified_claims(resp.access_token)
    lifetime = claims["exp"] - claims["iat"]
    assert lifetime == minutes * 60
    # Seconds left when the answer is built: the lifetime, less the moment the
    # handler spent after minting. What the client computes (`now + expires_in`)
    # lands on the token's `exp`.
    assert lifetime - 2 <= resp.expires_in <= lifetime
    assert abs((time.time() + resp.expires_in) - claims["exp"]) <= 2


async def _exchange():
    user = _user()
    code_data = {
        "client_id": "jnc_expires_in_test",
        "user_id": str(user.id),
        "redirect_uri": REDIRECT,
        "scope": "openid profile email offline_access",
        "nonce": None,
        "code_challenge": None,
    }
    db, patches = _claim_source_patches(user)
    patches += [
        patch(
            "app.routers.v1.oauth_provider_shared._get_auth_code", AsyncMock(return_value=code_data)
        ),
        patch(
            "app.routers.v1.oauth_provider_shared._delete_auth_code", AsyncMock(return_value=True)
        ),
    ]
    for p in patches:
        p.start()
    try:
        client = _client()
        client.is_confidential = True  # PKCE has its own tests
        return await op._handle_authorization_code_grant(
            code="c",
            redirect_uri=REDIRECT,
            client=client,
            code_verifier=None,
            db=db,
            redis=AsyncMock(),
        )
    finally:
        for p in reversed(patches):
            p.stop()


async def _refresh():
    user = _user()
    payload = {
        "sub": str(user.id),
        "client_id": "jnc_expires_in_test",
        "scope": "openid profile email offline_access",
        "family": "fam",
        "jti": "old",
    }
    db, patches = _claim_source_patches(user, verify_payload=payload)
    for p in patches:
        p.start()
    try:
        return await op._handle_refresh_token_grant(
            refresh_token="rt-in", client=_client(), db=db, redis=AsyncMock()
        )
    finally:
        for p in reversed(patches):
            p.stop()


class TestAdvertisedLifetimeMatchesTheToken:
    async def test_code_exchange(self):
        resp = await _exchange()
        _assert_matches_exp(resp, op.jwt_manager.access_token_expire_minutes)

    async def test_refresh(self):
        resp = await _refresh()
        _assert_matches_exp(resp, op.jwt_manager.access_token_expire_minutes)

    async def test_default_lifetime_is_not_the_old_literal(self):
        """Guards the regression itself: 480 minutes must not be announced as 3600 s."""
        assert op.jwt_manager.access_token_expire_minutes * 60 != 3600
        assert (await _refresh()).expires_in != 3600
        assert (await _exchange()).expires_in != 3600

    @pytest.mark.parametrize("minutes", [15, 60, 480])
    async def test_follows_a_changed_lifetime(self, monkeypatch, minutes):
        monkeypatch.setattr(op.jwt_manager, "access_token_expire_minutes", minutes)
        _assert_matches_exp(await _exchange(), minutes)
        _assert_matches_exp(await _refresh(), minutes)


class TestHelper:
    def test_without_an_expiry_falls_back_to_the_configured_lifetime(self):
        assert (
            grants._access_token_expires_in(None) == op.jwt_manager.access_token_expire_minutes * 60
        )
