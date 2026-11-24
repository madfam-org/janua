"""Shared devices as OAuth clients: kinds, templates, codes and boot identifiers.

A shared device (a shop-floor terminal that several people use) is a
confidential OAuth client of kind ``device``. It differs from an ordinary
service client in four ways, all defined here so that the enrolment routes
(`routers/v1/device_enrolment.py`) and the token endpoint
(`routers/v1/oauth_provider.py`) can never disagree:

1. **The device generates its own credential.** It draws 32 random bytes, sends
   them once at enrolment, and Janua keeps only a bcrypt hash. Nobody types or
   sees the secret, and Janua never returns one.
2. **The platform defines what a device may hold.** Its client is created from a
   template (``DEVICE_TEMPLATES``): a fixed audience, fixed scopes and fixed
   grants. Neither the device nor the administrator who approves it chooses a
   scope, and the token endpoint holds every request to the template, whatever
   the client row says.
3. **Its token is short.** ``TOKEN_TTL_SECONDS_BY_KIND`` gives each client kind
   its own access-token lifetime; a device's is fifteen minutes.
4. **It reports a boot identifier.** The device draws a random value at every
   start, keeps it in memory, and sends it with every token request. One device
   that restarts moves to a new value and never returns to an old one. A value
   that comes back after another one was seen means two holders of the same
   credential are taking turns (``observe_boot_id``). Janua then flags the
   device and tells the organization's administrators; a person decides what to
   do. Janua never disables a device on its own.

A device client is recognized by its ``client_id`` prefix (``jnd_``), which
only the enrolment path generates. The token endpoint therefore reads the device
table only for such a client and refuses one whose record it cannot read, while
every other client's token request is unchanged.

This module is pure (no database, no FastAPI) so any layer can import it.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Client kinds and their token lifetimes
# ---------------------------------------------------------------------------

#: An ordinary client_credentials client (a service in a cluster).
CLIENT_KIND_SERVICE = "service"
#: A shared device enrolled through the device enrolment routes.
CLIENT_KIND_DEVICE = "device"

#: Access-token lifetime of the client_credentials grant, per client kind.
#: An hour is the figure for a secret kept in a cluster secret store; a secret
#: on a device's removable storage gets a shorter window, and that window is
#: exactly how long a device that was disabled keeps a token it already holds.
TOKEN_TTL_SECONDS_BY_KIND: dict[str, int] = {
    CLIENT_KIND_SERVICE: 3600,
    CLIENT_KIND_DEVICE: 900,
}

#: Prefix of every device client's ``client_id``. Ordinary clients are
#: ``jnc_…``; registration refuses a pinned ``client_id`` with this prefix.
DEVICE_CLIENT_ID_PREFIX = "jnd_"
DEVICE_CLIENT_ID_RANDOM_BYTES = 24


def is_device_client_id(client_id: Optional[str]) -> bool:
    return bool(client_id) and str(client_id).startswith(DEVICE_CLIENT_ID_PREFIX)


def client_kind_for(client_id: Optional[str]) -> str:
    return CLIENT_KIND_DEVICE if is_device_client_id(client_id) else CLIENT_KIND_SERVICE


def token_ttl_seconds(kind: str) -> int:
    return TOKEN_TTL_SECONDS_BY_KIND[kind]


def generate_device_client_id() -> str:
    return f"{DEVICE_CLIENT_ID_PREFIX}{secrets.token_urlsafe(DEVICE_CLIENT_ID_RANDOM_BYTES)}"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceTemplate:
    """What every device enrolled from this template may hold. Platform-defined."""

    name: str
    audience: str
    scopes: frozenset[str]
    grant_types: frozenset[str]
    description: str


#: The scope of a shared shop-floor terminal's own token (audience
#: ``pravara-api``), named by Pravara's lane. Reserved like every
#: ``pravara-mes:<role>`` scope (``reserved_oauth_boundaries``, namespace rule)
#: and, more strictly, device-only (``DEVICE_ONLY_SCOPES`` below).
PRAVARA_TERMINAL_SCOPE = "pravara-mes:terminal"

#: The Nauta Edge shop-floor terminal: with a token of this template a terminal
#: may read what Pravara opens to terminals, deliver what it recorded and
#: report its own health. It never acts for a person.
NAUTA_EDGE_TERMINAL = DeviceTemplate(
    name="nauta-edge-terminal",
    audience="pravara-api",
    scopes=frozenset({PRAVARA_TERMINAL_SCOPE}),
    grant_types=frozenset({"client_credentials"}),
    description="Nauta Edge shop-floor terminal (shared device)",
)

DEVICE_TEMPLATES: dict[str, DeviceTemplate] = {NAUTA_EDGE_TERMINAL.name: NAUTA_EDGE_TERMINAL}
DEFAULT_DEVICE_TEMPLATE = NAUTA_EDGE_TERMINAL.name

#: Scopes that reach a client ONLY through an approved device enrolment. No
#: ordinary client path may write one onto a client, platform admins and the
#: internal key included (`schemas/oauth_client.py`,
#: `routers/v1/internal_oauth_client_scopes.py`), and the token endpoint never
#: grants one to a client that is not of kind ``device``
#: (`oauth_provider_scopes._client_allowed_scopes`), whatever its row holds.
DEVICE_ONLY_SCOPES: frozenset[str] = frozenset(
    scope for template in DEVICE_TEMPLATES.values() for scope in template.scopes
)
DEVICE_ONLY_SCOPE_DETAIL = "reaches a client only through device enrolment"


def device_only_scopes_in(scopes) -> list[str]:
    """The device-only scopes among ``scopes`` (sorted; empty when none)."""
    return sorted({str(scope).strip() for scope in (scopes or [])} & DEVICE_ONLY_SCOPES)


def get_device_template(name: Optional[str]) -> Optional[DeviceTemplate]:
    return DEVICE_TEMPLATES.get(name or "")


# ---------------------------------------------------------------------------
# Enrolment: the device's secret and the code it shows
# ---------------------------------------------------------------------------

DEVICE_SECRET_BYTES = 32
_HEX_SECRET = re.compile(r"^[0-9a-fA-F]{64}$")
_B64URL_SECRET = re.compile(r"^[A-Za-z0-9_-]{43}$")


def device_secret_is_valid(secret: Optional[str]) -> bool:
    """True when ``secret`` encodes exactly 32 bytes that are not all the same.

    Accepted encodings: 64 hexadecimal characters, or 43 characters of
    unpadded base64url. The secret is used as the client secret exactly as the
    device sends it, so the encoding it enrols with is the one it must keep.
    """
    if not isinstance(secret, str):
        return False
    raw: Optional[bytes] = None
    if _HEX_SECRET.match(secret):
        raw = bytes.fromhex(secret)
    elif _B64URL_SECRET.match(secret):
        try:
            raw = base64.urlsafe_b64decode(secret + "=")
        except (binascii.Error, ValueError):
            return False
    if raw is None or len(raw) != DEVICE_SECRET_BYTES:
        return False
    # A constant buffer (all zeros, say) is a device that never drew its bytes.
    return len(set(raw)) > 1


#: No vowels (no words) and no look-alike characters, as in Pravara's
#: edge-node enrolment. Eight letters: 20^8 ≈ 2.6 × 10^10 codes.
USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"
USER_CODE_LENGTH = 8


def generate_user_code() -> str:
    letters = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))
    return f"{letters[:4]}-{letters[4:]}"


def normalize_user_code(value: Optional[str]) -> Optional[str]:
    """``"bcdf ghjk"``, ``"BCDFGHJK"`` and ``"BCDF-GHJK"`` all read ``"BCDF-GHJK"``."""
    if not value:
        return None
    letters = re.sub(r"[\s-]", "", value).upper()
    if len(letters) != USER_CODE_LENGTH or any(c not in USER_CODE_ALPHABET for c in letters):
        return None
    return f"{letters[:4]}-{letters[4:]}"


# ---------------------------------------------------------------------------
# Boot identifiers
# ---------------------------------------------------------------------------

_BOOT_ID = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

#: How many distinct boot identifiers a device's record remembers. A device
#: restarts a few times a day at most; eight values cover two or three holders
#: taking turns over many restarts.
RECENT_BOOT_IDS_KEPT = 8
#: Stored digests are truncated SHA-256: 128 bits identify a random value
#: without keeping the value itself.
BOOT_ID_DIGEST_HEX_CHARS = 32


def boot_id_is_valid(boot_id: Optional[str]) -> bool:
    return isinstance(boot_id, str) and bool(_BOOT_ID.match(boot_id))


def boot_id_digest(boot_id: str) -> str:
    return hashlib.sha256(boot_id.encode("utf-8")).hexdigest()[:BOOT_ID_DIGEST_HEX_CHARS]


def parse_recent_boot_ids(stored: Optional[str]) -> list[str]:
    return [value for value in (stored or "").split() if value]


def serialize_recent_boot_ids(digests: list[str]) -> str:
    return " ".join(digests)


@dataclass(frozen=True)
class BootObservation:
    """The device's recent boot digests after one token request, and what it means."""

    recent: list[str]
    alternated: bool


def observe_boot_id(recent: list[str], boot_id: str) -> BootObservation:
    """Fold one token request's boot identifier into the device's recent list.

    ``recent`` is ordered oldest first; its last entry is the current boot.

    - Same as the current boot: nothing changes.
    - A value never seen (or forgotten): a restart. It becomes the current boot.
    - A value seen before that is NOT the current boot: an older boot came back.
      One device cannot do that, because each start draws a fresh value; two
      holders of one credential do it every time they take turns. That is an
      alternation. The value becomes current again.
    """
    digest = boot_id_digest(boot_id)
    if recent and recent[-1] == digest:
        return BootObservation(recent=list(recent), alternated=False)
    alternated = digest in recent
    updated = [value for value in recent if value != digest] + [digest]
    return BootObservation(recent=updated[-RECENT_BOOT_IDS_KEPT:], alternated=alternated)


__all__ = [
    "BOOT_ID_DIGEST_HEX_CHARS",
    "CLIENT_KIND_DEVICE",
    "CLIENT_KIND_SERVICE",
    "DEFAULT_DEVICE_TEMPLATE",
    "DEVICE_CLIENT_ID_PREFIX",
    "DEVICE_ONLY_SCOPES",
    "DEVICE_ONLY_SCOPE_DETAIL",
    "DEVICE_SECRET_BYTES",
    "DEVICE_TEMPLATES",
    "NAUTA_EDGE_TERMINAL",
    "PRAVARA_TERMINAL_SCOPE",
    "RECENT_BOOT_IDS_KEPT",
    "TOKEN_TTL_SECONDS_BY_KIND",
    "USER_CODE_ALPHABET",
    "BootObservation",
    "DeviceTemplate",
    "boot_id_digest",
    "boot_id_is_valid",
    "client_kind_for",
    "device_only_scopes_in",
    "device_secret_is_valid",
    "generate_device_client_id",
    "generate_user_code",
    "get_device_template",
    "is_device_client_id",
    "normalize_user_code",
    "observe_boot_id",
    "parse_recent_boot_ids",
    "serialize_recent_boot_ids",
    "token_ttl_seconds",
]
