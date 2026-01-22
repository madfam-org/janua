"""
Webhook Event Dispatcher System
Reliable webhook delivery with retry logic and HMAC signatures
"""

import asyncio
import hashlib
import hmac
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
import httpx
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ..models import WebhookEndpoint, WebhookEvent, WebhookDelivery, WebhookStatus
from app.core.tenant_context import TenantContext

logger = structlog.get_logger()


class WebhookDispatcher:
    """Manages webhook event creation and delivery"""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._delivery_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the webhook delivery worker"""
        if not self._worker_task:
            self._worker_task = asyncio.create_task(self._delivery_worker())
            logger.info("Webhook delivery worker started")

    async def stop(self):
        """Stop the webhook delivery worker"""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass  # Expected when task is cancelled during graceful shutdown
            logger.info("Webhook delivery worker stopped")

    async def emit_event(
        self,
        session: AsyncSession,
        event_type: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> WebhookEvent:
        """
        Create a webhook event and queue deliveries

        Args:
            session: Database session
            event_type: Type of event (e.g., "user.created", "organization.updated")
            data: Event payload data
            user_id: User associated with the event
            organization_id: Organization context

        Returns:
            Created webhook event
        """

        try:
            # Get organization context if not provided
            if not organization_id:
                organization_id = TenantContext.get_organization_id()

            # Create the event
            event = WebhookEvent(
                type=event_type,
                data=data,
                user_id=UUID(user_id) if user_id else None,
                organization_id=UUID(organization_id) if organization_id else None,
            )
            session.add(event)
            await session.flush()

            # Find matching endpoints
            endpoints = await self._find_matching_endpoints(
                session, event_type, organization_id, user_id
            )

            # Create delivery records
            for endpoint in endpoints:
                delivery = WebhookDelivery(
                    webhook_endpoint_id=endpoint.id,
                    webhook_event_id=event.id,
                    status=WebhookStatus.PENDING,
                    scheduled_at=datetime.utcnow(),
                )
                session.add(delivery)
                await session.flush()

                # Queue for delivery
                await self._delivery_queue.put(
                    {
                        "delivery_id": str(delivery.id),
                        "endpoint_id": str(endpoint.id),
                        "event_id": str(event.id),
                    }
                )

            await session.commit()

            logger.info(
                "Webhook event created",
                event_type=event_type,
                event_id=str(event.id),
                endpoint_count=len(endpoints),
            )

            return event

        except Exception as e:
            logger.error("Failed to emit webhook event", error=str(e))
            await session.rollback()
            raise

    async def deliver_webhook(self, session: AsyncSession, delivery_id: str) -> bool:
        """
        Deliver a specific webhook

        Args:
            session: Database session
            delivery_id: ID of the delivery to process

        Returns:
            Success status
        """

        try:
            # Get delivery with endpoint and event
            result = await session.execute(
                select(WebhookDelivery, WebhookEndpoint, WebhookEvent)
                .join(WebhookEndpoint)
                .join(WebhookEvent)
                .where(WebhookDelivery.id == delivery_id)
            )
            row = result.one_or_none()

            if not row:
                logger.warning("Webhook delivery not found", delivery_id=delivery_id)
                return False

            delivery, endpoint, event = row

            # Check if endpoint is active
            if not endpoint.is_active:
                delivery.status = WebhookStatus.FAILED
                delivery.error_message = "Endpoint is inactive"
                await session.commit()
                return False

            # Prepare payload
            payload = self._prepare_payload(event, endpoint)

            # Calculate signature
            signature = self._calculate_signature(json.dumps(payload).encode(), endpoint.secret)

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Event": event.type,
                "X-Webhook-Signature": signature,
                "X-Webhook-ID": str(event.id),
                "X-Webhook-Timestamp": str(int(datetime.utcnow().timestamp())),
            }

            # Add custom headers
            if endpoint.headers:
                headers.update(endpoint.headers)

            # Update delivery attempt
            delivery.attempts = (delivery.attempts or 0) + 1
            delivery.request_headers = headers
            delivery.request_body = payload

            # Make the request
            try:
                response = await self._client.post(endpoint.url, json=payload, headers=headers)

                # Record response
                delivery.response_status = response.status_code
                delivery.response_headers = dict(response.headers)
                delivery.response_body = response.text[:5000]  # Limit response size

                if 200 <= response.status_code < 300:
                    # Success
                    delivery.status = WebhookStatus.DELIVERED
                    delivery.delivered_at = datetime.utcnow()

                    # Update endpoint statistics
                    endpoint.success_count = (endpoint.success_count or 0) + 1
                    endpoint.last_success_at = datetime.utcnow()

                    await session.commit()

                    logger.info(
                        "Webhook delivered successfully",
                        delivery_id=delivery_id,
                        endpoint_url=endpoint.url,
                        status_code=response.status_code,
                    )

                    return True
                else:
                    # HTTP error
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response
                    )

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                # Delivery failed
                delivery.error_message = str(e)

                # Check if we should retry
                if delivery.attempts < endpoint.max_retries:
                    delivery.status = WebhookStatus.RETRYING
                    delivery.next_retry_at = self._calculate_next_retry(
                        delivery.attempts, endpoint.retry_delay
                    )

                    # Re-queue for retry
                    await self._delivery_queue.put(
                        {
                            "delivery_id": str(delivery.id),
                            "endpoint_id": str(endpoint.id),
                            "event_id": str(event.id),
                            "retry_at": delivery.next_retry_at.isoformat(),
                        }
                    )

                    logger.warning(
                        "Webhook delivery failed, will retry",
                        delivery_id=delivery_id,
                        attempt=delivery.attempts,
                        next_retry=delivery.next_retry_at.isoformat(),
                    )
                else:
                    # Max retries exceeded
                    delivery.status = WebhookStatus.FAILED

                    # Update endpoint statistics
                    endpoint.failure_count = (endpoint.failure_count or 0) + 1
                    endpoint.last_failure_at = datetime.utcnow()

                    logger.error(
                        "Webhook delivery failed permanently",
                        delivery_id=delivery_id,
                        attempts=delivery.attempts,
                        error=str(e),
                    )

                await session.commit()
                return False

        except Exception as e:
            logger.error("Webhook delivery error", error=str(e))
            await session.rollback()
            return False

    async def retry_failed_deliveries(
        self, session: AsyncSession, organization_id: Optional[str] = None
    ):
        """Retry failed webhook deliveries"""

        try:
            # Find deliveries to retry
            query = select(WebhookDelivery).where(
                and_(
                    WebhookDelivery.status == WebhookStatus.RETRYING,
                    WebhookDelivery.next_retry_at <= datetime.utcnow(),
                )
            )

            if organization_id:
                query = query.join(WebhookEndpoint).where(
                    WebhookEndpoint.organization_id == organization_id
                )

            result = await session.execute(query)
            deliveries = result.scalars().all()

            for delivery in deliveries:
                await self._delivery_queue.put(
                    {
                        "delivery_id": str(delivery.id),
                        "endpoint_id": str(delivery.webhook_endpoint_id),
                        "event_id": str(delivery.webhook_event_id),
                    }
                )

            logger.info(f"Queued {len(deliveries)} deliveries for retry")

        except Exception as e:
            logger.error("Failed to queue retries", error=str(e))

    # Private helper methods

    async def _delivery_worker(self):
        """Background worker for webhook delivery"""

        while True:
            try:
                # Get delivery from queue
                delivery_info = await self._delivery_queue.get()

                # Check if we should wait before delivery
                if "retry_at" in delivery_info:
                    retry_at = datetime.fromisoformat(delivery_info["retry_at"])
                    wait_seconds = (retry_at - datetime.utcnow()).total_seconds()
                    if wait_seconds > 0:
                        await asyncio.sleep(wait_seconds)

                # Create a new session for delivery
                from app.core.database_manager import db_manager

                async with db_manager.get_session() as session:
                    await self.deliver_webhook(session, delivery_info["delivery_id"])

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Delivery worker error", error=str(e))
                await asyncio.sleep(5)  # Brief pause on error

    async def _find_matching_endpoints(
        self,
        session: AsyncSession,
        event_type: str,
        organization_id: Optional[str],
        user_id: Optional[str],
    ) -> List[WebhookEndpoint]:
        """Find endpoints that should receive this event"""

        conditions = [
            WebhookEndpoint.is_active == True,
            WebhookEndpoint.events.contains([event_type]),
        ]

        if organization_id:
            conditions.append(WebhookEndpoint.organization_id == organization_id)

        if user_id:
            # Also check user-specific webhooks
            conditions = [
                and_(*conditions),
                or_(WebhookEndpoint.user_id == user_id, WebhookEndpoint.user_id.is_(None)),
            ]

        result = await session.execute(select(WebhookEndpoint).where(and_(*conditions)))

        return result.scalars().all()

    def _prepare_payload(self, event: WebhookEvent, endpoint: WebhookEndpoint) -> Dict[str, Any]:
        """Prepare the webhook payload"""

        return {
            "id": str(event.id),
            "type": event.type,
            "created_at": event.created_at.isoformat(),
            "data": event.data,
            "user_id": str(event.user_id) if event.user_id else None,
            "organization_id": str(event.organization_id) if event.organization_id else None,
        }

    def _calculate_signature(self, payload: bytes, secret: str) -> str:
        """Calculate HMAC-SHA256 signature"""

        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    def _calculate_next_retry(self, attempts: int, base_delay: int) -> datetime:
        """Calculate next retry time with exponential backoff"""

        # Exponential backoff: delay * 2^(attempt-1)
        delay_seconds = min(base_delay * (2 ** (attempts - 1)), 3600)  # Max 1 hour

        return datetime.utcnow() + timedelta(seconds=delay_seconds)


class WebhookEventTypes:
    """Standard webhook event types"""

    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_VERIFIED = "user.email_verified"
    USER_SUSPENDED = "user.suspended"
    USER_REACTIVATED = "user.reactivated"

    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_MFA_ENABLED = "auth.mfa_enabled"
    AUTH_MFA_DISABLED = "auth.mfa_disabled"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"
    AUTH_PASSWORD_RESET = "auth.password_reset"

    # Organization events
    ORG_CREATED = "organization.created"
    ORG_UPDATED = "organization.updated"
    ORG_DELETED = "organization.deleted"
    ORG_MEMBER_ADDED = "organization.member_added"
    ORG_MEMBER_REMOVED = "organization.member_removed"
    ORG_MEMBER_ROLE_CHANGED = "organization.member_role_changed"

    # Role events
    ROLE_CREATED = "role.created"
    ROLE_UPDATED = "role.updated"
    ROLE_DELETED = "role.deleted"
    ROLE_ASSIGNED = "role.assigned"
    ROLE_REVOKED = "role.revoked"

    # Security events
    SECURITY_THREAT_DETECTED = "security.threat_detected"
    SECURITY_BREACH_ATTEMPT = "security.breach_attempt"
    SECURITY_POLICY_VIOLATION = "security.policy_violation"

    # Compliance events
    COMPLIANCE_AUDIT_STARTED = "compliance.audit_started"
    COMPLIANCE_AUDIT_COMPLETED = "compliance.audit_completed"
    COMPLIANCE_VIOLATION = "compliance.violation"

    # System events
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_HEALTH_DEGRADED = "system.health_degraded"
    SYSTEM_ERROR = "system.error"


# Webhook verification utilities


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    timestamp: Optional[str] = None,
    max_age_seconds: int = 300,
) -> bool:
    """
    Verify webhook signature from Janua

    Args:
        payload: Request body bytes
        signature: X-Webhook-Signature header value
        secret: Webhook endpoint secret
        timestamp: X-Webhook-Timestamp header value
        max_age_seconds: Maximum age of webhook in seconds

    Returns:
        True if signature is valid
    """

    # Check timestamp if provided
    if timestamp:
        try:
            webhook_time = int(timestamp)
            current_time = int(datetime.utcnow().timestamp())

            if abs(current_time - webhook_time) > max_age_seconds:
                logger.warning("Webhook timestamp too old", age=abs(current_time - webhook_time))
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid webhook timestamp", timestamp=timestamp)
            return False

    # Calculate expected signature
    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Compare signatures (timing-safe)
    return hmac.compare_digest(signature, expected_signature)


# Global webhook dispatcher instance
webhook_dispatcher = WebhookDispatcher()


# Helper function for FastAPI dependency
async def emit_webhook_event(
    event_type: str,
    data: Dict[str, Any],
    session: AsyncSession,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
):
    """Convenience function to emit webhook events"""

    await webhook_dispatcher.emit_event(
        session=session,
        event_type=event_type,
        data=data,
        user_id=user_id,
        organization_id=organization_id,
    )
