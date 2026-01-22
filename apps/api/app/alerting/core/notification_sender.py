"""
Notification Sender
Handles sending notifications through various channels (email, Slack, Discord, webhooks).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx
import structlog
from jinja2 import Environment, select_autoescape

from .alert_models import Alert, NotificationChannel

logger = structlog.get_logger()


class NotificationSender:
    """Handles sending notifications through various channels"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        # Create a Jinja2 environment with autoescape enabled for HTML templates
        self.jinja_env = Environment(autoescape=select_autoescape(['html', 'xml']))

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

            # HTML email template with autoescape enabled
            html_template = self.jinja_env.from_string("""
            <html>
            <head><title>Janua Alert</title></head>
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
                        "footer": "Janua Alert System",
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
                    "text": "Janua Alert System"
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
