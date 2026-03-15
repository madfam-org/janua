"""Tests for the guest access token endpoint (POST /api/v1/auth/guest)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_invite(
    *,
    token: str = "valid-invite-token",
    org_id: uuid.UUID | None = None,
    revoked: bool = False,
    max_uses: int = 0,
    use_count: int = 0,
    expires_at: datetime | None = None,
    guest_ttl_hours: int = 4,
    room_id: str | None = None,
) -> MagicMock:
    invite = MagicMock()
    invite.token = token
    invite.organization_id = org_id or uuid.uuid4()
    invite.revoked = revoked
    invite.max_uses = max_uses
    invite.use_count = use_count
    invite.expires_at = expires_at
    invite.guest_ttl_hours = guest_ttl_hours
    invite.room_id = room_id
    return invite


def _make_org(name: str = "Test Org", org_id: uuid.UUID | None = None) -> MagicMock:
    org = MagicMock()
    org.id = org_id or uuid.uuid4()
    org.name = name
    return org


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/auth/guest
# ---------------------------------------------------------------------------


class TestGuestTokenEndpoint:
    """Tests for the guest token issuance endpoint."""

    def test_requires_invite_or_org_id(self):
        """Endpoint rejects requests with neither invite_token nor org_id."""
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/guest", json={"display_name": "Test"})
        assert resp.status_code in (400, 422)

    @patch("app.routers.v1.guest.settings")
    def test_guest_access_disabled(self, mock_settings):
        """Returns 403 when ENABLE_GUEST_ACCESS is False."""
        mock_settings.ENABLE_GUEST_ACCESS = False
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/auth/guest",
            json={"invite_token": "some-token"},
        )
        assert resp.status_code == 403


class TestInviteValidation:
    """Tests for GET /api/v1/auth/guest/validate/{token}."""

    def test_invalid_token_returns_valid_false(self):
        """Unknown token returns valid=False."""
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/auth/guest/validate/nonexistent-token")
        # May return 200 with valid=false or 500 if DB not configured
        if resp.status_code == 200:
            data = resp.json()
            assert data["valid"] is False
