#!/usr/bin/env python3
"""Read-only audit of OAuth clients against the registration authority rules.

Lists every OAuth client that carries authority a registration now needs a
platform admin (or an organization admin) for, with where it came from and
whether it was ever used:

- clients holding a reserved name, audience or scope
  (`app/core/reserved_oauth_boundaries.py`);
- ``client_credentials`` clients;
- organization-bound clients.

For each: the row id, public ``client_id``, organization id, creator id,
whether the creator is a platform admin, whether the creator is (today) an
owner/active admin of the client's organization, created/last-used dates, the
payment-mail dispatches attributed to it, and its audit-log actions. Ids and
counts only: no names, emails, secrets or hashes are printed (secrets and
hashes are never even selected).

Verdicts:

- ``ok``      created by a platform admin;
- ``review``  created by someone else AND it holds a reserved value, is a
              ``client_credentials`` client with no organization, or is bound
              to an organization its creator does not administer;
- ``info``    anything else listed (for completeness).

A ``review`` row that is ACTIVE and holds the payment-mail grant is refused by
the payment-mail boundary once this change is deployed (it trusts only
admin-registered clients): the summary counts those separately so a legitimate
one can be re-registered by an admin BEFORE the deploy.

USAGE (read-only; runs inside one READ ONLY transaction):

    python scripts/audit_reserved_oauth_clients.py            # table
    python scripts/audit_reserved_oauth_clients.py --json     # JSON lines

The script is self-contained (standard library + SQLAlchemy + psycopg2), so it
also runs in a pod whose image predates the registry module, piped on stdin:

    kubectl -n janua exec -i deploy/janua-api -- python - --json \\
        < apps/api/scripts/audit_reserved_oauth_clients.py

The database URL comes from ``DIRECT_DATABASE_URL``, else ``DATABASE_URL``
(the alembic precedence) and is never printed. Exit status: 0 when nothing
needs review, 2 when at least one row does, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Reserved values: a COPY of app/core/reserved_oauth_boundaries.py, so this
# runs against an image that predates it. A unit test fails if they drift.
# ---------------------------------------------------------------------------

RESERVED_AUDIENCE_PREFIXES = ("janua-",)
RESERVED_AUDIENCES = frozenset(
    {
        "janua-email",
        "janua-white-label",
        "janua-connections",
        "karafiel-api",
        "dhanam-api",
        "yantra4d-api",
        "pravara-api",
        "asset-shells-api",
        "creator-census-api",
    }
)
RESERVED_SCOPES = frozenset(
    {
        "crea-map:payment-mail",
        "white-label:branding",
        "connections:delegate",
        "madfam:silent_auth",
        "admin",
        "cfdi:issue",
        "billing:events",
        "legal:draft",
        "legal:client-profile",
        "yantra4d:render",
        "pravara-mes:jobs",
        "pravara-mes:nodes",
        "pravara-mes:passports",
        "pravara-mes:read",
        "asset-shells:read",
        "asset-shells:publish-types",
        "asset-shells:publish-instances",
    }
)
RESERVED_SCOPE_SUFFIXES = (":admin",)
FIRST_PARTY_NAME_PREFIXES = ("selva-office", "madfam-")
RESERVED_CLIENT_NAMES = frozenset({"creator-census", "creator-census-reauth"})

PAYMENT_MAIL_AUDIENCE = "janua-email"
PAYMENT_MAIL_SCOPE = "crea-map:payment-mail"


def reserved_fields(
    name: Optional[str], audience: Optional[str], scopes: Optional[Iterable[str]]
) -> list[str]:
    fields = []
    value = (name or "").strip().lower()
    if value.startswith(FIRST_PARTY_NAME_PREFIXES) or value in {
        n.lower() for n in RESERVED_CLIENT_NAMES
    }:
        fields.append("name")
    aud = (audience or "").strip()
    if aud and (aud in RESERVED_AUDIENCES or aud.startswith(RESERVED_AUDIENCE_PREFIXES)):
        fields.append("audience")
    if any(
        s and (s.strip() in RESERVED_SCOPES or s.strip().endswith(RESERVED_SCOPE_SUFFIXES))
        for s in (scopes or [])
    ):
        fields.append("allowed_scopes")
    return fields


def classify(row: dict) -> dict:
    """Pure: the audit verdict for one client row (see module docstring)."""
    scopes = _as_list(row.get("allowed_scopes"))
    grants = _as_list(row.get("grant_types"))
    reserved = reserved_fields(row.get("name"), row.get("audience"), scopes)
    machine = "client_credentials" in grants
    org_bound = row.get("organization_id") is not None
    listed = bool(reserved) or machine or org_bound
    creator_admin = bool(row.get("creator_is_admin"))
    reasons = []
    if not creator_admin:
        if reserved:
            reasons.append("reserved:" + "+".join(reserved))
        if machine and not org_bound:
            reasons.append("client_credentials_without_org")
        if org_bound and not row.get("creator_is_org_admin"):
            reasons.append("org_bound_by_non_org_admin")
    verdict = "ok" if creator_admin else ("review" if reasons else "info")
    payment_mail_grant = (
        (row.get("audience") or "") == PAYMENT_MAIL_AUDIENCE
        and PAYMENT_MAIL_SCOPE in scopes
        and machine
    )
    return {
        "listed": listed,
        "verdict": verdict,
        "reasons": reasons,
        "reserved_fields": reserved,
        "client_credentials": machine,
        "payment_mail_grant": payment_mail_grant,
        "refused_after_deploy": bool(
            payment_mail_grant and not creator_admin and row.get("is_active")
        ),
    }


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value]
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


# ---------------------------------------------------------------------------
# Database access (read-only)
# ---------------------------------------------------------------------------

CLIENTS_SQL = """
SELECT c.id::text              AS id,
       c.client_id             AS client_id,
       c.name                  AS name,
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
       CASE
         WHEN c.organization_id IS NULL THEN NULL
         ELSE (
           o.owner_id IS NOT NULL AND o.owner_id = c.created_by
           OR EXISTS (
             SELECT 1 FROM organization_members m
              WHERE m.organization_id = c.organization_id
                AND m.user_id = c.created_by
                AND m.role IN ('admin', 'owner')
                AND m.status = 'active'
           )
         )
       END                     AS creator_is_org_admin
  FROM oauth_clients c
  LEFT JOIN users u ON u.id = c.created_by
  LEFT JOIN organizations o ON o.id = c.organization_id
 ORDER BY c.created_at
"""

DISPATCH_SQL = """
SELECT client_id::text AS client_id, count(*) AS n, max(created_at) AS last_at
  FROM payment_mail_dispatches GROUP BY client_id
"""

AUDIT_SQL = """
SELECT resource_id::text AS client_id, action, count(*) AS n
  FROM audit_logs
 WHERE resource_type = 'oauth_client'
 GROUP BY resource_id, action
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


def collect(url: str) -> list[dict]:
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            tables = set(inspect(conn).get_table_names())
            rows = [dict(r._mapping) for r in conn.execute(text(CLIENTS_SQL))]
            dispatches = {}
            if "payment_mail_dispatches" in tables:
                dispatches = {
                    r.client_id: (int(r.n), r.last_at) for r in conn.execute(text(DISPATCH_SQL))
                }
            audit: dict[str, dict[str, int]] = {}
            if "audit_logs" in tables:
                for r in conn.execute(text(AUDIT_SQL)):
                    audit.setdefault(r.client_id, {})[r.action] = int(r.n)
            conn.rollback()
    finally:
        engine.dispose()

    report = []
    for row in rows:
        verdict = classify(row)
        if not verdict["listed"]:
            continue
        count, last_at = dispatches.get(row["id"], (0, None))
        report.append(
            {
                "id": row["id"],
                "client_id": row["client_id"],
                "organization_id": row["organization_id"],
                "created_by": row["created_by"],
                "creator_is_admin": bool(row["creator_is_admin"]),
                "creator_missing": bool(row["creator_missing"]),
                "creator_is_org_admin": row["creator_is_org_admin"],
                "is_active": bool(row["is_active"]),
                "is_confidential": bool(row["is_confidential"]),
                "created_at": _iso(row["created_at"]),
                "last_used_at": _iso(row["last_used_at"]),
                "payment_mail_dispatches": count,
                "last_payment_mail_dispatch_at": _iso(last_at),
                "audit_actions": audit.get(row["id"], {}),
                **{k: v for k, v in verdict.items() if k != "listed"},
            }
        )
    return report


def _iso(value) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def summary(report: list[dict]) -> dict:
    return {
        "listed": len(report),
        "ok": sum(r["verdict"] == "ok" for r in report),
        "review": sum(r["verdict"] == "review" for r in report),
        "info": sum(r["verdict"] == "info" for r in report),
        "review_ever_used": sum(
            r["verdict"] == "review" and (r["last_used_at"] or r["payment_mail_dispatches"])
            for r in report
        ),
        "review_with_payment_mail_dispatches": sum(
            r["verdict"] == "review" and r["payment_mail_dispatches"] > 0 for r in report
        ),
        "active_payment_mail_clients_refused_after_deploy": sum(
            r["refused_after_deploy"] for r in report
        ),
    }


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
            "verdict", "id", "client_id", "organization_id", "created_by", "creator_admin",
            "creator_org_admin", "active", "cc", "reserved", "created_at", "last_used_at",
            "mail_dispatches", "reasons",
        )  # fmt: skip
        print("\t".join(header))
        for r in report:
            print(
                "\t".join(
                    str(v)
                    for v in (
                        r["verdict"], r["id"], r["client_id"], r["organization_id"],
                        r["created_by"], r["creator_is_admin"], r["creator_is_org_admin"],
                        r["is_active"], r["client_credentials"],
                        "+".join(r["reserved_fields"]) or "-", r["created_at"],
                        r["last_used_at"], r["payment_mail_dispatches"],
                        ",".join(r["reasons"]) or "-",
                    )  # fmt: skip
                )
            )
        print("summary", json.dumps(totals, sort_keys=True))
    return 2 if totals["review"] else 0


if __name__ == "__main__":
    sys.exit(main())
