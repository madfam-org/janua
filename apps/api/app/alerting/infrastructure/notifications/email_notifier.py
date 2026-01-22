"""
Email Notification Strategy Implementation
Concrete implementation for email notification delivery
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Dict, List, Optional, Any, Tuple
from jinja2 import Environment, select_autoescape

from ...domain.models.notification import NotificationRequest, AbstractNotificationStrategy
import structlog

logger = structlog.get_logger()


class EmailNotificationStrategy(AbstractNotificationStrategy):
    """Concrete strategy for email notifications"""

    def __init__(self):
        # Create a Jinja2 environment with autoescape enabled for HTML templates
        self._jinja_env = Environment(autoescape=select_autoescape(["html", "xml"]))
        self._default_template = self._create_default_template()

    def get_channel_type(self) -> str:
        """Get supported channel type"""
        return "email"

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate email channel configuration"""
        required_keys = {"smtp_server", "username", "password", "to_addresses"}

        if not all(key in config for key in required_keys):
            missing = required_keys - set(config.keys())
            logger.error("Email config missing required keys: %s", missing)
            return False

        # Validate to_addresses is a list
        if not isinstance(config["to_addresses"], list) or not config["to_addresses"]:
            logger.error("to_addresses must be a non-empty list")
            return False

        # Validate SMTP port
        smtp_port = config.get("smtp_port", 587)
        if not isinstance(smtp_port, int) or smtp_port <= 0:
            logger.error("smtp_port must be a positive integer")
            return False

        return True

    async def send(self, request: NotificationRequest) -> bool:
        """Send email notification"""
        try:
            config = request.channel.config

            # Validate configuration
            if not await self.validate_config(config):
                self._log_error(request, "Invalid email configuration")
                return False

            # Extract configuration
            smtp_server = config["smtp_server"]
            smtp_port = config.get("smtp_port", 587)
            username = config["username"]
            password = config["password"]
            to_addresses = config["to_addresses"]
            from_name = config.get("from_name", "Janua Alert System")
            use_tls = config.get("use_tls", True)

            self._log_attempt(request, "sending email")

            # Create email message
            msg = await self._create_email_message(request, username, from_name, to_addresses)

            # Send email
            await self._send_smtp_email(msg, smtp_server, smtp_port, username, password, use_tls)

            logger.info(
                "Email notification sent successfully",
                request_id=request.request_id,
                channel_id=request.channel.channel_id,
                recipients=len(to_addresses),
            )

            return True

        except Exception as e:
            error_msg = f"Failed to send email notification: {str(e)}"
            self._log_error(request, error_msg)
            return False

    async def _create_email_message(
        self, request: NotificationRequest, username: str, from_name: str, to_addresses: List[str]
    ) -> MIMEMultipart:
        """Create email message"""
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = request.subject
        msg["From"] = formataddr((from_name, username))
        msg["To"] = ", ".join(to_addresses)

        # Add message ID for tracking
        msg["Message-ID"] = f"<{request.request_id}@janua-alerts>"

        # Add custom headers
        msg["X-Alert-ID"] = request.alert.alert_id
        msg["X-Alert-Severity"] = request.alert.severity.value
        msg["X-Alert-Rule-ID"] = request.alert.rule_id

        # Create HTML and text content
        html_content = await self._create_html_content(request)
        text_content = self._create_text_content(request)

        # Attach both versions
        text_part = MIMEText(text_content, "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")

        msg.attach(text_part)
        msg.attach(html_part)

        return msg

    async def _create_html_content(self, request: NotificationRequest) -> str:
        """Create HTML email content"""
        if request.template:
            # Use custom template
            template_context = request._build_template_context()
            return request.template.render_body(template_context)
        else:
            # Use default template
            return self._render_default_html_template(request)

    def _create_text_content(self, request: NotificationRequest) -> str:
        """Create plain text email content"""
        lines = [
            f"ALERT: {request.alert.title}",
            f"Severity: {request.alert.severity.value.upper()}",
            "",
            f"Description: {request.alert.description}",
            f"Triggered: {request.alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        # Add metrics if available
        if request.alert.metrics:
            lines.extend(
                [
                    "Metrics:",
                    f"  Metric: {request.alert.metrics.metric_name}",
                    f"  Current Value: {request.alert.metrics.current_value}",
                    f"  Threshold: {request.alert.metrics.comparison_operator} {request.alert.metrics.threshold_value}",
                    "",
                ]
            )

        # Add context if available
        if request.alert.context:
            lines.append("Additional Context:")
            for key, value in request.alert.context.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"  {key}: {value}")
            lines.append("")

        # Add alert details
        lines.extend(
            [
                "Alert Details:",
                f"  Alert ID: {request.alert.alert_id}",
                f"  Rule ID: {request.alert.rule_id}",
                f"  Status: {request.alert.status.value}",
                "",
                "--",
                "Janua Alert System",
            ]
        )

        return "\n".join(lines)

    def _render_default_html_template(self, request: NotificationRequest) -> str:
        """Render default HTML template"""
        # Severity color mapping
        severity_colors = {
            "low": "#4CAF50",  # Green
            "medium": "#FF9800",  # Orange
            "high": "#FF5722",  # Red
            "critical": "#F44336",  # Dark Red
        }

        severity_color = severity_colors.get(request.alert.severity.value, "#666")

        context = {
            "alert": request.alert,
            "severity_color": severity_color,
            "severity_name": request.alert.severity.value.upper(),
            "triggered_at_formatted": request.alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "channel_name": request.channel.name,
        }

        return self._default_template.render(**context)

    async def _send_smtp_email(
        self,
        msg: MIMEMultipart,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        use_tls: bool,
    ) -> None:
        """Send email via SMTP"""
        # Create SMTP connection
        if smtp_port == 465:  # SSL
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:  # TLS or plain
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()

        try:
            # Login and send
            server.login(username, password)
            server.send_message(msg)

        finally:
            server.quit()

    def _create_default_template(self):
        """Create default HTML email template with autoescape enabled"""
        template_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ alert.title }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: {{ severity_color }};
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .content {
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 0 0 8px 8px;
            border: 1px solid #ddd;
            border-top: none;
        }
        .alert-info {
            background-color: white;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border-left: 4px solid {{ severity_color }};
        }
        .metrics {
            background-color: #e7f3ff;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border-left: 4px solid #2196F3;
        }
        .context {
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
            border-top: 1px solid #ddd;
            padding-top: 15px;
        }
        .label {
            font-weight: bold;
            color: #555;
        }
        .value {
            margin-left: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        td {
            padding: 8px 0;
            vertical-align: top;
        }
        .key {
            font-weight: bold;
            width: 30%;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚨 {{ severity_name }} ALERT</h1>
    </div>

    <div class="content">
        <div class="alert-info">
            <h2 style="margin-top: 0; color: {{ severity_color }};">{{ alert.title }}</h2>
            <p><strong>Description:</strong> {{ alert.description }}</p>
            <p><strong>Triggered:</strong> {{ triggered_at_formatted }}</p>
            <p><strong>Status:</strong> {{ alert.status.value.title() }}</p>
        </div>

        {% if alert.metrics %}
        <div class="metrics">
            <h3 style="margin-top: 0;">📊 Metrics</h3>
            <table>
                <tr>
                    <td class="key">Metric:</td>
                    <td>{{ alert.metrics.metric_name }}</td>
                </tr>
                <tr>
                    <td class="key">Current Value:</td>
                    <td>{{ alert.metrics.current_value }}</td>
                </tr>
                <tr>
                    <td class="key">Threshold:</td>
                    <td>{{ alert.metrics.comparison_operator }} {{ alert.metrics.threshold_value }}</td>
                </tr>
                <tr>
                    <td class="key">Evaluation Window:</td>
                    <td>{{ alert.metrics.evaluation_window_seconds }} seconds</td>
                </tr>
            </table>
        </div>
        {% endif %}

        {% if alert.context %}
        <div class="context">
            <h3 style="margin-top: 0;">ℹ️ Additional Context</h3>
            <table>
                {% for key, value in alert.context.items() %}
                <tr>
                    <td class="key">{{ key.replace('_', ' ').title() }}:</td>
                    <td>{{ value }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}

        <div class="alert-info">
            <h3 style="margin-top: 0;">🔍 Alert Details</h3>
            <table>
                <tr>
                    <td class="key">Alert ID:</td>
                    <td><code>{{ alert.alert_id }}</code></td>
                </tr>
                <tr>
                    <td class="key">Rule ID:</td>
                    <td><code>{{ alert.rule_id }}</code></td>
                </tr>
                <tr>
                    <td class="key">Channel:</td>
                    <td>{{ channel_name }}</td>
                </tr>
            </table>
        </div>
    </div>

    <div class="footer">
        <p>Janua Alert System</p>
        <p>This is an automated alert notification. Please do not reply to this email.</p>
    </div>
</body>
</html>
        """

        # Use the Jinja2 environment with autoescape enabled
        return self._jinja_env.from_string(template_html)


class EmailConfigValidator:
    """Utility class for validating email configurations"""

    @staticmethod
    def validate_smtp_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate SMTP configuration"""
        required_fields = ["smtp_server", "username", "password", "to_addresses"]

        for field in required_fields:
            if field not in config:
                return False, f"Missing required field: {field}"

        # Validate email addresses
        to_addresses = config["to_addresses"]
        if not isinstance(to_addresses, list) or not to_addresses:
            return False, "to_addresses must be a non-empty list"

        for email in to_addresses:
            if not EmailConfigValidator._is_valid_email(email):
                return False, f"Invalid email address: {email}"

        # Validate port
        port = config.get("smtp_port", 587)
        if not isinstance(port, int) or port <= 0 or port > 65535:
            return False, "smtp_port must be a valid port number (1-65535)"

        return True, None

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    @staticmethod
    async def test_smtp_connection(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Test SMTP connection"""
        try:
            smtp_server = config["smtp_server"]
            smtp_port = config.get("smtp_port", 587)
            username = config["username"]
            password = config["password"]
            use_tls = config.get("use_tls", True)

            # Test connection
            if smtp_port == 465:  # SSL
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=10)
            else:  # TLS or plain
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                if use_tls:
                    server.starttls()

            try:
                server.login(username, password)
                server.quit()
                return True, None
            except smtplib.SMTPAuthenticationError:
                return False, "Authentication failed - check username and password"
            except Exception as e:
                return False, f"SMTP error: {str(e)}"

        except Exception as e:
            return False, f"Connection failed: {str(e)}"
