"""Reserved OAuth-client boundaries: the single registry.

Some values on an ``OAuthClient`` row are not configuration, they are
authority. A service boundary inside Janua (payment notices, white-label
branding, provider-token delegation) or a sibling resource server
(`docs/service-tokens.md`) decides whether to honour a token by reading the
client's ``audience``, ``allowed_scopes`` and, for the purpose registry and the
first-party trust predicate, its ``name``. Whoever can write those values onto
a client whose secret they hold can speak across that boundary.

So registering or editing a client that carries any value listed here is a
platform-admin action (``User.is_admin``). The registration check
(`services/oauth_client_authority.py`) and every service-auth module import
THIS module, so a new boundary is added in exactly one place and the two sides
can never disagree.

Adding a boundary: define its audience/scope constant here, add it to the
matching set below, and import the constant from the service-auth module that
enforces it. ``tests/unit/core/test_reserved_oauth_boundaries.py`` pins the
known members.

A sibling resource server's new machine scope or audience is reserved HERE,
and deployed, BEFORE any client carrying it is provisioned: until then any
organization admin may register a client with it.
``tests/unit/core/test_ecosystem_machine_edges_reserved.py`` lists the
ecosystem's machine edges and fails while one is neither reserved nor
deliberately tenant-bound.

This module is pure (no database, no FastAPI) so any layer can import it.
"""

from __future__ import annotations

from typing import Iterable, Optional

from app.core.consent_purposes import (
    CONNECTIONS_AUDIENCE,
    CONNECTIONS_DELEGATE_SCOPE,
    PURPOSES,
)

# ---------------------------------------------------------------------------
# Janua's own service boundaries (audience ``janua-<surface>``)
# ---------------------------------------------------------------------------

#: Payment notices (`services/payment_mail_auth.py`).
MAIL_AUDIENCE = "janua-email"
PAYMENT_MAIL_SCOPE = "crea-map:payment-mail"

#: White-label branding service authority (organization-bound).
BRANDING_AUDIENCE = "janua-white-label"
BRANDING_SCOPE = "white-label:branding"

#: A scope that makes an interactive client first-party: silent auth
#: (`prompt=none`) and no consent screen (`oauth_provider._is_silent_auth_allowed`).
SILENT_AUTH_SCOPE = "madfam:silent_auth"

#: ``admin`` on a client_credentials token becomes ``is_admin: true`` and the
#: ``admin`` role (`oauth_provider._get_client_credentials_claims`).
PLATFORM_ADMIN_SCOPE = "admin"

# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: Every ``janua-*`` audience names a Janua-internal surface.
RESERVED_AUDIENCE_PREFIXES: tuple[str, ...] = ("janua-",)

#: Sibling resource servers that authorize machine tokens by audience + scope
#: (docs/service-tokens.md), plus the audiences a consent purpose accepts on a
#: user's subject token.
ECOSYSTEM_SERVICE_AUDIENCES: frozenset[str] = frozenset(
    {
        "karafiel-api",
        # Karafiel also accepts its web client's audience on every route
        # (JANUA_ADDITIONAL_AUDIENCES, karafiel infra/k8s/production), and its
        # staging API trusts this issuer under its own audience.
        "karafiel-app",
        "karafiel-staging-api",
        "dhanam-api",
        # Dhanam's read-only Money Moves projection (JANUA_MONEY_MOVES_AUDIENCE).
        "dhanam-money-moves",
        # PhyndCRM machine tokens (PHYND_CRM_MACHINE_AUDIENCE, default
        # ``phynd-crm``). Distinct from the staff SSO client's audience
        # ``phynd-crm-api``, which stays ordinary.
        "phynd-crm",
        "yantra4d-api",
        "pravara-api",
        "asset-shells-api",
        "fabrication-prep-api",
    }
)

#: Karafiel machine scopes (audience ``karafiel-api``/``karafiel-app``).
#: Karafiel pins EVERY service token holding one of these to MADFAM's own
#: emisor RFC (``LEGAL_SERVICE_RFC``, karafiel ``core/middleware/active_rfc.py``
#: ``SERVICE_SCOPE_PREFIXES``), whatever the token's ``org_id``: whoever holds
#: one reads or writes MADFAM's own CFDI, contracts and client records. The
#: list mirrors karafiel ``core/plan_permissions.py`` plus ``cfdi:issue``
#: (``integrations/zavlo_webhook.py``).
KARAFIEL_SCOPES: frozenset[str] = frozenset(
    {
        "cfdi:issue",
        "legal:draft",
        "legal:employment-draft",
        "legal:contractor-draft",
        "legal:client-profile",
        "fiscal:invoice",
        "fiscal:csf-intake",
        "familia:documents",
    }
)

#: Dhanam machine scopes (audience ``dhanam-api``): the RouteCraft billing-event
#: relay, and the machine strategies under dhanam ``apps/api/src/modules``
#: (scheduled-payments writer, cost-events writer, merchant payment projection),
#: which also require
#: a reviewed per-client grant row in Dhanam. The audience is reserved too; the
#: scopes are reserved so the registry states the whole edge. The writer scope
#: is ``dhanam-scheduled-payments:write`` (ONE colon, the only shape client
#: registration accepts); its never-registrable two-colon predecessor
#: ``dhanam:scheduled-payments:write`` stays reserved so the UPDATE path cannot
#: write it onto a client either.
DHANAM_SCOPES: frozenset[str] = frozenset(
    {
        "billing:events",
        "dhanam-scheduled-payments:write",
        "dhanam:scheduled-payments:write",
        "dhanam-cost-events:write",
        "dhanam:merchant-read",
    }
)

#: Symbiosis-HCM's tenant-less machine scope: public market benchmarks for
#: platform-admin clients (``compensation/benchmark_views.py``). HCM's tenant
#: app roles (``hcm:hr`` and friends) are NOT reserved, see below.
HCM_PLATFORM_SCOPES: frozenset[str] = frozenset({"hcm-benchmarks:read"})

#: Pravara MES machine scopes (audience ``pravara-api``). Pravara reads
#: ``tenant_id`` from the token, so clients holding these are org-bound.
PRAVARA_SCOPES: frozenset[str] = frozenset(
    {
        "pravara-mes:jobs",
        "pravara-mes:nodes",
        "pravara-mes:passports",
        "pravara-mes:read",
    }
)

#: asset-shells (AAS store) scopes (audience ``asset-shells-api``).
#: ``publish-types`` writes tenant-less type shells (platform-admin clients);
#: ``publish-instances`` and ``read`` act on one tenant's instances (org-bound).
ASSET_SHELLS_SCOPES: frozenset[str] = frozenset(
    {
        "asset-shells:read",
        "asset-shells:publish-types",
        "asset-shells:publish-instances",
    }
)

#: fabrication-prep (slicing service) scope (audience ``fabrication-prep-api``).
#: Slice jobs belong to the calling client (``sub``) and carry no tenant data,
#: so the client that holds it is platform-admin.
FABRICATION_PREP_SCOPES: frozenset[str] = frozenset({"fabrication-prep:slice"})

#: PhyndCRM machine scopes (audience ``phynd-crm``). PhyndCRM maps each to a
#: fixed set of read scopes (phynd-crm ``apps/web/src/lib/trpc/machine-auth.ts``
#: ``MACHINE_SCOPE_GRANTS``: engagements and contacts, read only) and pins every
#: machine token to ONE configured tenant, refusing any ``org_id`` but
#: ``PHYND_CRM_MACHINE_JANUA_ORG_ID``. That pin is phynd's configuration, not
#: the token's own organization, so the scope is reserved rather than
#: tenant-bound: only a platform admin grants a read of MADFAM's CRM.
PHYND_CRM_SCOPES: frozenset[str] = frozenset({"phynd-crm-engagements:read"})

RESERVED_AUDIENCES: frozenset[str] = frozenset(
    {MAIL_AUDIENCE, BRANDING_AUDIENCE, CONNECTIONS_AUDIENCE}
    | ECOSYSTEM_SERVICE_AUDIENCES
    | {audience for purpose in PURPOSES.values() for audience in purpose.allowed_subject_audiences}
)

RESERVED_SCOPES: frozenset[str] = frozenset(
    {
        PAYMENT_MAIL_SCOPE,
        BRANDING_SCOPE,
        CONNECTIONS_DELEGATE_SCOPE,
        SILENT_AUTH_SCOPE,
        PLATFORM_ADMIN_SCOPE,
        # Service-to-service scopes honoured by sibling resource servers.
        "yantra4d:render",
    }
    | KARAFIEL_SCOPES
    | DHANAM_SCOPES
    | PHYND_CRM_SCOPES
    | HCM_PLATFORM_SCOPES
    | PRAVARA_SCOPES
    | ASSET_SHELLS_SCOPES
    | FABRICATION_PREP_SCOPES
)

#: Machine scopes and audiences the ecosystem declares that are deliberately
#: NOT reserved: the resource server authorizes them on the token's own
#: ``org_id`` (tenant), so an organization admin who grants one to a client of
#: their own organization grants authority over that organization only. Each
#: entry names why. ``tests/unit/core/test_ecosystem_machine_edges_reserved.py``
#: requires every declared machine edge to be reserved or listed here, so a
#: new edge cannot go unreviewed.
TENANT_BOUND_MACHINE_SCOPES: dict[str, str] = {
    "hcm:hr": "symbiosis-hcm TenantRolePermission requires org_id and reads it as the tenant",
    "selva:infer": "selva nexus-api scopes every request to the token's org_id (RLS)",
}
TENANT_BOUND_SERVICE_AUDIENCES: dict[str, str] = {
    "symbiosis-hcm": "tenant routes require org_id; hcm-benchmarks:read is reserved",
    "selva-office": "selva nexus-api scopes every request to the token's org_id (RLS)",
}

#: ``<product>:admin`` becomes a ``<product>_admin`` role on a machine token
#: whether or not the client is organization-bound.
RESERVED_SCOPE_SUFFIXES: tuple[str, ...] = (":admin",)

#: Client names that the first-party trust predicate treats as MADFAM itself
#: (silent auth, pre-consented). Compared case-insensitively.
FIRST_PARTY_NAME_PREFIXES: tuple[str, ...] = ("selva-office", "madfam-")

#: Client names a consent purpose authorizes BY NAME for provider-token
#: delegation (`consent_purposes.ConsentPurpose.exchange_clients`/`offline_clients`).
RESERVED_CLIENT_NAMES: frozenset[str] = frozenset(
    name
    for purpose in PURPOSES.values()
    for name in (*purpose.exchange_clients, *purpose.offline_clients)
)


def is_reserved_audience(audience: Optional[str]) -> bool:
    if not audience:
        return False
    value = audience.strip()
    return value in RESERVED_AUDIENCES or value.startswith(RESERVED_AUDIENCE_PREFIXES)


def is_reserved_scope(scope: Optional[str]) -> bool:
    if not scope:
        return False
    value = scope.strip()
    return value in RESERVED_SCOPES or value.endswith(RESERVED_SCOPE_SUFFIXES)


def is_first_party_name(name: Optional[str]) -> bool:
    """The first-party trust predicate's name rule (no trimming: exact prefix)."""
    return (name or "").lower().startswith(FIRST_PARTY_NAME_PREFIXES)


def is_reserved_name(name: Optional[str]) -> bool:
    value = (name or "").strip()
    return is_first_party_name(value) or value.lower() in {
        reserved.lower() for reserved in RESERVED_CLIENT_NAMES
    }


def reserved_fields(
    *,
    name: Optional[str] = None,
    audience: Optional[str] = None,
    scopes: Optional[Iterable[str]] = None,
) -> list[str]:
    """Which of ``name``/``audience``/``allowed_scopes`` hold a reserved value.

    Empty when nothing is reserved. Field names only, never the values, so the
    result is safe to return to the caller and to log.
    """
    fields = []
    if is_reserved_name(name):
        fields.append("name")
    if is_reserved_audience(audience):
        fields.append("audience")
    if any(is_reserved_scope(scope) for scope in (scopes or [])):
        fields.append("allowed_scopes")
    return fields


def client_is_reserved(client) -> bool:
    """True when a stored client row already carries a reserved value."""
    return bool(
        reserved_fields(
            name=getattr(client, "name", None),
            audience=getattr(client, "audience", None),
            scopes=getattr(client, "allowed_scopes", None),
        )
    )


__all__ = [
    "ASSET_SHELLS_SCOPES",
    "BRANDING_AUDIENCE",
    "BRANDING_SCOPE",
    "DHANAM_SCOPES",
    "ECOSYSTEM_SERVICE_AUDIENCES",
    "FABRICATION_PREP_SCOPES",
    "FIRST_PARTY_NAME_PREFIXES",
    "HCM_PLATFORM_SCOPES",
    "KARAFIEL_SCOPES",
    "MAIL_AUDIENCE",
    "PAYMENT_MAIL_SCOPE",
    "PHYND_CRM_SCOPES",
    "PLATFORM_ADMIN_SCOPE",
    "PRAVARA_SCOPES",
    "RESERVED_AUDIENCES",
    "RESERVED_AUDIENCE_PREFIXES",
    "RESERVED_CLIENT_NAMES",
    "RESERVED_SCOPES",
    "RESERVED_SCOPE_SUFFIXES",
    "SILENT_AUTH_SCOPE",
    "TENANT_BOUND_MACHINE_SCOPES",
    "TENANT_BOUND_SERVICE_AUDIENCES",
    "client_is_reserved",
    "is_first_party_name",
    "is_reserved_audience",
    "is_reserved_name",
    "is_reserved_scope",
    "reserved_fields",
]
