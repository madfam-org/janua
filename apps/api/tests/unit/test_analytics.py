"""
Unit tests for app.analytics (PostHog wrapper).

The wrapper is intentionally graceful: it must never raise, must no-op when
unconfigured, and must swallow exceptions from the underlying client. These
tests exercise both the no-op path and the configured path via a stubbed
client, without ever touching network or environment globally.
"""

from unittest.mock import MagicMock, patch

import pytest

import app.analytics as analytics


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset the module-level _client between tests."""
    saved = analytics._client
    analytics._client = None
    yield
    analytics._client = saved


# ---------------------------------------------------------------------------
# init_posthog
# ---------------------------------------------------------------------------


class TestInitPosthog:
    def test_init_no_api_key_is_noop(self, monkeypatch):
        monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
        analytics.init_posthog()
        assert analytics._client is None

    def test_init_empty_api_key_is_noop(self, monkeypatch):
        monkeypatch.setenv("POSTHOG_API_KEY", "")
        analytics.init_posthog()
        assert analytics._client is None

    def test_init_with_api_key_sets_client(self, monkeypatch):
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
        fake_posthog = MagicMock()
        with patch.dict("sys.modules", {"posthog": fake_posthog}):
            analytics.init_posthog()
        assert analytics._client is fake_posthog
        assert fake_posthog.api_key == "phc_test"

    def test_init_uses_default_host_when_unset(self, monkeypatch):
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
        monkeypatch.delenv("POSTHOG_HOST", raising=False)
        fake_posthog = MagicMock()
        with patch.dict("sys.modules", {"posthog": fake_posthog}):
            analytics.init_posthog()
        assert fake_posthog.host == "https://analytics.madfam.io"

    def test_init_respects_custom_host(self, monkeypatch):
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
        monkeypatch.setenv("POSTHOG_HOST", "https://example.test")
        fake_posthog = MagicMock()
        with patch.dict("sys.modules", {"posthog": fake_posthog}):
            analytics.init_posthog()
        assert fake_posthog.host == "https://example.test"

    def test_init_handles_missing_posthog_package(self, monkeypatch):
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
        # Ensure import fails by removing posthog from sys.modules and
        # forcing ImportError on import attempt.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "posthog":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            analytics.init_posthog()  # must not raise
        assert analytics._client is None


# ---------------------------------------------------------------------------
# track / identify / shutdown when client is None
# ---------------------------------------------------------------------------


class TestNoOpWhenUnconfigured:
    def test_track_noop(self):
        # No exception raised; no client to assert on
        analytics.track("user-1", "event")
        analytics.track("user-1", "event", {"k": "v"})

    def test_identify_noop(self):
        analytics.identify("user-1")
        analytics.identify("user-1", {"plan": "pro"})

    def test_shutdown_noop(self):
        analytics.shutdown()


# ---------------------------------------------------------------------------
# track / identify / shutdown with a configured client
# ---------------------------------------------------------------------------


class TestConfiguredClient:
    def test_track_calls_capture(self):
        client = MagicMock()
        analytics._client = client
        analytics.track("user-1", "event_x", {"plan": "pro"})
        client.capture.assert_called_once_with(
            "user-1", "event_x", properties={"plan": "pro"}
        )

    def test_track_defaults_properties_to_empty_dict(self):
        client = MagicMock()
        analytics._client = client
        analytics.track("user-1", "event_x")
        client.capture.assert_called_once_with("user-1", "event_x", properties={})

    def test_track_swallows_capture_exception(self):
        client = MagicMock()
        client.capture.side_effect = RuntimeError("network down")
        analytics._client = client
        # Must not raise - telemetry never breaks request paths
        analytics.track("user-1", "event_x")

    def test_identify_calls_underlying(self):
        client = MagicMock()
        analytics._client = client
        analytics.identify("user-1", {"role": "admin"})
        client.identify.assert_called_once_with(
            "user-1", properties={"role": "admin"}
        )

    def test_identify_defaults_properties_to_empty_dict(self):
        client = MagicMock()
        analytics._client = client
        analytics.identify("user-1")
        client.identify.assert_called_once_with("user-1", properties={})

    def test_identify_swallows_exception(self):
        client = MagicMock()
        client.identify.side_effect = RuntimeError("boom")
        analytics._client = client
        analytics.identify("user-1")  # must not raise

    def test_shutdown_flushes(self):
        client = MagicMock()
        analytics._client = client
        analytics.shutdown()
        client.shutdown.assert_called_once()

    def test_shutdown_swallows_exception(self):
        client = MagicMock()
        client.shutdown.side_effect = RuntimeError("teardown failed")
        analytics._client = client
        analytics.shutdown()  # must not raise
