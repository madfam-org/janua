"""CTM presentation only: no transport, tokens, sender, policy, or persistence.

Only trusted branding resolved by email_branding opts in. Missing tenant context
keeps the existing generic renderer. Backup-code lists are never email content.
"""

import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from jinja2 import Environment

from app.services.email_branding import CTM_BRANDING, resolve_branding
from app.services.email_i18n import build_email_environment, subject_for, template_candidates

KINDS = frozenset(
    {
        "magic_link",
        "password_reset",
        "verification",
        "welcome",
        "invitation",
        "product_invite",
        "mfa_recovery",
    }
)

_ES = {
    "magic_link": (
        "Entrar a Crea Tu Mundo",
        "Este enlace permite entrar a tu espacio de acceso.",
        "Este enlace permite entrar a su espacio de acceso.",
        "Entrar a mi espacio",
    ),
    "password_reset": (
        "Restablecer la contraseña",
        "Se solicitó cambiar la contraseña de tu cuenta. Usa el enlace sólo si hiciste esta solicitud.",
        "Se solicitó cambiar la contraseña de su cuenta. Use el enlace sólo si hizo esta solicitud.",
        "Restablecer contraseña",
    ),
    "verification": (
        "Verificar el correo electrónico",
        "Confirma tu correo para continuar con el acceso a Crea Tu Mundo.",
        "Confirme su correo para continuar con el acceso a Crea Tu Mundo.",
        "Verificar correo electrónico",
    ),
    "welcome": (
        "El acceso a Crea Tu Mundo está listo",
        "Abre tu espacio para continuar. La información vigente de tu cuenta se consulta en la plataforma.",
        "Abra su espacio para continuar. La información vigente de su cuenta se consulta en la plataforma.",
        "Abrir mi espacio",
    ),
    "invitation": (
        "Invitación a Crea Tu Mundo",
        "Revisa quién invita y a qué espacio corresponde antes de aceptar.",
        "Revise quién invita y a qué espacio corresponde antes de aceptar.",
        "Revisar la invitación",
    ),
    "product_invite": (
        "Invitación de acceso",
        "Revisa la invitación y continúa con el enlace de acceso.",
        "Revise la invitación y continúe con el enlace de acceso.",
        "Revisar mi acceso",
    ),
    "mfa_recovery": (
        "Solicitud de recuperación de acceso",
        "Se solicitó recuperar el acceso a tu cuenta. Sigue únicamente los pasos de recuperación que hayas solicitado.",
        "Se solicitó recuperar el acceso a su cuenta. Siga únicamente los pasos de recuperación que haya solicitado.",
        "Continuar la recuperación",
    ),
}
_EN = {
    "magic_link": (
        "Sign in to Crea Tu Mundo",
        "Use this link to open your access workspace.",
        "Sign in to my workspace",
    ),
    "password_reset": (
        "Reset your password",
        "A password reset was requested for your account. Use the link only if you made this request.",
        "Reset password",
    ),
    "verification": (
        "Verify your email address",
        "Confirm your email address to continue accessing Crea Tu Mundo.",
        "Verify email address",
    ),
    "welcome": (
        "Your Crea Tu Mundo access is ready",
        "Open your workspace to continue. Your current account information is available in the platform.",
        "Open my workspace",
    ),
    "invitation": (
        "Invitation to Crea Tu Mundo",
        "Review who invited you and which workspace the invitation belongs to before accepting.",
        "Review invitation",
    ),
    "product_invite": (
        "Access invitation",
        "Review the invitation and continue using the access link.",
        "Review my access",
    ),
    "mfa_recovery": (
        "Account access recovery request",
        "Account recovery was requested. Follow only recovery steps that you requested yourself.",
        "Continue recovery",
    ),
}
_LINKS = {
    "magic_link": ("magic_link", "magic_url"),
    "password_reset": ("reset_link", "reset_url"),
    "verification": ("verification_link", "verification_url"),
    "welcome": ("dashboard_link", "dashboard_url"),
    "invitation": ("invitation_url", "invitation_link"),
    "product_invite": ("magic_link", "magic_url"),
    "mfa_recovery": ("recovery_url",),
}
_PREHEADERS = {
    "es": {
        "magic_link": "Información para entrar a Crea Tu Mundo.",
        "password_reset": "Información sobre el cambio de contraseña en Crea Tu Mundo.",
        "verification": "Información para verificar el correo en Crea Tu Mundo.",
        "welcome": "Información sobre el acceso a Crea Tu Mundo.",
        "invitation": "Información sobre una invitación a Crea Tu Mundo.",
        "product_invite": "Información sobre una invitación de acceso.",
        "mfa_recovery": "Información sobre una solicitud de recuperación de acceso.",
    },
    "en": {
        "magic_link": "Information about signing in to Crea Tu Mundo.",
        "password_reset": "Information about changing a Crea Tu Mundo password.",
        "verification": "Information about verifying an email address in Crea Tu Mundo.",
        "welcome": "Information about access to Crea Tu Mundo.",
        "invitation": "Information about a Crea Tu Mundo invitation.",
        "product_invite": "Information about an access invitation.",
        "mfa_recovery": "Information about an account access recovery request.",
    },
}


def action_destination(value: Any) -> Optional[str]:
    """Validate presentation destinations without decoding or changing a token."""
    if not isinstance(value, str) or not value:
        return None
    if any(char.isspace() or unicodedata.category(char) in {"Cc", "Cf"} for char in value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme.lower() not in {"http", "https"} or not url.netloc or not url.hostname:
            return None
        if url.username is not None or url.password is not None:
            return None
        _ = url.port
    except ValueError:
        return None
    return value


def ctm_presentation_context(
    template_name: str,
    data: Dict[str, Any],
    locale: Optional[str] = None,
    formality: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    kind = template_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if data.get("presentation_family") != "ctm" or kind not in KINDS:
        return None
    language = "en" if str(locale or data.get("locale") or "es").lower().startswith("en") else "es"
    formal = (formality or data.get("formality")) == "usted"
    if language == "es":
        heading, informal, formal_intro, action = _ES[kind]
        intro = formal_intro if formal else informal
        security = (
            "Si no solicitó este acceso, ignore el mensaje. No comparta enlaces ni códigos: quien los tenga podría acceder a su cuenta."
            if formal
            else "Si no solicitaste este acceso, ignora el mensaje. No compartas enlaces ni códigos: quien los tenga podría acceder a tu cuenta."
        )
        labels = {
            "hello": "Hola",
            "security": "Seguridad del acceso",
            "fallback": "Si el botón no abre, esta es la misma dirección para copiar en el navegador:",
            "help": (
                "Para pedir ayuda, responda a este correo."
                if formal
                else "Para pedir ayuda, responde a este correo."
            ),
            "powered": "Con tecnología de",
            "inviter": "Invita",
            "organization": "Espacio",
            "role": "Rol",
            "code": "Código temporal",
            "no_link": "Este mensaje no contiene un enlace de recuperación.",
            "request": "Detalles de la solicitud",
            "time": "Fecha y hora",
            "ip": "Dirección IP",
            "browser": "Navegador",
        }
    else:
        heading, intro, action = _EN[kind]
        security = "If you did not request this access, ignore this message. Do not share links or codes: anyone holding them could access your account."
        labels = {
            "hello": "Hello",
            "security": "Protect your access",
            "fallback": "If the button does not open, copy this same address into your browser:",
            "help": "Reply to this email if you need help.",
            "powered": "Powered by",
            "inviter": "Invited by",
            "organization": "Workspace",
            "role": "Role",
            "code": "Temporary code",
            "no_link": "This message contains no recovery link.",
            "request": "Request details",
            "time": "Date and time",
            "ip": "IP address",
            "browser": "Browser",
        }
    link = (
        action_destination(next((data.get(key) for key in _LINKS[kind] if data.get(key)), None))
        or ""
    )
    expiry = ""
    if kind == "magic_link":
        expiry = (
            "Este enlace funciona una sola vez y expira en 15 minutos."
            if language == "es"
            else "This link works once and expires in 15 minutes."
        )
    elif kind == "password_reset":
        expiry = (
            "Este enlace expira en 1 hora." if language == "es" else "This link expires in 1 hour."
        )
    elif kind == "verification":
        hours = data.get("verification_expiry_hours")
        if type(hours) is int and hours > 0:
            expiry = (
                f"Este enlace de verificación expira en {hours} horas."
                if language == "es"
                else f"This verification link expires in {hours} hours."
            )
    elif kind in {"invitation", "product_invite"} and data.get("expires_at"):
        expiry = (
            f"Vigencia de la invitación: {data['expires_at']}"
            if language == "es"
            else f"Invitation valid until: {data['expires_at']}"
        )
    elif kind == "product_invite":
        hours = data.get("expires_hours")
        if type(hours) is int and hours > 0:
            expiry = (
                f"Este enlace de invitación expira en {hours} horas."
                if language == "es"
                else f"This invitation link expires in {hours} hours."
            )
    code = data.get(
        {
            "password_reset": "reset_code",
            "verification": "verification_code",
            "mfa_recovery": "recovery_code",
        }.get(kind, "")
    )
    code_expiry = ""
    if code:
        if kind == "mfa_recovery":
            minutes = data.get("recovery_expiry_minutes")
            if type(minutes) is int and minutes > 0:
                code_expiry = (
                    f"Este código temporal expira en {minutes} minutos."
                    if language == "es"
                    else f"This temporary code expires in {minutes} minutes."
                )
            elif language == "es":
                code_expiry = (
                    "No comparta este código. Úselo sólo en el proceso de recuperación solicitado."
                    if formal
                    else "No compartas este código. Úsalo sólo en el proceso de recuperación que solicitaste."
                )
            else:
                code_expiry = (
                    "Do not share this code. Use it only in the recovery process you requested."
                )
        else:
            minutes = 15 if kind == "verification" else 30
            code_expiry = (
                f"Este código temporal funciona una sola vez y expira en {minutes} minutos."
                if language == "es"
                else f"This temporary code works once and expires in {minutes} minutes."
            )
    if not link:
        expiry = ""
        if kind != "mfa_recovery":
            intro = (
                "El enlace para continuar no está disponible en este mensaje."
                if language == "es"
                else "The link to continue is not available in this message."
            )
    # Do not invent an expiry or a working recovery link for the legacy backup-
    # code notification path. Its recovery protocol requires separate review.
    context = {
        **data,
        "locale": language,
        "kind": kind,
        "heading": heading,
        "preheader": _PREHEADERS[language][kind],
        "intro": intro,
        "action_label": action,
        "action_url": link,
        "security_copy": security,
        "labels": labels,
        "expiry_copy": expiry,
        "temporary_code": code,
        "code_expiry_copy": code_expiry,
        "user_name": data.get("user_name")
        or (data.get("first_name") if kind == "product_invite" else None),
    }
    return context


def render_ctm_email(
    env: Environment,
    template_name: str,
    data: Dict[str, Any],
    locale: Optional[str] = None,
    formality: Optional[str] = None,
) -> Optional[str]:
    context = ctm_presentation_context(template_name, data, locale, formality)
    if context is None:
        return None
    extension = "txt" if template_name.endswith(".txt") else "html"
    return env.get_template(f"ctm/message.{extension}").render(**context)


def ctm_subject(
    template_name: str,
    data: Dict[str, Any],
    locale: Optional[str] = None,
    formality: Optional[str] = None,
) -> Optional[str]:
    context = ctm_presentation_context(template_name, data, locale, formality)
    return context["heading"] if context is not None else None


# These are preview capabilities, never additions to the send-template registry.
AUTH_PREVIEW_TEMPLATES = {
    "auth/password-reset": {
        "kind": "password_reset",
        "description": "Restablecimiento de contraseña — revisión de la presentación de acceso",
        "subject": "Restablecer la contraseña",
        "required": ["reset_url"],
        "optional": ["user_name", "locale"],
        "token_link": True,
    },
    "auth/mfa-recovery": {
        "kind": "mfa_recovery",
        "description": "Recuperación de acceso — revisión sin códigos de respaldo",
        "subject": "Solicitud de recuperación de acceso",
        "required": [],
        "optional": ["user_name", "recovery_url", "recovery_code", "request_time", "locale"],
        "token_link": True,
    },
}


def render_auth_preview(
    template_id: str,
    data: Dict[str, Any],
    org_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
    formality: Optional[str] = None,
) -> Dict[str, str]:
    """Pure local preview of the same presentation used by the auth mailers."""
    entry = AUTH_PREVIEW_TEMPLATES[template_id]
    missing = [
        key
        for key in entry["required"]
        if not data.get(key) and not (key == "reset_url" and data.get("reset_link"))
    ]
    if missing:
        raise ValueError(",".join(missing))
    context = {
        key: value
        for key, value in data.items()
        if key not in CTM_BRANDING
        and key not in {"recovery_expiry_minutes", "verification_expiry_hours"}
    }
    context.update(resolve_branding(org_id=org_id, redirect_url=redirect_url))
    language = "es" if str(data.get("locale") or "es").startswith("es") else "en"
    register = formality or "tu"
    env = build_email_environment(Path(__file__).parent.parent / "templates" / "email")
    parts = {}
    for extension in ("html", "txt"):
        name = f"{entry['kind']}.{extension}"
        rendered = render_ctm_email(env, name, context, language, register)
        if rendered is None:
            template = env.select_template(template_candidates(name, language))
            body_language = language if (template.name or "").startswith(f"{language}/") else "en"
            rendered = template.render(
                **{**context, "locale": body_language, "formality": register}
            )
        parts[extension] = rendered
    subject = ctm_subject(entry["kind"], context, language, register) or (
        subject_for(entry["kind"], language, register)
        if entry["kind"] == "password_reset"
        else "Account Recovery Request - Janua"
    )
    return {"subject": subject, "html": parts["html"], "text": parts["txt"]}


def payment_session_detail(sesiones: Any) -> str:
    """The Spanish session-count parenthetical for map/pago-confirmado, or "".

    Shared by the registered renderer and the local Jinja presentation. The
    optional phrase is composed once for HTML and text, so an absent count
    cannot leave an unresolved slot or a different number in either part.

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


def render_map_payment(data: Dict[str, Any]) -> Dict[str, str]:
    """The registered MAP payment body, pure Jinja with extension autoescape."""
    env = build_email_environment(Path(__file__).resolve().parents[2] / "templates" / "emails")
    context = {
        **data,
        **CTM_BRANDING,
        "sesiones_detalle": payment_session_detail(data.get("sesiones")),
    }
    return {
        "html": env.get_template("map_pago-confirmado.html").render(**context),
        "text": env.get_template("map_pago-confirmado.txt").render(**context),
    }
