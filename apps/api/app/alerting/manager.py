"""
Alert Manager
Core alert management and coordination between evaluation and notification systems
"""

import asyncio
import uuid
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import redis.asyncio as aioredis
import structlog

from .models import AlertRule, Alert, NotificationChannel, AlertSeverity, AlertStatus, AlertChannel
from .evaluation.evaluator import AlertEvaluator
from .notification.sender import NotificationSender
from .metrics import MetricsCollector

logger = structlog.get_logger()


class AlertManager:
    """Main alert management system"""

    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.alert_rules: Dict[str, AlertRule] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.evaluator = AlertEvaluator()
        self.notification_sender = NotificationSender()
        self.metrics_collector = MetricsCollector()
        self.evaluation_task: Optional[asyncio.Task] = None

        # Rate limiting for notifications
        self.notification_history: Dict[str, List[datetime]] = {}

        # Load default alert rules
        self._load_default_rules()

    async def initialize_redis(self):
        """Initialize Redis connection"""
        try:
            from app.config import settings
            self.redis_client = aioredis.from_url(
                f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/4",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Alert manager Redis connection initialized")

            # Load persisted rules and channels
            await self._load_persisted_data()

        except Exception as e:
            logger.error("Failed to initialize alert manager Redis", error=str(e))

    async def start_monitoring(self):
        """Start alert monitoring task"""
        if self.evaluation_task and not self.evaluation_task.done():
            logger.warning("Alert monitoring already running")
            return

        logger.info("Starting alert monitoring")
        self.evaluation_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop alert monitoring task"""
        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass
            logger.info("Alert monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._evaluate_all_rules()
                await asyncio.sleep(30)  # Evaluate every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error

    async def _evaluate_all_rules(self):
        """Evaluate all active alert rules"""
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue

            try:
                # Check if rule is in cooldown
                if await self._is_in_cooldown(rule.rule_id):
                    continue

                # Get current metric value
                current_value = await self.metrics_collector.get_metric_value(
                    rule.metric_name, rule.evaluation_window
                )

                if current_value is None:
                    continue

                # Evaluate rule
                should_trigger = self.evaluator.evaluate_rule(rule, current_value)

                if should_trigger:
                    # Check if alert already exists
                    existing_alert = await self._get_active_alert(rule.rule_id)
                    if existing_alert:
                        continue  # Alert already active

                    # Create new alert
                    alert = Alert(
                        alert_id=str(uuid.uuid4()),
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        status=AlertStatus.TRIGGERED,
                        title=rule.name,
                        description=rule.description,
                        metric_value=current_value,
                        threshold_value=rule.threshold_value,
                        triggered_at=datetime.now(),
                        context=await self.metrics_collector.get_alert_context(rule, current_value)
                    )

                    await self._trigger_alert(alert, rule)

            except Exception as e:
                logger.error("Failed to evaluate rule", rule_id=rule.rule_id, error=str(e))

    async def _trigger_alert(self, alert: Alert, rule: AlertRule):
        """Trigger an alert and send notifications"""
        try:
            # Store alert
            await self._store_alert(alert)
            self.active_alerts[alert.alert_id] = alert

            # Send notifications
            for channel_type in rule.channels:
                await self._send_notification(alert, channel_type)

            # Set cooldown
            await self._set_cooldown(rule.rule_id, rule.cooldown_period)

            logger.info("Alert triggered",
                       alert_id=alert.alert_id,
                       rule_id=rule.rule_id,
                       severity=alert.severity.value,
                       metric_value=alert.metric_value)

        except Exception as e:
            logger.error("Failed to trigger alert", alert_id=alert.alert_id, error=str(e))

    async def _send_notification(self, alert: Alert, channel_type: AlertChannel):
        """Send notification through specified channel"""
        try:
            # Find configured channels of this type
            matching_channels = [
                ch for ch in self.notification_channels.values()
                if ch.channel_type == channel_type and ch.enabled
            ]

            if not matching_channels:
                logger.warning("No configured channels found", channel_type=channel_type.value)
                return

            # Send to each matching channel
            for channel in matching_channels:
                # Check rate limiting
                if not await self._check_rate_limit(channel):
                    logger.warning("Rate limit exceeded for channel", channel_id=channel.channel_id)
                    continue

                success = await self.notification_sender.send_notification(channel, alert)

                if success:
                    alert.notifications_sent.append(f"{channel.channel_type.value}:{channel.channel_id}")
                    await self._record_notification(channel)

        except Exception as e:
            logger.error("Failed to send notification",
                        alert_id=alert.alert_id,
                        channel_type=channel_type.value,
                        error=str(e))

    async def _check_rate_limit(self, channel: NotificationChannel) -> bool:
        """Check if channel is within rate limit"""
        if not channel.rate_limit:
            return True

        now = datetime.now()
        channel_id = channel.channel_id

        if channel_id not in self.notification_history:
            self.notification_history[channel_id] = []

        # Remove old notifications (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self.notification_history[channel_id] = [
            ts for ts in self.notification_history[channel_id] if ts > cutoff
        ]

        # Check if under limit
        return len(self.notification_history[channel_id]) < channel.rate_limit

    async def _record_notification(self, channel: NotificationChannel):
        """Record notification for rate limiting"""
        now = datetime.now()
        if channel.channel_id not in self.notification_history:
            self.notification_history[channel.channel_id] = []

        self.notification_history[channel.channel_id].append(now)

    async def _is_in_cooldown(self, rule_id: str) -> bool:
        """Check if rule is in cooldown period"""
        if not self.redis_client:
            return False

        cooldown_key = f"alert:cooldown:{rule_id}"
        cooldown_time = await self.redis_client.get(cooldown_key)
        return cooldown_time is not None

    async def _set_cooldown(self, rule_id: str, cooldown_seconds: int):
        """Set cooldown period for rule"""
        if self.redis_client:
            cooldown_key = f"alert:cooldown:{rule_id}"
            await self.redis_client.setex(cooldown_key, cooldown_seconds, "1")

    async def _get_active_alert(self, rule_id: str) -> Optional[Alert]:
        """Get active alert for rule"""
        return next((alert for alert in self.active_alerts.values()
                    if alert.rule_id == rule_id and alert.status == AlertStatus.TRIGGERED), None)

    async def _store_alert(self, alert: Alert):
        """Store alert in Redis"""
        if self.redis_client:
            alert_key = f"alert:{alert.alert_id}"
            alert_data = {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "title": alert.title,
                "description": alert.description,
                "metric_value": alert.metric_value,
                "threshold_value": alert.threshold_value,
                "triggered_at": alert.triggered_at.isoformat(),
                "context": json.dumps(alert.context),
                "notifications_sent": json.dumps(alert.notifications_sent)
            }
            await self.redis_client.hset(alert_key, mapping=alert_data)
            await self.redis_client.expire(alert_key, 86400 * 7)  # 7 days

    def _load_default_rules(self):
        """Load default alert rules"""
        default_rules = [
            AlertRule(
                rule_id="high_response_time",
                name="High Response Time",
                description="API response time is above acceptable threshold",
                severity=AlertSeverity.HIGH,
                metric_name="avg_response_time",
                threshold_value=1000.0,  # 1 second
                comparison_operator=">",
                evaluation_window=300,
                trigger_count=3,
                cooldown_period=600,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
            ),
            AlertRule(
                rule_id="high_error_rate",
                name="High Error Rate",
                description="Error rate is above acceptable threshold",
                severity=AlertSeverity.CRITICAL,
                metric_name="error_rate",
                threshold_value=0.05,  # 5%
                comparison_operator=">",
                evaluation_window=300,
                trigger_count=2,
                cooldown_period=300,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK]
            )
        ]

        for rule in default_rules:
            self.alert_rules[rule.rule_id] = rule

    async def _load_persisted_data(self):
        """Load persisted rules and channels from Redis"""
        if not self.redis_client:
            return

        try:
            # Load alert rules
            rules_pattern = "alert_rule:*"
            rule_keys = await self.redis_client.keys(rules_pattern)
            for key in rule_keys:
                rule_data = await self.redis_client.hgetall(key)
                if rule_data:
                    # Reconstruct rule object
                    # Implementation would depend on serialization format
                    pass

            # Load notification channels
            channels_pattern = "notification_channel:*"
            channel_keys = await self.redis_client.keys(channels_pattern)
            for key in channel_keys:
                channel_data = await self.redis_client.hgetall(key)
                if channel_data:
                    # Reconstruct channel object
                    # Implementation would depend on serialization format
                    pass

        except Exception as e:
            logger.error("Failed to load persisted data", error=str(e))

    async def add_alert_rule(self, rule: AlertRule):
        """Add new alert rule"""
        self.alert_rules[rule.rule_id] = rule

        # Persist to Redis
        if self.redis_client:
            rule_key = f"alert_rule:{rule.rule_id}"
            # Store rule data - implementation depends on serialization needs

    async def add_notification_channel(self, channel: NotificationChannel):
        """Add new notification channel"""
        self.notification_channels[channel.channel_id] = channel

        # Persist to Redis
        if self.redis_client:
            channel_key = f"notification_channel:{channel.channel_id}"
            # Store channel data - implementation depends on serialization needs

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.acknowledged_by = acknowledged_by
            await self._store_alert(alert)

    async def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            await self._store_alert(alert)
            del self.active_alerts[alert_id]

    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())

    async def shutdown(self):
        """Shutdown alert manager"""
        await self.stop_monitoring()
        await self.notification_sender.close()
        if self.redis_client:
            await self.redis_client.close()


# Global instance
alert_manager = AlertManager()