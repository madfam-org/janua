"""Purpose-scoped provider consent — the allowlist of delegable purposes.

A *purpose* names one reason a downstream service may borrow a user's linked
provider credential. Each purpose pins:

- ``provider``: the only OAuth provider the purpose applies to;
- ``additional_scopes``: the provider scopes requested on top of the
  provider's sign-in scopes when the user links for this purpose. Keep it to
  the minimum the service uses today;
- ``exchange_clients``: Janua ``client_credentials`` clients, by registration
  **name** (see ``docs/service-tokens.md``), that may act in a user-bound
  token exchange (``POST /connections/token-exchange``). The user's own access
  token is the subject, so the service can only borrow tokens for users whose
  requests it is handling;
- ``offline_clients``: clients that may use header-based, user-absent
  delegation (``POST /connections/{id}/token`` + ``X-Acting-User-Id``) for
  background re-verification. Keep this list to credentials that live only in
  jobs with no ingress: this path trusts the asserted user id;
- ``allowed_subject_audiences``: audiences a user's own Janua access token may
  carry to be accepted as the exchange subject.

Both client lists need scope ``connections:delegate``; a client in one list is
refused on the other path. Every path still requires the user's active grant.

The registry is code, not configuration, on purpose: widening who may borrow a
user's provider token, or what it can do, is a reviewed change, never a
runtime toggle. Anything not listed here is refused.

Widening a purpose's scopes later: add the scope here in a reviewed change and
extend the provider's app verification to cover it. Existing grants then no
longer cover the purpose (``has_active_purpose_grant`` requires every scope),
so exchanges answer ``purpose_not_granted`` until each user links again with
``?purpose=`` (Google incremental consent). Narrowing takes effect at once.

See ``docs/service-tokens.md`` ("Purpose-scoped provider consent").
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

#: Audience a service token must carry to call ``POST /connections/{id}/token``.
#: Mirrors the ``janua-email`` convention: ``janua-<surface>``.
CONNECTIONS_AUDIENCE = "janua-connections"

#: Scope a service token must carry to request any delegated provider token.
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
    exchange_clients: frozenset[str]
    offline_clients: frozenset[str]
    allowed_subject_audiences: frozenset[str]
    description: str = ""


_PURPOSES: dict[str, ConsentPurpose] = {
    "creator-census.youtube": ConsentPurpose(
        id="creator-census.youtube",
        provider="google",
        # Minimum scope: channel statistics only. YouTube Analytics
        # (yt-analytics.readonly) is deliberately NOT requested until a
        # feature uses it; see "Widening a purpose's scopes" above.
        additional_scopes=("https://www.googleapis.com/auth/youtube.readonly",),
        # The census API pod: user-bound exchange only.
        exchange_clients=frozenset({"creator-census"}),
        # The census re-verification CronJob (no ingress): offline only.
        offline_clients=frozenset({"creator-census-reauth"}),
        allowed_subject_audiences=frozenset({"creator-census-api"}),
        description="Read the creator's own YouTube channel data.",
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
