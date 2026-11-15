"""Per-client privacy notices on the hosted sign-in page (``CLIENT_PRIVACY_NOTICES``).

A product that collects personal data through Janua's hosted login (MADFAM CV,
since its 2026-11-15 notice) must make its own privacy notice available at the
moment the person hands their data over. Janua's pages are shared by every
client, so the notice is per client: ``client_id=https://…`` pairs in one
setting, read the same way as ``INVITE_ONLY_CLIENTS``.

Fail closed in the safe direction: a malformed entry, or a URL that is not
``https`` with a host, is dropped and logged, so the page renders exactly as it
did without the setting. Nothing here reads the database or the network.
"""

from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urlsplit

import structlog

from app.config import settings

logger = structlog.get_logger()

#: A URL longer than this is not a notice address worth rendering.
MAX_NOTICE_URL_CHARS = 512


def _valid_notice_url(url: str) -> bool:
    if not url or len(url) > MAX_NOTICE_URL_CHARS:
        return False
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and bool(parts.hostname)
        and not parts.username
        and not parts.password
        and "\\" not in url
        and not any(ch.isspace() for ch in url)
    )


def parse_client_privacy_notices(raw: Optional[str]) -> Dict[str, str]:
    """``client_id -> notice URL`` from the setting; invalid pairs are dropped."""
    notices: Dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        client_id, _, url = entry.partition("=")
        client_id, url = client_id.strip(), url.strip()
        if not client_id or not _valid_notice_url(url):
            logger.error(
                "client_privacy_notices.invalid_entry_ignored", client_id=client_id or None
            )
            continue
        notices[client_id] = url
    return notices


def client_privacy_notice_url(client_id: Optional[str]) -> Optional[str]:
    """The privacy notice a client's hosted login links to, or None."""
    if not client_id:
        return None
    return parse_client_privacy_notices(settings.CLIENT_PRIVACY_NOTICES).get(client_id)
