"""Every ecosystem machine edge is reserved, or deliberately tenant-bound.

A machine scope or audience that a sibling resource server honours, but that
``core/reserved_oauth_boundaries.py`` does not reserve, can be put on a client
by ANY organization admin. Karafiel added ``legal:employment-draft``,
``legal:contractor-draft`` and ``familia:documents`` (and accepted the
``karafiel-app`` audience) without Janua reserving them, and Karafiel pins every
service token holding them to MADFAM's own RFC. These tables are the review
point that stops that from recurring:

- ``ECOSYSTEM_MACHINE_EDGES``: every ``client_credentials`` client declared in
  enclii ``config/ecosystem-oidc-provision.yaml`` (copied at c945fe0a,
  2026-10-27, plus ``symbiosis-hcm-dhanam-writer`` from enclii#900,
  ``karafiel-dhanam-cost-events`` (RFC 0050 Phase 1), the twelve RFC 0051 COGS
  MCP consumers from enclii#946 (``feat/cogs-mcp-consumer-clients``, open) and
  Symbiosis HCM's two labor-cost clients from symbiosis-hcm#232
  (``apps/api/symbiosis/settings.py``, open), Pravara's Dhanam cost-event writer
  (pravara-mes#71, declared in enclii#948) and ``ops-agents-selva-cogs``
  (enclii#946), each provisioned only after its reservation deploys) and in
  ``docs/reference/PROTECTED_RESOURCES_AND_MCP_CLIENTS.md``.
- ``CONSUMER_MACHINE_SCOPES`` / ``CONSUMER_AUDIENCES``: what the consumers'
  code authorizes machine tokens on, with the file that does it.
- ``scripts/seed_service_clients.py``: Janua's own service-client seed.

Each value must be reserved, or listed in ``TENANT_BOUND_MACHINE_SCOPES`` /
``TENANT_BOUND_SERVICE_AUDIENCES`` with the reason the resource server binds it
to the token's own organization. An audience that cannot be reserved
(``SHARED_DEFAULT_AUDIENCES``: Janua's own default) is allowed only on an edge
whose every scope is reserved. Adding a machine edge anywhere in the
ecosystem means adding it here and reserving it (or justifying it) in the same
Janua change, deployed before the client is provisioned.
"""

from __future__ import annotations

import pytest

from app.core import reserved_oauth_boundaries as reserved
from scripts.seed_service_clients import ORG_BOUND_SERVICE_CLIENTS, SERVICE_CLIENTS

#: name -> (audience, scopes, organization-bound)
ECOSYSTEM_MACHINE_EDGES: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "nauta-symbiosis-hcm": ("symbiosis-hcm", ("hcm:hr",), True),
    # Nauta's cockpit CRM reads (enclii ``nauta-phynd-crm``, declared after this
    # reservation deploys). Org-bound: phynd-crm refuses any org_id but
    # PHYND_CRM_MACHINE_JANUA_ORG_ID.
    "nauta-phynd-crm": ("phynd-crm", ("phynd-crm-engagements:read",), True),
    "crea-map-payment-mail": ("janua-email", ("crea-map:payment-mail",), True),
    "pravara-yantra4d-step-reader": ("yantra4d-api", ("yantra4d:render",), False),
    "yantra4d-asset-shells-publisher": (
        "asset-shells-api",
        ("asset-shells:publish-types",),
        False,
    ),
    "fashion-cabinet-asset-shells-publisher": (
        "asset-shells-api",
        ("asset-shells:publish-types",),
        False,
    ),
    "zavlo-cfdi-emitter": ("karafiel-api", ("cfdi:issue",), False),
    "pravara-fabrication-prep": ("fabrication-prep-api", ("fabrication-prep:slice",), False),
    "routecraft-billing-relay": ("dhanam-api", ("billing:events",), False),
    "forj-pravara-intake": ("pravara-api", ("pravara-mes:jobs",), True),
    "cotiza-pravara-intake": ("pravara-api", ("pravara-mes:jobs",), True),
    "pravara-asset-shells-publisher": (
        "asset-shells-api",
        ("asset-shells:publish-instances", "asset-shells:read"),
        True,
    ),
    "voxa-selva": ("selva-office", ("selva:infer",), True),
    "crea-sim-selva": ("selva-office", ("selva:infer",), True),
    "selva-yantra4d": ("yantra4d-api", ("yantra4d:render",), False),
    "selva-pravara-mes": ("pravara-api", ("pravara-mes:read",), True),
    "cv-hcm-benchmarks": ("symbiosis-hcm", ("hcm-benchmarks:read",), False),
    "symbiosis-hcm-dhanam-writer": (
        "dhanam-api",
        ("dhanam-scheduled-payments:write",),
        True,
    ),
    "karafiel-dhanam-cost-events": (
        "dhanam-api",
        ("dhanam-cost-events:write",),
        True,
    ),
    # Symbiosis HCM's labor cost events (RFC 0050 C10, symbiosis-hcm#232): one
    # client reads Nauta's hours, another writes Dhanam's cost events.
    "symbiosis-hcm-nauta-labor-hours": ("nauta-api", ("nauta-labor-hours:read",), True),
    "symbiosis-hcm-dhanam-cost-events": ("dhanam-api", ("dhanam-cost-events:write",), True),
    # Pravara MES job consumption as quantity-only cost events (RFC 0050 C12,
    # pravara-mes#71; client declared in enclii#948).
    "pravara-dhanam-cost-events": ("dhanam-api", ("dhanam-cost-events:write",), True),
    # The ops agents reading Selva's own COGS MCP (selva-office#362; client
    # declared in enclii#946). No Selva-fleet client for Selva's own ledger.
    "ops-agents-selva-cogs": ("selva-office", ("selva-cogs:read",), True),
    # RFC 0051 ruling M3 (enclii#946): Selva's fleet and the ops agents, one
    # client per platform MCP, each org-bound to madfam-ecosystem.
    **{
        f"{consumer}-{platform}-cogs": (audience, (f"{platform}-cogs:read",), True)
        for consumer in ("selva", "ops-agents")
        for platform, audience in (
            ("dhanam", "dhanam-api"),
            ("karafiel", "karafiel-api"),
            ("converge-dash", "converge-dash"),
            ("pravara", "pravara-api"),
            ("nauta", "nauta-api"),
            ("enclii", "janua.dev"),
        )
    },
}

#: scope -> where the consumer authorizes a machine token on it. None of these
#: is bound to the token's own organization, so each must be reserved.
CONSUMER_MACHINE_SCOPES: dict[str, str] = {
    "cfdi:issue": "karafiel apps/api/integrations/zavlo_webhook.py",
    "legal:draft": "karafiel apps/api/core/middleware/active_rfc.py SERVICE_SCOPE_PREFIXES",
    "legal:employment-draft": "karafiel apps/api/core/middleware/active_rfc.py",
    "legal:contractor-draft": "karafiel apps/api/core/middleware/active_rfc.py",
    "legal:client-profile": "karafiel apps/api/core/middleware/active_rfc.py",
    "fiscal:invoice": "karafiel apps/api/core/middleware/active_rfc.py",
    "fiscal:csf-intake": "karafiel apps/api/core/middleware/active_rfc.py",
    "familia:documents": "karafiel apps/api/core/middleware/active_rfc.py",
    "phynd-crm-engagements:read": (
        "phynd-crm apps/web/src/lib/trpc/machine-auth.ts MACHINE_SCOPE_GRANTS"
    ),
    "billing:events": "routecraft-billing-relay edge, docs/service-tokens.md (no check in dhanam yet)",
    "dhanam-scheduled-payments:write": "dhanam scheduled-payments/machine/writer.strategy.ts",
    "dhanam-cost-events:write": "dhanam cost-events/machine/cost-event-writer.strategy.ts",
    "dhanam:merchant-read": "dhanam spaces/payment-projection.strategy.ts",
    "hcm-benchmarks:read": "symbiosis-hcm apps/api/compensation/benchmark_views.py",
    # RFC 0051 native COGS MCPs: ``POST /mcp`` on each platform's API audience.
    "dhanam-cogs:read": "dhanam apps/api/src/modules/mcp/mcp-auth.strategy.ts (dhanam#942)",
    "karafiel-cogs:read": (
        "karafiel apps/api/core/middleware/active_rfc.py SERVICE_SCOPE_PREFIXES, "
        "apps/api/karafiel_mcp/views.py (karafiel#356)"
    ),
    "converge-dash-cogs:read": (
        "converge-dash apps/api/src/auth/policy.ts COGS_READ_SCOPE, "
        "apps/api/src/mcp/route.ts (converge-dash#42)"
    ),
    "pravara-cogs:read": (
        "pravara-mes apps/pravara-api/internal/middleware/scopes.go ScopeCogsRead, "
        "internal/api/mcp_routes.go (pravara-mes#69)"
    ),
    "nauta-cogs:read": (
        "nauta apps/web/src/lib/machine-reads.ts MACHINE_SCOPES.cogs, "
        "apps/web/src/app/mcp/route.ts (nauta#360)"
    ),
    "enclii-cogs:read": (
        "enclii apps/switchyard-api/internal/api/mcp_routes.go MCPScope "
        "(enclii#945, open, branch feat/waybill-mcp-cogs)"
    ),
    "selva-cogs:read": (
        "selva-office apps/nexus-api/nexus_api/mcp/router.py SELVA_COGS_READ_SCOPE "
        "(selva-office#362, open, branch feat/selva-mcp-cogs)"
    ),
    "symbiosis-hcm-cogs:read": (
        "symbiosis-hcm apps/api/hcm_mcp/views.py ALCANCE "
        "(symbiosis-hcm#233, open draft, branch feat/hcm-mcp-cogs)"
    ),
    # Nauta's other machine reads (nauta apps/web/src/lib/machine-reads.ts).
    "nauta-labor-hours:read": "nauta apps/web/src/app/api/internal/labor-hours/route.ts (nauta#359)",
    "nauta-engagements:read": "nauta apps/web/src/app/api/internal/engagements/route.ts (nauta#358)",
}

#: audience -> where a consumer accepts it on machine-reachable routes.
CONSUMER_AUDIENCES: dict[str, str] = {
    "karafiel-api": "karafiel JANUA_AUDIENCE",
    "karafiel-app": "karafiel JANUA_ADDITIONAL_AUDIENCES (infra/k8s/production)",
    "karafiel-staging-api": "karafiel staging JANUA_AUDIENCE",
    "phynd-crm": "phynd-crm PHYND_CRM_MACHINE_AUDIENCE (apps/web/src/lib/trpc/machine-auth.ts)",
    "dhanam-api": "dhanam machine strategies (hard-coded audience)",
    "dhanam-money-moves": "dhanam JANUA_MONEY_MOVES_AUDIENCE",
    "pravara-api": "pravara-mes apps/pravara-api/internal/config/config.go oidc.audience",
    "converge-dash": "converge-dash JANUA_AUDIENCE (apps/api/src/auth/janua.ts, /mcp)",
    "nauta-api": "nauta JANUA_AUDIENCE (apps/web/src/lib/machine-token.ts, /api/internal/, /mcp)",
}


def _scope_is_covered(scope: str) -> bool:
    return reserved.is_reserved_scope(scope) or scope in reserved.TENANT_BOUND_MACHINE_SCOPES


def _audience_is_covered(audience: str) -> bool:
    return (
        reserved.is_reserved_audience(audience)
        or audience in reserved.TENANT_BOUND_SERVICE_AUDIENCES
    )


@pytest.mark.parametrize("name", sorted(ECOSYSTEM_MACHINE_EDGES))
def test_every_declared_machine_edge_is_reserved_or_tenant_bound(name):
    audience, scopes, org_bound = ECOSYSTEM_MACHINE_EDGES[name]
    if audience in reserved.SHARED_DEFAULT_AUDIENCES:
        # Nothing about the audience gates this edge, so every scope must.
        for scope in scopes:
            assert reserved.is_reserved_scope(scope), f"{name}: {scope} on {audience}"
        return
    assert _audience_is_covered(audience), f"{name}: audience {audience} is unreviewed"
    for scope in scopes:
        assert _scope_is_covered(scope), f"{name}: scope {scope} is unreviewed"
        if scope in reserved.TENANT_BOUND_MACHINE_SCOPES:
            # A tenant-bound scope only stays tenant-bound on an org-bound client.
            assert org_bound, f"{name}: {scope} on a client with no organization"


@pytest.mark.parametrize("scope", sorted(CONSUMER_MACHINE_SCOPES))
def test_consumer_machine_scopes_are_reserved(scope):
    assert reserved.is_reserved_scope(scope), CONSUMER_MACHINE_SCOPES[scope]


@pytest.mark.parametrize("audience", sorted(CONSUMER_AUDIENCES))
def test_consumer_audiences_are_reserved(audience):
    assert reserved.is_reserved_audience(audience), CONSUMER_AUDIENCES[audience]


@pytest.mark.parametrize(
    "entry",
    [*SERVICE_CLIENTS, *ORG_BOUND_SERVICE_CLIENTS],
    ids=lambda entry: entry["name"],
)
def test_janua_seeded_service_clients_are_reserved(entry):
    assert reserved.is_reserved_audience(entry["audience"])
    assert all(reserved.is_reserved_scope(scope) for scope in entry["allowed_scopes"])


def test_tenant_bound_exceptions_are_not_reserved_and_give_a_reason():
    for scope, reason in reserved.TENANT_BOUND_MACHINE_SCOPES.items():
        assert not reserved.is_reserved_scope(scope)
        assert reason.strip()
    for audience, reason in reserved.TENANT_BOUND_SERVICE_AUDIENCES.items():
        assert not reserved.is_reserved_audience(audience)
        assert reason.strip()


def test_cogs_read_scopes_are_the_platform_cogs_read_shape_and_all_have_a_consumer():
    """RFC 0051 ruling M2: ``<platform>-cogs:read``, one colon, each enforced."""
    for scope in reserved.COGS_READ_SCOPES:
        namespace, _, action = scope.partition(":")
        assert action == "read" and namespace.endswith("-cogs") and ":" not in namespace
        assert scope in CONSUMER_MACHINE_SCOPES, scope
    for scope in reserved.NAUTA_SCOPES:
        assert scope in CONSUMER_MACHINE_SCOPES, scope


@pytest.mark.parametrize(
    "scope",
    # The shapes the consumers refuse must not slip in as reserved look-alikes,
    # and must not be needed: no consumer honours them.
    ["dhanam:cogs:read", "nauta:labor-hours:read", "dhanam-cogs:read-all", "cogs:read"],
)
def test_cogs_look_alikes_are_not_reserved(scope):
    assert not reserved.is_reserved_scope(scope)


def test_shared_default_audiences_are_janua_defaults_and_not_reservable():
    from app.config import Settings

    assert set(reserved.SHARED_DEFAULT_AUDIENCES) == {Settings.model_fields["JWT_AUDIENCE"].default}
    for audience, reason in reserved.SHARED_DEFAULT_AUDIENCES.items():
        assert not reserved.is_reserved_audience(audience)
        assert audience not in reserved.TENANT_BOUND_SERVICE_AUDIENCES
        assert reason.strip()


def test_a_shared_default_audience_edge_with_an_unreserved_scope_is_refused():
    """The guard itself: janua.dev plus a tenant-bound scope is not covered."""
    audience = next(iter(reserved.SHARED_DEFAULT_AUDIENCES))
    edge = (audience, ("selva:infer",), True)
    ECOSYSTEM_MACHINE_EDGES["__probe__"] = edge
    try:
        with pytest.raises(AssertionError, match="selva:infer on janua.dev"):
            test_every_declared_machine_edge_is_reserved_or_tenant_bound("__probe__")
    finally:
        del ECOSYSTEM_MACHINE_EDGES["__probe__"]
