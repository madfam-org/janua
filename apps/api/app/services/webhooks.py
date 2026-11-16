"""
Webhook service for event notifications
"""

import asyncio
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from ..models import LegacyWebhookEvent as WebhookEvent
from ..models import WebhookDelivery, WebhookEndpoint, WebhookStatus

logger = logging.getLogger(__name__)


#: Janua's settings have no API_VERSION field: reading `settings.API_VERSION` raised AttributeError, so every event
#: failed before any delivery (2026-11-16). The webhook payload version is "v1" unless a setting is added later.
_API_VERSION = getattr(settings, "API_VERSION", None) or "v1"


class WebhookEventType(str, Enum):
    """Webhook event types"""

    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_VERIFIED = "user.verified"
    USER_SUSPENDED = "user.suspended"
    USER_REACTIVATED = "user.reactivated"

    # Session events
    SESSION_CREATED = "session.created"
    SESSION_REVOKED = "session.revoked"
    SESSION_EXPIRED = "session.expired"

    # Organization events
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    MEMBER_ADDED = "organization.member.added"
    MEMBER_REMOVED = "organization.member.removed"
    MEMBER_ROLE_CHANGED = "organization.member.role_changed"

    # Security events
    MFA_ENABLED = "security.mfa.enabled"
    MFA_DISABLED = "security.mfa.disabled"
    PASSKEY_REGISTERED = "security.passkey.registered"
    PASSKEY_REMOVED = "security.passkey.removed"
    PASSWORD_CHANGED = "security.password.changed"
    PASSWORD_RESET = "security.password.reset"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"

    # OAuth events
    OAUTH_LINKED = "oauth.account.linked"
    OAUTH_UNLINKED = "oauth.account.unlinked"

    # Admin events
    ADMIN_ACTION = "admin.action"
    SYSTEM_ALERT = "system.alert"


class WebhookPayload(BaseModel):
    """Standard webhook payload structure"""

    id: str = Field(..., description="Unique event ID")
    type: WebhookEventType = Field(..., description="Event type")
    created_at: str = Field(..., description="ISO timestamp")
    data: Dict[str, Any] = Field(..., description="Event data")
    object: str = Field(..., description="Object type (user, session, etc)")
    api_version: str = Field(default="v1", description="API version")


class WebhookService:
    """Service for managing and delivering webhooks"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.max_retries = 3
        self.retry_delays = [1, 5, 30]  # Seconds between retries

    async def trigger_event(
        self,
        db: AsyncSession,
        event_type: WebhookEventType,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> None:
        """
        Trigger a webhook event for all registered endpoints

        Args:
            db: Database session
            event_type: Type of event
            data: Event data payload
            user_id: Associated user ID
            organization_id: Associated organization ID
        """
        try:
            # Create webhook event record
            event = WebhookEvent(
                type=event_type, data=data, user_id=user_id, organization_id=organization_id
            )
            db.add(event)
            await db.commit()

            # Get active endpoints for this event type
            endpoints = await self._get_active_endpoints(db, event_type, organization_id)

            if not endpoints:
                logger.debug(f"No active endpoints for event {event_type}")
                return

            # Create payload
            payload = WebhookPayload(
                id=str(event.id),
                type=event_type,
                created_at=datetime.utcnow().isoformat(),
                data=data,
                object=self._get_object_type(event_type),
                api_version=_API_VERSION,
            )

            # Send to all endpoints concurrently. Each delivery only adds its record to the session (no I/O on it);
            # the session commits once, after every delivery has finished, so no two coroutines use it at once.
            tasks = [self._deliver_webhook(db, endpoint, event, payload) for endpoint in endpoints]
            await asyncio.gather(*tasks, return_exceptions=True)
            await db.commit()

        except Exception as e:
            logger.error(f"Error triggering webhook event: {e}")

    async def _get_active_endpoints(
        self, db: AsyncSession, event_type: WebhookEventType, organization_id: Optional[str] = None
    ) -> List[WebhookEndpoint]:
        """Active endpoints subscribed to an event type.

        The subscription is matched in Python, not with `WebhookEndpoint.events.contains(...)`: on Janua's
        Text-based JSON type that compiles to `LIKE`, which PostgreSQL rejects for a JSONB column (2026-11-16).
        Endpoints are few, so reading the active ones and filtering is cheap and works on every dialect.
        """
        query = select(WebhookEndpoint).where(WebhookEndpoint.is_active == True)  # noqa: E712 - SQL expression
        if organization_id:
            query = query.where(WebhookEndpoint.organization_id == organization_id)
        wanted = getattr(event_type, "value", event_type)
        result = await db.execute(query)
        return [endpoint for endpoint in result.scalars().all() if wanted in (endpoint.events or [])]

    def _get_object_type(self, event_type: WebhookEventType) -> str:
        """Get object type from event type"""
        if event_type.startswith("user."):
            return "user"
        elif event_type.startswith("session."):
            return "session"
        elif event_type.startswith("organization."):
            return "organization"
        elif event_type.startswith("security."):
            return "security"
        elif event_type.startswith("oauth."):
            return "oauth"
        elif event_type.startswith("admin."):
            return "admin"
        else:
            return "system"

    async def _deliver_webhook(
        self, db: AsyncSession, endpoint: WebhookEndpoint, event: WebhookEvent, payload: WebhookPayload
    ) -> None:
        """Deliver webhook to a specific endpoint with retries"""

        # The model's own fields (status, attempts, last_attempt, response_status, error_message): the old
        # `WebhookDelivery(..., attempt=1)` and `status_code` / `delivered_at` / `error` do not exist on it, so the
        # constructor raised and no delivery was ever recorded or sent (2026-11-16: 0 rows in production).
        delivery = WebhookDelivery(
            webhook_endpoint_id=endpoint.id,
            webhook_event_id=event.id,
            status=WebhookStatus.PENDING,
            attempts=0,
        )
        db.add(delivery)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Prepare request
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": f"Janua-Webhook/{_API_VERSION}",
                    "X-Webhook-ID": str(event.id),
                    "X-Webhook-Timestamp": str(int(time.time())),
                    "X-Webhook-Signature": self._generate_signature(
                        endpoint.secret, payload.model_dump_json()
                    ),
                }

                # Add custom headers if configured
                if endpoint.headers:
                    headers.update(endpoint.headers)

                # Send webhook
                response = await self.client.post(
                    endpoint.url, json=payload.model_dump(), headers=headers
                )

                # Update delivery record
                delivery.attempts = attempt
                delivery.last_attempt = datetime.utcnow()
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]  # Limit response size

                if response.status_code < 300:
                    delivery.status = WebhookStatus.DELIVERED
                    delivery.error_message = None
                    logger.info(f"Webhook delivered to {endpoint.url}")
                    break
                else:
                    logger.warning(
                        f"Webhook delivery failed: {response.status_code} - {endpoint.url}"
                    )
                    delivery.status = WebhookStatus.RETRYING if attempt < self.max_retries else WebhookStatus.FAILED
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delays[attempt - 1])

            except Exception as e:
                logger.error(f"Webhook delivery error: {e} - {endpoint.url}")
                delivery.attempts = attempt
                delivery.last_attempt = datetime.utcnow()
                delivery.error_message = str(e)[:1000]
                delivery.status = WebhookStatus.RETRYING if attempt < self.max_retries else WebhookStatus.FAILED
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delays[attempt - 1])
        # The caller (trigger_event) commits once every delivery has finished.

    def _generate_signature(self, secret: str, payload: str) -> str:
        """Generate HMAC signature for webhook payload"""
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    async def verify_webhook_signature(self, secret: str, payload: str, signature: str) -> bool:
        """Verify webhook signature"""
        expected = self._generate_signature(secret, payload)
        return hmac.compare_digest(expected, signature)

    async def register_endpoint(
        self,
        db: AsyncSession,
        url: str,
        events: List[WebhookEventType],
        organization_id: Optional[str] = None,
        description: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint"""

        # Generate secret for signature verification
        secret = hashlib.sha256(f"{url}{time.time()}".encode()).hexdigest()

        endpoint = WebhookEndpoint(
            url=url,
            secret=secret,
            events=events,
            organization_id=organization_id,
            description=description,
            headers=headers,
            is_active=True,
        )

        db.add(endpoint)
        await db.commit()
        await db.refresh(endpoint)

        # SECURITY: constant message, values as fields (no log injection).
        # Stdlib logger: fields go through `extra` (keyword fields raise TypeError).
        logger.info("Registered webhook endpoint", extra={"url": url})

        return endpoint

    async def update_endpoint(
        self,
        db: AsyncSession,
        endpoint_id: str,
        url: Optional[str] = None,
        events: Optional[List[WebhookEventType]] = None,
        is_active: Optional[bool] = None,
        description: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> WebhookEndpoint:
        """Update webhook endpoint configuration"""

        endpoint = (
            await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id))
        ).scalar_one_or_none()

        if not endpoint:
            raise ValueError(f"Webhook endpoint {endpoint_id} not found")

        if url:
            endpoint.url = url
        if events is not None:
            endpoint.events = events
        if is_active is not None:
            endpoint.is_active = is_active
        if description is not None:
            endpoint.description = description
        if headers is not None:
            endpoint.headers = headers

        endpoint.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(endpoint)

        # SECURITY: constant message, values as fields (no log injection).
        # Stdlib logger: fields go through `extra` (keyword fields raise TypeError).
        logger.info("Updated webhook endpoint", extra={"endpoint_id": endpoint_id})

        return endpoint

    async def delete_endpoint(self, db: AsyncSession, endpoint_id: str) -> bool:
        """Delete webhook endpoint"""

        endpoint = (
            await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id))
        ).scalar_one_or_none()

        if not endpoint:
            return False

        await db.delete(endpoint)
        await db.commit()

        # SECURITY: constant message, values as fields (no log injection).
        # Stdlib logger: fields go through `extra` (keyword fields raise TypeError).
        logger.info("Deleted webhook endpoint", extra={"endpoint_id": endpoint_id})

        return True

    async def get_endpoint_stats(
        self, db: AsyncSession, endpoint_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """Get webhook endpoint delivery statistics"""

        since = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.webhook_endpoint_id == endpoint_id,
                WebhookDelivery.created_at >= since,
            )
        )
        deliveries = result.scalars().all()

        total = len(deliveries)
        delivered = [d for d in deliveries if d.status == WebhookStatus.DELIVERED]
        successful = len(delivered)
        failed = total - successful

        # Average time from the delivery record to its successful attempt
        delivery_times = [
            (d.last_attempt - d.created_at).total_seconds()
            for d in delivered
            if d.last_attempt and d.created_at
        ]

        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0

        return {
            "total_deliveries": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "average_delivery_time": avg_delivery_time,
            "period_days": days,
        }

    async def test_endpoint(self, db: AsyncSession, endpoint_id: str) -> bool:
        """Send test webhook to endpoint"""

        endpoint = (
            await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id))
        ).scalar_one_or_none()

        if not endpoint:
            raise ValueError(f"Webhook endpoint {endpoint_id} not found")

        # Create test payload
        test_data = {
            "test": True,
            "message": "This is a test webhook from Janua",
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.trigger_event(
            db, WebhookEventType.SYSTEM_ALERT, test_data, organization_id=endpoint.organization_id
        )

        return True

    async def cleanup_old_events(self, db: AsyncSession, days_to_keep: int = 30) -> int:
        """Clean up old webhook events and deliveries"""

        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        # Delete old deliveries
        deliveries_deleted = (
            await db.execute(delete(WebhookDelivery).where(WebhookDelivery.created_at < cutoff))
        ).rowcount

        # Delete old events
        events_deleted = (
            await db.execute(delete(WebhookEvent).where(WebhookEvent.created_at < cutoff))
        ).rowcount

        await db.commit()

        logger.info(f"Cleaned up {events_deleted} events and {deliveries_deleted} deliveries")

        return events_deleted + deliveries_deleted

    @staticmethod
    def process_stripe_webhook(webhook_data: dict) -> dict:
        """Process Stripe webhook"""
        # Placeholder implementation for testing
        return {"processed": True}

    @staticmethod
    def process_github_webhook(webhook_data: dict) -> dict:
        """Process GitHub webhook"""
        # Placeholder implementation for testing
        return {"processed": True}

    @staticmethod
    def process_generic_webhook(webhook_data: dict) -> dict:
        """Process generic webhook"""
        # Placeholder implementation for testing
        return {"processed": True}


# Create singleton instance
webhook_service = WebhookService()


# Convenience functions for common webhook triggers
async def trigger_user_webhook(
    db: AsyncSession, event_type: WebhookEventType, user_data: Dict[str, Any], user_id: str
) -> None:
    """Trigger user-related webhook"""
    await webhook_service.trigger_event(db, event_type, user_data, user_id=user_id)


async def trigger_organization_webhook(
    db: AsyncSession, event_type: WebhookEventType, org_data: Dict[str, Any], organization_id: str
) -> None:
    """Trigger organization-related webhook"""
    await webhook_service.trigger_event(db, event_type, org_data, organization_id=organization_id)


async def trigger_security_webhook(
    db: AsyncSession, event_type: WebhookEventType, security_data: Dict[str, Any], user_id: str
) -> None:
    """Trigger security-related webhook"""
    await webhook_service.trigger_event(db, event_type, security_data, user_id=user_id)
