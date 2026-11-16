"""PostgreSQL proof that ORM JSON writes are real JSON again, and that the cleanup unwraps legacy rows.

On a scratch database migrated to head: an ORM write stores an object/array (not a string), `@>` containment finds
it (the webhook-endpoint and audit queries depend on that), a legacy double-encoded row still reads back as a dict,
and scripts/normalize_jsonb_strings.py turns it into a real object so the same query finds it too.

The driver work runs in a subprocess: psycopg2 is mocked inside the test process (see test_migration_reentrancy).
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

PROGRAM = r'''
import asyncio, json, os, sys, uuid
sys.path.insert(0, os.environ["API_ROOT"])
sys.path.insert(0, os.path.join(os.environ["API_ROOT"], "scripts"))
from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.models import Organization, WebhookEndpoint
from app.models.types import JSON
import normalize_jsonb_strings as normalize

async def main():
    url = os.environ["U"]
    engine = create_async_engine(url)
    out = {}
    async with AsyncSession(engine) as db:
        org = Organization(name="Prueba", slug="prueba-" + uuid.uuid4().hex[:6], product_tiers={"dhanam": "pro"}, settings={"k": "v"})
        db.add(org)
        await db.flush()
        org_id = org.id  # read before commit: a committed object expires, and a lazy reload needs a greenlet
        # Explicit columns: the model declares columns the migrations never create (description, max_retries, ...).
        # `events` is still bound through Janua's JSON type, which is what this test is about.
        await db.execute(
            text("INSERT INTO webhook_endpoints (id, url, organization_id, events, is_active) VALUES (:id, :url, :org, :events, true)")
            .bindparams(bindparam("events", type_=JSON())),
            {"id": uuid.uuid4(), "url": "https://example.test/hook", "org": org_id, "events": ["user.created", "user.deleted"]},
        )
        await db.commit()
        out["typeof"] = (await db.execute(text("SELECT jsonb_typeof(product_tiers), jsonb_typeof(settings) FROM organizations WHERE id = :i"), {"i": org_id})).one()._tuple()
        out["events_typeof"] = (await db.execute(text("SELECT jsonb_typeof(events) FROM webhook_endpoints"))).scalar_one()
        out["contains_event"] = len((await db.execute(select(WebhookEndpoint.id).where(WebhookEndpoint.events.contains(["user.deleted"])))).scalars().all())
        out["contains_tier"] = len((await db.execute(select(Organization.id).where(Organization.product_tiers.contains({"dhanam": "pro"})))).scalars().all())
        # A legacy row, stored the way the old type stored it: a JSON string holding the document.
        await db.execute(text("UPDATE organizations SET settings = to_jsonb(CAST('{\"k\": \"legacy\"}' AS text)) WHERE id = :i"), {"i": org_id})
        await db.commit()
        db.expire_all()
        out["legacy_read"] = (await db.execute(select(Organization.settings).where(Organization.id == org_id))).scalar_one()
        out["legacy_contains_before"] = len((await db.execute(select(Organization.id).where(Organization.settings.contains({"k": "legacy"})))).scalars().all())
    out["dry_run"] = await normalize.run(os.environ["U_PLAIN"], apply=False)
    out["left_after_apply"] = await normalize.run(os.environ["U_PLAIN"], apply=True)
    async with AsyncSession(engine) as db:
        out["legacy_contains_after"] = len((await db.execute(select(Organization.id).where(Organization.settings.contains({"k": "legacy"})))).scalars().all())
        out["settings_typeof_after"] = (await db.execute(text("SELECT jsonb_typeof(settings) FROM organizations"))).scalar_one()
    await engine.dispose()
    print("RESULT=" + json.dumps(out))

asyncio.run(main())
'''


@pytest.fixture(scope="module")
def database():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI") or os.environ.get("JANUA_REQUIRE_LOCAL_PG_TESTS"):
            pytest.fail(f"{URL_ENV_VAR} must reach the isolated PostgreSQL service")
        pytest.skip(f"{URL_ENV_VAR} is not configured locally")
    name = f"janua_json_{uuid.uuid4().hex[:10]}"
    assert _psql(f'CREATE DATABASE "{name}"', base, autocommit=True).returncode == 0
    url = _with_database(base, name)
    try:
        migrated = _alembic(["upgrade", "head"], url)
        assert migrated.returncode == 0, migrated.stderr[-2000:]
        yield url
    finally:
        _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def test_orm_json_is_real_json_and_the_cleanup_unwraps_legacy_rows(database):
    async_url = database.replace("postgresql://", "postgresql+asyncpg://", 1) if "+asyncpg" not in database else database
    plain_url = async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    run = subprocess.run(
        [sys.executable, "-c", PROGRAM],
        env={**os.environ, "U": async_url, "U_PLAIN": plain_url, "API_ROOT": str(API_ROOT), "DATABASE_URL": async_url},
        capture_output=True, text=True, timeout=300,
    )
    line = next((row for row in run.stdout.splitlines() if row.startswith("RESULT=")), None)
    assert line, f"{run.stdout[-2000:]}\n{run.stderr[-4000:]}"
    out = json.loads(line.removeprefix("RESULT="))
    assert out["typeof"] == ["object", "object"], "an ORM write must store a JSON object, not a string"
    assert out["events_typeof"] == "array"
    assert out["contains_event"] == 1, "webhook endpoint matching (@>) must find an ORM-written endpoint"
    assert out["contains_tier"] == 1
    assert out["legacy_read"] == {"k": "legacy"}, "a legacy string row still reads back as a dict"
    assert out["legacy_contains_before"] == 0, "a legacy string row is invisible to @> (the bug)"
    assert out["dry_run"] == {"organizations.settings": 1}
    assert out["left_after_apply"] == {"organizations.settings": 0}
    assert out["legacy_contains_after"] == 1, "after the cleanup the same query finds it"
    assert out["settings_typeof_after"] == "object"
