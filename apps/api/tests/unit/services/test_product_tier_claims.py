"""`{product}_tier` claims on human tokens carry user-scoped grants (G1-1).

Products authorize on `{product}_tier` — Tezca reads `tezca_tier`
(apps/api/middleware/combined_auth.py), Yantra4D `yantra4d_tier`
(apps/api/services/core/tier_service.py), Karafiel `karafiel_tier`
(apps/api/core/authentication.py) — not on `madfam_entitled_products`. Dhanam's
hosted checkout grants a product to the buyer's Janua USER when the buyer has
no organization (owner ruling G1-1, 2026-10-14). These tests pin that the
grant reaches the claim, how it competes with an org tier, and that a
cancelled grant leaves it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.services import entitlements_service
from app.services.auth_service import AuthService
from app.services.entitlements_service import get_product_tier_claims
from app.sso.application.services.product_tiers import (
    PRODUCT_TIER_ORDERS,
    merge_product_tiers,
    pick_product_tier,
    product_tier_claims,
    resolve_product_tiers,
)

NOW = datetime(2026, 10, 14, 12, 0, 0)
KARAFIEL_LADDER = {"karafiel": ("contador", "consultor", "despacho", "firma")}


def _row(product: str, tier: str, expires_at=None):
    return SimpleNamespace(product=product, tier=tier, expires_at=expires_at)


def _user():
    return SimpleNamespace(id=uuid4(), email="buyer@example.com", tenant_id=uuid4(), is_admin=False)


# ---------------------------------------------------------------------------
# Precedence (pure)
# ---------------------------------------------------------------------------


class TestPickProductTier:
    def test_janua_ships_no_tier_ladder(self):
        assert dict(PRODUCT_TIER_ORDERS) == {}

    @pytest.mark.parametrize(
        "org, user, expected",
        [
            (None, "contador", "contador"),  # user-only grant
            ("despacho", None, "despacho"),  # org-only
            (None, None, None),
            ("contador", "firma", "contador"),  # both, no ladder → org wins
            ("firma", "contador", "firma"),
        ],
    )
    def test_without_a_ladder(self, org, user, expected):
        assert pick_product_tier("karafiel", org, user) == expected

    @pytest.mark.parametrize(
        "org, user, expected",
        [
            ("contador", "firma", "firma"),  # user grant higher → user
            ("firma", "contador", "firma"),  # org higher → org
            ("despacho", "despacho", "despacho"),
            ("contador", "platinum", "contador"),  # off-ladder tier → org
            ("legacy", "firma", "legacy"),
        ],
    )
    def test_with_the_products_ladder_the_higher_tier_wins(self, org, user, expected):
        assert pick_product_tier("karafiel", org, user, KARAFIEL_LADDER) == expected

    def test_merge_covers_every_product_either_source_names(self):
        merged = merge_product_tiers(
            {"tezca": "pro", "karafiel": "contador"},
            {"karafiel": "firma", "yantra4d": "pro"},
            KARAFIEL_LADDER,
        )
        assert merged == {"karafiel": "firma", "tezca": "pro", "yantra4d": "pro"}

    def test_claim_keys_are_claim_safe(self):
        assert product_tier_claims({"pravara-mes": "growth", "tezca": "pro", "empty": ""}) == {
            "pravara_mes_tier": "growth",
            "tezca_tier": "pro",
        }

    def test_sso_orchestrator_claims_include_user_grants(self):
        claims = resolve_product_tiers(None, None, {"yantra4d": "pro"})
        assert claims == {"foundry_tier": "community", "yantra4d_tier": "pro"}
        # No grants: exactly the previous output.
        assert resolve_product_tiers({"tezca": "pro"}, "pro") == {
            "foundry_tier": "sovereign",
            "tezca_tier": "pro",
        }


# ---------------------------------------------------------------------------
# get_product_tier_claims (DB reads stubbed)
# ---------------------------------------------------------------------------


async def _claims(rows, org_tiers=None, org_id="org-1"):
    db = AsyncMock()
    with (
        patch.object(entitlements_service, "_fetch_user_rows", AsyncMock(return_value=rows)),
        patch.object(
            entitlements_service,
            "_fetch_org_product_tiers",
            AsyncMock(return_value=org_tiers or {}),
        ) as org_read,
    ):
        claims = await get_product_tier_claims(_user(), db, org_id=org_id, now=NOW)
    return claims, org_read


@pytest.mark.asyncio
class TestGetProductTierClaims:
    async def test_user_only_grant_puts_the_claim_on_the_token(self):
        claims, _ = await _claims([_row("karafiel", "contador")], org_id=None)
        assert claims == {"karafiel_tier": "contador"}

    async def test_org_and_user_grant_resolve_by_precedence(self):
        claims, _ = await _claims(
            [_row("karafiel", "firma"), _row("yantra4d", "pro")],
            org_tiers={"karafiel": "contador", "tezca": "pro"},
        )
        # No ladder in Janua: the org tier wins where both exist.
        assert claims == {
            "karafiel_tier": "contador",
            "tezca_tier": "pro",
            "yantra4d_tier": "pro",
        }

    async def test_org_and_user_grant_with_a_ladder_take_the_higher(self):
        with patch.dict(
            "app.sso.application.services.product_tiers.PRODUCT_TIER_ORDERS", KARAFIEL_LADDER
        ):
            claims, _ = await _claims(
                [_row("karafiel", "firma")], org_tiers={"karafiel": "contador"}
            )
        assert claims == {"karafiel_tier": "firma"}

    async def test_cancelled_or_expired_grant_drops_out(self):
        claims, _ = await _claims(
            [
                _row("karafiel", "contador", expires_at=NOW),  # cancelled now
                _row("yantra4d", "pro", expires_at=NOW - timedelta(days=1)),
                _row("tezca", "pro", expires_at=NOW + timedelta(days=30)),  # still paid
            ],
            org_id=None,
        )
        assert claims == {"tezca_tier": "pro"}

    async def test_cancelled_grant_falls_back_to_the_org_tier(self):
        claims, _ = await _claims(
            [_row("karafiel", "firma", expires_at=NOW)], org_tiers={"karafiel": "contador"}
        )
        assert claims == {"karafiel_tier": "contador"}

    async def test_no_grant_and_no_org_tier_changes_nothing(self):
        claims, _ = await _claims([], org_id=None)
        assert claims == {}

    async def test_ambiguous_org_reads_no_org_tiers(self):
        claims, org_read = await _claims([], org_tiers={"karafiel": "firma"}, org_id=None)
        assert claims == {}
        org_read.assert_not_awaited()

    async def test_read_failures_never_raise(self):
        db = AsyncMock()
        with (
            patch.object(
                entitlements_service, "_fetch_user_rows", AsyncMock(side_effect=RuntimeError("x"))
            ),
            patch.object(
                entitlements_service,
                "_fetch_org_product_tiers",
                AsyncMock(side_effect=RuntimeError("y")),
            ),
        ):
            assert await get_product_tier_claims(_user(), db, org_id="org-1", now=NOW) == {}
        assert db.rollback.await_count == 2


# ---------------------------------------------------------------------------
# A minted session token carries it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_token_carries_the_user_grant_tier_claim():
    user = _user()
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()

    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements", AsyncMock(return_value=[])
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value={}),
        ),
        patch.object(
            entitlements_service,
            "_fetch_user_rows",
            AsyncMock(return_value=[_row("karafiel", "contador")]),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=db, user=user, enforce_session_limit=False
        )

    claims = pyjwt.decode(
        access_token, options={"verify_signature": False}, algorithms=["HS256", "RS256"]
    )
    assert claims["karafiel_tier"] == "contador"
    assert claims["madfam_entitled_products"] == []  # unchanged pipeline
    assert claims["sub"] == str(user.id)
