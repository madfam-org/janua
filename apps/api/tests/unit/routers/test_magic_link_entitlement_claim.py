"""Magic-link session tokens carry the MADFAM ecosystem entitlement claim.

Until this change janua stamped `madfam_entitled_products` ONLY in the OIDC
flows (auth-code + refresh in oauth_provider.py). A portal magic-link
assertion — minted through AuthService.create_session — carried no entitlement
claim, forcing downstream consumers (the nauta ERP hub) into a per-render
/me/entitlements round-trip.

These tests pin that:
  * create_access_token now accepts and merges `additional_claims`, without
    letting them spoof the reserved sub/tid/jti/exp/iss/aud claims;
  * create_session and refresh_tokens BOTH compute the claim through the same
    SSOT the OIDC path uses (`entitlements_to_claim(get_user_entitlements(...))`)
    — no re-implementation — and thread it into the mint;
  * a user with no entitlements gets the same shape the OIDC path produces:
    the claim is present as an empty list (never absent, never a spoof);
  * the claim reflects org-inherited + per-user precedence via the shared
    resolver;
  * the resulting JWT decodes with the claim in it.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.models import EntitlementSource, UserStatus
from app.services.auth_service import AuthService
from app.services.entitlements_service import Entitlement, entitlements_to_claim


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


# ---------------------------------------------------------------------------
# create_access_token: the additional_claims seam
# ---------------------------------------------------------------------------


def test_access_token_carries_additional_entitlement_claim():
    token, _jti, _exp = AuthService.create_access_token(
        user_id="u-1",
        tenant_id="t-1",
        email="a@b.test",
        additional_claims={"madfam_entitled_products": ["kalya:pro", "crea-map:pro"]},
    )
    claims = _decode(token)
    assert claims["madfam_entitled_products"] == ["kalya:pro", "crea-map:pro"]


def test_access_token_without_additional_claims_has_no_entitlement_key():
    """A caller that passes nothing gets the exact legacy payload shape — the
    claim key is simply absent, so existing non-magic-link callers that never
    supply it are unchanged."""
    token, _jti, _exp = AuthService.create_access_token(
        user_id="u-1", tenant_id="t-1", email="a@b.test"
    )
    assert "madfam_entitled_products" not in _decode(token)


def test_additional_claims_cannot_spoof_reserved_claims():
    """Reserved identity/security claims always win over additional_claims —
    a hostile or buggy dict cannot rewrite sub/tid/jti/iss/type/aud."""
    token, jti, _exp = AuthService.create_access_token(
        user_id="real-user",
        tenant_id="real-tenant",
        email="a@b.test",
        audience="real-aud",
        additional_claims={
            "sub": "attacker",
            "tid": "attacker-tenant",
            "jti": "attacker-jti",
            "iss": "evil",
            "type": "refresh",
            "aud": "evil-aud",
            "madfam_entitled_products": ["kalya:pro"],
        },
    )
    claims = _decode(token)
    assert claims["sub"] == "real-user"
    assert claims["tid"] == "real-tenant"
    assert claims["jti"] == jti != "attacker-jti"
    assert claims["iss"] != "evil"
    assert claims["type"] == "access"
    assert claims["aud"] == "real-aud"
    # The one non-reserved claim rides through untouched.
    assert claims["madfam_entitled_products"] == ["kalya:pro"]


# ---------------------------------------------------------------------------
# create_session: computes the claim via the SSOT and threads it in
# ---------------------------------------------------------------------------


def _user():
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        tenant_id=uuid4(),
        is_admin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_create_session_stamps_entitlement_claim_from_ssot():
    """Drive create_session with the entitlement resolver and the redis/session
    store side-effects stubbed, and assert the minted access token carries the
    claim the SSOT produced."""
    user = _user()
    resolved = [
        Entitlement("crea-map", "pro", None, EntitlementSource.INHERITED),
        Entitlement("kalya", "pro", None, EntitlementSource.DHANAM_SUBSCRIPTION),
    ]

    db = AsyncMock()
    # enforce_session_limit path issues one execute() returning zero sessions.
    exec_result = MagicMock()
    exec_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    session_store = AsyncMock()

    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=resolved),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=session_store),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=db, user=user, enforce_session_limit=False
        )

    claims = _decode(access_token)
    # Byte-identical to what the OIDC path would stamp for the same resolution.
    assert claims["madfam_entitled_products"] == entitlements_to_claim(resolved)
    assert claims["madfam_entitled_products"] == ["crea-map:pro", "kalya:pro"]


@pytest.mark.asyncio
async def test_create_session_no_entitlements_stamps_empty_list():
    """A user with no entitlements gets the claim present as an empty list —
    the exact shape the unconditional OIDC path produces (present, not absent)."""
    user = _user()

    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=db, user=user, enforce_session_limit=False
        )

    claims = _decode(access_token)
    assert claims["madfam_entitled_products"] == []


@pytest.mark.asyncio
async def test_create_session_survives_entitlement_resolution_failure():
    """Entitlement resolution must never block session issuance — a resolver
    blow-up degrades to an empty claim, not a failed login."""
    user = _user()

    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=db, user=user, enforce_session_limit=False
        )

    assert _decode(access_token)["madfam_entitled_products"] == []


@pytest.mark.asyncio
async def test_create_session_token_size_sane_with_many_entitlements():
    """A user with many entitlements still mints a token of reasonable size —
    guards against an accidental claim blow-up (JWT header limits ~8KB)."""
    user = _user()
    resolved = [
        Entitlement(f"product{i:02d}", "pro", None, EntitlementSource.INHERITED) for i in range(40)
    ]

    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=resolved),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=db, user=user, enforce_session_limit=False
        )

    claims = _decode(access_token)
    assert len(claims["madfam_entitled_products"]) == 40
    # Sanity: well under any reasonable header/cookie budget.
    assert len(access_token) < 4096


# ---------------------------------------------------------------------------
# refresh_tokens: magic-link sessions refresh through here, not OIDC refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_tokens_restamps_entitlement_claim():
    """Magic-link/session tokens refresh through AuthService.refresh_tokens (not
    the OIDC refresh grant). The refreshed access token must re-carry the claim,
    picking up any grant/revoke since the session was minted."""
    user = _user()
    resolved = [Entitlement("kalya", "pro", None, EntitlementSource.DHANAM_SUBSCRIPTION)]

    session = SimpleNamespace(
        id=uuid4(),
        access_token_jti=None,
        refresh_token_jti="old-refresh-jti",
        user_id=user.id,
        revoked=False,
        revoked_at=None,
        is_active=True,
        last_activity_at=None,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )

    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=session)
    db.execute = AsyncMock(return_value=exec_result)
    db.get = AsyncMock(return_value=user)
    db.commit = AsyncMock()

    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True

    with (
        patch.object(
            AuthService,
            "verify_token",
            AsyncMock(return_value={"jti": "old-refresh-jti", "sub": str(user.id), "family": "f1", "type": "refresh", "exp": (datetime.utcnow() + timedelta(days=7)).timestamp()}),
        ),
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=resolved),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=redis)),
    ):
        result = await AuthService.refresh_tokens(db, "old-refresh-token")

    assert result is not None
    access_token, _new_refresh = result
    claims = _decode(access_token)
    assert claims["madfam_entitled_products"] == ["kalya:pro"]


# ---------------------------------------------------------------------------
# SSOT-reuse source pins: no divergent re-implementation of the claim
# ---------------------------------------------------------------------------


def test_session_mint_paths_reuse_the_shared_entitlement_ssot():
    """Both session-minting seams must compute the claim through the shared
    entitlements_service helpers — never a local re-implementation, the exact
    anti-pattern the ecosystem avoids."""
    for fn in (AuthService.create_session, AuthService.refresh_tokens):
        source = inspect.getsource(fn)
        assert "get_user_entitlements" in source, fn.__name__
        assert "entitlements_to_claim" in source, fn.__name__
        assert "madfam_entitled_products" in source, fn.__name__
