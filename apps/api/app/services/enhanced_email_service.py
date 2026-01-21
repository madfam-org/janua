"""
Enhanced email service with failover, tracking, and advanced features
"""

import secrets
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional, Dict, Any, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from enum import Enum
from dataclasses import dataclass

import structlog
import redis.asyncio as redis
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from app.config import settings

logger = structlog.get_logger()


class EmailProvider(Enum):
    SENDGRID = "sendgrid"
    SMTP = "smtp"
    AWS_SES = "ses"
    CONSOLE = "console"


class EmailPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EmailDeliveryStatus:
    message_id: str
    status: str  # sent, delivered, failed, bounced, opened, clicked
    provider: EmailProvider
    timestamp: datetime
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EmailTemplate:
    name: str
    subject: str
    html_template: str
    text_template: str
    priority: EmailPriority = EmailPriority.NORMAL
    track_opens: bool = True
    track_clicks: bool = True


class EnhancedEmailService:
    """Enhanced email service with failover, tracking, and analytics"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.template_dir = Path(__file__).parent.parent / "templates" / "email"
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True
        )

        # Email provider configuration with priority order
        self.providers = self._configure_providers()
        self.delivery_tracking = {}

    def _configure_providers(self) -> List[EmailProvider]:
        """Configure email providers in order of preference"""
        providers = []

        # Primary provider: SendGrid (if configured)
        if settings.EMAIL_PROVIDER == "sendgrid" and settings.SENDGRID_API_KEY:
            providers.append(EmailProvider.SENDGRID)

        # Secondary provider: AWS SES (if configured)
        if hasattr(settings, 'AWS_SES_REGION') and settings.AWS_SES_REGION:
            providers.append(EmailProvider.AWS_SES)

        # Fallback provider: SMTP (if configured)
        if settings.SMTP_HOST:
            providers.append(EmailProvider.SMTP)

        # Development fallback: Console logging
        providers.append(EmailProvider.CONSOLE)

        return providers

    async def send_email_with_failover(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        priority: EmailPriority = EmailPriority.NORMAL,
        track_delivery: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EmailDeliveryStatus:
        """Send email with automatic failover between providers"""

        if not settings.EMAIL_ENABLED:
            logger.warning(f"Email service disabled, would send: {subject} to {to_email}")
            return EmailDeliveryStatus(
                message_id=f"disabled-{secrets.token_hex(8)}",
                status="disabled",
                provider=EmailProvider.CONSOLE,
                timestamp=datetime.utcnow(),
                error_message="Email service disabled"
            )

        # Generate unique message ID for tracking
        message_id = f"janua-{secrets.token_hex(12)}"

        # Try each provider in order until one succeeds
        last_error = None
        for provider in self.providers:
            try:
                success = await self._send_with_provider(
                    provider=provider,
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    message_id=message_id,
                    metadata=metadata
                )

                if success:
                    delivery_status = EmailDeliveryStatus(
                        message_id=message_id,
                        status="sent",
                        provider=provider,
                        timestamp=datetime.utcnow(),
                        metadata=metadata
                    )

                    # Track delivery if enabled
                    if track_delivery:
                        await self._track_delivery(delivery_status)

                    logger.info(f"Email sent successfully via {provider.value}",
                              message_id=message_id, to_email=to_email)
                    return delivery_status

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Failed to send via {provider.value}: {e}")
                continue

        # All providers failed
        delivery_status = EmailDeliveryStatus(
            message_id=message_id,
            status="failed",
            provider=self.providers[-1] if self.providers else EmailProvider.CONSOLE,
            timestamp=datetime.utcnow(),
            error_message=f"All providers failed. Last error: {last_error}",
            metadata=metadata
        )

        if track_delivery:
            await self._track_delivery(delivery_status)

        logger.error(f"Failed to send email after trying all providers",
                    message_id=message_id, to_email=to_email, error=last_error)
        return delivery_status

    async def _send_with_provider(
        self,
        provider: EmailProvider,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send email using specific provider"""

        if provider == EmailProvider.SENDGRID:
            return await self._send_with_sendgrid(
                to_email, subject, html_content, text_content, message_id, metadata
            )
        elif provider == EmailProvider.AWS_SES:
            return await self._send_with_ses(
                to_email, subject, html_content, text_content, message_id, metadata
            )
        elif provider == EmailProvider.SMTP:
            return await self._send_with_smtp(
                to_email, subject, html_content, text_content, message_id, metadata
            )
        elif provider == EmailProvider.CONSOLE:
            return await self._send_with_console(
                to_email, subject, html_content, text_content, message_id, metadata
            )
        else:
            return False

    async def _send_with_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send email using SendGrid API"""
        try:
            sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

            from_email = Email(settings.FROM_EMAIL or settings.EMAIL_FROM_ADDRESS,
                             settings.FROM_NAME or settings.EMAIL_FROM_NAME)
            to = To(to_email)

            # Create mail object
            mail = Mail(
                from_email=from_email,
                to_emails=to,
                subject=subject,
                html_content=html_content
            )

            if text_content:
                mail.add_content(Content("text/plain", text_content))

            # Add custom headers for tracking
            mail.add_header("X-Message-ID", message_id)
            if metadata:
                mail.add_header("X-Metadata", str(metadata))

            response = sg.send(mail)
            return response.status_code in [200, 201, 202]

        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return False

    async def _send_with_ses(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send email using AWS SES (placeholder implementation)"""
        # Note: This would require boto3 and AWS SES configuration
        # For now, return False to fall back to next provider
        logger.info("AWS SES provider not yet implemented, falling back")
        return False

    async def _send_with_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send email using SMTP"""
        try:
            import aiosmtplib

            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = formataddr((
                settings.FROM_NAME or settings.EMAIL_FROM_NAME or "Janua",
                settings.FROM_EMAIL or settings.EMAIL_FROM_ADDRESS
            ))
            message["To"] = to_email
            message["Message-ID"] = f"<{message_id}@janua.dev>"

            # Add text content
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)

            # Add HTML content
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)

            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT or 587,
                start_tls=settings.SMTP_TLS if hasattr(settings, 'SMTP_TLS') else True,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
            )

            return True

        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False

    async def _send_with_console(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Console logging for development"""
        logger.info(
            f"[CONSOLE EMAIL] To: {to_email} | Subject: {subject} | ID: {message_id}",
            html_content=html_content[:200] + "..." if len(html_content) > 200 else html_content
        )
        return True

    async def _track_delivery(self, delivery_status: EmailDeliveryStatus):
        """Track email delivery status in Redis"""
        if not self.redis_client:
            return

        try:
            # Store delivery status
            key = f"email_tracking:{delivery_status.message_id}"
            data = {
                "status": delivery_status.status,
                "provider": delivery_status.provider.value,
                "timestamp": delivery_status.timestamp.isoformat(),
                "error_message": delivery_status.error_message,
                "metadata": delivery_status.metadata
            }

            await self.redis_client.hset(key, mapping=data)
            await self.redis_client.expire(key, 86400 * 7)  # Keep for 7 days

            # Update delivery statistics
            stats_key = f"email_stats:{datetime.utcnow().strftime('%Y-%m-%d')}"
            await self.redis_client.hincrby(stats_key, f"total_{delivery_status.status}", 1)
            await self.redis_client.hincrby(stats_key, f"provider_{delivery_status.provider.value}", 1)
            await self.redis_client.expire(stats_key, 86400 * 30)  # Keep for 30 days

        except Exception as e:
            logger.error(f"Failed to track delivery: {e}")

    async def get_delivery_status(self, message_id: str) -> Optional[EmailDeliveryStatus]:
        """Get delivery status for a message"""
        if not self.redis_client:
            return None

        try:
            key = f"email_tracking:{message_id}"
            data = await self.redis_client.hgetall(key)

            if not data:
                return None

            return EmailDeliveryStatus(
                message_id=message_id,
                status=data.get('status'),
                provider=EmailProvider(data.get('provider')),
                timestamp=datetime.fromisoformat(data.get('timestamp')),
                error_message=data.get('error_message'),
                metadata=eval(data.get('metadata')) if data.get('metadata') else None
            )

        except Exception as e:
            logger.error(f"Failed to get delivery status: {e}")
            return None

    async def get_email_statistics(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get email delivery statistics for a date"""
        if not self.redis_client:
            return {}

        try:
            if not date:
                date = datetime.utcnow().strftime('%Y-%m-%d')

            stats_key = f"email_stats:{date}"
            stats = await self.redis_client.hgetall(stats_key)

            return {k: int(v) for k, v in stats.items()}

        except Exception as e:
            logger.error(f"Failed to get email statistics: {e}")
            return {}

    # Template-based email methods
    async def send_mfa_recovery_email(
        self,
        to_email: str,
        user_name: Optional[str],
        recovery_code: str,
        recovery_url: str,
        request_info: Dict[str, Any]
    ) -> EmailDeliveryStatus:
        """Send MFA recovery email"""

        context = {
            'user_name': user_name,
            'recovery_code': recovery_code,
            'recovery_url': recovery_url,
            'request_time': request_info.get('timestamp', datetime.utcnow().isoformat()),
            'ip_address': request_info.get('ip_address', 'Unknown'),
            'user_agent': request_info.get('user_agent', 'Unknown'),
            'support_email': settings.SUPPORT_EMAIL or 'support@janua.dev'
        }

        html_template = self.jinja_env.get_template('mfa_recovery.html')
        text_template = self.jinja_env.get_template('mfa_recovery.txt')

        html_content = html_template.render(**context)
        text_content = text_template.render(**context)

        return await self.send_email_with_failover(
            to_email=to_email,
            subject="Account Recovery - Two-Factor Authentication",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            metadata={'type': 'mfa_recovery', 'user_email': to_email}
        )

    async def send_security_alert_email(
        self,
        to_email: str,
        user_name: Optional[str],
        alert_type: str,
        alert_description: str,
        event_details: Dict[str, Any],
        recommended_actions: Optional[List[str]] = None
    ) -> EmailDeliveryStatus:
        """Send security alert email"""

        context = {
            'user_name': user_name,
            'alert_type': alert_type,
            'alert_description': alert_description,
            'event_time': event_details.get('timestamp', datetime.utcnow().isoformat()),
            'ip_address': event_details.get('ip_address', 'Unknown'),
            'user_agent': event_details.get('user_agent', 'Unknown'),
            'location': event_details.get('location'),
            'login_success': event_details.get('login_success', False),
            'recommended_actions': recommended_actions or [],
            'was_you': alert_type in ['Suspicious Login Attempt', 'New Device Login'],
            'confirm_url': f"{settings.FRONTEND_URL}/security/confirm/{event_details.get('event_id', '')}",
            'secure_account_url': f"{settings.FRONTEND_URL}/security/alert",
            'support_email': settings.SUPPORT_EMAIL or 'support@janua.dev'
        }

        html_template = self.jinja_env.get_template('security_alert.html')
        text_template = self.jinja_env.get_template('security_alert.txt')

        html_content = html_template.render(**context)
        text_content = text_template.render(**context)

        return await self.send_email_with_failover(
            to_email=to_email,
            subject=f"Security Alert - {alert_type}",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.CRITICAL,
            metadata={'type': 'security_alert', 'alert_type': alert_type, 'user_email': to_email}
        )


# Global service instance
enhanced_email_service = EnhancedEmailService()