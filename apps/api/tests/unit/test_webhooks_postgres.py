"""PostgreSQL proof that a Janua event reaches its subscribed endpoint and is recorded (2026-11-16).

Before the fix nothing was ever delivered (0 rows in production's webhook_deliveries): the service used the sync
Session API on the AsyncSession the app passes, matched subscriptions with `.contains()` (LIKE on JSONB, rejected by
PostgreSQL), read a missing `settings.API_VERSION`, and built WebhookDelivery with fields the model does not have.

On a scratch database migrated to head and brought to PRODUCTION's webhook schema (the migrations lack columns that
production's tables have; idempotent ADD COLUMN IF NOT EXISTS with production's types, read on 2026-11-16), one
`user.created` event on a real AsyncSession: records the event, calls only the subscribed endpoint (HTTP stubbed),
and commits a DELIVERED delivery row. Driver work runs in a subprocess (psycopg2 is mocked in-process).
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from tests.unit.test_migration_reentrancy import (
    URL_ENV_VAR,
    _alembic,
    _postgres_url,
    _psql,
    _with_database,
)

pytestmark = pytest.mark.database
API_ROOT = Path(__file__).resolve().parents[2]

#: Production's webhook tables (information_schema, 2026-11-16), applied idempotently.
PRODUCTION_WEBHOOK_SCHEMA = """
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'webhookstatus') THEN
        CREATE TYPE webhookstatus AS ENUM ('PENDING', 'DELIVERED', 'FAILED', 'RETRYING');
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS legacy_webhook_events (
    id uuid PRIMARY KEY, type varchar(255) NOT NULL, data jsonb, user_id uuid, organization_id uuid, created_at timestamp
);
CREATE TABLE IF NOT EXISTS webhook_endpoints (id uuid PRIMARY KEY, url varchar(500) NOT NULL);
ALTER TABLE webhook_endpoints
    ADD COLUMN IF NOT EXISTS user_id uuid, ADD COLUMN IF NOT EXISTS organization_id uuid,
    ADD COLUMN IF NOT EXISTS secret varchar(255), ADD COLUMN IF NOT EXISTS events jsonb,
    ADD COLUMN IF NOT EXISTS is_active boolean, ADD COLUMN IF NOT EXISTS created_at timestamp,
    ADD COLUMN IF NOT EXISTS updated_at timestamp, ADD COLUMN IF NOT EXISTS description varchar(500),
    ADD COLUMN IF NOT EXISTS headers jsonb, ADD COLUMN IF NOT EXISTS max_retries integer,
    ADD COLUMN IF NOT EXISTS retry_delay integer, ADD COLUMN IF NOT EXISTS success_count integer,
    ADD COLUMN IF NOT EXISTS failure_count integer, ADD COLUMN IF NOT EXISTS last_success_at timestamp,
    ADD COLUMN IF NOT EXISTS last_failure_at timestamp;
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id uuid PRIMARY KEY, webhook_endpoint_id uuid NOT NULL, webhook_event_id uuid NOT NULL
);
ALTER TABLE webhook_deliveries
    ADD COLUMN IF NOT EXISTS status webhookstatus, ADD COLUMN IF NOT EXISTS attempts integer,
    ADD COLUMN IF NOT EXISTS last_attempt timestamp, ADD COLUMN IF NOT EXISTS next_retry_at timestamp,
    ADD COLUMN IF NOT EXISTS response_status integer, ADD COLUMN IF NOT EXISTS response_body text,
    ADD COLUMN IF NOT EXISTS error_message text, ADD COLUMN IF NOT EXISTS created_at timestamp,
    ADD COLUMN IF NOT EXISTS updated_at timestamp;
"""

PROGRAM = r'''
import asyncio, json, os, sys, uuid
sys.path.insert(0, os.environ["API_ROOT"])
from types import SimpleNamespace
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.services.webhooks import WebhookEventType, WebhookService

async def main():
    engine = create_async_engine(os.environ["U"])
    service = WebhookService()
    calls = []
    async def post(url, json=None, headers=None):
        calls.append({"url": url, "type": json["type"], "signed": bool(headers.get("X-Webhook-Signature"))})
        return SimpleNamespace(status_code=202, text="accepted")
    service.client = SimpleNamespace(post=post)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        for url, events in (("https://crm.example.test/hook", '["user.created"]'), ("https://other.example.test/hook", '["user.deleted"]')):
            await db.execute(
                text("INSERT INTO webhook_endpoints (id, url, secret, events, is_active) VALUES (:i, :u, 's', CAST(:e AS jsonb), true)"),
                {"i": uuid.uuid4(), "u": url, "e": events},
            )
        await db.commit()
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await service.trigger_event(db, WebhookEventType.USER_CREATED, {"id": "u1", "email": "ana@example.test"})
    async with AsyncSession(engine) as db:
        events = (await db.execute(text("SELECT count(*) FROM legacy_webhook_events WHERE type = 'user.created'"))).scalar_one()
        rows = (await db.execute(text("SELECT status::text, attempts, response_status FROM webhook_deliveries"))).all()
    await engine.dispose()
    print("RESULT=" + json.dumps({"calls": calls, "events": events, "deliveries": [list(r) for r in rows]}))

asyncio.run(main())
'''


@pytest.fixture(scope="module")
def database():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI") or os.environ.get("JANUA_REQUIRE_LOCAL_PG_TESTS"):
            pytest.fail(f"{URL_ENV_VAR} must reach the isolated PostgreSQL service")
        pytest.skip(f"{URL_ENV_VAR} is not configured locally")
    name = f"janua_hooks_{uuid.uuid4().hex[:10]}"
    assert _psql(f'CREATE DATABASE "{name}"', base, autocommit=True).returncode == 0
    url = _with_database(base, name)
    try:
        migrated = _alembic(["upgrade", "head"], url)
        assert migrated.returncode == 0, migrated.stderr[-2000:]
        shaped = _psql(PRODUCTION_WEBHOOK_SCHEMA, url, autocommit=True)
        assert shaped.returncode == 0, shaped.stderr[-2000:]
        yield url
    finally:
        _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def test_a_user_created_event_reaches_only_its_subscriber_and_is_recorded(database):
    async_url = database if "+asyncpg" in database else database.replace("postgresql://", "postgresql+asyncpg://", 1)
    run = subprocess.run(
        [sys.executable, "-c", PROGRAM],
        env={**os.environ, "U": async_url, "API_ROOT": str(API_ROOT), "DATABASE_URL": async_url},
        capture_output=True, text=True, timeout=300,
    )
    line = next((row for row in run.stdout.splitlines() if row.startswith("RESULT=")), None)
    assert line, f"{run.stdout[-2000:]}\n{run.stderr[-4000:]}"
    out = json.loads(line.removeprefix("RESULT="))
    assert out["calls"] == [{"url": "https://crm.example.test/hook", "type": "user.created", "signed": True}]
    assert out["events"] == 1
    assert out["deliveries"] == [["DELIVERED", 1, 202]]
