"""
Stripe payment provider for international customers.

Supports:
- Credit/debit cards globally
- ACH, SEPA, and other local payment methods
- Multi-currency subscriptions
- Robust subscription management
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import stripe

from app.services.payment.base import (
    PaymentProvider,
    CustomerData,
    PaymentMethodData,
    SubscriptionData,
    WebhookEvent,
)


class StripeProvider(PaymentProvider):
    """
    Stripe payment provider implementation for international customers.

    Stripe provides:
    - Global card processing
    - 135+ currencies support
    - Local payment methods (ACH, SEPA, iDEAL, etc)
    - Advanced subscription management
    - Strong SCA (3D Secure 2) support
    """

    def __init__(self, api_key: str, test_mode: bool = False):
        super().__init__(api_key, test_mode)

        # Configure Stripe SDK
        stripe.api_key = api_key
        stripe.api_version = "2023-10-16"  # Pin API version for stability

    @property
    def provider_name(self) -> str:
        return "stripe"

    # ============================================================================
    # Customer Management
    # ============================================================================

    async def create_customer(self, customer_data: CustomerData) -> Dict[str, Any]:
        """Create Stripe customer."""
        try:
            customer = stripe.Customer.create(
                name=customer_data.name,
                email=customer_data.email,
                phone=customer_data.phone,
                metadata=customer_data.metadata or {},
            )

            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
                "created": customer.created,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe customer creation failed: {str(e)}")

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve Stripe customer."""
        try:
            customer = stripe.Customer.retrieve(customer_id)

            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
                "default_source": customer.default_source,
                "invoice_settings": customer.invoice_settings,
                "created": customer.created,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe customer retrieval failed: {str(e)}")

    async def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update Stripe customer."""
        try:
            customer = stripe.Customer.modify(customer_id, **updates)

            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe customer update failed: {str(e)}")

    async def delete_customer(self, customer_id: str) -> bool:
        """Delete Stripe customer."""
        try:
            stripe.Customer.delete(customer_id)
            return True

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe customer deletion failed: {str(e)}")

    # ============================================================================
    # Payment Method Management
    # ============================================================================

    async def create_payment_method(
        self, customer_id: str, payment_method_data: PaymentMethodData
    ) -> Dict[str, Any]:
        """
        Attach payment method to Stripe customer.

        Args:
            customer_id: Stripe customer ID
            payment_method_data: Payment method with token from Stripe.js
        """
        try:
            # Attach payment method to customer
            payment_method = stripe.PaymentMethod.attach(
                payment_method_data.token,
                customer=customer_id,
            )

            # Extract details
            result = {
                "payment_method_id": payment_method.id,
                "type": payment_method.type,
            }

            if payment_method.type == "card":
                card = payment_method.card
                result.update(
                    {
                        "last4": card.last4,
                        "brand": card.brand,
                        "exp_month": card.exp_month,
                        "exp_year": card.exp_year,
                        "country": card.country,
                    }
                )

            elif payment_method.type == "us_bank_account":
                bank = payment_method.us_bank_account
                result.update(
                    {
                        "last4": bank.last4,
                        "bank_name": bank.bank_name,
                        "account_type": bank.account_type,
                    }
                )

            elif payment_method.type == "sepa_debit":
                sepa = payment_method.sepa_debit
                result.update(
                    {
                        "last4": sepa.last4,
                        "bank_code": sepa.bank_code,
                        "country": sepa.country,
                    }
                )

            return result

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe payment method creation failed: {str(e)}")

    async def get_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Retrieve payment method details."""
        try:
            pm = stripe.PaymentMethod.retrieve(payment_method_id)

            result = {
                "payment_method_id": pm.id,
                "type": pm.type,
                "created": pm.created,
            }

            if pm.type == "card":
                result.update(
                    {
                        "last4": pm.card.last4,
                        "brand": pm.card.brand,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year,
                    }
                )

            return result

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe payment method retrieval failed: {str(e)}")

    async def list_payment_methods(
        self, customer_id: str, type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List customer payment methods."""
        try:
            params = {"customer": customer_id, "limit": 100}
            if type:
                params["type"] = type

            payment_methods = stripe.PaymentMethod.list(**params)

            result = []
            for pm in payment_methods.data:
                pm_data = {
                    "payment_method_id": pm.id,
                    "type": pm.type,
                }

                if pm.type == "card":
                    pm_data.update(
                        {
                            "last4": pm.card.last4,
                            "brand": pm.card.brand,
                            "exp_month": pm.card.exp_month,
                            "exp_year": pm.card.exp_year,
                        }
                    )

                result.append(pm_data)

            return result

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe payment methods listing failed: {str(e)}")

    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """Detach payment method."""
        try:
            stripe.PaymentMethod.detach(payment_method_id)
            return True

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe payment method deletion failed: {str(e)}")

    async def set_default_payment_method(
        self, customer_id: str, payment_method_id: str
    ) -> Dict[str, Any]:
        """Set default payment method."""
        try:
            customer = stripe.Customer.modify(
                customer_id, invoice_settings={"default_payment_method": payment_method_id}
            )

            return {
                "customer_id": customer.id,
                "default_payment_method": payment_method_id,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe default payment method failed: {str(e)}")

    # ============================================================================
    # Subscription Management
    # ============================================================================

    async def create_subscription(self, subscription_data: SubscriptionData) -> Dict[str, Any]:
        """Create Stripe subscription."""
        try:
            params = {
                "customer": subscription_data.customer_id,
                "items": [{"price": subscription_data.plan_id}],
                "metadata": subscription_data.metadata or {},
            }

            # Add default payment method if provided
            if subscription_data.payment_method_id:
                params["default_payment_method"] = subscription_data.payment_method_id

            # Add trial period if specified
            if subscription_data.trial_days:
                params["trial_period_days"] = subscription_data.trial_days

            # Enable automatic tax calculation
            params["automatic_tax"] = {"enabled": True}

            subscription = stripe.Subscription.create(**params)

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "trial_start": subscription.trial_start if subscription.trial_start else None,
                "trial_end": subscription.trial_end if subscription.trial_end else None,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "created": subscription.created,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe subscription creation failed: {str(e)}")

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Retrieve subscription details."""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)

            return {
                "subscription_id": subscription.id,
                "customer_id": subscription.customer,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "trial_start": subscription.trial_start,
                "trial_end": subscription.trial_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at,
                "items": [
                    {
                        "price_id": item.price.id,
                        "quantity": item.quantity,
                    }
                    for item in subscription.items.data
                ],
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe subscription retrieval failed: {str(e)}")

    async def update_subscription(
        self, subscription_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update subscription (change plan, quantity, etc)."""
        try:
            subscription = stripe.Subscription.modify(subscription_id, **updates)

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe subscription update failed: {str(e)}")

    async def cancel_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel subscription."""
        try:
            if cancel_at_period_end:
                # Cancel at end of billing period
                subscription = stripe.Subscription.modify(
                    subscription_id, cancel_at_period_end=True
                )
            else:
                # Cancel immediately
                subscription = stripe.Subscription.delete(subscription_id)

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe subscription cancellation failed: {str(e)}")

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Resume a canceled subscription."""
        try:
            subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": False,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe subscription resume failed: {str(e)}")

    # ============================================================================
    # Invoice Management
    # ============================================================================

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retrieve invoice details."""
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)

            return {
                "invoice_id": invoice.id,
                "customer_id": invoice.customer,
                "subscription_id": invoice.subscription,
                "amount": self.parse_amount(invoice.amount_due, invoice.currency.upper()),
                "currency": invoice.currency.upper(),
                "status": invoice.status,
                "invoice_pdf": invoice.invoice_pdf,
                "hosted_invoice_url": invoice.hosted_invoice_url,
                "due_date": invoice.due_date,
                "paid": invoice.paid,
                "created": invoice.created,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe invoice retrieval failed: {str(e)}")

    async def list_invoices(self, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """List customer invoices."""
        try:
            invoices = stripe.Invoice.list(customer=customer_id, limit=limit)

            result = []
            for invoice in invoices.data:
                result.append(
                    {
                        "invoice_id": invoice.id,
                        "amount": self.parse_amount(invoice.amount_due, invoice.currency.upper()),
                        "currency": invoice.currency.upper(),
                        "status": invoice.status,
                        "invoice_pdf": invoice.invoice_pdf,
                        "due_date": invoice.due_date,
                        "paid": invoice.paid,
                        "created": invoice.created,
                    }
                )

            return result

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe invoices listing failed: {str(e)}")

    async def pay_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Manually pay invoice (retry payment)."""
        try:
            invoice = stripe.Invoice.pay(invoice_id)

            return {
                "invoice_id": invoice.id,
                "status": invoice.status,
                "paid": invoice.paid,
                "paid_at": invoice.status_transitions.paid_at if invoice.paid else None,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe invoice payment failed: {str(e)}")

    # ============================================================================
    # Webhook Handling
    # ============================================================================

    def verify_webhook_signature(self, payload: bytes, signature: str, webhook_secret: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            stripe.Webhook.construct_event(payload, signature, webhook_secret)
            return True

        except stripe.error.SignatureVerificationError:
            return False

    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse Stripe webhook into standardized event."""
        return WebhookEvent(
            event_id=payload.get("id", ""),
            event_type=payload.get("type", ""),
            data=payload.get("data", {}).get("object", {}),
            created_at=datetime.fromtimestamp(payload.get("created", 0)),
        )

    # ============================================================================
    # Plan/Price Management
    # ============================================================================

    async def list_plans(self) -> List[Dict[str, Any]]:
        """List Stripe prices (modern way to handle plans)."""
        try:
            prices = stripe.Price.list(active=True, limit=100)

            result = []
            for price in prices.data:
                result.append(
                    {
                        "plan_id": price.id,
                        "product_id": price.product,
                        "amount": self.parse_amount(price.unit_amount, price.currency.upper())
                        if price.unit_amount
                        else None,
                        "currency": price.currency.upper(),
                        "interval": price.recurring.interval if price.recurring else None,
                        "interval_count": price.recurring.interval_count
                        if price.recurring
                        else None,
                    }
                )

            return result

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe plans listing failed: {str(e)}")

    async def get_plan(self, plan_id: str) -> Dict[str, Any]:
        """Get price/plan details."""
        try:
            price = stripe.Price.retrieve(plan_id)

            return {
                "plan_id": price.id,
                "product_id": price.product,
                "amount": self.parse_amount(price.unit_amount, price.currency.upper())
                if price.unit_amount
                else None,
                "currency": price.currency.upper(),
                "interval": price.recurring.interval if price.recurring else None,
                "interval_count": price.recurring.interval_count if price.recurring else None,
                "trial_period_days": price.recurring.trial_period_days if price.recurring else None,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe plan retrieval failed: {str(e)}")

    # ============================================================================
    # Stripe-Specific Methods
    # ============================================================================

    def supports_payment_method_type(self, method_type: str) -> bool:
        """Stripe supports many payment method types."""
        supported_types = [
            "card",
            "us_bank_account",
            "sepa_debit",
            "ideal",
            "giropay",
            "sofort",
            "bancontact",
            "eps",
            "p24",
            "alipay",
            "wechat_pay",
        ]
        return method_type in supported_types

    def get_supported_currencies(self) -> List[str]:
        """Stripe supports 135+ currencies."""
        # Return most common ones (full list available in Stripe docs)
        return [
            "USD",
            "EUR",
            "GBP",
            "CAD",
            "AUD",
            "JPY",
            "CNY",
            "INR",
            "BRL",
            "MXN",
            "CHF",
            "SEK",
            "NOK",
            "DKK",
            "PLN",
            "CZK",
            "HUF",
            "RON",
        ]

    async def create_setup_intent(self, customer_id: str) -> Dict[str, Any]:
        """
        Create SetupIntent for saving payment method without charge.

        Used for adding payment methods via Stripe Elements.
        """
        try:
            setup_intent = stripe.SetupIntent.create(
                customer=customer_id,
                payment_method_types=["card"],
            )

            return {
                "client_secret": setup_intent.client_secret,
                "setup_intent_id": setup_intent.id,
                "status": setup_intent.status,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe setup intent creation failed: {str(e)}")

    async def create_payment_intent(
        self,
        customer_id: str,
        amount: float,
        currency: str,
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create PaymentIntent for one-time payment.

        Used for non-subscription charges.
        """
        try:
            params = {
                "customer": customer_id,
                "amount": self.format_amount(amount, currency),
                "currency": currency.lower(),
                "automatic_payment_methods": {"enabled": True},
            }

            if payment_method_id:
                params["payment_method"] = payment_method_id
                params["confirm"] = True

            if description:
                params["description"] = description

            payment_intent = stripe.PaymentIntent.create(**params)

            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "status": payment_intent.status,
                "amount": self.parse_amount(payment_intent.amount, currency),
                "currency": payment_intent.currency.upper(),
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe payment intent creation failed: {str(e)}")
