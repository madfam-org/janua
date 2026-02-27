"""
Tests for Dhanam billing webhook plan parsing and per-product tier resolution.

Covers:
- parse_product_plan(): plan_id string -> (product, tier) tuple
- resolve_product_tiers(): organization tier data -> JWT claim dict
"""

import pytest

from app.routers.v1.webhooks_dhanam import parse_product_plan
from app.sso.application.services.sso_orchestrator import resolve_product_tiers


class TestParseProductPlan:
    """Test plan_id -> (product, tier) parsing logic."""

    # --- Product-prefixed plans ---

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("tezca_pro", ("tezca", "pro")),
            ("tezca_essentials", ("tezca", "essentials")),
            ("tezca_madfam", ("tezca", "madfam")),
            ("enclii_pro", ("enclii", "pro")),
            ("enclii_essentials", ("enclii", "essentials")),
            ("enclii_madfam", ("enclii", "madfam")),
            ("yantra4d_pro", ("yantra4d", "pro")),
            ("dhanam_essentials", ("dhanam", "essentials")),
        ],
    )
    def test_product_prefixed_plans(self, plan_id: str, expected: tuple):
        """Plans with '{product}_{tier}' format parse correctly."""
        assert parse_product_plan(plan_id) == expected

    # --- Legacy plan mappings ---

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("sovereign", ("enclii", "pro")),
            ("ecosystem", ("enclii", "madfam")),
            ("enclii_sovereign", ("enclii", "pro")),
            ("enclii_ecosystem", ("enclii", "madfam")),
            ("enterprise", ("dhanam", "madfam")),
            ("scale", ("dhanam", "pro")),
        ],
    )
    def test_legacy_plan_mappings(self, plan_id: str, expected: tuple):
        """Legacy plan names map to correct (product, tier) pairs."""
        assert parse_product_plan(plan_id) == expected

    # --- Cancel / free tiers ---

    @pytest.mark.parametrize("plan_id", ["free", "community", "trial"])
    def test_cancel_tier_bare(self, plan_id: str):
        """Bare cancel-tier names return (dhanam, None)."""
        product, tier = parse_product_plan(plan_id)
        assert product == "dhanam"
        assert tier is None

    @pytest.mark.parametrize(
        "plan_id, expected_product",
        [
            ("tezca_free", "tezca"),
            ("enclii_community", "enclii"),
            ("yantra4d_trial", "yantra4d"),
            ("dhanam_free", "dhanam"),
        ],
    )
    def test_cancel_tier_product_prefixed(self, plan_id: str, expected_product: str):
        """Product-prefixed cancel tiers return (product, None)."""
        product, tier = parse_product_plan(plan_id)
        assert product == expected_product
        assert tier is None

    # --- Bare tier names (no product prefix) ---

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("pro", ("dhanam", "pro")),
            ("essentials", ("dhanam", "essentials")),
            ("madfam", ("dhanam", "madfam")),
        ],
    )
    def test_bare_tier_defaults_to_dhanam(self, plan_id: str, expected: tuple):
        """Bare valid tier names default to dhanam product."""
        assert parse_product_plan(plan_id) == expected

    # --- Billing period suffix stripping ---

    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            ("tezca_pro_monthly", ("tezca", "pro")),
            ("enclii_essentials_annual", ("enclii", "essentials")),
            ("pro_yearly", ("dhanam", "pro")),
            ("sovereign_monthly", ("enclii", "pro")),
        ],
    )
    def test_billing_suffix_stripped(self, plan_id: str, expected: tuple):
        """Billing period suffixes (_monthly, _annual, _yearly) are stripped."""
        assert parse_product_plan(plan_id) == expected

    # --- Case insensitivity ---

    def test_case_insensitive(self):
        """Plan parsing is case-insensitive."""
        assert parse_product_plan("TEZCA_PRO") == ("tezca", "pro")
        assert parse_product_plan("Sovereign") == ("enclii", "pro")
        assert parse_product_plan("FREE") == ("dhanam", None)

    # --- Edge cases ---

    def test_empty_string(self):
        """Empty plan_id returns (dhanam, None)."""
        assert parse_product_plan("") == ("dhanam", None)

    def test_unrecognized_plan(self):
        """Completely unrecognized plan_id returns (dhanam, None)."""
        assert parse_product_plan("xyzzy_garbage") == ("dhanam", None)

    def test_unknown_tier_for_known_product(self):
        """Known product with unknown tier returns (product, tier) as-is."""
        product, tier = parse_product_plan("enclii_platinum")
        assert product == "enclii"
        assert tier == "platinum"


class TestResolveProductTiers:
    """Test Organization tier data -> JWT claims resolution."""

    # --- Empty / fallback behavior ---

    def test_empty_product_tiers_no_subscription(self):
        """No product_tiers and no subscription_tier -> community foundry_tier."""
        claims = resolve_product_tiers(None, None)
        assert claims["foundry_tier"] == "community"
        # No per-product claims for tezca/yantra4d/dhanam
        assert "tezca_tier" not in claims
        assert "yantra4d_tier" not in claims
        assert "dhanam_tier" not in claims

    def test_empty_product_tiers_with_legacy_subscription(self):
        """No product_tiers falls back to legacy subscription_tier mapping."""
        claims = resolve_product_tiers(None, "pro")
        assert claims["foundry_tier"] == "sovereign"

        claims = resolve_product_tiers({}, "enterprise")
        assert claims["foundry_tier"] == "ecosystem"

        claims = resolve_product_tiers({}, "community")
        assert claims["foundry_tier"] == "community"

    # --- Enclii -> foundry_tier mapping ---

    @pytest.mark.parametrize(
        "enclii_tier, expected_foundry",
        [
            ("essentials", "community"),
            ("pro", "sovereign"),
            ("madfam", "ecosystem"),
        ],
    )
    def test_enclii_tier_maps_to_foundry(self, enclii_tier: str, expected_foundry: str):
        """Enclii product tier maps to backwards-compatible foundry_tier values."""
        claims = resolve_product_tiers({"enclii": enclii_tier}, None)
        assert claims["foundry_tier"] == expected_foundry

    def test_enclii_tier_overrides_legacy_subscription(self):
        """Explicit enclii product_tier takes precedence over subscription_tier."""
        claims = resolve_product_tiers({"enclii": "pro"}, "community")
        assert claims["foundry_tier"] == "sovereign"

    # --- Per-product claims ---

    def test_tezca_tier_emitted(self):
        """Tezca product tier emits tezca_tier claim."""
        claims = resolve_product_tiers({"tezca": "pro"}, None)
        assert claims["tezca_tier"] == "pro"

    def test_yantra4d_tier_emitted(self):
        """Yantra4D product tier emits yantra4d_tier claim."""
        claims = resolve_product_tiers({"yantra4d": "madfam"}, None)
        assert claims["yantra4d_tier"] == "madfam"

    def test_dhanam_tier_emitted(self):
        """Dhanam product tier emits dhanam_tier claim."""
        claims = resolve_product_tiers({"dhanam": "essentials"}, None)
        assert claims["dhanam_tier"] == "essentials"

    def test_absent_product_tier_omits_claim(self):
        """Products without a tier do not appear in claims."""
        claims = resolve_product_tiers({"enclii": "pro"}, None)
        assert "tezca_tier" not in claims
        assert "yantra4d_tier" not in claims
        assert "dhanam_tier" not in claims

    # --- Multi-product scenarios ---

    def test_multi_product_tiers(self):
        """Multiple product tiers emit all corresponding claims."""
        tiers = {
            "enclii": "madfam",
            "tezca": "pro",
            "yantra4d": "essentials",
            "dhanam": "madfam",
        }
        claims = resolve_product_tiers(tiers, None)
        assert claims["foundry_tier"] == "ecosystem"
        assert claims["tezca_tier"] == "pro"
        assert claims["yantra4d_tier"] == "essentials"
        assert claims["dhanam_tier"] == "madfam"

    def test_partial_product_tiers(self):
        """Only products with tiers appear in claims."""
        tiers = {"tezca": "pro"}
        claims = resolve_product_tiers(tiers, "community")
        # No enclii tier -> falls back to legacy subscription_tier
        assert claims["foundry_tier"] == "community"
        assert claims["tezca_tier"] == "pro"
        assert "yantra4d_tier" not in claims
        assert "dhanam_tier" not in claims
