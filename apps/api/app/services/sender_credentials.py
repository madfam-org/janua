"""Resolve a binding's provider credential. The ONLY module that reads one.

A `SenderBinding` carries a `credential_ref` — a NAME, never a value. This
module turns that name into the secret at send time, and it is deliberately the
single place in the transactional-mail stack that ever holds one. Everything
else (the binding registry, the policy gate, the switch script, the logs) works
with references, which is what makes a binding safe to print in a PR diff and
safe for an operator script to echo.

TWO REFERENCE SHAPES, ONE FUNCTION

    RESEND_API_KEY                                   -> environment variable
    secret/data/janua/senders/ctm#resend_api_key     -> Vault path # field

Both go through `app.core.secrets_provider`, which is already the repo's
abstraction for exactly this (SOC 2 CF-06): it returns a `VaultSecretsProvider`
when `VAULT_ADDR`/`VAULT_TOKEN` are set and an `EnvSecretsProvider` otherwise.
Reusing it means a tenant credential lands in Vault through the same path as
every other janua secret, with the same 300s cache, rather than through a
second mechanism invented here.

WHY THE `#field` SUFFIX. Vault KV v2 stores a MAP at a path. The existing
provider is constructed around one path (`VAULT_SECRET_PATH`, default
`secret/data/janua`) and reads keys out of it, which is right for janua's own
config but wrong for per-tenant secrets: each tenant's credential should live at
its own path so it can be scoped by its own Vault policy, and so that granting
an operator access to one tenant's key does not grant them janua's whole config
map. The `#field` suffix names the key within that per-tenant path.

NEVER LOGGED. No function here returns, formats, or logs a credential value.
Failures log the REFERENCE and the reason, which is enough to diagnose
("wrong path", "field missing") and never enough to leak. `has_credential`
exists so an operator script can answer "is it there?" without the value ever
crossing a process boundary.

A MISSING TENANT CREDENTIAL MUST NOT BLOCK A SIGN-IN LINK (2026-09-07)

`resolve_credential` still RAISES on a tenant-account binding whose key is
absent — that is the loud, correct answer for a caller asking "give me the
credential", and `--check-credential` reports NO off the same path. But the
question the SEND path asks is different: "may this binding send as itself right
now?". Answering that with an exception would mean a client's magic link is not
sent at all when an operator has flipped a binding to their own account before
writing the key, and the owner's rule (#607) orders those outcomes explicitly:
mail from the platform address is a degraded outcome, mail nobody receives is an
outage.

So `tenant_credential_available` answers that second question with a BOOLEAN,
and — crucially — it is SYNCHRONOUS, because the thing that has to agree with it
is `email_sender.sender_for`, which is sync and is what every send path reads
the From line from. If only the async send path knew the credential was missing,
`sender_for` would keep returning the tenant's branded address while the message
actually left on MADFAM's account: a From line of
`Crea Tu Mundo <hola@creatumundo.mx>` sent on an account that has never verified
that domain, which Resend REJECTS outright. One sync check, consulted by the
resolution both paths share, is what keeps the envelope and the account from
disagreeing.

This is only possible because the credential in production is an ENV VAR
(`CTM_RESEND_API_KEY`, delivered by the janua-secrets ExternalSecret): reading
one is a dict lookup, not I/O. A Vault-path reference cannot be resolved
synchronously, and `tenant_credential_available` says so — see its docstring for
why that returns True rather than False.
"""

from __future__ import annotations

import os
from typing import Optional

import structlog

from app.config import settings
from app.services.sender_binding import (
    ACCOUNT_TENANT,
    MADFAM_RESEND_CREDENTIAL_REF,
    SenderBinding,
)

logger = structlog.get_logger()


class SenderCredentialError(RuntimeError):
    """A binding's credential could not be resolved.

    Raised rather than returning None so a misconfigured TENANT-account binding
    is loud. The send path catches it and falls back to the platform sender
    (see `resend_email_service`), because a sign-in link that does not arrive is
    worse than one from the platform address — but the exception is what makes
    the fallback an observable event instead of a silent one.
    """


def _is_vault_ref(credential_ref: str) -> bool:
    """True for a Vault path reference, False for an env var name.

    A Vault path contains a `/`; an environment variable name cannot. That is
    the whole discriminator, and it is unambiguous because POSIX env names are
    restricted to `[A-Za-z_][A-Za-z0-9_]*`.
    """
    return "/" in credential_ref


def _split_vault_ref(credential_ref: str) -> tuple[str, str]:
    """`secret/data/x/y#field` -> (`secret/data/x/y`, `field`).

    A reference with no `#` defaults to the field `api_key`, so the common case
    can be written as a bare path.
    """
    if "#" in credential_ref:
        path, field = credential_ref.rsplit("#", 1)
        return path.strip(), field.strip()
    return credential_ref.strip(), "api_key"


def _read_env_reference(ref: str) -> Optional[str]:
    """Read an ENV-VAR credential reference synchronously. Never logs the value.

    Split out of `_read_reference` so the sync availability check and the async
    resolution read env references through the exact same two lookups, in the
    same order. Two copies of "settings first, then os.environ" would be two
    chances for the check and the send to disagree about whether a key is there.
    """
    if not ref:
        return None
    # `settings` first so a value supplied through the app's own config surface
    # wins, then the raw environment.
    from_settings = getattr(settings, ref, None)
    if isinstance(from_settings, str) and from_settings.strip():
        return from_settings.strip()
    raw = os.environ.get(ref, "").strip()
    return raw or None


def tenant_credential_available(binding: SenderBinding) -> bool:
    """May this binding send on its OWN account right now? Synchronous.

    THE QUESTION THIS ANSWERS IS NOT `resolve_credential`'S. That one hands
    back a secret and raises when it cannot, which is right for an operator
    asking "is the key in place?" (`--check-credential` still reports NO off
    it). This one is consulted by `email_sender.sender_for` to decide whether
    the tenant's branded From line may go on the envelope at all, and its
    answer has to be available in a SYNC function on every send path — see the
    module docstring for why that matters.

    True for a binding on MADFAM's own account: that binding is not asking for a
    tenant credential, and the SDK/HTTP caller is already configured with the
    platform key.

    False ONLY for a tenant-account binding whose env-var credential is absent
    or blank. That is the state that must degrade to the platform sender rather
    than raise: an operator who flipped the binding before writing the key would
    otherwise take a client's sign-in links offline.

    True for a tenant-account binding on a VAULT reference, deliberately. A
    Vault read is I/O and cannot happen in a sync function, so this check has
    nothing to say about it and must not veto on ignorance — returning False
    would silently downgrade every Vault-backed binding to the platform sender
    forever. The async send path still resolves it properly and still falls back
    if the read comes back empty, so the Vault case degrades one layer later
    instead of never. Production does not use this shape today: janua-api runs
    without VAULT_ADDR/VAULT_TOKEN (verified on the live pod 2026-09-07), which
    is why CTM's `credential_ref` is the env var `CTM_RESEND_API_KEY`.
    """
    if not binding.is_on_tenant_account:
        return True

    ref = (binding.credential_ref or "").strip()
    if not ref:
        return False

    if _is_vault_ref(ref):
        # Not answerable synchronously; see the docstring. The async path owns
        # this case.
        return True

    if _read_env_reference(ref):
        return True

    logger.warning(
        "sender_credentials.tenant_credential_missing",
        tenant=binding.tenant,
        credential_ref=ref,  # a NAME, never a value
        provider=binding.provider,
        account=binding.account,
    )
    return False


async def resolve_credential(binding: SenderBinding) -> Optional[str]:
    """The provider credential for `binding`, or None to use process defaults.

    Returns None for a binding on MADFAM's own account whose reference is the
    platform key: the Resend SDK is already configured with
    `settings.RESEND_API_KEY` at service construction, so returning None means
    "change nothing", which keeps the pre-existing path byte-identical.

    Raises `SenderCredentialError` when a TENANT-account binding's credential
    is missing — that binding cannot send at all, and pretending otherwise
    would hand Resend someone else's key.
    """
    ref = (binding.credential_ref or "").strip()

    # MADFAM account on the platform key: nothing to resolve.
    if not binding.is_on_tenant_account and ref == MADFAM_RESEND_CREDENTIAL_REF:
        return None

    value = await _read_reference(ref)

    if value:
        return value

    if binding.account == ACCOUNT_TENANT:
        logger.error(
            "sender_credentials.missing_tenant_credential",
            tenant=binding.tenant,
            credential_ref=ref,  # a NAME, never a value
            provider=binding.provider,
        )
        raise SenderCredentialError(
            f"credential {ref!r} for tenant {binding.tenant!r} is not set; "
            "the binding is on the tenant's own account and cannot send without it"
        )

    logger.warning(
        "sender_credentials.missing_credential_using_platform_default",
        tenant=binding.tenant,
        credential_ref=ref,
    )
    return None


async def _read_reference(ref: str) -> Optional[str]:
    """Read one credential reference. Never logs the value."""
    if not ref:
        return None

    if not _is_vault_ref(ref):
        return _read_env_reference(ref)

    path, field = _split_vault_ref(ref)
    try:
        # Imported lazily: the module-level singleton in secrets_provider is
        # built on first use, and importing it at module scope would build it
        # during test collection where VAULT_ADDR is deliberately unset.
        import hvac  # noqa: F401  (presence check; the provider imports it too)
    except ImportError:
        logger.warning("sender_credentials.hvac_unavailable", credential_ref=ref)
        return None

    vault_addr = os.environ.get("VAULT_ADDR", "").strip()
    vault_token = os.environ.get("VAULT_TOKEN", "").strip()
    if not (vault_addr and vault_token):
        logger.warning("sender_credentials.vault_not_configured", credential_ref=ref)
        return None

    try:
        from app.core.secrets_provider import VaultSecretsProvider

        provider = VaultSecretsProvider(
            vault_addr=vault_addr,
            vault_token=vault_token,
            secret_path=path,
        )
        value = await provider.get_secret(field)
    except Exception as exc:  # pragma: no cover - exercised via the error path
        # `str(exc)` from hvac names the path and the HTTP status, never the
        # secret; the value never enters an exception in the first place.
        logger.warning(
            "sender_credentials.vault_read_failed",
            credential_ref=ref,
            error=str(exc),
        )
        return None

    return value.strip() if isinstance(value, str) and value.strip() else None


async def has_credential(binding: SenderBinding) -> bool:
    """True when this binding's credential resolves to something.

    For operator tooling: answers "is the key in place?" without the value
    crossing a process boundary or entering a log line.
    """
    try:
        if not binding.is_on_tenant_account:
            ref = (binding.credential_ref or "").strip()
            if ref == MADFAM_RESEND_CREDENTIAL_REF:
                return bool((settings.RESEND_API_KEY or "").strip())
        return await resolve_credential(binding) is not None
    except SenderCredentialError:
        return False


async def resolve_bound_credential(binding: SenderBinding) -> str:
    """Resolve exactly the configured account for a durable transactional intent.

    Unlike the legacy adapter, this never asks the caller to use ambient SDK
    state. The platform key is valid only when explicitly named by this binding.
    Missing alternate credentials cannot fall back to the platform account.
    """
    ref = (binding.credential_ref or "").strip()
    value = await _read_reference(ref) if ref else None
    if not value:
        raise SenderCredentialError("Bound email credential is unavailable")
    return value
