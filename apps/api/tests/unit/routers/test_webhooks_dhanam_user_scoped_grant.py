"""
User-scoped (org-less) grants on the Dhanam subscription webhook.

Dhanam's hosted checkout (owner ruling G1-1, 2026-10-14) sells to the buyer's
Janua user when the buyer has no organization they own or administer. Dhanam
then sends `data.grant_to = "user"` with `user_id` (Janua subject) and/or
`user_email`, and NO `organization_id`. Before this change the reader looked
for an organization first and answered 404, so the buyer paid and nothing
was unlocked.

Pins:
- the user path never reads or writes an organization (not even by
  `customer_id`, which may already be some org's billing customer);
- created/updated upsert, canceled/deleted cancel, the user's entitlement for
  the plan's product;
- strict refusals: unknown `grant_to` (400), no user identifier (400), no
  plan (400), a plan that names no product (422), unknown user (404);
- payloads without `grant_to` keep the org path unchanged (404 when no org).

Counterpart: madfam-org/dhanam branch feat/hosted-checkout-g1-1,
`subscription-janua-notifier.service.ts` (`notifyJanuaOfUserGrant`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import EntitlementSource
from app.routers.v1 import webhooks_dhanam
from app.routers.v1.webhooks_dhanam import dhanam_subscription_webhook

pytestmark = pytest.mark.asyncio

SECRET = "test-dhanam-webhook-secret"
MODULE = "app.routers.v1.webhooks_dhanam"


class _FakeRequest:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    async def body(self) -> bytes:
        return self._body

    async def json(self) -> dict:
        return json.loads(self._body)


def _signed(payload: dict) -> tuple[_FakeRequest, str]:
    request = _FakeRequest(payload)
    signature = hmac.new(SECRET.encode(), request._body, hashlib.sha256).hexdigest()
    return request, signature


def _user_grant(event_type: str = "subscription.created", **data) -> dict:
    base = {
        "customer_id": "dhanam-user-1",
        "plan_id": "karafiel_contador_yearly",
        "grant_to": "user",
        "user_id": str(uuid4()),
        "user_email": "buyer@example.com",
        "subscription_id": "sub_hosted_1",
    }
    base.update(data)
    return {"type": event_type, "data": {k: v for k, v in base.items() if v is not None}}


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(webhooks_dhanam.settings, "DHANAM_WEBHOOK_SECRET", SECRET)


async def _call(payload: dict, db=None):
    request, signature = _signed(payload)
    return await dhanam_subscription_webhook(
        request=request, db=db or AsyncMock(), x_dhanam_signature=signature
    )


class TestUserScopedGrant:
    async def test_created_upserts_the_user_entitlement_without_any_org(self):
        user = SimpleNamespace(id=uuid4())
        db = AsyncMock()
        with (
            patch(f"{MODULE}.find_organization", AsyncMock()) as find_org,
            patch(f"{MODULE}._resolve_user", AsyncMock(return_value=user)) as resolve,
            patch(
                f"{MODULE}.upsert_entitlement",
                AsyncMock(return_value=MagicMock(tier="contador")),
            ) as upsert,
        ):
            payload = _user_grant()
            out = await _call(payload, db)

        find_org.assert_not_awaited()
        resolve.assert_awaited_once_with(
            db, payload["data"]["user_id"], payload["data"]["user_email"]
        )
        kwargs = upsert.await_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["product"] == "karafiel"
        assert kwargs["tier"] == "contador"
        assert kwargs["source"] == EntitlementSource.DHANAM_SUBSCRIPTION
        assert kwargs["dhanam_subscription_id"] == "sub_hosted_1"
        db.commit.assert_awaited_once()
        assert out["status"] == "processed"
        assert out["grant_to"] == "user"
        assert out["product"] == "karafiel"
        assert out["new_tier"] == "contador"
        assert out["user_entitlement"]["action"] == "upserted"
        assert "organization_id" not in out

    @pytest.mark.parametrize("event_type", ["subscription.canceled", "subscription.deleted"])
    async def test_cancel_revokes_the_user_entitlement(self, event_type: str):
        user = SimpleNamespace(id=uuid4())
        with (
            patch(f"{MODULE}.find_organization", AsyncMock()) as find_org,
            patch(f"{MODULE}._resolve_user", AsyncMock(return_value=user)),
            patch(f"{MODULE}.cancel_entitlement", AsyncMock(return_value=MagicMock())) as cancel,
            patch(f"{MODULE}.upsert_entitlement", AsyncMock()) as upsert,
        ):
            out = await _call(_user_grant(event_type))

        find_org.assert_not_awaited()
        upsert.assert_not_awaited()
        cancel.assert_awaited_once()
        assert cancel.await_args.kwargs == {"user_id": user.id, "product": "karafiel"}
        assert out["user_entitlement"]["action"] == "cancelled"
        assert out["new_tier"] is None

    async def test_email_only_grant_is_accepted(self):
        user = SimpleNamespace(id=uuid4())
        with (
            patch(f"{MODULE}._resolve_user", AsyncMock(return_value=user)) as resolve,
            patch(
                f"{MODULE}.upsert_entitlement",
                AsyncMock(return_value=MagicMock(tier="pro")),
            ),
        ):
            out = await _call(_user_grant(plan_id="forgesight_pro", user_id=None))

        resolve.assert_awaited_once()
        assert resolve.await_args.args[1] is None
        assert resolve.await_args.args[2] == "buyer@example.com"
        assert out["user_entitlement"]["action"] == "upserted"

    async def test_unknown_user_is_404_and_writes_nothing(self):
        db = AsyncMock()
        with (
            patch(f"{MODULE}._resolve_user", AsyncMock(return_value=None)),
            patch(f"{MODULE}.upsert_entitlement", AsyncMock()) as upsert,
        ):
            with pytest.raises(HTTPException) as exc:
                await _call(_user_grant(), db)
        assert exc.value.status_code == 404
        upsert.assert_not_awaited()
        db.commit.assert_not_awaited()

    @pytest.mark.parametrize(
        "overrides, status",
        [
            ({"grant_to": "org"}, 400),
            ({"user_id": None, "user_email": None}, 400),
            ({"plan_id": "pro"}, 422),
            ({"plan_id": "xyzzy"}, 422),
        ],
    )
    async def test_strict_refusals(self, overrides: dict, status: int):
        with (
            patch(f"{MODULE}.find_organization", AsyncMock()) as find_org,
            patch(f"{MODULE}._resolve_user", AsyncMock()) as resolve,
        ):
            with pytest.raises(HTTPException) as exc:
                await _call(_user_grant(**overrides))
        assert exc.value.status_code == status
        find_org.assert_not_awaited()
        resolve.assert_not_awaited()

    async def test_cancel_without_plan_is_refused(self):
        with pytest.raises(HTTPException) as exc:
            await _call(_user_grant("subscription.canceled", plan_id=None))
        assert exc.value.status_code == 400

    async def test_dhanam_named_plan_is_a_valid_user_grant(self):
        user = SimpleNamespace(id=uuid4())
        with (
            patch(f"{MODULE}._resolve_user", AsyncMock(return_value=user)),
            patch(
                f"{MODULE}.upsert_entitlement",
                AsyncMock(return_value=MagicMock(tier="pro")),
            ) as upsert,
        ):
            await _call(_user_grant(plan_id="dhanam_pro"))
        assert upsert.await_args.kwargs["product"] == "dhanam"

    async def test_bad_signature_is_still_401(self):
        request, _ = _signed(_user_grant())
        with pytest.raises(HTTPException) as exc:
            await dhanam_subscription_webhook(
                request=request, db=AsyncMock(), x_dhanam_signature="0" * 64
            )
        assert exc.value.status_code == 401


class TestOrgPathUnchanged:
    async def test_payload_without_grant_to_and_without_org_is_still_404(self):
        payload = {
            "type": "subscription.created",
            "data": {"customer_id": "dhanam-user-1", "plan_id": "karafiel_contador"},
        }
        with (
            patch(f"{MODULE}.find_organization", AsyncMock(return_value=None)) as find_org,
            patch(f"{MODULE}.upsert_entitlement", AsyncMock()) as upsert,
        ):
            with pytest.raises(HTTPException) as exc:
                await _call(payload)
        assert exc.value.status_code == 404
        find_org.assert_awaited_once()
        upsert.assert_not_awaited()

    async def test_org_grant_still_writes_product_tiers(self):
        org = SimpleNamespace(
            id=uuid4(),
            name="Despacho",
            product_tiers={"dhanam": "pro"},
            subscription_tier="pro",
            billing_customer_id=None,
            updated_at=None,
        )
        payload = {
            "type": "subscription.created",
            "data": {
                "customer_id": "dhanam-user-1",
                "plan_id": "karafiel_contador",
                "organization_id": str(org.id),
            },
        }
        with patch(f"{MODULE}.find_organization", AsyncMock(return_value=org)):
            out = await _call(payload)
        assert out["status"] == "processed"
        assert org.product_tiers == {"dhanam": "pro", "karafiel": "contador"}
        assert out["user_entitlement"] == {"action": "skipped", "reason": "no_user_identifier"}
