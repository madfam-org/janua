# Email service
import logging
from typing import Optional


logger = logging.getLogger(__name__)


def _redact_email(email: str) -> str:
    """Redact email address for logging (shows first 2 chars and domain)."""
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


class EmailService:
    """Email service for sending emails"""

    @classmethod
    async def send_verification_email(
        cls, email: str, token: str, user_name: Optional[str] = None
    ) -> bool:
        """Send email verification"""
        logger.info("Sending verification email to %s", _redact_email(email))
        # Placeholder - would integrate with email provider
        return True

    @classmethod
    async def send_password_reset(
        cls, email: str, token: str, user_name: Optional[str] = None
    ) -> bool:
        """Send password reset email"""
        logger.info("Sending password reset email to %s", _redact_email(email))
        # Placeholder - would integrate with email provider
        return True

    @classmethod
    async def send_magic_link(
        cls, email: str, token: str, redirect_url: Optional[str] = None
    ) -> bool:
        """Send magic link for passwordless login"""
        logger.info("Sending magic link to %s", _redact_email(email))
        # Placeholder - would integrate with email provider
        return True

    @classmethod
    async def send_welcome_email(cls, email: str, user_name: Optional[str] = None) -> bool:
        """Send welcome email to new user"""
        logger.info("Sending welcome email to %s", _redact_email(email))
        # Placeholder - would integrate with email provider
        return True

    @classmethod
    async def send_email(cls, to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
        """Send generic email"""
        logger.info("Sending email to %s with subject_length=%d", _redact_email(to), len(subject))
        # Placeholder - would integrate with email provider
        return True
