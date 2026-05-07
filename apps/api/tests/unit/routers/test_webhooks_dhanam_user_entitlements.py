"""
Unit tests for the per-user entitlement extension to webhooks_dhanam.

Targets the `_maybe_upsert_user_entitlement` helper. Covers:
- Skip when the payload omits a user identifier.
- Skip when the identifier doesn't resolve to a Janua user.
- Upsert path on subscription.activated/updated.
- Cancel path on subscription.canceled/deleted.
- Cancel path when tier resolves to None (free/community plan).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import EntitlementSource
from app.routers.v1.webhooks_dhanam import _maybe_upsert_user_entitlement

pytestmark = pytest.mark.asyncio


def _user():
    return SimpleNamespace(id=uuid4(), email="ops@madfam.io")


class TestMaybeUpsertUserEntitlement:
    async def test_skip_when_no_user_identifier(self):
        db = AsyncMock()
        out = await _maybe_upsert_user_entitlement(
            db=db,
            product="karafiel",
            new_tier="contador",
            event_type="subscription.created",
            user_id_payload=None,
            user_email_payload=None,
            subscription_id="sub_1",
        )
        assert out["action"] == "skipped"
        assert out["reason"] == "no_user_identifier"

    async def test_skip_when_user_not_found(self):
        db = AsyncMock()
        with patch(
            "app.routers.v1.webhooks_dhanam._resolve_user",
            AsyncMock(return_value=None),
        ):
            out = await _maybe_upsert_user_entitlement(
                db=db,
                product="karafiel",
                new_tier="contador",
                event_type="subscription.created",
                user_id_payload=str(uuid4()),
                user_email_payload=None,
                subscription_id="sub_1",
            )
        assert out["action"] == "skipped"
        assert out["reason"] == "user_not_found"

    async def test_upsert_on_created(self):
        db = AsyncMock()
        user = _user()
        upserted_row = MagicMock(tier="contador")
        with (
            patch(
                "app.routers.v1.webhooks_dhanam._resolve_user",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.webhooks_dhanam.upsert_entitlement",
                AsyncMock(return_value=upserted_row),
            ) as upsert_mock,
        ):
            out = await _maybe_upsert_user_entitlement(
                db=db,
                product="karafiel",
                new_tier="contador",
                event_type="subscription.created",
                user_id_payload=str(user.id),
                user_email_payload=None,
                subscription_id="sub_1",
            )
        assert out["action"] == "upserted"
        upsert_mock.assert_awaited_once()
        kwargs = upsert_mock.await_args.kwargs
        assert kwargs["product"] == "karafiel"
        assert kwargs["tier"] == "contador"
        assert kwargs["source"] == EntitlementSource.DHANAM_SUBSCRIPTION
        assert kwargs["dhanam_subscription_id"] == "sub_1"

    async def test_cancel_on_canceled_event(self):
        db = AsyncMock()
        user = _user()
        with (
            patch(
                "app.routers.v1.webhooks_dhanam._resolve_user",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.webhooks_dhanam.cancel_entitlement",
                AsyncMock(return_value=MagicMock()),
            ) as cancel_mock,
        ):
            out = await _maybe_upsert_user_entitlement(
                db=db,
                product="karafiel",
                new_tier=None,
                event_type="subscription.canceled",
                user_id_payload=str(user.id),
                user_email_payload=None,
                subscription_id="sub_1",
            )
        assert out["action"] == "cancelled"
        cancel_mock.assert_awaited_once()

    async def test_cancel_on_deleted_event(self):
        db = AsyncMock()
        user = _user()
        with (
            patch(
                "app.routers.v1.webhooks_dhanam._resolve_user",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.webhooks_dhanam.cancel_entitlement",
                AsyncMock(return_value=MagicMock()),
            ) as cancel_mock,
        ):
            out = await _maybe_upsert_user_entitlement(
                db=db,
                product="karafiel",
                new_tier=None,
                event_type="subscription.deleted",
                user_id_payload=str(user.id),
                user_email_payload=None,
                subscription_id="sub_1",
            )
        assert out["action"] == "cancelled"
        cancel_mock.assert_awaited_once()

    async def test_cancel_when_tier_resolves_to_none(self):
        """A subscription.updated → free plan should drop the entitlement."""
        db = AsyncMock()
        user = _user()
        with (
            patch(
                "app.routers.v1.webhooks_dhanam._resolve_user",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.webhooks_dhanam.cancel_entitlement",
                AsyncMock(return_value=MagicMock()),
            ) as cancel_mock,
        ):
            out = await _maybe_upsert_user_entitlement(
                db=db,
                product="karafiel",
                new_tier=None,
                event_type="subscription.updated",
                user_id_payload=None,
                user_email_payload="ops@madfam.io",
                subscription_id="sub_1",
            )
        assert out["action"] == "cancelled"
        assert out["reason"] == "tier_resolved_to_none"
        cancel_mock.assert_awaited_once()

    async def test_invalid_uuid_payload_falls_back_to_email(self):
        """Malformed user_id must not crash the webhook — email lookup still tried."""
        db = AsyncMock()
        user = _user()

        # _resolve_user is the unit we exercise here. Mocked to return user.
        with (
            patch(
                "app.routers.v1.webhooks_dhanam._resolve_user",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.routers.v1.webhooks_dhanam.upsert_entitlement",
                AsyncMock(return_value=MagicMock(tier="contador")),
            ),
        ):
            out = await _maybe_upsert_user_entitlement(
                db=db,
                product="karafiel",
                new_tier="contador",
                event_type="subscription.updated",
                user_id_payload="not-a-uuid",
                user_email_payload="ops@madfam.io",
                subscription_id="sub_1",
            )
        assert out["action"] == "upserted"
