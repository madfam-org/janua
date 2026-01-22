"""
Notification Dispatcher Application Service
Coordinates notification delivery for alerts across multiple channels
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from ...domain.models.alert import Alert
from ...domain.models.rule import AlertRule
from ...domain.models.notification import (
    NotificationRequest,
    NotificationChannel,
    NotificationStatus,
    NotificationPriority,
    NotificationTemplate,
)
from ...domain.services.notification_strategy import (
    NotificationStrategyRegistry,
    NotificationPriorityQueue,
)
import structlog

logger = structlog.get_logger()


@dataclass
class NotificationBatch:
    """Batch of notification requests"""

    batch_id: str
    requests: List[NotificationRequest]
    created_at: datetime
    priority: NotificationPriority

    def size(self) -> int:
        return len(self.requests)

    def get_channel_types(self) -> Set[str]:
        return {req.channel.channel_type for req in self.requests}


class ChannelRepository:
    """Abstract repository for notification channels"""

    async def get_enabled_channels(
        self, channel_types: List[str] = None
    ) -> List[NotificationChannel]:
        """Get enabled notification channels"""
        raise NotImplementedError

    async def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """Get channel by ID"""
        raise NotImplementedError

    async def get_channels_by_type(self, channel_type: str) -> List[NotificationChannel]:
        """Get channels of specific type"""
        raise NotImplementedError


class TemplateRepository:
    """Abstract repository for notification templates"""

    async def get_template(
        self, channel_type: str, template_name: str = "default"
    ) -> Optional[NotificationTemplate]:
        """Get notification template"""
        raise NotImplementedError

    async def get_alert_template(
        self, channel_type: str, severity: str
    ) -> Optional[NotificationTemplate]:
        """Get template for alert notifications"""
        raise NotImplementedError


class NotificationDispatcher:
    """Application service for managing notification delivery"""

    def __init__(
        self,
        strategy_registry: NotificationStrategyRegistry,
        channel_repository: ChannelRepository,
        template_repository: TemplateRepository,
    ):
        self._strategy_registry = strategy_registry
        self._channel_repo = channel_repository
        self._template_repo = template_repository

        # Queue and processing
        self._priority_queue = NotificationPriorityQueue()
        self._processing_task: Optional[asyncio.Task] = None
        self._is_processing = False

        # Configuration
        self._batch_size = 10
        self._processing_interval_seconds = 5
        self._max_concurrent_notifications = 5
        self._retry_delays = [30, 60, 300]  # seconds

        # State tracking
        self._pending_retries: List[NotificationRequest] = []
        self._failed_notifications: List[NotificationRequest] = []

        # Statistics
        self._stats = {
            "total_sent": 0,
            "total_failed": 0,
            "total_retries": 0,
            "by_channel_type": {},
            "last_reset": datetime.now(),
        }

    async def start_processing(self) -> None:
        """Start the notification processing loop"""
        if self._processing_task and not self._processing_task.done():
            logger.warning("Notification processing already running")
            return

        self._is_processing = True
        self._processing_task = asyncio.create_task(self._processing_loop())
        logger.info("Notification processing started")

    async def stop_processing(self) -> None:
        """Stop the notification processing loop"""
        self._is_processing = False

        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass  # Expected when task is cancelled during graceful shutdown

        logger.info("Notification processing stopped")

    async def send_alert_notifications(
        self, alert: Alert, rule: AlertRule, notification_type: str = "alert"
    ) -> List[NotificationRequest]:
        """Send notifications for an alert"""
        try:
            # Get enabled channel types from rule
            enabled_channel_types = rule.get_enabled_channels()
            if not enabled_channel_types:
                logger.debug(f"No notification channels configured for rule {rule.rule_id}")
                return []

            # Get actual channel configurations
            channels = []
            for channel_type in enabled_channel_types:
                type_channels = await self._channel_repo.get_channels_by_type(channel_type)
                channels.extend([ch for ch in type_channels if ch.enabled])

            if not channels:
                logger.warning(
                    f"No enabled channels found for alert {alert.alert_id}",
                    required_types=enabled_channel_types,
                )
                return []

            # Create notification requests
            requests = []
            for channel in channels:
                try:
                    request = await self._create_notification_request(
                        alert, channel, notification_type
                    )
                    if request:
                        requests.append(request)
                except Exception as e:
                    logger.error(
                        f"Failed to create notification request",
                        alert_id=alert.alert_id,
                        channel_id=channel.channel_id,
                        error=str(e),
                    )

            # Queue requests for processing
            for request in requests:
                self._priority_queue.enqueue(request)

            # Record notifications in alert
            for request in requests:
                alert.add_notification_sent(
                    f"{request.channel.channel_type}:{request.channel.channel_id}"
                )

            logger.info(
                f"Queued {len(requests)} notification requests for alert {alert.alert_id}",
                channel_types=[req.channel.channel_type for req in requests],
            )

            return requests

        except Exception as e:
            logger.error(
                f"Failed to send alert notifications",
                alert_id=alert.alert_id,
                rule_id=rule.rule_id,
                error=str(e),
            )
            return []

    async def send_immediate_notification(self, request: NotificationRequest) -> bool:
        """Send a notification immediately, bypassing the queue"""
        try:
            # Prepare content
            if not request.subject and not request.message:
                request.prepare_content()

            # Send using strategy registry
            success = await self._strategy_registry.send_notification(request)

            # Update statistics
            self._update_stats(request, success)

            return success

        except Exception as e:
            logger.error(
                f"Failed to send immediate notification",
                request_id=request.request_id,
                error=str(e),
            )
            request.mark_failed(str(e))
            self._update_stats(request, False)
            return False

    async def get_queue_status(self) -> Dict[str, any]:
        """Get current queue status"""
        return {
            "queue_size": self._priority_queue.size(),
            "queue_by_priority": self._priority_queue.size_by_priority(),
            "pending_retries": len(self._pending_retries),
            "failed_notifications": len(self._failed_notifications),
            "is_processing": self._is_processing,
            "processing_interval_seconds": self._processing_interval_seconds,
            "max_concurrent_notifications": self._max_concurrent_notifications,
        }

    async def get_statistics(self, reset: bool = False) -> Dict[str, any]:
        """Get notification statistics"""
        stats = self._stats.copy()

        # Add strategy registry statistics
        strategy_stats = self._strategy_registry.get_delivery_statistics()
        stats["delivery_statistics"] = strategy_stats

        # Add current queue status
        stats["queue_status"] = await self.get_queue_status()

        if reset:
            self._reset_stats()

        return stats

    async def retry_failed_notifications(self, max_retries: int = None) -> int:
        """Retry failed notifications"""
        if max_retries is None:
            max_retries = len(self._retry_delays)

        retried_count = 0
        remaining_retries = []

        for request in self._pending_retries:
            if request.retry_count >= max_retries:
                self._failed_notifications.append(request)
                continue

            # Check if enough time has passed for retry
            if request.failed_at:
                retry_delay = self._retry_delays[
                    min(request.retry_count, len(self._retry_delays) - 1)
                ]
                if (datetime.now() - request.failed_at).total_seconds() < retry_delay:
                    remaining_retries.append(request)
                    continue

            # Retry the notification
            request.increment_retry()
            self._priority_queue.enqueue(request)
            retried_count += 1

            self._stats["total_retries"] += 1

        self._pending_retries = remaining_retries

        if retried_count > 0:
            logger.info(f"Retried {retried_count} failed notifications")

        return retried_count

    async def _create_notification_request(
        self, alert: Alert, channel: NotificationChannel, notification_type: str
    ) -> Optional[NotificationRequest]:
        """Create a notification request for alert and channel"""
        try:
            # Determine priority based on alert severity
            priority = self._get_priority_from_severity(alert.severity.value)

            # Check if channel supports this priority
            if not channel.supports_priority(priority):
                logger.debug(
                    f"Channel {channel.channel_id} does not support priority {priority.value}",
                    channel_priority_filter=channel.priority_filter.value
                    if channel.priority_filter
                    else None,
                )
                return None

            # Get template for this channel type and notification type
            template = await self._template_repo.get_alert_template(
                channel.channel_type, alert.severity.value
            )

            # Create notification request
            request = NotificationRequest(
                alert=alert,
                channel=channel,
                priority=priority,
                template=template,
                context={"notification_type": notification_type, "channel_name": channel.name},
            )

            return request

        except Exception as e:
            logger.error(
                f"Failed to create notification request",
                alert_id=alert.alert_id,
                channel_id=channel.channel_id,
                error=str(e),
            )
            return None

    async def _processing_loop(self) -> None:
        """Main notification processing loop"""
        while self._is_processing:
            try:
                # Process retries first
                await self.retry_failed_notifications()

                # Process queued notifications
                await self._process_notification_batch()

                # Clean up expired requests
                self._priority_queue.clear_expired(max_age_minutes=60)

                # Wait before next iteration
                await asyncio.sleep(self._processing_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in notification processing loop: {e}")
                await asyncio.sleep(self._processing_interval_seconds * 2)  # Wait longer on error

    async def _process_notification_batch(self) -> None:
        """Process a batch of notifications"""
        requests = []

        # Collect batch of requests
        for _ in range(self._batch_size):
            request = self._priority_queue.dequeue()
            if not request:
                break
            requests.append(request)

        if not requests:
            return

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self._max_concurrent_notifications)

        # Process requests concurrently
        tasks = [self._process_single_notification(request, semaphore) for request in requests]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_notification(
        self, request: NotificationRequest, semaphore: asyncio.Semaphore
    ) -> None:
        """Process a single notification request"""
        async with semaphore:
            try:
                # Prepare content if needed
                if not request.subject and not request.message:
                    request.prepare_content()

                # Send notification
                success = await self._strategy_registry.send_notification(request)

                # Handle result
                if success:
                    self._update_stats(request, True)
                elif request.status == NotificationStatus.RATE_LIMITED:
                    # Re-queue for later
                    self._priority_queue.enqueue(request)
                elif request.can_retry():
                    # Add to retry queue
                    self._pending_retries.append(request)
                else:
                    # Mark as permanently failed
                    self._failed_notifications.append(request)
                    self._update_stats(request, False)

            except Exception as e:
                logger.error(
                    f"Failed to process notification", request_id=request.request_id, error=str(e)
                )
                request.mark_failed(str(e))

                if request.can_retry():
                    self._pending_retries.append(request)
                else:
                    self._failed_notifications.append(request)

                self._update_stats(request, False)

    def _get_priority_from_severity(self, severity: str) -> NotificationPriority:
        """Map alert severity to notification priority"""
        mapping = {
            "low": NotificationPriority.LOW,
            "medium": NotificationPriority.NORMAL,
            "high": NotificationPriority.HIGH,
            "critical": NotificationPriority.URGENT,
        }
        return mapping.get(severity.lower(), NotificationPriority.NORMAL)

    def _update_stats(self, request: NotificationRequest, success: bool) -> None:
        """Update notification statistics"""
        if success:
            self._stats["total_sent"] += 1
        else:
            self._stats["total_failed"] += 1

        # Update by channel type
        channel_type = request.channel.channel_type
        if channel_type not in self._stats["by_channel_type"]:
            self._stats["by_channel_type"][channel_type] = {"sent": 0, "failed": 0}

        if success:
            self._stats["by_channel_type"][channel_type]["sent"] += 1
        else:
            self._stats["by_channel_type"][channel_type]["failed"] += 1

    def _reset_stats(self) -> None:
        """Reset statistics"""
        self._stats = {
            "total_sent": 0,
            "total_failed": 0,
            "total_retries": 0,
            "by_channel_type": {},
            "last_reset": datetime.now(),
        }
        logger.info("Notification statistics reset")

    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.stop_processing()

        # Clear queues
        self._priority_queue.clear_all()
        self._pending_retries.clear()

        # Clean up old failed notifications
        cutoff = datetime.now() - timedelta(days=7)
        self._failed_notifications = [
            req for req in self._failed_notifications if req.created_at >= cutoff
        ]

        logger.info("Notification dispatcher cleanup completed")
