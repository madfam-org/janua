"""
Email service for sending verification, password reset, and notification emails
"""

import smtplib
import secrets
import hashlib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

import structlog
import redis.asyncio as redis

from app.config import settings

logger = structlog.get_logger()


def _redact_email(email: str) -> str:
    """Redact email address for logging (shows first 2 chars and domain)."""
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


class EmailService:
    """Email service for sending transactional emails"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.template_dir = Path(__file__).parent.parent / "templates" / "email"
        self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir), autoescape=True)

    async def send_verification_email(
        self, email: str, user_name: str = None, user_id: str = None
    ) -> str:
        """Send email verification email and return verification token"""

        # Generate verification token
        verification_token = self._generate_verification_token()

        # Store token in Redis with 24-hour expiry
        if self.redis_client:
            token_key = f"email_verification:{verification_token}"
            token_data = {
                "email": email,
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "type": "email_verification",
            }
            await self.redis_client.setex(token_key, 24 * 60 * 60, str(token_data))  # 24 hours

        # Generate verification URL
        verification_url = f"{settings.BASE_URL}/auth/verify-email?token={verification_token}"

        # Prepare email content
        template_data = {
            "user_name": user_name or email.split("@")[0],
            "verification_url": verification_url,
            "base_url": settings.BASE_URL,
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        # Render email template
        subject = "Verify your Janua account"
        html_content = self._render_template("verification.html", template_data)
        text_content = self._render_template("verification.txt", template_data)

        # Send email
        success = await self._send_email(
            to_email=email, subject=subject, html_content=html_content, text_content=text_content
        )

        if success:
            logger.info("Verification email sent", email=_redact_email(email))
            return verification_token
        else:
            logger.error("Failed to send verification email", email=_redact_email(email))
            raise Exception("Failed to send verification email")

    async def verify_email_token(self, token: str) -> Dict[str, Any]:
        """Verify email verification token and return user data"""

        if not self.redis_client:
            raise Exception("Redis not available for token verification")

        token_key = f"email_verification:{token}"

        try:
            token_data = await self.redis_client.get(token_key)
            if not token_data:
                raise Exception("Invalid or expired verification token")

            # Parse token data (simplified for alpha)
            import ast

            token_info = ast.literal_eval(token_data.decode())

            # Delete token after successful verification
            await self.redis_client.delete(token_key)

            logger.info("Email verified successfully", email=_redact_email(token_info["email"]))
            return token_info

        except Exception as e:
            logger.error("Token verification failed", error_type=type(e).__name__)
            raise Exception("Invalid or expired verification token")

    async def send_password_reset_email(self, email: str, user_name: str = None) -> str:
        """Send password reset email and return reset token"""

        # Generate reset token
        reset_token = self._generate_verification_token()

        # Store token in Redis with 1-hour expiry
        if self.redis_client:
            token_key = f"password_reset:{reset_token}"
            token_data = {
                "email": email,
                "created_at": datetime.utcnow().isoformat(),
                "type": "password_reset",
            }
            await self.redis_client.setex(token_key, 60 * 60, str(token_data))  # 1 hour

        # Generate reset URL
        reset_url = f"{settings.BASE_URL}/auth/reset-password?token={reset_token}"

        # Prepare email content
        template_data = {
            "user_name": user_name or email.split("@")[0],
            "reset_url": reset_url,
            "base_url": settings.BASE_URL,
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        # Render email template
        subject = "Reset your Janua password"
        html_content = self._render_template("password_reset.html", template_data)
        text_content = self._render_template("password_reset.txt", template_data)

        # Send email
        success = await self._send_email(
            to_email=email, subject=subject, html_content=html_content, text_content=text_content
        )

        if success:
            logger.info("Password reset email sent", email=_redact_email(email))
            return reset_token
        else:
            logger.error("Failed to send password reset email", email=_redact_email(email))
            raise Exception("Failed to send password reset email")

    async def send_welcome_email(self, email: str, user_name: str = None) -> bool:
        """Send welcome email to new user"""

        template_data = {
            "user_name": user_name or email.split("@")[0],
            "dashboard_url": f"{settings.BASE_URL}/dashboard",
            "base_url": settings.BASE_URL,
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        # Render email template
        subject = "Welcome to Janua!"
        html_content = self._render_template("welcome.html", template_data)
        text_content = self._render_template("welcome.txt", template_data)

        # Send email
        success = await self._send_email(
            to_email=email, subject=subject, html_content=html_content, text_content=text_content
        )

        if success:
            logger.info("Welcome email sent", email=_redact_email(email))
        else:
            logger.error("Failed to send welcome email", email=_redact_email(email))

        return success

    def _generate_verification_token(self) -> str:
        """Generate a secure verification token"""
        # Generate 32-byte random token
        random_bytes = secrets.token_bytes(32)
        # Create deterministic hash for consistent length
        token_hash = hashlib.sha256(random_bytes).hexdigest()
        return token_hash[:64]  # 64-char hex string

    def _render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Render email template with data"""
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**data)
        except Exception as e:
            logger.error(
                "Template rendering failed", template=template_name, error_type=type(e).__name__
            )
            # Fallback to simple text
            if "verification" in template_name:
                return f"Please verify your email by clicking: {data.get('verification_url', '')}"
            elif "password_reset" in template_name:
                return f"Reset your password by clicking: {data.get('reset_url', '')}"
            elif "welcome" in template_name:
                return f"Welcome to Janua, {data.get('user_name', 'there')}!"
            return "Email content unavailable"

    async def _send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str = None
    ) -> bool:
        """Send email via SMTP or email service"""

        # For alpha launch, we'll use a simple implementation
        # In production, integrate with SendGrid, AWS SES, or similar

        try:
            # Check if email configuration is available
            if not hasattr(settings, "SMTP_HOST") or not settings.SMTP_HOST:
                # For alpha: Log email metadata instead of full details
                logger.info(
                    "EMAIL [Alpha Mode]: email sent",
                    to=_redact_email(to_email),
                    subject_length=len(subject),
                )
                logger.debug(
                    "Email content preview available (length=%d chars)",
                    len(text_content or html_content),
                )
                return True

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formataddr((settings.FROM_NAME or "Janua", settings.FROM_EMAIL))
            msg["To"] = to_email

            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                msg.attach(text_part)

            if html_content:
                html_part = MIMEText(html_content, "html", "utf-8")
                msg.attach(html_part)

            # Send via SMTP
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

                text = msg.as_string()
                server.sendmail(settings.FROM_EMAIL, [to_email], text)

            return True

        except Exception as e:
            logger.error(
                "Failed to send email", to=_redact_email(to_email), error_type=type(e).__name__
            )
            return False


# Create email service instance
def get_email_service(redis_client: Optional[redis.Redis] = None) -> EmailService:
    """Get email service instance"""
    return EmailService(redis_client)
