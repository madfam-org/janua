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
  2026-10-27, plus ``symbiosis-hcm-dhanam-writer`` from enclii#900 and
  ``karafiel-dhanam-cost-events`` (RFC 0050 Phase 1), each provisioned only
  after its reservation deploys) and in
  ``docs/reference/PROTECTED_RESOURCES_AND_MCP_CLIENTS.md``.
- ``CONSUMER_MACHINE_SCOPES`` / ``CONSUMER_AUDIENCES``: what the consumers'
  code authorizes machine tokens on, with the file that does it.
- ``scripts/seed_service_clients.py``: Janua's own service-client seed.

Each value must be reserved, or listed in ``TENANT_BOUND_MACHINE_SCOPES`` /
``TENANT_BOUND_SERVICE_AUDIENCES`` with the reason the resource server binds it
to the token's own organization. Adding a machine edge anywhere in the
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
}

#: audience -> where a consumer accepts it on machine-reachable routes.
CONSUMER_AUDIENCES: dict[str, str] = {
    "karafiel-api": "karafiel JANUA_AUDIENCE",
    "karafiel-app": "karafiel JANUA_ADDITIONAL_AUDIENCES (infra/k8s/production)",
    "karafiel-staging-api": "karafiel staging JANUA_AUDIENCE",
    "phynd-crm": "phynd-crm PHYND_CRM_MACHINE_AUDIENCE (apps/web/src/lib/trpc/machine-auth.ts)",
    "dhanam-api": "dhanam machine strategies (hard-coded audience)",
    "dhanam-money-moves": "dhanam JANUA_MONEY_MOVES_AUDIENCE",
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
