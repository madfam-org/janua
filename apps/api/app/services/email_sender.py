"""Per-tenant SENDER identity for transactional email — Phase 2.

This is the other half of `email_branding.py`. That module resolves what the
BODY of a message looks like; this one resolves the From line itself. Read
`docs/EMAIL_SENDER_POLICY.md` first: Phase 1 kept ONE sender —
`MADFAM <hola@madfam.io>` — for every message from every platform, because the
client was meeting our ecosystem for the first time and we did not control
their sending domain. Phase 2 begins per-client, the day we do.

    Phase 1   From: MADFAM <hola@madfam.io>       (every tenant)
    Phase 2   From: Crea Tu Mundo <hola@creatumundo.mx>   (CTM hosts)

WHY NOW. Owner directive, 2026-09-06: `creatumundo.mx` is CTM's own domain,
MADFAM manages it, and mail to CTM families should come from CTM. The policy
always said this was gated on exactly one thing — that domain being verified in
Resend — and the domain becoming ours is what unblocks the verification.

THE GATE IS THE WHOLE POINT OF THIS MODULE. Resend does not degrade when you
send from a domain it has not verified: it REJECTS the call. An unverified
sender is not a message in the spam folder, it is no message at all, and the
message in question is a sign-in link. So the sender table below is not
consulted on its own — every candidate address is checked against
`settings.resend_verified_domains_list` (env `RESEND_VERIFIED_DOMAINS`,
default `madfam.io`) and an address on an unverified domain is DOWNGRADED, not
sent. See `_fallback_for`.

THE DOWNGRADE IS TOTAL, NOT PARTIAL (reversed 2026-09-07). It used to keep the
tenant's DISPLAY NAME and revert only the address. That shipped, and the first
CTM magic link arrived as `Crea Tu Mundo <hola@madfam.io>` — a From line naming
one party over another party's mailbox. Only MADFAM sends from `hola@madfam.io`,
so the brand name may only appear beside the BRAND'S address. Display name and
address are now one decision:

    creatumundo.mx NOT yet verified -> MADFAM <hola@madfam.io>
    creatumundo.mx verified         -> Crea Tu Mundo <hola@creatumundo.mx>

Body branding is untouched: `email_branding.py` still renders the tenant header,
palette, voice and clock on both sides of that line. What waits for verification
is the envelope claim, not the tenant's presence in the message.

The production cutover is still a one-line manifest edit (add `creatumundo.mx`
to `RESEND_VERIFIED_DOMAINS`) with a one-line rollback (remove it), and the code
path that runs before and after verification is still the same code path, so the
cutover is not also a first execution.

WHY THE SIGNAL IS THE REDIRECT HOST. Same reason as `email_branding.py`: the
auth mailer runs inside FastAPI BackgroundTasks with no DB session, so the
per-org white-label table is unreachable at send time. The magic-link
`redirect_url` host names the product the recipient is being sent back to, and
it is the signal `resolve_sender` was built to read — see the "seam that makes
Phase 2 cheap" section of the policy doc. This module is that seam, filled in.

WHY THE HOST TABLE IS NOT SHARED WITH `email_branding.CTM_HOSTS`. It IS shared:
`SENDER_HOSTS` below is built from the branding registry's host tuple so a host
can never be CTM-branded in the body and MADFAM on the envelope (or vice
versa). One tenant, one host list.

2026-09-07 — THE TABLE MOVED, THE BEHAVIOUR DID NOT. The per-tenant sender is
now a `SenderBinding` record in `sender_binding.py` (display name, address,
reply-to, PROVIDER, ACCOUNT, credential reference, per-account verified
domains) rather than the bare triple that used to live in `_TENANT_SENDERS`
here. Two owner requirements drove that, and neither fits a triple:

  * a branded From is now restricted to vCTO clients — the gate is
    `sender_policy.is_vcto_entitled`, consulted below;
  * a client must be able to move to their OWN provider account — that is the
    binding's `account` / `credential_ref` pair, read at send time by
    `sender_credentials`.

2026-09-07, LATER THE SAME DAY — CTM IS ON ITS OWN RESEND ACCOUNT, AND THE
CREDENTIAL BECAME PART OF THE FROM DECISION. `creatumundo.mx` is verified in
CTM's own Resend account, so CTM's binding is `account="tenant"` with
`credential_ref="CTM_RESEND_API_KEY"` and its own `verified_domains`. That
introduces a state the two existing gates cannot see: the domain is verified —
on an account this process can only reach with a key it may not have. Sending
the branded address without that key means sending it on MADFAM's account,
where the domain is NOT verified, which Resend rejects; the message is a magic
link, so the outcome is a client who cannot sign in. `sender_for` therefore
consults `sender_credentials.tenant_credential_available` as a third gate and
falls back to `MADFAM <hola@madfam.io>` — degraded, delivered — when the key
is absent. The gate lives here, in the SYNC resolution every send path shares,
rather than only in the async send path, so the envelope and the account that
carries it can never disagree.

`_TENANT_SENDERS` and `SENDER_HOSTS` are kept as DERIVED views over the binding
registry: they were public names with tests pinning them, and deriving rather
than deleting means the registry stays the single source while nothing that
imported them breaks. Resolution order and the verified-domain downgrade are
unchanged; a tenant that passes the gate resolves exactly as it did before.

2026-10-04 — THE PLATFORM SENDER SPLITS BY MESSAGE CLASS (ruling R101). One
question decides it: should a person be able to reply?

    system / security  From: MADFAM <noreply@madfam.io>
                       Reply-To: support@madfam.io  (security@madfam.io for
                                 security mail)
    conversation       From: MADFAM <hola@madfam.io>  (as before)

A system event is a code, a link, an alert or a receipt: nobody should be
invited to answer it, but a reader who does must still reach a person, so the
Reply-To names the human inbox that owns the topic and `noreply@madfam.io` is
itself a real mailbox. Welcome and other conversation mail stays on `hola@`.

Only the PLATFORM sender moves. A tenant whose branded sender passes every gate
keeps its own From and Reply-To for every class (R101 leaves tier 1 alone), and
every downgrade returns the platform sender FOR THE MESSAGE'S CLASS — whole, as
THE RULE above requires; `MADFAM <noreply@madfam.io>` is still MADFAM's own
address. A caller that names no class gets the conversation sender, which is
exactly what every caller got before R101. Janua's own templates are classified
in `TEMPLATE_MESSAGE_CLASS`; blank `EMAIL_SYSTEM_FROM_ADDRESS` turns the split
off with one env edit.
"""

from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from app.config import settings
from app.services.sender_binding import (
    PLATFORM_BINDING,
    SenderBinding,
    all_bindings,
    resolve_binding,
)
from app.services.sender_binding import tenant_for_host as _binding_tenant_for_host
from app.services.sender_binding import tenant_for_org_id as _binding_tenant_for_org_id
from app.services.sender_credentials import tenant_credential_available
from app.services.sender_policy import is_vcto_entitled

# --------------------------------------------------------------------------
# A sender is a (display name, address, reply-to) triple. Reply-to is carried
# explicitly rather than defaulted to the From address because the two diverge
# the moment a tenant's mailbox is hosted somewhere the sending domain is not
# — which is exactly CTM's shape: Resend sends `hola@creatumundo.mx`, Proton
# RECEIVES it. Keeping the field means the reply destination is a decision the
# table records rather than an accident of the sending config.
# --------------------------------------------------------------------------
Sender = Tuple[str, str, str]

# The MADFAM default. DERIVED from the platform binding rather than restated,
# so there is exactly one place that decides what "the platform sender" is —
# and so the downgrade in `_fallback_for` cannot ship a display name the
# platform binding does not actually carry. Settings still override at
# resolution time, so an operator can move the platform sender with env alone.
DEFAULT_SENDER_NAME = PLATFORM_BINDING.display_name
DEFAULT_SENDER_ADDRESS = PLATFORM_BINDING.from_address

# --------------------------------------------------------------------------
# Message classes (ruling R101, 2026-10-04). See the module docstring.
# --------------------------------------------------------------------------
MESSAGE_CLASS_SYSTEM = "system"
MESSAGE_CLASS_SECURITY = "security"
MESSAGE_CLASS_CONVERSATION = "conversation"

#: The classes whose platform sender is the no-reply address with a Reply-To.
AUTOMATED_MESSAGE_CLASSES = frozenset({MESSAGE_CLASS_SYSTEM, MESSAGE_CLASS_SECURITY})

#: Janua's own messages, keyed by template stem, classified per R101. A
#: template missing from here resolves to no class, i.e. the conversation
#: sender every message had before R101 — so an unclassified template degrades
#: to the old behaviour rather than to a guess.
TEMPLATE_MESSAGE_CLASS: Dict[str, str] = {
    "magic_link": MESSAGE_CLASS_SYSTEM,
    "verification": MESSAGE_CLASS_SYSTEM,
    "password_reset": MESSAGE_CLASS_SYSTEM,
    "invitation": MESSAGE_CLASS_SYSTEM,
    "data_export_ready": MESSAGE_CLASS_SYSTEM,
    "sso_configuration": MESSAGE_CLASS_SYSTEM,
    "sso_enabled": MESSAGE_CLASS_SYSTEM,
    "compliance_alert": MESSAGE_CLASS_SYSTEM,
    "mfa_recovery": MESSAGE_CLASS_SECURITY,
    "security_alert": MESSAGE_CLASS_SECURITY,
    "welcome": MESSAGE_CLASS_CONVERSATION,
}


def message_class_for_template(template: Optional[str]) -> Optional[str]:
    """The R101 class of one of Janua's own templates, or None.

    Accepts the forms the send paths carry: a bare name (`magic_link`), a file
    name (`magic_link.html`) or a localized path (`es/magic_link.txt`).
    """
    if not template:
        return None
    stem = template.rsplit("/", 1)[-1].split(".", 1)[0]
    return TEMPLATE_MESSAGE_CLASS.get(stem)


def message_class_for_internal_send(token_link: bool) -> Optional[str]:
    """The R101 class of a message other MADFAM services send through Janua.

    A message carrying a sign-in, reset, verification or invitation link is a
    system event by definition, so it gets the system sender when no tenant's
    branded sender applies. Everything else on the internal door keeps the
    sender it had before R101 until its product classifies it.
    """
    return MESSAGE_CLASS_SYSTEM if token_link else None


def is_automated(message_class: Optional[str]) -> bool:
    """True for system and security mail: no-reply From, Reply-To to a person."""
    return message_class in AUTOMATED_MESSAGE_CLASSES


def stream_for(message_class: Optional[str]) -> Optional[str]:
    """The Resend `stream` tag value for a class, or None when unclassified.

    Tagging every send by stream keeps the two reputations separable while
    both senders share madfam.io (R101 supporting rule 3).
    """
    if is_automated(message_class):
        return "transactional"
    if message_class == MESSAGE_CLASS_CONVERSATION:
        return "conversational"
    return None


def _setting_address(name: str) -> str:
    """A sender setting as a clean string ("" when unset or not a string)."""
    value = getattr(settings, name, "")
    return value.strip() if isinstance(value, str) else ""


def _as_triple(binding: SenderBinding) -> Sender:
    """The (name, address, reply-to) view of a binding."""
    return (binding.display_name, binding.from_address, binding.reply_to)


# Crea Tu Mundo. `hola@creatumundo.mx` per the owner directive (2026-09-06);
# replies land in the Proton mailbox for that domain, which is why reply-to is
# the same address rather than bouncing a family back to hola@madfam.io.
# DERIVED from the binding registry — the values are identical to the literal
# that used to sit here, but there is now one place that decides them.
CTM_SENDER: Sender = _as_triple(resolve_binding("ctm"))

#: Every tenant's sender triple. A DERIVED view over `sender_binding._BINDINGS`
#: (see the module docstring): kept because it was a public name with tests
#: pinning it, rebuilt from the registry so the two cannot drift.
_TENANT_SENDERS: Dict[str, Sender] = {
    tenant: _as_triple(binding) for tenant, binding in all_bindings().items()
}

# Deliberately the SAME hosts the body branding uses. A host that renders the
# Crea Tu Mundo header must also carry the Crea Tu Mundo envelope; deriving the
# tuple rather than restating it makes the two impossible to drift apart. The
# binding carries `hosts=CTM_HOSTS` by reference, so this is still that exact
# tuple object and `SENDER_HOSTS["ctm"] is CTM_HOSTS` still holds.
SENDER_HOSTS: Dict[str, Tuple[str, ...]] = {
    tenant: binding.hosts for tenant, binding in all_bindings().items()
}


def _default_sender(message_class: Optional[str] = None) -> Sender:
    """The PLATFORM sender for one message class, or whatever env says.

    Since 2026-09-07 this is also what every downgrade returns — see
    `_fallback_for`. The two were separate functions producing different
    answers (this one whole, that one name-swapped), which is how
    `Crea Tu Mundo <hola@madfam.io>` reached a production inbox. They now
    return the same triple and `_fallback_for` delegates here.

    R101 (2026-10-04): system and security mail comes from
    `EMAIL_SYSTEM_FROM_ADDRESS` (`noreply@madfam.io`) with a Reply-To on
    `EMAIL_SUPPORT_REPLY_TO` or `EMAIL_SECURITY_REPLY_TO`; conversation and
    unclassified mail keeps `MADFAM <hola@madfam.io>`. The display name is the
    same MADFAM name for both, because both addresses are MADFAM's own. A
    blank system address turns the split off; a blank Reply-To falls back to
    the conversation address, so a reply always reaches a person.
    """
    name = settings.FROM_NAME or settings.EMAIL_FROM_NAME or DEFAULT_SENDER_NAME
    address = settings.FROM_EMAIL or settings.EMAIL_FROM_ADDRESS or DEFAULT_SENDER_ADDRESS
    if is_automated(message_class):
        system_address = _setting_address("EMAIL_SYSTEM_FROM_ADDRESS")
        if system_address:
            reply_setting = (
                "EMAIL_SECURITY_REPLY_TO"
                if message_class == MESSAGE_CLASS_SECURITY
                else "EMAIL_SUPPORT_REPLY_TO"
            )
            return name, system_address, _setting_address(reply_setting) or address
    return name, address, address


def _platform_addresses() -> frozenset:
    """Every address the platform sender can put on a From line, lowercased.

    Used where a decision must recognise "this is MADFAM's own address" for
    any class — `hola@` and, since R101, `noreply@` too.
    """
    return frozenset(
        _default_sender(message_class)[1].strip().lower()
        for message_class in (None, MESSAGE_CLASS_SYSTEM, MESSAGE_CLASS_SECURITY)
    )


def is_platform_address(address: Optional[str]) -> bool:
    """True when `address` is one of the platform sender's own From addresses.

    The R101 extras — the `Auto-Submitted` header and the automated-mail line —
    belong to MADFAM's sender only. A tenant's branded sender keeps its mail
    exactly as it was (R101 leaves tier 1 alone).
    """
    return bool(address) and address.strip().lower() in _platform_addresses()


def domain_of(address: Optional[str]) -> str:
    """The lowercased domain part of an address, or "" if there isn't one."""
    if not address or "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].strip().lower()


def is_verified_domain(address: Optional[str], binding: Optional[SenderBinding] = None) -> bool:
    """True when `address`'s domain is verified FOR THE ACCOUNT THAT WILL SEND.

    Exact domain match, NOT a suffix match: a verified `madfam.io` must not
    silently authorise `evil.madfam.io`, and Resend verifies each sending
    domain separately anyway.

    WHY THE ACCOUNT MATTERS. Domain verification in Resend is a property of an
    ACCOUNT, not of a domain. `creatumundo.mx` verified on MADFAM's account
    says nothing about whether it is verified on CTM's own account, so once a
    binding moves to `account="tenant"` the global `RESEND_VERIFIED_DOMAINS`
    (which describes MADFAM's account) is the wrong authority and the binding's
    own `verified_domains` is the right one. A binding on MADFAM's account, or
    no binding at all, reads the global list exactly as before.
    """
    domain = domain_of(address)
    if not domain:
        return False
    if binding is not None and binding.verified_domains:
        return domain in {d.strip().lower() for d in binding.verified_domains}
    return domain in settings.resend_verified_domains_list


def _tenant_for_host(host: Optional[str]) -> Optional[str]:
    """Map a redirect host to a sender tenant key, or None for the default.

    Delegates to the binding registry so host->tenant is decided in exactly one
    place. Same dot-boundary matching as before.
    """
    return _binding_tenant_for_host(host)


def _tenant_for_org_id(org_id: Optional[object]) -> Optional[str]:
    """Map an organization id to a sender tenant key, or None.

    Delegates to the binding registry, which carries each tenant's `org_id`.
    `CTM_ORG_ID` is still the value behind CTM's entry.
    """
    return _binding_tenant_for_org_id(org_id)


def _fallback_for(_sender: Optional[Sender] = None, message_class: Optional[str] = None) -> Sender:
    """The PLATFORM sender, verbatim — name and address together.

    THIS IS THE 2026-09-07 REVERSAL. Until this commit the downgrade was
    deliberately partial: it kept the tenant's DISPLAY NAME and reverted only
    the address, on the theory that "the brand arrives early, the
    deliverability risk never does". Production disproved the theory. The first
    magic link requested from `map.creatumundo.mx` arrived in the CTM inbox at
    2026-09-07 02:32:21 CDMX as:

        From: Crea Tu Mundo <hola@madfam.io>

    That header is a claim about two different parties at once. `hola@madfam.io`
    is MADFAM's mailbox and only MADFAM sends from it; putting a client's name
    in front of it tells the recipient that Crea Tu Mundo sends from MADFAM's
    address, which is not true, is not something a recipient can verify, and is
    the exact shape of a display-name spoof that mail clients teach people to
    distrust. Owner directive the same night: that From must NEVER be produced.

    So the display name and the address are now ONE decision keyed on a single
    fact — is the binding's own address domain verified for the account that
    will send it. Verified: the tenant's name AND the tenant's address.
    Not verified: the platform binding, verbatim, with the platform's own
    display name. There is no state in between, because the in-between state is
    the header above.

        creatumundo.mx NOT yet verified -> MADFAM <hola@madfam.io>
        creatumundo.mx verified         -> Crea Tu Mundo <hola@creatumundo.mx>

    The argument is accepted and ignored: callers pass the sender they were
    downgrading, and keeping the parameter means the reversal is one function
    body rather than a change at every call site. Nothing about the tenant
    survives the downgrade by design — that is the whole point.

    BODY BRANDING IS UNAFFECTED. `email_branding.py` still renders the tenant's
    header, palette, voice and clock. What is being withheld is the ENVELOPE
    claim, not the tenant's presence in the message.

    R101: the platform sender returned is the one for `message_class`, so a
    downgraded sign-in link leaves as `MADFAM <noreply@madfam.io>` with its
    Reply-To — still MADFAM's own name over MADFAM's own address.
    """
    # No verified-domain check on the platform address itself: if MADFAM's own
    # domain is missing from RESEND_VERIFIED_DOMAINS that is an operator
    # misconfiguration, and returning it anyway means the operator sees the
    # real rejection from Resend rather than mail silently coming from a third
    # address this function invented.
    return _default_sender(message_class)


def tenant_for(
    host: Optional[str] = None,
    redirect_url: Optional[str] = None,
    org_id: Optional[object] = None,
) -> Optional[str]:
    """The tenant key for one message, or None for the platform default.

    Factored out of `sender_for` because the binding, the vCTO gate and the
    credential all need the same answer, and three walks of the same precedence
    would be three chances for them to disagree about who is sending.
    """
    tenant = _tenant_for_org_id(org_id)
    if tenant is None and host:
        tenant = _tenant_for_host(host)
    if tenant is None and redirect_url:
        tenant = _tenant_for_host(urlparse(redirect_url).hostname)
    return tenant


def binding_for(
    host: Optional[str] = None,
    redirect_url: Optional[str] = None,
    org_id: Optional[object] = None,
) -> SenderBinding:
    """The `SenderBinding` one message resolves to.

    The account/provider/credential view of the same resolution `sender_for`
    performs. The send path needs this to know WHICH ACCOUNT to send on; see
    `sender_credentials.resolve_credential`.

    NOTE this returns the binding the tenant WOULD use, without applying the
    vCTO gate — a gated-off tenant sends on the platform account by definition,
    and `resend_email_service` reads the gate through `sender_for` before it
    ever asks for a credential.
    """
    return resolve_binding(tenant_for(host=host, redirect_url=redirect_url, org_id=org_id))


def sender_for(
    host: Optional[str] = None,
    redirect_url: Optional[str] = None,
    org_id: Optional[object] = None,
    vcto_entitled: Optional[bool] = None,
    message_class: Optional[str] = None,
) -> Sender:
    """The (display name, from address, reply-to) for one message.

    Resolution order, highest precedence first:

      1. `org_id` — a caller that already knows the tenant is authoritative.
      2. `host` — a bare hostname, when a caller has one directly.
      3. `redirect_url` — the magic-link redirect, whose host names the
         product; this is what the auth mailer actually has at send time.
      4. Nothing recognised -> the MADFAM default.

    THREE gates then apply to the resolved tenant, in this order:

      * **The vCTO gate** (`sender_policy.is_vcto_entitled`). A branded From
        line is reserved for clients whose infrastructure MADFAM operates —
        owner directive 2026-09-06. `vcto_entitled` lets a caller holding a DB
        session supply the authoritative answer; without one the policy
        module's cache decides and fails closed.

      * **The verified-domain gate**, evaluated against the ACCOUNT the binding
        names (see `is_verified_domain`).

      * **The credential gate** (`sender_credentials.tenant_credential_available`),
        added 2026-09-07 when CTM moved to its own Resend account. A binding on
        a TENANT account carries its own `verified_domains`, describing an
        account this process can only reach with that tenant's key. With the
        key absent, the first two gates would still pass — the domain IS
        verified, on an account we cannot authenticate to — and the branded
        address would leave on MADFAM's account, where `creatumundo.mx` is not
        verified and Resend rejects the send. That is a sign-in link that never
        arrives, so the credential is part of the same decision as the address.

    ANY GATE FAILING RETURNS THE PLATFORM BINDING WHOLE — name and address
    together (owner directive 2026-09-07; see `_fallback_for`). It used to
    return the tenant's display name on the platform address, which produced
    `Crea Tu Mundo <hola@madfam.io>` in a real inbox. The display name now
    follows the address it is entitled to, always.

    No gate is bypassable from a caller: passing `vcto_entitled=True` for a
    tenant whose domain is unverified still downgrades, because the later gates
    are about whether Resend will accept the send at all.

    `message_class` (R101) chooses WHICH platform sender the default and every
    downgrade return; a tenant that passes all three gates keeps its own
    sender whatever the class.
    """
    tenant = tenant_for(host=host, redirect_url=redirect_url, org_id=org_id)

    if tenant is None:
        return _default_sender(message_class)

    binding = resolve_binding(tenant)
    sender = _as_triple(binding)

    if not is_vcto_entitled(tenant, vcto_entitled=vcto_entitled):
        # Not a vCTO client: neither the name nor the domain ships. A branded
        # display name on the platform address is the header this whole module
        # was reversed on 2026-09-07 to stop producing.
        return _fallback_for(sender, message_class)

    if not is_verified_domain(sender[1], binding=binding):
        return _fallback_for(sender, message_class)

    if not tenant_credential_available(binding):
        # The binding says "send on the tenant's own account" and that
        # account's key is not present. Its verified_domains describe an
        # account this process cannot reach, so the branded address would go
        # out on MADFAM's account — where `creatumundo.mx` is NOT verified and
        # Resend rejects the call outright. Falling back here keeps the From
        # line and the account that carries it as ONE decision.
        return _fallback_for(sender, message_class)

    return sender


def sender_for_address(
    from_email: Optional[str],
    from_name: Optional[str] = None,
    host: Optional[str] = None,
    redirect_url: Optional[str] = None,
    org_id: Optional[object] = None,
    vcto_entitled: Optional[bool] = None,
    message_class: Optional[str] = None,
) -> Sender:
    """Honour a caller's explicit From, but only from a verified domain.

    The internal door (`POST /api/v1/email/send`) accepts `from_email` /
    `from_name` from other MADFAM services. Those fields were previously
    ignored outright, which was safe but opaque. Honouring them is only safe
    under the same gate everything else is under: an arbitrary caller-supplied
    domain is exactly the input that would hand Resend a rejection, or worse
    let one service send as another's brand.

    So: an explicit address is used when its domain is in
    `RESEND_VERIFIED_DOMAINS`, and otherwise the caller's From is DISCARDED and
    the host rule decides.

    2026-09-07: THE CALLER'S DISPLAY NAME IS DISCARDED WITH IT. It used to
    survive — "naming yourself is harmless, claiming a domain is not" — and
    that reasoning is what let `Crea Tu Mundo <hola@madfam.io>` be assembled
    from two individually harmless halves. A display name is only harmless
    while it names the party that owns the address underneath it. So the name
    is honoured exactly where the address is: on a verified address the caller
    was allowed to claim, and nowhere else. Once the host rule has fallen back
    to the platform binding, the From is the platform's, whole.

    THE vCTO GATE APPLIES HERE TOO, and it has to. If an explicit `from_email`
    could reach a tenant domain without passing the gate, then "restrict
    branded sending to vCTO clients" would hold for the auth mailer and be
    bypassable by any service holding the internal API key — which is the one
    caller most likely to be automating a client's mail. So an explicit address
    on a TENANT's domain is honoured only when that tenant passes the gate; an
    address on MADFAM's own verified domain is unaffected, because sending as
    MADFAM was never the branded privilege.

    An explicit address keeps its own Reply-To whatever `message_class` says:
    the class (R101) only chooses the platform sender the host rule falls
    back to.
    """
    if from_email and is_verified_domain(from_email):
        claimed = _tenant_for_verified_address(from_email)
        if claimed is None or is_vcto_entitled(claimed, vcto_entitled=vcto_entitled):
            name = from_name or _default_sender()[0]
            return name, from_email.strip(), from_email.strip()

    name, address, reply_to = sender_for(
        host=host,
        redirect_url=redirect_url,
        org_id=org_id,
        vcto_entitled=vcto_entitled,
        message_class=message_class,
    )
    # `from_name` is applied only when the resolved address is one the caller
    # would have been entitled to claim outright — i.e. the tenant's own
    # branded address survived both gates. On a platform address it is
    # dropped: see the 2026-09-07 note above. Without this check a caller could
    # pass `from_name="Crea Tu Mundo"` with no address at all and reassemble
    # the exact header the reversal forbids. Since R101 the platform has two
    # addresses, and the name is dropped on either.
    if from_name and not is_platform_address(address):
        name = from_name
    return name, address, reply_to


def _tenant_for_verified_address(address: Optional[str]) -> Optional[str]:
    """The tenant whose binding claims `address`'s domain, or None.

    Used to decide whether a caller-supplied From is asking to send as a
    CLIENT's brand (gated) or merely as MADFAM (never gated). Matches on the
    binding's own `from_address` domain, which is the domain the tenant was
    onboarded with.
    """
    domain = domain_of(address)
    if not domain:
        return None
    for tenant, binding in all_bindings().items():
        if domain_of(binding.from_address) == domain:
            return tenant
        if domain in {d.strip().lower() for d in binding.verified_domains}:
            return tenant
    return None
