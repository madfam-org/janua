"""
Dhanam plan ids whose catalog product slug itself contains an underscore.

Dhanam's catalog sells `enclii_depot`, `nauta_erp` and `nauta_vcto`. The
plan-id grammar `{product}_{tier}` split on the FIRST underscore, so:

- `nauta_erp_self_serve` read as product `nauta`, tier `erp_self_serve`;
- `enclii_depot_pro` read as product `enclii`, tier `depot_pro`, so a Depot
  purchase overwrote the buyer's Enclii tier and a Depot cancel removed it.

Pins:
- every listed slug followed by `_<tier>` parses to (slug, tier), with the
  billing-period suffix, cancel tiers and unknown tiers handled as before;
- the longest listed slug wins;
- every plan id that is not `<listed slug>_<tier>` parses exactly as before,
  including the bare slugs themselves;
- the webhook writes and removes only the multi-word product's key.
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
from app.routers.v1.webhooks_dhanam import (
    MULTI_WORD_PRODUCTS,
    dhanam_subscription_webhook,
    parse_product_plan,
)

SECRET = "test-dhanam-webhook-secret"
MODULE = "app.routers.v1.webhooks_dhanam"


class TestMultiWordProductGrammar:
    def test_vendored_list_matches_the_catalog_slugs(self):
        assert sorted(MULTI_WORD_PRODUCTS) == ["enclii_depot", "nauta_erp", "nauta_vcto"]

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("nauta_erp_self_serve", ("nauta_erp", "self_serve")),
            ("nauta_erp_team", ("nauta_erp", "team")),
            ("nauta_erp_biz", ("nauta_erp", "biz")),
            ("nauta_vcto_esencial", ("nauta_vcto", "esencial")),
            ("nauta_vcto_ecosistema", ("nauta_vcto", "ecosistema")),
            ("nauta_vcto_escala", ("nauta_vcto", "escala")),
            ("enclii_depot_pro", ("enclii_depot", "pro")),
            ("enclii_depot_premium", ("enclii_depot", "premium")),
            ("enclii_depot_madfam", ("enclii_depot", "madfam")),
        ],
    )
    def test_catalog_plans_name_the_multi_word_product(self, plan_id, expected):
        assert parse_product_plan(plan_id) == expected

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("nauta_erp_team_monthly", ("nauta_erp", "team")),
            ("enclii_depot_pro_yearly", ("enclii_depot", "pro")),
            ("nauta_vcto_escala_annual", ("nauta_vcto", "escala")),
        ],
    )
    def test_billing_period_suffix_is_stripped_first(self, plan_id, expected):
        assert parse_product_plan(plan_id) == expected

    @pytest.mark.parametrize("tier", ["free", "community", "trial"])
    def test_cancel_tier_removes_only_the_multi_word_product(self, tier):
        assert parse_product_plan(f"enclii_depot_{tier}") == ("enclii_depot", None)
        assert parse_product_plan(f"nauta_erp_{tier}") == ("nauta_erp", None)

    def test_case_insensitive(self):
        assert parse_product_plan("Enclii_Depot_PRO") == ("enclii_depot", "pro")

    def test_unknown_tier_is_kept_as_is(self):
        assert parse_product_plan("nauta_erp_platinum") == ("nauta_erp", "platinum")

    def test_longest_listed_slug_wins(self, monkeypatch):
        monkeypatch.setattr(webhooks_dhanam, "MULTI_WORD_PRODUCTS", ("nauta_erp", "nauta_erp_plus"))
        assert parse_product_plan("nauta_erp_plus_team") == ("nauta_erp_plus", "team")
        assert parse_product_plan("nauta_erp_team") == ("nauta_erp", "team")

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            # Bare slugs and an empty tier are not `<slug>_<tier>`: they keep
            # the first-underscore grammar they had before.
            ("nauta_erp", ("nauta", "erp")),
            ("nauta_vcto", ("nauta", "vcto")),
            ("enclii_depot", ("enclii", "depot")),
            ("nauta_erp_", ("nauta", "erp_")),
            # Single-word products are untouched, including the ones that
            # share a first word with a listed slug.
            ("enclii_pro", ("enclii", "pro")),
            ("enclii_essentials_monthly", ("enclii", "essentials")),
            ("enclii_sovereign", ("enclii", "pro")),
            ("nauta_pro", ("nauta", "pro")),
            ("enclii_depotx_pro", ("enclii", "depotx_pro")),
            ("tezca_pro_plus", ("tezca", "pro_plus")),
            ("nuit-one_artist_pro", ("nuit-one", "artist_pro")),
            ("pro", ("dhanam", "pro")),
            ("free", ("dhanam", None)),
            ("", ("dhanam", None)),
        ],
    )
    def test_everything_else_parses_as_before(self, plan_id, expected):
        assert parse_product_plan(plan_id) == expected


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


def _org(product_tiers: dict):
    return SimpleNamespace(
        id=uuid4(),
        name="Org",
        product_tiers=product_tiers,
        subscription_tier="pro",
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
class TestWebhookKeepsSiblingProducts:
    async def test_depot_purchase_leaves_the_enclii_tier(self):
        org = _org({"enclii": "pro"})
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            out = await _call(_event("subscription.created", "enclii_depot_pro", org))
        assert out["status"] == "processed"
        assert org.product_tiers == {"enclii": "pro", "enclii_depot": "pro"}

    async def test_depot_cancel_leaves_the_enclii_tier(self):
        org = _org({"enclii": "pro", "enclii_depot": "pro"})
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.canceled", "enclii_depot_pro", org))
        assert org.product_tiers == {"enclii": "pro"}

    async def test_nauta_products_are_separate_keys(self):
        org = _org({"nauta_vcto": "escala"})
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.created", "nauta_erp_self_serve", org))
        assert org.product_tiers == {"nauta_vcto": "escala", "nauta_erp": "self_serve"}

        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            await _call(_event("subscription.canceled", "nauta_vcto_escala", org))
        assert org.product_tiers == {"nauta_erp": "self_serve"}


class TestCheckoutKeepsTheCatalogPlanId:
    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("enclii_depot_pro", ("enclii_depot", "pro", "enclii_depot_pro")),
            ("nauta_erp_team_monthly", ("nauta_erp", "team", "nauta_erp_team_monthly")),
            ("enclii_pro", ("enclii", "pro", "enclii_pro")),
        ],
    )
    def test_checkout_resolves_the_multi_word_product(self, plan_id, expected):
        from app.routers.v1.checkout_dhanam import build_catalog_plan_id

        assert build_catalog_plan_id(plan_id) == expected
