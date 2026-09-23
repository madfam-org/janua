"""018_email_events: the Alembic revision and the owner-applied SQL agree.

Production DDL is applied BY HAND from docs/ops/sql/018_email_events.sql (the
promote does not run migrations), while every other environment runs the
Alembic revision. Two artefacts describing one schema drift apart silently, so
this applies BOTH to scratch PostgreSQL databases and compares the catalogs:
columns (type, nullability, default), indexes and constraints. It also proves
the SQL is idempotent, refuses a database at the wrong revision without
touching it, leaves a database that a later `alembic upgrade head` treats as
current, and that the revision downgrades and re-upgrades cleanly.

Same harness and the same skip/fail rule as test_migration_reentrancy.py:
skips without MIGRATION_TEST_DATABASE_URL locally, FAILS without it in CI.
"""

from __future__ import annotations

import os
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

REPO_ROOT = Path(__file__).resolve().parents[4]
SQL_FILE = REPO_ROOT / "docs" / "ops" / "sql" / "018_email_events.sql"
HEAD = "018_email_events"
PARENT = "017_payment_mail_dispatch"


def _sql_script() -> str:
    """The owner file minus psql meta-commands (`\\set`), which only psql parses."""
    return "\n".join(
        line for line in SQL_FILE.read_text().splitlines() if not line.lstrip().startswith("\\")
    )


@pytest.fixture
def scratch_factory():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI"):
            pytest.fail(f"{URL_ENV_VAR} is unset or unreachable in CI; this guard runs nowhere.")
        pytest.skip(f"{URL_ENV_VAR} not set to a reachable PostgreSQL")
    created: list[str] = []

    def make() -> str:
        name = f"janua_email_events_{uuid.uuid4().hex[:12]}"
        result = _psql(f'CREATE DATABASE "{name}"', base, autocommit=True)
        assert result.returncode == 0, result.stderr
        created.append(name)
        return _with_database(base, name)

    # The roles production has: objects owned by `enclii`, app runs as `janua`.
    _psql(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'enclii') THEN CREATE ROLE enclii NOLOGIN; END IF; "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janua') THEN CREATE ROLE janua NOLOGIN; END IF; "
        "END $$",
        base,
        autocommit=True,
    )
    try:
        yield make
    finally:
        for name in created:
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def _ok(result) -> str:
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def _version(url: str) -> str:
    return _ok(_psql("SELECT version_num FROM alembic_version", url))


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


def _prepare_like_production(url: str) -> None:
    """At 017 via Alembic, with `enclii` able to own new objects and move the version."""
    _ok(_alembic(["upgrade", PARENT], url))
    _ok(
        _psql(
            "GRANT CREATE, USAGE ON SCHEMA public TO enclii; "
            "GRANT SELECT, UPDATE ON alembic_version TO enclii",
            url,
        )
    )


def test_alembic_upgrade_downgrade_upgrade(scratch_factory) -> None:
    url = scratch_factory()
    _ok(_alembic(["upgrade", "head"], url))
    assert _version(url) == HEAD
    assert "uq_email_events_svix_id" in _catalog(url)["constraints"]

    _ok(_alembic(["downgrade", PARENT], url))
    assert _version(url) == PARENT
    assert _ok(_psql("SELECT to_regclass('public.email_events')", url)) in ("", "None")

    _ok(_alembic(["upgrade", "head"], url))
    assert _version(url) == HEAD


def test_owner_sql_matches_the_alembic_revision_and_is_idempotent(scratch_factory) -> None:
    via_alembic = scratch_factory()
    _ok(_alembic(["upgrade", "head"], via_alembic))

    via_sql = scratch_factory()
    _prepare_like_production(via_sql)
    _ok(_psql(_sql_script(), via_sql, autocommit=True))
    assert _version(via_sql) == HEAD
    assert _catalog(via_sql) == _catalog(via_alembic)

    # Owned by enclii; the app role gets exactly SELECT + INSERT (append-only).
    assert (
        _ok(_psql("SELECT tableowner FROM pg_tables WHERE tablename = 'email_events'", via_sql))
        == "enclii"
    )
    grants = _ok(
        _psql(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE table_name = 'email_events' AND grantee = 'janua' ORDER BY 1",
            via_sql,
        )
    ).split()
    assert grants == ["INSERT", "SELECT"]

    # Re-running changes nothing and still succeeds.
    _ok(_psql(_sql_script(), via_sql, autocommit=True))
    assert _version(via_sql) == HEAD
    assert _ok(_psql("SELECT count(*) FROM alembic_version", via_sql)) == "1"
    assert _catalog(via_sql) == _catalog(via_alembic)

    # Alembic sees the hand-applied database as current.
    _ok(_alembic(["upgrade", "head"], via_sql))
    assert _version(via_sql) == HEAD


def test_owner_sql_refuses_the_wrong_revision_and_changes_nothing(scratch_factory) -> None:
    url = scratch_factory()
    _ok(_alembic(["upgrade", "016_org_member_app_roles"], url))
    _ok(
        _psql(
            "GRANT CREATE, USAGE ON SCHEMA public TO enclii; GRANT SELECT, UPDATE ON alembic_version TO enclii",
            url,
        )
    )
    result = _psql(_sql_script(), url, autocommit=True)
    assert result.returncode != 0
    assert "expected alembic_version" in result.stderr
    # The failed script ran in its own connection; its transaction rolled back whole.
    assert _version(url) == "016_org_member_app_roles"
    assert _ok(_psql("SELECT to_regclass('public.email_events')", url)) in ("", "None")


async def test_receiver_insert_path_is_idempotent_on_postgresql(scratch_factory) -> None:
    """The production insert (ON CONFLICT DO NOTHING ... RETURNING on asyncpg)
    against the migrated table: one row per svix_id, feed reads it back."""
    from datetime import datetime, timedelta

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.services.email_events import ParsedEvent, list_events, record_event

    url = scratch_factory()
    _ok(_alembic(["upgrade", "head"], url))
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
            assert rows[0].received_at <= datetime.utcnow() + timedelta(seconds=1)
    finally:
        await engine.dispose()
