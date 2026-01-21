"""
Notification Strategy Domain Service
Registry and coordination for notification delivery strategies
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models.notification import (
    NotificationRequest, NotificationChannel, AbstractNotificationStrategy,
    NotificationPriority
)
import structlog
logger = structlog.get_logger()


@dataclass
class NotificationAttempt:
    """Record of a notification attempt"""
    channel_id: str
    request_id: str
    strategy_type: str
    attempted_at: datetime
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    delivery_time_ms: Optional[int] = None


class NotificationStrategyRegistry:
    """Registry for notification delivery strategies"""
    
    def __init__(self):
        self._strategies: Dict[str, AbstractNotificationStrategy] = {}
        self._attempt_history: List[NotificationAttempt] = []
        self._rate_limiter = NotificationRateLimiter()
    
    def register_strategy(self, strategy: AbstractNotificationStrategy) -> None:
        """Register a notification strategy"""
        channel_type = strategy.get_channel_type()
        if channel_type in self._strategies:
            logger.warning(
                f"Overriding existing strategy for channel type: {channel_type}",
                existing_strategy=type(self._strategies[channel_type]).__name__,
                new_strategy=type(strategy).__name__
            )
        
        self._strategies[channel_type] = strategy
        logger.info(
            f"Registered notification strategy",
            channel_type=channel_type,
            strategy_class=type(strategy).__name__
        )
    
    def get_strategy(self, channel_type: str) -> Optional[AbstractNotificationStrategy]:
        """Get strategy for channel type"""
        return self._strategies.get(channel_type)
    
    def get_supported_channels(self) -> Set[str]:
        """Get all supported channel types"""
        return set(self._strategies.keys())
    
    async def send_notification(self, request: NotificationRequest) -> bool:
        """Send notification using appropriate strategy"""
        channel_type = request.channel.channel_type
        strategy = self.get_strategy(channel_type)
        
        if not strategy:
            error_msg = f"No strategy registered for channel type: {channel_type}"
            logger.error(error_msg, request_id=request.request_id)
            request.mark_failed(error_msg)
            return False
        
        # Check rate limiting
        if self._rate_limiter.is_rate_limited(request.channel):
            logger.warning(
                f"Rate limit exceeded for channel",
                channel_id=request.channel.channel_id,
                request_id=request.request_id
            )
            request.mark_rate_limited()
            return False
        
        # Prepare content if not already done
        if not request.subject and not request.message:
            request.prepare_content()
        
        # Record attempt start
        attempt_start = datetime.now()
        
        try:
            # Send notification
            success = await strategy.send(request)
            
            # Calculate delivery time
            delivery_time = int((datetime.now() - attempt_start).total_seconds() * 1000)
            
            # Record attempt
            attempt = NotificationAttempt(
                channel_id=request.channel.channel_id,
                request_id=request.request_id,
                strategy_type=type(strategy).__name__,
                attempted_at=attempt_start,
                success=success,
                retry_count=request.retry_count,
                delivery_time_ms=delivery_time
            )
            self._attempt_history.append(attempt)
            
            # Update request status
            if success:
                request.mark_sent({"delivery_time_ms": delivery_time, "strategy": type(strategy).__name__})
                self._rate_limiter.record_sent(request.channel)
                logger.info(
                    f"Notification sent successfully",
                    request_id=request.request_id,
                    channel_id=request.channel.channel_id,
                    delivery_time_ms=delivery_time
                )
            else:
                request.mark_failed("Strategy returned failure")
                logger.error(
                    f"Notification strategy returned failure",
                    request_id=request.request_id,
                    channel_id=request.channel.channel_id
                )
            
            return success
            
        except Exception as e:
            error_msg = str(e)
            delivery_time = int((datetime.now() - attempt_start).total_seconds() * 1000)
            
            # Record failed attempt
            attempt = NotificationAttempt(
                channel_id=request.channel.channel_id,
                request_id=request.request_id,
                strategy_type=type(strategy).__name__,
                attempted_at=attempt_start,
                success=False,
                error_message=error_msg,
                retry_count=request.retry_count,
                delivery_time_ms=delivery_time
            )
            self._attempt_history.append(attempt)
            
            request.mark_failed(error_msg)
            logger.error(
                f"Notification failed with exception",
                request_id=request.request_id,
                channel_id=request.channel.channel_id,
                error=error_msg
            )
            
            return False
    
    async def validate_channel_config(self, channel: NotificationChannel) -> bool:
        """Validate channel configuration"""
        strategy = self.get_strategy(channel.channel_type)
        if not strategy:
            return False
        
        try:
            return await strategy.validate_config(channel.config)
        except Exception as e:
            logger.error(
                f"Failed to validate channel config",
                channel_id=channel.channel_id,
                error=str(e)
            )
            return False
    
    def get_delivery_statistics(self, hours: int = 24) -> Dict[str, any]:
        """Get delivery statistics for specified time window"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_attempts = [
            attempt for attempt in self._attempt_history
            if attempt.attempted_at >= cutoff
        ]
        
        if not recent_attempts:
            return {
                "time_window_hours": hours,
                "total_attempts": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
                "success_rate": 0.0,
                "average_delivery_time_ms": 0.0,
                "by_channel_type": {},
                "by_strategy": {}
            }
        
        successful = [a for a in recent_attempts if a.success]
        failed = [a for a in recent_attempts if not a.success]
        
        # Calculate average delivery time for successful attempts
        delivery_times = [a.delivery_time_ms for a in successful if a.delivery_time_ms]
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0.0
        
        # Group by channel type
        by_channel = {}
        for attempt in recent_attempts:
            channel_type = attempt.strategy_type  # Simplified - could extract from strategy
            if channel_type not in by_channel:
                by_channel[channel_type] = {"attempts": 0, "successes": 0}
            by_channel[channel_type]["attempts"] += 1
            if attempt.success:
                by_channel[channel_type]["successes"] += 1
        
        # Add success rates
        for channel_type in by_channel:
            stats = by_channel[channel_type]
            stats["success_rate"] = stats["successes"] / stats["attempts"] if stats["attempts"] > 0 else 0.0
        
        # Group by strategy type
        by_strategy = {}
        for attempt in recent_attempts:
            strategy_type = attempt.strategy_type
            if strategy_type not in by_strategy:
                by_strategy[strategy_type] = {"attempts": 0, "successes": 0}
            by_strategy[strategy_type]["attempts"] += 1
            if attempt.success:
                by_strategy[strategy_type]["successes"] += 1
        
        # Add success rates
        for strategy_type in by_strategy:
            stats = by_strategy[strategy_type]
            stats["success_rate"] = stats["successes"] / stats["attempts"] if stats["attempts"] > 0 else 0.0
        
        return {
            "time_window_hours": hours,
            "total_attempts": len(recent_attempts),
            "successful_deliveries": len(successful),
            "failed_deliveries": len(failed),
            "success_rate": len(successful) / len(recent_attempts),
            "average_delivery_time_ms": avg_delivery_time,
            "by_channel_type": by_channel,
            "by_strategy": by_strategy
        }
    
    def cleanup_old_attempts(self, days: int = 7) -> None:
        """Clean up old attempt history"""
        cutoff = datetime.now() - timedelta(days=days)
        initial_count = len(self._attempt_history)
        
        self._attempt_history = [
            attempt for attempt in self._attempt_history
            if attempt.attempted_at >= cutoff
        ]
        
        cleaned_count = initial_count - len(self._attempt_history)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old notification attempts")


class NotificationRateLimiter:
    """Rate limiter for notification channels"""
    
    def __init__(self):
        self._sent_history: Dict[str, List[datetime]] = {}
    
    def is_rate_limited(self, channel: NotificationChannel) -> bool:
        """Check if channel is rate limited"""
        if not channel.rate_limit_per_hour:
            return False
        
        channel_id = channel.channel_id
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        # Get recent send times
        if channel_id not in self._sent_history:
            self._sent_history[channel_id] = []
        
        # Clean up old history
        self._sent_history[channel_id] = [
            timestamp for timestamp in self._sent_history[channel_id]
            if timestamp >= cutoff
        ]
        
        # Check if over limit
        return len(self._sent_history[channel_id]) >= channel.rate_limit_per_hour
    
    def record_sent(self, channel: NotificationChannel) -> None:
        """Record that a notification was sent"""
        channel_id = channel.channel_id
        if channel_id not in self._sent_history:
            self._sent_history[channel_id] = []
        
        self._sent_history[channel_id].append(datetime.now())
    
    def get_remaining_quota(self, channel: NotificationChannel) -> Optional[int]:
        """Get remaining quota for channel"""
        if not channel.rate_limit_per_hour:
            return None
        
        channel_id = channel.channel_id
        cutoff = datetime.now() - timedelta(hours=1)
        
        if channel_id not in self._sent_history:
            return channel.rate_limit_per_hour
        
        # Count recent sends
        recent_sends = [
            timestamp for timestamp in self._sent_history[channel_id]
            if timestamp >= cutoff
        ]
        
        return max(0, channel.rate_limit_per_hour - len(recent_sends))
    
    def reset_quota(self, channel_id: str) -> None:
        """Reset quota for channel (admin function)"""
        self._sent_history.pop(channel_id, None)
        logger.info(f"Reset rate limit quota for channel {channel_id}")


class NotificationPriorityQueue:
    """Priority queue for notification requests"""
    
    def __init__(self):
        self._queues: Dict[NotificationPriority, List[NotificationRequest]] = {
            NotificationPriority.URGENT: [],
            NotificationPriority.HIGH: [],
            NotificationPriority.NORMAL: [],
            NotificationPriority.LOW: []
        }
    
    def enqueue(self, request: NotificationRequest) -> None:
        """Add request to appropriate priority queue"""
        self._queues[request.priority].append(request)
        logger.debug(
            f"Enqueued notification request",
            request_id=request.request_id,
            priority=request.priority.value
        )
    
    def dequeue(self) -> Optional[NotificationRequest]:
        """Get next request in priority order"""
        # Process in priority order: URGENT -> HIGH -> NORMAL -> LOW
        for priority in [NotificationPriority.URGENT, NotificationPriority.HIGH, 
                        NotificationPriority.NORMAL, NotificationPriority.LOW]:
            if self._queues[priority]:
                return self._queues[priority].pop(0)
        
        return None
    
    def peek(self) -> Optional[NotificationRequest]:
        """Peek at next request without removing it"""
        for priority in [NotificationPriority.URGENT, NotificationPriority.HIGH, 
                        NotificationPriority.NORMAL, NotificationPriority.LOW]:
            if self._queues[priority]:
                return self._queues[priority][0]
        
        return None
    
    def size(self) -> int:
        """Get total number of queued requests"""
        return sum(len(queue) for queue in self._queues.values())
    
    def size_by_priority(self) -> Dict[str, int]:
        """Get queue sizes by priority"""
        return {
            priority.value: len(queue)
            for priority, queue in self._queues.items()
        }
    
    def clear_expired(self, max_age_minutes: int = 60) -> int:
        """Remove expired requests from all queues"""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        removed_count = 0
        
        for priority in self._queues:
            initial_size = len(self._queues[priority])
            self._queues[priority] = [
                req for req in self._queues[priority]
                if req.created_at >= cutoff
            ]
            removed_count += initial_size - len(self._queues[priority])
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} expired notification requests from queue")
        
        return removed_count
    
    def clear_all(self) -> None:
        """Clear all queues"""
        total_removed = self.size()
        for queue in self._queues.values():
            queue.clear()
        
        if total_removed > 0:
            logger.info(f"Cleared {total_removed} notification requests from all queues")
