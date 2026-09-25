"""Tenant sender BINDINGS: who a message comes from, on whose account.

This is the third and last layer of the transactional-mail tenant stack. Read
the other two first — they are the thing this generalises, not replaces:

    email_branding.py   what the BODY looks like   (#601, header/palette/voice/clock)
    email_sender.py     what the FROM line says    (#603, resolve_sender + verified gate)
    sender_binding.py   whose ACCOUNT sends it     (this module)

WHY A THIRD LAYER RATHER THAN MORE FIELDS ON THE SECOND. `email_sender` answers
"which address goes on the envelope", and it answers it well. It cannot answer
two questions the owner asked on 2026-09-06:

  1. "This type of treatment should be left exclusively for our vCTO clients,
     where we have full operational control."  -> a branded From is now a
     PRIVILEGE that has to be checked, not a property of a host.
  2. "We should allow mechanisms so that CTM and any other vCTO client can
     easily move to their own Resend (or preferred provider) account."  -> the
     From line and the ACCOUNT that sends it are separable, and today they are
     welded together: `resend.api_key = settings.RESEND_API_KEY` is set once at
     ResendEmailService construction, so every tenant sends on MADFAM's account.

Both are properties of the TENANT, not of the address, so they belong on one
record per tenant rather than as two more parallel dicts keyed on host. That
record is `SenderBinding` below, and `email_sender.sender_for` now resolves
through it.

WHAT A BINDING IS

    SenderBinding(
        tenant="ctm",                        # the key the other two modules use
        display_name="Crea Tu Mundo",        # the From display name
        from_address="hola@creatumundo.mx",  # the From address
        reply_to="hola@creatumundo.mx",      # where replies land
        provider=PROVIDER_RESEND,            # resend | smtp
        account=ACCOUNT_MADFAM,              # madfam | tenant
        credential_ref="RESEND_API_KEY",     # a NAME, never a value
        verified_domains=("creatumundo.mx",),
    )

`credential_ref` is the whole reason portability is a config change rather than
a code change. It is an env var name or a Vault path — never a secret. Nothing
in this module reads a credential; `resolve_credential` in
`sender_credentials.py` does that at send time, and it is the only place that
does. A binding is therefore safe to log, safe to diff in a PR, and safe to
print from an operator script.

WHY A CODE TABLE AND NOT A DB TABLE (YET)

Same constraint that shaped `email_branding`, and it has not moved: the auth
mailer runs inside FastAPI BackgroundTasks with NO DB session. `EmailService()`
is constructed per task with neither Redis nor a DB handle, so a binding read
from a table would be unreachable at exactly the moment the From line is built.
A DB-backed binding is the right end state once a mailer carries a session (the
`WhiteLabelConfiguration` table is where it would live, keyed by
organization_id), and `resolve_binding` is deliberately shaped as a pure
function of (tenant) so that swapping the store underneath it is one function
body. No Alembic migration is part of this change.

THE GATE IS NOT IN THIS MODULE. A binding says what a tenant's branded sender
WOULD be. Whether the tenant is ALLOWED to use it is `sender_policy.py` — see
that module for why the vCTO check is janua's own entitlement and not a call to
nauta. Keeping "what" and "may" apart is what lets the gate fail closed without
the binding table having to know anything about tiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit

from app.services.email_branding import CTM_HOSTS, CTM_ORG_ID, _host_matches

# --------------------------------------------------------------------------
# Providers and accounts.
#
# `provider` is HOW a message leaves (which API/protocol). `account` is WHOSE
# credential pays for it. They are independent: a tenant can be on Resend under
# MADFAM's account (today), on Resend under their own account (after a switch),
# or on their own SMTP relay — three states, two orthogonal fields, no code
# branch per combination.
# --------------------------------------------------------------------------
PROVIDER_RESEND = "resend"
PROVIDER_SMTP = "smtp"

#: Every provider this module will emit. A binding naming anything else is a
#: configuration error and is rejected at import by `_validate_registry`,
#: because the alternative is discovering it at send time on a sign-in link.
SUPPORTED_PROVIDERS: Tuple[str, ...] = (PROVIDER_RESEND, PROVIDER_SMTP)

#: The message is sent on MADFAM's own provider account. The default, and the
#: only state that exists before a tenant runs the switch script.
ACCOUNT_MADFAM = "madfam"

#: The message is sent on the TENANT's provider account, with the tenant's own
#: credential. This is what "move to their own Resend account" means, and it is
#: a one-field change on the binding plus a Vault write — see
#: `scripts/sender_binding_switch.py`.
ACCOUNT_TENANT = "tenant"

SUPPORTED_ACCOUNTS: Tuple[str, ...] = (ACCOUNT_MADFAM, ACCOUNT_TENANT)

#: The env var holding MADFAM's own Resend key. Named here rather than read:
#: this module never touches a credential VALUE. See `sender_credentials.py`.
MADFAM_RESEND_CREDENTIAL_REF = "RESEND_API_KEY"


@dataclass(frozen=True)
class SenderBinding:
    """One tenant's sending identity and the account that carries it.

    Frozen because a binding is configuration, not state: a caller that wants a
    different one asks the registry, it does not mutate the one it was handed.
    Mutation here would be a cross-request bug in a long-lived worker, where the
    registry dicts are module-level and shared.
    """

    #: The tenant key. THE SAME KEY `email_branding` and `email_sender` use —
    #: one tenant has one key across body, envelope and account, so a host can
    #: never be CTM-branded in the body and someone else on the envelope.
    tenant: str

    #: The From display name. It does NOT survive a downgrade (reversed
    #: 2026-09-07): a display name is only meaningful beside the address whose
    #: owner it names, and `Crea Tu Mundo <hola@madfam.io>` — which the old
    #: "the name always survives" rule produced in a real inbox — names one
    #: party over another's mailbox. Name and address move together; see
    #: `email_sender._fallback_for`.
    display_name: str

    #: The From address a fully-enabled binding sends from.
    from_address: str

    #: Where replies land. Carried explicitly rather than defaulted to
    #: `from_address` because the two legitimately diverge: Resend SENDS
    #: hola@creatumundo.mx, Proton RECEIVES it.
    reply_to: str

    #: How the message leaves. One of SUPPORTED_PROVIDERS.
    provider: str = PROVIDER_RESEND

    #: Whose provider account pays for it. One of SUPPORTED_ACCOUNTS.
    account: str = ACCOUNT_MADFAM

    #: The NAME of the credential — an env var name, or a Vault path like
    #: `secret/data/janua/senders/ctm#resend_api_key`. NEVER a secret value.
    #: `sender_credentials.resolve_credential` is the only reader.
    credential_ref: str = MADFAM_RESEND_CREDENTIAL_REF

    #: Domains verified FOR THIS BINDING'S ACCOUNT. Verification is per-account
    #: in Resend: `creatumundo.mx` verified on MADFAM's account says nothing
    #: about the tenant's own account, and sending on the wrong one is the
    #: rejection this field exists to prevent. Empty tuple = "ask the global
    #: RESEND_VERIFIED_DOMAINS instead", which is the MADFAM-account case.
    verified_domains: Tuple[str, ...] = ()

    #: Hosts whose redirect resolves to this tenant. Derived from the branding
    #: registry rather than restated, so envelope and body cannot drift.
    hosts: Tuple[str, ...] = ()

    #: The janua Organization id for this tenant, when it has one. The key the
    #: vCTO gate reads `product_tiers` from — see `sender_policy.py`.
    org_id: Optional[str] = None

    #: The NAME of the setting holding this binding's FIRST-PARTY tracking origin
    #: (e.g. `CTM_TRACKING_HOST` -> `https://enlaces.creatumundo.mx`). A name,
    #: like `credential_ref`, read at send time by `tracking_host_for`, so an
    #: operator turns measurement on or off with env alone. None = this binding
    #: is never instrumented. See app/services/email_engagement.py.
    tracking_host_setting: Optional[str] = None

    #: Where a first-party tracking link that cannot be resolved (unknown token,
    #: bad index) sends the reader: the tenant's own public site.
    default_site: str = "https://madfam.io"

    @property
    def is_on_tenant_account(self) -> bool:
        """True when this binding sends on the TENANT's own provider account."""
        return self.account == ACCOUNT_TENANT

    def redacted(self) -> Dict[str, str]:
        """A dict safe to log or print.

        `credential_ref` is included BECAUSE it is a name and not a value —
        an operator debugging a switch needs to see which reference was used,
        and showing it is what makes "did I point at the right Vault path"
        answerable without ever printing a key.
        """
        return {
            "tenant": self.tenant,
            "display_name": self.display_name,
            "from_address": self.from_address,
            "reply_to": self.reply_to,
            "provider": self.provider,
            "account": self.account,
            "credential_ref": self.credential_ref,
            "verified_domains": ",".join(self.verified_domains),
        }


# --------------------------------------------------------------------------
# The MADFAM platform binding.
#
# Not a tenant: this is the fallback every unrecognised signal resolves to, and
# the address every downgrade lands on. Its display name and address still read
# from settings at resolution time (see `email_sender._default_sender`) so an
# operator can move the platform sender with env alone; the values here are the
# defaults that env overrides.
# --------------------------------------------------------------------------
PLATFORM_TENANT = "madfam"

PLATFORM_BINDING = SenderBinding(
    tenant=PLATFORM_TENANT,
    display_name="MADFAM",
    from_address="hola@madfam.io",
    reply_to="hola@madfam.io",
    provider=PROVIDER_RESEND,
    account=ACCOUNT_MADFAM,
    credential_ref=MADFAM_RESEND_CREDENTIAL_REF,
    # Empty: the platform binding defers to RESEND_VERIFIED_DOMAINS, whose
    # default is `madfam.io` and whose blank-value fallback is also `madfam.io`
    # precisely so that an empty config can never disable all mail.
    verified_domains=(),
    hosts=(),
    org_id=None,
)


# --------------------------------------------------------------------------
# Crea Tu Mundo. The first, and today the only, client binding.
#
# STATE SINCE 2026-09-07 (#608): `account=ACCOUNT_TENANT`. CTM sends on ITS
# OWN Resend account, where `creatumundo.mx` is verified. Confirmed in a real
# inbox at 12:07 CDMX that day: `From: Crea Tu Mundo <hola@creatumundo.mx>`.
#
# (#603 shipped `ACCOUNT_MADFAM` — CTM's address on MADFAM's account — which
# was correct while MADFAM ran the domain, before creatumundo.mx Switch 1.)
#
# The MIGRATION performed here was a two-field edit on this record —
# `account` and `credential_ref` — plus `verified_domains`, made by
# `scripts/sender_binding_switch.py`, which creates and verifies the domain in
# the tenant's own Resend account first. Nothing else changed: no code path, no
# caller, no template. That is the portability the owner asked for, and the
# reason `account` is a field rather than a global setting.
#
# `credential_ref` names an ENV VAR, not a Vault path: janua-api runs with no
# VAULT_ADDR/VAULT_TOKEN, so a `path#field` reference can never resolve at
# runtime. Vault `secret/janua#ctm_resend_api_key` reaches the pod as
# `CTM_RESEND_API_KEY` through the enclii-managed `janua-secrets`
# ExternalSecret. See docs/EMAIL_SENDER_POLICY.md "Phase 4".
# --------------------------------------------------------------------------
CTM_BINDING = SenderBinding(
    tenant="ctm",
    display_name="Crea Tu Mundo",
    from_address="hola@creatumundo.mx",
    reply_to="hola@creatumundo.mx",
    provider=PROVIDER_RESEND,
    account=ACCOUNT_TENANT,
    credential_ref="CTM_RESEND_API_KEY",
    # Non-empty BECAUSE `account` is `tenant`. Verification in Resend is per
    # ACCOUNT, so the global RESEND_VERIFIED_DOMAINS — which describes MADFAM's
    # account — is the wrong authority for a tenant-account binding. These two
    # fields move together, in both directions: a rollback to ACCOUNT_MADFAM
    # empties this tuple so the global list becomes authoritative again.
    verified_domains=("creatumundo.mx",),
    hosts=CTM_HOSTS,
    org_id=CTM_ORG_ID,
    # First-party open/click links live on CTM's own domain, never madfam.io.
    tracking_host_setting="CTM_TRACKING_HOST",
    default_site="https://creatumundo.mx",
)


#: Every client binding, keyed by tenant. The platform binding is deliberately
#: NOT in here: it is the fallback, not a tenant, and putting it in would let a
#: host resolve "to MADFAM" as though that were a branded outcome.
_BINDINGS: Dict[str, SenderBinding] = {
    CTM_BINDING.tenant: CTM_BINDING,
}


def _validate_registry() -> None:
    """Fail at IMPORT on a malformed binding, not at send time.

    A binding with an unknown provider, an unknown account, a tenant-account
    binding with no credential of its own, or an address with no domain, is a
    configuration mistake whose natural discovery point is a rejected sign-in
    link. Import time is the cheapest place to find it: the API will not start.
    """
    for tenant, binding in _BINDINGS.items():
        if binding.tenant != tenant:
            raise ValueError(f"sender binding key {tenant!r} != tenant {binding.tenant!r}")
        if binding.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"sender binding {tenant!r} has unknown provider {binding.provider!r}")
        if binding.account not in SUPPORTED_ACCOUNTS:
            raise ValueError(f"sender binding {tenant!r} has unknown account {binding.account!r}")
        if "@" not in binding.from_address:
            raise ValueError(f"sender binding {tenant!r} from_address is not an address")
        if "@" not in binding.reply_to:
            raise ValueError(f"sender binding {tenant!r} reply_to is not an address")
        if not binding.credential_ref:
            raise ValueError(f"sender binding {tenant!r} has no credential_ref")
        if binding.is_on_tenant_account:
            # A tenant-account binding pointing at MADFAM's key would send the
            # tenant's mail on MADFAM's account while claiming otherwise —
            # exactly the confusion the switch script exists to prevent.
            if binding.credential_ref == MADFAM_RESEND_CREDENTIAL_REF:
                raise ValueError(
                    f"sender binding {tenant!r} is on the tenant account but still "
                    "references MADFAM's credential"
                )
            # Verification is per-account. On the tenant's own account the
            # global RESEND_VERIFIED_DOMAINS describes the wrong account, so
            # the binding MUST carry its own list or nothing is sendable.
            if not binding.verified_domains:
                raise ValueError(
                    f"sender binding {tenant!r} is on the tenant account but lists no "
                    "verified_domains (the global list describes MADFAM's account)"
                )


_validate_registry()


def tenant_for_host(host: Optional[str]) -> Optional[str]:
    """The tenant key a hostname resolves to, or None for the platform default.

    Dot-boundary suffix match, inherited from `email_branding._host_matches`:
    `kalya.app` matches `kalya.app` and `app.kalya.app` but never
    `evilkalya.app`.
    """
    if not host:
        return None
    for tenant, binding in _BINDINGS.items():
        for pattern in binding.hosts:
            if _host_matches(host, pattern):
                return tenant
    return None


def tenant_for_org_id(org_id: Optional[object]) -> Optional[str]:
    """The tenant key an organization id resolves to, or None."""
    if not org_id:
        return None
    needle = str(org_id).strip().lower()
    for tenant, binding in _BINDINGS.items():
        if binding.org_id and binding.org_id.strip().lower() == needle:
            return tenant
    return None


def resolve_binding(tenant: Optional[str]) -> SenderBinding:
    """The binding for a tenant key, or the platform binding.

    Pure function of the key by design: this is the seam a DB-backed store
    would replace, and keeping it free of request context means that swap is
    one function body rather than a signature change through every caller.
    """
    if not tenant:
        return PLATFORM_BINDING
    return _BINDINGS.get(tenant, PLATFORM_BINDING)


def _normalize_tracking_origin(raw: object) -> Optional[str]:
    """`https://host` from a configured tracking origin, or None if unusable.

    Only an https origin with a real hostname and nothing else (no path, query,
    fragment, userinfo or port) is accepted: the links built from it go into
    real inboxes, and a half-valid value must disable measurement rather than
    produce broken links.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parts = urlsplit(raw.strip())
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() != "https" or not host or port is not None:
        return None
    if parts.path not in ("", "/") or parts.query or parts.fragment or parts.username:
        return None
    return f"https://{host.lower()}"


def tracking_host_for(binding: SenderBinding) -> Optional[str]:
    """The binding's first-party tracking origin (`https://host`), or None.

    Read from settings at call time (never cached on the frozen binding), so
    unsetting `CTM_TRACKING_HOST` turns measurement off at the next send.
    """
    if not binding.tracking_host_setting:
        return None
    from app.config import settings

    return _normalize_tracking_origin(getattr(settings, binding.tracking_host_setting, None))


def all_bindings() -> Dict[str, SenderBinding]:
    """A copy of the client binding registry, for operator tooling and tests.

    A copy, not the live dict: a caller that mutated the registry would change
    who every subsequent message in the process comes from.
    """
    return dict(_BINDINGS)


def tracking_bindings() -> Dict[str, SenderBinding]:
    """Every binding (platform included) with a usable tracking origin, by hostname.

    Used by the public tracking endpoints to pick the fallback site from the
    request's Host alone (so an unknown token and a known one on the same host
    get the same answer), and by main.py to trust those hosts.
    """
    found: Dict[str, SenderBinding] = {}
    for binding in (*_BINDINGS.values(), PLATFORM_BINDING):
        origin = tracking_host_for(binding)
        if origin:
            found[origin.removeprefix("https://")] = binding
    return found
