"""
Payment Router Service

Intelligent routing service that selects the appropriate payment provider
based on customer location, transaction type, and business rules.

Routing Logic (with Stripe as Universal Fallback):
- Mexican customers (MX) → Conekta (local payment methods) → Stripe (fallback)
- Product purchases → Polar (digital products) → Stripe (fallback)
- Non-Mexican customers → Stripe (global payment methods)
- Stripe is the universal fallback for all provider failures
"""

import os
import logging
from typing import Dict, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

from app.services.payment.base import PaymentProvider
from app.services.payment.conekta_provider import ConektaProvider
from app.services.payment.stripe_provider import StripeProvider
from app.services.payment.polar_provider import PolarProvider
from app.services.payment.geolocation import GeolocationService


logger = logging.getLogger(__name__)


class TransactionType(str, Enum):
    """Transaction type for provider routing."""

    SUBSCRIPTION = "subscription"
    PRODUCT_PURCHASE = "product_purchase"
    ONE_TIME_PAYMENT = "one_time_payment"
    INVOICE_PAYMENT = "invoice_payment"


class ProviderName(str, Enum):
    """Supported payment provider names."""

    CONEKTA = "conekta"
    STRIPE = "stripe"
    POLAR = "polar"


class ProviderFallbackReason(str, Enum):
    """Reasons for provider fallback to Stripe."""

    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    PROVIDER_API_ERROR = "provider_api_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class PaymentRouter:
    """
    Intelligent payment provider router.

    Selects the appropriate payment provider based on:
    - Customer location (geolocation)
    - Transaction type (subscription, product, one-time)
    - Business rules and preferences
    """

    def __init__(
        self,
        geolocation_service: Optional[GeolocationService] = None,
        conekta_api_key: Optional[str] = None,
        stripe_api_key: Optional[str] = None,
        polar_api_key: Optional[str] = None,
        test_mode: bool = False,
    ):
        """
        Initialize payment router with provider credentials.

        Args:
            geolocation_service: GeolocationService instance
            conekta_api_key: Conekta API key (defaults to env var)
            stripe_api_key: Stripe API key (defaults to env var)
            polar_api_key: Polar API key (defaults to env var)
            test_mode: Enable test mode for all providers
        """
        self.geolocation = geolocation_service or GeolocationService()
        self.test_mode = test_mode

        # Initialize providers with API keys
        self.providers: Dict[str, PaymentProvider] = {}

        # Conekta (Mexican market)
        conekta_key = conekta_api_key or os.getenv("CONEKTA_API_KEY")
        if conekta_key:
            self.providers[ProviderName.CONEKTA] = ConektaProvider(
                api_key=conekta_key, test_mode=test_mode
            )

        # Stripe (International market)
        stripe_key = stripe_api_key or os.getenv("STRIPE_API_KEY")
        if stripe_key:
            self.providers[ProviderName.STRIPE] = StripeProvider(
                api_key=stripe_key, test_mode=test_mode
            )

        # Polar (Digital products)
        polar_key = polar_api_key or os.getenv("POLAR_API_KEY")
        if polar_key:
            self.providers[ProviderName.POLAR] = PolarProvider(
                api_key=polar_key, test_mode=test_mode
            )

    async def get_provider(
        self,
        transaction_type: TransactionType = TransactionType.SUBSCRIPTION,
        billing_address: Optional[Dict[str, str]] = None,
        user_country: Optional[str] = None,
        ip_address: Optional[str] = None,
        force_provider: Optional[ProviderName] = None,
        allow_fallback: bool = True,
    ) -> Tuple[PaymentProvider, Optional[Dict[str, Any]]]:
        """
        Select appropriate payment provider with Stripe as universal fallback.

        Routing Priority (with automatic fallback to Stripe):
        1. Force provider (if specified) - no fallback
        2. Product purchases → Polar (fallback to Stripe if unavailable)
        3. Mexican customers → Conekta (fallback to Stripe if unavailable)
        4. Non-Mexican customers → Stripe (direct)

        Fallback Behavior:
        - If Conekta unavailable for Mexican customer → use Stripe
        - If Polar unavailable for product purchase → use Stripe
        - Fallback events are logged for monitoring

        Args:
            transaction_type: Type of transaction
            billing_address: Customer billing address
            user_country: User's country from profile
            ip_address: User's IP address for geolocation
            force_provider: Force specific provider (override routing, no fallback)
            allow_fallback: Enable automatic fallback to Stripe (default: True)

        Returns:
            Tuple of (PaymentProvider instance, fallback_info dict or None)
            fallback_info contains: {
                "attempted_provider": str,
                "fallback_provider": "stripe",
                "reason": str,
                "timestamp": datetime
            }

        Raises:
            ValueError: If Stripe not configured and fallback needed
        """
        fallback_info = None

        # Priority 1: Force specific provider (no fallback)
        if force_provider:
            if force_provider not in self.providers:
                raise ValueError(f"Provider {force_provider} not configured")
            return self.providers[force_provider], None

        # Priority 2: Product purchases → Polar (with Stripe fallback)
        if transaction_type == TransactionType.PRODUCT_PURCHASE:
            if ProviderName.POLAR in self.providers:
                return self.providers[ProviderName.POLAR], None
            elif allow_fallback and ProviderName.STRIPE in self.providers:
                # Fallback to Stripe for product purchases
                fallback_info = self._create_fallback_info(
                    attempted_provider=ProviderName.POLAR,
                    reason=ProviderFallbackReason.PROVIDER_NOT_CONFIGURED,
                )
                logger.warning(
                    f"Polar unavailable for product purchase, falling back to Stripe. "
                    f"Reason: {fallback_info['reason']}"
                )
                return self.providers[ProviderName.STRIPE], fallback_info
            else:
                raise ValueError("Polar and Stripe providers not configured for product purchases")

        # Priority 3: Detect customer country
        country = await self.geolocation.detect_country(
            ip_address=ip_address,
            user_country=user_country,
            billing_country=billing_address.get("country") if billing_address else None,
        )

        # Priority 4: Mexican customers → Conekta (with Stripe fallback)
        is_mexican = self.geolocation.is_mexican_customer(
            country_code=country, billing_address=billing_address
        )

        if is_mexican:
            if ProviderName.CONEKTA in self.providers:
                return self.providers[ProviderName.CONEKTA], None
            elif allow_fallback and ProviderName.STRIPE in self.providers:
                # Fallback to Stripe for Mexican customers
                fallback_info = self._create_fallback_info(
                    attempted_provider=ProviderName.CONEKTA,
                    reason=ProviderFallbackReason.PROVIDER_NOT_CONFIGURED,
                )
                logger.warning(
                    f"Conekta unavailable for Mexican customer, falling back to Stripe. "
                    f"Country: {country}, Reason: {fallback_info['reason']}"
                )
                return self.providers[ProviderName.STRIPE], fallback_info
            else:
                raise ValueError(
                    "Conekta and Stripe providers not configured for Mexican customers"
                )

        # Priority 5: Non-Mexican customers → Stripe (direct, no fallback needed)
        if ProviderName.STRIPE not in self.providers:
            raise ValueError("Stripe provider not configured for international customers")
        return self.providers[ProviderName.STRIPE], None

    def _create_fallback_info(
        self, attempted_provider: ProviderName, reason: ProviderFallbackReason
    ) -> Dict[str, Any]:
        """Create fallback information for logging and monitoring."""
        return {
            "attempted_provider": attempted_provider,
            "fallback_provider": ProviderName.STRIPE,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_provider_name(
        self,
        transaction_type: TransactionType = TransactionType.SUBSCRIPTION,
        billing_address: Optional[Dict[str, str]] = None,
        user_country: Optional[str] = None,
        ip_address: Optional[str] = None,
        force_provider: Optional[ProviderName] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Get provider name with fallback information.

        Useful for displaying to user which provider will be used.

        Returns:
            Tuple of (provider_name string, fallback_info dict or None)
        """
        provider, fallback_info = await self.get_provider(
            transaction_type=transaction_type,
            billing_address=billing_address,
            user_country=user_country,
            ip_address=ip_address,
            force_provider=force_provider,
        )
        return provider.provider_name, fallback_info

    def get_available_providers(self) -> list[str]:
        """
        Get list of configured providers.

        Returns:
            List of provider names
        """
        return list(self.providers.keys())

    def is_provider_available(self, provider_name: ProviderName) -> bool:
        """
        Check if specific provider is configured.

        Args:
            provider_name: Provider to check

        Returns:
            True if provider is available
        """
        return provider_name in self.providers

    async def get_currency_for_customer(
        self,
        billing_address: Optional[Dict[str, str]] = None,
        user_country: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """
        Determine appropriate currency for customer.

        Uses geolocation service to map country to currency.

        Returns:
            Currency code (e.g., "MXN", "USD", "EUR")
        """
        country = await self.geolocation.detect_country(
            ip_address=ip_address,
            user_country=user_country,
            billing_country=billing_address.get("country") if billing_address else None,
        )

        return self.geolocation.get_currency_for_country(country)

    async def validate_routing(
        self,
        transaction_type: TransactionType,
        billing_address: Optional[Dict[str, str]] = None,
        user_country: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate routing logic and return detailed routing information.

        Useful for debugging and displaying routing decisions to admins.

        Returns:
            Dict with routing details:
            {
                "provider": "conekta",
                "country": "MX",
                "currency": "MXN",
                "transaction_type": "subscription",
                "routing_reason": "Mexican customer detected from billing address"
            }
        """
        # Detect country
        country = await self.geolocation.detect_country(
            ip_address=ip_address,
            user_country=user_country,
            billing_country=billing_address.get("country") if billing_address else None,
        )

        # Get currency
        currency = self.geolocation.get_currency_for_country(country)

        # Determine provider and reason
        is_mexican = self.geolocation.is_mexican_customer(
            country_code=country, billing_address=billing_address
        )

        if transaction_type == TransactionType.PRODUCT_PURCHASE:
            provider_name = ProviderName.POLAR
            reason = "Product purchase transaction type"
        elif is_mexican:
            provider_name = ProviderName.CONEKTA
            if billing_address and billing_address.get("country") == "MX":
                reason = "Mexican customer detected from billing address"
            elif user_country == "MX":
                reason = "Mexican customer detected from user profile"
            else:
                reason = "Mexican customer detected from IP geolocation"
        else:
            provider_name = ProviderName.STRIPE
            reason = f"International customer from {country}"

        return {
            "provider": provider_name,
            "country": country,
            "currency": currency,
            "transaction_type": transaction_type,
            "routing_reason": reason,
            "available_providers": self.get_available_providers(),
        }

    async def get_payment_methods_for_customer(
        self,
        billing_address: Optional[Dict[str, str]] = None,
        user_country: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get available payment methods for customer based on location.

        Returns:
            Dict with provider and available payment methods
        """
        provider, fallback_info = await self.get_provider(
            billing_address=billing_address, user_country=user_country, ip_address=ip_address
        )

        currency = await self.get_currency_for_customer(
            billing_address=billing_address, user_country=user_country, ip_address=ip_address
        )

        # Define available payment methods per provider
        payment_methods = {
            ProviderName.CONEKTA: {
                "provider": "conekta",
                "currency": "MXN",
                "methods": ["card", "oxxo", "spei"],
                "cards": ["visa", "mastercard", "amex"],
                "local_methods": [
                    {
                        "type": "oxxo",
                        "name": "OXXO",
                        "description": "Pay cash at any OXXO store",
                        "processing_time": "instant",
                    },
                    {
                        "type": "spei",
                        "name": "SPEI",
                        "description": "Instant bank transfer",
                        "processing_time": "instant",
                    },
                ],
            },
            ProviderName.STRIPE: {
                "provider": "stripe",
                "currency": currency,
                "methods": ["card", "ach", "sepa", "ideal", "bancontact", "giropay"],
                "cards": ["visa", "mastercard", "amex", "discover", "diners", "jcb"],
                "local_methods": [],  # Varies by country
            },
            ProviderName.POLAR: {
                "provider": "polar",
                "currency": "USD",
                "methods": ["card"],
                "cards": ["visa", "mastercard", "amex"],
                "local_methods": [],
            },
        }

        return payment_methods.get(
            provider.provider_name, {"provider": provider.provider_name, "methods": ["card"]}
        )
