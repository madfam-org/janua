"""
Base payment provider interface for multi-provider support.

Defines the contract that all payment providers (Conekta, Stripe, Polar) must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CustomerData:
    """Customer information for provider customer creation."""

    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PaymentMethodData:
    """Payment method information."""

    token: str  # Provider-specific token from client-side SDK
    type: str  # card, bank_account, oxxo, spei
    billing_address: Optional[Dict[str, str]] = None  # {country, postal_code, city, line1}
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SubscriptionData:
    """Subscription creation parameters."""

    customer_id: str  # Provider customer ID
    plan_id: str  # Provider plan/price ID
    payment_method_id: Optional[str] = None  # Provider payment method ID
    trial_days: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WebhookEvent:
    """Standardized webhook event data."""

    event_id: str
    event_type: str
    data: Dict[str, Any]
    created_at: datetime


class PaymentProvider(ABC):
    """
    Abstract base class for payment providers.

    All payment providers (Conekta, Stripe, Polar) must implement this interface
    to ensure consistent behavior across different payment processors.
    """

    def __init__(self, api_key: str, test_mode: bool = False):
        """
        Initialize payment provider.

        Args:
            api_key: Provider API key
            test_mode: Whether to use test/sandbox mode
        """
        self.api_key = api_key
        self.test_mode = test_mode

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name (conekta, stripe, polar)."""

    # ============================================================================
    # Customer Management
    # ============================================================================

    @abstractmethod
    async def create_customer(self, customer_data: CustomerData) -> Dict[str, Any]:
        """
        Create a customer in the payment provider.

        Args:
            customer_data: Customer information

        Returns:
            Dict with customer_id and provider-specific data

        Example:
            {
                "customer_id": "cus_abc123",
                "email": "user@example.com",
                "created": 1234567890
            }
        """

    @abstractmethod
    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Retrieve customer details.

        Args:
            customer_id: Provider customer ID

        Returns:
            Customer details dict
        """

    @abstractmethod
    async def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update customer information.

        Args:
            customer_id: Provider customer ID
            updates: Fields to update

        Returns:
            Updated customer dict
        """

    @abstractmethod
    async def delete_customer(self, customer_id: str) -> bool:
        """
        Delete a customer.

        Args:
            customer_id: Provider customer ID

        Returns:
            True if successful
        """

    # ============================================================================
    # Payment Method Management
    # ============================================================================

    @abstractmethod
    async def create_payment_method(
        self, customer_id: str, payment_method_data: PaymentMethodData
    ) -> Dict[str, Any]:
        """
        Attach a payment method to customer.

        Args:
            customer_id: Provider customer ID
            payment_method_data: Payment method details

        Returns:
            Dict with payment_method_id and details

        Example:
            {
                "payment_method_id": "pm_abc123",
                "type": "card",
                "last4": "4242",
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2025
            }
        """

    @abstractmethod
    async def get_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """
        Retrieve payment method details.

        Args:
            payment_method_id: Provider payment method ID

        Returns:
            Payment method dict
        """

    @abstractmethod
    async def list_payment_methods(
        self, customer_id: str, type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List customer's payment methods.

        Args:
            customer_id: Provider customer ID
            type: Optional filter by type (card, bank_account)

        Returns:
            List of payment method dicts
        """

    @abstractmethod
    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """
        Detach/delete a payment method.

        Args:
            payment_method_id: Provider payment method ID

        Returns:
            True if successful
        """

    @abstractmethod
    async def set_default_payment_method(
        self, customer_id: str, payment_method_id: str
    ) -> Dict[str, Any]:
        """
        Set default payment method for customer.

        Args:
            customer_id: Provider customer ID
            payment_method_id: Provider payment method ID

        Returns:
            Updated customer dict
        """

    # ============================================================================
    # Subscription Management
    # ============================================================================

    @abstractmethod
    async def create_subscription(self, subscription_data: SubscriptionData) -> Dict[str, Any]:
        """
        Create a subscription.

        Args:
            subscription_data: Subscription parameters

        Returns:
            Dict with subscription details

        Example:
            {
                "subscription_id": "sub_abc123",
                "status": "active",
                "current_period_start": 1234567890,
                "current_period_end": 1237159890,
                "trial_end": 1235777890
            }
        """

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Retrieve subscription details.

        Args:
            subscription_id: Provider subscription ID

        Returns:
            Subscription dict
        """

    @abstractmethod
    async def update_subscription(
        self, subscription_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update subscription (change plan, quantity, etc).

        Args:
            subscription_id: Provider subscription ID
            updates: Fields to update (plan_id, quantity, etc)

        Returns:
            Updated subscription dict
        """

    @abstractmethod
    async def cancel_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Provider subscription ID
            cancel_at_period_end: If True, cancel at end of billing period

        Returns:
            Updated subscription dict
        """

    @abstractmethod
    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Resume a canceled subscription.

        Args:
            subscription_id: Provider subscription ID

        Returns:
            Updated subscription dict
        """

    # ============================================================================
    # Invoice Management
    # ============================================================================

    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Retrieve invoice details.

        Args:
            invoice_id: Provider invoice ID

        Returns:
            Invoice dict with amount, status, line items, etc
        """

    @abstractmethod
    async def list_invoices(self, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List customer invoices.

        Args:
            customer_id: Provider customer ID
            limit: Maximum number of invoices to return

        Returns:
            List of invoice dicts
        """

    @abstractmethod
    async def pay_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Manually pay an invoice (retry payment).

        Args:
            invoice_id: Provider invoice ID

        Returns:
            Updated invoice dict
        """

    # ============================================================================
    # Webhook Handling
    # ============================================================================

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str, webhook_secret: str) -> bool:
        """
        Verify webhook signature for security.

        Args:
            payload: Raw webhook payload
            signature: Signature header from webhook
            webhook_secret: Webhook signing secret

        Returns:
            True if signature is valid
        """

    @abstractmethod
    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Parse webhook payload into standardized event.

        Args:
            payload: Webhook payload dict

        Returns:
            WebhookEvent with standardized structure
        """

    # ============================================================================
    # Plan/Price Management
    # ============================================================================

    @abstractmethod
    async def list_plans(self) -> List[Dict[str, Any]]:
        """
        List available subscription plans/prices.

        Returns:
            List of plan dicts
        """

    @abstractmethod
    async def get_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Get plan/price details.

        Args:
            plan_id: Provider plan/price ID

        Returns:
            Plan dict
        """

    # ============================================================================
    # Utility Methods
    # ============================================================================

    def supports_payment_method_type(self, method_type: str) -> bool:
        """
        Check if provider supports payment method type.

        Args:
            method_type: Payment method type (card, bank_account, oxxo, spei)

        Returns:
            True if supported
        """
        # Override in subclass for provider-specific support
        return method_type in ["card", "bank_account"]

    def get_supported_currencies(self) -> List[str]:
        """
        Get list of supported currencies.

        Returns:
            List of currency codes (USD, MXN, EUR, etc)
        """
        # Override in subclass
        return ["USD"]

    def format_amount(self, amount: float, currency: str) -> int:
        """
        Format amount for provider API (most use cents/smallest unit).

        Args:
            amount: Amount in currency units (e.g., 19.99 USD)
            currency: Currency code

        Returns:
            Amount in smallest unit (e.g., 1999 cents)
        """
        # Most providers use cents/centavos
        return int(amount * 100)

    def parse_amount(self, amount: int, currency: str) -> float:
        """
        Parse amount from provider API (convert from smallest unit).

        Args:
            amount: Amount in smallest unit (e.g., 1999 cents)
            currency: Currency code

        Returns:
            Amount in currency units (e.g., 19.99 USD)
        """
        return amount / 100.0
