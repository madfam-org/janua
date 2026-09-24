"""018_email_events: the Alembic revision and the owner-applied SQL agree.

Production DDL is applied BY HAND from docs/ops/sql/018_email_events.sql (the
promote does not run migrations), while every other environment runs the
Alembic revision. Two artefacts describing one schema drift apart silently, so
this applies BOTH to scratch PostgreSQL databases and compares the catalogs:
columns (type, nullability, default), indexes and constraints. It also proves
the SQL refuses a database at the wrong revision without touching it, is
idempotent, leaves a database that a later `alembic upgrade head` treats as
current, that the receiver's insert path works on PostgreSQL, and that the
revision downgrades and re-upgrades cleanly.

Cost-conscious on purpose (the api-tests job has a 25-minute budget): two
scratch databases and two full-chain upgrades for the whole module.

Same harness and the same skip/fail rule as test_migration_reentrancy.py:
skips without MIGRATION_TEST_DATABASE_URL locally, FAILS without it in CI.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from tests.unit.test_migration_reentrancy import (
    URL_ENV_VAR,
    _alembic,
    _postgres_url,
    _psql,
    _with_database,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SQL_FILE = REPO_ROOT / "docs" / "ops" / "sql" / "018_email_events.sql"
HEAD = "018_email_events"
PARENT = "017_payment_mail_dispatch"
GRANDPARENT = "016_org_member_app_roles"


def _sql_script() -> str:
    """The owner file minus psql meta-commands (`\\set`), which only psql parses."""
    return "\n".join(
        line for line in SQL_FILE.read_text().splitlines() if not line.lstrip().startswith("\\")
    )


def _ok(result) -> str:
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def _version(url: str) -> str:
    return _ok(_psql("SELECT version_num FROM alembic_version", url))


def _table_absent(url: str) -> bool:
    return _ok(_psql("SELECT to_regclass('public.email_events')", url)) in ("", "None")


def _catalog(url: str) -> dict[str, str]:
    columns = _ok(
        _psql(
            "SELECT column_name, data_type, character_maximum_length, is_nullable, "
            "coalesce(column_default, '') FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'email_events' ORDER BY column_name",
            url,
        )
    )
    indexes = _ok(
        _psql(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = 'email_events' ORDER BY indexname",
            url,
        )
    )
    constraints = _ok(
        _psql(
            "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'public.email_events'::regclass ORDER BY conname",
            url,
        )
    )
    return {"columns": columns, "indexes": indexes, "constraints": constraints}


@pytest.fixture(scope="module")
def databases():
    """Two scratch databases: `head` (Alembic to head) and `hand` (for the SQL)."""
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI"):
            pytest.fail(f"{URL_ENV_VAR} is unset or unreachable in CI; this guard runs nowhere.")
        pytest.skip(f"{URL_ENV_VAR} not set to a reachable PostgreSQL")

    # The roles production has: objects owned by `enclii`, app runs as `janua`.
    _psql(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'enclii') "
        "THEN CREATE ROLE enclii NOLOGIN; END IF; "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janua') "
        "THEN CREATE ROLE janua NOLOGIN; END IF; "
        "END $$",
        base,
        autocommit=True,
    )
    names = {kind: f"janua_email_events_{kind}_{uuid.uuid4().hex[:8]}" for kind in ("head", "hand")}
    for name in names.values():
        created = _psql(f'CREATE DATABASE "{name}"', base, autocommit=True)
        assert created.returncode == 0, created.stderr
    urls = {kind: _with_database(base, name) for kind, name in names.items()}
    try:
        _ok(_alembic(["upgrade", "head"], urls["head"]))
        yield urls
    finally:
        for name in names.values():
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def test_owner_sql_refuses_wrong_revision_then_matches_alembic_and_is_idempotent(
    databases,
) -> None:
    head, hand = databases["head"], databases["hand"]

    # A database one revision too far back: the SQL refuses and changes nothing.
    _ok(_alembic(["upgrade", GRANDPARENT], hand))
    _ok(
        _psql(
            "GRANT CREATE, USAGE ON SCHEMA public TO enclii; "
            "GRANT SELECT, UPDATE ON alembic_version TO enclii",
            hand,
        )
    )
    refused = _psql(_sql_script(), hand, autocommit=True)
    assert refused.returncode != 0
    assert "expected alembic_version" in refused.stderr
    assert _version(hand) == GRANDPARENT
    assert _table_absent(hand)

    # At 017, as production is: applies, and the catalog equals Alembic's.
    _ok(_alembic(["upgrade", PARENT], hand))
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _catalog(hand) == _catalog(head)

    # Owned by enclii; the app role gets exactly SELECT + INSERT (append-only).
    owner = _psql("SELECT tableowner FROM pg_tables WHERE tablename = 'email_events'", hand)
    assert _ok(owner) == "enclii"
    grants = _ok(
        _psql(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE table_name = 'email_events' AND grantee = 'janua' ORDER BY 1",
            hand,
        )
    ).split()
    assert grants == ["INSERT", "SELECT"]

    # Re-running changes nothing and still succeeds.
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _ok(_psql("SELECT count(*) FROM alembic_version", hand)) == "1"
    assert _catalog(hand) == _catalog(head)

    # Alembic sees the hand-applied database as current.
    _ok(_alembic(["upgrade", "head"], hand))
    assert _version(hand) == HEAD


async def test_receiver_insert_path_is_idempotent_on_postgresql(databases) -> None:
    """The production insert (ON CONFLICT DO NOTHING ... RETURNING on asyncpg)
    against the migrated table: one row per svix_id, feed reads it back."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.services.email_events import ParsedEvent, list_events, record_event

    url = databases["head"]
    engine = create_async_engine(url.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        event = ParsedEvent(
            email_id="email-1",
            event_type="email.delivered",
            occurred_at=datetime(2026, 9, 23, 15, 0, 0),
            source_app="crea-map",
            org_id=None,
        )
        async with factory() as session:
            assert await record_event(session, "ctm", "msg_pg_1", event) is True
        async with factory() as session:
            assert await record_event(session, "ctm", "msg_pg_1", event) is False
        async with factory() as session:
            assert await list_events(session, "crea-map", 0, 10) == []  # settling
            rows = await list_events(session, "crea-map", 0, 10, settle_seconds=-60)
            assert [r.svix_id for r in rows] == ["msg_pg_1"]
    finally:
        await engine.dispose()


def test_alembic_downgrade_then_upgrade(databases) -> None:
    """Runs last: it drops and recreates the table on the `head` database."""
    url = databases["head"]
    assert _version(url) == HEAD
    assert "uq_email_events_svix_id" in _catalog(url)["constraints"]

    _ok(_alembic(["downgrade", PARENT], url))
    assert _version(url) == PARENT
    assert _table_absent(url)

    _ok(_alembic(["upgrade", "head"], url))
    assert _version(url) == HEAD
    assert "uq_email_events_svix_id" in _catalog(url)["constraints"]
