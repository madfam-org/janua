"""
Unit tests for `GET /api/v1/me/entitlements`.

Tests target the response shape contract — Atrium relies on this surface
to gate catalog tiles. Heavier integration coverage of the resolver lives
in `test_entitlements_service.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models import EntitlementSource
from app.routers.v1.me import EntitlementsResponse, my_entitlements
from app.services.entitlements_service import Entitlement

pytestmark = pytest.mark.asyncio


def _user(*, is_admin: bool = False):
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        is_admin=is_admin,
        tenant_id=None,
    )


class TestMyEntitlements:
    async def test_response_shape_matches_pydantic_model(self):
        user = _user()
        fake = [
            Entitlement(
                "karafiel",
                "contador",
                None,
                EntitlementSource.DHANAM_SUBSCRIPTION,
            ),
            Entitlement(
                "selva",
                "admin",
                None,
                EntitlementSource.ADMIN_GRANT,
            ),
        ]
        with patch(
            "app.routers.v1.me.get_user_entitlements",
            AsyncMock(return_value=fake),
        ):
            resp = await my_entitlements(current_user=user, db=AsyncMock())

        assert isinstance(resp, EntitlementsResponse)
        # Two products, sorted; claim_string_form mirrors the `<slug>:<tier>` form.
        assert [p.slug for p in resp.products] == ["karafiel", "selva"]
        assert resp.claim_string_form == ["karafiel:contador", "selva:admin"]

    async def test_empty_when_user_has_no_grants(self):
        user = _user()
        with patch(
            "app.routers.v1.me.get_user_entitlements",
            AsyncMock(return_value=[]),
        ):
            resp = await my_entitlements(current_user=user, db=AsyncMock())
        assert resp.products == []
        assert resp.claim_string_form == []

    async def test_source_field_is_string_value(self):
        """Atrium parses `source` as a string — make sure the enum doesn't leak."""
        user = _user()
        fake = [
            Entitlement(
                "dhanam",
                "pro",
                None,
                EntitlementSource.INHERITED,
            )
        ]
        with patch(
            "app.routers.v1.me.get_user_entitlements",
            AsyncMock(return_value=fake),
        ):
            resp = await my_entitlements(current_user=user, db=AsyncMock())
        assert resp.products[0].source == "inherited"

    async def test_expires_at_passed_through(self):
        user = _user()
        expiry = datetime(2027, 1, 1, tzinfo=timezone.utc)
        fake = [
            Entitlement(
                "karafiel",
                "contador",
                expiry,
                EntitlementSource.DHANAM_SUBSCRIPTION,
            )
        ]
        with patch(
            "app.routers.v1.me.get_user_entitlements",
            AsyncMock(return_value=fake),
        ):
            resp = await my_entitlements(current_user=user, db=AsyncMock())
        assert resp.products[0].expires_at == expiry
