"""Tests for Coupler connections API (P1)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.asyncio


class TestConnectionsDelegation_Disabled:
    def test_token_returns_404_without_service_token(self):
        with patch("app.routers.v1.connections.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = ""
            client = TestClient(app)
            resp = client.post(
                "/api/v1/connections/00000000-0000-4000-8000-000000000099/token",
                json={"purpose": "tool_execute", "ttl_seconds": 300},
                headers={"X-Acting-User-Id": "00000000-0000-4000-8000-000000000001"},
            )
            assert resp.status_code == 404


class TestConnectionsDelegation_Auth:
    def test_token_401_without_service_header(self):
        with patch("app.routers.v1.connections.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = "secret-xyz"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/connections/00000000-0000-4000-8000-000000000099/token",
                json={"purpose": "tool_execute", "ttl_seconds": 300},
                headers={"X-Acting-User-Id": "00000000-0000-4000-8000-000000000001"},
            )
            assert resp.status_code == 401

    def test_token_401_with_wrong_service_token(self):
        with patch("app.routers.v1.connections.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = "secret-xyz"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/connections/00000000-0000-4000-8000-000000000099/token",
                json={"purpose": "tool_execute", "ttl_seconds": 300},
                headers={
                    "X-Service-Token": "wrong",
                    "X-Acting-User-Id": "00000000-0000-4000-8000-000000000001",
                },
            )
            assert resp.status_code == 401


class TestConnectionsList_Unauthenticated:
    def test_list_requires_user_jwt(self):
        client = TestClient(app)
        resp = client.get("/api/v1/connections")
        assert resp.status_code in (401, 403)
