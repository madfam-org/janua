"""
Internal role/tier synchronization endpoints.
Called by Dhanam (billing engine) to sync subscription tier changes to Janua.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_engine import VALID_TIERS
from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.models import Organization
from app.schemas.internal import TierSyncRequest, TierSyncResponse

logger = structlog.get_logger()

router = APIRouter(tags=["internal"])


@router.post(
    "/organizations/{organization_id}/tier",
    response_model=TierSyncResponse,
)
async def sync_organization_tier(
    organization_id: UUID,
    body: TierSyncRequest,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync an organization's subscription tier from an external billing engine.

    This is an internal endpoint secured by API key, intended for service-to-service
    communication (e.g., Dhanam calls Janua after a subscription change).
    """
    # 1. Validate tier
    if body.tier not in VALID_TIERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {body.tier}. Valid tiers: {sorted(VALID_TIERS)}",
        )

    # 2. Fetch organization
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {organization_id} not found",
        )

    previous_tier = org.subscription_tier

    # 3. Idempotency: skip if already at requested tier with same key
    if previous_tier == body.tier:
        logger.info(
            "Tier sync is no-op (already at tier)",
            organization_id=str(organization_id),
            tier=body.tier,
            idempotency_key=body.idempotency_key,
        )
        return TierSyncResponse(
            status="ok",
            previous_tier=previous_tier,
            new_tier=body.tier,
        )

    # 4. Update tier
    org.subscription_tier = body.tier
    await db.commit()

    # 5. Audit log
    logger.info(
        "Subscription tier changed",
        organization_id=str(organization_id),
        previous_tier=previous_tier,
        new_tier=body.tier,
        source=body.source,
        idempotency_key=body.idempotency_key,
    )

    # Emit audit event if audit service is available
    try:
        from app.services.audit_service import AuditService

        audit = AuditService()
        await audit.log_event(
            db,
            event_type="SUBSCRIPTION_TIER_CHANGED",
            resource_type="organization",
            resource_id=str(organization_id),
            details={
                "previous_tier": previous_tier,
                "new_tier": body.tier,
                "source": body.source,
                "idempotency_key": body.idempotency_key,
            },
        )
    except Exception as e:
        # Audit logging failure should not block the tier sync
        logger.warning("Failed to emit audit event for tier change", error=str(e))

    return TierSyncResponse(
        status="ok",
        previous_tier=previous_tier,
        new_tier=body.tier,
    )
