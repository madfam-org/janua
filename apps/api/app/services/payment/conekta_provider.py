"""
Conekta payment provider for Mexican customers.

Supports:
- Credit/debit cards
- OXXO cash payments
- SPEI bank transfers
- Subscriptions in MXN (Mexican Pesos)
"""

from typing import Dict, Any, Optional, List
import hmac
import hashlib
from datetime import datetime
import conekta

from app.services.payment.base import (
    PaymentProvider,
    CustomerData,
    PaymentMethodData,
    SubscriptionData,
    WebhookEvent,
)


class ConektaProvider(PaymentProvider):
    """
    Conekta payment provider implementation for Mexican market.

    Conekta specializes in Mexican payment methods:
    - Cards (Visa, Mastercard, Amex)
    - OXXO (cash payment at convenience stores)
    - SPEI (instant bank transfers)
    - Subscriptions with recurring charges in MXN
    """

    def __init__(self, api_key: str, test_mode: bool = False):
        super().__init__(api_key, test_mode)

        # Configure Conekta SDK
        conekta.api_key = api_key
        conekta.api_version = "2.0.0"
        conekta.locale = "es"  # Spanish for Mexican customers

    @property
    def provider_name(self) -> str:
        return "conekta"

    # ============================================================================
    # Customer Management
    # ============================================================================

    async def create_customer(self, customer_data: CustomerData) -> Dict[str, Any]:
        """Create Conekta customer."""
        try:
            customer = conekta.Customer.create(
                {
                    "name": customer_data.name or customer_data.email,
                    "email": customer_data.email,
                    "phone": customer_data.phone,
                    "metadata": customer_data.metadata or {},
                }
            )

            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
                "created": customer.created_at,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta customer creation failed: {e.message}")

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve Conekta customer."""
        try:
            customer = conekta.Customer.find(customer_id)

            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
                "default_payment_source_id": customer.default_payment_source_id,
                "created": customer.created_at,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta customer retrieval failed: {e.message}")

    async def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update Conekta customer."""
        try:
            customer = conekta.Customer.find(customer_id)
            customer.update(updates)

            return {
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta customer update failed: {e.message}")

    async def delete_customer(self, customer_id: str) -> bool:
        """Delete Conekta customer."""
        try:
            customer = conekta.Customer.find(customer_id)
            customer.delete()
            return True

        except conekta.ConektaError as e:
            raise Exception(f"Conekta customer deletion failed: {e.message}")

    # ============================================================================
    # Payment Method Management
    # ============================================================================

    async def create_payment_method(
        self, customer_id: str, payment_method_data: PaymentMethodData
    ) -> Dict[str, Any]:
        """
        Attach payment method to Conekta customer.

        Supports:
        - Cards: token from Conekta.js
        - OXXO: type "oxxo_recurrent"
        - SPEI: type "spei"
        """
        try:
            customer = conekta.Customer.find(customer_id)

            # Create payment source
            source_params = {
                "type": payment_method_data.type,
                "token_id": payment_method_data.token,
            }

            payment_source = customer.createPaymentSource(source_params)

            # Extract payment method details based on type
            result = {
                "payment_method_id": payment_source.id,
                "type": payment_method_data.type,
            }

            if payment_method_data.type == "card":
                result.update(
                    {
                        "last4": payment_source.last4,
                        "brand": payment_source.brand,
                        "exp_month": payment_source.exp_month,
                        "exp_year": payment_source.exp_year,
                    }
                )

            return result

        except conekta.ConektaError as e:
            raise Exception(f"Conekta payment method creation failed: {e.message}")

    async def get_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Retrieve payment method details."""
        # Note: Conekta requires customer context to get payment source
        # This is a limitation - we'd need to store customer_id with payment_method
        raise NotImplementedError(
            "Conekta requires customer_id to retrieve payment source. "
            "Use list_payment_methods instead."
        )

    async def list_payment_methods(
        self, customer_id: str, type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List customer payment sources."""
        try:
            customer = conekta.Customer.find(customer_id)
            sources = customer.payment_sources

            result = []
            for source in sources:
                if type and source.type != type:
                    continue

                source_data = {
                    "payment_method_id": source.id,
                    "type": source.type,
                }

                if source.type == "card":
                    source_data.update(
                        {
                            "last4": source.last4,
                            "brand": source.brand,
                            "exp_month": source.exp_month,
                            "exp_year": source.exp_year,
                        }
                    )

                result.append(source_data)

            return result

        except conekta.ConektaError as e:
            raise Exception(f"Conekta payment methods listing failed: {e.message}")

    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """Delete payment source (requires customer context)."""
        # Note: Similar limitation as get_payment_method
        raise NotImplementedError(
            "Conekta requires customer_id to delete payment source. "
            "Store customer_id with payment_method_id to enable deletion."
        )

    async def set_default_payment_method(
        self, customer_id: str, payment_method_id: str
    ) -> Dict[str, Any]:
        """Set default payment source."""
        try:
            customer = conekta.Customer.find(customer_id)
            customer.update({"default_payment_source_id": payment_method_id})

            return {
                "customer_id": customer.id,
                "default_payment_source_id": payment_method_id,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta default payment method failed: {e.message}")

    # ============================================================================
    # Subscription Management
    # ============================================================================

    async def create_subscription(self, subscription_data: SubscriptionData) -> Dict[str, Any]:
        """
        Create Conekta subscription.

        Note: Conekta subscriptions are created on customers, not standalone.
        """
        try:
            customer = conekta.Customer.find(subscription_data.customer_id)

            sub_params = {
                "plan": subscription_data.plan_id,
            }

            # Add trial period if specified
            if subscription_data.trial_days:
                sub_params["trial_end"] = int(
                    (datetime.utcnow().timestamp() + (subscription_data.trial_days * 86400))
                )

            # Add card token if provided (for first charge)
            if subscription_data.payment_method_id:
                sub_params["card"] = subscription_data.payment_method_id

            subscription = customer.createSubscription(sub_params)

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "plan_id": subscription.plan_id,
                "billing_cycle_start": subscription.billing_cycle_start,
                "billing_cycle_end": subscription.billing_cycle_end,
                "trial_start": subscription.trial_start
                if hasattr(subscription, "trial_start")
                else None,
                "trial_end": subscription.trial_end if hasattr(subscription, "trial_end") else None,
                "created": subscription.created_at,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta subscription creation failed: {e.message}")

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Retrieve subscription (requires customer context in Conekta)."""
        # Note: Conekta subscriptions are nested under customers
        raise NotImplementedError(
            "Conekta requires customer_id to retrieve subscription. "
            "Store customer_id with subscription_id."
        )

    async def update_subscription(
        self, subscription_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update subscription (change plan, card, etc)."""
        # Note: Requires customer context
        raise NotImplementedError(
            "Conekta subscription updates require customer_id. "
            "Retrieve customer first, then update subscription."
        )

    async def cancel_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel subscription."""
        # Note: Requires customer context
        raise NotImplementedError(
            "Conekta subscription cancellation requires customer_id. "
            "Retrieve customer first, then cancel subscription."
        )

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Resume canceled subscription."""
        raise NotImplementedError("Conekta does not support resuming subscriptions.")

    # ============================================================================
    # Invoice Management
    # ============================================================================

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retrieve invoice (Conekta calls these 'charges')."""
        try:
            # In Conekta, charges are similar to invoices
            charge = conekta.Charge.find(invoice_id)

            return {
                "invoice_id": charge.id,
                "amount": self.parse_amount(charge.amount, "MXN"),
                "currency": charge.currency.upper(),
                "status": charge.status,
                "description": charge.description,
                "created": charge.created_at,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta invoice retrieval failed: {e.message}")

    async def list_invoices(self, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """List customer charges/invoices."""
        try:
            customer = conekta.Customer.find(customer_id)

            # Get charges from customer's subscription
            charges = []
            if hasattr(customer, "subscription") and customer.subscription:
                # Subscription charges would be here
                pass

            return charges

        except conekta.ConektaError as e:
            raise Exception(f"Conekta invoices listing failed: {e.message}")

    async def pay_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retry payment on failed charge."""
        raise NotImplementedError("Conekta charge retry not directly supported via API.")

    # ============================================================================
    # Webhook Handling
    # ============================================================================

    def verify_webhook_signature(self, payload: bytes, signature: str, webhook_secret: str) -> bool:
        """
        Verify Conekta webhook signature using HMAC SHA256.

        Conekta sends signature in X-Conekta-Signature header.
        """
        try:
            computed_signature = hmac.new(
                webhook_secret.encode(), payload, hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(computed_signature, signature)

        except Exception:
            return False

    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse Conekta webhook into standardized event."""
        return WebhookEvent(
            event_id=payload.get("id", ""),
            event_type=payload.get("type", ""),
            data=payload.get("data", {}),
            created_at=datetime.fromtimestamp(payload.get("created_at", 0)),
        )

    # ============================================================================
    # Plan Management
    # ============================================================================

    async def list_plans(self) -> List[Dict[str, Any]]:
        """List Conekta subscription plans."""
        try:
            plans = conekta.Plan.where()

            result = []
            for plan in plans:
                result.append(
                    {
                        "plan_id": plan.id,
                        "name": plan.name,
                        "amount": self.parse_amount(plan.amount, "MXN"),
                        "currency": "MXN",
                        "interval": plan.frequency,  # days, weeks, months
                        "interval_count": plan.frequency_count,
                    }
                )

            return result

        except conekta.ConektaError as e:
            raise Exception(f"Conekta plans listing failed: {e.message}")

    async def get_plan(self, plan_id: str) -> Dict[str, Any]:
        """Get plan details."""
        try:
            plan = conekta.Plan.find(plan_id)

            return {
                "plan_id": plan.id,
                "name": plan.name,
                "amount": self.parse_amount(plan.amount, "MXN"),
                "currency": "MXN",
                "interval": plan.frequency,
                "interval_count": plan.frequency_count,
                "trial_period_days": plan.trial_period_days,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta plan retrieval failed: {e.message}")

    # ============================================================================
    # Conekta-Specific Methods
    # ============================================================================

    def supports_payment_method_type(self, method_type: str) -> bool:
        """Conekta supports cards, OXXO, and SPEI."""
        return method_type in ["card", "oxxo", "oxxo_recurrent", "spei"]

    def get_supported_currencies(self) -> List[str]:
        """Conekta only supports MXN."""
        return ["MXN"]

    async def create_oxxo_charge(
        self, customer_id: str, amount: float, description: str, expires_at: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create OXXO cash payment (Mexican convenience store payment).

        Args:
            customer_id: Conekta customer ID
            amount: Amount in MXN
            description: Payment description
            expires_at: Unix timestamp when payment expires (default: 3 days)

        Returns:
            Dict with charge details and OXXO reference number
        """
        try:
            # Default expiration: 3 days from now
            if not expires_at:
                expires_at = int(datetime.utcnow().timestamp() + (3 * 86400))

            charge = conekta.Charge.create(
                {
                    "amount": self.format_amount(amount, "MXN"),
                    "currency": "MXN",
                    "description": description,
                    "customer_info": {
                        "customer_id": customer_id,
                    },
                    "cash": {
                        "type": "oxxo",
                        "expires_at": expires_at,
                    },
                }
            )

            return {
                "charge_id": charge.id,
                "oxxo_reference": charge.payment_method.reference,
                "expires_at": charge.payment_method.expires_at,
                "amount": self.parse_amount(charge.amount, "MXN"),
                "status": charge.status,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta OXXO charge creation failed: {e.message}")

    async def create_spei_charge(
        self, customer_id: str, amount: float, description: str, expires_at: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create SPEI bank transfer (Mexican instant bank transfer).

        Args:
            customer_id: Conekta customer ID
            amount: Amount in MXN
            description: Payment description
            expires_at: Unix timestamp when payment expires

        Returns:
            Dict with CLABE account number for transfer
        """
        try:
            # Default expiration: 1 day
            if not expires_at:
                expires_at = int(datetime.utcnow().timestamp() + 86400)

            charge = conekta.Charge.create(
                {
                    "amount": self.format_amount(amount, "MXN"),
                    "currency": "MXN",
                    "description": description,
                    "customer_info": {
                        "customer_id": customer_id,
                    },
                    "bank_transfer": {
                        "type": "spei",
                        "expires_at": expires_at,
                    },
                }
            )

            return {
                "charge_id": charge.id,
                "clabe": charge.payment_method.clabe,
                "bank_name": charge.payment_method.bank_name,
                "expires_at": charge.payment_method.expires_at,
                "amount": self.parse_amount(charge.amount, "MXN"),
                "status": charge.status,
            }

        except conekta.ConektaError as e:
            raise Exception(f"Conekta SPEI charge creation failed: {e.message}")
