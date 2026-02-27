"""
Dhanam Checkout Integration - Creates checkout sessions for ecosystem billing

This endpoint is called when a user initiates an upgrade from any MADFAM
application (Enclii, Tezca, Yantra4D, Dhanam) through Dhanam billing service.

Flow:
1. User hits tier limit in any product
2. Product app redirects to Dhanam with org context and product plan_id
3. Dhanam calls this endpoint to get checkout session
4. User completes payment on Dhanam/payment provider
5. Dhanam sends webhook to /api/v1/webhooks/dhanam/subscription
6. Janua updates organization.product_tiers[product] = tier
7. User's next JWT has per-product tier claims
"""

import uuid as uuid_mod
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import CheckoutSession, Organization, OrganizationMember, User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/checkout", tags=["billing"])


# Re-use the product plan parser from webhooks module
from app.routers.v1.webhooks_dhanam import parse_product_plan, KNOWN_PRODUCTS, VALID_TIERS


class CreateCheckoutRequest(BaseModel):
    """Request to create a checkout session for Dhanam billing integration."""

    plan_id: str = Field(..., description="Dhanam plan ID (e.g., 'enclii_sovereign', 'pro')")
    organization_id: UUID = Field(..., description="Janua organization ID to upgrade")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is cancelled")


class CheckoutSessionResponse(BaseModel):
    """Response with checkout session details."""

    checkout_url: str = Field(..., description="URL to redirect user for payment")
    session_id: str = Field(..., description="Checkout session ID")
    customer_id: Optional[str] = Field(None, description="Billing customer ID linked to organization")
    provider: str = Field(..., description="Payment provider hint (conekta for MX, polar for intl)")
    organization_id: str = Field(..., description="Organization ID being upgraded")
    plan_id: str = Field(..., description="Plan ID for the checkout")
    product: str = Field(..., description="Product being upgraded (enclii, tezca, yantra4d, dhanam)")
    janua_tier: str = Field(..., description="Corresponding tier")


def determine_provider_hint(email: str) -> str:
    """
    Simple provider hint based on email domain TLD.
    Actual provider selection happens in Dhanam.
    """
    # Default to polar for international
    if email.endswith(".mx") or "mexico" in email.lower():
        return "conekta"
    return "polar"


@router.post("/dhanam", response_model=CheckoutSessionResponse)
async def create_dhanam_checkout(
    request_data: CreateCheckoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a checkout session for Dhanam billing integration.

    This endpoint:
    1. Validates the organization and user permissions
    2. Creates a checkout session record
    3. Links billing_customer_id to the organization (if not already)
    4. Returns checkout URL for Dhanam to process payment

    The checkout URL pattern: https://dhanam.madfam.io/checkout/session/{session_id}
    Dhanam will handle the actual payment provider integration.
    """
    # Parse product and tier from plan_id
    product, tier = parse_product_plan(request_data.plan_id)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id: {request_data.plan_id}. Expected format: '{{product}}_{{tier}}' where product is one of {sorted(KNOWN_PRODUCTS)} and tier is one of {sorted(VALID_TIERS)}",
        )
    janua_tier = tier  # For response compat

    # Get the organization
    result = await db.execute(
        select(Organization).where(Organization.id == request_data.organization_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization not found: {request_data.organization_id}",
        )

    # Verify user has permission (must be owner or admin)
    is_owner = organization.owner_id == current_user.id

    if not is_owner:
        # Check if user is an admin member
        member_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.role.in_(["admin", "owner"]),
            )
        )
        member = member_result.scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization owners and admins can initiate billing changes",
            )

    # Generate unique session ID
    session_id = f"checkout_{uuid_mod.uuid4().hex[:16]}"

    # Determine provider hint (actual selection happens in Dhanam)
    provider_hint = determine_provider_hint(current_user.email or "")

    # Create checkout session record
    checkout_session = CheckoutSession(
        session_id=session_id,
        organization_id=organization.id,
        user_id=current_user.id,
        price_id=request_data.plan_id,
        provider=provider_hint,
        status="pending",
        session_metadata=str({
            "success_url": request_data.success_url,
            "cancel_url": request_data.cancel_url,
            "janua_tier": janua_tier,
            "organization_slug": organization.slug,
            "user_email": current_user.email,
        }),
    )
    db.add(checkout_session)
    await db.commit()

    # Construct Dhanam checkout URL
    checkout_url = f"{settings.DHANAM_URL}/checkout/session/{session_id}"

    logger.info(
        "Created Dhanam checkout session",
        session_id=session_id,
        organization_id=str(organization.id),
        organization_slug=organization.slug,
        plan_id=request_data.plan_id,
        janua_tier=janua_tier,
        provider_hint=provider_hint,
        user_email=current_user.email,
    )

    return CheckoutSessionResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        customer_id=organization.billing_customer_id,
        provider=provider_hint,
        organization_id=str(organization.id),
        plan_id=request_data.plan_id,
        product=product,
        janua_tier=janua_tier,
    )


@router.get("/session/{session_id}")
async def get_checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get checkout session details.

    Allows Dhanam or other services to verify checkout session details.
    Only the user who created the session or org admins can access.
    """
    result = await db.execute(
        select(CheckoutSession).where(CheckoutSession.session_id == session_id)
    )
    checkout_session = result.scalar_one_or_none()

    if not checkout_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkout session not found: {session_id}",
        )

    # Verify access (session owner or org admin)
    is_session_owner = checkout_session.user_id == current_user.id

    if not is_session_owner:
        # Check if user is org admin
        member_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == checkout_session.organization_id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.role.in_(["admin", "owner"]),
            )
        )
        member = member_result.scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    return {
        "session_id": checkout_session.session_id,
        "organization_id": str(checkout_session.organization_id),
        "price_id": checkout_session.price_id,
        "provider": checkout_session.provider,
        "status": checkout_session.status,
        "created_at": checkout_session.created_at.isoformat() if checkout_session.created_at else None,
    }


@router.post("/session/{session_id}/complete")
async def complete_checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a checkout session as completed.

    Called by Dhanam after successful payment to update session status.
    The actual tier update happens via the webhook handler.

    Note: This endpoint should be protected by internal API key in production.
    """
    # In production, verify internal API key
    # For now, allow for testing

    result = await db.execute(
        select(CheckoutSession).where(CheckoutSession.session_id == session_id)
    )
    checkout_session = result.scalar_one_or_none()

    if not checkout_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkout session not found: {session_id}",
        )

    checkout_session.status = "completed"
    checkout_session.updated_at = datetime.utcnow()
    await db.commit()

    logger.info(
        "Checkout session completed",
        session_id=session_id,
        organization_id=str(checkout_session.organization_id),
    )

    return {"status": "completed", "session_id": session_id}
