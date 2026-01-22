"""
Alert Manager
Main alert management system orchestrating evaluation, triggering, and lifecycle management.
"""

import asyncio
import time
import uuid
import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import redis.asyncio as aioredis
import structlog

from app.config import settings
from app.monitoring.apm import apm_collector
from app.logging.log_analyzer import log_analyzer

from .alert_types import AlertSeverity, AlertStatus, AlertChannel
from .alert_models import AlertRule, Alert, NotificationChannel
from .alert_evaluator import AlertEvaluator
from .notification_sender import NotificationSender

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
        self.evaluation_task: Optional[asyncio.Task] = None

        # Rate limiting for notifications
        self.notification_history: Dict[str, List[datetime]] = {}

        # Load default alert rules
        self._load_default_rules()

    async def initialize_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = aioredis.from_url(
                f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/4",
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("Alert manager Redis connection initialized")

            # Load persisted rules and channels
            await self._load_persisted_data()

        except Exception as e:
            logger.error("Failed to initialize alert manager Redis", error=str(e))

    def _load_default_rules(self):
        """Load default alert rules"""
        default_rules = [
            AlertRule(
                rule_id="high_response_time",
                name="High Response Time",
                description="API response time is above threshold",
                severity=AlertSeverity.HIGH,
                metric_name="avg_response_time",
                threshold_value=2000.0,  # 2 seconds
                comparison_operator=">",
                evaluation_window=300,  # 5 minutes
                trigger_count=3,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
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
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            ),
            AlertRule(
                rule_id="low_disk_space",
                name="Low Disk Space",
                description="Available disk space is running low",
                severity=AlertSeverity.HIGH,
                metric_name="disk_usage_percent",
                threshold_value=85.0,
                comparison_operator=">",
                evaluation_window=600,  # 10 minutes
                trigger_count=1,
                channels=[AlertChannel.EMAIL],
            ),
            AlertRule(
                rule_id="high_memory_usage",
                name="High Memory Usage",
                description="Memory usage is critically high",
                severity=AlertSeverity.CRITICAL,
                metric_name="memory_usage_percent",
                threshold_value=90.0,
                comparison_operator=">",
                evaluation_window=300,
                trigger_count=2,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            ),
            AlertRule(
                rule_id="database_connection_failure",
                name="Database Connection Failure",
                description="Unable to connect to database",
                severity=AlertSeverity.CRITICAL,
                metric_name="database_connection_errors",
                threshold_value=0,
                comparison_operator=">",
                evaluation_window=60,
                trigger_count=1,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            ),
            AlertRule(
                rule_id="security_events",
                name="Security Events Detected",
                description="Security threats or anomalies detected",
                severity=AlertSeverity.HIGH,
                metric_name="security_events_count",
                threshold_value=5,
                comparison_operator=">",
                evaluation_window=300,
                trigger_count=1,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            ),
        ]

        for rule in default_rules:
            self.alert_rules[rule.rule_id] = rule

    async def _load_persisted_data(self):
        """Load alert rules and channels from Redis"""
        if not self.redis_client:
            return

        try:
            # Load alert rules
            rule_keys = await self.redis_client.smembers("alert:rules")
            for rule_id in rule_keys:
                rule_data = await self.redis_client.hgetall(f"alert:rule:{rule_id}")
                if rule_data:
                    # Reconstruct AlertRule object
                    rule = AlertRule(
                        rule_id=rule_data["rule_id"],
                        name=rule_data["name"],
                        description=rule_data["description"],
                        severity=AlertSeverity(rule_data["severity"]),
                        metric_name=rule_data["metric_name"],
                        threshold_value=float(rule_data["threshold_value"]),
                        comparison_operator=rule_data["comparison_operator"],
                        evaluation_window=int(rule_data["evaluation_window"]),
                        trigger_count=int(rule_data.get("trigger_count", 1)),
                        cooldown_period=int(rule_data.get("cooldown_period", 300)),
                        enabled=rule_data.get("enabled", "true").lower() == "true",
                        channels=[
                            AlertChannel(ch) for ch in json.loads(rule_data.get("channels", "[]"))
                        ],
                        conditions=json.loads(rule_data.get("conditions", "{}")),
                        metadata=json.loads(rule_data.get("metadata", "{}")),
                    )
                    self.alert_rules[rule_id] = rule

            # Load notification channels
            channel_keys = await self.redis_client.smembers("alert:channels")
            for channel_id in channel_keys:
                channel_data = await self.redis_client.hgetall(f"alert:channel:{channel_id}")
                if channel_data:
                    channel = NotificationChannel(
                        channel_id=channel_data["channel_id"],
                        channel_type=AlertChannel(channel_data["channel_type"]),
                        name=channel_data["name"],
                        config=json.loads(channel_data["config"]),
                        enabled=channel_data.get("enabled", "true").lower() == "true",
                        rate_limit=int(channel_data["rate_limit"])
                        if channel_data.get("rate_limit")
                        else None,
                    )
                    self.notification_channels[channel_id] = channel

        except Exception as e:
            logger.error("Failed to load persisted alert data", error=str(e))

    async def start_monitoring(self):
        """Start the alert evaluation loop"""
        if self.evaluation_task and not self.evaluation_task.done():
            return

        self.evaluation_task = asyncio.create_task(self._evaluation_loop())
        logger.info("Alert monitoring started")

    async def stop_monitoring(self):
        """Stop the alert evaluation loop"""
        if self.evaluation_task and not self.evaluation_task.done():
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass  # Expected when task is cancelled during graceful shutdown

        logger.info("Alert monitoring stopped")

    async def _evaluation_loop(self):
        """Main evaluation loop"""
        while True:
            try:
                await self._evaluate_all_rules()
                await asyncio.sleep(30)  # Evaluate every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in alert evaluation loop", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error

    async def _evaluate_all_rules(self):
        """Evaluate all alert rules"""
        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            try:
                await self._evaluate_rule(rule)
            except Exception as e:
                logger.error("Failed to evaluate rule", rule_id=rule_id, error=str(e))

    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule"""
        # Get current metric value
        current_value = await self._get_metric_value(rule.metric_name, rule.evaluation_window)

        if current_value is None:
            logger.debug("No metric value available", metric=rule.metric_name, rule_id=rule.rule_id)
            return

        # Check if rule should trigger
        should_trigger = self.evaluator.evaluate_rule(rule, current_value)

        if should_trigger:
            # Check cooldown period
            if await self._is_in_cooldown(rule.rule_id):
                return

            # Check if alert already exists
            existing_alert = await self._get_active_alert(rule.rule_id)
            if existing_alert:
                return

            # Create and trigger alert
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
                context=await self._get_alert_context(rule, current_value),
            )

            await self._trigger_alert(alert, rule)

    async def _get_metric_value(self, metric_name: str, window_seconds: int) -> Optional[float]:
        """Get current metric value"""
        try:
            if metric_name == "avg_response_time":
                # Get from APM data
                perf_summary = await apm_collector.get_performance_summary("all", hours=1)
                return perf_summary.get("performance", {}).get("avg_duration_ms", 0)

            elif metric_name == "error_rate":
                perf_summary = await apm_collector.get_performance_summary("all", hours=1)
                return perf_summary.get("errors", {}).get("error_rate", 0)

            elif metric_name == "memory_usage_percent":
                # Would integrate with system monitoring
                return 75.0  # Placeholder

            elif metric_name == "disk_usage_percent":
                # Would integrate with system monitoring
                return 70.0  # Placeholder

            elif metric_name == "database_connection_errors":
                # Would check database connection health
                return 0  # Placeholder

            elif metric_name == "security_events_count":
                # Get from log analyzer
                log_stats = await log_analyzer.get_log_statistics(hours=1)
                return log_stats.get("security", {}).get("security_events", 0)

            else:
                logger.warning("Unknown metric name", metric_name=metric_name)
                return None

        except Exception as e:
            logger.error("Failed to get metric value", metric_name=metric_name, error=str(e))
            return None

    async def _get_alert_context(self, rule: AlertRule, current_value: float) -> Dict[str, Any]:
        """Get additional context for alert"""
        context = {
            "metric_name": rule.metric_name,
            "evaluation_window": rule.evaluation_window,
            "comparison": f"{current_value} {rule.comparison_operator} {rule.threshold_value}",
        }

        # Add rule-specific context
        if rule.metric_name == "avg_response_time":
            # Add slowest endpoints
            perf_summary = await apm_collector.get_performance_summary("all", hours=1)
            context["slowest_endpoints"] = perf_summary.get("performance", {}).get(
                "slowest_endpoints", []
            )[:5]

        elif rule.metric_name == "error_rate":
            # Add error distribution
            log_stats = await log_analyzer.get_log_statistics(hours=1)
            context["error_types"] = log_stats.get("errors", {}).get("error_types", {})

        return context

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

            logger.info(
                "Alert triggered",
                alert_id=alert.alert_id,
                rule_id=rule.rule_id,
                severity=alert.severity.value,
                metric_value=alert.metric_value,
            )

        except Exception as e:
            logger.error("Failed to trigger alert", alert_id=alert.alert_id, error=str(e))

    async def _send_notification(self, alert: Alert, channel_type: AlertChannel):
        """Send notification through specified channel"""
        try:
            # Find configured channels of this type
            matching_channels = [
                ch
                for ch in self.notification_channels.values()
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

                success = False
                if channel_type == AlertChannel.EMAIL:
                    success = await self.notification_sender.send_email(channel, alert)
                elif channel_type == AlertChannel.SLACK:
                    success = await self.notification_sender.send_slack(channel, alert)
                elif channel_type == AlertChannel.WEBHOOK:
                    success = await self.notification_sender.send_webhook(channel, alert)
                elif channel_type == AlertChannel.DISCORD:
                    success = await self.notification_sender.send_discord(channel, alert)

                if success:
                    alert.notifications_sent.append(
                        f"{channel.channel_type.value}:{channel.channel_id}"
                    )
                    await self._record_notification(channel)

        except Exception as e:
            logger.error(
                "Failed to send notification",
                alert_id=alert.alert_id,
                channel_type=channel_type.value,
                error=str(e),
            )

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
        return next(
            (
                alert
                for alert in self.active_alerts.values()
                if alert.rule_id == rule_id and alert.status == AlertStatus.TRIGGERED
            ),
            None,
        )

    async def _store_alert(self, alert: Alert):
        """Store alert in Redis"""
        if not self.redis_client:
            return

        try:
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
                "notifications_sent": json.dumps(alert.notifications_sent),
            }

            await self.redis_client.hset(f"alert:instance:{alert.alert_id}", mapping=alert_data)
            await self.redis_client.zadd("alerts:timeline", {alert.alert_id: time.time()})

            # Set expiration (keep alerts for 90 days)
            await self.redis_client.expire(f"alert:instance:{alert.alert_id}", 7776000)

        except Exception as e:
            logger.error("Failed to store alert", alert_id=alert.alert_id, error=str(e))

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = acknowledged_by

                await self._store_alert(alert)

                logger.info(
                    "Alert acknowledged", alert_id=alert_id, acknowledged_by=acknowledged_by
                )
                return True

            return False

        except Exception as e:
            logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
            return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()

                await self._store_alert(alert)
                del self.active_alerts[alert_id]

                logger.info("Alert resolved", alert_id=alert_id)
                return True

            return False

        except Exception as e:
            logger.error("Failed to resolve alert", alert_id=alert_id, error=str(e))
            return False

    async def get_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get alert statistics"""
        if not self.redis_client:
            return {"error": "Redis not available"}

        try:
            cutoff_time = time.time() - (hours * 3600)
            alert_ids = await self.redis_client.zrangebyscore(
                "alerts:timeline", cutoff_time, "+inf"
            )

            alerts = []
            for alert_id in alert_ids:
                alert_data = await self.redis_client.hgetall(f"alert:instance:{alert_id}")
                if alert_data:
                    alerts.append(alert_data)

            # Statistics
            total_alerts = len(alerts)
            severity_counts = Counter(alert["severity"] for alert in alerts)
            status_counts = Counter(alert["status"] for alert in alerts)
            rule_counts = Counter(alert["rule_id"] for alert in alerts)

            return {
                "time_range_hours": hours,
                "total_alerts": total_alerts,
                "severity_distribution": dict(severity_counts),
                "status_distribution": dict(status_counts),
                "top_triggered_rules": dict(rule_counts.most_common(10)),
                "active_alerts": len(self.active_alerts),
            }

        except Exception as e:
            logger.error("Failed to get alert statistics", error=str(e))
            return {"error": "Failed to retrieve statistics"}

    async def cleanup(self):
        """Cleanup resources"""
        await self.stop_monitoring()
        await self.notification_sender.close()
