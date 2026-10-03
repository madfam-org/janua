"""
Seed machine (client_credentials) OAuth clients for cross-service auth.

These are the RFC 0024 §P4 consolidation service identities:

- ``zavlo-cfdi-emitter``      — Zavlo → Karafiel CFDI stamping bridge
- ``routecraft-billing-relay`` — RouteCraft → Dhanam billing delegation

plus the other platform-admin edges below, and the ORGANIZATION-BOUND edge
templates in ``ORG_BOUND_SERVICE_CLIENTS`` (one client per organization, see
``--org-bound``).

Unlike the interactive clients in ``seed_core_clients.py``, these clients:

- allow ONLY the ``client_credentials`` grant (no browser flows),
- have no redirect URIs,
- are confidential (a ``client_secret`` is required), and
- carry a narrow scope allowlist (least privilege).

The client_secret is printed exactly once on creation — store it in the
approved secret store (Enclii/Vault) for the calling service. Never commit it.

Alternative (zero-touch) provisioning: each consumer service's bootstrap can
instead call ``POST /api/v1/oauth/clients/register`` with ``X-Internal-API-Key``
and the same payload shape. This script exists for operator-driven seeding.

Usage:
    cd apps/api
    # platform-admin clients (SERVICE_CLIENTS)
    python scripts/seed_service_clients.py
    # one organization-bound client: <template>.<organization slug>
    python scripts/seed_service_clients.py --org-bound forj-pravara-intake --organization <slug>

See docs/service-tokens.md for the full integration contract.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_core_clients import (  # noqa: E402
    _resolve_database_url,
    _seed_clients,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service (machine-to-machine) client definitions
# ---------------------------------------------------------------------------

SERVICE_CLIENTS: list[dict[str, Any]] = [
    {
        "name": "zavlo-cfdi-emitter",
        "description": (
            "Zavlo → Karafiel CFDI stamping bridge service client "
            "(internal-devops RFC 0024 §P4.2). Emits zavlo.* payment "
            "envelopes to Karafiel's CFDI billing bridge."
        ),
        "audience": "karafiel-api",
        "redirect_uris": [],
        "allowed_scopes": ["cfdi:issue"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
    {
        "name": "nauta-legal-drafts",
        "description": (
            "Nauta → Karafiel legal document generation service client "
            "(nauta docs/LEGAL_OPS_INTEGRATION_PLAN_2026-08-12.md, step "
            "D3.5). legal:draft creates and compiles service-agreement "
            "drafts and reads generated-document metadata. "
            "legal:client-profile creates and updates the client's own "
            "legal-entity profile (karafiel PR #148). Nothing else."
        ),
        "audience": "karafiel-api",
        "redirect_uris": [],
        "allowed_scopes": ["legal:draft", "legal:client-profile"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
    {
        "name": "routecraft-billing-relay",
        "description": (
            "RouteCraft → Dhanam billing delegation service client "
            "(internal-devops RFC 0024 §P4.3). Emits signed billing events "
            "and delegated checkout requests to Dhanam's billing APIs."
        ),
        "audience": "dhanam-api",
        "redirect_uris": [],
        "allowed_scopes": ["billing:events"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
    {
        "name": "forj-catalog-materializer",
        "description": (
            "Forj → Yantra4D render service client. The forj catalog "
            "materializer pre-renders hyperobject parameter-sets (from the "
            "yantra4d + fashion-cabinet commons) into GLB assets for the "
            "forj infinite-scroll storefront (buy → manufacture-on-demand). "
            "yantra4d:render is the only scope: it lets a machine token clear "
            "yantra4d's pro-tier GLB export gate (yantra4d apps/api/"
            "middleware/auth.py RENDER_SCOPE). Nothing else. Same edge "
            "fashion-cabinet's body_render.py already uses."
        ),
        "audience": "yantra4d-api",
        "redirect_uris": [],
        "allowed_scopes": ["yantra4d:render"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
    {
        "name": "pravara-yantra4d-step-reader",
        "description": (
            "Pravara MES → Yantra4D render service client. Pravara's dispatcher "
            "pulls STEP exports of a hyperobject parameter-set before slicing; "
            "STEP is a format of the render call, so yantra4d:render is the "
            "only scope. Platform-admin: yantra4d renders carry no tenant."
        ),
        "audience": "yantra4d-api",
        "redirect_uris": [],
        "allowed_scopes": ["yantra4d:render"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
        "organization_id": None,
    },
    {
        "name": "yantra4d-asset-shells-publisher",
        "description": (
            "Yantra4D → asset-shells type publisher. Publishes the solid "
            "commons' type shells (tenant-less) to asset-shells. "
            "asset-shells:publish-types only. Platform-admin."
        ),
        "audience": "asset-shells-api",
        "redirect_uris": [],
        "allowed_scopes": ["asset-shells:publish-types"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
        "organization_id": None,
    },
    {
        "name": "fashion-cabinet-asset-shells-publisher",
        "description": (
            "Fashion Cabinet → asset-shells type publisher. Publishes the soft "
            "commons' type shells (tenant-less) to asset-shells. "
            "asset-shells:publish-types only. Platform-admin."
        ),
        "audience": "asset-shells-api",
        "redirect_uris": [],
        "allowed_scopes": ["asset-shells:publish-types"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
        "organization_id": None,
    },
]

#: Organization-bound edge templates. The receiving API reads ``tenant_id``
#: from the token, and Janua sets it only on a client bound to an organization
#: (the organization id). One client carries one tenant, so every organization
#: gets its own client, named ``<template>.<organization slug>``; nothing here is
#: created without ``--org-bound``/``--organization``.
ORG_BOUND_SERVICE_CLIENTS: list[dict[str, Any]] = [
    {
        "name": "pravara-asset-shells-publisher",
        "description": (
            "Pravara MES → asset-shells instance publisher for one "
            "organization: publishes instance shells and appends passport "
            "events, and reads them back."
        ),
        "audience": "asset-shells-api",
        "redirect_uris": [],
        "allowed_scopes": ["asset-shells:publish-instances", "asset-shells:read"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
    {
        "name": "forj-pravara-intake",
        "description": (
            "Forj → Pravara MES order intake for one organization's "
            "fabrication floor. pravara-mes:jobs only."
        ),
        "audience": "pravara-api",
        "redirect_uris": [],
        "allowed_scopes": ["pravara-mes:jobs"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
    {
        "name": "cotiza-pravara-intake",
        "description": (
            "Cotiza → Pravara MES job intake for one organization's "
            "fabrication floor. pravara-mes:jobs only."
        ),
        "audience": "pravara-api",
        "redirect_uris": [],
        "allowed_scopes": ["pravara-mes:jobs"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    },
]


def org_bound_client(template_name: str, organization_id: str, organization_slug: str) -> dict:
    """Materialize one organization's client from an ORG_BOUND template."""
    template = next((c for c in ORG_BOUND_SERVICE_CLIENTS if c["name"] == template_name), None)
    if template is None:
        known = ", ".join(c["name"] for c in ORG_BOUND_SERVICE_CLIENTS)
        raise SystemExit(f"Unknown org-bound template {template_name!r}. Known: {known}")
    if not organization_id or not organization_slug:
        raise SystemExit("An organization-bound client needs an existing organization.")
    client = dict(template)
    client["name"] = f"{template_name}.{organization_slug}"
    client["organization_id"] = str(organization_id)
    client["description"] = f"{template['description']} Organization: {organization_slug}."
    return client


async def _organization_id_for_slug(engine, slug: str) -> str:
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": slug}
            )
        ).fetchone()
    if row is None:
        raise SystemExit(f"No organization with slug {slug!r}.")
    return str(row[0])


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed machine OAuth clients.")
    parser.add_argument(
        "--org-bound",
        metavar="TEMPLATE",
        help="Seed one organization-bound client from ORG_BOUND_SERVICE_CLIENTS.",
    )
    parser.add_argument("--organization", metavar="SLUG", help="Organization slug for --org-bound.")
    args = parser.parse_args(argv)
    if bool(args.org_bound) != bool(args.organization):
        parser.error("--org-bound and --organization go together")
    return args


async def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    database_url = _resolve_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        if args.org_bound:
            org_id = await _organization_id_for_slug(engine, args.organization)
            clients = [org_bound_client(args.org_bound, org_id, args.organization)]
        else:
            clients = SERVICE_CLIENTS
        await _seed_clients(engine, clients=clients)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(130)
