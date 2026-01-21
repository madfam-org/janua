"""
Admin notification system for critical system events
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

import structlog
from app.config import settings
from app.services.enhanced_email_service import enhanced_email_service, EmailPriority

logger = structlog.get_logger()


class NotificationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


@dataclass
class AdminNotification:
    title: str
    message: str
    level: NotificationLevel
    category: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class AdminNotificationService:
    """Service for sending notifications to administrators"""

    def __init__(self):
        self.admin_emails = self._get_admin_emails()
        self.notification_settings = self._get_notification_settings()

    def _get_admin_emails(self) -> List[str]:
        """Get list of admin email addresses"""
        admin_emails = []

        # From environment variables
        if hasattr(settings, 'ADMIN_EMAILS') and settings.ADMIN_EMAILS:
            admin_emails.extend(settings.ADMIN_EMAILS.split(','))

        # Fallback defaults
        fallback_emails = [
            settings.SUPPORT_EMAIL or 'support@janua.dev',
            'admin@janua.dev',
            'alerts@janua.dev'
        ]

        admin_emails.extend([email for email in fallback_emails if email not in admin_emails])

        return [email.strip() for email in admin_emails if email.strip()]

    def _get_notification_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get notification settings for different categories"""
        return {
            'security': {
                'channels': [NotificationChannel.EMAIL],
                'min_level': NotificationLevel.WARNING,
                'rate_limit_minutes': 5
            },
            'system': {
                'channels': [NotificationChannel.EMAIL],
                'min_level': NotificationLevel.ERROR,
                'rate_limit_minutes': 15
            },
            'user_management': {
                'channels': [NotificationChannel.EMAIL],
                'min_level': NotificationLevel.INFO,
                'rate_limit_minutes': 60
            },
            'performance': {
                'channels': [NotificationChannel.EMAIL],
                'min_level': NotificationLevel.WARNING,
                'rate_limit_minutes': 30
            },
            'compliance': {
                'channels': [NotificationChannel.EMAIL],
                'min_level': NotificationLevel.INFO,
                'rate_limit_minutes': 0  # No rate limiting for compliance
            }
        }

    async def notify(
        self,
        notification: AdminNotification,
        force_send: bool = False
    ):
        """Send admin notification"""

        try:
            settings_key = notification.category.lower()
            category_settings = self.notification_settings.get(settings_key, {})

            # Check if notification level meets minimum threshold
            min_level = category_settings.get('min_level', NotificationLevel.INFO)
            if not force_send and self._get_level_priority(notification.level) < self._get_level_priority(min_level):
                logger.debug(f"Notification level {notification.level} below threshold {min_level}")
                return

            # Check rate limiting
            if not force_send:
                rate_limit_minutes = category_settings.get('rate_limit_minutes', 0)
                if rate_limit_minutes > 0:
                    if not await self._check_rate_limit(notification.category, rate_limit_minutes):
                        logger.debug(f"Rate limit active for category {notification.category}")
                        return

            # Send via configured channels
            channels = category_settings.get('channels', [NotificationChannel.EMAIL])
            for channel in channels:
                await self._send_via_channel(notification, channel)

            logger.info(f"Admin notification sent: {notification.title}")

        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")

    def _get_level_priority(self, level: NotificationLevel) -> int:
        """Get numeric priority for notification level"""
        priorities = {
            NotificationLevel.INFO: 1,
            NotificationLevel.WARNING: 2,
            NotificationLevel.ERROR: 3,
            NotificationLevel.CRITICAL: 4
        }
        return priorities.get(level, 1)

    async def _check_rate_limit(self, category: str, rate_limit_minutes: int) -> bool:
        """Check if notification is within rate limit"""
        # For now, implement basic in-memory rate limiting
        # In production, this should use Redis
        rate_limit_key = f"admin_notification_rate_limit:{category}"
        # Simplified implementation - would use Redis in production
        return True

    async def _send_via_channel(self, notification: AdminNotification, channel: NotificationChannel):
        """Send notification via specific channel"""

        if channel == NotificationChannel.EMAIL:
            await self._send_email_notification(notification)
        elif channel == NotificationChannel.SLACK:
            await self._send_slack_notification(notification)
        elif channel == NotificationChannel.WEBHOOK:
            await self._send_webhook_notification(notification)

    async def _send_email_notification(self, notification: AdminNotification):
        """Send email notification to admins"""

        # Determine email priority based on notification level
        email_priority = EmailPriority.NORMAL
        if notification.level == NotificationLevel.CRITICAL:
            email_priority = EmailPriority.CRITICAL
        elif notification.level == NotificationLevel.ERROR:
            email_priority = EmailPriority.HIGH
        elif notification.level == NotificationLevel.WARNING:
            email_priority = EmailPriority.NORMAL

        # Generate email content
        subject = f"[JANUA ADMIN] {notification.level.value.upper()}: {notification.title}"

        html_content = self._generate_admin_email_html(notification)
        text_content = self._generate_admin_email_text(notification)

        # Send to all admin emails
        tasks = []
        for admin_email in self.admin_emails:
            task = enhanced_email_service.send_email_with_failover(
                to_email=admin_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                priority=email_priority,
                metadata={
                    'type': 'admin_notification',
                    'category': notification.category,
                    'level': notification.level.value
                }
            )
            tasks.append(task)

        # Send all emails concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _generate_admin_email_html(self, notification: AdminNotification) -> str:
        """Generate HTML email content for admin notification"""

        # Level-specific styling
        level_styles = {
            NotificationLevel.INFO: {"color": "#0ea5e9", "bg": "#f0f9ff", "border": "#0ea5e9"},
            NotificationLevel.WARNING: {"color": "#f59e0b", "bg": "#fefbeb", "border": "#f59e0b"},
            NotificationLevel.ERROR: {"color": "#ef4444", "bg": "#fef2f2", "border": "#ef4444"},
            NotificationLevel.CRITICAL: {"color": "#dc2626", "bg": "#fef2f2", "border": "#dc2626"}
        }

        style = level_styles.get(notification.level, level_styles[NotificationLevel.INFO])

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Janua Admin Notification</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%); padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px; font-weight: 600;">
                Janua Admin Alert
            </h1>
        </div>

        <!-- Alert Level -->
        <div style="background: {style['bg']}; border-left: 4px solid {style['border']}; padding: 16px; margin: 0;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 18px;">
                    {'🔴' if notification.level == NotificationLevel.CRITICAL else
                     '⚠️' if notification.level == NotificationLevel.ERROR else
                     '🟡' if notification.level == NotificationLevel.WARNING else '🔵'}
                </span>
                <span style="color: {style['color']}; font-weight: 600; font-size: 18px; text-transform: uppercase;">
                    {notification.level.value}
                </span>
                <span style="color: #6b7280; font-size: 14px;">
                    {notification.category.title()}
                </span>
            </div>
        </div>

        <!-- Content -->
        <div style="padding: 24px;">
            <h2 style="color: #1f2937; font-size: 20px; font-weight: 600; margin: 0 0 16px 0;">
                {notification.title}
            </h2>

            <div style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 24px 0;">
                {notification.message.replace(chr(10), '<br>')}
            </div>

            {'<div style="background: #f9fafb; border-radius: 6px; padding: 16px; margin: 16px 0;"><h3 style="color: #1f2937; font-size: 16px; margin: 0 0 12px 0;">Additional Details</h3><pre style="color: #4b5563; font-size: 14px; white-space: pre-wrap; margin: 0;">' + str(notification.data) + '</pre></div>' if notification.data else ''}
        </div>

        <!-- Footer -->
        <div style="background: #f9fafb; padding: 16px; border-top: 1px solid #e5e7eb; text-align: center;">
            <p style="color: #6b7280; font-size: 14px; margin: 0;">
                <strong>Timestamp:</strong> {notification.timestamp.isoformat()} UTC<br>
                <strong>Environment:</strong> {getattr(settings, 'ENVIRONMENT', 'production')}
            </p>
        </div>
    </div>
</body>
</html>"""

        return html

    def _generate_admin_email_text(self, notification: AdminNotification) -> str:
        """Generate text email content for admin notification"""

        level_icon = {
            NotificationLevel.INFO: 'ℹ️',
            NotificationLevel.WARNING: '⚠️',
            NotificationLevel.ERROR: '❌',
            NotificationLevel.CRITICAL: '🚨'
        }.get(notification.level, 'ℹ️')

        text = f"""JANUA ADMIN NOTIFICATION

{level_icon} {notification.level.value.upper()} - {notification.category.title()}

{notification.title}

{notification.message}
"""

        if notification.data:
            text += f"\nAdditional Details:\n{notification.data}\n"

        text += f"""
Timestamp: {notification.timestamp.isoformat()} UTC
Environment: {getattr(settings, 'ENVIRONMENT', 'production')}

---
This is an automated admin notification from Janua Identity Platform.
"""

        return text

    async def _send_slack_notification(self, notification: AdminNotification):
        """Send Slack notification (placeholder implementation)"""
        # This would integrate with Slack API
        logger.info(f"Slack notification not implemented: {notification.title}")

    async def _send_webhook_notification(self, notification: AdminNotification):
        """Send webhook notification (placeholder implementation)"""
        # This would send to configured webhook URLs
        logger.info(f"Webhook notification not implemented: {notification.title}")

    # Convenience methods for common notifications
    async def notify_security_incident(
        self,
        title: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        severity: NotificationLevel = NotificationLevel.WARNING
    ):
        """Send security incident notification"""
        data = {}
        if user_id:
            data['user_id'] = user_id
        if ip_address:
            data['ip_address'] = ip_address

        notification = AdminNotification(
            title=title,
            message=description,
            level=severity,
            category='security',
            data=data if data else None
        )

        await self.notify(notification)

    async def notify_system_error(
        self,
        title: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        service: Optional[str] = None
    ):
        """Send system error notification"""
        data = {}
        if stack_trace:
            data['stack_trace'] = stack_trace
        if service:
            data['service'] = service

        notification = AdminNotification(
            title=title,
            message=error_message,
            level=NotificationLevel.ERROR,
            category='system',
            data=data if data else None
        )

        await self.notify(notification)

    async def notify_user_activity(
        self,
        title: str,
        description: str,
        user_count: Optional[int] = None,
        activity_type: Optional[str] = None
    ):
        """Send user activity notification"""
        data = {}
        if user_count is not None:
            data['user_count'] = user_count
        if activity_type:
            data['activity_type'] = activity_type

        notification = AdminNotification(
            title=title,
            message=description,
            level=NotificationLevel.INFO,
            category='user_management',
            data=data if data else None
        )

        await self.notify(notification)

    async def notify_performance_issue(
        self,
        title: str,
        description: str,
        metrics: Optional[Dict[str, Any]] = None,
        severity: NotificationLevel = NotificationLevel.WARNING
    ):
        """Send performance issue notification"""
        notification = AdminNotification(
            title=title,
            message=description,
            level=severity,
            category='performance',
            data=metrics
        )

        await self.notify(notification)


# Global service instance
admin_notifications = AdminNotificationService()