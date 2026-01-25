"""
Billing models for multi-provider payment infrastructure.

Supports Conekta (Mexico), Stripe (International), and Polar (Products).
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class PaymentProvider(str, Enum):
    """Supported payment providers."""

    CONEKTA = "conekta"  # Mexican customers
    STRIPE = "stripe"  # International customers
    POLAR = "polar"  # Product purchases


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle states."""

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"


class InvoiceStatus(str, Enum):
    """Invoice payment states."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"


class PaymentMethodType(str, Enum):
    """Payment method types."""

    CARD = "card"
    BANK_ACCOUNT = "bank_account"
    OXXO = "oxxo"  # Conekta cash payment
    SPEI = "spei"  # Conekta bank transfer


class BillingInterval(str, Enum):
    """Billing frequency."""

    MONTHLY = "monthly"
    YEARLY = "yearly"
    ONE_TIME = "one_time"


class SubscriptionPlan(Base):
    """
    Subscription plan with multi-provider support.

    Each plan can have different IDs across providers (Conekta, Stripe, Polar).
    """

    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Multi-provider plan IDs (JSON: {"conekta": "plan_xxx", "stripe": "price_xxx", "polar": "product_xxx"})
    provider_plan_ids = Column(JSON, nullable=False, default=dict)

    # Pricing
    price_monthly = Column(Numeric(10, 2), nullable=True)  # USD/MXN monthly price
    price_yearly = Column(Numeric(10, 2), nullable=True)  # USD/MXN yearly price
    currency_usd = Column(String(3), default="USD")  # For Stripe/Polar
    currency_mxn = Column(String(3), default="MXN")  # For Conekta

    # Plan features and limits
    features = Column(JSON, nullable=False, default=list)  # ["SSO", "Advanced MFA", "Audit Logs"]
    limits = Column(JSON, nullable=False, default=dict)  # {"api_calls": 10000, "users": 50}

    # Metadata
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")

    def __repr__(self):
        return f"<SubscriptionPlan {self.name} (${self.price_monthly}/mo)>"

    def get_provider_plan_id(self, provider: PaymentProvider) -> Optional[str]:
        """Get plan ID for specific provider."""
        return self.provider_plan_ids.get(provider.value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "price_monthly": float(self.price_monthly) if self.price_monthly else None,
            "price_yearly": float(self.price_yearly) if self.price_yearly else None,
            "currency_usd": self.currency_usd,
            "currency_mxn": self.currency_mxn,
            "features": self.features,
            "limits": self.limits,
            "is_active": self.is_active,
            "is_popular": self.is_popular,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Subscription(Base):
    """
    Organization subscription with multi-provider support.

    Stores provider-specific IDs and metadata for Conekta, Stripe, or Polar.
    """

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)

    # Provider information
    provider = Column(String(20), nullable=False)  # conekta, stripe, polar
    provider_subscription_id = Column(String(255), nullable=False, unique=True)
    provider_customer_id = Column(String(255), nullable=False)

    # Subscription state
    status = Column(String(30), nullable=False, default=SubscriptionStatus.ACTIVE.value)
    billing_interval = Column(String(20), nullable=False, default=BillingInterval.MONTHLY.value)

    # Billing cycle
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)

    # Cancellation
    cancel_at_period_end = Column(Boolean, default=False)
    cancel_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)

    # Usage tracking
    usage_data = Column(JSON, default=dict)  # {"api_calls": 5000, "storage_gb": 10}

    # Provider-specific metadata
    provider_metadata = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription {self.id} ({self.provider}: {self.status})>"

    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status in [
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIALING.value,
        ]

    def days_until_renewal(self) -> int:
        """Calculate days until next billing cycle."""
        if self.current_period_end:
            delta = self.current_period_end - datetime.utcnow()
            return max(0, delta.days)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "plan_id": str(self.plan_id),
            "plan": self.plan.to_dict() if self.plan else None,
            "provider": self.provider,
            "status": self.status,
            "billing_interval": self.billing_interval,
            "current_period_start": self.current_period_start.isoformat()
            if self.current_period_start
            else None,
            "current_period_end": self.current_period_end.isoformat()
            if self.current_period_end
            else None,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "canceled_at": self.canceled_at.isoformat() if self.canceled_at else None,
            "usage_data": self.usage_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PaymentMethod(Base):
    """
    Stored payment method with multi-provider support.

    Stores tokenized payment methods (cards, bank accounts) from any provider.
    Never stores raw card numbers - only tokens and display info.
    """

    __tablename__ = "payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Provider information
    provider = Column(String(20), nullable=False)  # conekta, stripe, polar
    provider_payment_method_id = Column(String(255), nullable=False)
    provider_customer_id = Column(String(255), nullable=False)

    # Payment method details (for display only)
    type = Column(String(20), nullable=False)  # card, bank_account, oxxo, spei
    last4 = Column(String(4), nullable=True)  # Last 4 digits of card/account
    brand = Column(String(20), nullable=True)  # visa, mastercard, amex
    exp_month = Column(Integer, nullable=True)
    exp_year = Column(Integer, nullable=True)

    # Billing address (used for provider routing)
    billing_address = Column(JSON, nullable=True)  # {country, postal_code, city, line1, line2}

    # Status
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PaymentMethod {self.brand} ****{self.last4} ({self.provider})>"

    def get_billing_country(self) -> Optional[str]:
        """Extract country code from billing address."""
        if self.billing_address and isinstance(self.billing_address, dict):
            return self.billing_address.get("country")
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses (safe for client)."""
        return {
            "id": str(self.id),
            "type": self.type,
            "last4": self.last4,
            "brand": self.brand,
            "exp_month": self.exp_month,
            "exp_year": self.exp_year,
            "billing_address": self.billing_address,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Invoice(Base):
    """
    Invoice record for subscription billing.

    Tracks invoices from all providers (Conekta, Stripe, Polar).
    """

    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)

    # Provider information
    provider = Column(String(20), nullable=False)
    provider_invoice_id = Column(String(255), nullable=False, unique=True)

    # Invoice details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(30), nullable=False, default=InvoiceStatus.OPEN.value)

    # Payment information
    payment_intent_id = Column(String(255), nullable=True)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)

    # Billing period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Invoice URLs
    invoice_pdf_url = Column(String(500), nullable=True)
    hosted_invoice_url = Column(String(500), nullable=True)

    # Dates
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    # Line items (JSON array of {description, amount, quantity})
    line_items = Column(JSON, default=list)

    # Metadata
    invoice_metadata = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    payment_method = relationship("PaymentMethod")

    def __repr__(self):
        return f"<Invoice {self.provider_invoice_id} ({self.currency} {self.amount})>"

    def is_paid(self) -> bool:
        """Check if invoice has been paid."""
        return self.status == InvoiceStatus.PAID.value

    def is_overdue(self) -> bool:
        """Check if invoice is past due date."""
        if self.due_date and not self.is_paid():
            return datetime.utcnow() > self.due_date
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "subscription_id": str(self.subscription_id) if self.subscription_id else None,
            "provider": self.provider,
            "amount": float(self.amount),
            "currency": self.currency,
            "status": self.status,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "invoice_pdf_url": self.invoice_pdf_url,
            "hosted_invoice_url": self.hosted_invoice_url,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "line_items": self.line_items,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WebhookEvent(Base):
    """
    Webhook event log for idempotency and auditing.

    Prevents duplicate processing of webhooks from providers.
    """

    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Provider information
    provider = Column(String(20), nullable=False)
    provider_event_id = Column(String(255), nullable=False, unique=True)
    event_type = Column(String(100), nullable=False)

    # Processing status
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Event data (stored for debugging)
    payload = Column(JSON, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<WebhookEvent {self.provider}:{self.event_type} (processed={self.processed})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "provider": self.provider,
            "event_type": self.event_type,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
