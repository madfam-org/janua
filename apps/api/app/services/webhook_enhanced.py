"""
Enhanced webhook service with retry logic and dead letter queue.
"""

import json
import logging
import hashlib
import hmac
import time
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import WebhookEndpoint, WebhookEvent, WebhookDelivery
from app.services.cache import CacheService
from app.services.audit_logger import AuditLogger, AuditAction
from app.config import settings


logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    SENDING = "sending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DLQ = "dead_letter_queue"


class WebhookService:
    """
    Enhanced webhook service with retry logic and dead letter queue.
    """
    
    # Retry configuration
    MAX_RETRIES = 5
    RETRY_DELAYS = [1, 5, 30, 300, 1800]  # Seconds: 1s, 5s, 30s, 5m, 30m
    TIMEOUT = 30  # Request timeout in seconds
    
    # DLQ configuration
    DLQ_THRESHOLD = 3  # Move to DLQ after 3 consecutive failures
    DLQ_RETENTION_DAYS = 30
    
    def __init__(self, db: Session):
        self.db = db
        self.cache = CacheService()
        self.audit_logger = AuditLogger(db)
        self.http_client = None
        self._delivery_queue = asyncio.Queue()
        self._retry_queue = asyncio.Queue()
        self._dlq = asyncio.Queue()
        self._workers = []
    
    async def start_workers(self, num_workers: int = 3):
        """
        Start background workers for webhook delivery.
        """
        # Create HTTP client
        self.http_client = httpx.AsyncClient(timeout=self.TIMEOUT)
        
        # Start delivery workers
        for i in range(num_workers):
            worker = asyncio.create_task(self._delivery_worker(f"worker-{i}"))
            self._workers.append(worker)
        
        # Start retry worker
        retry_worker = asyncio.create_task(self._retry_worker())
        self._workers.append(retry_worker)
        
        # Start DLQ processor
        dlq_worker = asyncio.create_task(self._dlq_worker())
        self._workers.append(dlq_worker)
    
    async def stop_workers(self):
        """
        Stop all background workers.
        """
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
    
    async def trigger_event(
        self,
        event_type: str,
        tenant_id: str,
        data: Dict[str, Any],
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Trigger a webhook event for all subscribed endpoints.
        """
        # Get active endpoints for this event
        endpoints = self.db.query(WebhookEndpoint).filter(
            and_(
                WebhookEndpoint.tenant_id == tenant_id,
                WebhookEndpoint.enabled == True,
                WebhookEndpoint.events.contains([event_type])
            )
        ).all()
        
        if not endpoints:
            return
        
        # Create event record
        event = WebhookEvent(
            tenant_id=tenant_id,
            organization_id=organization_id,
            event_type=event_type,
            data=data,
            user_id=user_id
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        # Queue deliveries for each endpoint
        for endpoint in endpoints:
            delivery = WebhookDelivery(
                webhook_id=endpoint.id,
                event_id=event.id,
                url=endpoint.url,
                status=DeliveryStatus.PENDING.value,
                attempts=0
            )
            
            self.db.add(delivery)
            self.db.commit()
            self.db.refresh(delivery)
            
            # Add to delivery queue
            await self._delivery_queue.put({
                "delivery": delivery,
                "endpoint": endpoint,
                "event": event
            })
        
        # Log audit event
        await self.audit_logger.log(
            action=AuditAction.WEBHOOK_TRIGGERED,
            user_id=user_id,
            resource_type="webhook",
            resource_id=str(event.id),
            details={
                "event_type": event_type,
                "endpoints_count": len(endpoints)
            }
        )
    
    async def _delivery_worker(self, worker_id: str):
        """
        Worker for processing webhook deliveries.
        """
        while True:
            try:
                # Get delivery from queue
                item = await self._delivery_queue.get()
                delivery = item["delivery"]
                endpoint = item["endpoint"]
                event = item["event"]
                
                # Attempt delivery
                success = await self._deliver_webhook(
                    delivery=delivery,
                    endpoint=endpoint,
                    event=event
                )
                
                if not success and delivery.attempts < self.MAX_RETRIES:
                    # Schedule retry
                    await self._schedule_retry(delivery, endpoint, event)
                elif not success:
                    # Move to DLQ
                    await self._move_to_dlq(delivery, endpoint, event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Delivery worker {worker_id} error: {e}")
                await asyncio.sleep(1)
    
    async def _retry_worker(self):
        """
        Worker for processing webhook retries.
        """
        while True:
            try:
                # Check for retries every minute
                await asyncio.sleep(60)
                
                # Get pending retries
                retries = self.db.query(WebhookDelivery).filter(
                    and_(
                        WebhookDelivery.status == DeliveryStatus.RETRYING.value,
                        WebhookDelivery.next_retry_at <= datetime.utcnow()
                    )
                ).all()
                
                for delivery in retries:
                    # Get endpoint and event
                    endpoint = self.db.query(WebhookEndpoint).filter(
                        WebhookEndpoint.id == delivery.webhook_id
                    ).first()
                    
                    event = self.db.query(WebhookEvent).filter(
                        WebhookEvent.id == delivery.event_id
                    ).first()
                    
                    if endpoint and event:
                        # Add back to delivery queue
                        await self._delivery_queue.put({
                            "delivery": delivery,
                            "endpoint": endpoint,
                            "event": event
                        })
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry worker error: {e}")
                await asyncio.sleep(60)
    
    async def _dlq_worker(self):
        """
        Worker for processing dead letter queue.
        """
        while True:
            try:
                # Process DLQ every hour
                await asyncio.sleep(3600)
                
                # Clean up old DLQ entries
                cutoff = datetime.utcnow() - timedelta(days=self.DLQ_RETENTION_DAYS)
                
                deleted = self.db.query(WebhookDelivery).filter(
                    and_(
                        WebhookDelivery.status == DeliveryStatus.DLQ.value,
                        WebhookDelivery.updated_at < cutoff
                    )
                ).delete()
                
                if deleted > 0:
                    self.db.commit()
                    logger.info(f"Cleaned {deleted} old DLQ entries")
                
                # Optional: Retry DLQ items if endpoint is re-enabled
                # This could be triggered manually by admin
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DLQ worker error: {e}")
                await asyncio.sleep(3600)
    
    async def _deliver_webhook(
        self,
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
        event: WebhookEvent
    ) -> bool:
        """
        Attempt to deliver a webhook.
        """
        try:
            # Update status
            delivery.status = DeliveryStatus.SENDING.value
            delivery.attempts += 1
            delivery.last_attempt_at = datetime.utcnow()
            self.db.commit()
            
            # Prepare payload
            payload = {
                "id": str(event.id),
                "type": event.event_type,
                "created": event.created_at.isoformat(),
                "data": event.data
            }
            
            # Generate signature
            signature = self._generate_signature(
                json.dumps(payload),
                endpoint.secret
            )
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Id": str(event.id),
                "X-Webhook-Timestamp": str(int(time.time())),
                "X-Webhook-Signature": signature,
                "User-Agent": "Plinto-Webhook/1.0"
            }
            
            # Add custom headers if configured
            if endpoint.headers:
                headers.update(endpoint.headers)
            
            # Send request
            response = await self.http_client.post(
                endpoint.url,
                json=payload,
                headers=headers,
                timeout=self.TIMEOUT
            )
            
            # Check response
            if 200 <= response.status_code < 300:
                # Success
                delivery.status = DeliveryStatus.SUCCESS.value
                delivery.response_status = response.status_code
                delivery.response_headers = dict(response.headers)
                delivery.response_body = response.text[:1000]  # Store first 1000 chars
                delivery.delivered_at = datetime.utcnow()
                self.db.commit()
                
                logger.info(f"Webhook delivered successfully: {endpoint.url}")
                return True
            else:
                # HTTP error
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]
                delivery.error_message = f"HTTP {response.status_code}"
                
                # Check if we should retry
                if response.status_code >= 500 or response.status_code == 429:
                    # Server error or rate limit - retry
                    delivery.status = DeliveryStatus.FAILED.value
                else:
                    # Client error - don't retry
                    delivery.status = DeliveryStatus.DLQ.value
                
                self.db.commit()
                
                logger.warning(f"Webhook delivery failed: {endpoint.url} - HTTP {response.status_code}")
                return False
                
        except httpx.TimeoutException:
            # Timeout
            delivery.error_message = "Request timeout"
            delivery.status = DeliveryStatus.FAILED.value
            self.db.commit()
            
            logger.warning(f"Webhook delivery timeout: {endpoint.url}")
            return False
            
        except Exception as e:
            # Other error
            delivery.error_message = str(e)
            delivery.status = DeliveryStatus.FAILED.value
            self.db.commit()
            
            logger.error(f"Webhook delivery error: {endpoint.url} - {e}")
            return False
    
    async def _schedule_retry(
        self,
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
        event: WebhookEvent
    ):
        """
        Schedule a webhook retry with exponential backoff.
        """
        # Calculate retry delay
        retry_index = min(delivery.attempts - 1, len(self.RETRY_DELAYS) - 1)
        delay_seconds = self.RETRY_DELAYS[retry_index]
        
        # Add jitter (±10%)
        import random
        jitter = delay_seconds * 0.1 * (2 * random.random() - 1)
        delay_seconds = int(delay_seconds + jitter)
        
        # Update delivery
        delivery.status = DeliveryStatus.RETRYING.value
        delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        self.db.commit()
        
        logger.info(f"Scheduled retry for {endpoint.url} in {delay_seconds} seconds")
    
    async def _move_to_dlq(
        self,
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
        event: WebhookEvent
    ):
        """
        Move a failed webhook to the dead letter queue.
        """
        delivery.status = DeliveryStatus.DLQ.value
        delivery.dlq_at = datetime.utcnow()
        self.db.commit()
        
        # Log to audit
        await self.audit_logger.log(
            action=AuditAction.WEBHOOK_DLQ,
            resource_type="webhook",
            resource_id=str(delivery.id),
            details={
                "endpoint": endpoint.url,
                "event_type": event.event_type,
                "attempts": delivery.attempts,
                "error": delivery.error_message
            }
        )
        
        # Notify admins (optional)
        # await self._notify_dlq_event(delivery, endpoint, event)
        
        logger.error(f"Moved webhook to DLQ: {endpoint.url} after {delivery.attempts} attempts")
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate HMAC signature for webhook payload.
        """
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def retry_dlq_item(self, delivery_id: str) -> bool:
        """
        Manually retry a DLQ item.
        """
        delivery = self.db.query(WebhookDelivery).filter(
            WebhookDelivery.id == delivery_id
        ).first()
        
        if not delivery or delivery.status != DeliveryStatus.DLQ.value:
            return False
        
        # Get endpoint and event
        endpoint = self.db.query(WebhookEndpoint).filter(
            WebhookEndpoint.id == delivery.webhook_id
        ).first()
        
        event = self.db.query(WebhookEvent).filter(
            WebhookEvent.id == delivery.event_id
        ).first()
        
        if not endpoint or not event:
            return False
        
        # Reset attempts and add to queue
        delivery.attempts = 0
        delivery.status = DeliveryStatus.PENDING.value
        self.db.commit()
        
        await self._delivery_queue.put({
            "delivery": delivery,
            "endpoint": endpoint,
            "event": event
        })
        
        return True
    
    async def get_delivery_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get webhook delivery statistics.
        """
        # Get counts by status
        from sqlalchemy import func
        
        status_counts = self.db.query(
            WebhookDelivery.status,
            func.count(WebhookDelivery.id)
        ).join(
            WebhookEndpoint
        ).filter(
            WebhookEndpoint.tenant_id == tenant_id
        ).group_by(
            WebhookDelivery.status
        ).all()
        
        stats = {
            "total": sum(count for _, count in status_counts),
            "by_status": {status: count for status, count in status_counts},
            "queue_size": self._delivery_queue.qsize(),
            "retry_queue_size": self._retry_queue.qsize(),
            "dlq_size": self._dlq.qsize()
        }
        
        return stats