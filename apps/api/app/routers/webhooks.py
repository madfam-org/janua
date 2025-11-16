"""
Payment Provider Webhooks

Webhook handlers for Conekta, Stripe, and Polar payment providers.

Security:
- All webhooks verify signature before processing
- Idempotent processing using webhook_events table
- Async processing for performance

Events Handled:
- subscription.created, updated, canceled
- invoice.created, payment_succeeded, payment_failed
- payment_method.attached, detached
- customer.created, updated, deleted
"""

import hashlib
import hmac
import os
from typing import Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.billing import (
    Subscription,
    Invoice,
    PaymentMethod,
    WebhookEvent,
    SubscriptionStatus,
    PaymentStatus,
    InvoiceStatus
)
from app.services.payment.router import PaymentRouter, ProviderName
from app.services.payment.conekta_provider import ConektaProvider
from app.services.payment.stripe_provider import StripeProvider
from app.services.payment.polar_provider import PolarProvider


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ============================================================================
# Helper Functions
# ============================================================================

async def check_webhook_processed(
    db: AsyncSession,
    provider: str,
    event_id: str
) -> bool:
    """Check if webhook event was already processed (idempotency)."""
    result = await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.provider == provider,
            WebhookEvent.provider_event_id == event_id
        )
    )
    return result.scalar_one_or_none() is not None


async def record_webhook_event(
    db: AsyncSession,
    provider: str,
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    processed: bool = True
):
    """Record webhook event for idempotency and audit."""
    webhook_event = WebhookEvent(
        provider=provider,
        provider_event_id=event_id,
        event_type=event_type,
        payload=payload,
        processed=processed
    )
    db.add(webhook_event)
    await db.commit()


# ============================================================================
# Conekta Webhooks
# ============================================================================

@router.post("/conekta")
async def conekta_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_conekta_signature: str = Header(None, alias="X-Conekta-Signature")
):
    """
    Conekta webhook handler.

    Events:
    - subscription.created, updated, canceled, paused, resumed
    - charge.created, paid, refunded
    - order.created, paid
    - customer.created, updated
    """
    # Get raw body for signature verification
    body = await request.body()
    payload = await request.json()

    # Verify webhook signature
    webhook_secret = os.getenv("CONEKTA_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )

    provider = ConektaProvider(api_key=os.getenv("CONEKTA_API_KEY", ""))

    if not provider.verify_webhook_signature(
        body,
        x_conekta_signature or "",
        webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Extract event data
    event_id = payload.get("id")
    event_type = payload.get("type")
    event_data = payload.get("data", {}).get("object", {})

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload"
        )

    # Check if already processed (idempotency)
    if await check_webhook_processed(db, "conekta", event_id):
        return {"status": "already_processed"}

    # Process event based on type
    try:
        if event_type.startswith("subscription."):
            await process_conekta_subscription_event(db, event_type, event_data)
        elif event_type.startswith("charge."):
            await process_conekta_charge_event(db, event_type, event_data)
        elif event_type.startswith("order."):
            await process_conekta_order_event(db, event_type, event_data)

        # Record successful processing
        await record_webhook_event(db, "conekta", event_id, event_type, payload, True)

        return {"status": "processed"}

    except Exception as e:
        # Record failed processing
        await record_webhook_event(db, "conekta", event_id, event_type, payload, False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


async def process_conekta_subscription_event(
    db: AsyncSession,
    event_type: str,
    subscription_data: Dict[str, Any]
):
    """Process Conekta subscription events."""
    subscription_id = subscription_data.get("id")

    # Find subscription in database
    result = await db.execute(
        select(Subscription).where(
            Subscription.provider == "conekta",
            Subscription.provider_subscription_id == subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return  # Subscription not in our system

    # Update subscription based on event
    if event_type == "subscription.canceled":
        subscription.status = SubscriptionStatus.CANCELED
        subscription.canceled_at = datetime.utcnow()
    elif event_type == "subscription.paused":
        subscription.status = SubscriptionStatus.PAUSED
    elif event_type == "subscription.resumed":
        subscription.status = SubscriptionStatus.ACTIVE
    elif event_type in ["subscription.created", "subscription.updated"]:
        subscription.status = SubscriptionStatus(subscription_data.get("status", "active"))

    await db.commit()


async def process_conekta_charge_event(
    db: AsyncSession,
    event_type: str,
    charge_data: Dict[str, Any]
):
    """Process Conekta charge events (for invoices)."""
    charge_id = charge_data.get("id")

    # Find invoice by charge ID
    result = await db.execute(
        select(Invoice).where(
            Invoice.provider == "conekta",
            Invoice.provider_invoice_id == charge_id
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        return  # Invoice not in our system

    # Update invoice based on event
    if event_type == "charge.paid":
        invoice.status = PaymentStatus.PAID
        invoice.paid_at = datetime.utcnow()
    elif event_type == "charge.refunded":
        invoice.status = PaymentStatus.REFUNDED

    await db.commit()


async def process_conekta_order_event(
    db: AsyncSession,
    event_type: str,
    order_data: Dict[str, Any]
):
    """Process Conekta order events."""
    # Handle one-time orders if needed
    pass


# ============================================================================
# Stripe Webhooks
# ============================================================================

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """
    Stripe webhook handler.

    Events:
    - customer.subscription.created, updated, deleted
    - invoice.created, paid, payment_failed
    - payment_method.attached, detached
    - customer.created, updated, deleted
    """
    import stripe

    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )

    try:
        event = stripe.Webhook.construct_event(
            body,
            stripe_signature or "",
            webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    event_id = event["id"]
    event_type = event["type"]
    event_data = event["data"]["object"]

    # Check if already processed
    if await check_webhook_processed(db, "stripe", event_id):
        return {"status": "already_processed"}

    # Process event
    try:
        if event_type.startswith("customer.subscription."):
            await process_stripe_subscription_event(db, event_type, event_data)
        elif event_type.startswith("invoice."):
            await process_stripe_invoice_event(db, event_type, event_data)
        elif event_type.startswith("payment_method."):
            await process_stripe_payment_method_event(db, event_type, event_data)

        # Record successful processing
        await record_webhook_event(db, "stripe", event_id, event_type, event, True)

        return {"status": "processed"}

    except Exception as e:
        await record_webhook_event(db, "stripe", event_id, event_type, event, False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


async def process_stripe_subscription_event(
    db: AsyncSession,
    event_type: str,
    subscription_data: Dict[str, Any]
):
    """Process Stripe subscription events."""
    subscription_id = subscription_data.get("id")

    result = await db.execute(
        select(Subscription).where(
            Subscription.provider == "stripe",
            Subscription.provider_subscription_id == subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return

    if event_type == "customer.subscription.deleted":
        subscription.status = SubscriptionStatus.CANCELED
        subscription.canceled_at = datetime.utcnow()
    elif event_type in ["customer.subscription.created", "customer.subscription.updated"]:
        subscription.status = SubscriptionStatus(subscription_data.get("status", "active"))
        subscription.current_period_start = datetime.fromtimestamp(subscription_data["current_period_start"])
        subscription.current_period_end = datetime.fromtimestamp(subscription_data["current_period_end"])

    await db.commit()


async def process_stripe_invoice_event(
    db: AsyncSession,
    event_type: str,
    invoice_data: Dict[str, Any]
):
    """Process Stripe invoice events."""
    invoice_id = invoice_data.get("id")

    result = await db.execute(
        select(Invoice).where(
            Invoice.provider == "stripe",
            Invoice.provider_invoice_id == invoice_id
        )
    )
    invoice = result.scalar_one_or_none()

    if event_type == "invoice.created" and not invoice:
        # Create new invoice record
        subscription_id = invoice_data.get("subscription")
        if subscription_id:
            result = await db.execute(
                select(Subscription).where(
                    Subscription.provider == "stripe",
                    Subscription.provider_subscription_id == subscription_id
                )
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                invoice = Invoice(
                    subscription_id=subscription.id,
                    provider="stripe",
                    provider_invoice_id=invoice_id,
                    amount=invoice_data["amount_due"] / 100,  # Convert cents to dollars
                    currency=invoice_data["currency"].upper(),
                    status=PaymentStatus.PENDING,
                    invoice_date=datetime.fromtimestamp(invoice_data["created"]),
                    due_date=datetime.fromtimestamp(invoice_data["due_date"]) if invoice_data.get("due_date") else None,
                    hosted_invoice_url=invoice_data.get("hosted_invoice_url"),
                    invoice_pdf=invoice_data.get("invoice_pdf")
                )
                db.add(invoice)

    elif invoice:
        if event_type == "invoice.paid":
            invoice.status = PaymentStatus.PAID
            invoice.paid_at = datetime.utcnow()
        elif event_type == "invoice.payment_failed":
            invoice.status = PaymentStatus.FAILED

    await db.commit()


async def process_stripe_payment_method_event(
    db: AsyncSession,
    event_type: str,
    payment_method_data: Dict[str, Any]
):
    """Process Stripe payment method events."""
    # Handle payment method attached/detached if needed
    pass


# ============================================================================
# Polar Webhooks
# ============================================================================

@router.post("/polar")
async def polar_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_polar_signature: str = Header(None, alias="X-Polar-Signature")
):
    """
    Polar webhook handler.

    Events:
    - order.created, order.completed
    - subscription.created, updated, canceled
    - benefit.granted, revoked
    """
    # Get raw body for signature verification
    body = await request.body()
    payload = await request.json()

    # Verify webhook signature
    webhook_secret = os.getenv("POLAR_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )

    provider = PolarProvider(api_key=os.getenv("POLAR_API_KEY", ""))

    if not provider.verify_webhook_signature(
        body,
        x_polar_signature or "",
        webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    event_id = payload.get("id")
    event_type = payload.get("type")
    event_data = payload.get("data")

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload"
        )

    # Check if already processed
    if await check_webhook_processed(db, "polar", event_id):
        return {"status": "already_processed"}

    # Process event
    try:
        if event_type.startswith("order."):
            await process_polar_order_event(db, event_type, event_data)
        elif event_type.startswith("subscription."):
            await process_polar_subscription_event(db, event_type, event_data)

        # Record successful processing
        await record_webhook_event(db, "polar", event_id, event_type, payload, True)

        return {"status": "processed"}

    except Exception as e:
        await record_webhook_event(db, "polar", event_id, event_type, payload, False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


async def process_polar_order_event(
    db: AsyncSession,
    event_type: str,
    order_data: Dict[str, Any]
):
    """Process Polar order events (one-time purchases)."""
    order_id = order_data.get("id")

    # Find invoice by order ID
    result = await db.execute(
        select(Invoice).where(
            Invoice.provider == "polar",
            Invoice.provider_invoice_id == order_id
        )
    )
    invoice = result.scalar_one_or_none()

    if event_type == "order.completed" and invoice:
        invoice.status = PaymentStatus.PAID
        invoice.paid_at = datetime.utcnow()
        await db.commit()


async def process_polar_subscription_event(
    db: AsyncSession,
    event_type: str,
    subscription_data: Dict[str, Any]
):
    """Process Polar subscription events."""
    subscription_id = subscription_data.get("id")

    result = await db.execute(
        select(Subscription).where(
            Subscription.provider == "polar",
            Subscription.provider_subscription_id == subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return

    if event_type == "subscription.canceled":
        subscription.status = SubscriptionStatus.CANCELED
        subscription.canceled_at = datetime.utcnow()
    elif event_type in ["subscription.created", "subscription.updated"]:
        subscription.status = SubscriptionStatus(subscription_data.get("status", "active"))

    await db.commit()
