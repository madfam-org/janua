"""
/api/v1/me/* — caller-scoped endpoints that don't fit under /auth.

Today this exposes one endpoint, `GET /me/entitlements`, which is the
authoritative read of what products the calling user can access at what
tier under their current plan. The Atrium UI hits this on mount to gate
catalog tiles before any iframe is rendered.

The same data is also embedded into JWTs as the `madfam_entitled_products`
claim — clients that already trust the JWT can skip this call. The endpoint
exists so:

  1. Long-lived sessions can re-poll without forcing a token refresh.
  2. Server-side renderers (Next.js) that don't have the JWT can ask Janua
     directly via the user's session cookie.
  3. The shape decouples Atrium UX from JWT churn — adding fields here
     does not invalidate existing JWTs.

See ADR 2026-05-04-selva-unified-sso (internal-devops/decisions/) for
design rationale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.entitlements_service import (
    Entitlement,
    get_user_entitlements,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/me", tags=["Me"])


class EntitlementResponse(BaseModel):
    """One entitlement row in the `/me/entitlements` response."""

    slug: str = Field(..., description="Product slug (e.g. 'karafiel', 'dhanam').")
    tier: str = Field(..., description="Tier within that product (e.g. 'pro', 'admin').")
    expires_at: Optional[datetime] = Field(
        None,
        description=(
            "When the entitlement ends. NULL = no expiry (admin grants typically). "
            "If set in the past the entitlement is treated as inactive and would "
            "not appear here."
        ),
    )
    source: str = Field(
        ...,
        description=(
            "How this entitlement was granted. One of: 'dhanam_subscription', "
            "'admin_grant', 'inherited'."
        ),
    )


class EntitlementsResponse(BaseModel):
    """
    Wrapper for `/me/entitlements`.

    `claim_string_form` is the same data formatted as the JWT claim shape
    (`["<product>:<tier>", ...]`). Clients that already use the JWT claim
    can compare `claim_string_form` to it for equality without re-parsing
    individual rows.
    """

    products: list[EntitlementResponse]
    claim_string_form: list[str]


def _to_response(entry: Entitlement) -> EntitlementResponse:
    return EntitlementResponse(
        slug=entry.product,
        tier=entry.tier,
        expires_at=entry.expires_at,
        source=entry.source.value,
    )


@router.get("/entitlements", response_model=EntitlementsResponse)
async def my_entitlements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntitlementsResponse:
    """
    Active product entitlements for the calling user.

    Mirrors the `madfam_entitled_products` JWT claim. Returns active rows
    only (`expires_at` in the future or unset). Cancelled / past-expiry
    rows are filtered out.
    """
    entitlements = await get_user_entitlements(current_user, db)
    return EntitlementsResponse(
        products=[_to_response(e) for e in entitlements],
        claim_string_form=[e.to_claim() for e in entitlements],
    )
