"""
Slack Notification Strategy Implementation
Concrete implementation for Slack notification delivery
"""

import json
from typing import Dict, List, Optional, Any, Tuple
import httpx

from ...domain.models.notification import NotificationRequest, AbstractNotificationStrategy
import structlog

logger = structlog.get_logger()


class SlackNotificationStrategy(AbstractNotificationStrategy):
    """Concrete strategy for Slack notifications"""

    def __init__(self, timeout: int = 30):
        self._timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    def get_channel_type(self) -> str:
        """Get supported channel type"""
        return "slack"

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate Slack channel configuration"""
        if "webhook_url" not in config:
            logger.error("Slack config missing webhook_url")
            return False

        webhook_url = config["webhook_url"]
        if not isinstance(webhook_url, str) or not webhook_url.startswith(
            "https://hooks.slack.com/"
        ):
            logger.error("Invalid Slack webhook URL format")
            return False

        return True

    async def send(self, request: NotificationRequest) -> bool:
        """Send Slack notification"""
        try:
            config = request.channel.config

            # Validate configuration
            if not await self.validate_config(config):
                self._log_error(request, "Invalid Slack configuration")
                return False

            webhook_url = config["webhook_url"]

            self._log_attempt(request, "sending Slack message")

            # Create HTTP client if needed
            if not self._http_client:
                self._http_client = httpx.AsyncClient(timeout=self._timeout)

            # Create Slack payload
            payload = await self._create_slack_payload(request, config)

            # Send to Slack
            response = await self._http_client.post(webhook_url, json=payload)
            response.raise_for_status()

            # Slack webhooks return "ok" on success
            if response.text.strip() == "ok":
                logger.info(
                    f"Slack notification sent successfully",
                    request_id=request.request_id,
                    channel_id=request.channel.channel_id,
                )
                return True
            else:
                error_msg = f"Slack webhook returned unexpected response: {response.text}"
                self._log_error(request, error_msg)
                return False

        except httpx.TimeoutException:
            error_msg = "Slack notification timed out"
            self._log_error(request, error_msg)
            return False
        except httpx.HTTPStatusError as e:
            error_msg = f"Slack API error: {e.response.status_code} - {e.response.text}"
            self._log_error(request, error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to send Slack notification: {str(e)}"
            self._log_error(request, error_msg)
            return False

    async def _create_slack_payload(
        self, request: NotificationRequest, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Slack message payload"""
        if request.template:
            # Use custom template
            return await self._create_template_payload(request)
        else:
            # Use default Slack format
            return self._create_default_payload(request, config)

    async def _create_template_payload(self, request: NotificationRequest) -> Dict[str, Any]:
        """Create payload from template"""
        template_context = request._build_template_context()

        # Assume template provides JSON format for Slack
        try:
            payload_json = request.template.render_body(template_context)
            return json.loads(payload_json)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse template as JSON, falling back to text: {e}")
            # Fall back to text message
            return {"text": request.template.render_body(template_context)}

    def _create_default_payload(
        self, request: NotificationRequest, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create default Slack payload"""
        alert = request.alert

        # Severity color mapping for Slack
        severity_colors = {
            "low": "good",  # Green
            "medium": "warning",  # Yellow
            "high": "danger",  # Red
            "critical": "#FF0000",  # Bright red
        }

        color = severity_colors.get(alert.severity.value, "good")

        # Create main attachment
        attachment = {
            "color": color,
            "title": f"🚨 {alert.severity.value.upper()} Alert: {alert.title}",
            "text": alert.description,
            "fields": self._create_slack_fields(request),
            "footer": "Janua Alert System",
            "footer_icon": "https://janua.dev/favicon.ico",  # Optional
            "ts": int(alert.triggered_at.timestamp()),
        }

        # Add action buttons if configured
        if config.get("include_actions", True):
            attachment["actions"] = self._create_action_buttons(alert)

        # Main payload
        payload = {
            "text": f"🚨 {alert.severity.value.upper()} Alert: {alert.title}",
            "attachments": [attachment],
        }

        # Add channel/username overrides if configured
        if "channel" in config:
            payload["channel"] = config["channel"]
        if "username" in config:
            payload["username"] = config["username"]
        if "icon_emoji" in config:
            payload["icon_emoji"] = config["icon_emoji"]

        return payload

    def _create_slack_fields(self, request: NotificationRequest) -> List[Dict[str, Any]]:
        """Create Slack attachment fields"""
        alert = request.alert
        fields = []

        # Core alert information
        fields.extend(
            [
                {"title": "Status", "value": alert.status.value.title(), "short": True},
                {
                    "title": "Triggered At",
                    "value": alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "short": True,
                },
            ]
        )

        # Add metrics if available
        if alert.metrics:
            fields.extend(
                [
                    {"title": "Metric", "value": alert.metrics.metric_name, "short": True},
                    {
                        "title": "Current Value",
                        "value": str(alert.metrics.current_value),
                        "short": True,
                    },
                    {
                        "title": "Threshold",
                        "value": f"{alert.metrics.comparison_operator} {alert.metrics.threshold_value}",
                        "short": True,
                    },
                ]
            )

        # Add acknowledgment info if available
        if alert.acknowledged_at and alert.acknowledged_by:
            fields.append(
                {
                    "title": "Acknowledged",
                    "value": f"By {alert.acknowledged_by} at {alert.acknowledged_at.strftime('%H:%M:%S UTC')}",
                    "short": False,
                }
            )

        # Add selected context items (limit to avoid message size issues)
        context_items = list(alert.context.items())[:3]  # Max 3 context items
        for key, value in context_items:
            if isinstance(value, (str, int, float, bool)):
                fields.append(
                    {"title": key.replace("_", " ").title(), "value": str(value), "short": True}
                )

        # Alert IDs for reference
        fields.extend(
            [
                {"title": "Alert ID", "value": f"`{alert.alert_id}`", "short": True},
                {"title": "Rule ID", "value": f"`{alert.rule_id}`", "short": True},
            ]
        )

        return fields

    def _create_action_buttons(self, alert) -> List[Dict[str, Any]]:
        """Create action buttons for Slack message"""
        actions = []

        # Acknowledge button (if not already acknowledged)
        if alert.status.value not in ["acknowledged", "resolved"]:
            actions.append(
                {
                    "type": "button",
                    "text": "Acknowledge",
                    "name": "acknowledge",
                    "value": alert.alert_id,
                    "style": "primary",
                }
            )

        # Resolve button (if not already resolved)
        if alert.status.value != "resolved":
            actions.append(
                {
                    "type": "button",
                    "text": "Resolve",
                    "name": "resolve",
                    "value": alert.alert_id,
                    "style": "danger",
                }
            )

        # View details button
        actions.append(
            {
                "type": "button",
                "text": "View Details",
                "name": "view_details",
                "value": alert.alert_id,
                "url": f"https://your-dashboard.com/alerts/{alert.alert_id}",  # Configure as needed
            }
        )

        return actions

    async def close(self) -> None:
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


class SlackConfigValidator:
    """Utility class for validating Slack configurations"""

    @staticmethod
    def validate_webhook_url(webhook_url: str) -> Tuple[bool, Optional[str]]:
        """Validate Slack webhook URL"""
        if not webhook_url:
            return False, "Webhook URL is required"

        if not isinstance(webhook_url, str):
            return False, "Webhook URL must be a string"

        if not webhook_url.startswith("https://hooks.slack.com/"):
            return False, "Invalid Slack webhook URL format"

        # Basic URL validation
        import re

        pattern = r"^https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+$"
        if not re.match(pattern, webhook_url):
            return False, "Webhook URL format is invalid"

        return True, None

    @staticmethod
    async def test_webhook(webhook_url: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
        """Test Slack webhook connectivity"""
        try:
            # Validate URL format first
            is_valid, error = SlackConfigValidator.validate_webhook_url(webhook_url)
            if not is_valid:
                return False, error

            # Test with a simple message
            test_payload = {
                "text": "Test message from Janua Alert System",
                "attachments": [
                    {
                        "color": "good",
                        "text": "This is a test to verify webhook connectivity.",
                        "footer": "Janua Alert System - Test",
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(webhook_url, json=test_payload)
                response.raise_for_status()

                if response.text.strip() == "ok":
                    return True, None
                else:
                    return False, f"Unexpected response: {response.text}"

        except httpx.TimeoutException:
            return False, "Connection timeout - check your network and webhook URL"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False, "Webhook not found - check your webhook URL"
            elif e.response.status_code == 403:
                return False, "Access forbidden - webhook may be disabled"
            else:
                return False, f"HTTP error {e.response.status_code}: {e.response.text}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"


class SlackMessageFormatter:
    """Utility class for formatting Slack messages"""

    @staticmethod
    def format_alert_summary(alert) -> str:
        """Format a brief alert summary for Slack"""
        emoji_map = {
            "low": "🟢",  # Green circle
            "medium": "🟡",  # Yellow circle
            "high": "🔴",  # Red circle
            "critical": "⚠️",  # Warning sign
        }

        emoji = emoji_map.get(alert.severity.value, "🚨")

        return f"{emoji} *{alert.severity.value.upper()}*: {alert.title}"

    @staticmethod
    def format_metrics_text(metrics) -> str:
        """Format metrics as text"""
        if not metrics:
            return "No metrics available"

        return f"*{metrics.metric_name}*: {metrics.current_value} {metrics.comparison_operator} {metrics.threshold_value}"

    @staticmethod
    def format_duration(minutes: float) -> str:
        """Format duration in human-readable format"""
        if minutes < 1:
            return "< 1 minute"
        elif minutes < 60:
            return f"{int(minutes)} minute{'s' if minutes != 1 else ''}"
        else:
            hours = minutes / 60
            return f"{hours:.1f} hour{'s' if hours != 1 else ''}"

    @staticmethod
    def truncate_text(text: str, max_length: int = 2000) -> str:
        """Truncate text to Slack message limits"""
        if len(text) <= max_length:
            return text

        return text[: max_length - 3] + "..."


class SlackThreadManager:
    """Manager for Slack message threading (for follow-up notifications)"""

    def __init__(self):
        self._thread_mapping: Dict[str, str] = {}  # alert_id -> thread_ts

    def register_thread(self, alert_id: str, thread_ts: str) -> None:
        """Register a thread timestamp for an alert"""
        self._thread_mapping[alert_id] = thread_ts

    def get_thread(self, alert_id: str) -> Optional[str]:
        """Get thread timestamp for an alert"""
        return self._thread_mapping.get(alert_id)

    def clear_thread(self, alert_id: str) -> None:
        """Clear thread mapping for resolved alert"""
        self._thread_mapping.pop(alert_id, None)

    def create_threaded_payload(
        self, base_payload: Dict[str, Any], thread_ts: str
    ) -> Dict[str, Any]:
        """Create a threaded message payload"""
        threaded_payload = base_payload.copy()
        threaded_payload["thread_ts"] = thread_ts
        return threaded_payload
