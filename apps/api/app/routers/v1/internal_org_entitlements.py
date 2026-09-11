"""Internal by-org entitlement read — GET /api/v1/internal/orgs/{org_id}/entitlements.

WHAT THIS ANSWERS, AND WHY IT IS NOT `/me/entitlements`
-------------------------------------------------------
`GET /api/v1/me/entitlements` answers "what can the CALLING USER reach", scoped
to ``get_current_user``: it reads the bearer's per-user grants, the bearer's
primary-org inheritance, and admin bootstrap. That is the right question for a
client reading their OWN workspace, and the wrong one for a MADFAM advisor
viewing a client's workspace — the advisor's own token names the advisor's
(empty/MADFAM) entitlements, not the client's, so a hub keying off it renders
every client product slice as "not entitled".

This endpoint answers a DIFFERENT question: "what does THIS ORGANIZATION grant",
independent of any viewer, read straight from the org's ``product_tiers``. Nauta
calls it with the VIEWED WORKSPACE'S janua org id when the viewer is an advisor,
so the tiles resolve to the client's real entitlements rather than the advisor's.

Response is the SAME shape ``/me/entitlements`` returns (``products`` +
``claim_string_form``), so a caller that already parses one parses the other with
no new contract — see ``routers/v1/me.py`` and the ``entitlements_to_claim``
rendering both share.

Auth
----
``verify_internal_api_key`` — the same ``X-Internal-API-Key`` dependency as
``internal_users.py``, ``internal_app_roles.py`` and ``internal_capability_links.py``,
and the same trust janua already extends to sibling apps. This surface must NOT
be reachable with a user's own access token: an org's entitlements are a fact
about the org, and answering it for any bearer who names an org id would let a
client enumerate another org's product mix. A service credential is the correct
authority, exactly as the org-scoped writes (`set_org_product_tier`) are not on
the user-scoped surface either.

What this does NOT do
---------------------
No per-user layer and no admin bootstrap: neither is a property of the
organization, and folding either in would answer a different question than the
one the advisor case needs. It is a pure read — no write, no grant, no audit
mutation — so it carries no side effect an operator would need to reverse.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import verify_internal_api_key
from app.routers.v1.me import EntitlementsResponse, _to_response
from app.services.entitlements_service import get_org_entitlements

logger = structlog.get_logger()

router = APIRouter(prefix="/orgs", tags=["internal"])


@router.get(
    "/{org_id}/entitlements",
    response_model=EntitlementsResponse,
)
async def org_entitlements(
    org_id: str,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> EntitlementsResponse:
    """
    Active product entitlements an ORGANIZATION grants, by org id.

    Mirrors the `/me/entitlements` shape: `products` is the per-slug rows and
    `claim_string_form` is the same data as the JWT claim (`["<slug>:<tier>"]`).
    Sourced from the org's `product_tiers`; every row is `inherited` because
    that is what an org tier is. An org with no `product_tiers` returns an empty
    set — "this org grants nothing", not "unknown".
    """
    try:
        parsed_org_id = UUID(org_id)
    except (ValueError, TypeError):
        # A malformed id is a client error, not a 500 and not an empty set: an
        # empty set would read as "this org grants nothing", which is a claim we
        # cannot make about an id we could not even parse.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="org_id is not a valid UUID",
        )

    entitlements = await get_org_entitlements(parsed_org_id, db)
    return EntitlementsResponse(
        products=[_to_response(e) for e in entitlements],
        claim_string_form=[e.to_claim() for e in entitlements],
    )


__all__ = ["router"]
