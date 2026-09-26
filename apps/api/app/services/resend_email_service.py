"""
Resend email service for enterprise-grade email delivery
Replaces SendGrid with Resend for better developer experience and reliability
"""

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from email.headerregistry import Address
from email.utils import formataddr
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
import structlog

from app.config import settings
from app.services.email_engagement import bind_email_id, prepare_engagement
from app.services.email_i18n import build_email_environment
from app.services.email_sender import binding_for, sender_for_address
from app.services.email_tags import normalize_tags
from app.services.email_tracking import untracked_bodies
from app.services.resend_transport import send_on_account
from app.services.sender_binding import PROVIDER_SMTP
from app.services.sender_credentials import SenderCredentialError, resolve_credential

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


@dataclass
class MessageEnvelope:
    """The resolved From line, account and wire bodies of one message.

    `api_key_override` is a credential VALUE (the tenant's own provider key)
    and exists only for the transport; it is never serialized, logged or
    returned by the preview endpoint.
    """

    sender_name: str
    sender_address: str
    sender_reply_to: Optional[str]
    html: Optional[str]
    text: Optional[str]
    forced_text_only: bool = False
    api_key_override: Optional[str] = field(default=None, repr=False)
    #: Set when the resolved binding names a provider with no transport (smtp).
    unsupported_provider_tenant: Optional[str] = None

    @property
    def from_header(self) -> str:
        """The From exactly as handed to Resend (RFC 2047-encoded when non-ASCII)."""
        return formataddr((self.sender_name, self.sender_address))

    @property
    def from_display(self) -> str:
        """The same From, human-readable: `MAP · Crea Tu Mundo <hola@creatumundo.mx>`."""
        return str(Address(display_name=self.sender_name, addr_spec=self.sender_address))


async def resolve_message_envelope(
    *,
    html_content: Optional[str],
    text_content: Optional[str],
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    redirect_url: Optional[str] = None,
    org_id: Optional[str] = None,
    token_link: bool = False,
    message_id: Optional[str] = None,
    observe: bool = True,
) -> MessageEnvelope:
    """Resolve sender, provider account and wire bodies WITHOUT sending.

    Shared by `ResendEmailService.send_email` and the preview endpoint
    (app/routers/v1/email_preview.py). `observe=False` silences the operational
    log lines, so a preview never raises a "credential missing" alert.
    """
    # Phase 2: the From line follows the tenant when that tenant's domain is
    # Resend-verified, and falls back to the PLATFORM sender WHOLE — `MADFAM
    # <hola@madfam.io>`, name and address — when it is not (owner directive
    # 2026-09-07; the earlier partial downgrade put the tenant's name on
    # MADFAM's address and reached a real inbox).
    sender_name, sender_address, sender_reply_to = sender_for_address(
        from_email=from_email,
        from_name=from_name,
        redirect_url=redirect_url,
        org_id=org_id,
    )

    # WHICH ACCOUNT SENDS THIS. The From line above says who the mail is from;
    # the binding says whose provider account carries it. They are separate so
    # a vCTO client can move to their own Resend account without a code change
    # — owner directive 2026-09-06. A binding on MADFAM's account uses the
    # platform credential.
    binding = binding_for(redirect_url=redirect_url, org_id=org_id)
    api_key_override: Optional[str] = None
    if binding.provider == PROVIDER_SMTP:
        # The SMTP provider stub is a BINDING-level declaration with no
        # transport behind it yet. Sending it through Resend anyway would be a
        # silent lie about how the mail left, so this fails visibly. Recipient
        # deliberately absent from the log.
        if observe:
            logger.error(
                "email.smtp_provider_not_implemented",
                tenant=binding.tenant,
                message_id=message_id,
            )
        return MessageEnvelope(
            sender_name=sender_name,
            sender_address=sender_address,
            sender_reply_to=sender_reply_to,
            html=html_content,
            text=text_content,
            unsupported_provider_tenant=binding.tenant,
        )
    if binding.is_on_tenant_account:
        try:
            api_key_override = await resolve_credential(binding)
        except SenderCredentialError as exc:
            # The tenant's own key is missing. Fall back to the PLATFORM sender
            # on the platform account rather than dropping a sign-in link: a
            # mail from hola@madfam.io is a degraded outcome, a mail nobody
            # receives is an outage.
            if observe:
                logger.error(
                    "email.tenant_credential_unavailable_falling_back",
                    tenant=binding.tenant,
                    credential_ref=binding.credential_ref,  # a name, not a value
                    error=str(exc),
                )
            # `from_name` is deliberately NOT carried over: a fallback to the
            # platform account sends as the platform, whole (2026-09-07).
            sender_name, sender_address, sender_reply_to = sender_for_address(
                from_email=None,
                from_name=None,
                redirect_url=None,
                org_id=None,
            )
            api_key_override = None

    # Token links never pass through Resend's tracking: decided on the From
    # address that will actually be used (after any fallback).
    wire_html, wire_text, forced_text_only = untracked_bodies(
        sender_address, html_content, text_content, token_link=token_link
    )
    if forced_text_only and observe:
        logger.info(
            "email.token_link_sent_text_only",
            message_id=message_id,
            sender_domain=sender_address.rsplit("@", 1)[-1],
        )
    return MessageEnvelope(
        sender_name=sender_name,
        sender_address=sender_address,
        sender_reply_to=sender_reply_to,
        html=wire_html,
        text=wire_text,
        forced_text_only=forced_text_only,
        api_key_override=api_key_override,
    )


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
        # Shared factory: templates/email/base.html renders localized chrome
        # via t()/lang(), which must be registered on every environment
        # that loads this directory.
        self.jinja_env = build_email_environment(self.template_dir)

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
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        redirect_url: Optional[str] = None,
        org_id: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        token_link: bool = False,
        track_engagement: bool = False,
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
            reply_to: Reply-to email address (overrides the resolved default)
            cc: CC recipients
            bcc: BCC recipients
            from_email: Caller-supplied sender address. HONOURED ONLY when its
                domain is in RESEND_VERIFIED_DOMAINS; otherwise discarded and
                the host/tenant rule decides. See app/services/email_sender.py.
            from_name: Caller-supplied display name (always honoured — naming
                yourself is harmless, claiming a domain is not)
            redirect_url: Tenant signal; its host selects the tenant sender
            org_id: Tenant signal that outranks the host when the caller knows it
            attachments: File attachments to carry on the message. Each entry is
                a dict already in Resend's shape — ``{"filename": str,
                "content": <base64 str>, "content_type"?: str}`` (Resend's
                ``Attachment`` TypedDict; ``content`` may also be a list of
                ints, but Janua's EmailAttachment model carries base64 strings).
                This is what unblocks CFDI delivery (stamped XML + PDF). When
                omitted or empty the ``attachments`` key is never added to the
                Resend payload, so a message with no files is byte-identical to
                the pre-attachment path.
            token_link: The body carries a one-time or signed link (or other
                credential). On a sender domain listed in
                EMAIL_TRACKED_SENDER_DOMAINS the message is then sent
                TEXT-ONLY so Resend's click/open tracking never touches it.
                Credential-looking link parameters are also detected in the
                HTML regardless of this flag. See app/services/email_tracking.py.
            track_engagement: Ask for FIRST-PARTY open/click measurement. Honoured
                only for non-token mail whose resolved binding has a tracking host
                on the From domain; otherwise the message goes out unmodified and
                the reason is logged. See app/services/email_engagement.py.

        Returns:
            EmailDeliveryStatus object with delivery information
        """

        if not settings.EMAIL_ENABLED:
            logger.warning("Email service disabled; no message transmitted")
            return EmailDeliveryStatus(
                message_id=f"disabled-{secrets.token_hex(8)}",
                status="disabled",
                timestamp=datetime.utcnow(),
                error_message="Email service disabled",
            )

        # Generate unique message ID for tracking
        message_id = f"janua-{secrets.token_hex(12)}"

        try:
            # Development mode: console logging
            if not settings.RESEND_API_KEY or settings.ENVIRONMENT == "development":
                return await self._send_with_console(
                    to_email, subject, html_content, text_content, message_id, metadata
                )

            # Production mode: Resend API. Who the mail is FROM, which account
            # carries it, and which bodies go on the wire are resolved by
            # `resolve_message_envelope` -- the same function the preview
            # endpoint uses, so a preview is exactly what this sends.
            envelope = await resolve_message_envelope(
                html_content=html_content,
                text_content=text_content,
                from_email=from_email,
                from_name=from_name,
                redirect_url=redirect_url,
                org_id=org_id,
                token_link=token_link,
                message_id=message_id,
            )
            if envelope.unsupported_provider_tenant is not None:
                return EmailDeliveryStatus(
                    message_id=message_id,
                    status="failed",
                    timestamp=datetime.utcnow(),
                    error_message=(
                        f"binding {envelope.unsupported_provider_tenant!r} declares provider "
                        "'smtp', which has no transport implementation yet"
                    ),
                )
            sender_name, sender_address = envelope.sender_name, envelope.sender_address
            sender_reply_to = envelope.sender_reply_to
            wire_html, wire_text = envelope.html, envelope.text
            api_key_override = envelope.api_key_override

            params: Dict[str, Any] = {
                "from": formataddr((sender_name, sender_address)),
                "to": [to_email],
                "subject": subject,
            }
            if wire_html:
                params["html"] = wire_html
            # An explicit reply_to from the caller wins; otherwise the resolved
            # one is set only when it differs from From (see email_sender).
            if not reply_to and sender_reply_to and sender_reply_to != sender_address:
                reply_to = sender_reply_to

            # Add optional parameters
            if wire_text:
                params["text"] = wire_text

            if reply_to:
                params["reply_to"] = reply_to

            if cc:
                params["cc"] = cc

            if bcc:
                params["bcc"] = bcc

            # Every send is tagged with its source_app (default "janua") and,
            # when known, org_id: Resend echoes tags on every webhook event,
            # which is how events are scoped per app. Sanitized to Resend's
            # tag charset, since one illegal tag fails the whole send.
            params["tags"] = normalize_tags(tags, org_id=org_id)

            # Attachments. The entries arrive already mapped to Resend's
            # `Attachment` shape by the router (filename / base64 content /
            # optional content_type), so this is a straight pass-through. The
            # key is added ONLY when there is at least one file, so an ordinary
            # message's payload is unchanged. This is the wiring that was
            # missing: the field existed on the request model but never reached
            # `resend.Emails.send`, so callers' attachments were silently
            # dropped.
            if attachments:
                params["attachments"] = attachments

            # FIRST-PARTY engagement measurement (opt-in, never on token mail).
            # Decided on the bodies and the From that will actually go out, so a
            # text-only or fallen-back message is never instrumented.
            engagement = None
            if track_engagement:
                engagement = await prepare_engagement(
                    requested=True,
                    html=wire_html,
                    token_link=token_link,
                    binding=binding_for(redirect_url=redirect_url, org_id=org_id),
                    sender_address=sender_address,
                    tags=params["tags"],
                    message_id=message_id,
                )
                if engagement is not None:
                    params["html"] = engagement.html

            # Add custom headers for tracking
            params["headers"] = {"X-Message-ID": message_id, "X-Priority": priority.value}

            if metadata:
                params["headers"]["X-Metadata"] = str(metadata)

            # All adapters share the lock, including platform sends and service
            # construction. No request can inherit another tenant's SDK key.
            response = send_on_account(params, api_key_override or settings.RESEND_API_KEY)

            # Resend returns {"id": "..."} on success
            delivery_status = EmailDeliveryStatus(
                message_id=response["id"],
                status="sent",
                timestamp=datetime.utcnow(),
                metadata=metadata,
            )

            if engagement is not None:
                await bind_email_id(engagement.token_hash, delivery_status.message_id)

            # Track delivery if enabled
            if track_delivery:
                await self._track_delivery(delivery_status)

            logger.info(
                "Email sent successfully via Resend",
                message_id=delivery_status.message_id,
            )
            return delivery_status

        except Exception as e:
            # Handle failure
            delivery_status = EmailDeliveryStatus(
                message_id=message_id,
                status="failed",
                timestamp=datetime.utcnow(),
                error_message="Email provider send failed",
                metadata=metadata,
            )

            if track_delivery:
                await self._track_delivery(delivery_status)

            logger.error(
                "Failed to send email via Resend",
                message_id=message_id,
                error_type=type(e).__name__,
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
        logger.info("Email simulated; no message transmitted", message_id=message_id)
        return EmailDeliveryStatus(
            message_id=message_id,
            status="simulated",
            timestamp=datetime.utcnow(),
            metadata=metadata,
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
                metadata=json.loads(data.get("metadata")) if data.get("metadata") else None,
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        html_content = self._render_template("verification.html", context)
        text_content = self._render_template("verification.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Verify your Janua account",
            token_link=True,
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        html_content = self._render_template("password_reset.html", context)
        text_content = self._render_template("password_reset.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Reset your Janua password",
            token_link=True,
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        html_content = self._render_template("welcome.html", context)
        text_content = self._render_template("welcome.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Welcome to Janua!",
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        html_content = self._render_template("invitation.html", context)
        text_content = self._render_template("invitation.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject=f"{inviter_name} invited you to join {organization_name} on Janua",
            token_link=True,
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
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
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        html_content = self._render_template("data_export_ready.html", context)
        text_content = self._render_template("data_export_ready.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="Your Data Export is Ready",
            token_link=True,
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

    async def send_mfa_recovery_email(
        self,
        to_email: str,
        user_name: str,
        backup_codes: List[str],
    ) -> EmailDeliveryStatus:
        """Send MFA recovery email with backup codes"""

        context = {
            "user_name": user_name,
            "backup_codes": backup_codes,
            "base_url": settings.BASE_URL,
            "company_name": "Janua",
            "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
        }

        html_content = self._render_template("mfa_recovery.html", context)
        text_content = self._render_template("mfa_recovery.txt", context)

        return await self.send_email(
            to_email=to_email,
            subject="MFA Recovery Codes - Janua",
            token_link=True,
            html_content=html_content,
            text_content=text_content,
            priority=EmailPriority.HIGH,
            tags=[{"name": "category", "value": "mfa_recovery"}],
            metadata={"type": "mfa_recovery", "user_email": to_email},
        )

    async def check_health(self) -> Dict[str, Any]:
        """Check Resend email service health"""
        if not settings.EMAIL_ENABLED:
            return {"status": "disabled", "message": "Email service disabled"}

        if not settings.RESEND_API_KEY:
            return {"status": "not_configured", "message": "Resend API key not configured"}

        try:
            # Verify API key format (Resend keys start with 're_')
            if settings.ENVIRONMENT == "production" and not settings.RESEND_API_KEY.startswith(
                "re_"
            ):
                return {"status": "unhealthy", "message": "Invalid Resend API key format"}

            # Check Redis connection for delivery tracking
            if self.redis_client:
                await self.redis_client.ping()

            return {"status": "healthy", "message": "Email service operational"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}


# Global service instance
def get_resend_email_service(redis_client: Optional[redis.Redis] = None) -> ResendEmailService:
    """Get Resend email service instance"""
    return ResendEmailService(redis_client)


# Export singleton for backwards compatibility
resend_email_service = ResendEmailService()
