"""
Dhanam Billing Webhooks - Updates organization per-product tiers

Handles subscription events from Dhanam billing system to keep Janua
organization tiers in sync for JWT claims across all products.

Plan ID format: "{product}_{tier}" (e.g. "tezca_pro", "enclii_pro")
Bare plan IDs (e.g. "pro") default to product="dhanam".

Per-product tiers are stored in Organization.product_tiers JSONB and emitted
as individual JWT claims (foundry_tier, tezca_tier, yantra4d_tier, dhanam_tier).
"""

import hashlib
import hmac
import re
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models import Organization

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks/dhanam", tags=["webhooks"])

# Open product validation: any lowercase alphanumeric name is a valid product.
# No hardcoded product list — new ecosystem services are accepted automatically.
PRODUCT_PATTERN = re.compile(r"^[a-z][a-z0-9]*$")
VALID_TIERS = {"essentials", "pro", "madfam"}

# Legacy plan names -> (product, tier) for backwards compatibility
LEGACY_PLAN_MAP = {
    "sovereign": ("enclii", "pro"),
    "ecosystem": ("enclii", "madfam"),
    "enclii_sovereign": ("enclii", "pro"),
    "enclii_ecosystem": ("enclii", "madfam"),
    "enterprise": ("dhanam", "madfam"),
    "scale": ("dhanam", "pro"),
}

# Plans that mean "not billed" — remove product tier on these
CANCEL_TIERS = {"free", "community", "trial"}


def verify_dhanam_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Dhanam webhook HMAC-SHA256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def parse_product_plan(plan_id: str) -> tuple[str, str | None]:
    """Parse a Dhanam plan_id into (product, tier).

    Examples:
        "tezca_pro" -> ("tezca", "pro")
        "enclii_essentials" -> ("enclii", "essentials")
        "pro" -> ("dhanam", "pro")
        "sovereign" -> ("enclii", "pro")  # legacy
        "free" -> ("dhanam", None)  # cancel tier
    """
    if not plan_id:
        return "dhanam", None

    plan_lower = plan_id.lower()

    # Strip billing period suffixes
    for suffix in ("_monthly", "_annual", "_yearly"):
        if plan_lower.endswith(suffix):
            plan_lower = plan_lower[: -len(suffix)]
            break

    # Check legacy plan names first
    if plan_lower in LEGACY_PLAN_MAP:
        return LEGACY_PLAN_MAP[plan_lower]

    # Check cancel/free tiers
    if plan_lower in CANCEL_TIERS:
        return "dhanam", None

    # Parse "{product}_{tier}" format — accepts any valid product name
    parts = plan_lower.split("_", 1)
    if len(parts) == 2 and PRODUCT_PATTERN.match(parts[0]):
        product, tier = parts
        if tier in CANCEL_TIERS:
            return product, None
        if tier in VALID_TIERS:
            return product, tier
        # Unknown tier name for known product — log and use as-is
        logger.warning("Unknown tier in plan_id", plan_id=plan_id, product=product, tier=tier)
        return product, tier

    # Bare tier name — default to dhanam product
    if plan_lower in VALID_TIERS:
        return "dhanam", plan_lower

    logger.warning("Unrecognized plan_id", plan_id=plan_id)
    return "dhanam", None


async def find_organization(
    db: AsyncSession,
    customer_id: str | None,
    org_id: str | None,
    metadata: dict | None = None,
) -> Organization | None:
    """
    Find organization using multiple lookup strategies:
    1. By billing_customer_id (primary)
    2. By organization_id in metadata
    3. By explicit org_id parameter
    """
    organization = None

    # Strategy 1: Lookup by billing_customer_id
    if customer_id:
        result = await db.execute(
            select(Organization).where(Organization.billing_customer_id == customer_id)
        )
        organization = result.scalar_one_or_none()
        if organization:
            logger.debug(
                "Found organization by billing_customer_id",
                org_id=str(organization.id),
                customer_id=customer_id,
            )
            return organization

    # Strategy 2: Lookup by org_id from metadata
    if metadata and metadata.get("organization_id"):
        try:
            org_uuid = UUID(metadata["organization_id"])
            result = await db.execute(
                select(Organization).where(Organization.id == org_uuid)
            )
            organization = result.scalar_one_or_none()
            if organization:
                logger.debug(
                    "Found organization by metadata.organization_id",
                    org_id=str(organization.id),
                )
                # Also link the customer_id if we have it
                if customer_id and not organization.billing_customer_id:
                    organization.billing_customer_id = customer_id
                    logger.info(
                        "Linked billing_customer_id to organization",
                        org_id=str(organization.id),
                        customer_id=customer_id,
                    )
                return organization
        except (ValueError, TypeError) as e:
            logger.warning(
                "Invalid organization_id in metadata",
                org_id=metadata.get("organization_id"),
                error=str(e),
            )

    # Strategy 3: Direct org_id lookup
    if org_id:
        try:
            org_uuid = UUID(org_id)
            result = await db.execute(
                select(Organization).where(Organization.id == org_uuid)
            )
            organization = result.scalar_one_or_none()
            if organization:
                logger.debug(
                    "Found organization by direct org_id",
                    org_id=str(organization.id),
                )
                return organization
        except (ValueError, TypeError) as e:
            logger.warning(
                "Invalid org_id parameter",
                org_id=org_id,
                error=str(e),
            )

    return None


@router.post("/subscription")
async def dhanam_subscription_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_dhanam_signature: str = Header(..., alias="X-Dhanam-Signature"),
):
    """
    Handle Dhanam subscription events.

    Supported events:
    - subscription.created: New subscription, set tier
    - subscription.updated: Plan change, update tier
    - subscription.canceled: Subscription ended, downgrade to community

    Updates the organization's subscription_tier based on the Dhanam plan,
    which affects the foundry_tier claim in SSO JWT tokens for Enclii feature gating.

    Expected payload format:
    ```json
    {
        "type": "subscription.created" | "subscription.updated" | "subscription.canceled",
        "data": {
            "customer_id": "cust_xxx",
            "plan_id": "pro" | "sovereign" | "enterprise" | etc.,
            "metadata": {
                "organization_id": "uuid-optional-fallback"
            }
        }
    }
    ```
    """
    body = await request.body()

    # Verify signature
    if not settings.DHANAM_WEBHOOK_SECRET:
        logger.error("DHANAM_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=500,
            detail="Webhook secret not configured",
        )

    if not verify_dhanam_signature(body, x_dhanam_signature, settings.DHANAM_WEBHOOK_SECRET):
        logger.warning("Invalid Dhanam webhook signature")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    # Parse payload
    payload = await request.json()
    event_type = payload.get("type")
    event_data = payload.get("data", {})
    metadata = event_data.get("metadata", {})

    logger.info(
        "Received Dhanam webhook",
        event_type=event_type,
        customer_id=event_data.get("customer_id"),
        plan_id=event_data.get("plan_id"),
        has_metadata=bool(metadata),
    )

    # Handle supported events
    supported_events = (
        "subscription.created",
        "subscription.updated",
        "subscription.canceled",
        "subscription.deleted",
    )
    if event_type not in supported_events:
        logger.info("Ignoring unsupported event", event_type=event_type)
        return {"status": "ignored", "reason": "unsupported_event_type"}

    customer_id = event_data.get("customer_id")
    plan_id = event_data.get("plan_id")
    org_id = event_data.get("organization_id")

    # For cancel events, plan_id might be missing - that's OK
    if event_type in ("subscription.created", "subscription.updated"):
        if not plan_id:
            logger.warning("Missing plan_id for subscription event", event_type=event_type)
            raise HTTPException(
                status_code=400,
                detail="Missing plan_id in webhook payload",
            )

    # Find organization using multiple strategies
    organization = await find_organization(db, customer_id, org_id, metadata)

    if not organization:
        logger.warning(
            "Organization not found",
            customer_id=customer_id,
            org_id=org_id,
            metadata_org_id=metadata.get("organization_id"),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Organization not found. Tried: customer_id={customer_id}, org_id={org_id}, metadata.organization_id={metadata.get('organization_id')}",
        )

    # Parse product and tier from plan_id
    if event_type in ("subscription.canceled", "subscription.deleted"):
        # For cancellations, parse product from plan_id to know which product to downgrade
        product, _ = parse_product_plan(plan_id) if plan_id else ("dhanam", None)
        new_tier = None  # Remove tier = not billed
    else:
        product, new_tier = parse_product_plan(plan_id)

    # Update product_tiers JSONB
    current_tiers = dict(organization.product_tiers or {})
    old_product_tier = current_tiers.get(product)

    if new_tier:
        current_tiers[product] = new_tier
    else:
        current_tiers.pop(product, None)  # Remove product tier on cancel

    organization.product_tiers = current_tiers

    # Keep legacy subscription_tier in sync (derived from highest product tier)
    tier_rank = {"essentials": 1, "pro": 2, "madfam": 3}
    highest = max(
        (tier_rank.get(t, 0) for t in current_tiers.values()),
        default=0,
    )
    rank_to_legacy = {0: "community", 1: "pro", 2: "pro", 3: "enterprise"}
    organization.subscription_tier = rank_to_legacy.get(highest, "community")

    organization.updated_at = datetime.utcnow()

    # Ensure billing_customer_id is linked
    if customer_id and not organization.billing_customer_id:
        organization.billing_customer_id = customer_id
        logger.info(
            "Linked billing_customer_id during webhook",
            organization_id=str(organization.id),
            customer_id=customer_id,
        )

    await db.commit()

    logger.info(
        "Product tier updated via Dhanam webhook",
        organization_id=str(organization.id),
        organization_name=organization.name,
        product=product,
        old_tier=old_product_tier,
        new_tier=new_tier,
        product_tiers=current_tiers,
        plan_id=plan_id,
        event_type=event_type,
    )

    return {
        "status": "processed",
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "product": product,
        "old_tier": old_product_tier,
        "new_tier": new_tier,
        "product_tiers": current_tiers,
        "event_type": event_type,
    }
