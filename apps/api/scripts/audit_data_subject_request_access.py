#!/usr/bin/env python3
"""Read-only counts of data subject requests and who last processed them.

Data subject requests are available only to their data subject and to
platform administrators. This script reports, as counts only, what the
database can say about how existing requests were processed:

- how many data subject requests exist, by type and by status;
- for each request type, who last processed each request (the
  ``assigned_to`` column the processing path sets): nobody yet, the request's
  own subject, a platform administrator (``users.is_admin`` today), another
  user, or a user row that no longer exists;
- audit-log rows about data subject requests or GDPR events, by action.

What the schema cannot tell (printed in the output as ``not_knowable``):

- ``assigned_to`` keeps only the LAST processor of a request. Every export of
  an access request overwrites it, so an earlier export by someone else is
  invisible once the subject (or anyone) exports it again.
- The export path writes no audit-log row, so no table records each export,
  its caller, or how many times a request was exported.
- ``users.is_admin`` is read as it is today, not as it was at export time.

No ids, emails, names or personal data are selected or printed; the per-row
query returns only types, statuses and booleans, which are aggregated here.

USAGE (read-only; runs inside one READ ONLY transaction):

    python scripts/audit_data_subject_request_access.py            # text
    python scripts/audit_data_subject_request_access.py --json     # one JSON object

The script is self-contained (standard library + SQLAlchemy + psycopg2), so it
also runs in a pod, piped on stdin:

    kubectl -n janua exec -i deploy/janua-api -- python - --json \\
        < apps/api/scripts/audit_data_subject_request_access.py

The database URL comes from ``DIRECT_DATABASE_URL``, else ``DATABASE_URL``
(the alembic precedence) and is never printed. Exit status: 0 when no request
was last processed by someone other than its subject or a platform
administrator, 2 when at least one was (or its processor no longer exists), 1
on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Iterable, Optional

LAST_PROCESSOR_CATEGORIES = (
    "not_processed",
    "subject",
    "platform_admin",
    "other_user",
    "missing_user",
)

NOT_KNOWABLE = [
    "earlier processors of a request: assigned_to keeps only the last one",
    "each export, its caller and how often a request was exported: "
    "the export path writes no audit-log row",
    "whether a processor was a platform administrator at export time: "
    "users.is_admin is read as it is today",
]


def last_processor_category(row: dict) -> str:
    """Pure: who last processed one request (see module docstring)."""
    if not row.get("processed"):
        return "not_processed"
    if row.get("by_subject"):
        return "subject"
    if row.get("assignee_missing"):
        return "missing_user"
    if row.get("assignee_is_admin"):
        return "platform_admin"
    return "other_user"


def summarize(rows: Iterable[dict], audit_actions: Optional[dict] = None) -> dict:
    """Pure: aggregate per-request rows into the report (counts only)."""
    by_type: Counter = Counter()
    by_status: Counter = Counter()
    by_type_status: dict = {}
    last_processor: dict = {}
    total = 0
    for row in rows:
        total += 1
        request_type = str(row.get("request_type") or "unknown")
        status = str(row.get("status") or "unknown")
        by_type[request_type] += 1
        by_status[status] += 1
        by_type_status.setdefault(request_type, Counter())[status] += 1
        category = last_processor_category(row)
        bucket = last_processor.setdefault(
            request_type, dict.fromkeys(LAST_PROCESSOR_CATEGORIES, 0)
        )
        bucket[category] += 1

    other = sum(bucket["other_user"] for bucket in last_processor.values())
    missing = sum(bucket["missing_user"] for bucket in last_processor.values())
    return {
        "data_subject_requests": total,
        "by_type": dict(sorted(by_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_type_and_status": {
            key: dict(sorted(value.items())) for key, value in sorted(by_type_status.items())
        },
        "last_processor_by_type": dict(sorted(last_processor.items())),
        "last_processed_by_other_user": other,
        "last_processed_by_missing_user": missing,
        "audit_log_rows_by_action": dict(sorted((audit_actions or {}).items())),
        "audit_log_table_present": audit_actions is not None,
        "not_knowable": NOT_KNOWABLE,
    }


# ---------------------------------------------------------------------------
# Database access (read-only)
# ---------------------------------------------------------------------------

# Types, statuses and booleans only: no ids leave the database.
REQUESTS_SQL = """
SELECT CAST(r.request_type AS TEXT)        AS request_type,
       CAST(r.status AS TEXT)              AS status,
       (r.assigned_to IS NOT NULL)         AS processed,
       (r.assigned_to = r.user_id)         AS by_subject,
       COALESCE(u.is_admin, false)         AS assignee_is_admin,
       (r.assigned_to IS NOT NULL AND u.id IS NULL) AS assignee_missing
  FROM data_subject_requests r
  LEFT JOIN users u ON u.id = r.assigned_to
"""

AUDIT_SQL = """
SELECT action, count(*) AS n
  FROM audit_logs
 WHERE resource_type IN ('data_subject_request', 'user_data')
    OR action LIKE 'gdpr.%'
 GROUP BY action
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


def collect(url: str) -> dict:
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            tables = set(inspect(conn).get_table_names())
            if "data_subject_requests" not in tables:
                conn.rollback()
                raise RuntimeError("data_subject_requests table not found")
            rows = [dict(r._mapping) for r in conn.execute(text(REQUESTS_SQL))]
            audit_actions = None
            if "audit_logs" in tables:
                audit_actions = {str(r.action): int(r.n) for r in conn.execute(text(AUDIT_SQL))}
            conn.rollback()
    finally:
        engine.dispose()
    return summarize(rows, audit_actions)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    args = parser.parse_args(argv)
    try:
        report = collect(_database_url())
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - report the class, never the URL
        print(f"audit failed: {type(error).__name__}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        for key in (
            "data_subject_requests",
            "by_type",
            "by_status",
            "by_type_and_status",
            "last_processor_by_type",
            "last_processed_by_other_user",
            "last_processed_by_missing_user",
            "audit_log_table_present",
            "audit_log_rows_by_action",
        ):
            print(f"{key}\t{json.dumps(report[key], sort_keys=True)}")
        for line in report["not_knowable"]:
            print(f"not_knowable\t{line}")
    needs_review = report["last_processed_by_other_user"] + report["last_processed_by_missing_user"]
    return 2 if needs_review else 0


if __name__ == "__main__":
    sys.exit(main())
