"""
Janua Internal Email API
Centralized email service for all MADFAM applications via Resend
"""

from typing import Any, Dict, List, Optional

import structlog
from app.services.resend_email_service import ResendEmailService as ResendService
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/email", tags=["email"])

# Internal API key for service-to-service communication
INTERNAL_API_KEY = settings.INTERNAL_API_KEY


# ==========================================
# Request/Response Models
# ==========================================


class EmailAttachment(BaseModel):
    filename: str
    content: str  # Base64 encoded
    content_type: str = "application/octet-stream"


class SendEmailRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    attachments: Optional[List[EmailAttachment]] = None
    tags: Optional[Dict[str, str]] = None
    source_app: str  # Required: dhanam, digifab, forj, avala, madfam-site
    source_type: Optional[str] = "notification"  # auth, billing, transactional, notification


class SendTemplateEmailRequest(BaseModel):
    to: List[EmailStr]
    template: str  # Template ID from registry
    variables: Dict[str, Any]
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = None
    source_app: str
    source_type: Optional[str] = "notification"


class EmailResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class TemplateInfo(BaseModel):
    id: str
    description: str
    required_variables: List[str]
    optional_variables: List[str]


# ==========================================
# Email Template Registry
# ==========================================

EMAIL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # Authentication templates
    "auth/welcome": {
        "description": "Welcome email for new users",
        "required": ["user_name", "app_name"],
        "optional": ["login_url", "support_email"],
        "subject": "Welcome to {app_name}!",
    },
    "auth/password-reset": {
        "description": "Password reset request",
        "required": ["reset_link", "expires_in"],
        "optional": ["user_name", "support_email"],
        "subject": "Reset your password",
    },
    "auth/email-verification": {
        "description": "Email address verification",
        "required": ["verification_link", "expires_in"],
        "optional": ["user_name"],
        "subject": "Verify your email address",
    },
    "auth/magic-link": {
        "description": "Passwordless login link",
        "required": ["magic_link", "expires_in"],
        "optional": ["user_name", "app_name"],
        "subject": "Your login link",
    },
    # Billing templates
    "billing/invoice": {
        "description": "Invoice notification",
        "required": ["invoice_number", "amount", "currency", "due_date"],
        "optional": ["items", "payment_url", "company_name"],
        "subject": "Invoice #{invoice_number}",
    },
    "billing/payment-succeeded": {
        "description": "Payment confirmation",
        "required": ["amount", "currency"],
        "optional": ["invoice_number", "receipt_url", "next_billing_date"],
        "subject": "Payment received - Thank you!",
    },
    "billing/payment-failed": {
        "description": "Payment failure notification",
        "required": ["amount", "currency", "retry_date"],
        "optional": ["update_payment_url", "support_email"],
        "subject": "Payment failed - Action required",
    },
    "billing/subscription-created": {
        "description": "New subscription confirmation",
        "required": ["plan_name", "amount", "currency", "billing_cycle"],
        "optional": ["features", "portal_url"],
        "subject": "Welcome to {plan_name}!",
    },
    "billing/subscription-cancelled": {
        "description": "Subscription cancellation confirmation",
        "required": ["plan_name", "end_date"],
        "optional": ["reactivate_url", "feedback_url"],
        "subject": "Your subscription has been cancelled",
    },
    # Transactional templates (app-specific)
    "transactional/quote-ready": {
        "description": "Quote ready notification (Digifab)",
        "required": ["quote_number", "total_amount"],
        "optional": ["valid_until", "view_url", "item_count"],
        "subject": "Your quote #{quote_number} is ready",
    },
    "transactional/order-confirmation": {
        "description": "Order confirmation (Digifab)",
        "required": ["order_number", "total_amount", "currency"],
        "optional": ["items", "shipping_address", "estimated_delivery"],
        "subject": "Order confirmed - #{order_number}",
    },
    "transactional/certificate": {
        "description": "Certificate/DC-3 notification (Avala)",
        "required": ["certificate_name", "recipient_name"],
        "optional": ["issue_date", "download_url", "folio"],
        "subject": "Your certificate is ready: {certificate_name}",
    },
    "transactional/enrollment": {
        "description": "Course enrollment notification (Avala)",
        "required": ["course_name", "student_name"],
        "optional": ["start_date", "instructor_name", "course_url"],
        "subject": "You're enrolled in {course_name}",
    },
    "transactional/budget-alert": {
        "description": "Budget threshold alert (Dhanam)",
        "required": ["budget_name", "percentage", "spent", "limit"],
        "optional": ["currency", "category", "view_url"],
        "subject": "Budget Alert: {budget_name} at {percentage}%",
    },
    # Invitation templates
    "invitation/team-invite": {
        "description": "Team invitation",
        "required": ["inviter_name", "team_name", "invite_url"],
        "optional": ["role", "expires_in", "message"],
        "subject": "{inviter_name} invited you to join {team_name}",
    },
    "invitation/creator-invite": {
        "description": "Creator platform invitation (Forj)",
        "required": ["invite_url"],
        "optional": ["role", "expires_in", "inviter_name"],
        "subject": "You're invited to join Forj",
    },
    # Onboarding templates
    "onboarding/complete": {
        "description": "Onboarding completion",
        "required": ["user_name"],
        "optional": ["app_name", "next_steps", "dashboard_url"],
        "subject": "You're all set up!",
    },
}

# ==========================================
# Security: Template filename whitelist
# Maps template IDs to their safe filenames (no user input in path construction)
# ==========================================

TEMPLATE_FILENAMES: Dict[str, str] = {
    "auth/welcome": "auth_welcome.html",
    "auth/password-reset": "auth_password-reset.html",
    "auth/email-verification": "auth_email-verification.html",
    "auth/magic-link": "auth_magic-link.html",
    "billing/invoice": "billing_invoice.html",
    "billing/payment-succeeded": "billing_payment-succeeded.html",
    "billing/payment-failed": "billing_payment-failed.html",
    "billing/subscription-created": "billing_subscription-created.html",
    "billing/subscription-cancelled": "billing_subscription-cancelled.html",
    "transactional/quote-ready": "transactional_quote-ready.html",
    "transactional/order-confirmation": "transactional_order-confirmation.html",
    "transactional/certificate": "transactional_certificate.html",
    "transactional/enrollment": "transactional_enrollment.html",
    "transactional/budget-alert": "transactional_budget-alert.html",
    "invitation/team-invite": "invitation_team-invite.html",
    "invitation/creator-invite": "invitation_creator-invite.html",
    "onboarding/complete": "onboarding_complete.html",
}


# ==========================================
# Authentication
# ==========================================


async def verify_internal_api_key(
    x_internal_api_key: str = Header(..., alias="X-Internal-API-Key"),
) -> bool:
    """Verify internal API key for service-to-service communication."""
    if not INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Email service not configured"
        )
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return True


# ==========================================
# Endpoints
# ==========================================


@router.post("/send", response_model=EmailResponse)
async def send_email(request: SendEmailRequest, _: bool = Depends(verify_internal_api_key)):
    """
    Send a custom email via Resend.
    Used for emails that don't fit a predefined template.
    """
    try:
        resend_service = ResendService()

        # Build tags for tracking (convert dict to list format expected by Resend)
        tag_list = [
            {"name": "source_app", "value": request.source_app},
            {"name": "source_type", "value": request.source_type or "notification"},
        ]
        if request.tags:
            tag_list.extend([{"name": k, "value": v} for k, v in request.tags.items()])

        # Note: ResendEmailService uses settings for from_email/from_name
        # Custom from_email, from_name, and attachments are not currently supported
        # Send to each recipient (service expects single email address)
        results = []
        for recipient in request.to:
            result = await resend_service.send_email(
                to_email=recipient,
                subject=request.subject,
                html_content=request.html or "",
                text_content=request.text,
                reply_to=request.reply_to,
                cc=request.cc,
                bcc=request.bcc,
                tags=tag_list,
            )
            results.append(result)

        # Use the last result for the response (all should succeed or fail together)
        last_result = results[-1] if results else None
        message_id = last_result.message_id if last_result else None

        logger.info(
            "Email sent",
            message_id=message_id,
            source_app=request.source_app,
            source_type=request.source_type,
            recipients=len(request.to),
        )

        return EmailResponse(success=True, message_id=message_id)

    except Exception as e:
        logger.error("Failed to send email", error=str(e), source_app=request.source_app)
        return EmailResponse(success=False, error=str(e))


@router.post("/send-template", response_model=EmailResponse)
async def send_template_email(
    request: SendTemplateEmailRequest, _: bool = Depends(verify_internal_api_key)
):
    """
    Send an email using a predefined template.
    Templates are rendered server-side with provided variables.
    """
    # Validate template exists
    template = EMAIL_TEMPLATES.get(request.template)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown template: {request.template}"
        )

    # Validate required variables
    missing = [v for v in template["required"] if v not in request.variables]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required variables: {', '.join(missing)}",
        )

    try:
        resend_service = ResendService()

        # Generate subject from template
        subject = template["subject"].format(**request.variables)

        # Render HTML from template
        html_content = await render_template(request.template, request.variables)

        # Build tags list format expected by Resend
        tag_list = [
            {"name": "source_app", "value": request.source_app},
            {"name": "source_type", "value": request.source_type or "notification"},
            {"name": "template", "value": request.template},
        ]

        # Note: ResendEmailService uses settings for from_email/from_name
        # Custom from_email, from_name, and attachments are not currently supported
        # Send to each recipient (service expects single email address)
        results = []
        for recipient in request.to:
            result = await resend_service.send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
                tags=tag_list,
            )
            results.append(result)

        # Use the last result for the response
        last_result = results[-1] if results else None
        message_id = last_result.message_id if last_result else None

        logger.info(
            "Template email sent",
            message_id=message_id,
            template=request.template,
            source_app=request.source_app,
        )

        return EmailResponse(success=True, message_id=message_id)

    except Exception as e:
        logger.error(
            "Failed to send template email",
            error=str(e),
            template=request.template,
            source_app=request.source_app,
        )
        return EmailResponse(success=False, error=str(e))


@router.get("/templates", response_model=List[TemplateInfo])
async def list_templates(_: bool = Depends(verify_internal_api_key)):
    """List all available email templates."""
    return [
        TemplateInfo(
            id=template_id,
            description=info["description"],
            required_variables=info["required"],
            optional_variables=info.get("optional", []),
        )
        for template_id, info in EMAIL_TEMPLATES.items()
    ]


@router.get("/health")
async def health_check():
    """Health check for email service."""
    resend_configured = bool(settings.RESEND_API_KEY)
    internal_api_configured = bool(INTERNAL_API_KEY)

    return {
        "status": "healthy" if (resend_configured and internal_api_configured) else "degraded",
        "resend_configured": resend_configured,
        "internal_api_configured": internal_api_configured,
        "templates_available": len(EMAIL_TEMPLATES),
    }


# ==========================================
# Template Rendering
# ==========================================


def _get_safe_template_path(template_id: str) -> str:
    """
    Get the safe template file path for a given template ID.

    Security: This function uses a strict whitelist approach to prevent path injection.
    The template filename is looked up from a predefined dictionary rather than
    being constructed from user input.

    Args:
        template_id: The template identifier (e.g., "auth/welcome")

    Returns:
        Absolute path to the template file

    Raises:
        ValueError: If template_id is not in the whitelist
    """
    from pathlib import Path

    # Security: Strict whitelist validation - template_id must exist in both registries
    if template_id not in EMAIL_TEMPLATES:
        raise ValueError(f"Unknown template: {template_id}")

    if template_id not in TEMPLATE_FILENAMES:
        raise ValueError(f"Template filename not registered: {template_id}")

    # Security: Get filename from whitelist (no user input in path construction)
    safe_filename: str = TEMPLATE_FILENAMES[template_id]

    # Define the templates base directory
    templates_base: Path = (
        Path(__file__).parent.parent.parent.parent / "templates" / "emails"
    ).resolve()

    # Security: Construct path using only whitelisted filename
    template_path: Path = templates_base / safe_filename

    # Security: Final validation - ensure resolved path is within templates directory
    # This is defense-in-depth in case the whitelist is somehow corrupted
    resolved_path: Path = template_path.resolve()
    try:
        resolved_path.relative_to(templates_base)
    except ValueError:
        # Path traversal detected - should never happen with proper whitelist
        raise ValueError(f"Invalid template path detected: {template_id}")

    return str(resolved_path)


async def render_template(template_id: str, variables: Dict[str, Any]) -> str:
    """
    Render an email template with variables.
    Templates are stored in templates/emails/ directory.

    Security: This function uses _get_safe_template_path() which implements
    strict whitelist-based path resolution to prevent path traversal attacks.
    User input (template_id) is validated against a whitelist before any
    file operations occur.
    """
    from pathlib import Path

    try:
        # Security: Get safe path using whitelist lookup (no user input in path)
        template_path_str: str = _get_safe_template_path(template_id)
        template_path: Path = Path(template_path_str)

        if template_path.exists():
            # Security: Path has been validated by _get_safe_template_path
            template_content: str = template_path.read_text(encoding="utf-8")
            # Simple variable substitution
            for key, value in variables.items():
                template_content = template_content.replace(f"{{{{{key}}}}}", str(value))
            return template_content

    except ValueError:
        # Template not in whitelist - fall through to fallback
        pass

    # Fallback: Generate simple HTML from variables
    return generate_fallback_html(template_id, variables)


def generate_fallback_html(template_id: str, variables: Dict[str, Any]) -> str:
    """Generate simple HTML when template file is not found."""
    template_info = EMAIL_TEMPLATES.get(template_id, {})
    subject = template_info.get("subject", "Notification").format(**variables)

    # Build variable list
    var_html = "".join(
        [
            f"<p><strong>{k.replace('_', ' ').title()}:</strong> {v}</p>"
            for k, v in variables.items()
            if v is not None
        ]
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
            a {{ color: #667eea; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{subject}</h1>
        </div>
        <div class="content">
            {var_html}
        </div>
        <div class="footer">
            <p>Sent via MADFAM Platform</p>
        </div>
    </body>
    </html>
    """
