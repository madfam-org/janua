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

Purposes are immutable once shipped (purpose limitation). A registered
purpose's ``provider`` and ``additional_scopes`` never change after it ships,
because consent was given to exactly that. To need more scopes, register a
NEW purpose id (for example ``creator-census.youtube-analytics``), which users
grant separately. Widening a purpose in place would turn every existing grant
into ``purpose_not_granted`` (``has_active_purpose_grant`` requires every
scope). Consumers read that reason as the user's withdrawal and delete data.
``SHIPPED_PURPOSE_FINGERPRINTS`` records each shipped purpose's fingerprint,
and a unit test fails when a registered purpose no longer matches it.
Client allowlists and subject audiences are not part of the fingerprint: they
decide *who* may act on a grant, not *what* the user consented to.

See ``docs/service-tokens.md`` ("Purpose-scoped provider consent").
"""

from __future__ import annotations

import hashlib
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
        # Minimum scope: channel data only. SHIPPED: provider and scopes are
        # frozen (see SHIPPED_PURPOSE_FINGERPRINTS). YouTube Analytics would be
        # a NEW purpose id (e.g. creator-census.youtube-analytics), never a
        # scope added here.
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


def purpose_fingerprint(provider: str, scopes) -> str:
    """sha256 over the provider and the sorted scope set: what consent covers."""
    material = provider + "\n" + "\n".join(sorted(set(scopes)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


#: Fingerprints of shipped purposes, recorded when each purpose shipped.
#: APPEND-ONLY. Never edit or delete an entry: a shipped purpose's provider and
#: scopes are immutable. Needing different scopes means registering a new
#: purpose id and appending its fingerprint here in the same reviewed change.
SHIPPED_PURPOSE_FINGERPRINTS: Mapping[str, str] = MappingProxyType(
    {
        # google + {youtube.readonly}
        "creator-census.youtube": (
            "f4068b399021f9d2bd83727c11fa51cbae14654a90be1d410823858419351866"
        ),
    }
)


def purpose_drift() -> list[str]:
    """Human-readable violations of purpose immutability; empty when sound.

    Every registered purpose must have a recorded fingerprint, and it must
    still match. Used by the registry unit test; cheap enough to call anywhere.
    """
    problems: list[str] = []
    for purpose_id, purpose in PURPOSES.items():
        recorded = SHIPPED_PURPOSE_FINGERPRINTS.get(purpose_id)
        current = purpose_fingerprint(purpose.provider, purpose.additional_scopes)
        if recorded is None:
            problems.append(
                f"Purpose {purpose_id!r} has no recorded fingerprint. When it ships, "
                f"append {purpose_id!r}: {current!r} to SHIPPED_PURPOSE_FINGERPRINTS."
            )
        elif recorded != current:
            problems.append(
                f"Purpose {purpose_id!r} changed its provider or scopes after shipping "
                f"(recorded {recorded[:12]}..., now {current[:12]}...). Shipped purposes "
                "are immutable: revert this change and register a NEW purpose id for the "
                "new scope set instead. Widening in place turns every existing grant "
                "into purpose_not_granted, which consumers treat as the user's "
                "withdrawal and act on by deleting data."
            )
    for purpose_id in SHIPPED_PURPOSE_FINGERPRINTS:
        if purpose_id not in PURPOSES:
            problems.append(
                f"Shipped purpose {purpose_id!r} was removed from the registry. Retiring "
                "a purpose is a deliberate, coordinated change with its consumers; "
                "keep the fingerprint entry either way (it is append-only)."
            )
    return problems


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
    "SHIPPED_PURPOSE_FINGERPRINTS",
    "ConsentPurpose",
    "get_purpose",
    "purpose_drift",
    "purpose_fingerprint",
]
