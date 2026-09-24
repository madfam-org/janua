"""Purpose-scoped provider consent — the allowlist of delegable purposes.

A *purpose* names one reason a downstream service may borrow a user's linked
provider credential. Each purpose pins three things and nothing else:

- ``provider``: the only OAuth provider the purpose applies to;
- ``additional_scopes``: the provider scopes requested on top of the
  provider's sign-in scopes when the user links for this purpose;
- ``allowed_service_clients``: the Janua ``client_credentials`` clients, by
  registration **name** (see ``docs/service-tokens.md``), that may request a
  delegated token for this purpose.

The registry is code, not configuration, on purpose: widening who may borrow a
user's provider token is a reviewed change, never a runtime toggle. Anything
not listed here is refused — at link time and at delegation time.

See ``docs/service-tokens.md`` ("Purpose-scoped provider consent").
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

#: Audience a service token must carry to call ``POST /connections/{id}/token``.
#: Mirrors the ``janua-email`` convention: ``janua-<surface>``.
CONNECTIONS_AUDIENCE = "janua-connections"

#: Scope a service token must carry to request a delegated provider token.
CONNECTIONS_DELEGATE_SCOPE = "connections:delegate"

#: ``account_metadata`` key under which purpose grants are recorded on a
#: ``ConnectedAccount`` row (existing JSON column; no migration).
PURPOSES_METADATA_KEY = "purposes"

PURPOSE_STATUS_GRANTED = "granted"
PURPOSE_STATUS_REVOKED = "revoked"


@dataclass(frozen=True)
class ConsentPurpose:
    id: str
    provider: str
    additional_scopes: tuple[str, ...]
    allowed_service_clients: frozenset[str]
    description: str = ""


_PURPOSES: dict[str, ConsentPurpose] = {
    "creator-census.youtube": ConsentPurpose(
        id="creator-census.youtube",
        provider="google",
        additional_scopes=(
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
        ),
        allowed_service_clients=frozenset({"creator-census"}),
        description="Read the creator's own YouTube channel statistics and analytics.",
    ),
}

PURPOSES: Mapping[str, ConsentPurpose] = MappingProxyType(_PURPOSES)


def get_purpose(purpose_id: Optional[str]) -> Optional[ConsentPurpose]:
    """Return the registered purpose, or None for anything unknown."""
    if not purpose_id:
        return None
    return PURPOSES.get(purpose_id)


__all__ = [
    "CONNECTIONS_AUDIENCE",
    "CONNECTIONS_DELEGATE_SCOPE",
    "PURPOSES",
    "PURPOSES_METADATA_KEY",
    "PURPOSE_STATUS_GRANTED",
    "PURPOSE_STATUS_REVOKED",
    "ConsentPurpose",
    "get_purpose",
]
