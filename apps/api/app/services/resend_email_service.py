"""
Resend email service for enterprise-grade email delivery
Replaces SendGrid with Resend for better developer experience and reliability
"""

import asyncio
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
import structlog
from jinja2 import Environment, FileSystemLoader

from app.config import settings

# Optional import for resend - gracefully handle if not installed
try:
    import resend

    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    resend = None

logger = structlog.get_logger()


class EmailPriority(Enum):
    """Email priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EmailDeliveryStatus:
    """Email delivery status tracking"""

    message_id: str
    status: str  # sent, delivered, failed, bounced
    timestamp: datetime
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ResendEmailService:
    """
    Enterprise email service using Resend

    Features:
    - Simple, reliable email delivery via Resend API
    - Template rendering with Jinja2
    - Delivery tracking via Redis
    - Enterprise email flows (invitations, SSO, compliance)
    - Development mode with console logging
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.template_dir = Path(__file__).parent.parent / "templates" / "email"
        self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir), autoescape=True)

        # Initialize Resend client
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        priority: EmailPriority = EmailPriority.NORMAL,
        track_delivery: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> EmailDeliveryStatus:
        """
        Send email via Resend API

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email content
            text_content: Plain text email content (optional)
            priority: Email priority level
            track_delivery: Enable delivery tracking
            metadata: Custom metadata for tracking
            tags: Email tags for categorization
            reply_to: Reply-to email address
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            EmailDeliveryStatus object with delivery information
        """

        if not settings.EMAIL_ENABLED:
            logger.warning(f"Email service disabled, would send: {subject} to {to_email}")
            return EmailDeliveryStatus(
                message_id=f"disabled-{secrets.token_hex(8)}",
                status="disabled",
                timestamp=datetime.utcnow(),
                error_message="Email service disabled",
            )

        # Generate unique message ID for tracking
        message_id = f"plinto-{secrets.token_hex(12)}"

        try:
            # Development mode: console logging
            if not settings.RESEND_API_KEY or settings.ENVIRONMENT == "development":
                return await self._send_with_console(
                    to_email, subject, html_content, text_content, message_id, metadata
                )

            # Production mode: Resend API
            params = {
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            # Add optional parameters
            if text_content:
                params["text"] = text_content

            if reply_to:
                params["reply_to"] = reply_to

            if cc:
                params["cc"] = cc

            if bcc:
                params["bcc"] = bcc

            if tags:
                params["tags"] = tags

            # Add custom headers for tracking
            params["headers"] = {"X-Message-ID": message_id, "X-Priority": priority.value}

            if metadata:
                params["headers"]["X-Metadata"] = str(metadata)

            # Send via Resend
            response = resend.Emails.send(params)

            # Resend returns {"id": "..."} on success
            delivery_status = EmailDeliveryStatus(
                message_id=response.get("id", message_id),
                status="sent",
                timestamp=datetime.utcnow(),
                metadata=metadata,
            )

            # Track delivery if enabled
            if track_delivery:
                await self._track_delivery(delivery_status)

            logger.info(
                f"Email sent successfully via Resend",
                message_id=delivery_status.message_id,
                to_email=to_email,
            )
            return delivery_status

        except Exception as e:
            # Handle failure
            delivery_status = EmailDeliveryStatus(
                message_id=message_id,
                status="failed",
                timestamp=datetime.utcnow(),
                error_message=str(e),
                metadata=metadata,
            )

            if track_delivery:
                await self._track_delivery(delivery_status)

            logger.error(
                f"Failed to send email via Resend",
                message_id=message_id,
                to_email=to_email,
                error=str(e),
            )
            return delivery_status

    async def _send_with_console(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmailDeliveryStatus:
        """Console logging for development"""
        logger.info(
            f"[CONSOLE EMAIL] To: {to_email} | Subject: {subject} | ID: {message_id}",
            html_preview=html_content[:200] + "..." if len(html_content) > 200 else html_content,
        )

        return EmailDeliveryStatus(
            message_id=message_id, status="sent", timestamp=datetime.utcnow(), metadata=metadata
        )

    async def _track_delivery(self, delivery_status: EmailDeliveryStatus):
        """Track email delivery status in Redis"""
        if not self.redis_client:
            return

        try:
            # Store delivery status
            key = f"email_tracking:{delivery_status.message_id}"
            data = {
                "status": delivery_status.status,
                "timestamp": delivery_status.timestamp.isoformat(),
                "error_message": delivery_status.error_message or "",
                "metadata": str(delivery_status.metadata) if delivery_status.metadata else "",
            }

            await self.redis_client.hset(key, mapping=data)
            await self.redis_client.expire(key, 86400 * 7)  # Keep for 7 days

            # Update delivery statistics
            stats_key = f"email_stats:{datetime.utcnow().strftime('%Y-%m-%d')}"
            await self.redis_client.hincrby(stats_key, f"total_{delivery_status.status}", 1)
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
                status=data.get("status", ""),
                timestamp=datetime.fromisoformat(
                    data.get("timestamp", datetime.utcnow().isoformat())
                ),
                error_message=data.get("error_message") if data.get("error_message") else None,
                metadata=eval(data.get("metadata")) if data.get("metadata") else None,
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
                date = datetime.utcnow().strftime("%Y-%m-%d")

            stats_key = f"email_stats:{date}"
            stats = await self.redis_client.hgetall(stats_key)

            return {k: int(v) for k, v in stats.items()}

        except Exception as e:
            logger.error(f"Failed to get email statistics: {e}")
            return {}

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render email template with context"""
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Template rendering failed for {template_name}: {e}")
            raise

    # ===== Transactional Email Methods =====

    async def send_verification_email(
        self, to_email: str, user_name: Optional[str], verification_url: str
    ) -> EmailDeliveryStatus:
        """Send email verification email"""

        context = {
            "user_name": user_name or to_email.split("@")[0],
            "verification_url": verification_url,
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("verification.html", context)
        text_content = self._render_template("verification.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Verify your Plinto account",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            tags=[{"name": "category", "value": "verification"}],
            metadata={"type": "email_verification", "user_email": to_email},
        )

    async def send_password_reset_email(
        self, to_email: str, user_name: Optional[str], reset_url: str
    ) -> EmailDeliveryStatus:
        """Send password reset email"""

        context = {
            "user_name": user_name or to_email.split("@")[0],
            "reset_url": reset_url,
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("password_reset.html", context)
        text_content = self._render_template("password_reset.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Reset your Plinto password",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            tags=[{"name": "category", "value": "password_reset"}],
            metadata={"type": "password_reset", "user_email": to_email},
        )

    async def send_welcome_email(
        self, to_email: str, user_name: Optional[str]
    ) -> EmailDeliveryStatus:
        """Send welcome email to new user"""

        context = {
            "user_name": user_name or to_email.split("@")[0],
            "dashboard_url": f"{settings.BASE_URL}/dashboard",
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("welcome.html", context)
        text_content = self._render_template("welcome.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Welcome to Plinto!",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.NORMAL,
            tags=[{"name": "category", "value": "welcome"}],
            metadata={"type": "welcome", "user_email": to_email},
        )

    # ===== Enterprise Email Methods =====

    async def send_invitation_email(
        self,
        to_email: str,
        inviter_name: str,
        organization_name: str,
        role: str,
        invitation_url: str,
        expires_at: datetime,
        teams: Optional[List[str]] = None,
    ) -> EmailDeliveryStatus:
        """Send organization invitation email"""

        context = {
            "inviter_name": inviter_name,
            "organization_name": organization_name,
            "role": role,
            "invitation_url": invitation_url,
            "expires_at": expires_at.strftime("%B %d, %Y at %I:%M %p UTC"),
            "teams": teams or [],
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("invitation.html", context)
        text_content = self._render_template("invitation.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject=f"{inviter_name} invited you to join {organization_name} on Plinto",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            tags=[
                {"name": "category", "value": "invitation"},
                {"name": "organization", "value": organization_name},
            ],
            metadata={
                "type": "invitation",
                "user_email": to_email,
                "organization": organization_name,
                "role": role,
            },
        )

    async def send_sso_configuration_email(
        self,
        to_email: str,
        admin_name: str,
        organization_name: str,
        sso_provider: str,
        configuration_url: str,
        domains: List[str],
    ) -> EmailDeliveryStatus:
        """Send SSO configuration notification email"""

        context = {
            "admin_name": admin_name,
            "organization_name": organization_name,
            "sso_provider": sso_provider.upper(),
            "configuration_url": configuration_url,
            "domains": domains,
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("sso_configuration.html", context)
        text_content = self._render_template("sso_configuration.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject=f"SSO Configuration Completed for {organization_name}",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            tags=[
                {"name": "category", "value": "sso"},
                {"name": "organization", "value": organization_name},
            ],
            metadata={
                "type": "sso_configuration",
                "user_email": to_email,
                "organization": organization_name,
                "provider": sso_provider,
            },
        )

    async def send_sso_enabled_email(
        self,
        to_email: str,
        user_name: str,
        organization_name: str,
        sso_provider: str,
        login_url: str,
    ) -> EmailDeliveryStatus:
        """Send SSO enabled notification to users"""

        context = {
            "user_name": user_name,
            "organization_name": organization_name,
            "sso_provider": sso_provider.upper(),
            "login_url": login_url,
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("sso_enabled.html", context)
        text_content = self._render_template("sso_enabled.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject=f"Single Sign-On Enabled for {organization_name}",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.NORMAL,
            tags=[
                {"name": "category", "value": "sso"},
                {"name": "organization", "value": organization_name},
            ],
            metadata={
                "type": "sso_enabled",
                "user_email": to_email,
                "organization": organization_name,
                "provider": sso_provider,
            },
        )

    async def send_compliance_alert_email(
        self,
        to_email: str,
        admin_name: str,
        organization_name: str,
        alert_type: str,
        alert_description: str,
        action_required: bool,
        action_url: Optional[str] = None,
        deadline: Optional[datetime] = None,
    ) -> EmailDeliveryStatus:
        """Send compliance alert email"""

        context = {
            "admin_name": admin_name,
            "organization_name": organization_name,
            "alert_type": alert_type,
            "alert_description": alert_description,
            "action_required": action_required,
            "action_url": action_url,
            "deadline": deadline.strftime("%B %d, %Y") if deadline else None,
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("compliance_alert.html", context)
        text_content = self._render_template("compliance_alert.txt", context)

        priority = EmailPriority.CRITICAL if action_required else EmailPriority.HIGH

        return await self.send_email(
            to_email=to_email,
            subject=f"Compliance Alert: {alert_type} - {organization_name}",
            html_content=html_content,
            text_content=text_content,
            priority=priority,
            tags=[
                {"name": "category", "value": "compliance"},
                {"name": "organization", "value": organization_name},
                {"name": "alert_type", "value": alert_type},
            ],
            metadata={
                "type": "compliance_alert",
                "user_email": to_email,
                "organization": organization_name,
                "alert_type": alert_type,
                "action_required": action_required,
            },
        )

    async def send_data_export_ready_email(
        self,
        to_email: str,
        user_name: str,
        request_type: str,
        download_url: str,
        expires_at: datetime,
    ) -> EmailDeliveryStatus:
        """Send data export ready notification"""

        context = {
            "user_name": user_name,
            "request_type": request_type,
            "download_url": download_url,
            "expires_at": expires_at.strftime("%B %d, %Y at %I:%M %p UTC"),
            "base_url": settings.BASE_URL,
            "company_name": "Plinto",
            "support_email": settings.SUPPORT_EMAIL or "support@plinto.dev",
        }

        html_content = self._render_template("data_export_ready.html", context)
        text_content = self._render_template("data_export_ready.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Your Data Export is Ready",
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            tags=[
                {"name": "category", "value": "compliance"},
                {"name": "request_type", "value": request_type},
            ],
            metadata={
                "type": "data_export_ready",
                "user_email": to_email,
                "request_type": request_type,
            },
        )


# Global service instance
def get_resend_email_service(redis_client: Optional[redis.Redis] = None) -> ResendEmailService:
    """Get Resend email service instance"""
    return ResendEmailService(redis_client)


# Export singleton for backwards compatibility
resend_email_service = ResendEmailService()
