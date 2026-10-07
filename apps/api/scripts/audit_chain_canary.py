#!/usr/bin/env python3
"""Read-only canary for the audit_logs hash chain after a deploy.

Answers two questions, inside one READ ONLY transaction, with counts only:

1. Did the running audit logger write chained rows since ``--since``? Counts
   ``audit_logs`` rows with ``event_type`` and ``current_hash`` set and
   ``created_at`` at or after that time (UTC, the column's own clock).
2. Do the chains it wrote verify? For every tenant with a chained row since
   ``--since`` (at most ``--max-tenants``, newest first), walks the tenant's
   whole chain in ``(created_at, id)`` order, the way
   ``AuditLogger.verify_integrity`` does: the first entry starts the chain, each
   ``previous_hash`` is the previous ``current_hash``, and each ``current_hash``
   is recomputed with the running image's ``AuditLogger`` hash.

It never prints tenant ids, row contents, hashes or the database URL, and it
writes nothing. It needs an image that includes migration 020's audit logger,
so run it in the api pod after the promote, piped on stdin:

    ssh ssh.madfam.io "sudo kubectl -n janua exec -i deploy/janua-api -- python - --json --since 2026-10-01T18:00:00" \\
        < apps/api/scripts/audit_chain_canary.py

``--since`` is a UTC time (``YYYY-MM-DDTHH:MM:SS``); the default is one hour ago.
The database URL comes from ``DIRECT_DATABASE_URL``, else ``DATABASE_URL``.
Exit status: 0 when at least one chained row exists since ``--since`` and every
checked chain verifies; 2 when there is no such row yet, or a chain does not
verify; 1 on error.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ATTENTION = 2


def _database_url_from(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://", 1)
        .split("?")[0]
    )


def _database_url() -> str:
    url = os.environ.get("DIRECT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DIRECT_DATABASE_URL / DATABASE_URL is not set")
    return _database_url_from(url)


def _redact(message: str) -> str:
    for name in ("DIRECT_DATABASE_URL", "DATABASE_URL"):
        url = os.environ.get(name)
        if url:
            message = message.replace(url, "<url>").replace(_database_url_from(url), "<url>")
    return message


def _import_app():
    here = globals().get("__file__", "")
    if here.endswith(".py"):
        # Run as a file from apps/api/scripts: make `app` importable.
        sys.path.insert(0, str(Path(here).resolve().parents[1]))
    # Importing the app package logs its startup lines; keep stdout for the report.
    with contextlib.redirect_stdout(sys.stderr):
        from app.models import AuditLog
        from app.services.audit_logger import AuditLogger
    return AuditLog, AuditLogger


def first_break(rows: List[Any], row_hash) -> Optional[int]:
    """Index of the first entry that breaks the chain, or None if it verifies."""
    previous_hash = None
    for index, row in enumerate(rows):
        if row.previous_hash != previous_hash or row_hash(row) != row.current_hash:
            return index
        previous_hash = row.current_hash
    return None


def collect(url: str, since: datetime, max_tenants: int) -> Dict[str, Any]:
    from sqlalchemy import create_engine, func, select, text
    from sqlalchemy.orm import Session

    AuditLog, AuditLogger = _import_app()
    # Only the hash is used: no session, no R2 client.
    hasher = AuditLogger(None, r2_client=object())

    chained = AuditLog.event_type.is_not(None) & AuditLog.current_hash.is_not(None)
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            database = session.execute(text("SELECT current_database()")).scalar()
            since_count = session.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(chained, AuditLog.created_at >= since)
            ).scalar()
            total_count = session.execute(
                select(func.count()).select_from(AuditLog).where(chained)
            ).scalar()
            recent = session.execute(
                select(AuditLog.tenant_id, func.max(AuditLog.created_at).label("last"))
                .where(chained, AuditLog.created_at >= since)
                .group_by(AuditLog.tenant_id)
                .order_by(func.max(AuditLog.created_at).desc())
                .limit(max_tenants)
            ).all()
            checked = []
            for tenant_id, _last in recent:
                rows = (
                    session.execute(
                        select(AuditLog)
                        .where(AuditLog.tenant_id == tenant_id, AuditLog.current_hash.is_not(None))
                        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
                    )
                    .scalars()
                    .all()
                )
                checked.append(
                    {"entries": len(rows), "broken_at": first_break(rows, hasher._row_hash)}
                )
            session.rollback()
    finally:
        engine.dispose()

    broken = [c for c in checked if c["broken_at"] is not None]
    return {
        "database": database,
        "since": since.isoformat(),
        "chained_rows_since": since_count,
        "chained_rows_total": total_count,
        "tenants_checked": len(checked),
        "tenants_valid": len(checked) - len(broken),
        "tenants_broken": len(broken),
        "broken": broken,
        "ok": bool(since_count) and not broken,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    parser.add_argument(
        "--since",
        type=datetime.fromisoformat,
        default=None,
        help="UTC time, YYYY-MM-DDTHH:MM:SS (default: one hour ago)",
    )
    parser.add_argument("--max-tenants", type=int, default=20, help="most recent tenants to verify")
    args = parser.parse_args(argv)
    since = args.since or datetime.utcnow() - timedelta(hours=1)

    try:
        report = collect(_database_url(), since, args.max_tenants)
    except Exception as e:
        print(f"ERROR: {_redact(f'{type(e).__name__}: {e}')}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"database: {report['database']}")
        print(f"since: {report['since']}")
        print(f"chained rows since: {report['chained_rows_since']}")
        print(f"chained rows total: {report['chained_rows_total']}")
        print(
            f"tenants checked: {report['tenants_checked']}, valid: {report['tenants_valid']}, "
            f"broken: {report['tenants_broken']}"
        )
        for item in report["broken"]:
            print(f"BROKEN chain of {item['entries']} entries at index {item['broken_at']}")
        print("CANARY: OK" if report["ok"] else "CANARY: ATTENTION")
    return EXIT_OK if report["ok"] else EXIT_ATTENTION


if __name__ == "__main__":
    sys.exit(main())
