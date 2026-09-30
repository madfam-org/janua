#!/usr/bin/env python3
"""Read-only audit: which OAuth clients the provenance rules for machine tokens change.

Two rules key on whether a client was registered by a platform admin
(``created_by`` is a user with ``is_admin``, see
``app/services/oauth_client_authority.client_registered_by_platform_admin``):

1. **Product tier claims** on a ``client_credentials`` token. A client
   registered by a platform admin gets ``<product>_tier: "madfam"`` for every
   product it holds a namespaced scope for (``<product>:<action>``). Any other
   client gets a ``<product>_tier`` claim only from its organization's
   ``product_tiers``. Listed as ``kind = "tier_claims"``: each
   ``client_credentials`` client NOT registered by a platform admin whose
   ``allowed_scopes`` name a product its organization has no tier for, with
   the claim keys its tokens no longer carry (``tier_claims_dropped``).

2. **The connections boundary** (audience ``janua-connections``, scope
   ``connections:delegate``) accepts only clients registered by a platform
   admin. Listed as ``kind = "connections"``: each client that holds that grant
   and was NOT registered by a platform admin. ``refused_after_deploy`` is
   true when every other check of the boundary passes today (active and
   confidential), i.e. the client works before the deploy and not after.

Ids, flags, dates, claim keys and counts only: no names, emails, secrets or
hashes are printed (secrets and hashes are never selected).

USAGE (read-only; runs inside one READ ONLY transaction):

    python scripts/audit_client_credentials_tier_claims.py            # table
    python scripts/audit_client_credentials_tier_claims.py --json     # JSON lines

Self-contained (standard library + SQLAlchemy + psycopg2), so it also runs in
a pod whose image predates this change, piped on stdin:

    kubectl -n janua exec -i deploy/janua-api -- python - --json \\
        < apps/api/scripts/audit_client_credentials_tier_claims.py

The database URL comes from ``DIRECT_DATABASE_URL``, else ``DATABASE_URL``,
and is never printed. Exit status: 0 when no ACTIVE client changes, 2 when at
least one does, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Optional

# A COPY of the values in app/core/consent_purposes.py, so this runs against an
# image that predates this script. A unit test fails if they drift.
CONNECTIONS_AUDIENCE = "janua-connections"
CONNECTIONS_DELEGATE_SCOPE = "connections:delegate"
MADFAM_TIER = "madfam"


def claim_key(product) -> str:
    """The ``<key>`` of ``<key>_tier``, exactly as the token builder derives it."""
    return re.sub(r"[^a-z0-9_]", "_", str(product).lower())


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value]
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


def _as_dict(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def classify(row: dict) -> dict:
    """Pure: what the provenance rules change for one client row.

    ``row`` needs ``allowed_scopes``, ``grant_types``, ``audience``,
    ``creator_is_admin``, ``is_active``, ``is_confidential`` and
    ``product_tiers`` (the organization's, or None when unbound or missing).
    """
    scopes = _as_list(row.get("allowed_scopes"))
    grants = _as_list(row.get("grant_types"))
    machine = "client_credentials" in grants
    admin = bool(row.get("creator_is_admin"))
    active = bool(row.get("is_active"))

    dropped: list[str] = []
    if machine and not admin:
        scoped = {claim_key(s.split(":", 1)[0]) for s in scopes if ":" in s}
        entitled = {claim_key(p) for p in _as_dict(row.get("product_tiers"))}
        dropped = sorted(f"{key}_tier" for key in scoped - entitled if key)

    connections_grant = (
        machine
        and (row.get("audience") or "") == CONNECTIONS_AUDIENCE
        and CONNECTIONS_DELEGATE_SCOPE in scopes
    )
    connections = connections_grant and not admin
    return {
        "tier_claims_dropped": dropped,
        "connections": connections,
        "refused_after_deploy": bool(
            connections and active and row.get("is_confidential")
        ),
        "changes_active_client": bool(active and (dropped or connections)),
    }


# ---------------------------------------------------------------------------
# Database access (read-only)
# ---------------------------------------------------------------------------

CLIENTS_SQL = """
SELECT c.id::text              AS id,
       c.client_id             AS client_id,
       c.audience              AS audience,
       c.allowed_scopes        AS allowed_scopes,
       c.grant_types           AS grant_types,
       c.organization_id::text AS organization_id,
       c.created_by::text      AS created_by,
       c.is_active             AS is_active,
       c.is_confidential       AS is_confidential,
       c.created_at            AS created_at,
       c.last_used_at          AS last_used_at,
       COALESCE(u.is_admin, false) AS creator_is_admin,
       (u.id IS NULL)          AS creator_missing,
       o.product_tiers         AS product_tiers
  FROM oauth_clients c
  LEFT JOIN users u ON u.id = c.created_by
  LEFT JOIN organizations o ON o.id = c.organization_id
 ORDER BY c.created_at
"""


def _database_url() -> str:
    url = os.environ.get("DIRECT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DIRECT_DATABASE_URL / DATABASE_URL is not set")
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://", 1)
    )


def _iso(value) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def report_rows(rows: list[dict]) -> list[dict]:
    """Pure: the report for already-fetched rows (one line per rule a row hits)."""
    report = []
    for row in rows:
        verdict = classify(row)
        base = {
            "id": row["id"],
            "client_id": row["client_id"],
            "organization_id": row["organization_id"],
            "created_by": row["created_by"],
            "creator_missing": bool(row["creator_missing"]),
            "is_active": bool(row["is_active"]),
            "created_at": _iso(row["created_at"]),
            "last_used_at": _iso(row["last_used_at"]),
        }
        if verdict["tier_claims_dropped"]:
            report.append(
                {
                    "kind": "tier_claims",
                    **base,
                    "tier_claims_dropped": verdict["tier_claims_dropped"],
                }
            )
        if verdict["connections"]:
            report.append(
                {
                    "kind": "connections",
                    **base,
                    "refused_after_deploy": verdict["refused_after_deploy"],
                }
            )
    return report


def collect(url: str) -> list[dict]:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            rows = [dict(r._mapping) for r in conn.execute(text(CLIENTS_SQL))]
            conn.rollback()
    finally:
        engine.dispose()
    return report_rows(rows)


def summary(report: list[dict]) -> dict:
    tier = [r for r in report if r["kind"] == "tier_claims"]
    conn = [r for r in report if r["kind"] == "connections"]
    by_claim: dict[str, int] = {}
    for r in tier:
        if r["is_active"]:
            for key in r["tier_claims_dropped"]:
                by_claim[key] = by_claim.get(key, 0) + 1
    return {
        "tier_claims_clients": len(tier),
        "tier_claims_clients_active": sum(r["is_active"] for r in tier),
        "tier_claims_clients_active_ever_used": sum(
            bool(r["is_active"] and r["last_used_at"]) for r in tier
        ),
        "tier_claims_dropped_by_claim_active": dict(sorted(by_claim.items())),
        "connections_clients": len(conn),
        "connections_refused_after_deploy": sum(r["refused_after_deploy"] for r in conn),
        "connections_refused_after_deploy_ever_used": sum(
            bool(r["refused_after_deploy"] and r["last_used_at"]) for r in conn
        ),
    }


def exit_status(report: list[dict]) -> int:
    changed = any(
        (r["kind"] == "tier_claims" and r["is_active"])
        or (r["kind"] == "connections" and r["refused_after_deploy"])
        for r in report
    )
    return 2 if changed else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="emit JSON lines")
    args = parser.parse_args(argv)
    try:
        report = collect(_database_url())
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - report the class, never the URL
        print(f"audit failed: {type(error).__name__}", file=sys.stderr)
        return 1

    totals = summary(report)
    if args.json:
        for row in report:
            print(json.dumps(row, sort_keys=True))
        print(json.dumps({"summary": totals}, sort_keys=True))
    else:
        header = (
            "kind", "id", "client_id", "organization_id", "created_by", "active",
            "created_at", "last_used_at", "detail",
        )  # fmt: skip
        print("\t".join(header))
        for r in report:
            detail = (
                ",".join(r["tier_claims_dropped"])
                if r["kind"] == "tier_claims"
                else f"refused_after_deploy={r['refused_after_deploy']}"
            )
            print(
                "\t".join(
                    str(v)
                    for v in (
                        r["kind"], r["id"], r["client_id"], r["organization_id"],
                        r["created_by"], r["is_active"], r["created_at"],
                        r["last_used_at"], detail,
                    )  # fmt: skip
                )
            )
        print("summary", json.dumps(totals, sort_keys=True))
    return exit_status(report)


if __name__ == "__main__":
    sys.exit(main())
