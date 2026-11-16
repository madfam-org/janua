"""Point webhook_deliveries.webhook_event_id at legacy_webhook_events (one-off, idempotent, operator-run).

The WebhookDelivery model declares `ForeignKey("legacy_webhook_events.id")`, and the webhook service records its
events in `legacy_webhook_events`; production's constraint pointed at `webhook_events` instead (a table with 0 rows
on 2026-11-16), so every delivery record would fail its foreign key. This re-points the constraint to match the model.

Refuses to change anything if a delivery references an event missing from legacy_webhook_events. Dry run by default
(prints the current target and counts); ``--apply`` drops the old constraint and adds the new one in one transaction.
Prints names and counts, never values.

    kubectl -n janua exec -i deploy/janua-api -c janua-api -- python - < apps/api/scripts/repoint_webhook_delivery_event_fk.py
    kubectl -n janua exec -i deploy/janua-api -c janua-api -- python - --apply < apps/api/scripts/repoint_webhook_delivery_event_fk.py
"""

from __future__ import annotations

import asyncio
import os
import sys

NEW_NAME = "fk_webhook_deliveries_webhook_event_id_legacy_webhook_events"

CURRENT = """
SELECT c.conname, t.relname AS target
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.confrelid
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
WHERE c.conrelid = 'public.webhook_deliveries'::regclass AND c.contype = 'f' AND a.attname = 'webhook_event_id'
"""

ORPHANS = """
SELECT count(*) FROM webhook_deliveries d
WHERE NOT EXISTS (SELECT 1 FROM legacy_webhook_events e WHERE e.id = d.webhook_event_id)
"""


async def run(url: str, apply: bool) -> dict:
    import asyncpg

    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        current = [(r["conname"], r["target"]) for r in await conn.fetch(CURRENT)]
        deliveries = await conn.fetchval("SELECT count(*) FROM webhook_deliveries")
        orphans = await conn.fetchval(ORPHANS)
        state = {"constraints": current, "deliveries": deliveries, "orphans": orphans}
        print("current:", current, "| deliveries:", deliveries, "| without a legacy event:", orphans)
        if all(target == "legacy_webhook_events" for _, target in current) and current:
            print("already points at legacy_webhook_events; nothing to do")
            state["changed"] = False
            return state
        if not apply:
            print("would re-point webhook_event_id to legacy_webhook_events (dry run)")
            state["changed"] = False
            return state
        if orphans:
            print("refusing: deliveries reference events missing from legacy_webhook_events", file=sys.stderr)
            state["changed"] = False
            return state
        async with conn.transaction():
            for name, target in current:
                if target != "legacy_webhook_events":
                    await conn.execute(f'ALTER TABLE webhook_deliveries DROP CONSTRAINT "{name}"')
            await conn.execute(
                f'ALTER TABLE webhook_deliveries ADD CONSTRAINT "{NEW_NAME}" '
                "FOREIGN KEY (webhook_event_id) REFERENCES legacy_webhook_events (id)"
            )
        state["constraints"] = [(r["conname"], r["target"]) for r in await conn.fetch(CURRENT)]
        state["changed"] = True
        print("now:", state["constraints"])
        return state
    finally:
        await conn.close()


def main(argv: list[str]) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    state = asyncio.run(run(url, "--apply" in argv))
    ok = all(target == "legacy_webhook_events" for _, target in state["constraints"]) and state["constraints"]
    return 0 if ("--apply" not in argv or ok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
