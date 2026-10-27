"""The language of the hosted sign-in pages, from OIDC ``ui_locales``.

A client that knows its person's language says so on the authorize request
(OIDC Core §3.1.2.1, ``ui_locales``: space-separated BCP 47 tags in order of
preference). ``/oauth/authorize`` carries the first tag Janua can render to the
hosted login page, and every hosted page after it (the password and sign-in
link forms, their error re-renders, «check your inbox», password recovery)
carries it forward in a hidden field or a query parameter.

ENGLISH STAYS THE DEFAULT, BYTE FOR BYTE. A request without ``ui_locales`` (every
client before MADFAM CV) renders exactly the English page it rendered before:
the ``en`` strings below are the literals the pages already printed, and the
regression tests pin them. Spanish appears only when a client asks for it.

THE SPANISH REGISTER IS ``tú``. The hosted Spanish pages that already existed
(the magic-link interstitial and the dead-link page) speak ``tú``, and so do the
products that ask for Spanish today (Crea Tu Mundo's, MADFAM CV). One journey
should not switch voice between screens.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.locale import normalize_locale

#: The OIDC parameter name, used on the authorize request, the login URL, the
#: hidden form field and the recovery links alike.
UI_LOCALES_PARAM = "ui_locales"

#: What a hosted page renders in when the request named no supported language.
DEFAULT_HOSTED_LOCALE = "en"

#: The languages the hosted pages have copy for (keys of HOSTED_COPY below).
HOSTED_LOCALES = ("es", "en")

# A ui_locales value is attacker-controlled; read a bounded prefix.
_MAX_UI_LOCALES_CHARS = 256
_MAX_UI_LOCALES_TAGS = 16


def hosted_locale(ui_locales: Any) -> Optional[str]:
    """The first tag of an OIDC ``ui_locales`` value Janua can render, or None.

    ``"es-MX en"`` → ``"es"``; ``"fr-CA es"`` → ``"es"``; ``"fr"`` → None. Never
    raises: an absent, malformed or hostile value is simply no preference.
    """
    if not ui_locales or not isinstance(ui_locales, str):
        return None
    for tag in ui_locales[:_MAX_UI_LOCALES_CHARS].split()[:_MAX_UI_LOCALES_TAGS]:
        normalized = normalize_locale(tag)
        # Return OUR constant, never a slice of the request: every hosted page
        # prints this value (lang attribute, hidden field, links), so it must be
        # provably one of a fixed set, not merely checked against one.
        for supported in HOSTED_LOCALES:
            if normalized == supported:
                return supported
    return None


def page_locale(ui_locales: Any) -> str:
    """The language a hosted page renders in: the request's, else English."""
    return hosted_locale(ui_locales) or DEFAULT_HOSTED_LOCALE


def html_lang(locale: str) -> str:
    """The ``<html lang>`` value for a page locale."""
    return "es-MX" if locale == "es" else "en"


# Every string the hosted sign-in pages print. ``en`` values are the exact
# literals the pages printed before this module existed (the regression tests
# assert several of them verbatim); change them only together with those tests.
HOSTED_COPY: Dict[str, Dict[str, str]] = {
    "en": {
        "sign_in_title": "Sign in - Janua",
        "tagline": "Identity Platform",
        "signing_in_to": "Signing in to",
        "email_label": "Email",
        "password_label": "Password",
        "forgot_password": "Forgot your password?",
        "sign_in_button": "Sign In",
        "magic_hint": "We'll email you a link that signs you in &mdash; no password needed.",
        "magic_button": "Email me a sign-in link",
        "switch_to_password": "Use a password instead",
        "switch_to_magic": "Email me a sign-in link instead",
        "footer": "Powered by Janua &bull; Secure Authentication",
        "invalid_credentials": "Invalid email or password. Please try again.",
        "locked_temporarily": (
            "Account temporarily locked due to too many failed login attempts. "
            "Please try again in {minutes} minute(s)."
        ),
        "locked_now": (
            "Account locked due to too many failed login attempts. "
            "Please try again in {minutes} minute(s)."
        ),
        "invalid_email": "Enter a valid email address.",
        "magic_unavailable": "Sign-in links are not available right now. Please use your password.",
        "magic_send_failed": "We could not send a sign-in link.",
        "session_expired_title": "Sign-in session expired",
        "session_expired_body": (
            "This sign-in request is no longer valid. Go back to the "
            "application and start signing in again."
        ),
        "inbox_title": "Check your inbox - Janua",
        "inbox_heading": "Check your inbox",
        "inbox_sent_to": "We emailed a sign-in link to",
        "inbox_open_on_device": "Open it on this device to continue to",
        "inbox_hint": (
            "The link works once and expires in 15 minutes. Nothing there? Check your\n"
            "        spam folder, then go back and request another."
        ),
        # Invite-only clients: the same page for an address that has access and
        # one that does not, so the form never says which addresses exist.
        "inbox_if_invited": "If this address has been invited to",
        "inbox_if_invited_tail": ", a sign-in link is on its way to",
        "recovery_title": "Password recovery - Janua",
        "recovery_tagline": "Password recovery",
        "recovery_lead": (
            "Enter your account email and we&#39;ll send you a reset link. "
            "The link works once and expires in 1 hour."
        ),
        "recovery_button": "Send reset link",
        "recovery_sent": (
            "If an account exists for <strong>{email}</strong>, a reset link is on its way. "
            "It works once and expires in 1 hour."
        ),
        "recovery_retry": (
            "Didn&#39;t get it? Check spam, or <a href=\"{retry_url}\">try again</a> "
            "in a few minutes."
        ),
        "invite_only_title": "Invitation required - Janua",
        "invite_only_heading": "This account has no access to",
        "invite_only_body": (
            "Access is by invitation. If you were invited with another email address, "
            "sign in with that one."
        ),
        "invite_only_other_account": "Use another account",
    },
    "es": {
        "sign_in_title": "Iniciar sesión - Janua",
        "tagline": "Plataforma de identidad",
        "signing_in_to": "Entrando a",
        "email_label": "Correo electrónico",
        "password_label": "Contraseña",
        "forgot_password": "¿Olvidaste tu contraseña?",
        "sign_in_button": "Entrar",
        "magic_hint": "Te enviamos por correo un enlace para entrar, sin contraseña.",
        "magic_button": "Enviarme un enlace para entrar",
        "switch_to_password": "Usar mi contraseña",
        "switch_to_magic": "Enviarme un enlace para entrar",
        "footer": "Con tecnología de Janua &bull; Autenticación segura",
        "invalid_credentials": "El correo o la contraseña no son correctos. Inténtalo de nuevo.",
        "locked_temporarily": (
            "La cuenta está bloqueada por demasiados intentos fallidos. "
            "Inténtalo de nuevo en {minutes} minuto(s)."
        ),
        "locked_now": (
            "La cuenta quedó bloqueada por demasiados intentos fallidos. "
            "Inténtalo de nuevo en {minutes} minuto(s)."
        ),
        "invalid_email": "Escribe un correo electrónico válido.",
        "magic_unavailable": (
            "Los enlaces para entrar no están disponibles en este momento. "
            "Entra con tu contraseña."
        ),
        "magic_send_failed": "No pudimos enviar el enlace para entrar.",
        "session_expired_title": "La solicitud para entrar venció",
        "session_expired_body": (
            "Esta solicitud ya no es válida. Regresa a la aplicación y vuelve a iniciar sesión."
        ),
        "inbox_title": "Revisa tu correo - Janua",
        "inbox_heading": "Revisa tu correo",
        "inbox_sent_to": "Enviamos un enlace para entrar a",
        "inbox_open_on_device": "Ábrelo en este dispositivo para continuar a",
        "inbox_hint": (
            "El enlace funciona una sola vez y vence en 15 minutos. ¿No llegó? Revisa la\n"
            "        carpeta de spam y vuelve a pedirlo."
        ),
        "inbox_if_invited": "Si esta dirección tiene invitación a",
        "inbox_if_invited_tail": ", te llegará un enlace para entrar en",
        "recovery_title": "Recuperar contraseña - Janua",
        "recovery_tagline": "Recuperar contraseña",
        "recovery_lead": (
            "Escribe el correo de tu cuenta y te enviamos un enlace para cambiar la contraseña. "
            "Funciona una sola vez y vence en 1 hora."
        ),
        "recovery_button": "Enviar enlace",
        "recovery_sent": (
            "Si existe una cuenta con <strong>{email}</strong>, ya va en camino un enlace "
            "para cambiar la contraseña. Funciona una sola vez y vence en 1 hora."
        ),
        "recovery_retry": (
            "¿No llegó? Revisa la carpeta de spam o <a href=\"{retry_url}\">vuelve a "
            "intentarlo</a> en unos minutos."
        ),
        "invite_only_title": "Se necesita invitación - Janua",
        "invite_only_heading": "Esta cuenta no tiene acceso a",
        "invite_only_body": (
            "El acceso es por invitación. Si te invitaron con otro correo, entra con ese."
        ),
        "invite_only_other_account": "Usar otra cuenta",
    },
}


def hosted_copy(locale: Optional[str]) -> Dict[str, str]:
    """The string table for a page locale (English for anything unknown)."""
    return HOSTED_COPY.get(locale or DEFAULT_HOSTED_LOCALE, HOSTED_COPY[DEFAULT_HOSTED_LOCALE])


def hidden_ui_locales_field(locale: Optional[str]) -> str:
    """The hidden form field that carries a NON-default page language forward.

    Empty for English, so the English forms stay byte-identical to the forms
    every client already had. Only Spanish produces a field (a constant).
    """
    if locale == "es":
        return f'<input type="hidden" name="{UI_LOCALES_PARAM}" value="es">'
    return ""


def ui_locales_query(locale: Optional[str]) -> str:
    """``?ui_locales=es`` for a non-default page language, else an empty string."""
    if locale == "es":
        return f"?{UI_LOCALES_PARAM}=es"
    return ""
