"""
Comprehensive Alerting System
Intelligent monitoring, threshold detection, and multi-channel notification system
"""

import asyncio
import time
import uuid
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import aioredis
import httpx
import structlog
from jinja2 import Template

from app.config import settings
from app.monitoring.apm import apm_collector
from app.logging.log_analyzer import log_analyzer

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states"""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    DISCORD = "discord"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    threshold_value: float
    comparison_operator: str  # >, <, >=, <=, ==, !=
    evaluation_window: int  # seconds
    trigger_count: int = 1  # consecutive evaluations to trigger
    cooldown_period: int = 300  # seconds between alerts
    enabled: bool = True
    channels: List[AlertChannel] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert instance"""
    alert_id: str
    rule_id: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    metric_value: float
    threshold_value: float
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    notifications_sent: List[str] = field(default_factory=list)


@dataclass
class NotificationChannel:
    """Notification channel configuration"""
    channel_id: str
    channel_type: AlertChannel
    name: str
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit: Optional[int] = None  # max notifications per hour


class AlertEvaluator:
    """Evaluates metrics against alert rules"""

    def __init__(self):
        self.evaluation_history: Dict[str, List[bool]] = {}

    def evaluate_rule(self, rule: AlertRule, current_value: float) -> bool:
        """Evaluate a single rule against current metric value"""
        threshold = rule.threshold_value
        operator = rule.comparison_operator

        # Perform comparison
        if operator == ">":
            result = current_value > threshold
        elif operator == "<":
            result = current_value < threshold
        elif operator == ">=":
            result = current_value >= threshold
        elif operator == "<=":
            result = current_value <= threshold
        elif operator == "==":
            result = current_value == threshold
        elif operator == "!=":
            result = current_value != threshold
        else:
            logger.warning("Unknown comparison operator", operator=operator, rule_id=rule.rule_id)
            return False

        # Track evaluation history for trigger count logic
        if rule.rule_id not in self.evaluation_history:
            self.evaluation_history[rule.rule_id] = []

        self.evaluation_history[rule.rule_id].append(result)

        # Keep only recent evaluations
        max_history = max(rule.trigger_count, 10)
        self.evaluation_history[rule.rule_id] = self.evaluation_history[rule.rule_id][-max_history:]

        # Check if we have enough consecutive positive evaluations
        recent_evaluations = self.evaluation_history[rule.rule_id][-rule.trigger_count:]

        if len(recent_evaluations) >= rule.trigger_count:
            return all(recent_evaluations)

        return False


class NotificationSender:
    """Handles sending notifications through various channels"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def send_email(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send email notification"""
        try:
            config = channel.config
            smtp_server = config.get('smtp_server')
            smtp_port = config.get('smtp_port', 587)
            username = config.get('username')
            password = config.get('password')
            to_addresses = config.get('to_addresses', [])

            if not all([smtp_server, username, password, to_addresses]):
                logger.error("Incomplete email configuration", channel_id=channel.channel_id)
                return False

            # Create email content
            subject = f"[{alert.severity.value.upper()}] {alert.title}"

            # HTML email template
            html_template = Template("""
            <html>
            <head><title>Plinto Alert</title></head>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: {{ severity_color }}; color: white; padding: 20px; text-align: center;">
                        <h1>{{ severity.upper() }} ALERT</h1>
                    </div>
                    <div style="padding: 20px; background-color: #f9f9f9;">
                        <h2>{{ title }}</h2>
                        <p><strong>Description:</strong> {{ description }}</p>
                        <p><strong>Triggered At:</strong> {{ triggered_at }}</p>
                        <p><strong>Current Value:</strong> {{ metric_value }}</p>
                        <p><strong>Threshold:</strong> {{ threshold_value }}</p>

                        {% if context %}
                        <h3>Additional Context:</h3>
                        <ul>
                        {% for key, value in context.items() %}
                            <li><strong>{{ key }}:</strong> {{ value }}</li>
                        {% endfor %}
                        </ul>
                        {% endif %}

                        <div style="margin-top: 30px; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #2196F3;">
                            <p><strong>Alert ID:</strong> {{ alert_id }}</p>
                            <p><strong>Rule ID:</strong> {{ rule_id }}</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """)

            # Color based on severity
            severity_colors = {
                "low": "#4CAF50",
                "medium": "#FF9800",
                "high": "#FF5722",
                "critical": "#F44336"
            }

            html_body = html_template.render(
                severity=alert.severity.value,
                severity_color=severity_colors.get(alert.severity.value, "#666"),
                title=alert.title,
                description=alert.description,
                triggered_at=alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                metric_value=alert.metric_value,
                threshold_value=alert.threshold_value,
                context=alert.context,
                alert_id=alert.alert_id,
                rule_id=alert.rule_id
            )

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = username
            msg['To'] = ', '.join(to_addresses)

            # Add HTML part
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

            logger.info("Email alert sent successfully",
                       channel_id=channel.channel_id,
                       alert_id=alert.alert_id,
                       recipients=len(to_addresses))
            return True

        except Exception as e:
            logger.error("Failed to send email alert",
                        channel_id=channel.channel_id,
                        alert_id=alert.alert_id,
                        error=str(e))
            return False

    async def send_slack(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send Slack notification"""
        try:
            webhook_url = channel.config.get('webhook_url')
            if not webhook_url:
                logger.error("Slack webhook URL not configured", channel_id=channel.channel_id)
                return False

            # Color based on severity
            severity_colors = {
                "low": "good",
                "medium": "warning",
                "high": "danger",
                "critical": "#FF0000"
            }

            # Create Slack payload
            payload = {
                "text": f"🚨 {alert.severity.value.upper()} Alert: {alert.title}",
                "attachments": [
                    {
                        "color": severity_colors.get(alert.severity.value, "good"),
                        "fields": [
                            {
                                "title": "Description",
                                "value": alert.description,
                                "short": False
                            },
                            {
                                "title": "Current Value",
                                "value": str(alert.metric_value),
                                "short": True
                            },
                            {
                                "title": "Threshold",
                                "value": str(alert.threshold_value),
                                "short": True
                            },
                            {
                                "title": "Triggered At",
                                "value": alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.alert_id,
                                "short": True
                            }
                        ],
                        "footer": "Plinto Alert System",
                        "ts": int(alert.triggered_at.timestamp())
                    }
                ]
            }

            # Add context fields if available
            if alert.context:
                for key, value in alert.context.items():
                    payload["attachments"][0]["fields"].append({
                        "title": key,
                        "value": str(value),
                        "short": True
                    })

            response = await self.http_client.post(webhook_url, json=payload)
            response.raise_for_status()

            logger.info("Slack alert sent successfully",
                       channel_id=channel.channel_id,
                       alert_id=alert.alert_id)
            return True

        except Exception as e:
            logger.error("Failed to send Slack alert",
                        channel_id=channel.channel_id,
                        alert_id=alert.alert_id,
                        error=str(e))
            return False

    async def send_webhook(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send webhook notification"""
        try:
            webhook_url = channel.config.get('webhook_url')
            headers = channel.config.get('headers', {})
            method = channel.config.get('method', 'POST').upper()

            if not webhook_url:
                logger.error("Webhook URL not configured", channel_id=channel.channel_id)
                return False

            # Create webhook payload
            payload = {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "title": alert.title,
                "description": alert.description,
                "metric_value": alert.metric_value,
                "threshold_value": alert.threshold_value,
                "triggered_at": alert.triggered_at.isoformat(),
                "context": alert.context
            }

            if method == 'POST':
                response = await self.http_client.post(webhook_url, json=payload, headers=headers)
            elif method == 'PUT':
                response = await self.http_client.put(webhook_url, json=payload, headers=headers)
            else:
                logger.error("Unsupported webhook method", method=method)
                return False

            response.raise_for_status()

            logger.info("Webhook alert sent successfully",
                       channel_id=channel.channel_id,
                       alert_id=alert.alert_id,
                       webhook_url=webhook_url)
            return True

        except Exception as e:
            logger.error("Failed to send webhook alert",
                        channel_id=channel.channel_id,
                        alert_id=alert.alert_id,
                        error=str(e))
            return False

    async def send_discord(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send Discord notification"""
        try:
            webhook_url = channel.config.get('webhook_url')
            if not webhook_url:
                logger.error("Discord webhook URL not configured", channel_id=channel.channel_id)
                return False

            # Color based on severity
            severity_colors = {
                "low": 0x4CAF50,
                "medium": 0xFF9800,
                "high": 0xFF5722,
                "critical": 0xF44336
            }

            # Create Discord embed
            embed = {
                "title": f"🚨 {alert.severity.value.upper()} Alert",
                "description": alert.title,
                "color": severity_colors.get(alert.severity.value, 0x666666),
                "fields": [
                    {
                        "name": "Description",
                        "value": alert.description,
                        "inline": False
                    },
                    {
                        "name": "Current Value",
                        "value": str(alert.metric_value),
                        "inline": True
                    },
                    {
                        "name": "Threshold",
                        "value": str(alert.threshold_value),
                        "inline": True
                    },
                    {
                        "name": "Alert ID",
                        "value": alert.alert_id,
                        "inline": True
                    }
                ],
                "timestamp": alert.triggered_at.isoformat(),
                "footer": {
                    "text": "Plinto Alert System"
                }
            }

            # Add context fields
            if alert.context:
                for key, value in list(alert.context.items())[:5]:  # Limit to 5 additional fields
                    embed["fields"].append({
                        "name": key,
                        "value": str(value),
                        "inline": True
                    })

            payload = {"embeds": [embed]}

            response = await self.http_client.post(webhook_url, json=payload)
            response.raise_for_status()

            logger.info("Discord alert sent successfully",
                       channel_id=channel.channel_id,
                       alert_id=alert.alert_id)
            return True

        except Exception as e:
            logger.error("Failed to send Discord alert",
                        channel_id=channel.channel_id,
                        alert_id=alert.alert_id,
                        error=str(e))
            return False

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


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
                decode_responses=True
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
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
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
                channels=[AlertChannel.EMAIL]
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
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
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
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
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
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
            )
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
                        rule_id=rule_data['rule_id'],
                        name=rule_data['name'],
                        description=rule_data['description'],
                        severity=AlertSeverity(rule_data['severity']),
                        metric_name=rule_data['metric_name'],
                        threshold_value=float(rule_data['threshold_value']),
                        comparison_operator=rule_data['comparison_operator'],
                        evaluation_window=int(rule_data['evaluation_window']),
                        trigger_count=int(rule_data.get('trigger_count', 1)),
                        cooldown_period=int(rule_data.get('cooldown_period', 300)),
                        enabled=rule_data.get('enabled', 'true').lower() == 'true',
                        channels=[AlertChannel(ch) for ch in json.loads(rule_data.get('channels', '[]'))],
                        conditions=json.loads(rule_data.get('conditions', '{}')),
                        metadata=json.loads(rule_data.get('metadata', '{}'))
                    )
                    self.alert_rules[rule_id] = rule

            # Load notification channels
            channel_keys = await self.redis_client.smembers("alert:channels")
            for channel_id in channel_keys:
                channel_data = await self.redis_client.hgetall(f"alert:channel:{channel_id}")
                if channel_data:
                    channel = NotificationChannel(
                        channel_id=channel_data['channel_id'],
                        channel_type=AlertChannel(channel_data['channel_type']),
                        name=channel_data['name'],
                        config=json.loads(channel_data['config']),
                        enabled=channel_data.get('enabled', 'true').lower() == 'true',
                        rate_limit=int(channel_data['rate_limit']) if channel_data.get('rate_limit') else None
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
                pass

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
                context=await self._get_alert_context(rule, current_value)
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
            "comparison": f"{current_value} {rule.comparison_operator} {rule.threshold_value}"
        }

        # Add rule-specific context
        if rule.metric_name == "avg_response_time":
            # Add slowest endpoints
            perf_summary = await apm_collector.get_performance_summary("all", hours=1)
            context["slowest_endpoints"] = perf_summary.get("performance", {}).get("slowest_endpoints", [])[:5]

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
                "notifications_sent": json.dumps(alert.notifications_sent)
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

                logger.info("Alert acknowledged",
                           alert_id=alert_id,
                           acknowledged_by=acknowledged_by)
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
            alert_ids = await self.redis_client.zrangebyscore("alerts:timeline", cutoff_time, "+inf")

            alerts = []
            for alert_id in alert_ids:
                alert_data = await self.redis_client.hgetall(f"alert:instance:{alert_id}")
                if alert_data:
                    alerts.append(alert_data)

            # Statistics
            total_alerts = len(alerts)
            severity_counts = Counter(alert['severity'] for alert in alerts)
            status_counts = Counter(alert['status'] for alert in alerts)
            rule_counts = Counter(alert['rule_id'] for alert in alerts)

            return {
                "time_range_hours": hours,
                "total_alerts": total_alerts,
                "severity_distribution": dict(severity_counts),
                "status_distribution": dict(status_counts),
                "top_triggered_rules": dict(rule_counts.most_common(10)),
                "active_alerts": len(self.active_alerts)
            }

        except Exception as e:
            logger.error("Failed to get alert statistics", error=str(e))
            return {"error": "Failed to retrieve statistics"}

    async def cleanup(self):
        """Cleanup resources"""
        await self.stop_monitoring()
        await self.notification_sender.close()


# Global alert manager instance
alert_manager = AlertManager()


# Helper functions
async def initialize_alerting():
    """Initialize the alerting system"""
    await alert_manager.initialize_redis()
    await alert_manager.start_monitoring()


async def trigger_manual_alert(title: str, description: str, severity: AlertSeverity,
                             context: Optional[Dict[str, Any]] = None) -> str:
    """Trigger a manual alert"""
    alert = Alert(
        alert_id=str(uuid.uuid4()),
        rule_id="manual",
        severity=severity,
        status=AlertStatus.TRIGGERED,
        title=title,
        description=description,
        metric_value=0,
        threshold_value=0,
        triggered_at=datetime.now(),
        context=context or {}
    )

    # Send notifications to all configured channels
    for channel_type in [AlertChannel.EMAIL, AlertChannel.SLACK]:
        await alert_manager._send_notification(alert, channel_type)

    await alert_manager._store_alert(alert)
    alert_manager.active_alerts[alert.alert_id] = alert

    return alert.alert_id


async def get_alert_health() -> Dict[str, Any]:
    """Get alerting system health"""
    return {
        "status": "healthy" if alert_manager.evaluation_task and not alert_manager.evaluation_task.done() else "stopped",
        "active_alerts": len(alert_manager.active_alerts),
        "configured_rules": len(alert_manager.alert_rules),
        "configured_channels": len(alert_manager.notification_channels),
        "redis_connected": alert_manager.redis_client is not None
    }