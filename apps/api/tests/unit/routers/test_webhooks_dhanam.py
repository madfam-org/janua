"""
Tests for Dhanam billing webhook plan parsing and per-product tier resolution.

Covers:
- parse_product_plan(): plan_id string -> (product, tier) tuple
- resolve_product_tiers(): organization tier data -> JWT claim dict
- find_organization(): an explicit organization id takes precedence over the
  billing_customer_id lookup (ruling V14)
"""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.routers.v1 import webhooks_dhanam
from app.routers.v1.webhooks_dhanam import (
    dhanam_subscription_webhook,
    find_organization,
    parse_product_plan,
)
from app.sso.application.services.product_tiers import resolve_product_tiers


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
            # Zero-touch: any product name is accepted without code changes
            ("karafiel_pro", ("karafiel", "pro")),
            ("karafiel_essentials", ("karafiel", "essentials")),
            ("forgesight_madfam", ("forgesight", "madfam")),
            ("newservice_pro", ("newservice", "pro")),
            # Hyphenated catalog slugs — before the hyphen fix these fell
            # through to ("dhanam", None), which cancelled the buyer's dhanam
            # tier instead of granting the purchased product.
            ("pravara-mes_starter", ("pravara-mes", "starter")),
            ("pravara-mes_growth", ("pravara-mes", "growth")),
            ("pravara-mes_enterprise", ("pravara-mes", "enterprise")),
            ("nuit-one_artist_pro", ("nuit-one", "artist_pro")),
            ("nuit-one_label", ("nuit-one", "label")),
        ],
    )
    def test_product_prefixed_plans(self, plan_id: str, expected: tuple):
        """Plans with '{product}_{tier}' format parse correctly (any product accepted)."""
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
            ("karafiel_free", "karafiel"),
            ("newservice_community", "newservice"),
            ("pravara-mes_free", "pravara-mes"),
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
            ("nuit-one_artist_pro_monthly", ("nuit-one", "artist_pro")),
            ("pravara-mes_starter_yearly", ("pravara-mes", "starter")),
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

    def test_unrecognized_plan_single_word(self):
        """Single unrecognized word (not a tier, not a legacy plan) returns (dhanam, None)."""
        assert parse_product_plan("xyzzy") == ("dhanam", None)

    def test_numeric_prefix_rejected(self):
        """Product names starting with digits are rejected."""
        assert parse_product_plan("123_pro") == ("dhanam", None)

    @pytest.mark.parametrize("plan_id", ["-nuit_pro", "nuit-_pro", "nuit--one_pro"])
    def test_malformed_hyphen_slugs_rejected(self, plan_id: str):
        """Leading/trailing/doubled hyphens are not valid product slugs."""
        assert parse_product_plan(plan_id) == ("dhanam", None)

    def test_unknown_tier_for_any_product(self):
        """Any product with unknown tier returns (product, tier) as-is."""
        product, tier = parse_product_plan("enclii_platinum")
        assert product == "enclii"
        assert tier == "platinum"

        # Works for new products too (open product parsing)
        product2, tier2 = parse_product_plan("newservice_platinum")
        assert product2 == "newservice"
        assert tier2 == "platinum"


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

    def test_karafiel_tier_emitted(self):
        """Karafiel product tier emits karafiel_tier claim (zero-touch, no code change needed)."""
        claims = resolve_product_tiers({"karafiel": "pro"}, None)
        assert claims["karafiel_tier"] == "pro"

    def test_forgesight_tier_emitted(self):
        """Forgesight product tier emits forgesight_tier claim."""
        claims = resolve_product_tiers({"forgesight": "essentials"}, None)
        assert claims["forgesight_tier"] == "essentials"

    def test_unknown_product_tier_emitted(self):
        """Any product stored in product_tiers gets a JWT claim (zero-touch onboarding)."""
        claims = resolve_product_tiers({"newservice": "pro"}, None)
        assert claims["newservice_tier"] == "pro"

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
            "karafiel": "pro",
            "forgesight": "essentials",
        }
        claims = resolve_product_tiers(tiers, None)
        assert claims["foundry_tier"] == "ecosystem"
        assert claims["tezca_tier"] == "pro"
        assert claims["yantra4d_tier"] == "essentials"
        assert claims["dhanam_tier"] == "madfam"
        assert claims["karafiel_tier"] == "pro"
        assert claims["forgesight_tier"] == "essentials"

    def test_partial_product_tiers(self):
        """Only products with tiers appear in claims."""
        tiers = {"tezca": "pro"}
        claims = resolve_product_tiers(tiers, "community")
        # No enclii tier -> falls back to legacy subscription_tier
        assert claims["foundry_tier"] == "community"
        assert claims["tezca_tier"] == "pro"
        assert "yantra4d_tier" not in claims
        assert "dhanam_tier" not in claims


# ---------------------------------------------------------------------------
# find_organization: explicit organization id first (ruling V14)
# ---------------------------------------------------------------------------

CUSTOMER = "cus_buyer_1"
SECRET = "test-dhanam-webhook-secret"


class _Result:
    def __init__(self, rows: list):
        self._rows = rows

    def scalar_one_or_none(self):
        assert len(self._rows) <= 1
        return self._rows[0] if self._rows else None

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _FakeOrgDB:
    """Answers `select(Organization).where(Organization.<col> == value)`
    from an in-memory list, and records which column each query used."""

    def __init__(self, *orgs):
        self.orgs = list(orgs)
        self.queried_columns: list[str] = []
        self.commit = AsyncMock()

    async def execute(self, stmt):
        clause = stmt.whereclause
        column = clause.left.key
        value = clause.right.value
        self.queried_columns.append(column)
        rows = [o for o in self.orgs if getattr(o, column) == value]
        limit = getattr(stmt, "_limit", None)
        return _Result(rows[:limit] if limit else rows)


def _org(billing_customer_id: str | None, name: str = "Org"):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        billing_customer_id=billing_customer_id,
        product_tiers={},
        subscription_tier="community",
        updated_at=None,
    )


@pytest.mark.asyncio
class TestFindOrganizationExplicitIdWins:
    async def test_buyer_with_two_orgs_buying_for_the_second(self):
        first = _org(CUSTOMER, "First")
        second = _org(None, "Second")
        db = _FakeOrgDB(first, second)

        found = await find_organization(db, CUSTOMER, str(second.id), {})

        assert found is second
        assert db.queried_columns == ["id"]
        # The empty field is linked; the first org keeps its link.
        assert second.billing_customer_id == CUSTOMER
        assert first.billing_customer_id == CUSTOMER

    async def test_metadata_organization_id_is_also_explicit(self):
        first = _org(CUSTOMER)
        second = _org(None)
        db = _FakeOrgDB(first, second)

        found = await find_organization(db, CUSTOMER, None, {"organization_id": str(second.id)})

        assert found is second
        assert db.queried_columns == ["id"]

    async def test_existing_link_on_the_target_is_never_repointed(self):
        first = _org(CUSTOMER)
        second = _org("cus_other")
        db = _FakeOrgDB(first, second)

        found = await find_organization(db, CUSTOMER, str(second.id), {})

        assert found is second
        assert second.billing_customer_id == "cus_other"
        assert first.billing_customer_id == CUSTOMER

    @pytest.mark.parametrize("explicit", ["5f0c6a52-0000-4000-8000-000000000001", "not-a-uuid"])
    async def test_unknown_explicit_id_is_not_found_without_customer_fallback(self, explicit):
        linked = _org(CUSTOMER)
        db = _FakeOrgDB(linked)

        assert await find_organization(db, CUSTOMER, explicit, {}) is None
        assert await find_organization(db, CUSTOMER, None, {"organization_id": explicit}) is None
        assert "billing_customer_id" not in db.queried_columns

    async def test_no_explicit_id_keeps_the_customer_lookup(self):
        linked = _org(CUSTOMER)
        db = _FakeOrgDB(linked, _org(None))

        assert await find_organization(db, CUSTOMER, None, {}) is linked
        assert db.queried_columns == ["billing_customer_id"]

    async def test_no_explicit_id_and_no_match_is_not_found(self):
        db = _FakeOrgDB(_org("cus_other"))
        assert await find_organization(db, CUSTOMER, None, None) is None

    async def test_customer_shared_by_two_orgs_needs_an_explicit_id(self):
        db = _FakeOrgDB(_org(CUSTOMER), _org(CUSTOMER))
        assert await find_organization(db, CUSTOMER, None, {}) is None


class _FakeRequest:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    async def body(self) -> bytes:
        return self._body

    async def json(self) -> dict:
        return json.loads(self._body)


@pytest.mark.asyncio
class TestWebhookAppliesToTheExplicitOrganization:
    @pytest.fixture(autouse=True)
    def _secret(self, monkeypatch):
        monkeypatch.setattr(webhooks_dhanam.settings, "DHANAM_WEBHOOK_SECRET", SECRET)

    async def _call(self, payload: dict, db):
        request = _FakeRequest(payload)
        signature = hmac.new(SECRET.encode(), request._body, hashlib.sha256).hexdigest()
        with patch.object(
            webhooks_dhanam, "_maybe_upsert_user_entitlement", AsyncMock(return_value=None)
        ):
            return await dhanam_subscription_webhook(
                request=request, db=db, x_dhanam_signature=signature
            )

    async def test_second_purchase_lands_on_the_chosen_org(self):
        first = _org(CUSTOMER, "First")
        first.product_tiers = {"karafiel": "contador"}
        second = _org(None, "Second")
        db = _FakeOrgDB(first, second)

        out = await self._call(
            {
                "type": "subscription.created",
                "data": {
                    "customer_id": CUSTOMER,
                    "plan_id": "selva_team",
                    "organization_id": str(second.id),
                },
            },
            db,
        )

        assert out["organization_id"] == str(second.id)
        assert second.product_tiers == {"selva": "team"}
        assert first.product_tiers == {"karafiel": "contador"}
        db.commit.assert_awaited_once()

    async def test_unknown_explicit_id_answers_404(self):
        from fastapi import HTTPException

        db = _FakeOrgDB(_org(CUSTOMER))
        with pytest.raises(HTTPException) as exc:
            await self._call(
                {
                    "type": "subscription.created",
                    "data": {
                        "customer_id": CUSTOMER,
                        "plan_id": "selva_team",
                        "organization_id": str(uuid4()),
                    },
                },
                db,
            )
        assert exc.value.status_code == 404
        db.commit.assert_not_awaited()
