"""020_audit_log_hash_chain: the Alembic revision, the owner SQL and the drift check agree.

Same harness and skip/fail rule as test_email_engagement_migration.py (019):
the PostgreSQL tests carry the `database` marker, skip without
MIGRATION_TEST_DATABASE_URL locally and FAIL without it in CI. Two scratch
databases: `head` (Alembic to head) and `hand` (Alembic to 019, then the owner
SQL). They prove that:

- the owner SQL runs exactly the revision's statements (no database needed);
- the SQL refuses a database at the wrong revision without touching it, lands
  on Alembic's catalog for `audit_logs` whichever role owns the table, is
  idempotent, and leaves a database a later `alembic upgrade head` treats as
  current;
- the revision is re-entrant, and downgrades and re-upgrades cleanly;
- on PostgreSQL, rows written with `action` only still insert, and concurrent
  audit loggers of one tenant build one unbroken chain;
- scripts/audit_logs_drift_check.py reports the four missing columns and the
  index at 019 and 0 drift at head, without printing the database password.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.unit.test_migration_reentrancy import (
    API_ROOT,
    URL_ENV_VAR,
    _alembic,
    _postgres_url,
    _psql,
    _sync_url,
    _with_database,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SQL_FILE = REPO_ROOT / "docs" / "ops" / "sql" / "020_audit_log_hash_chain.sql"
MIGRATION_FILE = API_ROOT / "alembic" / "versions" / "020_audit_log_hash_chain.py"
DRIFT_SCRIPT = API_ROOT / "scripts" / "audit_logs_drift_check.py"
HEAD = "020_audit_log_hash_chain"
PARENT = "019_email_first_party_engagement"
GRANDPARENT = "018_email_events"
NEW_COLUMNS = ("current_hash", "event_type", "previous_hash", "tenant_id")


def _migration():
    spec = importlib.util.spec_from_file_location("migration_020", MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _new_columns(url: str) -> list[str]:
    return _ok(
        _psql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'audit_logs' "
            f"AND column_name IN {NEW_COLUMNS!r} ORDER BY 1",
            url,
        )
    ).split()


def _catalog(url: str) -> dict[str, str]:
    return {
        "columns": _ok(
            _psql(
                "SELECT column_name, data_type, character_maximum_length, is_nullable, "
                "coalesce(column_default, '') FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'audit_logs' "
                "ORDER BY column_name",
                url,
            )
        ),
        "indexes": _ok(
            _psql(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'audit_logs' ORDER BY indexname",
                url,
            )
        ),
        "constraints": _ok(
            _psql(
                "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'public.audit_logs'::regclass ORDER BY conname",
                url,
            )
        ),
    }


def _drift_check(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DRIFT_SCRIPT), *args],
        cwd=API_ROOT,
        env={**os.environ, "DATABASE_URL": url, "DIRECT_DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_owner_sql_runs_exactly_the_revision_statements() -> None:
    """No database: the five DDL statements are the same text in both files."""
    statements = [
        statement.strip()
        for statement in _sql_script().split(";")
        if re.match(r"\s*(ALTER TABLE audit_logs|CREATE INDEX)", statement)
    ]
    assert statements == list(_migration().UPGRADE_STATEMENTS)
    for statement in statements:
        assert "IF NOT EXISTS" in statement


@pytest.fixture(scope="module")
def databases():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI"):
            pytest.fail(f"{URL_ENV_VAR} is unset or unreachable in CI; this guard runs nowhere.")
        pytest.skip(f"{URL_ENV_VAR} not set to a reachable PostgreSQL")

    _psql(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'enclii') "
        "THEN CREATE ROLE enclii NOLOGIN; END IF; "
        "END $$",
        base,
        autocommit=True,
    )
    names = {kind: f"janua_audit_chain_{kind}_{uuid.uuid4().hex[:8]}" for kind in ("head", "hand")}
    for name in names.values():
        created = _psql(f'CREATE DATABASE "{name}"', base, autocommit=True)
        assert created.returncode == 0, created.stderr
    urls = {kind: _with_database(base, name) for kind, name in names.items()}
    try:
        _ok(_alembic(["upgrade", HEAD], urls["head"]))
        yield urls
    finally:
        for name in names.values():
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


@pytest.mark.database
def test_owner_sql_refuses_wrong_revision_then_matches_alembic_and_is_idempotent(
    databases,
) -> None:
    head, hand = databases["head"], databases["hand"]

    # One revision too far back: refuses and changes nothing.
    _ok(_alembic(["upgrade", GRANDPARENT], hand))
    refused = _psql(_sql_script(), hand, autocommit=True)
    assert refused.returncode != 0
    assert "expected alembic_version" in refused.stderr
    assert _version(hand) == GRANDPARENT
    assert _new_columns(hand) == []

    # At 019, with audit_logs owned by a role other than the one applying the
    # SQL, as in production.
    _ok(_alembic(["upgrade", PARENT], hand))
    _ok(_psql("ALTER TABLE audit_logs OWNER TO enclii", hand))
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _catalog(hand) == _catalog(head)
    index_owner = _psql(
        "SELECT pg_get_userbyid(c.relowner) FROM pg_class c "
        "WHERE c.relname = 'ix_audit_logs_tenant_chain'",
        hand,
    )
    assert _ok(index_owner) == "enclii"

    # Re-running changes nothing and still succeeds.
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _ok(_psql("SELECT count(*) FROM alembic_version", hand)) == "1"
    assert _catalog(hand) == _catalog(head)

    # Alembic sees the hand-applied database as current.
    _ok(_alembic(["upgrade", HEAD], hand))
    assert _version(hand) == HEAD


@pytest.mark.database
def test_upgrade_is_reentrant_over_its_own_objects(databases) -> None:
    head = databases["head"]
    before = _catalog(head)

    _ok(_alembic(["stamp", PARENT], head))
    _ok(_alembic(["upgrade", HEAD], head))

    assert _version(head) == HEAD
    assert _catalog(head) == before


@pytest.mark.database
def test_rows_with_action_only_still_insert(databases) -> None:
    head = databases["head"]
    _ok(
        _psql(
            "INSERT INTO audit_logs (id, action, resource_type, details, created_at) "
            f"VALUES ('{uuid.uuid4()}', 'oauth_client.create', 'oauth_client', '{{}}', now())",
            head,
        )
    )
    row = _ok(
        _psql(
            "SELECT action, event_type IS NULL, tenant_id IS NULL, current_hash IS NULL "
            "FROM audit_logs WHERE action = 'oauth_client.create'",
            head,
        )
    )
    assert row == "oauth_client.create\tTrue\tTrue\tTrue"


@pytest.mark.database
async def test_concurrent_loggers_of_one_tenant_build_one_chain(databases, monkeypatch) -> None:
    """One AuditLogger and one session per request, as the routers do."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models import AuditLog
    from app.services import audit_logger as audit_logger_module
    from app.services.audit_logger import RESOURCE_REF_KEY, AuditEventType, AuditLogger

    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)

    url = databases["head"]
    engine = create_async_engine(
        _sync_url(url).replace("postgresql://", "postgresql+asyncpg://"), pool_size=10
    )
    tenant = str(uuid.uuid4())
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def one_request(i: int) -> None:
            async with factory() as session:
                await AuditLogger(session).log(
                    event_type=AuditEventType.USER_UPDATE,
                    tenant_id=tenant,
                    resource_type="user",
                    resource_id=str(uuid.uuid4()) if i % 2 else f"external-{i}",
                    details={"i": i},
                    ip_address="192.0.2.1",
                )

        await asyncio.gather(*(one_request(i) for i in range(12)))

        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(AuditLog)
                        .where(AuditLog.tenant_id == tenant)
                        .order_by(AuditLog.created_at, AuditLog.id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 12
            assert rows[0].previous_hash is None
            assert [r.previous_hash for r in rows[1:]] == [r.current_hash for r in rows[:-1]]
            assert {r.action for r in rows} == {"user.update"}
            external = [r for r in rows if r.resource_id is None]
            assert len(external) == 6
            assert all(r.details[RESOURCE_REF_KEY].startswith("external-") for r in external)

            result = await AuditLogger(session).verify_integrity(tenant)
            assert result["valid"] is True and result["count"] == 12
    finally:
        await engine.dispose()


@pytest.mark.database
def test_drift_check_reports_020_at_019_and_nothing_at_head(databases) -> None:
    head = databases["head"]
    password = urlsplit(head).password

    clean = _drift_check(head)
    assert clean.returncode == 0, f"{clean.stdout}\n{clean.stderr}"
    assert "DRIFT-TOTAL: 0" in clean.stdout
    assert f"alembic_version: {HEAD}" in clean.stdout

    # Read-only: the database is the same afterwards.
    assert _version(head) == HEAD

    with_json = _drift_check(head, "--json")
    assert with_json.returncode == 0
    assert '"drift_total": 0' in with_json.stdout

    at_parent = databases["hand"]
    _ok(_alembic(["downgrade", PARENT], at_parent))
    stale = _drift_check(at_parent)
    assert stale.returncode == 2, f"{stale.stdout}\n{stale.stderr}"
    for column in NEW_COLUMNS:
        assert f"column audit_logs.{column} is missing" in stale.stdout
        # The model in this checkout maps them, so they are model drift too.
        assert f"model column audit_logs.{column} is missing" in stale.stdout
    assert "index ix_audit_logs_tenant_chain on audit_logs is missing" in stale.stdout
    assert "DRIFT-TOTAL: 9" in stale.stdout

    for result in (clean, with_json, stale):
        if password:
            assert password not in result.stdout + result.stderr


@pytest.mark.database
def test_alembic_downgrade_then_upgrade(databases) -> None:
    """Runs last: drops and recreates the 020 objects on the `head` database."""
    url = databases["head"]
    assert _version(url) == HEAD
    _ok(_alembic(["downgrade", PARENT], url))
    assert _version(url) == PARENT
    assert _new_columns(url) == []
    index = _ok(_psql("SELECT to_regclass('public.ix_audit_logs_tenant_chain')", url))
    assert index in ("", "None")

    # Downgrade is re-entrant too.
    _ok(_alembic(["stamp", HEAD], url))
    _ok(_alembic(["downgrade", PARENT], url))

    _ok(_alembic(["upgrade", HEAD], url))
    assert _version(url) == HEAD
    assert _new_columns(url) == sorted(NEW_COLUMNS)
