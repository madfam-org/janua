"""
Billing Webhook Handlers - Complete Implementation
"""

from datetime import datetime, timezone
from typing import Dict, Any
import hmac
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.models.user import Tenant, Subscription
from app.config import settings

logger = structlog.get_logger()


class BillingWebhookHandler:
    """Handle webhooks from payment providers"""

    @staticmethod
    def verify_conekta_signature(payload: bytes, signature: str) -> bool:
        """Verify Conekta webhook signature"""
        expected_signature = hmac.new(
            settings.CONEKTA_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)

    @staticmethod
    def verify_fungies_signature(payload: bytes, signature: str) -> bool:
        """Verify Fungies webhook signature"""
        expected_signature = hmac.new(
            settings.FUNGIES_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)

    @staticmethod
    async def handle_conekta_webhook(
        db: AsyncSession, event_type: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Conekta webhook events"""

        handlers = {
            "order.paid": BillingWebhookHandler.handle_conekta_order_paid,
            "charge.paid": BillingWebhookHandler.handle_conekta_charge_paid,
            "subscription.created": BillingWebhookHandler.handle_conekta_subscription_created,
            "subscription.updated": BillingWebhookHandler.handle_conekta_subscription_updated,
            "subscription.canceled": BillingWebhookHandler.handle_conekta_subscription_canceled,
            "subscription.paused": BillingWebhookHandler.handle_conekta_subscription_paused,
            "charge.refunded": BillingWebhookHandler.handle_conekta_charge_refunded,
        }

        handler = handlers.get(event_type)
        if not handler:
            logger.warning(f"Unhandled Conekta webhook event: {event_type}")
            return {"status": "ignored", "event": event_type}

        return await handler(db, data)

    @staticmethod
    async def handle_fungies_webhook(
        db: AsyncSession, event_type: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies webhook events"""

        handlers = {
            "payment.success": BillingWebhookHandler.handle_fungies_payment_success,
            "payment.failed": BillingWebhookHandler.handle_fungies_payment_failed,
            "subscription.activated": BillingWebhookHandler.handle_fungies_subscription_activated,
            "subscription.updated": BillingWebhookHandler.handle_fungies_subscription_updated,
            "subscription.cancelled": BillingWebhookHandler.handle_fungies_subscription_cancelled,
            "subscription.expired": BillingWebhookHandler.handle_fungies_subscription_expired,
            "refund.processed": BillingWebhookHandler.handle_fungies_refund_processed,
        }

        handler = handlers.get(event_type)
        if not handler:
            logger.warning(f"Unhandled Fungies webhook event: {event_type}")
            return {"status": "ignored", "event": event_type}

        return await handler(db, data)

    # Conekta Event Handlers

    @staticmethod
    async def handle_conekta_order_paid(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Conekta order paid event"""
        try:
            order_id = data.get("id")
            customer_id = data.get("customer_info", {}).get("customer_id")
            amount = data.get("amount", 0) / 100  # Convert from cents

            # Find tenant by customer ID
            tenant = await db.scalar(
                select(Tenant).where(Tenant.conekta_customer_id == customer_id)
            )

            if tenant:
                # Update subscription status
                tenant.subscription_status = "active"
                tenant.updated_at = datetime.now(timezone.utc)

                # Store payment record (if you have a payments table)
                logger.info(f"Payment processed for tenant {tenant.id}: ${amount}")

                await db.commit()

            return {"status": "processed", "order_id": order_id}

        except Exception as e:
            logger.error(f"Error handling Conekta order paid: {e}")
            await db.rollback()
            raise

    @staticmethod
    async def handle_conekta_charge_paid(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Conekta charge paid event"""
        charge_id = data.get("id")
        amount = data.get("amount", 0) / 100

        logger.info(f"Charge paid: {charge_id} for ${amount}")
        return {"status": "processed", "charge_id": charge_id}

    @staticmethod
    async def handle_conekta_subscription_created(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Conekta subscription created event"""
        try:
            subscription_id = data.get("id")
            customer_id = data.get("customer_id")
            plan_id = data.get("plan_id")

            # Find tenant
            tenant = await db.scalar(
                select(Tenant).where(Tenant.conekta_customer_id == customer_id)
            )

            if tenant:
                # Create or update subscription record
                subscription = await db.scalar(
                    select(Subscription).where(Subscription.tenant_id == tenant.id)
                )

                if not subscription:
                    subscription = Subscription(
                        tenant_id=tenant.id,
                        provider="conekta",
                        provider_subscription_id=subscription_id,
                        plan_id=plan_id,
                        status="active",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(subscription)
                else:
                    subscription.provider_subscription_id = subscription_id
                    subscription.plan_id = plan_id
                    subscription.status = "active"
                    subscription.updated_at = datetime.now(timezone.utc)

                tenant.subscription_status = "active"
                tenant.subscription_tier = plan_id
                tenant.updated_at = datetime.now(timezone.utc)

                await db.commit()

            return {"status": "processed", "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling Conekta subscription created: {e}")
            await db.rollback()
            raise

    @staticmethod
    async def handle_conekta_subscription_updated(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Conekta subscription updated event"""
        subscription_id = data.get("id")
        status = data.get("status")

        # Update subscription status in database
        subscription = await db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )

        if subscription:
            subscription.status = status
            subscription.updated_at = datetime.now(timezone.utc)

            # Update tenant status
            tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
            if tenant:
                tenant.subscription_status = status
                tenant.updated_at = datetime.now(timezone.utc)

            await db.commit()

        return {"status": "processed", "subscription_id": subscription_id}

    @staticmethod
    async def handle_conekta_subscription_canceled(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Conekta subscription canceled event"""
        subscription_id = data.get("id")

        subscription = await db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )

        if subscription:
            subscription.status = "canceled"
            subscription.canceled_at = datetime.now(timezone.utc)
            subscription.updated_at = datetime.now(timezone.utc)

            # Update tenant
            tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
            if tenant:
                tenant.subscription_status = "canceled"
                tenant.updated_at = datetime.now(timezone.utc)

            await db.commit()

        return {"status": "processed", "subscription_id": subscription_id}

    @staticmethod
    async def handle_conekta_subscription_paused(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Conekta subscription paused event"""
        subscription_id = data.get("id")

        subscription = await db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )

        if subscription:
            subscription.status = "paused"
            subscription.updated_at = datetime.now(timezone.utc)

            # Update tenant
            tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
            if tenant:
                tenant.subscription_status = "paused"
                tenant.updated_at = datetime.now(timezone.utc)

            await db.commit()

        return {"status": "processed", "subscription_id": subscription_id}

    @staticmethod
    async def handle_conekta_charge_refunded(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Conekta charge refunded event"""
        charge_id = data.get("id")
        refund_amount = data.get("amount_refunded", 0) / 100

        logger.info(f"Charge refunded: {charge_id} for ${refund_amount}")
        # Store refund record if needed

        return {"status": "processed", "charge_id": charge_id}

    # Fungies Event Handlers

    @staticmethod
    async def handle_fungies_payment_success(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies payment success event"""
        try:
            payment_id = data.get("id")
            customer_id = data.get("customer_id")
            amount = data.get("amount")

            # Find tenant by customer ID
            tenant = await db.scalar(
                select(Tenant).where(Tenant.fungies_customer_id == customer_id)
            )

            if tenant:
                tenant.subscription_status = "active"
                tenant.updated_at = datetime.now(timezone.utc)

                logger.info(f"Payment processed for tenant {tenant.id}: ${amount}")
                await db.commit()

            return {"status": "processed", "payment_id": payment_id}

        except Exception as e:
            logger.error(f"Error handling Fungies payment success: {e}")
            await db.rollback()
            raise

    @staticmethod
    async def handle_fungies_payment_failed(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies payment failed event"""
        payment_id = data.get("id")
        customer_id = data.get("customer_id")

        logger.warning(f"Payment failed for customer {customer_id}: {payment_id}")

        # Could update tenant status or send notification
        tenant = await db.scalar(select(Tenant).where(Tenant.fungies_customer_id == customer_id))

        if tenant:
            # Don't immediately cancel, but could set a flag for follow-up
            logger.warning(f"Payment failed for tenant {tenant.id}")

        return {"status": "processed", "payment_id": payment_id}

    @staticmethod
    async def handle_fungies_subscription_activated(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies subscription activated event"""
        try:
            subscription_id = data.get("subscription_id")
            customer_id = data.get("customer_id")
            plan = data.get("plan")

            tenant = await db.scalar(
                select(Tenant).where(Tenant.fungies_customer_id == customer_id)
            )

            if tenant:
                # Create or update subscription
                subscription = await db.scalar(
                    select(Subscription).where(Subscription.tenant_id == tenant.id)
                )

                if not subscription:
                    subscription = Subscription(
                        tenant_id=tenant.id,
                        provider="fungies",
                        provider_subscription_id=subscription_id,
                        plan_id=plan,
                        status="active",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(subscription)
                else:
                    subscription.provider_subscription_id = subscription_id
                    subscription.plan_id = plan
                    subscription.status = "active"
                    subscription.updated_at = datetime.now(timezone.utc)

                tenant.subscription_status = "active"
                tenant.subscription_tier = plan
                tenant.updated_at = datetime.now(timezone.utc)

                await db.commit()

            return {"status": "processed", "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling Fungies subscription activated: {e}")
            await db.rollback()
            raise

    @staticmethod
    async def handle_fungies_subscription_updated(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies subscription updated event"""
        subscription_id = data.get("subscription_id")
        new_plan = data.get("new_plan")

        subscription = await db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )

        if subscription:
            subscription.plan_id = new_plan
            subscription.updated_at = datetime.now(timezone.utc)

            # Update tenant
            tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
            if tenant:
                tenant.subscription_tier = new_plan
                tenant.updated_at = datetime.now(timezone.utc)

            await db.commit()

        return {"status": "processed", "subscription_id": subscription_id}

    @staticmethod
    async def handle_fungies_subscription_cancelled(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies subscription cancelled event"""
        subscription_id = data.get("subscription_id")

        subscription = await db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )

        if subscription:
            subscription.status = "canceled"
            subscription.canceled_at = datetime.now(timezone.utc)
            subscription.updated_at = datetime.now(timezone.utc)

            # Update tenant
            tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
            if tenant:
                tenant.subscription_status = "canceled"
                tenant.updated_at = datetime.now(timezone.utc)

            await db.commit()

        return {"status": "processed", "subscription_id": subscription_id}

    @staticmethod
    async def handle_fungies_subscription_expired(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies subscription expired event"""
        subscription_id = data.get("subscription_id")

        subscription = await db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )

        if subscription:
            subscription.status = "expired"
            subscription.expired_at = datetime.now(timezone.utc)
            subscription.updated_at = datetime.now(timezone.utc)

            # Update tenant
            tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
            if tenant:
                tenant.subscription_status = "expired"
                tenant.updated_at = datetime.now(timezone.utc)

            await db.commit()

        return {"status": "processed", "subscription_id": subscription_id}

    @staticmethod
    async def handle_fungies_refund_processed(
        db: AsyncSession, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Fungies refund processed event"""
        refund_id = data.get("refund_id")
        amount = data.get("amount")

        logger.info(f"Refund processed: {refund_id} for ${amount}")
        # Store refund record if needed

        return {"status": "processed", "refund_id": refund_id}
