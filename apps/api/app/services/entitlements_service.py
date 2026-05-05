"""
User entitlements service.

Computes the `madfam_entitled_products` JWT claim and answers
GET /api/v1/me/entitlements. This is the canonical place to derive what
products a user can access at what tier — the OAuth provider, the /me
endpoint, and any future internal caller all go through here.

Sources of truth (merged in priority order):

1. **Per-user grants** (`user_entitlements` table). Written by the Dhanam
   subscription webhook and by admin tooling. Authoritative and explicit.

2. **Org membership inheritance**. If the user belongs to an organization
   whose `product_tiers` JSONB grants a product:tier and the user has no
   explicit per-user row, the org tier is inherited. This is what keeps
   the Phase 0 org-level billing working without having to backfill per-user
   rows for every member.

3. **Admin catch-all**. Users flagged `is_admin=True` (or whose email matches
   a configured operator address) get `:admin` tier on every product slug
   referenced anywhere in the merged set, plus a fixed bootstrap set of
   platform products (selva, janua, enclii, dhanam) so first-run before any
   data exists still resolves admin entry points.

Entitlements with `expires_at <= now()` are excluded.

The JWT claim `madfam_entitled_products` is encoded as a list of strings
"<product>:<tier>" (e.g. "karafiel:contador"). Order is sorted by product
slug for stability across token refreshes — downstream caches (e.g. the
Atrium store) can diff tokens by string equality on the claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID as UuidType

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EntitlementSource,
    Organization,
    OrganizationMember,
    User,
    UserEntitlement,
)

logger = structlog.get_logger()

# Admin catch-all: these products are always granted at `admin` tier to any
# user marked `is_admin=True`. Keeps first-run admin access working before
# any subscription data exists. Specific to the MADFAM ecosystem; new
# platforms get their slug appended here in a follow-up PR (or via the
# product-tier-mapping.yaml in internal-devops/ecosystem/).
ADMIN_BOOTSTRAP_PRODUCTS: tuple[str, ...] = (
    "selva",
    "janua",
    "enclii",
    "dhanam",
    "karafiel",
    "tezca",
    "forgesight",
    "fortuna",
    "rondelio",
    "phyne-crm",
    "cotiza",
    "pravara-mes",
    "sim4d",
    "ceq",
)

ADMIN_TIER = "admin"


@dataclass(frozen=True)
class Entitlement:
    """Immutable entitlement record returned to callers."""

    product: str
    tier: str
    expires_at: Optional[datetime]
    source: EntitlementSource

    def to_claim(self) -> str:
        """Render as the canonical "<product>:<tier>" claim form."""
        return f"{self.product}:{self.tier}"


def _is_active(expires_at: Optional[datetime], now: datetime) -> bool:
    """An entitlement is active iff `expires_at` is unset or in the future."""
    return expires_at is None or expires_at > now


async def _fetch_user_rows(
    user_id: UuidType, db: AsyncSession
) -> list[UserEntitlement]:
    """Pull all rows for this user. Filtering by expiry happens upstream so
    callers can choose to surface recently-cancelled entitlements (e.g. for
    audit) — the JWT claim and the /me endpoint both filter to active."""
    result = await db.execute(
        select(UserEntitlement).where(UserEntitlement.user_id == user_id)
    )
    return list(result.scalars().all())


async def _fetch_org_tiers(
    user: User, db: AsyncSession
) -> dict[str, str]:
    """Read the user's primary organization's product_tiers JSONB.

    Per-user rows always win over org inheritance; this is purely a fallback
    for users who don't yet have explicit per-user rows but belong to an org
    that does have product_tiers from the legacy Dhanam webhook flow.
    """
    # Resolve primary org: prefer User.tenant_id when set, otherwise the
    # user's first organization membership.
    primary_org_id: Optional[UuidType] = getattr(user, "tenant_id", None)

    if not primary_org_id:
        membership_result = await db.execute(
            select(OrganizationMember.organization_id)
            .where(OrganizationMember.user_id == user.id)
            .limit(1)
        )
        row = membership_result.first()
        if row:
            primary_org_id = row[0]

    if not primary_org_id:
        return {}

    org_result = await db.execute(
        select(Organization).where(Organization.id == primary_org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org or not org.product_tiers:
        return {}

    # product_tiers is JSONB shaped like {"karafiel": "pro", "dhanam": "pro"}.
    return {str(k): str(v) for k, v in dict(org.product_tiers).items()}


async def get_user_entitlements(
    user: User,
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
) -> list[Entitlement]:
    """
    Resolve the active entitlements for a user.

    Result is sorted by product slug for deterministic JWT claim ordering.
    Per-user rows beat org inheritance beat admin bootstrap; the highest-
    priority source wins on duplicate product slugs.
    """
    if now is None:
        now = datetime.utcnow()

    merged: dict[str, Entitlement] = {}

    # 3rd priority — admin bootstrap catch-all.
    if getattr(user, "is_admin", False):
        for slug in ADMIN_BOOTSTRAP_PRODUCTS:
            merged[slug] = Entitlement(
                product=slug,
                tier=ADMIN_TIER,
                expires_at=None,
                source=EntitlementSource.ADMIN_GRANT,
            )

    # 2nd priority — org membership inheritance.
    try:
        org_tiers = await _fetch_org_tiers(user, db)
    except Exception as exc:
        # Failure to read org tiers must not block JWT issuance — degrade
        # gracefully to "no inherited grants" and log loudly so ops can see.
        logger.warning(
            "Failed to fetch org product_tiers for entitlements",
            user_id=str(user.id),
            error=str(exc),
        )
        org_tiers = {}

    for product, tier in org_tiers.items():
        merged[product] = Entitlement(
            product=product,
            tier=str(tier),
            expires_at=None,
            source=EntitlementSource.INHERITED,
        )

    # 1st priority — explicit per-user rows. Inactive (expired) rows are
    # dropped here; they don't override a still-valid org inheritance.
    try:
        user_rows = await _fetch_user_rows(user.id, db)
    except Exception as exc:
        logger.warning(
            "Failed to fetch user_entitlements rows",
            user_id=str(user.id),
            error=str(exc),
        )
        user_rows = []

    for row in user_rows:
        if not _is_active(row.expires_at, now):
            continue
        merged[row.product] = Entitlement(
            product=row.product,
            tier=row.tier,
            expires_at=row.expires_at,
            source=row.source,
        )

    return sorted(merged.values(), key=lambda e: e.product)


def entitlements_to_claim(entitlements: Iterable[Entitlement]) -> list[str]:
    """Render the entitlements list to the JWT claim shape (sorted strings)."""
    return [e.to_claim() for e in sorted(entitlements, key=lambda e: e.product)]


async def upsert_entitlement(
    db: AsyncSession,
    *,
    user_id: UuidType,
    product: str,
    tier: str,
    source: EntitlementSource,
    dhanam_subscription_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> UserEntitlement:
    """
    Idempotent upsert for the (user_id, product) unique pair.

    Used by the Dhanam webhook handler. Updates tier/source/expires_at on
    an existing row; inserts when no row exists. Never duplicates: the
    unique constraint on (user_id, product) guarantees one row per pair.
    """
    existing_result = await db.execute(
        select(UserEntitlement).where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.product == product,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        existing.tier = tier
        existing.source = source
        existing.dhanam_subscription_id = (
            dhanam_subscription_id or existing.dhanam_subscription_id
        )
        existing.expires_at = expires_at
        existing.updated_at = datetime.utcnow()
        await db.flush()
        return existing

    row = UserEntitlement(
        user_id=user_id,
        product=product,
        tier=tier,
        source=source,
        dhanam_subscription_id=dhanam_subscription_id,
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row


async def cancel_entitlement(
    db: AsyncSession,
    *,
    user_id: UuidType,
    product: str,
    effective_at: Optional[datetime] = None,
) -> Optional[UserEntitlement]:
    """
    Mark an entitlement as expired. Defaults to "now" (immediate effect);
    callers can pass a future timestamp for grace-period semantics.

    Returns the row when one was found, None otherwise. Idempotent — calling
    cancel twice on the same product is a no-op the second time.
    """
    if effective_at is None:
        effective_at = datetime.utcnow()

    result = await db.execute(
        select(UserEntitlement).where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.product == product,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    # Don't push expiry further into the future when caller asks for "now"
    # but the row already had an earlier expiry recorded — preserve audit.
    if row.expires_at is None or row.expires_at > effective_at:
        row.expires_at = effective_at
        row.updated_at = datetime.utcnow()
        await db.flush()
    return row
