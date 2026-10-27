"""Invite-only OAuth clients: the client's product entitlement IS the invitation.

WHY. Janua is the estate identity: any active account can sign in to any
client, and a hosted sign-in link creates the account it is asked for. That is
right for products that take sign-ups, and wrong for a closed beta (MADFAM CV,
2026-10-22): the owner invites each person, and nobody else may get in.

WHAT IT REUSES. No new table. Access to a product is already a Janua record —
the per-user ``user_entitlements`` row (written by Dhanam webhooks and admin
grants, projected into the ``madfam_entitled_products`` claim) plus org
inheritance (``services/entitlements_service.py``). A client becomes
invite-only by naming the product its people must be entitled to, in
``settings.INVITE_ONLY_CLIENTS`` (``client_id=product`` pairs). The invitation
is an ADMIN_GRANT row for that product; removing an invitee cancels the row
(``expires_at = now``), which keeps the audit history.

WHERE IT IS ENFORCED (see the tests in tests/unit/routers/test_invite_only_clients.py):

* ``/oauth/authorize`` refuses an authenticated person without the entitlement
  (a page in the request's language, or ``access_denied`` for ``prompt=none``);
* the token endpoint refuses the authorization-code AND refresh grants for
  them — the choke point every code path ends at, so a removed invitee loses
  the client at their next refresh;
* a sign-in link requested for the client (hosted form or ``POST /magic-link``)
  never creates an identity.

FAIL CLOSED. A listed client whose product is missing or malformed accepts
nobody; an entitlement read that fails reads as "no entitlement". Nothing here
can turn a misconfiguration into an open door.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

import structlog

from app.config import settings

logger = structlog.get_logger()

#: Product slugs as user_entitlements stores them (lowercase, short, no spaces).
PRODUCT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: The tier an operator invitation grants when the caller names none.
DEFAULT_INVITE_TIER = "beta"


def parse_invite_only_clients(raw: Optional[str]) -> Dict[str, str]:
    """``client_id -> product`` from the ``INVITE_ONLY_CLIENTS`` setting.

    A pair whose product is absent or malformed maps to ``""``, which no
    entitlement satisfies: the client is locked rather than silently opened.
    """
    policy: Dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        client_id, _, product = entry.partition("=")
        client_id, product = client_id.strip(), product.strip().lower()
        if not client_id:
            logger.error("invite_only_clients.entry_without_client_id")
            continue
        if not PRODUCT_SLUG.fullmatch(product):
            logger.error(
                "invite_only_clients.entry_without_product_locks_client",
                client_id=client_id,
            )
            product = ""
        policy[client_id] = product
    return policy


def invite_only_product(client_id: Optional[str]) -> Optional[str]:
    """The product a client's people must be entitled to; None when it is open.

    ``""`` means invite-only but misconfigured: nobody qualifies.
    """
    if not client_id:
        return None
    return parse_invite_only_clients(settings.INVITE_ONLY_CLIENTS).get(client_id)


def is_invite_only(client_id: Optional[str]) -> bool:
    return invite_only_product(client_id) is not None


async def has_invited_access(user: Any, client_id: Optional[str], db: Any) -> bool:
    """Whether ``user`` may sign in to ``client_id``. True for every open client."""
    product = invite_only_product(client_id)
    if product is None:
        return True
    if not product or user is None:
        return False
    from app.services.entitlements_service import get_user_entitlements

    try:
        entitlements = await get_user_entitlements(user, db)
    except Exception as exc:  # fail closed: an unreadable grant is no grant
        logger.error(
            "invite_only_clients.entitlement_read_failed",
            client_id=client_id,
            user_id=str(getattr(user, "id", "")),
            error=type(exc).__name__,
        )
        return False
    return any(entitlement.product == product for entitlement in entitlements)
