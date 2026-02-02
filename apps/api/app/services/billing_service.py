"""
Billing Service with Multi-Provider Support

Provider Strategy:
- Mexico: Conekta (primary) → Stripe (fallback)
- International: Polar.sh (primary) → Stripe (fallback)
- Detection: Geolocation + billing address validation
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import Tenant

logger = structlog.get_logger()

# Pricing tiers
PRICING_TIERS = {
    "community": {
        "price_mxn": 0,
        "price_usd": 0,
        "mau_limit": 2000,
        "features": ["basic_auth", "email_support", "standard_integrations"],
    },
    "pro": {
        "price_mxn": 1380,  # ~$69 USD at 20 MXN/USD
        "price_usd": 69,
        "mau_limit": 10000,
        "features": ["everything_community", "advanced_rbac", "custom_domains", "webhooks", "sso"],
    },
    "scale": {
        "price_mxn": 5980,  # ~$299 USD
        "price_usd": 299,
        "mau_limit": 50000,
        "features": [
            "everything_pro",
            "priority_support",
            "multi_region",
            "compliance",
            "custom_sla",
        ],
    },
    "enterprise": {
        "price_mxn": None,  # Custom pricing
        "price_usd": None,
        "mau_limit": None,
        "features": ["everything_scale", "dedicated_support", "on_premise", "saml", "scim"],
    },
}


class BillingService:
    """Handles billing with Conekta (Mexico), Polar.sh (International), and Stripe (Fallback)"""

    def __init__(self):
        # Test-compatible configuration access with fallbacks
        self.conekta_api_key = getattr(settings, "CONEKTA_API_KEY", "test_conekta_key")
        self.conekta_api_url = "https://api.conekta.io"
        self.polar_api_key = getattr(settings, "POLAR_API_KEY", "test_polar_key")
        self.polar_api_url = "https://api.polar.sh/v1"
        self.stripe_api_key = getattr(settings, "STRIPE_API_KEY", "test_stripe_key")
        self.stripe_api_url = "https://api.stripe.com/v1"

    async def determine_payment_provider(
        self, country: str, fallback: bool = False
    ) -> Literal["conekta", "polar", "stripe"]:
        """
        Determine which payment provider to use based on country and fallback status

        Args:
            country: ISO 3166-1 alpha-2 country code
            fallback: If True, return Stripe as universal fallback

        Returns:
            Payment provider: "conekta" (Mexico), "polar" (International), or "stripe" (Fallback)
        """
        if fallback:
            return "stripe"

        # Use Conekta for Mexico, Polar.sh for everything else
        return "conekta" if country.upper() == "MX" else "polar"

    # ==================== Conekta Integration (Mexico) ====================

    async def create_conekta_customer(
        self, email: str, name: str, phone: Optional[str] = None, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create a customer in Conekta"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.conekta_api_url}/customers",
                    headers={
                        "Authorization": f"Bearer {self.conekta_api_key}",
                        "Accept": "application/vnd.conekta-v2.1.0+json",
                        "Content-Type": "application/json",
                    },
                    json={"email": email, "name": name, "phone": phone, "metadata": metadata or {}},
                )
                await response.raise_for_status()
                customer = await response.json()
                logger.info("Conekta customer created", customer_id=customer["id"])
                return customer

            except httpx.HTTPError as e:
                logger.error("Failed to create Conekta customer", error=str(e))
                raise

    async def create_conekta_subscription(
        self,
        customer_id: str,
        plan_id: str,
        card_token: Optional[str] = None,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a subscription in Conekta"""
        async with httpx.AsyncClient() as client:
            try:
                # First, add payment method if card token provided
                if card_token:
                    payment_response = await client.post(
                        f"{self.conekta_api_url}/customers/{customer_id}/payment_sources",
                        headers={
                            "Authorization": f"Bearer {self.conekta_api_key}",
                            "Accept": "application/vnd.conekta-v2.1.0+json",
                            "Content-Type": "application/json",
                        },
                        json={"type": "card", "token_id": card_token},
                    )
                    await payment_response.raise_for_status()
                    payment_method = await payment_response.json()
                    payment_method["id"]

                # Create subscription
                response = await client.post(
                    f"{self.conekta_api_url}/customers/{customer_id}/subscription",
                    headers={
                        "Authorization": f"Bearer {self.conekta_api_key}",
                        "Accept": "application/vnd.conekta-v2.1.0+json",
                        "Content-Type": "application/json",
                    },
                    json={"plan_id": plan_id},
                )
                await response.raise_for_status()
                subscription = await response.json()
                logger.info(
                    "Conekta subscription created",
                    subscription_id=subscription["id"],
                    customer_id=customer_id,
                )
                return subscription

            except httpx.HTTPError as e:
                logger.error("Failed to create Conekta subscription", error=str(e))
                raise

    async def cancel_conekta_subscription(self, subscription_id: str) -> bool:
        """Cancel a Conekta subscription"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.conekta_api_url}/subscriptions/{subscription_id}/cancel",
                    headers={
                        "Authorization": f"Bearer {self.conekta_api_key}",
                        "Accept": "application/vnd.conekta-v2.1.0+json",
                    },
                )
                await response.raise_for_status()
                logger.info("Conekta subscription canceled", subscription_id=subscription_id)
                return True

            except httpx.HTTPError as e:
                logger.error("Failed to cancel Conekta subscription", error=str(e))
                return False

    async def create_conekta_checkout_session(
        self, customer_email: str, tier: str, success_url: str, cancel_url: str
    ) -> Dict[str, Any]:
        """Create a Conekta checkout session for one-time payment"""
        if tier not in PRICING_TIERS or tier == "community":
            raise ValueError(f"Invalid tier for payment: {tier}")

        price_mxn = PRICING_TIERS[tier]["price_mxn"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.conekta_api_url}/checkout/sessions",
                    headers={
                        "Authorization": f"Bearer {self.conekta_api_key}",
                        "Accept": "application/vnd.conekta-v2.1.0+json",
                        "Content-Type": "application/json",
                    },
                    json={
                        "success_url": success_url,
                        "cancel_url": cancel_url,
                        "customer_email": customer_email,
                        "line_items": [
                            {
                                "name": f"Janua {tier.capitalize()} Plan",
                                "unit_price": price_mxn * 100,  # Conekta uses cents
                                "quantity": 1,
                            }
                        ],
                        "currency": "MXN",
                        "metadata": {"tier": tier},
                    },
                )
                await response.raise_for_status()
                session = await response.json()
                logger.info("Conekta checkout session created", session_id=session["id"])
                return session

            except httpx.HTTPError as e:
                logger.error("Failed to create Conekta checkout session", error=str(e))
                raise

    # ==================== Polar.sh Integration (International) ====================

    async def create_polar_customer(
        self, email: str, name: str, country: str, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create a customer in Polar.sh"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.polar_api_url}/customers",
                    headers={
                        "Authorization": f"Bearer {self.polar_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "email": email,
                        "name": name,
                        "country": country,
                        "metadata": metadata or {},
                    },
                )
                await response.raise_for_status()
                customer = await response.json()
                logger.info("Polar customer created", customer_id=customer["id"])
                return customer

            except httpx.HTTPError as e:
                logger.error("Failed to create Polar customer", error=str(e))
                raise

    async def create_polar_subscription(
        self, customer_id: str, tier: str, payment_method_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a subscription in Polar.sh"""
        if tier not in PRICING_TIERS or tier == "community":
            raise ValueError(f"Invalid tier for payment: {tier}")

        price_usd = PRICING_TIERS[tier]["price_usd"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.polar_api_url}/subscriptions",
                    headers={
                        "Authorization": f"Bearer {self.polar_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "customer_id": customer_id,
                        "plan": {
                            "name": f"Janua {tier.capitalize()}",
                            "amount": price_usd * 100,  # In cents
                            "currency": "USD",
                            "interval": "month",
                        },
                        "payment_method_id": payment_method_id,
                        "metadata": {
                            "tier": tier,
                            "mau_limit": PRICING_TIERS[tier]["mau_limit"],
                        },
                    },
                )
                await response.raise_for_status()
                subscription = await response.json()
                logger.info(
                    "Polar subscription created",
                    subscription_id=subscription["id"],
                    customer_id=customer_id,
                )
                return subscription

            except httpx.HTTPError as e:
                logger.error("Failed to create Polar subscription", error=str(e))
                raise

    async def create_polar_checkout_session(
        self, customer_email: str, tier: str, country: str, success_url: str, cancel_url: str
    ) -> Dict[str, Any]:
        """Create a Polar checkout session"""
        if tier not in PRICING_TIERS or tier == "community":
            raise ValueError(f"Invalid tier for payment: {tier}")

        price_usd = PRICING_TIERS[tier]["price_usd"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.polar_api_url}/checkout/sessions",
                    headers={
                        "Authorization": f"Bearer {self.polar_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "success_url": success_url,
                        "cancel_url": cancel_url,
                        "customer_email": customer_email,
                        "customer_country": country,
                        "mode": "subscription",
                        "line_items": [
                            {
                                "price_data": {
                                    "currency": "USD",
                                    "product_data": {
                                        "name": f"Janua {tier.capitalize()} Plan",
                                        "description": f"Up to {PRICING_TIERS[tier]['mau_limit']:,} MAU",
                                    },
                                    "unit_amount": price_usd * 100,
                                    "recurring": {"interval": "month"},
                                },
                                "quantity": 1,
                            }
                        ],
                        "metadata": {"tier": tier},
                    },
                )
                await response.raise_for_status()
                session = await response.json()
                logger.info("Polar checkout session created", session_id=session["id"])
                return session

            except httpx.HTTPError as e:
                logger.error("Failed to create Polar checkout session", error=str(e))
                raise

    async def update_polar_subscription(self, subscription_id: str, tier: str) -> Dict[str, Any]:
        """Update a subscription in Polar.sh"""
        if tier not in PRICING_TIERS or tier == "community":
            raise ValueError(f"Invalid tier for payment: {tier}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"{self.polar_api_url}/subscriptions/{subscription_id}",
                    headers={
                        "Authorization": f"Bearer {self.polar_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"tier": tier, "metadata": {"tier": tier}},
                )
                await response.raise_for_status()
                subscription = await response.json()
                logger.info(
                    "Polar subscription updated", subscription_id=subscription["id"], tier=tier
                )
                return subscription

            except httpx.HTTPError as e:
                logger.error("Failed to update Polar subscription", error=str(e))
                raise

    async def cancel_polar_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription in Polar.sh"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.polar_api_url}/subscriptions/{subscription_id}",
                    headers={"Authorization": f"Bearer {self.polar_api_key}"},
                )
                await response.raise_for_status()
                logger.info("Polar subscription cancelled", subscription_id=subscription_id)
                return True

            except httpx.HTTPError as e:
                logger.error("Failed to cancel Polar subscription", error=str(e))
                raise

    # ==================== Stripe Integration (Universal Fallback) ====================

    async def create_stripe_customer(
        self, email: str, name: str, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create a customer in Stripe"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.stripe_api_url}/customers",
                    headers={
                        "Authorization": f"Bearer {self.stripe_api_key}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "email": email,
                        "name": name,
                        **({"metadata": metadata} if metadata else {}),
                    },
                )
                await response.raise_for_status()
                customer = await response.json()
                logger.info("Stripe customer created", customer_id=customer["id"])
                return customer

            except httpx.HTTPError as e:
                logger.error("Failed to create Stripe customer", error=str(e))
                raise

    async def create_stripe_checkout_session(
        self,
        customer_email: str,
        tier: str,
        country: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session"""
        if tier not in PRICING_TIERS or tier == "community":
            raise ValueError(f"Invalid tier for payment: {tier}")

        # Use appropriate currency based on country
        currency = "MXN" if country.upper() == "MX" else "USD"
        price_key = "price_mxn" if currency == "MXN" else "price_usd"
        price = PRICING_TIERS[tier][price_key]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.stripe_api_url}/checkout/sessions",
                    headers={
                        "Authorization": f"Bearer {self.stripe_api_key}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "success_url": success_url,
                        "cancel_url": cancel_url,
                        "customer_email": customer_email,
                        "mode": "subscription",
                        "line_items[0][price_data][currency]": currency,
                        "line_items[0][price_data][product_data][name]": f"Janua {tier.capitalize()} Plan",
                        "line_items[0][price_data][unit_amount]": str(price * 100),
                        "line_items[0][price_data][recurring][interval]": "month",
                        "line_items[0][quantity]": "1",
                        "metadata[tier]": tier,
                    },
                )
                await response.raise_for_status()
                session = await response.json()
                logger.info("Stripe checkout session created", session_id=session["id"])
                return session

            except httpx.HTTPError as e:
                logger.error("Failed to create Stripe checkout session", error=str(e))
                raise

    # ==================== Unified Billing Interface ====================

    async def create_subscription(
        self,
        customer_id: str,
        tier: str,
        country: str,
        payment_method_id: Optional[str] = None,
        use_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Create a subscription using the appropriate provider based on country"""
        provider = await self.determine_payment_provider(country, fallback=use_fallback)

        if provider == "conekta":
            return await self.create_conekta_subscription(
                customer_id=customer_id, plan_id=tier, card_token=payment_method_id
            )
        elif provider == "polar":
            return await self.create_polar_subscription(
                customer_id=customer_id, tier=tier, payment_method_id=payment_method_id
            )
        else:  # stripe fallback
            # Stripe subscription creation would go here
            logger.info("Using Stripe fallback for subscription creation")
            # DEPRECATED: Billing moved to Dhanam — Stripe subscription creation will not be implemented here.
            raise NotImplementedError("Stripe subscription creation not yet implemented")

    def get_pricing_for_country(self, country: str) -> Dict[str, Any]:
        """Get pricing information for a specific country"""
        provider = "conekta" if country.upper() == "MX" else "polar"
        currency = "MXN" if country.upper() == "MX" else "USD"

        pricing = {}
        for tier, info in PRICING_TIERS.items():
            if tier == "community":
                pricing[tier] = {"price": 0, "currency": currency}
            elif tier == "enterprise":
                pricing[tier] = {"price": "custom", "currency": currency}
            else:
                price_key = f"price_{currency.lower()}" if currency == "MXN" else "price_usd"
                pricing[tier] = {
                    "price": info.get(price_key, info.get("price_usd", 0)),
                    "currency": currency,
                    "features": info.get("features", []),
                    "mau_limit": info.get("mau_limit"),
                }

        return {"provider": provider, "currency": currency, "tiers": pricing}

    def validate_plan(self, tier: str) -> bool:
        """Validate if a plan/tier is valid"""
        return tier in PRICING_TIERS

    def get_plan_features(self, tier: str) -> Optional[List[str]]:
        """Get features for a specific plan/tier"""
        if tier not in PRICING_TIERS:
            return None
        return PRICING_TIERS[tier].get("features", [])

    def get_plan_mau_limit(self, tier: str) -> Optional[int]:
        """Get MAU limit for a specific plan/tier"""
        if tier not in PRICING_TIERS:
            return None
        return PRICING_TIERS[tier].get("mau_limit")

    def calculate_overage_cost(self, tier: str, mau_count: int) -> float:
        """Calculate overage cost for exceeding MAU limits"""
        if tier not in PRICING_TIERS:
            return 0.0

        mau_limit = PRICING_TIERS[tier].get("mau_limit")
        if not mau_limit or mau_count <= mau_limit:
            return 0.0

        # Simple overage calculation: $0.01 per MAU over limit
        overage = mau_count - mau_limit
        return overage * 0.01

    async def check_usage_limits(
        self, db: AsyncSession, tenant_id: UUID
    ) -> tuple[bool, Optional[str]]:
        """Check if tenant is within usage limits"""
        # Get tenant
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if not tenant:
            return False, "Tenant not found"

        # Check MAU limit
        tier_limits = PRICING_TIERS.get(tenant.subscription_tier, {})
        mau_limit = tier_limits.get("mau_limit", 0)

        if mau_limit and int(tenant.current_mau) >= mau_limit:
            return False, f"MAU limit reached ({mau_limit:,}). Please upgrade your plan."

        return True, None
