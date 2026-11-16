"""Unwrap JSON values the ORM stored as JSON strings (one-off, idempotent, operator-run).

Until the JSON column type stopped encoding twice on PostgreSQL (app/models/types.py), every ORM write landed as a
JSON *string* holding the encoded document: ``jsonb_typeof(col) = 'string'`` with ``col #>> '{}'`` = ``'{"a": 1}'``.
The ORM read both shapes, but SQL-level JSON queries (``@>``, ``->>``, paths) never matched those rows. This script
turns each such string back into the object or array it holds, in every ``jsonb`` column of the ``public`` schema.

Only strings whose text parses to a JSON object or array are touched; a genuine string value is left alone. Run it
after the fixed type is live, so nothing re-encodes behind it. Dry run by default (counts only, nothing written);
``--apply`` rewrites in one transaction and re-counts. Prints table/column names and counts, never values.

    kubectl -n janua exec -i deploy/janua-api -c janua-api -- python - < apps/api/scripts/normalize_jsonb_strings.py
    kubectl -n janua exec -i deploy/janua-api -c janua-api -- python - --apply < apps/api/scripts/normalize_jsonb_strings.py

(``python -`` reads the script from stdin; the arguments after ``-`` reach it in ``sys.argv``.)
"""

from __future__ import annotations

import asyncio
import os
import sys

TRY_JSONB = """
CREATE OR REPLACE FUNCTION pg_temp.janua_try_jsonb(t text) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    RETURN t::jsonb;
EXCEPTION WHEN others THEN
    RETURN NULL;
END $$
"""

#: A row is wrapped when it is a JSON string whose text is itself a JSON object or array.
WRAPPED = (
    "jsonb_typeof({col}) = 'string' "
    "AND jsonb_typeof(pg_temp.janua_try_jsonb({col} #>> '{{}}')) IN ('object', 'array')"
)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


async def columns(conn) -> list[tuple[str, str]]:
    rows = await conn.fetch(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND data_type = 'jsonb' ORDER BY table_name, column_name"
    )
    return [(r["table_name"], r["column_name"]) for r in rows]


async def count_wrapped(conn, table: str, col: str) -> int:
    return await conn.fetchval(f"SELECT count(*) FROM {quote(table)} WHERE {WRAPPED.format(col=quote(col))}")


async def run(url: str, apply: bool) -> dict[str, int]:
    import asyncpg

    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        await conn.execute(TRY_JSONB)
        found: dict[str, int] = {}
        for table, col in await columns(conn):
            n = await count_wrapped(conn, table, col)
            if n:
                found[f"{table}.{col}"] = n
        print(("would unwrap" if not apply else "unwrapping"), sum(found.values()), "values in", len(found), "columns")
        for name, n in found.items():
            print(f"  {name}: {n}")
        if apply and found:
            async with conn.transaction():
                for name in found:
                    table, col = name.split(".", 1)
                    q = quote(col)
                    # A value encoded more than once unwraps one level per pass; stop when nothing is left.
                    for _ in range(5):
                        status = await conn.execute(
                            f"UPDATE {quote(table)} SET {q} = pg_temp.janua_try_jsonb({q} #>> '{{}}') "
                            f"WHERE {WRAPPED.format(col=q)}"
                        )
                        if status.endswith(" 0"):
                            break
            left = {name: await count_wrapped(conn, *name.split(".", 1)) for name in found}
            print("left after apply:", sum(left.values()))
            return left
        return found
    finally:
        await conn.close()


def main(argv: list[str]) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    apply = "--apply" in argv
    result = asyncio.run(run(url, apply))
    return 1 if apply and any(result.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
