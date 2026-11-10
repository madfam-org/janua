"""
The legacy single `Organization.subscription_tier` written by the Dhanam webhook.

Before this fix the webhook derived the summary by ranking only the slugs
`essentials` / `pro` / `madfam`. Dhanam writes each product's catalog tier
slug verbatim (`karafiel_contador`, `selva_team`, `tezca_academic`, …), so a
buyer of almost any catalog tier was summarised as `community`, the unbilled
value, while `madfam_entitled_products` and `{product}_tier` were right.

Pins:
- every sellable tier of the priority products summarises as `pro`;
- free tier slugs summarise as `community`;
- an unknown tier slug is never `community` and never above `pro`;
- the operator-only `madfam` tier still summarises as `enterprise`;
- the webhook writes that summary (created, updated, canceled);
- `foundry_tier` (Enclii) no longer falls back to the summary once an
  organization has per-product tiers, so a non-Enclii purchase never reads as
  an Enclii plan.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.routers.v1 import webhooks_dhanam
from app.routers.v1.webhooks_dhanam import dhanam_subscription_webhook
from app.sso.application.services.product_tiers import (
    legacy_subscription_tier,
    resolve_product_tiers,
)

SECRET = "test-dhanam-webhook-secret"
MODULE = "app.routers.v1.webhooks_dhanam"

# Tier slugs of the priority products as Dhanam's public catalog publishes
# them (GET /v1/billing/catalog, 2026-11-09). Each is what the webhook stores
# in `product_tiers` for a buyer of that tier.
PAID_CATALOG_TIERS = [
    ("dhanam", "essentials"),
    ("dhanam", "pro"),
    ("dhanam", "premium"),
    ("karafiel", "contador"),
    ("karafiel", "consultor"),
    ("karafiel", "despacho"),
    ("karafiel", "firma"),
    ("selva", "developer"),
    ("selva", "team"),
    ("selva", "business"),
    ("janua", "pro"),
    ("enclii", "pro"),
    ("symbiosis-hcm", "pilot"),
    ("symbiosis-hcm", "tenant"),
    ("symbiosis-hcm", "enterprise"),
    ("tezca", "essentials"),
    ("tezca", "academic"),
    ("tezca", "institutional"),
    ("tezca", "pro"),
    ("tezca", "pro_plus"),
    ("cotiza", "creator_pro"),
    ("pravara-mes", "growth"),
]


class TestLegacySubscriptionTier:
    @pytest.mark.parametrize("product, tier", PAID_CATALOG_TIERS)
    def test_every_paid_catalog_tier_summarises_as_pro(self, product, tier):
        assert legacy_subscription_tier({product: tier}) == "pro"

    @pytest.mark.parametrize(
        "tier", ["free", "community", "trial", "open_source", "incluida", "incluido", "", None]
    )
    def test_free_tier_slugs_summarise_as_community(self, tier):
        assert legacy_subscription_tier({"janua": tier}) == "community"

    @pytest.mark.parametrize("tiers", [None, {}])
    def test_no_product_tiers_is_community(self, tiers):
        assert legacy_subscription_tier(tiers) == "community"

    def test_unknown_paid_slug_is_pro_never_community_never_higher(self):
        assert legacy_subscription_tier({"newservice": "platinum"}) == "pro"

    @pytest.mark.parametrize("tier", ["premium", "firma", "enterprise", "institutional"])
    def test_top_catalog_tier_is_never_summarised_above_pro(self, tier):
        # `enterprise` is the operator-only (`madfam`) summary, not a top tier.
        assert legacy_subscription_tier({"karafiel": tier}) == "pro"

    def test_madfam_tier_is_enterprise_unchanged(self):
        assert legacy_subscription_tier({"yantra4d": "madfam"}) == "enterprise"
        assert (
            legacy_subscription_tier({"karafiel": "contador", "enclii": "madfam"}) == "enterprise"
        )

    def test_case_and_whitespace_do_not_change_the_summary(self):
        assert legacy_subscription_tier({"enclii": " MADFAM "}) == "enterprise"
        assert legacy_subscription_tier({"janua": "Open_Source"}) == "community"

    def test_one_paid_product_among_free_ones_is_pro(self):
        assert legacy_subscription_tier({"janua": "open_source", "karafiel": "contador"}) == "pro"


class TestFoundryTierFallback:
    """`foundry_tier` reads the legacy field only for orgs without per-product tiers."""

    def test_non_enclii_purchase_does_not_read_as_an_enclii_plan(self):
        claims = resolve_product_tiers({"karafiel": "contador"}, "pro")
        assert claims["foundry_tier"] == "community"
        assert claims["karafiel_tier"] == "contador"

    def test_madfam_on_another_product_does_not_read_as_enclii_ecosystem(self):
        claims = resolve_product_tiers({"yantra4d": "madfam"}, "enterprise")
        assert claims["foundry_tier"] == "community"

    def test_enclii_tier_still_wins(self):
        claims = resolve_product_tiers({"enclii": "pro", "karafiel": "firma"}, "pro")
        assert claims["foundry_tier"] == "sovereign"

    @pytest.mark.parametrize("product_tiers", [None, {}])
    def test_org_without_product_tiers_keeps_the_legacy_fallback(self, product_tiers):
        assert resolve_product_tiers(product_tiers, "pro")["foundry_tier"] == "sovereign"
        assert resolve_product_tiers(product_tiers, "enterprise")["foundry_tier"] == "ecosystem"

    def test_user_grant_does_not_remove_the_org_legacy_fallback(self):
        claims = resolve_product_tiers({}, "pro", {"karafiel": "contador"})
        assert claims["foundry_tier"] == "sovereign"
        assert claims["karafiel_tier"] == "contador"


# ----------------------------------------------------------------- webhook


class _FakeRequest:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    async def body(self) -> bytes:
        return self._body

    async def json(self) -> dict:
        return json.loads(self._body)


async def _call(payload: dict):
    request = _FakeRequest(payload)
    signature = hmac.new(SECRET.encode(), request._body, hashlib.sha256).hexdigest()
    return await dhanam_subscription_webhook(
        request=request, db=AsyncMock(), x_dhanam_signature=signature
    )


def _org(product_tiers: dict, subscription_tier: str = "community"):
    return SimpleNamespace(
        id=uuid4(),
        name="Org",
        product_tiers=product_tiers,
        subscription_tier=subscription_tier,
        billing_customer_id="cus_1",
        updated_at=None,
    )


def _event(event_type: str, plan_id: str, org) -> dict:
    return {
        "type": event_type,
        "data": {"customer_id": "cus_1", "plan_id": plan_id, "organization_id": str(org.id)},
    }


@pytest.fixture
def _secret(monkeypatch):
    monkeypatch.setattr(webhooks_dhanam.settings, "DHANAM_WEBHOOK_SECRET", SECRET)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_secret")
class TestWebhookWritesTheSummary:
    @pytest.mark.parametrize(
        "plan_id",
        ["karafiel_contador", "dhanam_premium_monthly", "selva_team", "tezca_academic_yearly"],
    )
    async def test_catalog_purchase_is_no_longer_community(self, plan_id):
        org = _org({})
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            out = await _call(_event("subscription.created", plan_id, org))
        assert out["status"] == "processed"
        assert org.subscription_tier == "pro"

    async def test_upgrade_within_a_product_stays_pro(self):
        org = _org({"karafiel": "contador"}, "pro")
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.updated", "karafiel_firma", org))
        assert org.product_tiers == {"karafiel": "firma"}
        assert org.subscription_tier == "pro"

    async def test_cancel_of_the_only_paid_product_returns_to_community(self):
        org = _org({"karafiel": "contador"}, "pro")
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.canceled", "karafiel_contador", org))
        assert org.product_tiers == {}
        assert org.subscription_tier == "community"

    async def test_cancel_keeps_pro_while_another_product_is_paid(self):
        org = _org({"karafiel": "contador", "selva": "team"}, "pro")
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.canceled", "selva_team", org))
        assert org.subscription_tier == "pro"

    async def test_madfam_org_summary_is_unchanged(self):
        org = _org({"yantra4d": "madfam", "cotiza": "madfam"}, "enterprise")
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.created", "karafiel_contador", org))
        assert org.subscription_tier == "enterprise"
