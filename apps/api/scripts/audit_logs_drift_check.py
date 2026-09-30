#!/usr/bin/env python3
"""Read-only drift check for ``audit_logs`` (migration 020_audit_log_hash_chain).

Compares, inside one READ ONLY transaction:

1. The ORM model with the database: every column ``Base.metadata`` maps on the
   checked tables must exist in ``information_schema.columns``. A model column
   the database lacks is drift: the running code would select or insert it and
   fail. This part reflects the image the script runs in.
2. Migration 020 with the database, independent of the image: ``audit_logs``
   must have ``event_type`` VARCHAR(100), ``tenant_id`` VARCHAR(255),
   ``current_hash`` VARCHAR(64) and ``previous_hash`` VARCHAR(64), all
   nullable; the index ``ix_audit_logs_tenant_chain`` on
   (tenant_id, created_at, id); and INSERT and SELECT on the new columns for
   the role the api connects as.

It also prints context, counts only: ``alembic_version``, the number of
``audit_logs`` rows, and how many carry a hash chain. It never prints row
contents or the database URL, and it writes nothing.

USAGE, from the repository root (the owner runs this; it is piped on stdin, so
it also runs in a pod whose image predates it):

    ssh ssh.madfam.io "sudo kubectl -n janua exec -i deploy/janua-api -- python - --json" \\
        < apps/api/scripts/audit_logs_drift_check.py

    python scripts/audit_logs_drift_check.py            # from apps/api: text
    python scripts/audit_logs_drift_check.py --all      # every model table, not only audit_logs

The database URL comes from ``DIRECT_DATABASE_URL``, else ``DATABASE_URL`` (the
alembic precedence), with the async driver swapped for psycopg2. Exit status: 0
when DRIFT-TOTAL is 0, 2 when it is not, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

TABLE = "audit_logs"
REVISION = "020_audit_log_hash_chain"
EXPECTED_COLUMNS: Dict[str, int] = {
    "event_type": 100,
    "tenant_id": 255,
    "current_hash": 64,
    "previous_hash": 64,
}
EXPECTED_INDEX = "ix_audit_logs_tenant_chain"
EXPECTED_INDEX_COLUMNS = ("tenant_id", "created_at", "id")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DRIFT = 2


def _database_url() -> str:
    url = os.environ.get("DIRECT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DIRECT_DATABASE_URL / DATABASE_URL is not set")
    return _database_url_from(url)


def _redact(message: str) -> str:
    """``message`` with any database URL from the environment replaced."""
    for name in ("DIRECT_DATABASE_URL", "DATABASE_URL"):
        url = os.environ.get(name)
        if url:
            message = message.replace(url, "<url>")
            message = message.replace(_database_url_from(url), "<url>")
    return message


def _database_url_from(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://", 1)
        .split("?")[0]
    )


def model_columns(tables: Optional[List[str]]) -> Dict[str, List[str]]:
    """Columns the ORM maps, per table (``tables=None``: every model table)."""
    here = globals().get("__file__", "")
    if here.endswith(".py"):
        # Run as a file from apps/api/scripts: make `app` importable.
        sys.path.insert(0, str(Path(here).resolve().parents[1]))
    from app.models import Base

    selected = sorted(Base.metadata.tables) if tables is None else tables
    return {
        name: sorted(column.name for column in Base.metadata.tables[name].columns)
        for name in selected
        if name in Base.metadata.tables
    }


def collect(url: str, tables: Optional[List[str]]) -> Dict[str, Any]:
    from sqlalchemy import create_engine, text

    mapped = model_columns(tables)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            db_columns: Dict[str, Dict[str, Dict[str, Any]]] = {}
            for row in conn.execute(
                text(
                    "SELECT table_name, column_name, data_type, character_maximum_length, "
                    "is_nullable FROM information_schema.columns "
                    "WHERE table_schema = current_schema()"
                )
            ):
                db_columns.setdefault(row.table_name, {})[row.column_name] = {
                    "type": row.data_type,
                    "length": row.character_maximum_length,
                    "nullable": row.is_nullable == "YES",
                }
            index = conn.execute(
                text(
                    "SELECT a.attname FROM pg_index i "
                    "JOIN pg_class c ON c.oid = i.indexrelid "
                    "JOIN pg_class t ON t.oid = i.indrelid "
                    "JOIN pg_namespace n ON n.oid = t.relnamespace "
                    "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true "
                    "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum "
                    "WHERE c.relname = :index AND t.relname = :table "
                    "AND n.nspname = current_schema() ORDER BY k.ord"
                ),
                {"index": EXPECTED_INDEX, "table": TABLE},
            )
            index_columns = [row.attname for row in index]
            present_new = [c for c in EXPECTED_COLUMNS if c in db_columns.get(TABLE, {})]
            privileges = {
                column: {
                    privilege: bool(
                        conn.execute(
                            text(
                                "SELECT has_column_privilege(current_user, :table, :column, "
                                ":privilege)"
                            ),
                            {"table": TABLE, "column": column, "privilege": privilege},
                        ).scalar()
                    )
                    for privilege in ("SELECT", "INSERT")
                }
                for column in present_new
            }
            version = None
            if "alembic_version" in db_columns:
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            counts: Dict[str, Optional[int]] = {"rows": None, "chained_rows": None}
            if TABLE in db_columns:
                counts["rows"] = conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar()
                if "current_hash" in db_columns[TABLE]:
                    counts["chained_rows"] = conn.execute(
                        text(f"SELECT count(*) FROM {TABLE} WHERE current_hash IS NOT NULL")
                    ).scalar()
            conn.rollback()
    finally:
        engine.dispose()

    problems: List[str] = []
    for table, columns in mapped.items():
        present = db_columns.get(table)
        if present is None:
            problems.append(f"model table {table} is missing in the database")
            continue
        for column in columns:
            if column not in present:
                problems.append(f"model column {table}.{column} is missing in the database")

    table_columns = db_columns.get(TABLE, {})
    for column, length in EXPECTED_COLUMNS.items():
        found = table_columns.get(column)
        if found is None:
            problems.append(f"{REVISION}: column {TABLE}.{column} is missing")
        elif (found["type"], found["length"], found["nullable"]) != (
            "character varying",
            length,
            True,
        ):
            problems.append(
                f"{REVISION}: column {TABLE}.{column} is {found['type']}({found['length']}) "
                f"nullable={found['nullable']}, expected character varying({length}) nullable"
            )
    if tuple(index_columns) != EXPECTED_INDEX_COLUMNS:
        problems.append(
            f"{REVISION}: index {EXPECTED_INDEX} on {TABLE} "
            + (f"covers {index_columns}" if index_columns else "is missing")
            + f", expected {list(EXPECTED_INDEX_COLUMNS)}"
        )
    for column, granted in privileges.items():
        for privilege, ok in granted.items():
            if not ok:
                problems.append(f"{REVISION}: current_user lacks {privilege} on {TABLE}.{column}")

    return {
        "alembic_version": version,
        "tables_checked": sorted(mapped),
        "audit_logs": counts,
        "problems": problems,
        "drift_total": len(problems),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    parser.add_argument(
        "--all", action="store_true", help="check every model table, not only audit_logs"
    )
    args = parser.parse_args(argv)

    try:
        report = collect(_database_url(), None if args.all else [TABLE])
    except Exception as e:
        print(f"ERROR: {_redact(f'{type(e).__name__}: {e}')}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"alembic_version: {report['alembic_version']}")
        print(f"tables checked: {', '.join(report['tables_checked'])}")
        print(
            f"{TABLE}: {report['audit_logs']['rows']} rows, "
            f"{report['audit_logs']['chained_rows']} with a hash chain"
        )
        for problem in report["problems"]:
            print(f"DRIFT {problem}")
        print(f"DRIFT-TOTAL: {report['drift_total']}")
    return EXIT_OK if report["drift_total"] == 0 else EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
