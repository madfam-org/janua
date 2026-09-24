"""Render-only email preview: POST /api/v1/internal/email/preview (+ template list).

THE CONTRACT (sending apps code against this; keep it exact). Same
`X-Internal-API-Key` dependency as /internal/email/send.

    POST /api/v1/internal/email/preview
      {"kind": "template", "template": "map/pago-confirmado",
       "context": {"periodo": "septiembre de 2026"}, "org_id": "<uuid>"?}
      {"kind": "raw", <the same body as POST /internal/email/send>}
      Optional on both, mirroring the send routes: org_id, from_email,
      from_name, redirect_url. "raw" accepts the whole SendEmailRequest schema
      (to/cc/bcc optional and ignored; reply_to, source_app, source_type, tags,
      attachments, contains_token_link accepted and applied as a send would --
      none of them changes subject, From or bodies) and IGNORES unknown fields,
      so a caller can preview the exact body it is about to send.

    200 {"subject": str, "from": "Display <addr>" (decoded, human-readable),
         "html": str|null,
         "text": str|null, "template": str (template kind only)}
    404 {"detail": "Unknown template"}
    422 {"detail": "Missing required variables", "missing": ["periodo", ...]}
    503 {"detail": "Sender binding has no transport"}   (smtp binding stub)

    GET /api/v1/internal/email/preview/templates
    200 [{"id", "description", "subject", "required_variables",
          "optional_variables", "token_link"}]

WHAT A PREVIEW IS. Exactly the subject, From header and bodies the real send
would hand to Resend for the same input, produced by the SAME functions:
`render_registered_template` (the /send-template renderer) and
`resolve_message_envelope` (the send path's sender, account and
tracked-domain token-link resolution). So when a real send would go out
text-only (EMAIL_TRACKED_SENDER_DOMAINS + a token link), the preview has
`html: null` too. For "raw", Janua applies NO layout, branding or wrapping on
/send: the bodies come back as given, except for that token-link rule.

WHAT A PREVIEW NEVER DOES: send, call Resend, open a database session, write
an audit/log row, or emit the send path's operational log lines.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import verify_internal_api_key
from app.routers.v1.email import (
    EMAIL_TEMPLATES,
    MissingTemplateVariablesError,
    UnknownTemplateError,
    render_registered_template,
)
from app.services.resend_email_service import resolve_message_envelope

router = APIRouter(prefix="/email", tags=["email"])


class _SenderSignals(BaseModel):
    # str, like SendEmailRequest/SendTemplateEmailRequest: an org id the
    # resolver does not know resolves to the platform sender, as on a send.
    org_id: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    redirect_url: Optional[str] = None


class TemplatePreviewRequest(_SenderSignals):
    kind: Literal["template"]
    template: str = Field(min_length=1)
    context: Dict[str, Any] = Field(default_factory=dict)


class RawPreviewRequest(_SenderSignals):
    """SendEmailRequest's schema, with every field that cannot change the
    rendered message accepted loosely so a real send body never 422s here."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["raw"]
    subject: str
    text: Optional[str] = None
    html: Optional[str] = None
    contains_token_link: bool = False
    # Accepted and ignored: recipients and envelope-only fields.
    to: Optional[Any] = None
    cc: Optional[Any] = None
    bcc: Optional[Any] = None
    reply_to: Optional[Any] = None
    attachments: Optional[Any] = None
    tags: Optional[Any] = None
    source_app: Optional[Any] = None
    source_type: Optional[Any] = None


PreviewRequest = Annotated[
    Union[TemplatePreviewRequest, RawPreviewRequest], Field(discriminator="kind")
]


class PreviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    subject: str
    from_: str = Field(alias="from")
    html: Optional[str]
    text: Optional[str]
    template: Optional[str] = None


class PreviewTemplateInfo(BaseModel):
    id: str
    description: str
    subject: str
    required_variables: List[str]
    optional_variables: List[str]
    token_link: bool


@router.post(
    "/preview",
    response_model=PreviewResponse,
    response_model_by_alias=True,
    response_model_exclude_unset=True,
)
async def preview_email(
    request: PreviewRequest = Body(...),
    _: bool = Depends(verify_internal_api_key),
) -> Any:
    template_id: Optional[str] = None
    from_email, from_name = request.from_email, request.from_name
    if isinstance(request, TemplatePreviewRequest):
        try:
            rendered = await render_registered_template(request.template, request.context)
        except UnknownTemplateError:
            return JSONResponse(status_code=404, content={"detail": "Unknown template"})
        except MissingTemplateVariablesError as exc:
            return JSONResponse(
                status_code=422,
                content={"detail": "Missing required variables", "missing": exc.missing},
            )
        template_id, subject = rendered.template_id, rendered.subject
        html: Optional[str] = rendered.html
        text: Optional[str] = None  # /send-template sends HTML only
        token_link = rendered.token_link
        # Same default-sender precedence as /send-template.
        from_email = from_email or rendered.default_from_email
        from_name = from_name or rendered.default_from_name
    else:
        subject = request.subject
        html = request.html or ""  # exactly what /send passes to the service
        text = request.text
        token_link = request.contains_token_link

    envelope = await resolve_message_envelope(
        html_content=html,
        text_content=text,
        from_email=from_email,
        from_name=from_name,
        redirect_url=request.redirect_url,
        org_id=request.org_id,
        token_link=token_link,
        observe=False,
    )
    if envelope.unsupported_provider_tenant is not None:
        return JSONResponse(status_code=503, content={"detail": "Sender binding has no transport"})

    fields: Dict[str, Any] = {
        "subject": subject,
        # Human-readable; the wire form is its RFC 2047 encoding (same header).
        "from_": envelope.from_display,
        # The transport omits an empty body; so does the preview.
        "html": envelope.html or None,
        "text": envelope.text or None,
    }
    if template_id is not None:
        fields["template"] = template_id
    return PreviewResponse(**fields)


@router.get("/preview/templates", response_model=List[PreviewTemplateInfo])
async def list_preview_templates(_: bool = Depends(verify_internal_api_key)) -> Any:
    """Every Janua-owned template previewable (and sendable via /send-template)."""
    return [
        PreviewTemplateInfo(
            id=template_id,
            description=info["description"],
            subject=info["subject"],
            required_variables=list(info["required"]),
            optional_variables=list(info.get("optional", [])),
            token_link=bool(info.get("token_link")),
        )
        for template_id, info in EMAIL_TEMPLATES.items()
    ]
