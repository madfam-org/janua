"""
Billing API Router

Subscription and payment management endpoints for multi-provider billing system.

Endpoints:
- Subscriptions: Create, get, update, cancel, resume
- Payment Methods: Add, list, delete, set default
- Invoices: List, get, pay
- Plans: List available subscription plans
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.billing import (
    SubscriptionPlan,
    Subscription,
    PaymentMethod,
    Invoice,
    SubscriptionStatus,
    BillingInterval,
    PaymentStatus
)
from app.services.payment.router import PaymentRouter, TransactionType
from app.services.payment.base import CustomerData, PaymentMethodData, SubscriptionData


router = APIRouter(prefix="/billing", tags=["billing"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SubscriptionPlanResponse(BaseModel):
    """Subscription plan response."""
    id: UUID
    name: str
    description: Optional[str]
    price_monthly: Optional[float]
    price_yearly: Optional[float]
    currency_usd: str
    currency_mxn: str
    features: List[str]
    limits: Dict[str, Any]
    is_active: bool

    class Config:
        from_attributes = True


class CreateSubscriptionRequest(BaseModel):
    """Create subscription request."""
    plan_id: UUID
    billing_interval: BillingInterval
    payment_method_id: Optional[UUID] = None
    trial_days: Optional[int] = Field(None, ge=0, le=90)


class UpdateSubscriptionRequest(BaseModel):
    """Update subscription request."""
    plan_id: Optional[UUID] = None
    billing_interval: Optional[BillingInterval] = None


class SubscriptionResponse(BaseModel):
    """Subscription response."""
    id: UUID
    organization_id: UUID
    plan_id: UUID
    plan_name: str
    provider: str
    status: SubscriptionStatus
    billing_interval: BillingInterval
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    trial_end: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AddPaymentMethodRequest(BaseModel):
    """Add payment method request."""
    token: str  # Provider-specific token from client SDK
    billing_address: Dict[str, str]
    set_as_default: bool = False


class PaymentMethodResponse(BaseModel):
    """Payment method response."""
    id: UUID
    provider: str
    type: str
    last4: Optional[str]
    brand: Optional[str]
    exp_month: Optional[int]
    exp_year: Optional[int]
    is_default: bool
    billing_address: Optional[Dict[str, str]]

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Invoice response."""
    id: UUID
    subscription_id: UUID
    provider: str
    provider_invoice_id: str
    amount: float
    currency: str
    status: PaymentStatus
    invoice_date: datetime
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    hosted_invoice_url: Optional[str]
    invoice_pdf: Optional[str]

    class Config:
        from_attributes = True


# ============================================================================
# Subscription Plans
# ============================================================================

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all available subscription plans.

    Returns active plans with pricing and features.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
    )
    plans = result.scalars().all()

    return plans


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific subscription plan details."""
    from sqlalchemy import select

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )

    return plan


# ============================================================================
# Subscriptions
# ============================================================================

@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    request_data: CreateSubscriptionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new subscription for organization.

    Workflow:
    1. Get plan details
    2. Detect customer location for provider routing
    3. Create customer in payment provider (if needed)
    4. Create subscription in payment provider
    5. Store subscription in database
    """
    from sqlalchemy import select

    # Get organization (assuming user has organization)
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization"
        )

    # Get plan
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == request_data.plan_id)
    )
    plan = result.scalar_one_or_none()

    if not plan or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found or inactive"
        )

    # Initialize payment router
    payment_router = PaymentRouter()

    # Get client IP for geolocation
    client_ip = request.client.host

    # Get provider based on location (with automatic Stripe fallback)
    provider, fallback_info = await payment_router.get_provider(
        transaction_type=TransactionType.SUBSCRIPTION,
        ip_address=client_ip,
        user_country=getattr(current_user, "country", None)
    )

    # Log fallback events for monitoring
    if fallback_info:
        logger.warning(
            f"Provider fallback occurred during subscription creation: "
            f"attempted={fallback_info['attempted_provider']}, "
            f"fallback={fallback_info['fallback_provider']}, "
            f"reason={fallback_info['reason']}, "
            f"user_id={current_user.id}"
        )

    # Get payment method if specified
    payment_method_provider_id = None
    if request_data.payment_method_id:
        result = await db.execute(
            select(PaymentMethod).where(
                PaymentMethod.id == request_data.payment_method_id,
                PaymentMethod.organization_id == current_user.organization_id
            )
        )
        payment_method = result.scalar_one_or_none()

        if not payment_method:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment method not found"
            )
        payment_method_provider_id = payment_method.provider_payment_method_id

    # Check if organization already has customer in provider
    result = await db.execute(
        select(Subscription).where(
            Subscription.organization_id == current_user.organization_id,
            Subscription.provider == provider.provider_name
        ).limit(1)
    )
    existing_subscription = result.scalar_one_or_none()

    if existing_subscription:
        provider_customer_id = existing_subscription.provider_customer_id
    else:
        # Create customer in provider
        customer_data = CustomerData(
            email=current_user.email,
            name=getattr(current_user, "name", None),
            metadata={"organization_id": str(current_user.organization_id)}
        )
        customer_response = await provider.create_customer(customer_data)
        provider_customer_id = customer_response["customer_id"]

    # Get provider plan ID
    provider_plan_ids = plan.provider_plan_ids or {}
    provider_plan_id = provider_plan_ids.get(provider.provider_name)

    if not provider_plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan not configured for provider {provider.provider_name}"
        )

    # Create subscription in provider
    subscription_data = SubscriptionData(
        customer_id=provider_customer_id,
        plan_id=provider_plan_id,
        payment_method_id=payment_method_provider_id,
        trial_days=request_data.trial_days,
        metadata={
            "organization_id": str(current_user.organization_id),
            "plan_id": str(plan.id),
            "created_by": str(current_user.id)
        }
    )

    provider_subscription = await provider.create_subscription(subscription_data)

    # Store subscription in database
    subscription = Subscription(
        organization_id=current_user.organization_id,
        plan_id=plan.id,
        provider=provider.provider_name,
        provider_subscription_id=provider_subscription["subscription_id"],
        provider_customer_id=provider_customer_id,
        status=SubscriptionStatus(provider_subscription["status"]),
        billing_interval=request_data.billing_interval,
        current_period_start=datetime.fromtimestamp(provider_subscription["current_period_start"]),
        current_period_end=datetime.fromtimestamp(provider_subscription["current_period_end"]),
        trial_end=datetime.fromtimestamp(provider_subscription["trial_end"]) if provider_subscription.get("trial_end") else None
    )

    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    # Return response with plan name
    response = SubscriptionResponse.model_validate(subscription)
    response.plan_name = plan.name

    return response


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all subscriptions for current organization."""
    from sqlalchemy import select

    if not current_user.organization_id:
        return []

    result = await db.execute(
        select(Subscription)
        .where(Subscription.organization_id == current_user.organization_id)
        .order_by(Subscription.created_at.desc())
    )
    subscriptions = result.scalars().all()

    # Enrich with plan names
    responses = []
    for sub in subscriptions:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id)
        )
        plan = result.scalar_one_or_none()

        response = SubscriptionResponse.model_validate(sub)
        response.plan_name = plan.name if plan else "Unknown Plan"
        responses.append(response)

    return responses


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get subscription details."""
    from sqlalchemy import select

    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.organization_id == current_user.organization_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Get plan name
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    response = SubscriptionResponse.model_validate(subscription)
    response.plan_name = plan.name if plan else "Unknown Plan"

    return response


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    request_data: UpdateSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update subscription (change plan or billing interval).

    Note: This creates a new subscription in the provider and cancels the old one.
    """
    from sqlalchemy import select

    # Get existing subscription
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.organization_id == current_user.organization_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Get provider
    payment_router = PaymentRouter()
    provider = payment_router.providers.get(subscription.provider)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provider {subscription.provider} not configured"
        )

    # Update subscription in provider
    update_data = {}

    if request_data.plan_id:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == request_data.plan_id)
        )
        new_plan = result.scalar_one_or_none()

        if not new_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="New plan not found"
            )

        provider_plan_id = new_plan.provider_plan_ids.get(provider.provider_name)
        if not provider_plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New plan not configured for provider {provider.provider_name}"
            )

        update_data["plan_id"] = provider_plan_id
        subscription.plan_id = request_data.plan_id

    if request_data.billing_interval:
        subscription.billing_interval = request_data.billing_interval

    # Update in provider
    if update_data:
        provider_response = await provider.update_subscription(
            subscription.provider_subscription_id,
            update_data
        )

        subscription.status = SubscriptionStatus(provider_response["status"])
        subscription.current_period_start = datetime.fromtimestamp(provider_response["current_period_start"])
        subscription.current_period_end = datetime.fromtimestamp(provider_response["current_period_end"])

    await db.commit()
    await db.refresh(subscription)

    # Get plan name
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    response = SubscriptionResponse.model_validate(subscription)
    response.plan_name = plan.name if plan else "Unknown Plan"

    return response


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: UUID,
    cancel_immediately: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel subscription.

    Args:
        cancel_immediately: If True, cancel now. If False, cancel at period end.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.organization_id == current_user.organization_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Get provider
    payment_router = PaymentRouter()
    provider = payment_router.providers.get(subscription.provider)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provider {subscription.provider} not configured"
        )

    # Cancel in provider
    provider_response = await provider.cancel_subscription(
        subscription.provider_subscription_id,
        cancel_immediately
    )

    # Update database
    subscription.status = SubscriptionStatus(provider_response["status"])
    subscription.cancel_at_period_end = provider_response.get("cancel_at_period_end", False)

    if cancel_immediately:
        subscription.canceled_at = datetime.utcnow()

    await db.commit()
    await db.refresh(subscription)

    # Get plan name
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    response = SubscriptionResponse.model_validate(subscription)
    response.plan_name = plan.name if plan else "Unknown Plan"

    return response


@router.post("/subscriptions/{subscription_id}/resume", response_model=SubscriptionResponse)
async def resume_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resume a canceled subscription (only if cancel_at_period_end was set)."""
    from sqlalchemy import select

    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.organization_id == current_user.organization_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    if not subscription.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not scheduled for cancellation"
        )

    # Get provider
    payment_router = PaymentRouter()
    provider = payment_router.providers.get(subscription.provider)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provider {subscription.provider} not configured"
        )

    # Resume in provider
    provider_response = await provider.resume_subscription(
        subscription.provider_subscription_id
    )

    # Update database
    subscription.status = SubscriptionStatus(provider_response["status"])
    subscription.cancel_at_period_end = False

    await db.commit()
    await db.refresh(subscription)

    # Get plan name
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    response = SubscriptionResponse.model_validate(subscription)
    response.plan_name = plan.name if plan else "Unknown Plan"

    return response

# ============================================================================
# Payment Methods
# ============================================================================

@router.post("/payment-methods", response_model=PaymentMethodResponse)
async def add_payment_method(
    request_data: AddPaymentMethodRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add payment method to organization."""
    from sqlalchemy import select

    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization"
        )

    payment_router = PaymentRouter()
    client_ip = request.client.host

    # Get provider based on location and billing address (with automatic Stripe fallback)
    provider, fallback_info = await payment_router.get_provider(
        billing_address=request_data.billing_address,
        ip_address=client_ip,
        user_country=getattr(current_user, "country", None)
    )

    # Log fallback events for monitoring
    if fallback_info:
        logger.warning(
            f"Provider fallback occurred during payment method creation: "
            f"attempted={fallback_info['attempted_provider']}, "
            f"fallback={fallback_info['fallback_provider']}, "
            f"reason={fallback_info['reason']}, "
            f"user_id={current_user.id}"
        )

    # Get or create customer
    result = await db.execute(
        select(Subscription).where(
            Subscription.organization_id == current_user.organization_id,
            Subscription.provider == provider.provider_name
        ).limit(1)
    )
    existing_subscription = result.scalar_one_or_none()

    if existing_subscription:
        provider_customer_id = existing_subscription.provider_customer_id
    else:
        customer_data = CustomerData(
            email=current_user.email,
            name=getattr(current_user, "name", None),
            metadata={"organization_id": str(current_user.organization_id)}
        )
        customer_response = await provider.create_customer(customer_data)
        provider_customer_id = customer_response["customer_id"]

    # Add payment method
    payment_method_data = PaymentMethodData(
        token=request_data.token,
        type="card",
        billing_address=request_data.billing_address
    )

    provider_response = await provider.create_payment_method(
        provider_customer_id,
        payment_method_data
    )

    payment_method = PaymentMethod(
        organization_id=current_user.organization_id,
        provider=provider.provider_name,
        provider_payment_method_id=provider_response["payment_method_id"],
        provider_customer_id=provider_customer_id,
        type=provider_response.get("type", "card"),
        last4=provider_response.get("last4"),
        brand=provider_response.get("brand"),
        exp_month=provider_response.get("exp_month"),
        exp_year=provider_response.get("exp_year"),
        billing_address=request_data.billing_address,
        is_default=request_data.set_as_default
    )

    if request_data.set_as_default:
        result = await db.execute(
            select(PaymentMethod).where(
                PaymentMethod.organization_id == current_user.organization_id,
                PaymentMethod.provider == provider.provider_name,
                PaymentMethod.is_default == True
            )
        )
        for old_default in result.scalars().all():
            old_default.is_default = False

    db.add(payment_method)
    await db.commit()
    await db.refresh(payment_method)

    return payment_method


@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
async def list_payment_methods(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List payment methods for organization."""
    from sqlalchemy import select

    if not current_user.organization_id:
        return []

    query = select(PaymentMethod).where(
        PaymentMethod.organization_id == current_user.organization_id
    )

    if provider:
        query = query.where(PaymentMethod.provider == provider)

    result = await db.execute(query.order_by(PaymentMethod.is_default.desc()))
    return result.scalars().all()


@router.delete("/payment-methods/{payment_method_id}")
async def delete_payment_method(
    payment_method_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove payment method."""
    from sqlalchemy import select

    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == payment_method_id,
            PaymentMethod.organization_id == current_user.organization_id
        )
    )
    payment_method = result.scalar_one_or_none()

    if not payment_method:
        raise HTTPException(status_code=404, detail="Payment method not found")

    payment_router = PaymentRouter()
    provider = payment_router.providers.get(payment_method.provider)

    if provider:
        await provider.delete_payment_method(
            payment_method.provider_customer_id,
            payment_method.provider_payment_method_id
        )

    await db.delete(payment_method)
    await db.commit()

    return {"message": "Payment method deleted"}


# ============================================================================
# Invoices
# ============================================================================

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    subscription_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List invoices for organization."""
    from sqlalchemy import select

    if not current_user.organization_id:
        return []

    subscription_query = select(Subscription.id).where(
        Subscription.organization_id == current_user.organization_id
    )

    if subscription_id:
        subscription_query = subscription_query.where(Subscription.id == subscription_id)

    subscription_result = await db.execute(subscription_query)
    subscription_ids = [row[0] for row in subscription_result.all()]

    if not subscription_ids:
        return []

    result = await db.execute(
        select(Invoice)
        .where(Invoice.subscription_id.in_(subscription_ids))
        .order_by(Invoice.invoice_date.desc())
    )
    return result.scalars().all()
