"""
Infrastructure layer repositories for the alerting system.
Provides Redis-backed storage for alerts and rules.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import redis.asyncio as redis

from ..domain.models.alert import Alert, AlertStatus, AlertSeverity, AlertMetrics
from ..domain.models.rule import AlertRule, RuleCondition, ComparisonOperator
from ..domain.models.notification import NotificationChannel, NotificationTemplate
from ..application.services.alert_orchestrator import AlertRepository, RuleRepository
from ..application.services.notification_dispatcher import ChannelRepository, TemplateRepository

import structlog
logger = structlog.get_logger()


class RedisAlertRepository(AlertRepository):
    """Redis-backed repository for alert persistence"""

    ALERT_PREFIX = "alert:"
    ACTIVE_ALERTS_KEY = "alerts:active"
    RULE_ALERTS_PREFIX = "alerts:rule:"

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._alert_ttl_seconds = 86400 * 7  # 7 days

    async def save_alert(self, alert: Alert) -> None:
        """Save alert to Redis"""
        try:
            alert_key = f"{self.ALERT_PREFIX}{alert.alert_id}"
            alert_data = self._serialize_alert(alert)

            # Store alert data with TTL
            await self._redis.setex(
                alert_key,
                self._alert_ttl_seconds,
                json.dumps(alert_data)
            )

            # Add to active alerts set if active
            if alert.is_active():
                await self._redis.sadd(self.ACTIVE_ALERTS_KEY, alert.alert_id)
            else:
                await self._redis.srem(self.ACTIVE_ALERTS_KEY, alert.alert_id)

            # Index by rule ID
            rule_key = f"{self.RULE_ALERTS_PREFIX}{alert.rule_id}"
            await self._redis.sadd(rule_key, alert.alert_id)

            logger.debug(f"Saved alert {alert.alert_id} to Redis")

        except Exception as e:
            logger.error(f"Failed to save alert to Redis: {e}")
            raise

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        try:
            alert_key = f"{self.ALERT_PREFIX}{alert_id}"
            data = await self._redis.get(alert_key)

            if not data:
                return None

            return self._deserialize_alert(json.loads(data))

        except Exception as e:
            logger.error(f"Failed to get alert from Redis: {e}")
            return None

    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        try:
            alert_ids = await self._redis.smembers(self.ACTIVE_ALERTS_KEY)
            alerts = []

            for alert_id in alert_ids:
                alert = await self.get_alert(alert_id.decode() if isinstance(alert_id, bytes) else alert_id)
                if alert and alert.is_active():
                    alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []

    async def get_alerts_by_rule(self, rule_id: str) -> List[Alert]:
        """Get alerts for specific rule"""
        try:
            rule_key = f"{self.RULE_ALERTS_PREFIX}{rule_id}"
            alert_ids = await self._redis.smembers(rule_key)
            alerts = []

            for alert_id in alert_ids:
                alert = await self.get_alert(alert_id.decode() if isinstance(alert_id, bytes) else alert_id)
                if alert:
                    alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Failed to get alerts by rule: {e}")
            return []

    async def update_alert_status(self, alert_id: str, status: AlertStatus, metadata: Dict[str, Any] = None) -> bool:
        """Update alert status"""
        try:
            alert = await self.get_alert(alert_id)
            if not alert:
                return False

            # Update status based on status type
            if status == AlertStatus.ACKNOWLEDGED:
                alert.acknowledge(metadata.get("acknowledged_by", "system") if metadata else "system")
            elif status == AlertStatus.RESOLVED:
                alert.resolve(metadata.get("resolved_by") if metadata else None)
            elif status == AlertStatus.ESCALATED:
                alert.escalate(metadata.get("reason", "status update") if metadata else "status update")
            elif status == AlertStatus.SUPPRESSED:
                alert.suppress(metadata.get("reason", "status update") if metadata else "status update")

            # Save updated alert
            await self.save_alert(alert)
            return True

        except Exception as e:
            logger.error(f"Failed to update alert status: {e}")
            return False

    def _serialize_alert(self, alert: Alert) -> Dict[str, Any]:
        """Serialize alert to dictionary"""
        return {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "title": alert.title,
            "description": alert.description,
            "metrics": {
                "metric_name": alert.metrics.metric_name,
                "current_value": alert.metrics.current_value,
                "threshold_value": alert.metrics.threshold_value,
                "comparison_operator": alert.metrics.comparison_operator,
                "evaluation_window_seconds": alert.metrics.evaluation_window_seconds
            } if alert.metrics else None,
            "triggered_at": alert.triggered_at.isoformat(),
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "escalated_at": alert.escalated_at.isoformat() if alert.escalated_at else None,
            "acknowledged_by": alert.acknowledged_by,
            "resolved_by": alert.resolved_by,
            "context": alert.context,
            "notifications_sent": alert.notifications_sent
        }

    def _deserialize_alert(self, data: Dict[str, Any]) -> Alert:
        """Deserialize alert from dictionary"""
        metrics = None
        if data.get("metrics"):
            m = data["metrics"]
            metrics = AlertMetrics(
                metric_name=m["metric_name"],
                current_value=m["current_value"],
                threshold_value=m["threshold_value"],
                comparison_operator=m["comparison_operator"],
                evaluation_window_seconds=m["evaluation_window_seconds"]
            )

        alert = Alert(
            alert_id=data["alert_id"],
            rule_id=data["rule_id"],
            severity=AlertSeverity(data["severity"]),
            status=AlertStatus(data["status"]),
            title=data["title"],
            description=data.get("description", ""),
            metrics=metrics,
            triggered_at=datetime.fromisoformat(data["triggered_at"]),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            escalated_at=datetime.fromisoformat(data["escalated_at"]) if data.get("escalated_at") else None,
            acknowledged_by=data.get("acknowledged_by"),
            resolved_by=data.get("resolved_by"),
            context=data.get("context", {}),
            notifications_sent=data.get("notifications_sent", [])
        )
        return alert


class RedisRuleRepository(RuleRepository):
    """Redis-backed repository for alert rule persistence"""

    RULE_PREFIX = "alert_rule:"
    ENABLED_RULES_KEY = "alert_rules:enabled"

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def get_enabled_rules(self) -> List[AlertRule]:
        """Get all enabled alert rules"""
        try:
            rule_ids = await self._redis.smembers(self.ENABLED_RULES_KEY)
            rules = []

            for rule_id in rule_ids:
                rule = await self.get_rule(rule_id.decode() if isinstance(rule_id, bytes) else rule_id)
                if rule and rule.enabled:
                    rules.append(rule)

            return rules

        except Exception as e:
            logger.error(f"Failed to get enabled rules: {e}")
            return []

    async def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get rule by ID"""
        try:
            rule_key = f"{self.RULE_PREFIX}{rule_id}"
            data = await self._redis.get(rule_key)

            if not data:
                return None

            return AlertRule.from_dict(json.loads(data))

        except Exception as e:
            logger.error(f"Failed to get rule from Redis: {e}")
            return None

    async def save_rule(self, rule: AlertRule) -> None:
        """Save rule to Redis"""
        try:
            rule_key = f"{self.RULE_PREFIX}{rule.rule_id}"
            rule_data = rule.to_dict()

            await self._redis.set(rule_key, json.dumps(rule_data))

            # Update enabled rules index
            if rule.enabled:
                await self._redis.sadd(self.ENABLED_RULES_KEY, rule.rule_id)
            else:
                await self._redis.srem(self.ENABLED_RULES_KEY, rule.rule_id)

            logger.debug(f"Saved rule {rule.rule_id} to Redis")

        except Exception as e:
            logger.error(f"Failed to save rule to Redis: {e}")
            raise


class InMemoryChannelRepository(ChannelRepository):
    """In-memory repository for notification channels (uses settings)"""

    def __init__(self, settings: Any = None):
        self._settings = settings
        self._channels: Dict[str, NotificationChannel] = {}
        self._load_default_channels()

    def _load_default_channels(self) -> None:
        """Load default notification channels from settings"""
        # Email channel (always available) - requires full config per domain model
        smtp_host = getattr(self._settings, "SMTP_HOST", "localhost") if self._settings else "localhost"
        smtp_user = getattr(self._settings, "SMTP_USER", "alerts@localhost") if self._settings else "alerts@localhost"
        smtp_pass = getattr(self._settings, "SMTP_PASSWORD", "") if self._settings else ""
        alert_emails = getattr(self._settings, "ALERT_EMAIL_RECIPIENTS", ["admin@localhost"]) if self._settings else ["admin@localhost"]

        self._channels["email_default"] = NotificationChannel(
            channel_id="email_default",
            channel_type="email",
            name="Default Email",
            enabled=True,
            config={
                "smtp_server": smtp_host,
                "username": smtp_user,
                "password": smtp_pass,
                "to_addresses": alert_emails
            }
        )

        # Slack channel if configured
        if self._settings and getattr(self._settings, "SLACK_WEBHOOK_URL", None):
            self._channels["slack_default"] = NotificationChannel(
                channel_id="slack_default",
                channel_type="slack",
                name="Default Slack",
                enabled=True,
                config={"webhook_url": self._settings.SLACK_WEBHOOK_URL}
            )

    async def get_enabled_channels(self, channel_types: List[str] = None) -> List[NotificationChannel]:
        """Get enabled notification channels"""
        channels = [ch for ch in self._channels.values() if ch.enabled]

        if channel_types:
            channels = [ch for ch in channels if ch.channel_type in channel_types]

        return channels

    async def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """Get channel by ID"""
        return self._channels.get(channel_id)

    async def get_channels_by_type(self, channel_type: str) -> List[NotificationChannel]:
        """Get channels of specific type"""
        return [ch for ch in self._channels.values() if ch.channel_type == channel_type]


class InMemoryTemplateRepository(TemplateRepository):
    """In-memory repository for notification templates"""

    def __init__(self):
        self._templates: Dict[str, NotificationTemplate] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """Load default notification templates"""
        # Email templates - NotificationTemplate uses subject_template, body_template, and variables
        for severity in ["low", "medium", "high", "critical"]:
            template_id = f"email_alert_{severity}"
            self._templates[template_id] = NotificationTemplate(
                template_id=template_id,
                channel_type="email",
                subject_template="[{severity}] {title}",
                body_template="""Alert: {title}
Severity: {severity}
Status: {status}

{description}

Triggered: {triggered_at}
""",
                variables=["severity", "title", "status", "description", "triggered_at"]
            )

        # Slack templates
        for severity in ["low", "medium", "high", "critical"]:
            template_id = f"slack_alert_{severity}"
            severity_emoji = {
                "low": ":information_source:",
                "medium": ":warning:",
                "high": ":rotating_light:",
                "critical": ":fire:"
            }
            emoji = severity_emoji.get(severity, ":bell:")
            self._templates[template_id] = NotificationTemplate(
                template_id=template_id,
                channel_type="slack",
                subject_template="",
                body_template=f"""{emoji} *{{title}}*
Severity: {{severity}}
Status: {{status}}

{{description}}
""",
                variables=["title", "severity", "status", "description"]
            )

    async def get_template(self, channel_type: str, template_name: str = "default") -> Optional[NotificationTemplate]:
        """Get notification template"""
        # Try exact match by template_id containing the template_name
        for template in self._templates.values():
            if template.channel_type == channel_type and template_name in template.template_id:
                return template

        # Fall back to any template of that type (prefer medium severity as default)
        default_template_id = f"{channel_type}_alert_medium"
        if default_template_id in self._templates:
            return self._templates[default_template_id]

        # Fall back to any template of that channel type
        for template in self._templates.values():
            if template.channel_type == channel_type:
                return template

        return None

    async def get_alert_template(self, channel_type: str, severity: str) -> Optional[NotificationTemplate]:
        """Get template for alert notifications"""
        template_id = f"{channel_type}_alert_{severity}"
        template = self._templates.get(template_id)

        if not template:
            # Fall back to medium severity template
            template = self._templates.get(f"{channel_type}_alert_medium")

        return template


def create_alert_repositories(redis_client: redis.Redis, settings: Any = None):
    """Factory function to create all alert repositories"""
    return {
        "alert_repository": RedisAlertRepository(redis_client),
        "rule_repository": RedisRuleRepository(redis_client),
        "channel_repository": InMemoryChannelRepository(settings),
        "template_repository": InMemoryTemplateRepository()
    }
