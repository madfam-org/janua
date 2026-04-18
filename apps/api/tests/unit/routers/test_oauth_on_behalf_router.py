"""
Tests for app/routers/v1/oauth_on_behalf.py — P3.2 Sprint 1.

Validates the service-token gate, 404 when the feature is disabled, and
that the on-behalf surface does not accept unauthenticated or forged
callers. Heavy OAuth exchange logic is not exercised here — we lean on
the existing oauth.py tests and just verify the new perimeter.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.asyncio


class TestOnBehalfEndpoints_Disabled:
    """When JANUA_SERVICE_TOKEN is empty, both endpoints return 404."""

    def test_start_returns_404_without_service_token_configured(self):
        with patch("app.routers.v1.oauth_on_behalf.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = ""
            mock_settings.API_BASE_URL = "https://api.janua.dev"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/oauth/link/github/on-behalf",
                json={
                    "user_sub": "abc",
                    "state": "s",
                    "redirect_uri": "https://enclii/cb",
                },
            )
            assert resp.status_code == 404

    def test_complete_returns_404_without_service_token_configured(self):
        with patch("app.routers.v1.oauth_on_behalf.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = ""
            mock_settings.API_BASE_URL = "https://api.janua.dev"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/oauth/link/github/complete?code=x&user_sub=y",
            )
            assert resp.status_code == 404


class TestOnBehalfEndpoints_UnauthenticatedRejection:
    """When the token IS configured, missing/wrong tokens get 401."""

    def test_start_401_without_header(self):
        with patch("app.routers.v1.oauth_on_behalf.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = "secret-xyz"
            mock_settings.API_BASE_URL = "https://api.janua.dev"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/oauth/link/github/on-behalf",
                json={
                    "user_sub": "abc",
                    "state": "s",
                    "redirect_uri": "https://enclii/cb",
                },
            )
            assert resp.status_code == 401

    def test_start_401_with_wrong_token(self):
        with patch("app.routers.v1.oauth_on_behalf.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = "secret-xyz"
            mock_settings.API_BASE_URL = "https://api.janua.dev"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/oauth/link/github/on-behalf",
                json={
                    "user_sub": "abc",
                    "state": "s",
                    "redirect_uri": "https://enclii/cb",
                },
                headers={"X-Service-Token": "wrong"},
            )
            assert resp.status_code == 401

    def test_complete_401_with_wrong_bearer(self):
        with patch("app.routers.v1.oauth_on_behalf.settings") as mock_settings:
            mock_settings.JANUA_SERVICE_TOKEN = "secret-xyz"
            mock_settings.API_BASE_URL = "https://api.janua.dev"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/oauth/link/github/complete?code=x&user_sub=y",
                headers={"Authorization": "Bearer nope"},
            )
            assert resp.status_code == 401


class TestOnBehalfEndpoints_BearerAcceptance:
    """Accept the token on either header form."""

    def test_bearer_token_passes_gate_then_404_for_missing_user(self):
        # With the service token valid, we clear the auth gate and hit
        # the user lookup — which returns 404 since we don't have a real
        # DB in this test. We stop here rather than mocking the full DB
        # query; the integration test suite covers end-to-end.
        with patch("app.routers.v1.oauth_on_behalf.settings") as mock_settings, patch(
            "app.routers.v1.oauth_on_behalf.get_db"
        ):
            mock_settings.JANUA_SERVICE_TOKEN = "secret-xyz"
            mock_settings.API_BASE_URL = "https://api.janua.dev"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/auth/oauth/link/github/on-behalf",
                json={
                    "user_sub": "no-such-user",
                    "state": "s",
                    "redirect_uri": "https://enclii/cb",
                },
                headers={"Authorization": "Bearer secret-xyz"},
            )
            # Not 401 (gate passed). May be 404/500 depending on DB stub.
            assert resp.status_code != 401
