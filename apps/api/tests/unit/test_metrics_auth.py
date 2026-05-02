"""
Tests for the /metrics* auth guard added to mitigate the public-surfaces
audit finding (Prometheus exposition + per-endpoint latency profile reachable
on api.janua.dev without authentication).

These tests exercise `app.main._require_metrics_token` directly so they do
not depend on the full FastAPI app graph (which pulls in DB, Redis, Vault).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException


def _make_request(headers: dict | None = None):
    """Build a minimal Starlette Request wrapper exposing only `.headers`."""

    class _Req:
        def __init__(self, hdrs: dict | None):
            # Starlette headers are case-insensitive; mimic that with a dict
            # whose keys are lowercased for the .get() calls in the guard.
            self.headers = {k.lower(): v for k, v in (hdrs or {}).items()}

    return _Req(headers)


@pytest.fixture
def guard():
    # Import lazily so the test file doesn't fail collection if a peer
    # module breaks; this keeps the regression check tight.
    from app.main import _require_metrics_token

    return _require_metrics_token


def test_guard_404_when_token_unset_in_production(guard):
    with patch.dict(os.environ, {"METRICS_TOKEN": ""}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "production"
            with pytest.raises(HTTPException) as exc:
                guard(_make_request())
            assert exc.value.status_code == 404


def test_guard_open_in_development_when_token_unset(guard):
    with patch.dict(os.environ, {"METRICS_TOKEN": ""}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "development"
            # Should NOT raise.
            assert guard(_make_request()) is None


def test_guard_404_when_token_set_but_no_authorization_header(guard):
    with patch.dict(os.environ, {"METRICS_TOKEN": "shh-secret"}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "production"
            with pytest.raises(HTTPException) as exc:
                guard(_make_request())
            assert exc.value.status_code == 404


def test_guard_404_when_token_set_but_authorization_is_wrong_scheme(guard):
    with patch.dict(os.environ, {"METRICS_TOKEN": "shh-secret"}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "production"
            req = _make_request({"authorization": "Basic Zm9vOmJhcg=="})
            with pytest.raises(HTTPException) as exc:
                guard(req)
            assert exc.value.status_code == 404


def test_guard_404_when_bearer_token_does_not_match(guard):
    with patch.dict(os.environ, {"METRICS_TOKEN": "shh-secret"}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "production"
            req = _make_request({"authorization": "Bearer wrong-token"})
            with pytest.raises(HTTPException) as exc:
                guard(req)
            assert exc.value.status_code == 404


def test_guard_passes_when_bearer_token_matches(guard):
    with patch.dict(os.environ, {"METRICS_TOKEN": "shh-secret"}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "production"
            req = _make_request({"authorization": "Bearer shh-secret"})
            # Should NOT raise.
            assert guard(req) is None


def test_guard_uses_constant_time_compare(guard):
    """
    We compare with secrets.compare_digest. A near-miss must still 404, not
    leak timing/length info.
    """
    with patch.dict(os.environ, {"METRICS_TOKEN": "shh-secret"}, clear=False):
        with patch("app.main.settings") as st:
            st.ENVIRONMENT = "production"
            req = _make_request({"authorization": "Bearer shh-secre"})  # off by one
            with pytest.raises(HTTPException) as exc:
                guard(req)
            assert exc.value.status_code == 404
