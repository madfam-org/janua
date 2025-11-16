"""
Polar payment provider for digital product sales.

Supports:
- One-time product purchases
- Digital goods and downloads
- Customer portal integration
- Benefit tier management
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
import hmac
import hashlib

from app.services.payment.base import (
    PaymentProvider,
    CustomerData,
    PaymentMethodData,
    SubscriptionData,
    WebhookEvent,
)


class PolarProvider(PaymentProvider):
    """
    Polar payment provider for digital products and benefits.
    
    Polar specializes in:
    - Digital product sales
    - Benefit/tier management
    - Customer portal (hosted checkout)
    - Creator economy features
    """

    BASE_URL = "https://api.polar.sh/v1"

    def __init__(self, api_key: str, test_mode: bool = False):
        super().__init__(api_key, test_mode)
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def provider_name(self) -> str:
        return "polar"

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Polar API."""
        url = f"{self.BASE_URL}/{endpoint}"

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=self.headers)
            elif method == "POST":
                response = await client.post(url, headers=self.headers, json=data)
            elif method == "PATCH":
                response = await client.patch(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = await client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

    # ============================================================================
    # Customer Management
    # ============================================================================

    async def create_customer(self, customer_data: CustomerData) -> Dict[str, Any]:
        """
        Create Polar customer.
        
        Note: Polar creates customers automatically during checkout.
        This is mainly for record-keeping.
        """
        try:
            result = await self._request("POST", "customers", {
                "email": customer_data.email,
                "name": customer_data.name,
                "metadata": customer_data.metadata or {},
            })

            return {
                "customer_id": result.get("id"),
                "email": result.get("email"),
                "name": result.get("name"),
                "created": result.get("created_at"),
            }

        except Exception as e:
            raise Exception(f"Polar customer creation failed: {str(e)}")

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve Polar customer."""
        try:
            result = await self._request("GET", f"customers/{customer_id}")

            return {
                "customer_id": result.get("id"),
                "email": result.get("email"),
                "name": result.get("name"),
                "created": result.get("created_at"),
            }

        except Exception as e:
            raise Exception(f"Polar customer retrieval failed: {str(e)}")

    async def update_customer(
        self,
        customer_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update Polar customer."""
        try:
            result = await self._request("PATCH", f"customers/{customer_id}", updates)

            return {
                "customer_id": result.get("id"),
                "email": result.get("email"),
                "name": result.get("name"),
            }

        except Exception as e:
            raise Exception(f"Polar customer update failed: {str(e)}")

    async def delete_customer(self, customer_id: str) -> bool:
        """Delete Polar customer."""
        try:
            await self._request("DELETE", f"customers/{customer_id}")
            return True

        except Exception as e:
            raise Exception(f"Polar customer deletion failed: {str(e)}")

    # ============================================================================
    # Payment Method Management (Limited in Polar)
    # ============================================================================

    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_data: PaymentMethodData
    ) -> Dict[str, Any]:
        """
        Polar handles payment methods through checkout.
        
        This method is not directly supported.
        """
        raise NotImplementedError(
            "Polar manages payment methods through checkout flow. "
            "Payment methods are not stored separately."
        )

    async def get_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Not supported by Polar."""
        raise NotImplementedError("Polar does not expose payment method details.")

    async def list_payment_methods(
        self,
        customer_id: str,
        type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Not supported by Polar."""
        return []

    async def delete_payment_method(self, payment_method_id: str) -> bool:
        """Not supported by Polar."""
        raise NotImplementedError("Polar does not support payment method deletion.")

    async def set_default_payment_method(
        self,
        customer_id: str,
        payment_method_id: str
    ) -> Dict[str, Any]:
        """Not supported by Polar."""
        raise NotImplementedError("Polar does not support default payment methods.")

    # ============================================================================
    # Subscription Management (Product-based)
    # ============================================================================

    async def create_subscription(
        self,
        subscription_data: SubscriptionData
    ) -> Dict[str, Any]:
        """
        Create Polar subscription (for benefit tiers).
        
        Note: Polar subscriptions are created via checkout, not API.
        This returns checkout URL.
        """
        try:
            # Create checkout session for subscription
            checkout = await self._request("POST", "checkouts", {
                "product_id": subscription_data.plan_id,
                "customer_email": subscription_data.metadata.get("email") if subscription_data.metadata else None,
                "success_url": subscription_data.metadata.get("success_url") if subscription_data.metadata else None,
            })

            return {
                "subscription_id": checkout.get("id"),
                "checkout_url": checkout.get("url"),
                "status": "pending",  # Will be active after checkout
            }

        except Exception as e:
            raise Exception(f"Polar subscription creation failed: {str(e)}")

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Retrieve Polar subscription."""
        try:
            result = await self._request("GET", f"subscriptions/{subscription_id}")

            return {
                "subscription_id": result.get("id"),
                "customer_id": result.get("customer_id"),
                "product_id": result.get("product_id"),
                "status": result.get("status"),
                "current_period_start": result.get("current_period_start"),
                "current_period_end": result.get("current_period_end"),
            }

        except Exception as e:
            raise Exception(f"Polar subscription retrieval failed: {str(e)}")

    async def update_subscription(
        self,
        subscription_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update Polar subscription."""
        try:
            result = await self._request("PATCH", f"subscriptions/{subscription_id}", updates)

            return {
                "subscription_id": result.get("id"),
                "status": result.get("status"),
            }

        except Exception as e:
            raise Exception(f"Polar subscription update failed: {str(e)}")

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel Polar subscription."""
        try:
            result = await self._request("POST", f"subscriptions/{subscription_id}/cancel", {
                "cancel_at_period_end": cancel_at_period_end
            })

            return {
                "subscription_id": result.get("id"),
                "status": result.get("status"),
                "cancel_at_period_end": cancel_at_period_end,
            }

        except Exception as e:
            raise Exception(f"Polar subscription cancellation failed: {str(e)}")

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Resume canceled Polar subscription."""
        raise NotImplementedError("Polar does not support resuming subscriptions.")

    # ============================================================================
    # Invoice/Order Management
    # ============================================================================

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Retrieve Polar order (equivalent to invoice).
        
        Polar uses "orders" instead of invoices.
        """
        try:
            result = await self._request("GET", f"orders/{invoice_id}")

            return {
                "invoice_id": result.get("id"),
                "customer_id": result.get("customer_id"),
                "amount": result.get("amount", 0) / 100,  # Convert from cents
                "currency": result.get("currency", "USD").upper(),
                "status": result.get("status"),
                "created": result.get("created_at"),
            }

        except Exception as e:
            raise Exception(f"Polar order retrieval failed: {str(e)}")

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List Polar orders for customer."""
        try:
            result = await self._request("GET", f"orders?customer_id={customer_id}&limit={limit}")

            orders = []
            for order in result.get("data", []):
                orders.append({
                    "invoice_id": order.get("id"),
                    "amount": order.get("amount", 0) / 100,
                    "currency": order.get("currency", "USD").upper(),
                    "status": order.get("status"),
                    "created": order.get("created_at"),
                })

            return orders

        except Exception as e:
            raise Exception(f"Polar orders listing failed: {str(e)}")

    async def pay_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Polar orders are paid during checkout."""
        raise NotImplementedError("Polar orders cannot be paid via API.")

    # ============================================================================
    # Webhook Handling
    # ============================================================================

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str
    ) -> bool:
        """
        Verify Polar webhook signature.
        
        Polar uses HMAC SHA256 for webhook verification.
        """
        try:
            computed_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(computed_signature, signature)

        except Exception:
            return False

    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse Polar webhook into standardized event."""
        return WebhookEvent(
            event_id=payload.get("id", ""),
            event_type=payload.get("type", ""),
            data=payload.get("data", {}),
            created_at=datetime.fromisoformat(
                payload.get("created_at", datetime.utcnow().isoformat())
            ),
        )

    # ============================================================================
    # Product/Plan Management
    # ============================================================================

    async def list_plans(self) -> List[Dict[str, Any]]:
        """List Polar products (equivalent to plans)."""
        try:
            result = await self._request("GET", "products?is_archived=false")

            products = []
            for product in result.get("data", []):
                products.append({
                    "plan_id": product.get("id"),
                    "name": product.get("name"),
                    "description": product.get("description"),
                    "amount": product.get("price", 0) / 100 if product.get("price") else None,
                    "currency": "USD",
                    "type": product.get("type"),  # digital, subscription, etc
                })

            return products

        except Exception as e:
            raise Exception(f"Polar products listing failed: {str(e)}")

    async def get_plan(self, plan_id: str) -> Dict[str, Any]:
        """Get Polar product details."""
        try:
            result = await self._request("GET", f"products/{plan_id}")

            return {
                "plan_id": result.get("id"),
                "name": result.get("name"),
                "description": result.get("description"),
                "amount": result.get("price", 0) / 100 if result.get("price") else None,
                "currency": "USD",
                "type": result.get("type"),
                "benefits": result.get("benefits", []),
            }

        except Exception as e:
            raise Exception(f"Polar product retrieval failed: {str(e)}")

    # ============================================================================
    # Polar-Specific Methods
    # ============================================================================

    def supports_payment_method_type(self, method_type: str) -> bool:
        """Polar supports cards through Stripe integration."""
        return method_type == "card"

    def get_supported_currencies(self) -> List[str]:
        """Polar primarily supports USD."""
        return ["USD"]

    async def create_checkout_session(
        self,
        product_id: str,
        customer_email: Optional[str] = None,
        success_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create Polar checkout session for product purchase.
        
        This is the primary way to sell products with Polar.
        """
        try:
            checkout_data = {
                "product_id": product_id,
            }

            if customer_email:
                checkout_data["customer_email"] = customer_email

            if success_url:
                checkout_data["success_url"] = success_url

            if metadata:
                checkout_data["metadata"] = metadata

            result = await self._request("POST", "checkouts", checkout_data)

            return {
                "checkout_id": result.get("id"),
                "checkout_url": result.get("url"),
                "expires_at": result.get("expires_at"),
            }

        except Exception as e:
            raise Exception(f"Polar checkout creation failed: {str(e)}")

    async def get_checkout_session(self, checkout_id: str) -> Dict[str, Any]:
        """Retrieve checkout session details."""
        try:
            result = await self._request("GET", f"checkouts/{checkout_id}")

            return {
                "checkout_id": result.get("id"),
                "status": result.get("status"),
                "product_id": result.get("product_id"),
                "customer_id": result.get("customer_id"),
                "amount": result.get("amount", 0) / 100 if result.get("amount") else None,
            }

        except Exception as e:
            raise Exception(f"Polar checkout retrieval failed: {str(e)}")

    async def create_benefit(
        self,
        product_id: str,
        benefit_type: str,
        description: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create benefit for product/subscription.
        
        Polar benefits can be:
        - Discord role
        - GitHub repository access
        - Custom webhook
        - Download access
        """
        try:
            benefit_data = {
                "product_id": product_id,
                "type": benefit_type,
                "description": description,
            }

            if properties:
                benefit_data["properties"] = properties

            result = await self._request("POST", "benefits", benefit_data)

            return {
                "benefit_id": result.get("id"),
                "type": result.get("type"),
                "description": result.get("description"),
            }

        except Exception as e:
            raise Exception(f"Polar benefit creation failed: {str(e)}")

    async def list_customer_benefits(self, customer_id: str) -> List[Dict[str, Any]]:
        """List benefits granted to customer."""
        try:
            result = await self._request("GET", f"customers/{customer_id}/benefits")

            benefits = []
            for benefit in result.get("data", []):
                benefits.append({
                    "benefit_id": benefit.get("id"),
                    "type": benefit.get("type"),
                    "description": benefit.get("description"),
                    "granted_at": benefit.get("granted_at"),
                })

            return benefits

        except Exception as e:
            raise Exception(f"Polar customer benefits listing failed: {str(e)}")
