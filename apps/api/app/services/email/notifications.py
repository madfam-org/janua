"""
Email Notifications

Helper functions for sending transactional notification emails using Resend.

Notification Types:
- Invitation emails (new user invites, acceptance confirmations)
- SSO emails (configuration, login notifications)
- Payment emails (invoice failures, payment confirmations)
- Compliance emails (data export, deletion confirmations)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from .resend_service import get_resend_service

logger = logging.getLogger(__name__)

# Frontend URL for links
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.janua.dev")


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


def _redact_ip(ip_address: str) -> str:
    """Redact IP address for logging (shows first two octets only).

    Security: This function sanitizes IP addresses before logging to prevent
    clear-text logging of user location data (CWE-532).
    """
    if not ip_address:
        return "[redacted]"
    parts = ip_address.split(".")
    if len(parts) == 4:  # IPv4
        return f"{parts[0]}.{parts[1]}.*.*"
    elif ":" in ip_address:  # IPv6
        return ip_address[:ip_address.find(":", 4) + 1] + "***"
    return "[redacted]"


# ============================================================================
# Invitation Emails
# ============================================================================

async def send_invitation_email(
    invitee_email: str,
    inviter_name: str,
    organization_name: str,
    role: str,
    invitation_token: str,
    expires_days: int = 7
) -> None:
    """
    Send invitation to new user.

    Args:
        invitee_email: Email of the person being invited
        inviter_name: Name of the person sending the invitation
        organization_name: Name of the organization
        role: Role being assigned
        invitation_token: Token for accepting invitation
        expires_days: Days until invitation expires
    """
    try:
        resend = get_resend_service()

        invitation_link = f"{FRONTEND_URL}/accept-invitation?token={invitation_token}"
        expiration_date = (datetime.utcnow() + timedelta(days=expires_days)).strftime("%B %d, %Y")

        await resend.send_template_email(
            to=invitee_email,
            template="invitation",
            variables={
                "subject": f"You've been invited to join {organization_name}",
                "inviter_name": inviter_name,
                "organization_name": organization_name,
                "role": role,
                "invitation_link": invitation_link,
                "expiration_date": expiration_date,
            },
            tags={"type": "invitation", "org": organization_name}
        )

        # Log with redacted PII - email is sanitized before logging
        redacted = _redact_email(invitee_email)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "Invitation email sent: email=%s, org=%s",
            redacted,
            organization_name
        )

    except Exception as e:
        logger.error(
            "Failed to send invitation email: email=%s, error_type=%s",
            _redact_email(invitee_email),
            type(e).__name__
        )
        raise


async def send_invitation_accepted_email(
    inviter_email: str,
    invitee_name: str,
    invitee_email: str,
    organization_name: str
) -> None:
    """
    Notify inviter that invitation was accepted.

    Args:
        inviter_email: Email of the person who sent the invitation
        invitee_name: Name of person who accepted
        invitee_email: Email of person who accepted
        organization_name: Name of the organization
    """
    try:
        resend = get_resend_service()

        await resend.send_template_email(
            to=inviter_email,
            template="invitation_accepted",
            variables={
                "subject": f"{invitee_name} accepted your invitation",
                "invitee_name": invitee_name,
                "invitee_email": invitee_email,
                "organization_name": organization_name,
            },
            tags={"type": "invitation_accepted", "org": organization_name}
        )

        # Log with redacted PII - emails are sanitized before logging
        redacted_inviter = _redact_email(inviter_email)  # lgtm[py/clear-text-logging-sensitive-data]
        redacted_invitee = _redact_email(invitee_email)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "Invitation accepted email sent: inviter=%s, invitee=%s",
            redacted_inviter,
            redacted_invitee
        )

    except Exception as e:
        logger.error(
            "Failed to send invitation accepted email: error_type=%s",
            type(e).__name__
        )
        # Don't raise - this is a nice-to-have notification


# ============================================================================
# SSO Emails
# ============================================================================

async def send_sso_configured_email(
    admin_emails: List[str],
    organization_name: str,
    provider_type: str,
    provider_name: str,
    configured_by: str
) -> None:
    """
    Notify admins that SSO was configured.

    Args:
        admin_emails: List of admin emails to notify
        organization_name: Name of the organization
        provider_type: Type of SSO (SAML, OIDC)
        provider_name: Name of the SSO provider
        configured_by: Name of person who configured SSO
    """
    try:
        resend = get_resend_service()

        await resend.send_template_email(
            to=admin_emails,
            template="sso_configured",
            variables={
                "subject": f"SSO configured for {organization_name}",
                "organization_name": organization_name,
                "provider_type": provider_type,
                "provider_name": provider_name,
                "configured_by": configured_by,
                "test_link": f"{FRONTEND_URL}/auth/sso/test",
            },
            tags={"type": "sso_configured", "org": organization_name}
        )

        logger.info(
            "SSO configured email sent: org=%s, provider=%s, recipients=%d",
            organization_name,
            provider_name,
            len(admin_emails)
        )

    except Exception as e:
        logger.error(
            "Failed to send SSO configured email: error_type=%s",
            type(e).__name__
        )
        # Don't raise - this is a nice-to-have notification


async def send_sso_login_notification(
    user_email: str,
    ip_address: str,
    location: str,
    timestamp: datetime,
    device_info: Optional[str] = None
) -> None:
    """
    Send notification for SSO login (security alert).

    Args:
        user_email: User's email
        ip_address: IP address of login
        location: Geographic location
        timestamp: Time of login
        device_info: Device/browser information
    """
    try:
        resend = get_resend_service()

        formatted_time = timestamp.strftime("%B %d, %Y at %I:%M %p UTC")

        await resend.send_template_email(
            to=user_email,
            template="sso_login_notification",
            variables={
                "subject": "New SSO login to your account",
                "ip_address": ip_address,
                "location": location,
                "timestamp": formatted_time,
                "device_info": device_info or "Unknown device",
                "security_link": f"{FRONTEND_URL}/security",
            },
            tags={"type": "sso_login", "ip": ip_address}
        )

        # Log with redacted PII - email and IP are sanitized before logging
        redacted_email = _redact_email(user_email)  # lgtm[py/clear-text-logging-sensitive-data]
        redacted_ip = _redact_ip(ip_address)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "SSO login notification sent: email=%s, ip=%s",
            redacted_email,
            redacted_ip
        )

    except Exception as e:
        logger.error(
            "Failed to send SSO login notification: error_type=%s",
            type(e).__name__
        )
        # Don't raise - login should still succeed


# ============================================================================
# Payment Emails
# ============================================================================

async def send_invoice_payment_failed_email(
    billing_email: str,
    organization_name: str,
    invoice_number: str,
    amount: float,
    currency: str,
    payment_method_last4: str,
    retry_url: Optional[str] = None
) -> None:
    """
    Notify about failed invoice payment.

    Args:
        billing_email: Email to send notification to
        organization_name: Name of the organization
        invoice_number: Invoice identifier
        amount: Amount that failed to charge (in cents)
        currency: Currency code
        payment_method_last4: Last 4 digits of payment method
        retry_url: Optional URL to retry payment
    """
    try:
        resend = get_resend_service()

        formatted_amount = f"{currency.upper()} ${amount / 100:.2f}"
        retry_link = retry_url or f"{FRONTEND_URL}/billing/invoices/{invoice_number}"

        await resend.send_template_email(
            to=billing_email,
            template="invoice_payment_failed",
            variables={
                "subject": f"Payment failed for invoice {invoice_number}",
                "organization_name": organization_name,
                "invoice_number": invoice_number,
                "amount": formatted_amount,
                "currency": currency.upper(),
                "payment_method_last4": payment_method_last4,
                "retry_link": retry_link,
            },
            tags={"type": "payment_failed", "invoice": invoice_number}
        )

        # Log with redacted email - sanitized before logging
        redacted = _redact_email(billing_email)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "Payment failed email sent: email=%s, invoice=%s",
            redacted,
            invoice_number
        )

    except Exception as e:
        logger.error(
            "Failed to send payment failed email: error_type=%s",
            type(e).__name__
        )
        raise


async def send_subscription_canceled_email(
    billing_email: str,
    organization_name: str,
    plan_name: str,
    cancellation_date: datetime,
    reason: Optional[str] = None
) -> None:
    """
    Notify about subscription cancellation.

    Args:
        billing_email: Email to send notification to
        organization_name: Name of the organization
        plan_name: Name of the canceled plan
        cancellation_date: When subscription ends
        reason: Optional cancellation reason
    """
    try:
        resend = get_resend_service()

        formatted_date = cancellation_date.strftime("%B %d, %Y")

        await resend.send_template_email(
            to=billing_email,
            template="subscription_canceled",
            variables={
                "subject": f"Subscription canceled for {organization_name}",
                "organization_name": organization_name,
                "plan_name": plan_name,
                "cancellation_date": formatted_date,
                "reason": reason or "Not provided",
                "reactivate_link": f"{FRONTEND_URL}/billing",
            },
            tags={"type": "subscription_canceled", "org": organization_name}
        )

        # Log with redacted email - sanitized before logging
        redacted = _redact_email(billing_email)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "Subscription canceled email sent: email=%s, org=%s",
            redacted,
            organization_name
        )

    except Exception as e:
        logger.error(
            "Failed to send subscription canceled email: error_type=%s",
            type(e).__name__
        )
        # Don't raise - cancellation should still proceed


# ============================================================================
# Compliance Emails
# ============================================================================

async def send_data_export_ready_email(
    user_email: str,
    export_id: str,
    download_url: str,
    expires_hours: int = 24
) -> None:
    """
    Notify user that data export is ready.

    Args:
        user_email: User's email
        export_id: Export identifier
        download_url: URL to download export
        expires_hours: Hours until download expires
    """
    try:
        resend = get_resend_service()

        expiration_time = (datetime.utcnow() + timedelta(hours=expires_hours)).strftime("%B %d, %Y at %I:%M %p UTC")

        await resend.send_template_email(
            to=user_email,
            template="data_export_ready",
            variables={
                "subject": "Your data export is ready",
                "export_id": export_id,
                "download_url": download_url,
                "expiration_time": expiration_time,
            },
            tags={"type": "data_export", "export_id": export_id}
        )

        # Log with redacted email - sanitized before logging
        redacted = _redact_email(user_email)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "Data export ready email sent: email=%s, export_id=%s",
            redacted,
            export_id
        )

    except Exception as e:
        logger.error(
            "Failed to send data export ready email: error_type=%s",
            type(e).__name__
        )
        raise


async def send_account_deletion_confirmation_email(
    user_email: str,
    deletion_date: datetime,
    cancellation_url: Optional[str] = None
) -> None:
    """
    Confirm account deletion request.

    Args:
        user_email: User's email
        deletion_date: When account will be deleted
        cancellation_url: Optional URL to cancel deletion
    """
    try:
        resend = get_resend_service()

        formatted_date = deletion_date.strftime("%B %d, %Y at %I:%M %p UTC")

        await resend.send_template_email(
            to=user_email,
            template="account_deletion_confirmation",
            variables={
                "subject": "Account deletion scheduled",
                "deletion_date": formatted_date,
                "cancellation_url": cancellation_url or f"{FRONTEND_URL}/account/cancel-deletion",
            },
            tags={"type": "account_deletion"}
        )

        # Log with redacted email - sanitized before logging
        redacted = _redact_email(user_email)  # lgtm[py/clear-text-logging-sensitive-data]
        logger.info(
            "Account deletion confirmation email sent: email=%s",
            redacted
        )

    except Exception as e:
        logger.error(
            "Failed to send account deletion confirmation email: error_type=%s",
            type(e).__name__
        )
        raise
