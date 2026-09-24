"""Per-tenant BODY branding for transactional email.

This is a Phase-1 *refinement*, not Phase 2. See `docs/EMAIL_SENDER_POLICY.md`.

WHAT THIS DOES AND, JUST AS IMPORTANTLY, WHAT IT DOES NOT. Phase 1 keeps one
sender for every message — `MADFAM <hola@madfam.io>` — because a bespoke client
meets several MADFAM platforms over an engagement and a sender that changes per
product reads as several vendors. That does not have to mean every BODY reads
"MADFAM" as well: a client who signs into their own workspace should see their
own name at the top of the sign-in mail, with MADFAM credited underneath. This
module resolves the header name and header palette that vary per tenant, and
NOTHING it returns is ever used to build the From line. `resolve_sender` in
`email_service.py` stays the single, deliberately-unused Phase-2 seam.

    From line   -> ALWAYS MADFAM (resolve_sender, untouched)
    Body header -> the tenant's name and palette (this module)
    Body footer -> "Con tecnología de <platform>" — the platform credited, and
                   for a client tenant the platform IS MADFAM, so the footer
                   reads "Con tecnología de MADFAM" (es) / "Powered by MADFAM".

WHY THE SIGNAL IS THE REDIRECT HOST, NOT A DB LOOKUP. The auth mailer runs
inside FastAPI BackgroundTasks, which hold no DB session — `EmailService()` is
instantiated per task with neither Redis nor a DB handle. The tenant signal
that IS available at send time is the same one `resolve_sender` was built to
read: the magic-link `redirect_url`, whose host names the product the recipient
is being sent back to. That is why branding is keyed on host here rather than on
`WhiteLabelConfiguration` (which exists, is keyed by `organization_id`, and is
the right home once a send path carries a session — a caller that already knows
the org id can pass it via `org_id` and it is honored first).

WHY THIS IS NOT "A GIANT HOST MAP". It is one tenant. The registry is CTM's
canonical org id plus the two hosts CTM users actually sign in through
(crea-map, kalya). A second client is a second entry, added the day their
branding is agreed — not a config surface for every product.

TWO MORE THINGS ARE KEYED ON THE SAME SIGNAL (2026-09-06): the VOICE the mail
speaks in (`tú` / `usted`) and the CLOCK its subject line is stamped with. Both
are properties of the product the reader is being sent back to, and both were
previously either fixed or absent — so both belong on the same host key rather
than on three parallel registries. See `default_formality_for` and
`timezone_for`.
"""

from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from app.services.email_i18n import FORMALITY_TU, FORMALITY_USTED

# --------------------------------------------------------------------------
# The MADFAM default. Byte-for-byte the header base.html rendered before this
# module existed: the blue gradient, white text, the "MADFAM" wordmark. Every
# caller that resolves to no tenant gets exactly this, so an unknown or absent
# signal is a no-op — the regression tests pin that the default render is
# identical to today's.
# --------------------------------------------------------------------------
MADFAM_BRANDING: Dict[str, str] = {
    # `header_name` drives the wordmark in base.html's header. `platform_name`
    # / `platform_url` drive the "Con tecnología de" footer, and default to
    # Janua exactly as base.html did before (the footer credits the platform;
    # for a MADFAM-branded message the platform underneath is Janua).
    "header_name": "MADFAM",
    "header_bg": "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
    "header_fg": "#ffffff",
    "platform_name": "Janua",
    "platform_url": "https://janua.dev",
    # `header_logo_url` / `footer_logo_url` are the hotlinked brand marks. EMPTY
    # for the MADFAM default: a MADFAM-branded message keeps its INLINE base64
    # wordmark (base.html, gated on header_name == 'MADFAM') and needs no footer
    # mark — the header already carries the brand. A client tenant sets these to
    # the client's header mark and MADFAM's footer mark. Empty string, not a
    # missing key, so the template's `if` is a plain truthiness test.
    "header_logo_url": "",
    "footer_logo_url": "",
}

# --------------------------------------------------------------------------
# Crea Tu Mundo Autismo (CTM). Its canonical Janua org and the hosts its users
# sign in through. Header reads the client's name in the client's palette and
# carries the client's LOGO; footer credits MADFAM with the MADFAM mark (the
# platform underneath a client tenant IS MADFAM, so `platform_name` is MADFAM
# here, not Janua).
#
# CTM palette: deep royal indigo on a warm cream ground. The header logo is
# the gold Crea mark with the indigo header ground BAKED IN (flat RGB PNG, no
# alpha), the same asset the kalya booking emails carry and which is verified
# to render in real inboxes (Proton, 2026-08-29). The client's own name in
# brand colors remains the `<img>` alt text, so with images OFF the header
# still reads "Crea Tu Mundo" — the logo is an enhancement over the
# typographic frame, not a replacement for it.
#
# WHY HOTLINKED, NOT INLINE. The MADFAM default header ships an inline base64
# PNG (blocked-image-proof). CTM's marks are hotlinked from the MAP's canonical
# host map.creatumundo.mx instead, deliberately: they are ALREADY LIVE and public there, they are the
# byte-identical assets the kalya emails use (one source of truth for the CTM
# brand across both mailers), and they proved to render in Proton. Keeping the
# alt text as the brand name preserves the images-off case. The URLs name the
# canonical host, never the crea-map.madfam.io alias: the alias answers 301,
# and mail image proxies do not reliably follow redirects.
# --------------------------------------------------------------------------
CTM_ORG_ID = "e6cbd51d-8329-4c4e-8c74-aba643ab4575"

CTM_BRANDING: Dict[str, str] = {
    "header_name": "Crea Tu Mundo",
    # Deep royal indigo, flat (no gradient) — reads as the brand, not as a
    # second MADFAM. `header_fg` is the warm-cream text on that indigo ground.
    "header_bg": "#1a2a8f",
    "header_fg": "#fdf6e3",
    # The footer credits the platform, which for a client tenant is MADFAM.
    "platform_name": "MADFAM",
    "platform_url": "https://madfam.io",
    # The gold Crea mark on the indigo header ground (60px, flat RGB, ~10KB),
    # and the MADFAM mark for the "Con tecnología de MADFAM" footer (28px).
    # Same public assets as the kalya booking emails (crea-map origin).
    "header_logo_url": "https://map.creatumundo.mx/crea-logo-email.png",
    "footer_logo_url": "https://map.creatumundo.mx/madfam-logo.png",
}

# Hosts whose sign-in redirect identifies a CTM user. Matched on exact host or
# a subdomain suffix, so both `crea-map.madfam.io` and a bare `kalya.app`
# resolve. NOT a catch-all: `madfam.io` itself is deliberately absent — it is
# MADFAM's own host and must keep MADFAM branding.
CTM_HOSTS: Tuple[str, ...] = (
    # Legacy 301 alias of map.creatumundo.mx; kept while the alias lives so a
    # redirect that still names it keeps CTM branding.
    "crea-map.madfam.io",
    "ensayo-map.madfam.io",
    "kalya.app",
    # 2026-09-06: the client's own brand zone. Dot-boundary suffix matching
    # covers `map.creatumundo.mx` and `erp.creatumundo.mx` (the brand hosts
    # that will serve the MAP and the ERP portal) with one entry, and never
    # `notcreatumundo.mx`.
    "creatumundo.mx",
)


def _host_matches(host: str, pattern: str) -> bool:
    """True when `host` is `pattern` or a subdomain of it.

    Suffix match on a dot boundary so `kalya.app` matches `kalya.app` and
    `app.kalya.app` but never `evilkalya.app`.
    """
    host = host.lower().strip()
    pattern = pattern.lower().strip()
    return host == pattern or host.endswith("." + pattern)


def _tenant_for_host(host: Optional[str]) -> Optional[str]:
    """Map a redirect host to a tenant key, or None for MADFAM default."""
    if not host:
        return None
    for pattern in CTM_HOSTS:
        if _host_matches(host, pattern):
            return "ctm"
    return None


def _tenant_for_org_id(org_id: Optional[str]) -> Optional[str]:
    """Map an organization id to a tenant key, or None for MADFAM default."""
    if not org_id:
        return None
    if str(org_id).strip().lower() == CTM_ORG_ID:
        return "ctm"
    return None


_TENANT_BRANDING: Dict[str, Dict[str, str]] = {
    "ctm": CTM_BRANDING,
}


def resolve_branding(
    redirect_url: Optional[str] = None,
    org_id: Optional[Any] = None,
) -> Dict[str, str]:
    """The BODY branding context for one message.

    Returns a plain dict merged into the template context: `header_name`,
    `header_bg`, `header_fg` (the header wordmark and palette) plus
    `platform_name` / `platform_url` (the "Con tecnología de" footer). Always a
    complete set — a template never has to guard for a missing key.

    Resolution order, highest precedence first:

      1. `org_id` — a caller that already knows the tenant (a send path with a
         session, or the template endpoint if a caller passes one) is
         authoritative. This is where `WhiteLabelConfiguration` would be read
         from once a mailer carries a DB session; today it is the static
         registry.
      2. `redirect_url` host — the signal the auth mailer actually has at send
         time, the same host `resolve_sender` reads.
      3. Neither, or an unrecognized value -> MADFAM. Unknown tenants get
         today's exact MADFAM frame; this is a no-op for every existing caller.

    NEVER used to build the From line. Body branding only. See module docstring
    and `docs/EMAIL_SENDER_POLICY.md`.
    """
    tenant = _tenant_for_org_id(org_id)
    if tenant is None and redirect_url:
        host = urlparse(redirect_url).hostname
        tenant = _tenant_for_host(host)
    if tenant is None:
        return dict(MADFAM_BRANDING)
    return {**MADFAM_BRANDING, **_TENANT_BRANDING[tenant]}


def resolve_tenant(
    redirect_url: Optional[str] = None,
    org_id: Optional[Any] = None,
) -> Optional[str]:
    """The tenant key for one message, or None for the MADFAM default.

    Same precedence as `resolve_branding` (explicit org id, then the redirect
    host) — factored out because branding is no longer the only thing keyed on
    it: the voice and the clock are too, and three copies of this walk would
    be three chances for them to disagree about who the reader is.
    """
    tenant = _tenant_for_org_id(org_id)
    if tenant is None and redirect_url:
        tenant = _tenant_for_host(urlparse(redirect_url).hostname)
    return tenant


# --------------------------------------------------------------------------
# The voice each product speaks in.
#
# WHY THIS IS PER-PRODUCT AND NOT PER-DEPLOYMENT. `resolve_formality` in
# email_i18n deliberately has no deployment-wide tier: register is a property
# of the reader. But most readers have never been asked, so their user row is
# NULL — and NULL used to mean the global `usted` default for everyone. The
# result, found live 2026-09-06: crea-map's own login page says «Escribe el
# correo… te llega un enlace y con un clic estás dentro» (tú), and the mail
# janua sent for that page opened «Inicie sesión en su portal · Use el
# siguiente botón» (usted). One journey, two voices, in the two screens a
# person sees back to back.
#
# So this table is NOT a fourth opinion about the reader. It is what the
# REQUESTING PRODUCT already sounds like, used only when the reader has not
# said otherwise — a better guess than a global constant, and strictly below
# both an explicit request value and the user's own stored choice. See
# `resolve_formality_for_request` in email_i18n for the full precedence.
#
# CTM's products (crea-map, kalya, the creatumundo.mx brand hosts) address
# families and clinicians as `tú` throughout their UI, so their mail does too.
# Everything else — MADFAM's own hosts, the nauta client portal, any host not
# listed — stays `usted`: these are B2B/professional surfaces, and formal is
# the cheaper error for a first contact (email_i18n, DEFAULT_FORMALITY).
# --------------------------------------------------------------------------
_TENANT_FORMALITY: Dict[str, str] = {
    "ctm": FORMALITY_TU,
}

# The register for a host that resolves to no tenant. Same value as
# email_i18n.DEFAULT_FORMALITY and for the same reason; named separately so a
# future tenant table entry reads as an override of a stated default rather
# than of an implicit one.
DEFAULT_TENANT_FORMALITY = FORMALITY_USTED


def default_formality_for(
    redirect_url: Optional[str] = None,
    org_id: Optional[Any] = None,
) -> str:
    """The register the REQUESTING PRODUCT speaks in.

    The lowest-but-one tier of the magic-link precedence chain: consulted only
    when neither the request nor the user row named a register. Never None —
    an unknown host is `usted`, which is exactly what it rendered before this
    table existed.
    """
    tenant = resolve_tenant(redirect_url=redirect_url, org_id=org_id)
    if tenant is None:
        return DEFAULT_TENANT_FORMALITY
    return _TENANT_FORMALITY.get(tenant, DEFAULT_TENANT_FORMALITY)


# --------------------------------------------------------------------------
# The clock each product's subject line is stamped with.
#
# WHY THIS EXISTS AT ALL. Every re-sendable transactional email carried a
# CONSTANT subject: five requests produced five messages all titled «Su enlace
# de acceso», which mail clients thread together. A person with a threaded
# inbox opens the top of the thread — which is the OLDEST message — and lands
# on an expired link, over and over, with nothing on screen to tell them which
# of the five is the live one. (Observed 2026-09-06 on the technical account's
# Proton inbox: one thread, «[32] Su enlace de acceso».) A send-time stamp in
# the subject makes each request its own message and makes "the newest one"
# something a human can read rather than guess.
#
# WHY A ZONE PER TENANT RATHER THAN UTC. The stamp is only useful if the
# reader can compare it to their own wall clock without arithmetic. UTC would
# read as six hours in the future to every Mexican reader and would make the
# newest link look like it had not arrived yet. There was no timezone notion
# anywhere in this codebase before (verified: no ZoneInfo/pytz import in
# apps/api/app), so this table is the first one — deliberately small, keyed on
# the same host signal as everything else here, and defaulting to CDMX because
# that is MADFAM's operating timezone and every current reader is in it.
# --------------------------------------------------------------------------
_TENANT_TIMEZONE: Dict[str, str] = {
    # CTM operates from Mexico City. Same zone as the MADFAM default today;
    # named explicitly so a future tenant elsewhere is one line, not a rewrite.
    "ctm": "America/Mexico_City",
}

# MADFAM's operating timezone. See the ecosystem rule that ALL human-facing
# times are CDMX: a stamp in any other zone is a stamp the reader has to
# convert, which defeats the point of putting it in front of them.
DEFAULT_TIMEZONE = "America/Mexico_City"


def timezone_for(
    redirect_url: Optional[str] = None,
    org_id: Optional[Any] = None,
) -> str:
    """The IANA zone name to stamp this message's subject in.

    Always a real zone name, never None: an unknown host gets CDMX, which is
    correct for every reader this platform has today and is the zone the whole
    ecosystem states its human-facing times in.
    """
    tenant = resolve_tenant(redirect_url=redirect_url, org_id=org_id)
    if tenant is None:
        return DEFAULT_TIMEZONE
    return _TENANT_TIMEZONE.get(tenant, DEFAULT_TIMEZONE)
