"""
Tests for app.services.entitlements_service.

Covers the core invariants of the Selva-unified SSO Phase 1 entitlement
resolution: priority order (per-user > org > admin bootstrap), expiry
filtering, idempotent upsert, and cancellation semantics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import EntitlementSource
from app.services.entitlements_service import (
    ADMIN_BOOTSTRAP_PRODUCTS,
    ADMIN_TIER,
    Entitlement,
    cancel_entitlement,
    entitlements_to_claim,
    get_user_entitlements,
    upsert_entitlement,
)

pytestmark = pytest.mark.asyncio


def _user(*, is_admin: bool = False, tenant_id=None):
    """Build a minimal User-like object with the attributes the service reads."""
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        is_admin=is_admin,
        tenant_id=tenant_id,
    )


def _make_db_with_results(*query_results):
    """Build an AsyncSession mock that returns a sequence of execute() results.

    Each entry in `query_results` is a (mode, value) tuple:
      - ('scalars_all', list)   → execute().scalars().all() returns the list
      - ('scalar_one_or_none', value) → execute().scalar_one_or_none() returns value
      - ('first', tuple_or_none) → execute().first() returns the row
    """
    db = AsyncMock()
    calls = list(query_results)

    async def _execute(*_args, **_kwargs):
        if not calls:
            raise AssertionError("Unexpected execute() call after fixture exhausted")
        mode, value = calls.pop(0)
        result = MagicMock()
        if mode == "scalars_all":
            result.scalars.return_value = MagicMock(all=MagicMock(return_value=value))
        elif mode == "scalar_one_or_none":
            result.scalar_one_or_none = MagicMock(return_value=value)
        elif mode == "first":
            result.first = MagicMock(return_value=value)
        else:  # pragma: no cover
            raise ValueError(f"Unknown mock mode: {mode}")
        return result

    db.execute = AsyncMock(side_effect=_execute)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


class TestEntitlementToClaim:
    """The dataclass/serialization layer is small but load-bearing for JWT shape."""

    def test_to_claim_renders_product_colon_tier(self):
        e = Entitlement(
            product="karafiel",
            tier="contador",
            expires_at=None,
            source=EntitlementSource.DHANAM_SUBSCRIPTION,
        )
        assert e.to_claim() == "karafiel:contador"

    def test_entitlements_to_claim_sorts_by_product(self):
        items = [
            Entitlement("zeta", "pro", None, EntitlementSource.ADMIN_GRANT),
            Entitlement("alpha", "pro", None, EntitlementSource.ADMIN_GRANT),
            Entitlement("mu", "pro", None, EntitlementSource.ADMIN_GRANT),
        ]
        assert entitlements_to_claim(items) == ["alpha:pro", "mu:pro", "zeta:pro"]


class TestGetUserEntitlements:
    """Priority + filtering invariants for the canonical resolver."""

    async def test_no_grants_returns_empty(self):
        user = _user()
        # No memberships → primary org lookup returns nothing → org_tiers={}.
        # Then user_entitlements query returns [].
        db = _make_db_with_results(
            ("first", None),  # OrganizationMember.organization_id query
            ("scalars_all", []),  # UserEntitlement query
        )
        out = await get_user_entitlements(user, db)
        assert out == []

    async def test_missing_user_entitlements_table_rolls_back_session(self):
        user = _user()
        db = _make_db_with_results(("first", None))
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=None)),
                Exception('relation "user_entitlements" does not exist'),
            ]
        )
        db.rollback = AsyncMock()
        out = await get_user_entitlements(user, db)
        assert out == []
        db.rollback.assert_awaited_once()

    async def test_admin_bootstrap_grants_every_product(self):
        user = _user(is_admin=True)
        db = _make_db_with_results(
            ("first", None),
            ("scalars_all", []),
        )
        out = await get_user_entitlements(user, db)
        slugs = [e.product for e in out]
        for product in ADMIN_BOOTSTRAP_PRODUCTS:
            assert product in slugs
        assert all(e.tier == ADMIN_TIER for e in out)
        assert all(e.source == EntitlementSource.ADMIN_GRANT for e in out)

    async def test_per_user_row_overrides_admin_bootstrap(self):
        user = _user(is_admin=True)
        karafiel_row = MagicMock(
            product="karafiel",
            tier="contador",
            expires_at=None,
            source=EntitlementSource.DHANAM_SUBSCRIPTION,
        )
        db = _make_db_with_results(
            ("first", None),
            ("scalars_all", [karafiel_row]),
        )
        out = await get_user_entitlements(user, db)
        karafiel = next(e for e in out if e.product == "karafiel")
        # Per-user wins: tier should be 'contador', not 'admin'.
        assert karafiel.tier == "contador"
        assert karafiel.source == EntitlementSource.DHANAM_SUBSCRIPTION

    async def test_expired_per_user_row_excluded(self):
        user = _user()
        expired_row = MagicMock(
            product="karafiel",
            tier="contador",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            source=EntitlementSource.DHANAM_SUBSCRIPTION,
        )
        db = _make_db_with_results(
            ("first", None),
            ("scalars_all", [expired_row]),
        )
        out = await get_user_entitlements(user, db)
        assert all(e.product != "karafiel" for e in out)

    async def test_org_inheritance_when_no_per_user_row(self):
        org_id = uuid4()
        user = _user(tenant_id=org_id)
        org = MagicMock(product_tiers={"karafiel": "pro", "dhanam": "essentials"})
        db = _make_db_with_results(
            ("scalar_one_or_none", org),
            ("scalars_all", []),
        )
        out = await get_user_entitlements(user, db)
        karafiel = next(e for e in out if e.product == "karafiel")
        assert karafiel.tier == "pro"
        assert karafiel.source == EntitlementSource.INHERITED

    async def test_per_user_overrides_org_inheritance(self):
        org_id = uuid4()
        user = _user(tenant_id=org_id)
        org = MagicMock(product_tiers={"karafiel": "essentials"})
        explicit_row = MagicMock(
            product="karafiel",
            tier="firma",
            expires_at=None,
            source=EntitlementSource.DHANAM_SUBSCRIPTION,
        )
        db = _make_db_with_results(
            ("scalar_one_or_none", org),
            ("scalars_all", [explicit_row]),
        )
        out = await get_user_entitlements(user, db)
        karafiel = next(e for e in out if e.product == "karafiel")
        assert karafiel.tier == "firma"

    async def test_org_lookup_failure_does_not_raise(self):
        """Service must degrade silently — never block JWT issuance."""
        user = _user(tenant_id=uuid4())

        db = AsyncMock()

        # First call (org fetch) raises, second call (user rows) returns [].
        async def _execute(*_a, **_kw):
            if not getattr(_execute, "called", False):
                _execute.called = True
                raise RuntimeError("org fetch boom")
            result = MagicMock()
            result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
            return result

        db.execute = AsyncMock(side_effect=_execute)
        out = await get_user_entitlements(user, db)
        assert out == []

    async def test_user_rows_failure_does_not_raise(self):
        """Same invariant on the per-user rows query."""
        user = _user()

        db = AsyncMock()
        call_count = {"n": 0}

        async def _execute(*_a, **_kw):
            call_count["n"] += 1
            # 1st call: org member lookup returns no membership → no org tiers.
            if call_count["n"] == 1:
                result = MagicMock()
                result.first = MagicMock(return_value=None)
                return result
            # 2nd call: user_entitlements query raises
            raise RuntimeError("rows boom")

        db.execute = AsyncMock(side_effect=_execute)
        out = await get_user_entitlements(user, db)
        assert out == []


class TestUpsertEntitlement:
    """Idempotency contract for the Dhanam webhook integration."""

    async def test_creates_new_row_when_missing(self):
        user_id = uuid4()
        db = _make_db_with_results(("scalar_one_or_none", None))

        row = await upsert_entitlement(
            db,
            user_id=user_id,
            product="karafiel",
            tier="contador",
            source=EntitlementSource.DHANAM_SUBSCRIPTION,
            dhanam_subscription_id="sub_1",
        )

        db.add.assert_called_once()
        added_row = db.add.call_args.args[0]
        assert added_row.user_id == user_id
        assert added_row.product == "karafiel"
        assert added_row.tier == "contador"
        assert added_row.source == EntitlementSource.DHANAM_SUBSCRIPTION
        assert added_row.dhanam_subscription_id == "sub_1"
        assert row is added_row

    async def test_updates_existing_row(self):
        existing = MagicMock(
            tier="essentials",
            source=EntitlementSource.INHERITED,
            dhanam_subscription_id=None,
            expires_at=None,
            updated_at=datetime.utcnow(),
        )
        db = _make_db_with_results(("scalar_one_or_none", existing))

        row = await upsert_entitlement(
            db,
            user_id=uuid4(),
            product="karafiel",
            tier="firma",
            source=EntitlementSource.DHANAM_SUBSCRIPTION,
            dhanam_subscription_id="sub_xyz",
        )

        # No new row added — existing was mutated in place.
        db.add.assert_not_called()
        assert existing.tier == "firma"
        assert existing.source == EntitlementSource.DHANAM_SUBSCRIPTION
        assert existing.dhanam_subscription_id == "sub_xyz"
        assert row is existing


class TestCancelEntitlement:
    """Cancellation semantics for the webhook handler."""

    async def test_returns_none_when_no_row(self):
        db = _make_db_with_results(("scalar_one_or_none", None))
        out = await cancel_entitlement(db, user_id=uuid4(), product="karafiel")
        assert out is None

    async def test_sets_expires_at_when_active_row(self):
        existing = MagicMock(expires_at=None, updated_at=datetime.utcnow())
        db = _make_db_with_results(("scalar_one_or_none", existing))
        out = await cancel_entitlement(db, user_id=uuid4(), product="karafiel")
        assert out is existing
        assert existing.expires_at is not None

    async def test_idempotent_when_already_cancelled_in_past(self):
        """Calling cancel twice should not push the timestamp forward."""
        past = datetime.utcnow() - timedelta(days=1)
        existing = MagicMock(expires_at=past, updated_at=past)
        db = _make_db_with_results(("scalar_one_or_none", existing))
        await cancel_entitlement(db, user_id=uuid4(), product="karafiel")
        # Past expiry preserved — must not be overwritten with a later "now".
        assert existing.expires_at == past
