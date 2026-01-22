"""
Resend Email Service

Modern email service for transactional emails using Resend API.

Features:
- Template-based emails with variable substitution
- HTML and text versions
- Attachment support
- Batch sending
- Error handling with retries
- Email tracking and analytics
"""

import os
import logging
from typing import Optional, List, Dict, Any
import resend
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)


def _redact_email(email: str) -> str:
    """Redact email address for logging (shows first 2 chars and domain).

    Security: This function sanitizes email addresses before logging to prevent
    clear-text logging of sensitive user data (CWE-532, CWE-117).
    """
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def _redact_emails(emails: list | str) -> str:
    """Redact list of emails for logging.

    Security: This function sanitizes email lists before logging to prevent
    clear-text logging of sensitive user data (CWE-532, CWE-117).
    """
    if isinstance(emails, str):
        return _redact_email(emails)
    return ", ".join(_redact_email(e) for e in emails[:3]) + (
        f" (+{len(emails)-3} more)" if len(emails) > 3 else ""
    )


class ResendService:
    """
    Resend email service for transactional emails.

    Provides template-based email sending with support for HTML/text versions,
    attachments, and batch operations.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        template_dir: Optional[str] = None,
    ):
        """
        Initialize Resend service.

        Args:
            api_key: Resend API key (defaults to RESEND_API_KEY env var)
            from_email: Default sender email (defaults to RESEND_FROM_EMAIL env var)
            from_name: Default sender name (defaults to RESEND_FROM_NAME env var)
            template_dir: Directory for email templates
        """
        self.api_key = api_key or os.getenv("RESEND_API_KEY")
        self.from_email = from_email or os.getenv("RESEND_FROM_EMAIL", "noreply@janua.dev")
        self.from_name = from_name or os.getenv("RESEND_FROM_NAME", "Janua")

        if not self.api_key:
            raise ValueError("Resend API key is required")

        # Initialize Resend client
        resend.api_key = self.api_key

        # Initialize template engine
        template_path = template_dir or os.path.join(
            os.path.dirname(__file__), "../../templates/emails"
        )
        self.template_env = Environment(loader=FileSystemLoader(template_path), autoescape=True)

        # Log initialization without exposing full email - extract domain only
        from_domain = self.from_email.split("@")[-1] if "@" in self.from_email else "unknown"
        logger.info("ResendService initialized with from_domain=%s", from_domain)

    def _format_from(self, from_email: Optional[str] = None) -> str:
        """Format sender email with name."""
        email = from_email or self.from_email
        return f"{self.from_name} <{email}>"

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        html: str,
        text: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a single email.

        Args:
            to: Recipient email(s)
            subject: Email subject
            html: HTML email content
            text: Plain text version (optional)
            from_email: Sender email (optional, uses default)
            reply_to: Reply-to email (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            attachments: List of attachments (optional)
            tags: Email tags for tracking (optional)

        Returns:
            Dict containing email ID and status

        Raises:
            Exception if email sending fails
        """
        try:
            # Ensure 'to' is a list
            recipients = [to] if isinstance(to, str) else to

            # Build email params
            params: Dict[str, Any] = {
                "from": self._format_from(from_email),
                "to": recipients,
                "subject": subject,
                "html": html,
            }

            if text:
                params["text"] = text

            if reply_to:
                params["reply_to"] = reply_to

            if cc:
                params["cc"] = cc

            if bcc:
                params["bcc"] = bcc

            if attachments:
                params["attachments"] = attachments

            if tags:
                params["tags"] = tags

            # Send email
            response = resend.Emails.send(params)

            # Log success with redacted recipient - sanitized before logging
            redacted = _redact_emails(recipients)  # nosec B608 - data is redacted before logging
            logger.info(
                "Email sent successfully: id=%s, to=%s, subject_length=%d",
                response.get("id"),
                redacted,
                len(subject),
            )

            return response

        except Exception as e:
            # Log error with redacted recipient - sanitized before logging
            redacted = _redact_emails(to)  # nosec B608 - data is redacted before logging
            logger.error("Failed to send email: to=%s, error_type=%s", redacted, type(e).__name__)
            raise

    def _render_template(self, template_name: str, variables: Dict[str, Any]) -> tuple[str, str]:
        """
        Render email template with variables.

        Args:
            template_name: Name of template file (without extension)
            variables: Template variables

        Returns:
            Tuple of (html, text) content

        Raises:
            TemplateNotFound if template doesn't exist
        """
        try:
            # Render HTML version
            html_template = self.template_env.get_template(f"{template_name}.html")
            html = html_template.render(**variables)

            # Try to render text version (optional)
            text = None
            try:
                text_template = self.template_env.get_template(f"{template_name}.txt")
                text = text_template.render(**variables)
            except TemplateNotFound:
                logger.debug("Text template not found for %s, using HTML only", template_name)

            return html, text

        except TemplateNotFound:
            logger.error("Template not found: %s", template_name)
            raise

    async def send_template_email(
        self,
        to: str | List[str],
        template: str,
        variables: Dict[str, Any],
        subject: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send email using a template.

        Args:
            to: Recipient email(s)
            template: Template name (without extension)
            variables: Template variables
            subject: Email subject (optional, can be in template variables)
            from_email: Sender email (optional, uses default)
            reply_to: Reply-to email (optional)
            tags: Email tags for tracking (optional)

        Returns:
            Dict containing email ID and status

        Raises:
            Exception if email sending fails
        """
        try:
            # Render template
            html, text = self._render_template(template, variables)

            # Get subject from variables or parameter
            email_subject = subject or variables.get("subject", "")
            if not email_subject:
                raise ValueError("Email subject is required")

            # Send email
            return await self.send_email(
                to=to,
                subject=email_subject,
                html=html,
                text=text,
                from_email=from_email,
                reply_to=reply_to,
                tags=tags or {"template": template},
            )

        except Exception as e:
            # Log error with redacted recipient - sanitized before logging
            redacted = _redact_emails(to)  # nosec B608 - data is redacted before logging
            logger.error(
                "Failed to send template email: template=%s, to=%s, error_type=%s",
                template,
                redacted,
                type(e).__name__,
            )
            raise

    async def send_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Send multiple emails in batch.

        Args:
            emails: List of email dicts with keys: to, subject, html, text, etc.

        Returns:
            List of responses for each email

        Raises:
            Exception if batch sending fails
        """
        try:
            results = []

            for email_data in emails:
                result = await self.send_email(**email_data)
                results.append(result)

            logger.info("Batch emails sent: count=%d", len(results))

            return results

        except Exception as e:
            logger.error("Failed to send batch emails: error_type=%s", type(e).__name__)
            raise


# Global service instance
_resend_service: Optional[ResendService] = None


def get_resend_service() -> ResendService:
    """Get or create global Resend service instance."""
    global _resend_service

    if _resend_service is None:
        _resend_service = ResendService()

    return _resend_service
