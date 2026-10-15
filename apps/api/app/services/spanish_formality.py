"""The person's Spanish register (`tú` / `usted`): the one place it is written and claimed.

`users.spanish_formality` (migration 012) has existed since the email formality
work, and `email_i18n.resolve_formality_for_request` already ranks it above the
requesting product's voice. But nothing in janua could WRITE it, so it was NULL
for everyone and tier 2 of that precedence never fired. The directive this
module serves: ask each person once — in janua or inside a product's own
onboarding — and honour the answer everywhere.

Two writers, one rule
---------------------
* The person themself, through `PATCH /api/v1/users/me`.
* A product relaying the answer the person gave inside it, through
  `POST /api/v1/internal/users/spanish-formality`.

Both go through `record_spanish_formality`, so they cannot drift on validation
or on what the audit row says.

NULL is "never asked", and an answer is kept
--------------------------------------------
Neither writer can clear the column. NULL is not a third register: it is the
absence of an answer, and resolves to the product's voice and then to `usted`.
Letting a write put it back would make "this person told us `tú`" silently
revert to a product default — the thing the column exists to prevent. A person
who changes their mind sends the other register, which is recorded as a change.

The claim
---------
`spanish_formality` rides tokens (ID token, session and OIDC access tokens)
ONLY when the person has answered, and is absent otherwise — the same shape
rule as `is_service_account` (see `service_principal.py`): every token of a
person who has not answered is byte-identical to what it was before this
existed. Absence means "not asked yet"; a product that wants an answer asks,
then relays it. The userinfo endpoint reports it under the profile scope as
`null` until it is answered.

A token carries the value it was minted with. A change reaches access tokens at
the next refresh; `/oauth/userinfo` and `/users/me` read the row live.

Audit
-----
Every change stages a direct `audit_logs` row on the caller's session (the
`oauth_clients` / `internal_oauth_client_scopes` construction), so the value
and its record commit in ONE transaction. `AuditLogger` is not used: its
hash-chain write path references `audit_logs` columns that the model does not
have, so its entries never reach the table. A write that changes nothing (the
same register again) writes no row, so retries do not pad the trail.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any, Optional, get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.services.audit_logger import AuditEventType
from app.services.email_i18n import SpanishFormality, normalize_formality

# `SpanishFormality` (re-exported) is the strict write vocabulary: "tu" | "usted",
# no accents, no case folding, no `vosotros` (see email_i18n for why that
# register is not coming). It lives in email_i18n next to SPANISH_FORMALITIES.

#: Token / userinfo claim key. Stamped only when the person has answered.
SPANISH_FORMALITY_CLAIM = "spanish_formality"

#: `audit_logs.action` for a change. Same string as `AuditEventType.USER_UPDATE`,
#: with `details.field` naming what changed.
AUDIT_ACTION = AuditEventType.USER_UPDATE.value

#: `details.field` on the audit row.
AUDIT_FIELD = "spanish_formality"

#: `details.source` values: who gave janua the answer.
SOURCE_SELF = "self"
SOURCE_PRODUCT = "product"

#: The refusal text for a NULL write, shared by both writers.
CLEARING_REFUSED_DETAIL = (
    "spanish_formality cannot be cleared: NULL means the person has never been "
    "asked, and an answer is kept. Send 'tu' or 'usted', or omit the field."
)


def stored_formality(user: Any) -> Optional[str]:
    """The person's stored register, normalized, or None when they have not answered.

    Tolerant of objects that predate the column (and of test doubles that omit
    it): a missing or unrecognized value reads as "not answered".
    """
    if user is None:
        return None
    return normalize_formality(getattr(user, "spanish_formality", None))


def spanish_formality_claims(user: Any) -> dict[str, str]:
    """Claims to merge into a token payload for `user`.

    `{"spanish_formality": "tu" | "usted"}` once the person has answered, and an
    EMPTY dict before that, so an unanswered person's token gains no key at all.
    """
    value = stored_formality(user)
    return {SPANISH_FORMALITY_CLAIM: value} if value else {}


@dataclass(frozen=True)
class FormalityChange:
    """What a write did. `previous` is the raw stored value (None = never asked)."""

    previous: Optional[str]
    current: str
    changed: bool


def _audit_ip(raw: Optional[str]) -> Optional[str]:
    """An address the INET column will accept, or None.

    `request.client.host` is not always an IP literal (test clients, some proxy
    setups); a non-address would fail the Postgres INET cast and roll back the
    write it was meant to record.
    """
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def record_spanish_formality(
    db: AsyncSession,
    user: Any,
    value: Any,
    *,
    actor_user_id: Any,
    actor: str,
    actor_type: str,
    source: str,
    via: str,
    source_app: Optional[str] = None,
    organization_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> FormalityChange:
    """Set `user.spanish_formality` and stage its audit row. Does NOT commit.

    The caller commits, so the value and its audit row land together or not at
    all. Idempotent: writing the register already stored changes nothing and
    stages no row.

    Raises ValueError for anything but `"tu"` / `"usted"`, None included — the
    request schemas already refuse those with a 422, and this is the backstop
    for any future caller that skips them.
    """
    if value not in get_args(SpanishFormality):
        raise ValueError(CLEARING_REFUSED_DETAIL if value is None else "unsupported register")

    previous = getattr(user, "spanish_formality", None)
    if previous == value:
        return FormalityChange(previous=previous, current=value, changed=False)

    user.spanish_formality = value

    details: dict[str, Any] = {
        "field": AUDIT_FIELD,
        "old": previous,
        "new": value,
        "source": source,
        "actor": actor,
        "actor_type": actor_type,
        "via": via,
    }
    if source_app is not None:
        details["source_app"] = source_app
    if organization_id is not None:
        details["organization_id"] = organization_id

    db.add(
        AuditLog(
            user_id=actor_user_id,
            action=AUDIT_ACTION,
            resource_type="user",
            resource_id=user.id,
            details=details,
            ip_address=_audit_ip(ip_address),
            user_agent=user_agent,
        )
    )
    return FormalityChange(previous=previous, current=value, changed=True)


__all__ = [
    "AUDIT_ACTION",
    "AUDIT_FIELD",
    "CLEARING_REFUSED_DETAIL",
    "SOURCE_PRODUCT",
    "SOURCE_SELF",
    "SPANISH_FORMALITY_CLAIM",
    "FormalityChange",
    "SpanishFormality",
    "record_spanish_formality",
    "spanish_formality_claims",
    "stored_formality",
]
