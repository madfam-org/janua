"""
Janua Internal Email API
Centralized email service for all MADFAM applications via Resend
"""

import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.database import AsyncSessionLocal
from app.dependencies import verify_internal_api_key
from app.routers.v1 import email_billing_notice, email_ops_alert
from app.routers.v1.email_cfdi import cfdi_portal_slots
from app.services.email_branding import CTM_BRANDING, default_formality_for
from app.services.email_i18n import (
    FORMALITY_TU,
    FORMALITY_USTED,
    normalize_formality,
    resolve_formality_for_request,
)
from app.services.email_sender import message_class_for_internal_send
from app.services.email_tags import build_tags
from app.services.email_usage import QUOTA_ERROR_TYPES
from app.services.resend_email_service import ResendEmailService as ResendService
from app.services.user_lookup import (
    AmbiguousEmailAcrossPools,
    resolve_user_by_email_across_pools,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/email", tags=["email"])

# Internal API key reference kept for health check endpoint
INTERNAL_API_KEY = settings.INTERNAL_API_KEY


# ==========================================
# Request/Response Models
# ==========================================


class EmailAttachment(BaseModel):
    filename: str
    content: str  # Base64 encoded
    content_type: str = "application/octet-stream"


def _attachments_for_resend(
    attachments: Optional[List["EmailAttachment"]],
) -> Optional[List[Dict[str, str]]]:
    """Map request EmailAttachment models to Resend's Attachment shape.

    Resend's Python SDK (resend>=2.5) expects each attachment as
    ``{"filename": str, "content": <base64 str | list[int]>, "content_type"?:
    str}``. Janua's EmailAttachment already carries base64 ``content``, so this
    is a field-name-preserving copy. Returns ``None`` for an absent/empty list
    so the service never adds an empty ``attachments`` key to the payload.
    """
    if not attachments:
        return None
    return [
        {
            "filename": a.filename,
            "content": a.content,
            "content_type": a.content_type,
        }
        for a in attachments
    ]


class SendEmailRequest(BaseModel):
    to: List[EmailStr] = Field(min_length=1)
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
    # Tenant signals for the Phase-2 sender. A caller that knows which tenant
    # the message is for can say so; the host in `redirect_url` is the same
    # signal the auth mailer reads. Neither is required, and neither can force
    # an unverified sending domain onto the wire — see app/services/email_sender.py.
    redirect_url: Optional[str] = None
    org_id: Optional[str] = None
    # Set when the body carries a one-time or signed link (sign-in, reset,
    # invitation, ...). On a sender domain with Resend tracking enabled the
    # message then goes out text-only, so the link is never rewritten through
    # Resend's redirector. Janua also detects credential-looking link
    # parameters on its own; this flag is for links it cannot recognise.
    contains_token_link: bool = False
    # Opt in to FIRST-PARTY open/click measurement (Janua's own tracking host,
    # never Resend's). Honoured only when the message is not token mail (the
    # flag above is false AND no credential-looking link is detected) and the
    # resolved sender binding has a tracking host on the From domain; otherwise
    # the message is sent unmodified and the reason is logged. The text part is
    # never modified. See app/services/email_engagement.py.
    track_engagement: bool = False


class SendTemplateEmailRequest(BaseModel):
    to: List[EmailStr] = Field(min_length=1)
    template: str  # Template ID from registry
    variables: Dict[str, Any]
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = None
    # Where replies go. A template's From is often a sending-only address (the
    # CFDI template sends from facturacion@madfam.io); a caller that knows who
    # should answer (the client's advisor) says so here.
    reply_to: Optional[EmailStr] = None
    # A blind copy of ONE recipient's message. Each address in `to` gets its own
    # message (rendered in that recipient's register), so the BCC rides on the
    # message to the FIRST address in `to` only: a BCC holder receives exactly
    # one copy, and it is exactly what that recipient received (same register,
    # same greeting). It is never attached to the other recipients' messages.
    # An address that is also in `to` (case-insensitive) is dropped, since it
    # already gets its own message, and a repeated address is kept once. An
    # empty list is the same as none. Every BCC address counts against the
    # sending Resend account's quota, like any recipient.
    bcc: Optional[List[EmailStr]] = None
    source_app: str
    source_type: Optional[str] = "notification"
    redirect_url: Optional[str] = None
    org_id: Optional[str] = None
    # The Spanish register to render in: "tu" or "usted" (strict; anything
    # else is a 422). The HIGHEST tier, as on the magic link: request > the
    # recipient's stored users.spanish_formality > the template's own voice
    # (or, for a template that declares none, the requesting product's) >
    # usted. It only changes templates that have a register variant
    # (TEMPLATE_FILENAMES_TU); for the rest the caller's copy already carries
    # its register.
    formality: Optional[Literal["tu", "usted"]] = None


class EmailResponse(BaseModel):
    success: bool
    delivery_status: Literal["accepted", "simulated", "failed"] = "failed"
    message_id: Optional[str] = None
    error: Optional[str] = None
    #: Set only when the provider refused for quota: `daily_quota_exceeded`
    #: (clears at 00:00 UTC) or `monthly_quota_exceeded`. Absent otherwise.
    error_code: Optional[str] = None


def _email_response(results: list[Any]) -> EmailResponse:
    """Provider acceptance is distinct from disabled/console simulation and delivery."""
    if not results:
        return EmailResponse(success=False, error="No recipients processed")
    if all(r.status in {"disabled", "simulated"} for r in results):
        return EmailResponse(
            success=False, delivery_status="simulated", error="No message transmitted"
        )
    failed = [r for r in results if r.status not in {"sent", "delivered"} or not r.message_id]
    if failed:
        quota = next(
            (c for c in (getattr(r, "error_code", None) for r in failed) if c in QUOTA_ERROR_TYPES),
            None,
        )
        return EmailResponse(
            success=False,
            error=f"{len(failed)} recipient(s) failed acceptance",
            error_code=quota,
        )
    return EmailResponse(
        success=True, delivery_status="accepted", message_id=results[-1].message_id
    )


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
        "token_link": True,
    },
    "auth/email-verification": {
        "description": "Email address verification",
        "required": ["verification_link", "expires_in"],
        "optional": ["user_name"],
        "subject": "Verify your email address",
        "token_link": True,
    },
    "auth/magic-link": {
        "description": "Passwordless login link",
        "required": ["magic_link", "expires_in"],
        "optional": ["user_name", "app_name"],
        "subject": "Your login link",
        "token_link": True,
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
        "optional": ["invoice_number", "receipt_url", "next_billing_date", "payment_date"],
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
    # CFDI delivery (Mexico fiscal). Client-facing, so the BODY is Spanish;
    # the message carries the stamped CFDI as attachments (XML + PDF), which is
    # why this slice wired attachments through to Resend. The sender is a
    # madfam.io FISCAL address — fiscal/vCTO comms come from madfam.io, never a
    # client domain — set as a per-template default below; a caller may still
    # override from_email, but it is honoured only on a RESEND_VERIFIED_DOMAINS
    # domain (see resend_email_service / email_sender).
    #
    # v2 (2026-09-24), after the first real send (CTM Ciclo 2) went out with a
    # literal {rfc_receptor} placeholder, an unformatted total, the tú register
    # and no MADFAM branding. Every fiscal value is now REQUIRED and pre-formatted
    # by the caller from the stamped XML it attaches, so the body always matches
    # the CFDI. The one optional value (portal_url) reaches the HTML only through
    # a derived slot (portal_bloque / portal_texto). Values are HTML-escaped
    # (escape_html), and a plain-text part rides along (text_template).
    "billing/cfdi": {
        "description": "CFDI (Mexican tax receipt) delivery — stamped XML + PDF attached",
        "required": [
            "cliente_nombre",
            "receptor_nombre",
            "rfc_receptor",
            "emisor_nombre",
            "rfc_emisor",
            "serie_folio",
            "folio_fiscal",
            "fecha_emision",
            "periodo",
            "subtotal",
            "iva",
            "total",
            "forma_pago",
            "metodo_pago",
            "verificacion_url",
        ],
        "optional": ["portal_url"],
        "subject": "Su CFDI {serie_folio} de MADFAM — {periodo}",
        # The tú variant (2026-10-14): nauta now asks each client which register
        # they want and sends it as `formality`. Without a request value or a
        # stored answer the voice below keeps v2's usted.
        "subject_tu": "Tu CFDI {serie_folio} de MADFAM — {periodo}",
        "default_formality": FORMALITY_USTED,
        "escape_html": True,
        # Per-template default sender. Applied only when the caller omits
        # from_email (see send_template_email). facturacion@madfam.io is on the
        # verified madfam.io domain, so it passes the sender gate.
        "default_from_email": "facturacion@madfam.io",
        "default_from_name": "MADFAM Facturación",
    },
    # Monthly billing notice (nauta → a vCTO client), Spanish. Every line of copy
    # arrives composed by nauta in the reader's register; the template only lays
    # it out, so it has ONE register-neutral variant. The repeating parts are
    # lists, expanded into escaped rows by email_billing_notice.py, and every
    # optional section is dropped whole when its keys are absent. No default
    # sender: the platform sender applies (app/services/email_sender.py).
    "billing/aviso-de-cobro": {
        "description": "Aviso de cobro mensual (nauta): total, desglose, cómo pagar y avance",
        "required": [
            "asunto",
            "preencabezado",
            "marca",
            "etiqueta",
            "titulo",
            "saludo",
            "introduccion",
            "total",
            "moneda",
            "total_nota",
            "periodo",
            "fecha_pago",
            "factura_cuando",
            "subtotal",
            "iva_etiqueta",
            "iva",
            "total_linea",
            "pago_titulo",
            "pago_nota",
            "factura_nota",
            "cierre",
            "firma_nombre",
            "firma_cargo",
            "pie",
            "pie_nota",
            "conceptos",
            "pago_datos",
        ],
        "optional": [
            "fecha_pago_nota",
            "cta_comprobante_etiqueta",
            "cta_comprobante_url",
            "entregado_titulo",
            "entregado_periodo",
            "viene_titulo",
            "acciones_titulo",
            "acciones_enlace_etiqueta",
            "acciones_enlace_url",
            "estado_cuenta_etiqueta",
            "estado_cuenta_url",
            "entregado_destacados",
            "entregado",
            "viene",
            "acciones",
        ],
        # Item shapes of the list variables; validated before rendering.
        "lists": email_billing_notice.LIST_ITEM_KEYS,
        "subject": "{asunto}",
        "escape_html": True,
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
        "token_link": True,
    },
    "invitation/creator-invite": {
        "description": "Creator platform invitation (Forj)",
        "required": ["invite_url"],
        "optional": ["role", "expires_in", "inviter_name"],
        "subject": "You're invited to join Forj",
        "token_link": True,
    },
    # Onboarding templates
    "onboarding/complete": {
        "description": "Onboarding completion",
        "required": ["user_name"],
        "optional": ["app_name", "next_steps", "dashboard_url"],
        "subject": "You're all set up!",
    },
    # Engagement lifecycle (Nauta). The client-facing template takes fully
    # composed Spanish lines: Nauta owns the tú/usted register system, and
    # this renderer is plain string substitution — no conditionals here.
    "transactional/agreement-accepted": {
        "description": "Service agreement accepted — operator notification (Nauta)",
        "required": ["workspace_name", "accepted_by", "accepted_at", "checksum", "cockpit_url"],
        "optional": [],
        "subject": "Agreement accepted — {workspace_name}",
    },
    "transactional/request-filed": {
        "description": "Client priority filed — operator notification (Nauta)",
        "required": [
            "workspace_name",
            "submitted_by",
            "title",
            "kind",
            "severity",
            "sla_line",
            "filed_at",
            "body_excerpt",
            "cockpit_url",
        ],
        "optional": [],
        "subject": "Priority filed — {workspace_name}: {title}",
    },
    "transactional/workspace-activated": {
        "description": "Workspace activated — client notification (Nauta, register-composed)",
        "required": [
            "heading",
            "greeting",
            "line_deposit",
            "line_next",
            "workspace_url",
            "cta_label",
            "line_support",
            "workspace_host",
        ],
        "optional": [],
        "subject": "Espacio de trabajo activo — {workspace_host}",
    },
    # MAP (Crea Tu Mundo) — payment confirmation for an integrante.
    #
    # DELIBERATELY MONEY-LIGHT. This tells a colaboradora that the period's work
    # was paid and thanks her; it carries NO amount, currency, rate, bank/CLABE,
    # beca/percentage, or clinical field. Those figures live in HCM and the CFDI
    # cockpit, never in this notice — it mirrors the MAP-side privacy boundary in
    # crea-map/src/server/notifications-pago.ts and the money-email guard
    # doctrine. `sesiones` is a non-fiscal session COUNT for enrichment only.
    #
    # SENDER: unlike billing/cfdi (a madfam.io FISCAL sender), this is a team
    # notice FROM the CTM org, so it declares NO default_from_email — it resolves
    # to CTM's own sender (Crea Tu Mundo <hola@creatumundo.mx>) via org_id, the
    # same envelope as MAP's other campana mail. See app/services/email_sender.py.
    "map/pago-confirmado": {
        "description": "MAP — aviso a una integrante de que su pago mensual quedó confirmado",
        "required": ["periodo"],
        "optional": ["sesiones"],
        "subject": "Tu pago quedó confirmado",
    },
    # Operator alert (a MADFAM service → MADFAM's operators), Spanish. Generic on
    # purpose: a probe or worker says what broke or recovered, where, and when.
    # Internal, so it addresses nobody: the template's own words are labels with
    # no tú/usted marker and it has ONE register-neutral variant (no
    # TEMPLATE_FILENAMES_TU entry, no default_formality). `detalle` is
    # multi-line plain text; email_ops_alert.py escapes it line by line for the
    # HTML. The optional action link reaches the body only through derived slots
    # and only for an https URL. No default sender: the platform sender applies
    # (app/services/email_sender.py), as for the other operator notices.
    "ops/alert": {
        "description": "Aviso operativo interno para el equipo de MADFAM (registro neutro)",
        "required": ["asunto", "titulo", "detalle", "servicio", "ocurrio"],
        "optional": ["accion_url", "accion_texto"],
        "subject": "{asunto}",
        "escape_html": True,
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
    "billing/cfdi": "billing_cfdi.html",
    "billing/aviso-de-cobro": "billing_aviso-de-cobro.html",
    "transactional/quote-ready": "transactional_quote-ready.html",
    "transactional/order-confirmation": "transactional_order-confirmation.html",
    "transactional/certificate": "transactional_certificate.html",
    "transactional/enrollment": "transactional_enrollment.html",
    "transactional/budget-alert": "transactional_budget-alert.html",
    "invitation/team-invite": "invitation_team-invite.html",
    "invitation/creator-invite": "invitation_creator-invite.html",
    "onboarding/complete": "onboarding_complete.html",
    "transactional/agreement-accepted": "transactional_agreement-accepted.html",
    "transactional/workspace-activated": "transactional_workspace-activated.html",
    "transactional/request-filed": "transactional_request-filed.html",
    "map/pago-confirmado": "map_pago-confirmado.html",
    "ops/alert": "ops_alert.html",
}

# Plain-text companions, whitelisted exactly like TEMPLATE_FILENAMES. A template
# listed here is sent multipart (HTML + text): better deliverability at strict
# consumer mailboxes (Hotmail/Outlook.com) and readable in text-only clients.
TEXT_TEMPLATE_FILENAMES: Dict[str, str] = {
    "billing/cfdi": "billing_cfdi.txt",
    "billing/aviso-de-cobro": "billing_aviso-de-cobro.txt",
    "ops/alert": "ops_alert.txt",
}

# `tú` variants, whitelisted the same way. A template listed here has copy of its
# own that addresses the reader, so it ships one file per register; the base
# entries above are the usted variant. Every other template renders the same
# file in either register (its caller composes the reader-facing copy).
# tests/unit/routers/test_email_billing_notice.py pins that both variants of a
# template use exactly the same placeholders.
TEMPLATE_FILENAMES_TU: Dict[str, str] = {
    "billing/cfdi": "billing_cfdi_tu.html",
}
TEXT_TEMPLATE_FILENAMES_TU: Dict[str, str] = {
    "billing/cfdi": "billing_cfdi_tu.txt",
}


def has_register_variants(template_id: str) -> bool:
    """Whether the register changes this template's output."""
    return template_id in TEMPLATE_FILENAMES_TU or template_id in TEXT_TEMPLATE_FILENAMES_TU


def template_voice(
    template_id: str, redirect_url: Optional[str] = None, org_id: Optional[str] = None
) -> str:
    """The product tier of the register precedence for one template send.

    A template that declares `default_formality` speaks in that voice: billing/cfdi
    is MADFAM's fiscal mail, so a CTM-hosted request must not turn it into CTM's
    `tú`. Any other template takes the requesting product's voice, exactly as the
    magic link does (`email_branding.default_formality_for`).
    """
    declared = normalize_formality(EMAIL_TEMPLATES.get(template_id, {}).get("default_formality"))
    return declared or default_formality_for(redirect_url=redirect_url, org_id=org_id)


def resolve_template_formality(
    template_id: str,
    requested: Optional[str] = None,
    stored: Optional[str] = None,
    redirect_url: Optional[str] = None,
    org_id: Optional[str] = None,
) -> str:
    """request > the reader's stored register > the template's/product's voice > usted."""
    reader = SimpleNamespace(spanish_formality=stored) if stored else None
    return resolve_formality_for_request(
        requested,
        user=reader,
        client_default=template_voice(template_id, redirect_url=redirect_url, org_id=org_id),
    )


async def _stored_formality_for(email: str, org_id: Optional[str]) -> Optional[str]:
    """The recipient's stored `users.spanish_formality`, or None.

    The person tier for template sends. Never blocks a send: no such user, an
    address shared by people in several identity pools, or a database error all
    answer None and the next tier decides. `org_id` names the preferred pool.
    """
    try:
        preferred = UUID(str(org_id)) if org_id else None
    except (TypeError, ValueError):
        preferred = None
    try:
        async with AsyncSessionLocal() as db:
            user = await resolve_user_by_email_across_pools(
                db, email, preferred_tenant_id=preferred, active_only=True
            )
            if user is None and email != email.lower():
                user = await resolve_user_by_email_across_pools(
                    db, email.lower(), preferred_tenant_id=preferred, active_only=True
                )
    except AmbiguousEmailAcrossPools:
        return None
    except Exception as exc:  # the register is cosmetic; the send must go on
        logger.warning("Stored register lookup failed", error_type=type(exc).__name__)
        return None
    return normalize_formality(getattr(user, "spanish_formality", None)) if user else None


def _first_message_bcc(to: List[str], bcc: Optional[List[str]]) -> Optional[List[str]]:
    """The BCC list for the first recipient's template message, or None.

    Drops every address that is also a `to` recipient (it gets its own message)
    and every repeat, comparing case-insensitively, so each BCC holder receives
    exactly one copy. None when nothing is left, so the provider payload never
    carries an empty `bcc`.
    """
    if not bcc:
        return None
    seen = {address.lower() for address in to}
    kept: List[str] = []
    for address in bcc:
        key = address.lower()
        if key not in seen:
            seen.add(key)
            kept.append(address)
    return kept or None


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

        # Resend tags scope every webhook event back to the sending app and
        # tenant (app/services/email_tags.py). Reserved names cannot be
        # overridden by the caller's own `tags`.
        tag_list = build_tags(
            source_app=request.source_app,
            source_type=request.source_type or "notification",
            org_id=request.org_id,
            extra=request.tags,
        )

        # from_email / from_name are now passed through, but they are NOT
        # trusted: `sender_for_address` honours an explicit address only when
        # its domain is in RESEND_VERIFIED_DOMAINS, and otherwise falls back to
        # the tenant/host rule. Attachments are now forwarded to Resend (mapped
        # to its Attachment shape) — this unblocks CFDI XML+PDF delivery.
        resend_attachments = _attachments_for_resend(request.attachments)
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
                from_email=request.from_email,
                from_name=request.from_name,
                redirect_url=request.redirect_url,
                org_id=request.org_id,
                attachments=resend_attachments,
                token_link=request.contains_token_link,
                track_engagement=request.track_engagement,
                # R101: token mail leaves from the system sender with a
                # Reply-To when no tenant's branded sender applies.
                message_class=message_class_for_internal_send(request.contains_token_link),
            )
            results.append(result)

        return _email_response(results)

    except Exception as e:
        logger.error(
            "Failed to send email", error_type=type(e).__name__, source_app=request.source_app
        )
        return EmailResponse(success=False, error="Email provider send failed")


@router.post("/send-template", response_model=EmailResponse)
async def send_template_email(
    request: SendTemplateEmailRequest, _: bool = Depends(verify_internal_api_key)
):
    """
    Send an email using a predefined template.
    Templates are rendered server-side with provided variables.
    """
    # The register before the person tier: request > the template's/product's
    # voice. The recipient's stored choice is consulted per recipient below.
    base_formality = resolve_template_formality(
        request.template,
        request.formality,
        redirect_url=request.redirect_url,
        org_id=request.org_id,
    )
    # Validate and render with the same helper the preview endpoint uses.
    try:
        rendered = await render_registered_template(
            request.template, request.variables, base_formality
        )
    except UnknownTemplateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown template: {request.template}"
        )
    except UnresolvedTemplateVariablesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template placeholders without a value: {', '.join(exc.missing)}",
        )
    except InvalidTemplateVariablesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template variables: {', '.join(exc.missing)}",
        )
    except MissingTemplateVariablesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required variables: {', '.join(exc.missing)}",
        )
    except Exception as e:  # rendering failure: same answer as a failed send
        logger.error(
            "Failed to render template email",
            error_type=type(e).__name__,
            template=request.template,
            source_app=request.source_app,
        )
        return EmailResponse(success=False, error="Email provider send failed")

    # The person tier, per recipient — only where the register changes the
    # output and the request did not name one (the request outranks the reader).
    # Every variant is rendered BEFORE the first send, so a failure here cannot
    # leave some recipients mailed and others not.
    per_recipient: Dict[str, RenderedTemplate] = {}
    try:
        renders: Dict[str, RenderedTemplate] = {rendered.formality: rendered}
        for recipient in request.to:
            message = rendered
            if request.formality is None and has_register_variants(request.template):
                stored = await _stored_formality_for(recipient, request.org_id)
                if stored:
                    register = resolve_template_formality(
                        request.template,
                        None,
                        stored,
                        redirect_url=request.redirect_url,
                        org_id=request.org_id,
                    )
                    if register not in renders:
                        renders[register] = await render_registered_template(
                            request.template, request.variables, register
                        )
                    message = renders[register]
            per_recipient[recipient] = message
    except Exception as e:
        logger.error(
            "Failed to render template email",
            error_type=type(e).__name__,
            template=request.template,
            source_app=request.source_app,
        )
        return EmailResponse(success=False, error="Email provider send failed")

    try:
        resend_service = ResendService()

        # Resend tags (sanitized: "auth/magic-link" is not a legal tag value).
        tag_list = build_tags(
            source_app=request.source_app,
            source_type=request.source_type or "notification",
            org_id=request.org_id,
            template=request.template,
        )

        # from_email / from_name are passed through under the verified-domain
        # gate (see /send above). A template may declare a default sender
        # (e.g. the CFDI template defaults to the madfam.io fiscal address);
        # the caller's explicit from_email always takes precedence when given.
        from_email = request.from_email or rendered.default_from_email
        from_name = request.from_name or rendered.default_from_name

        # Attachments are now forwarded for template sends too — this is what
        # lets a CFDI-delivery template carry its stamped XML + PDF.
        resend_attachments = _attachments_for_resend(request.attachments)

        # The blind copy rides on the first recipient's message only
        # (SendTemplateEmailRequest.bcc), so it is one copy of one real message.
        first_message_bcc = _first_message_bcc(request.to, request.bcc)

        # Send to each recipient (service expects single email address)
        results = []
        for index, recipient in enumerate(request.to):
            message = per_recipient[recipient]
            result = await resend_service.send_email(
                to_email=recipient,
                subject=message.subject,
                html_content=message.html,
                text_content=message.text,
                tags=tag_list,
                reply_to=request.reply_to,
                bcc=first_message_bcc if index == 0 else None,
                from_email=from_email,
                from_name=from_name,
                redirect_url=request.redirect_url,
                org_id=request.org_id,
                attachments=resend_attachments,
                token_link=rendered.token_link,
                message_class=message_class_for_internal_send(rendered.token_link),
            )
            results.append(result)

        return _email_response(results)

    except Exception as e:
        logger.error(
            "Failed to send template email",
            error_type=type(e).__name__,
            template=request.template,
            source_app=request.source_app,
        )
        return EmailResponse(success=False, error="Email provider send failed")


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


def _get_safe_template_path(template_id: str, formality: Optional[str] = None) -> str:
    """
    Get the safe template file path for a given template ID.

    Security: This function uses a strict whitelist approach to prevent path injection.
    The template filename is looked up from a predefined dictionary rather than
    being constructed from user input.

    Args:
        template_id: The template identifier (e.g., "auth/welcome")
        formality: "tu" selects the template's tú variant when it has one
            (TEMPLATE_FILENAMES_TU); anything else, the base (usted) file.

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
    if formality == FORMALITY_TU and template_id in TEMPLATE_FILENAMES_TU:
        safe_filename = TEMPLATE_FILENAMES_TU[template_id]

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


#: The Crea frame slots map/pago-confirmado fills from CTM_BRANDING: the same
#: header ground/text, logos and platform credit base.html draws for the CTM
#: tenant. `frame_owner` is a Jinja-frame switch with no slot here, so it is
#: left out.
_CTM_FRAME_SLOTS: Dict[str, str] = {
    key: CTM_BRANDING[key]
    for key in (
        "header_name",
        "header_bg",
        "header_fg",
        "header_logo_url",
        "footer_logo_url",
        "platform_name",
        "platform_url",
    )
}


def _sesiones_detalle(sesiones: Any) -> str:
    """The Spanish session-count parenthetical for map/pago-confirmado, or "".

    The renderer does naive ``{{key}}`` substitution and CANNOT do Jinja
    conditionals or singular/plural, so the whole optional phrase is composed
    here and exposed to the template as a single always-present ``{{sesiones_detalle}}``
    slot. This is what keeps the count OPTIONAL without ever leaking a literal
    ``{{sesiones}}`` into a family-facing message when the caller omits it.

    Deliberately money-light: this renders only a non-fiscal session COUNT — no
    amount, rate, or total (those live in HCM / the CFDI cockpit, never here).

        absent / blank / <= 0  -> ""              (nothing shown)
        1                      -> " (1 sesión)"
        n > 1                  -> " (n sesiones)"

    A non-integer value is ignored rather than rendered raw, so a malformed
    caller can never inject arbitrary text into the body through this slot.
    """
    if sesiones is None:
        return ""
    try:
        count = int(sesiones)
    except (TypeError, ValueError):
        return ""
    if count <= 0:
        return ""
    palabra = "sesión" if count == 1 else "sesiones"
    return f" ({count} {palabra})"


def _derive_template_variables(
    template_id: str, variables: Dict[str, Any], formality: Optional[str] = None
) -> Dict[str, Any]:
    """Return a copy of ``variables`` with any template-derived slots added.

    Derived slots are values the template body needs but the caller does not
    pass directly — e.g. map/pago-confirmado composes ``sesiones_detalle`` from
    the optional ``sesiones`` count so the naive substitution renderer never has
    to decide singular/plural or hide an absent optional. The caller's dict is
    not mutated; unrelated templates pass through untouched. `formality` is the
    register being rendered, for derived copy that addresses the reader.
    """
    if template_id == "map/pago-confirmado":
        derived = dict(variables)
        derived["sesiones_detalle"] = _sesiones_detalle(variables.get("sesiones"))
        # The Crea frame's values (brand ground and text, both logos, the
        # credited platform) come from the one CTM registry the sign-in mail's
        # frame reads too, never from the caller: set last, so a caller's
        # same-named variable cannot restyle or re-link the frame.
        derived.update(_CTM_FRAME_SLOTS)
        return derived
    if template_id == "billing/cfdi":
        derived = dict(variables)
        derived["portal_bloque"], derived["portal_texto"] = cfdi_portal_slots(
            variables.get("portal_url"), formality
        )
        # The footer's copyright year, as of the send (CDMX), never hardcoded.
        derived["anio"] = str(datetime.now(ZoneInfo("America/Mexico_City")).year)
        return derived
    if template_id == email_billing_notice.TEMPLATE_ID:
        derived = dict(variables)
        # Rows, links and section flags; set after the caller's values so a
        # same-named variable cannot replace composed markup.
        derived.update(email_billing_notice.billing_notice_slots(variables))
        derived["anio"] = str(datetime.now(ZoneInfo("America/Mexico_City")).year)
        return derived
    if template_id == email_ops_alert.TEMPLATE_ID:
        derived = dict(variables)
        # The escaped multi-line detail and the optional action link; set after
        # the caller's values so a same-named variable cannot replace them.
        derived.update(email_ops_alert.ops_alert_slots(variables))
        derived["anio"] = str(datetime.now(ZoneInfo("America/Mexico_City")).year)
        return derived
    return variables


class UnknownTemplateError(LookupError):
    """The template id is not in EMAIL_TEMPLATES."""


class MissingTemplateVariablesError(ValueError):
    """The context lacks variables the template needs (names in `missing`)."""

    def __init__(self, missing: List[str]):
        super().__init__(", ".join(missing))
        self.missing = missing


class InvalidTemplateVariablesError(MissingTemplateVariablesError):
    """A list variable breaks its item contract (paths such as ``conceptos[1].monto``).

    A subclass of MissingTemplateVariablesError so every existing handler still
    refuses the render; /send-template names it separately.
    """


class UnresolvedTemplateVariablesError(MissingTemplateVariablesError):
    """The template body uses placeholders nothing fills.

    Neither passed, derived, nor declared optional (names in ``missing``). The
    send is refused instead of mailing a literal placeholder to a client: the
    2026-09-24 CTM CFDI went out showing its RFC slot as raw template text.
    """


#: A ``{{name}}`` placeholder as the substitution renderer understands it.
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

#: HTML comments, except Outlook conditionals (``<!--[if mso]>`` / ``<!--<![endif]-->``).
#: Template comments are notes for maintainers and must not ship in a client's email.
_HTML_COMMENT = re.compile(r"<!--(?!\[if)(?!<!\[endif).*?-->", re.DOTALL)


def _strip_html_comments(source: str) -> str:
    return _HTML_COMMENT.sub("", source)


def _read_template_source(template_id: str, formality: Optional[str] = None) -> Optional[str]:
    """The HTML template body (comments stripped), or None when it has no file."""
    from pathlib import Path

    try:
        path = Path(_get_safe_template_path(template_id, formality))
    except ValueError:
        return None
    return _strip_html_comments(path.read_text(encoding="utf-8")) if path.exists() else None


def _read_text_template_source(template_id: str, formality: Optional[str] = None) -> Optional[str]:
    """The plain-text companion body, or None. Whitelisted like the HTML files."""
    from pathlib import Path

    filename = TEXT_TEMPLATE_FILENAMES.get(template_id)
    if formality == FORMALITY_TU and template_id in TEXT_TEMPLATE_FILENAMES_TU:
        filename = TEXT_TEMPLATE_FILENAMES_TU[template_id]
    if filename is None or template_id not in EMAIL_TEMPLATES:
        return None
    base = (Path(__file__).parent.parent.parent.parent / "templates" / "emails").resolve()
    path = (base / filename).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        raise ValueError(f"Invalid text template path detected: {template_id}")
    return path.read_text(encoding="utf-8") if path.exists() else None


def _unresolved_placeholders(
    template_id: str, variables: Dict[str, Any], formality: Optional[str] = None
) -> List[str]:
    """Placeholders the template bodies use that nothing will fill.

    Checked against the template SOURCE, not the rendered output, so a value that
    happens to contain braces can never trip it.
    """
    template = EMAIL_TEMPLATES.get(template_id, {})
    used: set = set()
    for source in (
        _read_template_source(template_id, formality),
        _read_text_template_source(template_id, formality),
    ):
        if source:
            used.update(_PLACEHOLDER.findall(source))
    filled = set(_derive_template_variables(template_id, variables, formality))
    return sorted(used - filled - set(template.get("optional", [])))


#: A Mustache-style section, ``{{#name}}…{{/name}}``: kept when ``name`` has a
#: value, dropped otherwise. Two legacy templates (auth/password-reset,
#: invitation/team-invite) were written with sections the renderer never
#: understood, so they leaked the tags verbatim.
_SECTION = re.compile(r"\{\{#([A-Za-z_][A-Za-z0-9_]*)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)


def _substitute(source: str, template_id: str, variables: Dict[str, Any]) -> str:
    """Resolve sections, fill ``{{key}}`` slots, then blank declared optionals left empty."""
    source = _SECTION.sub(lambda m: m.group(2) if variables.get(m.group(1)) else "", source)
    for key, value in variables.items():
        source = source.replace(f"{{{{{key}}}}}", str(value))
    for name in EMAIL_TEMPLATES.get(template_id, {}).get("optional", []):
        if name not in variables:
            source = source.replace(f"{{{{{name}}}}}", "")
    return source


@dataclass(frozen=True)
class RenderedTemplate:
    template_id: str
    subject: str
    html: str
    default_from_email: Optional[str]
    default_from_name: Optional[str]
    token_link: bool
    # The plain-text part, for templates with a TEXT_TEMPLATE_FILENAMES companion.
    text: Optional[str] = None
    # The register this rendering is in ("tu" | "usted").
    formality: str = FORMALITY_USTED


async def render_registered_template(
    template_id: str, variables: Dict[str, Any], formality: Optional[str] = None
) -> RenderedTemplate:
    """Validate and render one registry template. Render-only: never sends.

    The single implementation behind POST /send-template and POST /preview,
    so a preview is byte-for-byte the subject and HTML a send would produce.

    `formality` is the register ALREADY RESOLVED by the caller
    (`resolve_template_formality`); None means the template's own voice.
    """
    template = EMAIL_TEMPLATES.get(template_id)
    if not template:
        raise UnknownTemplateError(template_id)
    register = normalize_formality(formality) or template_voice(template_id)
    missing = [v for v in template["required"] if v not in variables]
    if missing:
        raise MissingTemplateVariablesError(missing)
    invalid = _invalid_list_variables(template, variables)
    if invalid:
        raise InvalidTemplateVariablesError(invalid)
    subject_source = template["subject"]
    if register == FORMALITY_TU and "subject_tu" in template:
        subject_source = template["subject_tu"]
    try:
        subject = subject_source.format(**variables)
    except KeyError as exc:  # a subject slot outside the declared contract
        raise MissingTemplateVariablesError([str(exc.args[0])])
    unresolved = _unresolved_placeholders(template_id, variables, register)
    if unresolved:
        raise UnresolvedTemplateVariablesError(unresolved)
    html = await render_template(template_id, variables, register)
    text = await render_text_template(template_id, variables, register)
    return RenderedTemplate(
        template_id=template_id,
        subject=subject,
        html=html,
        default_from_email=template.get("default_from_email"),
        default_from_name=template.get("default_from_name"),
        token_link=bool(template.get("token_link")),
        text=text,
        formality=register,
    )


def _invalid_list_variables(template: Dict[str, Any], variables: Dict[str, Any]) -> List[str]:
    """List variables (or item paths) that break the template's declared item shapes."""
    if not template.get("lists"):
        return []
    return email_billing_notice.list_variable_problems(
        variables, template["required"], template["lists"]
    )


async def render_template(
    template_id: str, variables: Dict[str, Any], formality: Optional[str] = None
) -> str:
    """
    Render an email template with variables.
    Templates are stored in templates/emails/ directory.

    Security: This function uses _get_safe_template_path() which implements
    strict whitelist-based path resolution to prevent path traversal attacks.
    User input (template_id) is validated against a whitelist before any
    file operations occur.
    """
    from pathlib import Path

    # Compose any template-derived slots (e.g. the map/pago-confirmado session
    # parenthetical) before substitution, without mutating the caller's dict.
    caller = variables
    variables = _derive_template_variables(template_id, variables, formality)
    if EMAIL_TEMPLATES.get(template_id, {}).get("escape_html"):
        # Caller values are data, not markup; derived slots are composed (and
        # escaped) in Python, so they pass through as-is — including a derived
        # slot a caller happened to send a same-named value for, which the
        # derivation has already replaced.
        variables = {
            k: html_lib.escape(str(v), quote=True) if k in caller and v is caller[k] else v
            for k, v in variables.items()
        }

    try:
        # Security: Get safe path using whitelist lookup (no user input in path)
        template_path_str: str = _get_safe_template_path(template_id, formality)
        template_path: Path = Path(template_path_str)

        if template_path.exists():
            # Security: Path has been validated by _get_safe_template_path
            template_content: str = _strip_html_comments(template_path.read_text(encoding="utf-8"))
            return _substitute(template_content, template_id, variables)

    except ValueError:
        # Template not in whitelist - fall through to fallback
        pass

    # Fallback: Generate simple HTML from variables
    return generate_fallback_html(template_id, variables)


async def render_text_template(
    template_id: str, variables: Dict[str, Any], formality: Optional[str] = None
) -> Optional[str]:
    """The plain-text part for templates that have one, else None. Never escaped."""
    source = _read_text_template_source(template_id, formality)
    if source is None:
        return None
    return _substitute(
        source, template_id, _derive_template_variables(template_id, variables, formality)
    )


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
