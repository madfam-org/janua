"""Locale resolution and localized strings for transactional email.

The mail path had no notion of language at all: subjects were string literals
at each call site and every template was English-only. That made English the
first thing every recipient saw, regardless of who they are — which is wrong
for a user base that is predominantly Mexican.

Three moving parts live here so the email service stays about *sending*:

1. `resolve_locale` — per-recipient language with an explicit precedence.
2. `subject_for`   — the subject line, keyed by message rather than hardcoded.
3. `template_candidates` — the localized template name, with English as the
   fallback so a locale that has not been translated yet still sends a real
   message instead of failing.

Locale tags are normalized to a bare language subtag (`es-MX`, `es_419`,
`ES-mx` all mean `es`), because a translation set is per-language; regional
variants share it. The Spanish copy is written for es-MX specifically.

Spanish additionally carries a *register* — how the reader is addressed. See
the "Spanish formality" section below; `t()` resolves every Spanish string
against the recipient's chosen register, so a template author picks a key and
never picks a register.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape

# Languages that have a full translation set. Order is not significant.
SUPPORTED_LOCALES: tuple = ("es", "en")

# English is the fallback for any string a locale has not translated yet —
# never an empty body.
FALLBACK_LOCALE = "en"

# Client-facing mail defaults to Spanish: this platform's users are
# predominantly Mexican, so English is the wrong default even though it was
# the only option before. Overridable per-deployment via DEFAULT_EMAIL_LOCALE
# and per-message via the `locale` argument.
DEFAULT_LOCALE = "es"


def normalize_locale(raw: Any) -> Optional[str]:
    """Reduce a locale tag to a supported bare language subtag.

    Accepts the shapes that actually show up in stored user profiles and
    Accept-Language headers: `es`, `es-MX`, `es_MX`, `ES-mx`, `es-419`.
    Returns None for anything unsupported or unparseable so callers can fall
    through to the next precedence tier rather than silently picking a
    language nobody asked for.
    """
    if not raw or not isinstance(raw, str):
        return None
    # Split on both separators; BCP 47 uses "-", POSIX-style profiles use "_".
    language = raw.strip().replace("_", "-").split("-", 1)[0].lower()
    if language in SUPPORTED_LOCALES:
        return language
    return None


def resolve_locale(
    explicit: Any = None,
    user: Any = None,
    default: Any = None,
) -> str:
    """Resolve the language for one recipient, highest precedence first.

    1. `explicit` — what the caller passed. A caller that knows the audience
       (an invitation addressed to a specific person, an operator-triggered
       resend) always wins.
    2. `user.locale` — the recipient's stored preference. `users.locale`
       exists on the model and in the schema, so this is a real column and
       not an aspiration; it is nullable and unset for most rows today.
    3. `default` — the deployment default (DEFAULT_EMAIL_LOCALE).
    4. `DEFAULT_LOCALE` — es-MX.

    Each tier is skipped when it is absent OR unsupported, so a stored
    `fr-CA` does not shadow the configured default with an untranslated
    language.
    """
    for candidate in (
        explicit,
        getattr(user, "locale", None) if user is not None else None,
        default,
    ):
        normalized = normalize_locale(candidate)
        if normalized:
            return normalized
    return DEFAULT_LOCALE


def template_candidates(template_name: str, locale: str) -> List[str]:
    """Template names to try, most specific first.

    Localized templates live in a per-language subdirectory
    (`templates/email/es/magic_link.html`); English stays at the root, where
    it already is. The loader is rooted at `templates/email`, so a template
    under `es/` still resolves `{% extends "base.html" %}` to the one shared
    base — the subdirectory changes nothing about inheritance.

    English is always appended last: a message with no translation yet sends
    in English rather than raising.
    """
    if locale == FALLBACK_LOCALE:
        return [template_name]
    return [f"{locale}/{template_name}", template_name]


# --------------------------------------------------------------------------
# Spanish formality (register)
#
# Spanish forces a choice English does not: every sentence addressed at the
# reader is either `tú` (informal) or `usted` (formal). There is no neutral
# second person, so mail written in one register and read by someone who
# expects the other lands as either presumptuous or cold — and that judgement
# belongs to the reader, not to us.
#
# ONLY TWO REGISTERS ARE SUPPORTED, AND `vosotros` IS DELIBERATELY NOT ONE OF
# THEM. `vosotros` is Peninsular Spanish; in Mexico it is not merely unused,
# it reads as either foreign or comic — the register of a dubbed cartoon, not
# of a clinic writing to its patients. The client this exists for is Mexican.
# Please do not re-propose it: adding it would mean maintaining a third copy
# of every string for an audience this platform does not have.
# --------------------------------------------------------------------------
FORMALITY_TU = "tu"
FORMALITY_USTED = "usted"
SPANISH_FORMALITIES: tuple = (FORMALITY_TU, FORMALITY_USTED)

# `usted` is the default, and NULL on the user row means "has not chosen".
# A first contact is with someone who has told us nothing about themselves;
# `usted` is the register that is merely formal if wrong, where `tú` is
# familiar if wrong. Formal-if-wrong is the cheaper error.
DEFAULT_FORMALITY = FORMALITY_USTED


def normalize_formality(raw: Any) -> Optional[str]:
    """Reduce a stored/received formality value to a supported register.

    Accepts the shapes that show up in practice: `tu`, `tú` (accented, as a
    human would type it), `USTED`, surrounding whitespace. Returns None for
    anything else — including `vosotros` — so callers fall through to the
    next precedence tier instead of rendering a register nobody supports.
    """
    if not raw or not isinstance(raw, str):
        return None
    value = raw.strip().lower().replace("ú", "u")
    if value in SPANISH_FORMALITIES:
        return value
    return None


def resolve_formality(explicit: Any = None, user: Any = None) -> str:
    """Resolve the Spanish register for one recipient, highest precedence first.

    1. `explicit` — what the caller passed. A caller that knows the audience
       (an operator resending on someone's behalf) always wins.
    2. `user.spanish_formality` — the recipient's stored choice. Nullable;
       NULL means "has not chosen" and falls through rather than meaning `tú`.
    3. `DEFAULT_FORMALITY` — `usted`.

    Deliberately has no deployment-wide tier the way `resolve_locale` does:
    register is a property of the reader, not of the installation.

    It DOES have a per-product tier, one level below the reader — see
    `resolve_formality_for_request`, which threads the requesting product's own
    voice in between the user row and DEFAULT_FORMALITY. That is not a
    deployment tier: it is a fact about the app the reader just clicked.
    """
    for candidate in (
        explicit,
        getattr(user, "spanish_formality", None) if user is not None else None,
    ):
        normalized = normalize_formality(candidate)
        if normalized:
            return normalized
    return DEFAULT_FORMALITY


def resolve_formality_for_request(
    explicit: Any = None,
    user: Any = None,
    client_default: Any = None,
) -> str:
    """Resolve the register for a message sent ON BEHALF OF a product.

    Same as `resolve_formality` with one tier inserted: what the REQUESTING
    PRODUCT sounds like, consulted after the reader and before the global
    default. Highest precedence first:

    1. `explicit` — a register named on the request itself. The product knows
       its own audience, and an operator resending on someone's behalf knows
       better still.
    2. `user.spanish_formality` — the reader's own stored choice. Still beats
       the product: a person who has told us how they want to be addressed is
       addressed that way in every product's mail.
    3. `client_default` — the requesting product's voice
       (`email_branding.default_formality_for`, keyed on the redirect host).
       This tier exists because tier 2 is NULL for almost everybody, and
       falling straight to `usted` made janua's mail contradict the login page
       the reader had just read in `tú` (2026-09-06, crea-map).
    4. `DEFAULT_FORMALITY` — `usted`.

    Each tier is skipped when absent or unsupported, so an unrecognized value
    anywhere falls through instead of shadowing a good one below it.
    """
    for candidate in (
        explicit,
        getattr(user, "spanish_formality", None) if user is not None else None,
        client_default,
    ):
        normalized = normalize_formality(candidate)
        if normalized:
            return normalized
    return DEFAULT_FORMALITY


# --------------------------------------------------------------------------
# Subjects
#
# Keyed by message so the call sites stop carrying English string literals.
# es-MX business register: usted-form, "correo electrónico", "iniciar sesión".
#
# The `es` entries here are the USTED register. Their `tú` counterparts live
# in SUBJECTS_ES_TU below; every one of these five subjects addresses the
# reader, so every one of them has a counterpart.
# --------------------------------------------------------------------------
SUBJECTS: Dict[str, Dict[str, str]] = {
    "verification": {
        "en": "Verify your Janua account",
        "es": "Verifique su cuenta de Janua",
    },
    "password_reset": {
        "en": "Reset your Janua password",
        "es": "Restablezca su contraseña de Janua",
    },
    "magic_link": {
        "en": "Your sign-in link",
        "es": "Su enlace de acceso",
    },
    "welcome": {
        "en": "Welcome to Janua!",
        "es": "Le damos la bienvenida a Janua",
    },
    "invitation": {
        "en": "You're invited to join {organization_name} on Janua",
        "es": "Le invitaron a unirse a {organization_name} en Janua",
    },
}

# `tú` subjects. Keyed identically to SUBJECTS; a message missing from here
# falls back to its usted subject rather than to English.
# tests/unit/services/test_email_formality.py fails if a key here has no
# Spanish counterpart in SUBJECTS, or if a Spanish subject has no entry here.
SUBJECTS_ES_TU: Dict[str, str] = {
    "verification": "Verifica tu cuenta de Janua",
    "password_reset": "Restablece tu contraseña de Janua",
    "magic_link": "Tu enlace de acceso",
    "welcome": "Te damos la bienvenida a Janua",
    "invitation": "Te invitaron a unirse a {organization_name} en Janua",
}


def subject_for(
    message_key: str,
    locale: Optional[str] = None,
    formality: Optional[str] = None,
    **fields: Any,
) -> str:
    """Return the localized subject for a message, in the reader's register.

    Falls back to English when the locale has no translation for this
    message, and to the message key itself only if the key is unknown — an
    unknown key is a programming error, and a visible one beats an email with
    an empty subject line.

    `formality` applies to Spanish only and is ignored for every other
    language; an absent `tú` variant falls back to the usted subject, never
    to English.
    """
    per_locale = SUBJECTS.get(message_key)
    if not per_locale:
        return message_key
    resolved = normalize_locale(locale) or FALLBACK_LOCALE
    template = per_locale.get(resolved) or per_locale[FALLBACK_LOCALE]
    if resolved == "es" and normalize_formality(formality) == FORMALITY_TU:
        template = SUBJECTS_ES_TU.get(message_key, template)
    if fields:
        try:
            return template.format(**fields)
        except (KeyError, IndexError):
            return template
    return template


# --------------------------------------------------------------------------
# Send-time stamp on the subject line.
#
# THE PROBLEM. Every re-sendable message had a CONSTANT subject, so five
# requests produced five messages titled «Su enlace de acceso» — which every
# mail client threads into one conversation. A threaded reader opens the top
# of the thread, which is the OLDEST message, lands on an expired link, and
# has nothing on screen that distinguishes the live link from the four dead
# ones. Observed 2026-09-06 on a real inbox as a single thread labelled
# «[32] Su enlace de acceso».
#
# THE SHAPE. `<subject> | YYYY-MM-DD HH:MM:SS`, after Anthropic's
# "Your secure link to Claude.ai is here | 2026-09-06 16:23:11". Chosen over
# the alternatives on purpose:
#   * The separator is " | ", not a dash or parentheses: it reads as metadata
#     appended to a title rather than as part of the sentence.
#   * The stamp is LAST, so the subject still starts with the words the reader
#     scans for, and a client that truncates a long subject truncates the
#     stamp rather than the meaning.
#   * ISO-ordered date, 24h clock, no zone suffix: sortable, unambiguous
#     between es-MX and en readers (11/09 vs 09/11), and short. The zone is
#     not printed because it is the reader's own — see `timezone_for`.
#   * Seconds are included: two links requested in the same minute is exactly
#     the case a person hits when the first one seems not to arrive.
#
# THE CLOCK IS READ, NEVER CACHED. `stamp_subject` takes the moment as an
# argument so tests can pin it, and `now_for_timezone` is the only place that
# calls the real clock. A module-level "now" evaluated at import would stamp
# every message in a long-lived process with the time the worker booted.
# --------------------------------------------------------------------------
SUBJECT_STAMP_SEPARATOR = " | "
SUBJECT_STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_for_timezone(timezone_name: Optional[str] = None) -> datetime:
    """The current moment in one IANA zone, read from the real clock.

    Falls back to UTC only when the zone name is unknown to the system tzdata,
    which is a packaging problem rather than a caller error: a subject stamped
    in the wrong zone is still more useful than a message that failed to send.
    """
    try:
        return datetime.now(ZoneInfo(timezone_name or "UTC"))
    except (ZoneInfoNotFoundError, ValueError):
        return datetime.now(timezone.utc)


def stamp_subject(subject: str, moment: Optional[datetime] = None) -> str:
    """Append the send-time stamp to a subject line.

    `moment` is required in practice — callers pass `now_for_timezone(...)` so
    the zone is the reader's — and defaults to UTC-now only so that calling
    this with no clock still produces a stamped subject rather than raising.

    Idempotent by nature of being called once per send; it does NOT try to
    detect an existing stamp, because a subject that legitimately contains
    " | " (none do today) should not silently lose its stamp.
    """
    when = moment if moment is not None else datetime.now(timezone.utc)
    return f"{subject}{SUBJECT_STAMP_SEPARATOR}{when.strftime(SUBJECT_STAMP_FORMAT)}"


# --------------------------------------------------------------------------
# Shared chrome
#
# base.html's header and footer are outside every {% block content %}, so
# localized bodies would otherwise sit inside an English frame. These strings
# are exposed to templates as `t('key')` rather than duplicating base.html.
# --------------------------------------------------------------------------
CHROME: Dict[str, Dict[str, str]] = {
    "en": {
        # The header now reads MADFAM on every message, so the tagline is
        # MADFAM's rather than one platform's.
        "tagline": "Technology, engineered for your operation",
        "rights": "All rights reserved.",
        "powered_by": "Powered by",
        "privacy": "Privacy Policy",
        "terms": "Terms of Service",
        "support": "Support",
        "why_received": "You received this email because you have an account with MADFAM.",
        "location": "Innovaciones MADFAM S.A.S. de C.V. • Cuernavaca, Morelos, Mexico",
        # The name the message signs off with. It is MADFAM for the same reason
        # the header and the From address are: the reader has a relationship
        # with MADFAM and has never heard of the platform underneath. Ten
        # plain-text and HTML templates hard-coded "the Janua Team", so a
        # message arrived under a MADFAM header, from hola@madfam.io, and then
        # signed off as a company the reader does not know — which is the exact
        # confusion the sender work existed to remove, surviving in the part of
        # the email people actually read last.
        "signoff": "The MADFAM Team",
        # Ruling R101 (2026-10-04): system and security mail comes from
        # noreply@madfam.io with a Reply-To on a human inbox, and says so in
        # one line. The Reply-To is what makes the sentence true.
        "automated_notice": "This message is automated; if you reply, a person will answer.",
    },
    "es": {
        "tagline": "Tecnología, diseñada para su operación",
        "signoff": "Equipo MADFAM",
        "rights": "Todos los derechos reservados.",
        # "Con tecnología de" is the standard es-MX rendering of "Powered by".
        # "Impulsado por" reads as marketing; this reads as an attribution.
        "powered_by": "Con tecnología de",
        "privacy": "Aviso de privacidad",
        "terms": "Términos del servicio",
        "support": "Soporte",
        "why_received": "Recibió este correo electrónico porque tiene una cuenta con MADFAM.",
        "location": "Innovaciones MADFAM S.A.S. de C.V. • Cuernavaca, Morelos, México",
        # R101 (2026-10-04). The `tú` copy is the ruling's own sentence; this
        # is its usted register.
        "automated_notice": "Este mensaje es automático; si responde, le atiende una persona.",
    },
}


# --------------------------------------------------------------------------
# Spanish body copy
#
# Prose that ADDRESSES THE READER lives here rather than inline in the `es/`
# templates, because that is the only prose whose wording changes with the
# register. Register-neutral text — a button that reads "Iniciar sesión", a
# field label, a sentence about the product in the third person — stays inline
# in the template on purpose: lifting it here would create two entries to keep
# in sync for a string that is byte-identical in both registers.
#
# The split is enforced, not conventional:
# tests/unit/services/test_email_formality.py scans the visible text of every
# `es/` template for second-person-formal markers and fails if any survive
# outside a `t()` call.
#
# Keys are `<message>.<slot>`; `<message>.txt_<slot>` where the plain-text
# part words or wraps something differently from the HTML part. Embedded "\n"
# reproduces the hand-wrapping the .txt templates already had.
# --------------------------------------------------------------------------
ES_BODY: Dict[str, str] = {
    # -- shared across messages ------------------------------------------
    "common.need_help": "¿Necesita ayuda? Escríbanos a",
    # -- magic_link -------------------------------------------------------
    "magic_link.heading": "Inicie sesión en su portal",
    "magic_link.intro": (
        "Use el siguiente botón para iniciar sesión. No necesita contraseña: "
        "el enlace le da acceso directo."
    ),
    "magic_link.security_notice": (
        "Si usted no solicitó iniciar sesión, puede ignorar este correo electrónico: "
        "el enlace está ligado a su dirección y no hace nada hasta que se abre. "
        "Nunca lo reenvíe, ya que cualquier persona que lo tenga podría entrar a su "
        "cuenta hasta que el enlace expire."
    ),
    "magic_link.button_fallback": "Si el botón no funciona, copie esta dirección en su navegador:",
    "magic_link.txt_intro": "Inicie sesión en su portal con este enlace:",
    "magic_link.txt_security_notice": (
        "Si usted no solicitó iniciar sesión, puede ignorar este correo electrónico. Nunca\n"
        "reenvíe este enlace: cualquier persona que lo tenga podría entrar a su cuenta hasta\n"
        "que expire."
    ),
    # -- password_reset ---------------------------------------------------
    "password_reset.heading": "Restablezca su contraseña",
    "password_reset.intro": (
        "Recibimos una solicitud para restablecer la contraseña de su cuenta de Janua. "
        "Si usted hizo esta solicitud, use el código que aparece abajo o haga clic en el "
        "botón para crear una contraseña nueva."
    ),
    "password_reset.code_label": "Su código para restablecer la contraseña:",
    "password_reset.security_notice": (
        "Si usted no solicitó restablecer su contraseña, es posible que alguien esté "
        "intentando acceder a su cuenta. Le recomendamos:"
    ),
    "password_reset.tip_change_password": "Cambiar su contraseña de inmediato",
    "password_reset.tip_review_activity": "Revisar la actividad reciente de su cuenta",
    "password_reset.link_lifetime": (
        "Por seguridad, este enlace expira en 30 minutos. Si necesita un enlace nuevo, "
        "puede solicitarlo desde la página de inicio de sesión."
    ),
    "password_reset.txt_intro": (
        "Recibimos una solicitud para restablecer la contraseña de su cuenta de Janua."
    ),
    "password_reset.txt_cta": "Restablezca su contraseña con este enlace:",
    "password_reset.txt_ignore": (
        "Si usted no solicitó restablecer su contraseña, puede ignorar este correo\n"
        "electrónico. Su contraseña no se modificará."
    ),
    # -- verification -----------------------------------------------------
    "verification.heading": "Verifique su correo electrónico",
    "verification.intro": (
        "Le damos la bienvenida a Janua. Verifique su dirección de correo electrónico "
        "para terminar de configurar su cuenta y acceder a todas las funciones."
    ),
    "verification.code_label": "Su código de verificación:",
    "verification.or_click": (
        "O haga clic en el siguiente botón para verificar su correo electrónico:"
    ),
    "verification.why_title": "¿Por qué verificar su correo electrónico?",
    "verification.why_body": (
        "La verificación nos ayuda a proteger su cuenta y habilita funciones importantes "
        "como la recuperación de contraseña y las notificaciones de seguridad."
    ),
    "verification.not_you": (
        "Si usted no creó una cuenta en Janua, puede ignorar este correo electrónico."
    ),
    "verification.txt_intro": (
        "Le damos la bienvenida a Janua. Verifique su dirección de correo electrónico para\n"
        "terminar de configurar su cuenta y acceder a todas las funciones."
    ),
    "verification.txt_cta": "Verifique su correo electrónico con este enlace:",
    "verification.txt_why_body": (
        "La verificación nos ayuda a proteger su cuenta y habilita funciones importantes\n"
        "como la recuperación de contraseña y las notificaciones de seguridad."
    ),
    # -- welcome ----------------------------------------------------------
    "welcome.heading": "Le damos la bienvenida a Janua 🎉",
    "welcome.intro": (
        "Su cuenta de Janua se creó correctamente. Ya forma parte de una plataforma de "
        "identidad segura en la que confían organizaciones de todo el mundo."
    ),
    "welcome.account_details": "Datos de su cuenta:",
    "welcome.steps_intro": "Le sugerimos empezar por aquí para aprovechar Janua al máximo:",
    "welcome.step_mfa_title": "Active la autenticación de dos factores",
    "welcome.step_mfa_body": "Añada una capa adicional de seguridad a su cuenta",
    "welcome.step_org_title": "Configure su organización",
    "welcome.step_org_body": "Invite a su equipo y defina roles y permisos",
    "welcome.step_integrate_title": "Intégrelo con su aplicación",
    "welcome.step_integrate_body": (
        "Use nuestros SDK para añadir autenticación a sus aplicaciones"
    ),
    "welcome.step_passkeys_title": "Habilite las llaves de acceso",
    "welcome.step_passkeys_body": "Configure el acceso sin contraseña para mayor seguridad",
    "welcome.help_title": "¿Necesita ayuda?",
    "welcome.help_body": "Nuestro equipo está a sus órdenes:",
    "welcome.help_support": "Reciba ayuda de nuestro equipo",
    "welcome.thanks": (
        "Gracias por elegir Janua. Nos da gusto acompañarle en la seguridad de su plataforma."
    ),
    "welcome.txt_intro": (
        "Le damos la bienvenida a Janua. Su cuenta se creó y se verificó correctamente."
    ),
    "welcome.txt_dashboard_cta": "Comience por su panel:",
    "welcome.txt_capabilities": "Lo que puede hacer con Janua:",
    "welcome.txt_capability_identity": "Administrar su identidad digital",
    "welcome.txt_capability_privacy": "Controlar sus datos y su privacidad",
    "welcome.txt_help": (
        "¿Necesita ayuda para empezar? Consulte nuestra documentación o escríbanos a"
    ),
    "welcome.txt_closing": "Nos da mucho gusto tenerle con nosotros.",
    # -- invitation -------------------------------------------------------
    "invitation.heading": "Le invitaron a colaborar",
    # Sentence fragment on purpose: the inviter and organization names are
    # wrapped in <strong> in the HTML, so the sentence cannot be one string
    # without either escaping the markup or marking user-supplied names
    # |safe. The fragment is grammatically stable in both registers.
    "invitation.invited_to_join": "le invitó a unirse a",
    "invitation.txt_invited_to_join": "Le invitaron a unirse a",
    "invitation.accept_before": "Le pedimos aceptarla antes de esa fecha.",
    "invitation.button_fallback": (
        "Si el botón anterior no funciona, copie y pegue esta dirección en su navegador:"
    ),
    "invitation.questions": "¿Tiene alguna duda? Escriba a",
    "invitation.txt_open_link": "Abra el siguiente enlace para aceptar su invitación:",
    "invitation.txt_questions": "¿Tiene alguna duda? Escríbanos a",
}

# Every Spanish string a template can ask for, in the USTED register. Built
# from CHROME so the shared frame and the body copy resolve through one map.
ES_STRINGS: Dict[str, str] = {**CHROME["es"], **ES_BODY}

# --------------------------------------------------------------------------
# `tú` variants.
#
# ONLY the keys whose wording actually differs. A key absent from here falls
# back to its usted string at render time, so a missing variant degrades to
# the safe register rather than to a blank paragraph — but it cannot be
# missing by accident: ES_STRINGS must partition exactly into
# `set(ES_TU) | ES_REGISTER_NEUTRAL`, and the test fails on any key that is
# in neither.
#
# NOTE ON PRONOUN DROPPING. Where the usted copy spells out the subject
# pronoun ("Si USTED no solicitó..."), the tú copy drops it ("Si no
# solicitaste..."). This is not an oversight. In usted the pronoun does real
# work — "solicitó" alone is also third person, so without it the sentence
# could be read as being about someone else. "Solicitaste" is unambiguous, and
# an explicit "tú" there reads contrastive/emphatic, as if arguing with the
# reader. Dropping it is what a Mexican writer would do.
# --------------------------------------------------------------------------
ES_TU: Dict[str, str] = {
    # -- chrome -----------------------------------------------------------
    # The frame is MADFAM's in BOTH registers. `why_received` said "una cuenta
    # en Janua" here while the usted copy already said MADFAM — which would
    # have shown the brand this branch exists to stop showing to exactly the
    # readers who asked for the friendlier register.
    #
    # `tagline` was register-neutral while it read "Plataforma de identidad
    # segura", a sentence about the product. It now addresses the reader's
    # operation ("su"/"tu"), so it is register-sensitive and moved out of
    # ES_REGISTER_NEUTRAL.
    "tagline": "Tecnología, diseñada para tu operación",
    "why_received": "Recibiste este correo electrónico porque tienes una cuenta con MADFAM.",
    # Ruling R101 (2026-10-04), verbatim.
    "automated_notice": "Este mensaje es automático; si respondes, te atiende una persona.",
    # -- shared -----------------------------------------------------------
    "common.need_help": "¿Necesitas ayuda? Escríbenos a",
    # -- magic_link -------------------------------------------------------
    "magic_link.heading": "Inicia sesión en tu portal",
    "magic_link.intro": (
        "Usa el siguiente botón para iniciar sesión. No necesitas contraseña: "
        "el enlace te da acceso directo."
    ),
    "magic_link.security_notice": (
        "Si no solicitaste iniciar sesión, puedes ignorar este correo electrónico: "
        "el enlace está ligado a tu dirección y no hace nada hasta que se abre. "
        "Nunca lo reenvíes, ya que cualquier persona que lo tenga podría entrar a tu "
        "cuenta hasta que el enlace expire."
    ),
    "magic_link.button_fallback": "Si el botón no funciona, copia esta dirección en tu navegador:",
    "magic_link.txt_intro": "Inicia sesión en tu portal con este enlace:",
    "magic_link.txt_security_notice": (
        "Si no solicitaste iniciar sesión, puedes ignorar este correo electrónico. Nunca\n"
        "reenvíes este enlace: cualquier persona que lo tenga podría entrar a tu cuenta hasta\n"
        "que expire."
    ),
    # -- password_reset ---------------------------------------------------
    "password_reset.heading": "Restablece tu contraseña",
    "password_reset.intro": (
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta de Janua. "
        "Si hiciste esta solicitud, usa el código que aparece abajo o haz clic en el "
        "botón para crear una contraseña nueva."
    ),
    "password_reset.code_label": "Tu código para restablecer la contraseña:",
    "password_reset.security_notice": (
        "Si no solicitaste restablecer tu contraseña, es posible que alguien esté "
        "intentando acceder a tu cuenta. Te recomendamos:"
    ),
    "password_reset.tip_change_password": "Cambiar tu contraseña de inmediato",
    "password_reset.tip_review_activity": "Revisar la actividad reciente de tu cuenta",
    "password_reset.link_lifetime": (
        "Por seguridad, este enlace expira en 30 minutos. Si necesitas un enlace nuevo, "
        "puedes solicitarlo desde la página de inicio de sesión."
    ),
    "password_reset.txt_intro": (
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta de Janua."
    ),
    "password_reset.txt_cta": "Restablece tu contraseña con este enlace:",
    "password_reset.txt_ignore": (
        "Si no solicitaste restablecer tu contraseña, puedes ignorar este correo\n"
        "electrónico. Tu contraseña no se modificará."
    ),
    # -- verification -----------------------------------------------------
    "verification.heading": "Verifica tu correo electrónico",
    "verification.intro": (
        "Te damos la bienvenida a Janua. Verifica tu dirección de correo electrónico "
        "para terminar de configurar tu cuenta y acceder a todas las funciones."
    ),
    "verification.code_label": "Tu código de verificación:",
    "verification.or_click": (
        "O haz clic en el siguiente botón para verificar tu correo electrónico:"
    ),
    "verification.why_title": "¿Por qué verificar tu correo electrónico?",
    "verification.why_body": (
        "La verificación nos ayuda a proteger tu cuenta y habilita funciones importantes "
        "como la recuperación de contraseña y las notificaciones de seguridad."
    ),
    "verification.not_you": (
        "Si no creaste una cuenta en Janua, puedes ignorar este correo electrónico."
    ),
    "verification.txt_intro": (
        "Te damos la bienvenida a Janua. Verifica tu dirección de correo electrónico para\n"
        "terminar de configurar tu cuenta y acceder a todas las funciones."
    ),
    "verification.txt_cta": "Verifica tu correo electrónico con este enlace:",
    "verification.txt_why_body": (
        "La verificación nos ayuda a proteger tu cuenta y habilita funciones importantes\n"
        "como la recuperación de contraseña y las notificaciones de seguridad."
    ),
    # -- welcome ----------------------------------------------------------
    "welcome.heading": "Te damos la bienvenida a Janua 🎉",
    "welcome.intro": (
        "Tu cuenta de Janua se creó correctamente. Ya formas parte de una plataforma de "
        "identidad segura en la que confían organizaciones de todo el mundo."
    ),
    "welcome.account_details": "Datos de tu cuenta:",
    "welcome.steps_intro": "Te sugerimos empezar por aquí para aprovechar Janua al máximo:",
    "welcome.step_mfa_title": "Activa la autenticación de dos factores",
    "welcome.step_mfa_body": "Añade una capa adicional de seguridad a tu cuenta",
    "welcome.step_org_title": "Configura tu organización",
    "welcome.step_org_body": "Invita a tu equipo y define roles y permisos",
    "welcome.step_integrate_title": "Intégralo con tu aplicación",
    "welcome.step_integrate_body": "Usa nuestros SDK para añadir autenticación a tus aplicaciones",
    "welcome.step_passkeys_title": "Habilita las llaves de acceso",
    "welcome.step_passkeys_body": "Configura el acceso sin contraseña para mayor seguridad",
    "welcome.help_title": "¿Necesitas ayuda?",
    # "a tus órdenes" is idiomatic in Mexico in exactly the same courtesy
    # slot as "a sus órdenes"; it is not a literal-but-odd calque.
    "welcome.help_body": "Nuestro equipo está a tus órdenes:",
    "welcome.help_support": "Recibe ayuda de nuestro equipo",
    "welcome.thanks": (
        "Gracias por elegir Janua. Nos da gusto acompañarte en la seguridad de tu plataforma."
    ),
    "welcome.txt_intro": (
        "Te damos la bienvenida a Janua. Tu cuenta se creó y se verificó correctamente."
    ),
    "welcome.txt_dashboard_cta": "Comienza por tu panel:",
    "welcome.txt_capabilities": "Lo que puedes hacer con Janua:",
    "welcome.txt_capability_identity": "Administrar tu identidad digital",
    "welcome.txt_capability_privacy": "Controlar tus datos y tu privacidad",
    "welcome.txt_help": (
        "¿Necesitas ayuda para empezar? Consulta nuestra documentación o escríbenos a"
    ),
    "welcome.txt_closing": "Nos da mucho gusto tenerte con nosotros.",
    # -- invitation -------------------------------------------------------
    "invitation.heading": "Te invitaron a colaborar",
    "invitation.invited_to_join": "te invitó a unirse a",
    "invitation.txt_invited_to_join": "Te invitaron a unirse a",
    "invitation.accept_before": "Te pedimos aceptarla antes de esa fecha.",
    "invitation.button_fallback": (
        "Si el botón anterior no funciona, copia y pega esta dirección en tu navegador:"
    ),
    "invitation.questions": "¿Tienes alguna duda? Escribe a",
    "invitation.txt_open_link": "Abre el siguiente enlace para aceptar tu invitación:",
    "invitation.txt_questions": "¿Tienes alguna duda? Escríbenos a",
}

# --------------------------------------------------------------------------
# Register-neutral Spanish keys.
#
# These are byte-identical in `tú` and `usted` — they name a thing rather than
# address the reader — so they are DELIBERATELY NOT duplicated into ES_TU.
# Duplicating them would mean two strings to keep in sync with no
# reader-visible difference between them.
#
# This set is not documentation: it is half of the partition the tests check.
# Adding a Spanish key without either a `tú` variant or a line here fails
# tests/unit/services/test_email_formality.py, which is the point — a
# register-sensitive string cannot reach a reader unreviewed.
# --------------------------------------------------------------------------
ES_REGISTER_NEUTRAL: Set[str] = {
    # `tagline` is NOT here any more: it now reads "diseñada para su operación",
    # which addresses the reader, so it lives in ES_TU with both registers.
    "rights",  # "Todos los derechos reservados." — boilerplate, no addressee
    "powered_by",  # "Con tecnología de" — an attribution, no addressee
    "privacy",  # "Aviso de privacidad" — the name of a document
    "terms",  # "Términos del servicio" — the name of a document
    "support",  # "Soporte" — a noun
    "location",  # a postal address
    # "Equipo MADFAM" — the sender's own name. It has no addressee, so it is
    # byte-identical in `tú` and `usted` and must NOT be duplicated into ES_TU.
    "signoff",
}


def chrome_string(key: str, locale: Optional[str] = None, formality: Optional[str] = None) -> str:
    """Look up a localized string by key: shared chrome or Spanish body copy.

    Defaults to English when no locale is in scope so that rendering a
    template directly — without going through the service, as the template
    guards in the test suite do — produces exactly the frame it produced
    before localization existed.

    For Spanish, `formality` selects the register. An absent `tú` variant
    falls back to the usted string, NEVER to English: a Spanish reader who
    asked for `tú` and hits an untranslated key should get slightly formal
    Spanish, not a language they did not ask for.
    """
    resolved = normalize_locale(locale) or FALLBACK_LOCALE
    if resolved == "es":
        if normalize_formality(formality) == FORMALITY_TU:
            informal = ES_TU.get(key)
            if informal is not None:
                return informal
        formal = ES_STRINGS.get(key)
        if formal is not None:
            return formal
    return CHROME.get(resolved, CHROME[FALLBACK_LOCALE]).get(
        key, CHROME[FALLBACK_LOCALE].get(key, "")
    )


def append_automated_notice(
    text: str, locale: Optional[str] = None, formality: Optional[str] = None
) -> str:
    """A plain-text body with the R101 automated-mail line after its sign-off.

    The HTML frame renders the same line in base.html's footer. The plain-text
    templates have no shared frame, so the line is appended here, once, for
    every automated message rather than copied into each `.txt` file.
    """
    notice = chrome_string("automated_notice", locale, formality)
    if not text or not notice:
        return text
    return f"{text.rstrip()}\n\n{notice}"


def html_lang(locale: Optional[str] = None) -> str:
    """The `lang` attribute for <html>, so screen readers and clients that
    offer translation see the real language of the message."""
    resolved = normalize_locale(locale) or FALLBACK_LOCALE
    return "es-MX" if resolved == "es" else "en"


@pass_context
def _chrome_global(ctx, key: str) -> str:
    """`t('key')` inside a template: any localized string, by key.

    Context-aware so base.html renders in the same language as the body
    without every template forwarding the locale explicitly. With no locale in
    context — a template rendered directly rather than through a service —
    this yields the English frame the templates had before localization.

    The register is read from context the same way, so a template author picks
    a key and never picks a register; `formality` absent means `usted`.
    """
    return chrome_string(key, ctx.get("locale"), ctx.get("formality"))


@pass_context
def _lang_global(ctx) -> str:
    """`lang()` inside a template: the <html lang> attribute value."""
    return html_lang(ctx.get("locale"))


def install_template_globals(env: Environment) -> Environment:
    """Register the globals `templates/email/base.html` depends on.

    base.html calls `t()` and `lang()`, and Jinja raises on calling an
    undefined name — so any environment that loads these templates must have
    them. Three services build their own environment over this same
    directory; routing them all through `build_email_environment` keeps that
    from being something a fourth one can forget.
    """
    env.globals["t"] = _chrome_global
    env.globals["lang"] = _lang_global
    return env


def build_email_environment(template_dir: Any) -> Environment:
    """The Jinja environment for `templates/email`, globals included.

    Autoescape by EXTENSION, not unconditionally: `autoescape=True` was
    HTML-escaping the plain-text bodies too, so the .txt part of every email
    carried `&amp;` inside its URLs — and a recipient copying the "if the
    button doesn't work" address out of a text-mode client pasted a link
    whose query string literally began `amp;token=` (found 2026-08-15 by the
    magic-link destination tests). Entities belong in markup only.
    """
    return install_template_globals(
        Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(
                enabled_extensions=("html", "htm", "xml"), default=False
            ),
        )
    )
