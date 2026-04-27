"""PostHog analytics client -- graceful no-op when API key is empty."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_client: Optional[object] = None


def init_posthog() -> None:
    """Initialize PostHog client. No-op if POSTHOG_API_KEY is not set."""
    global _client
    api_key = os.environ.get("POSTHOG_API_KEY", "")
    if not api_key:
        return
    try:
        import posthog
        posthog.api_key = api_key
        posthog.host = os.environ.get("POSTHOG_HOST", "https://analytics.madfam.io")
        _client = posthog
    except ImportError:
        # posthog package not installed -- analytics permanently disabled.
        logger.debug("posthog package not installed; analytics disabled")


def track(distinct_id: str, event: str, properties: Optional[dict] = None) -> None:
    """Capture an event. No-op if PostHog is not initialized."""
    if _client is None:
        return
    try:
        _client.capture(distinct_id, event, properties=properties or {})
    except Exception:
        # Telemetry must never break a request path. Log at debug to avoid
        # log spam when the analytics endpoint is degraded.
        logger.debug("posthog capture failed", exc_info=True)


def identify(distinct_id: str, properties: Optional[dict] = None) -> None:
    """Identify a user. No-op if PostHog is not initialized."""
    if _client is None:
        return
    try:
        _client.identify(distinct_id, properties=properties or {})
    except Exception:
        # Telemetry must never break a request path. Log at debug to avoid
        # log spam when the analytics endpoint is degraded.
        logger.debug("posthog identify failed", exc_info=True)


def shutdown() -> None:
    """Flush pending events."""
    if _client is None:
        return
    try:
        _client.shutdown()
    except Exception:
        # Shutdown is best-effort during process exit; failures are not actionable.
        logger.debug("posthog shutdown failed", exc_info=True)
