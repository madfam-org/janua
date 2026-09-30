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

Both lists count only clients the token endpoint would issue a
``client_credentials`` token to, reading ``grant_types`` and
``allowed_scopes`` exactly as the app does (see ``app_grant_types``).

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


# How the app reads a client row, as a COPY so this runs against an image that
# predates it; unit tests fail if any of it drifts from the app.
#
# A JSON column goes through two steps in the app: the database driver decodes
# the stored JSON once, then the model type (`app/models/types.JSON.
# process_result_value`) decodes a resulting string once more. So a stored
# JSON array and a stored JSON string holding array text both load as a list,
# while a string that is not JSON text cannot be loaded at all (the request
# fails). The token endpoint then takes the loaded value as-is
# (`oauth_provider._client_grant_types` / `_client_allowed_scopes`:
# ``set(value or default)``).
#
# Row values handed to ``classify`` are the DRIVER-decoded values (one decode),
# which ``collect`` produces deterministically from ``::text``.
DEFAULT_CLIENT_GRANT_TYPES = ("authorization_code", "refresh_token")
DEFAULT_CLIENT_SCOPES = ("openid", "profile", "email")


class Unloadable(Exception):
    """The app cannot load this value, so it serves no token for the row."""


def app_loaded(value):
    """COPY of `app/models/types.JSON.process_result_value`."""
    if value is not None:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError as error:
                raise Unloadable from error
    return value


def _as_app_set(value, default) -> set:
    """``set(loaded or default)`` as the app computes it; empty when it cannot.

    A value the app cannot load, or cannot turn into a set (a number, a
    boolean, a list holding an object), makes it fail the token request, so
    it grants nothing.
    """
    try:
        return set(app_loaded(value) or default)
    except (Unloadable, TypeError):
        return set()


def app_grant_types(value) -> set:
    return _as_app_set(value, DEFAULT_CLIENT_GRANT_TYPES)


def app_allowed_scopes(value) -> set:
    return _as_app_set(value, DEFAULT_CLIENT_SCOPES)


def app_loads(value) -> bool:
    try:
        app_loaded(value)
    except Unloadable:
        return False
    return True


def app_product_tiers(value) -> Optional[dict]:
    """The organization's tiers as the claims builder reads them (``loaded or {}``).

    None when the builder cannot read them (unloadable, or a non-empty value
    that is not an object): the app then fails every token request for the
    organization's clients, so nothing about those tokens changes.
    """
    try:
        loaded = app_loaded(value) or {}
    except Unloadable:
        return None
    return loaded if isinstance(loaded, dict) else None


def classify(row: dict) -> dict:
    """Pure: what the provenance rules change for one client row.

    ``row`` needs ``allowed_scopes``, ``grant_types``, ``redirect_uris``,
    ``audience``, ``creator_is_admin``, ``is_active``, ``is_confidential`` and
    ``product_tiers`` (the organization's, or None when unbound or missing),
    the JSON ones as the driver decodes them. A client is considered only when
    the app would issue it a ``client_credentials`` token: the grant is in its
    grant types, it is confidential, its row loads, and its organization's
    tiers are readable. (Other organization columns are not examined; one the
    app could not load would only make this audit list more, never less.)
    """
    grants = app_grant_types(row.get("grant_types"))
    scopes = app_allowed_scopes(row.get("allowed_scopes"))
    tiers = app_product_tiers(row.get("product_tiers"))
    machine = (
        "client_credentials" in grants
        and bool(row.get("is_confidential"))
        and app_loads(row.get("redirect_uris"))
        and tiers is not None
    )
    admin = bool(row.get("creator_is_admin"))
    active = bool(row.get("is_active"))

    dropped: list[str] = []
    if machine and not admin:
        # Only string scopes can be requested, so only they reach a token.
        scoped = {claim_key(s.split(":", 1)[0]) for s in scopes if isinstance(s, str) and ":" in s}
        entitled = {claim_key(p) for p in tiers or {}}
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
        "refused_after_deploy": bool(connections and active),
        "changes_active_client": bool(active and (dropped or connections)),
    }


# ---------------------------------------------------------------------------
# Database access (read-only)
# ---------------------------------------------------------------------------

CLIENTS_SQL = """
SELECT c.id::text              AS id,
       c.client_id             AS client_id,
       c.audience              AS audience,
       c.allowed_scopes::text  AS allowed_scopes,
       c.grant_types::text     AS grant_types,
       c.redirect_uris::text   AS redirect_uris,
       c.organization_id::text AS organization_id,
       c.created_by::text      AS created_by,
       c.is_active             AS is_active,
       c.is_confidential       AS is_confidential,
       c.created_at            AS created_at,
       c.last_used_at          AS last_used_at,
       COALESCE(u.is_admin, false) AS creator_is_admin,
       (u.id IS NULL)          AS creator_missing,
       o.product_tiers::text   AS product_tiers
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
    for row in rows:
        # The driver's one decode, done here so it does not depend on how the
        # driver happens to be configured in this process.
        for column in JSON_COLUMNS:
            if row[column] is not None:
                row[column] = json.loads(row[column])
    return report_rows(rows)


JSON_COLUMNS = ("allowed_scopes", "grant_types", "redirect_uris", "product_tiers")


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
