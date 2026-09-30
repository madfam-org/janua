"""Every migration's upgrade() must survive its objects already existing.

WHY THIS EXISTS. Production runs `Base.metadata.create_all`
(settings.AUTO_MIGRATE), so the schema is populated by the models while
`alembic_version` still records an old revision -- it read '002' on 2026-08-13
with nine migrations unapplied. In that state a migration that creates
unconditionally does not "skip harmlessly"; it raises DuplicateTable and, since
alembic wraps the upgrade in one transaction, rolls the *whole chain* back. One
unguarded migration therefore pins the database at its parent revision forever,
and every later migration is dead behind it. That is how 004 blocked 005-011.

Reproduced exactly: upgrade to head on a fresh database, `stamp` back to 002 so
the schema is populated but the version is stale, then upgrade again. Against
the migrations as they stood, step three failed with
`DuplicateTableError: relation "guest_invites" already exists`.

EVERY database interaction here is a subprocess, for two independent reasons.
alembic/env.py resolves its URL from `settings` at import time, so only a fresh
process reads the scratch DATABASE_URL. And `tests/fixtures/external_mocks.py`
installs an autouse, session-scoped `patch.dict("sys.modules", ...)` that
replaces `psycopg2` with a `Mock` for the whole run -- an in-process
`import psycopg2` here yields that Mock and dies on `with conn.cursor()`.

This lives in tests/unit/ because CI passes `--ignore=tests/integration`, so a
file there would never run. It skips when no PostgreSQL is reachable, which is
the normal local case; CI's api-postgres-tests job provides one as a service.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

API_ROOT = Path(__file__).resolve().parents[2]

# The revision production was stamped at while its schema was already populated.
# Any revision would exercise re-entrancy; this one reproduces the real incident.
STALE_REVISION = "002"

# Set by CI's api-postgres-tests job to its `postgres` service. See _postgres_url().
URL_ENV_VAR = "MIGRATION_TEST_DATABASE_URL"


def _sync_url(url: str) -> str:
    """asyncpg URL -> psycopg2 URL. Only the driver differs."""
    return url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", "", ""))


def _psql(sql: str, url: str, autocommit: bool = False) -> subprocess.CompletedProcess[str]:
    """Run SQL in a subprocess, printing each result row tab-separated.

    A subprocess because psycopg2 is a Mock inside this process (see module
    docstring); the driver is only real on the other side of a fork+exec.
    """
    prog = (
        "import os,sys,psycopg2\n"
        "c=psycopg2.connect(os.environ['U'])\n"
        f"c.autocommit={autocommit!r}\n"
        "cur=c.cursor()\n"
        "cur.execute(os.environ['Q'])\n"
        "rows=cur.fetchall() if cur.description else []\n"
        "c.commit() if not c.autocommit else None\n"
        "print('\\n'.join('\\t'.join(map(str,r)) for r in rows))\n"
    )
    return subprocess.run(
        [sys.executable, "-c", prog],
        env={**os.environ, "U": _sync_url(url), "Q": sql},
        capture_output=True,
        text=True,
        timeout=120,
    )


def _postgres_url() -> str | None:
    """The scratch server's URL, or None when this environment has no PostgreSQL.

    Deliberately NOT `DATABASE_URL`: pytest.ini pins that to
    `sqlite+aiosqlite:///:memory:` for every run, so keying off it would make
    this test skip permanently -- including in CI, where it is the only place a
    real server exists. A silently-skipped guard is the failure mode this file
    is meant to prevent, so it reads a variable nothing else overrides and
    fails loudly below when CI forgets to set it.
    """
    url = os.environ.get(URL_ENV_VAR, "")
    if "postgresql" not in url:
        return None
    if _psql("SELECT 1", url).returncode != 0:  # pragma: no cover - no server
        return None
    return url


def _alembic(args: list[str], url: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "DATABASE_URL": url,
        # env.py prefers DIRECT_DATABASE_URL when set; the ambient value would
        # point every subprocess at the wrong database and silently migrate it.
        "DIRECT_DATABASE_URL": url,
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.fixture
def scratch_database() -> str:
    """A throwaway database on the configured server, dropped afterwards."""
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI"):
            # Fail rather than skip: CI is the only environment with a server,
            # so a skip here means this guard silently stopped protecting
            # anything while the job still reported green.
            pytest.fail(
                f"{URL_ENV_VAR} is unset or unreachable in CI. The api-postgres-tests job "
                "runs a postgres service; point this variable at it, or this "
                "migration guard runs nowhere."
            )
        pytest.skip(f"{URL_ENV_VAR} not set to a reachable PostgreSQL")

    name = f"janua_reentrancy_{uuid.uuid4().hex[:12]}"
    # CREATE/DROP DATABASE cannot run inside a transaction, hence autocommit.
    created = _psql(f'CREATE DATABASE "{name}"', base, autocommit=True)
    assert created.returncode == 0, f"could not create scratch database:\n{created.stderr}"

    try:
        yield _with_database(base, name)
    finally:
        _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


@pytest.mark.database
def test_upgrade_is_reentrant_over_an_already_populated_schema(scratch_database: str) -> None:
    first = _alembic(["upgrade", "head"], scratch_database)
    assert first.returncode == 0, f"fresh upgrade failed:\n{first.stdout}\n{first.stderr}"

    # Populated schema, stale version -- production's exact condition.
    stamped = _alembic(["stamp", STALE_REVISION], scratch_database)
    assert stamped.returncode == 0, f"stamp failed:\n{stamped.stdout}\n{stamped.stderr}"

    second = _alembic(["upgrade", "head"], scratch_database)
    assert second.returncode == 0, (
        "re-running the chain over an already-populated schema failed. A migration "
        "creates an object without checking whether it exists; in production that "
        "aborts the whole upgrade and pins the database at its parent revision.\n"
        f"{second.stdout}\n{second.stderr}"
    )

    # Head must actually be *recorded*, not merely reached: a revision id longer
    # than alembic_version.version_num's VARCHAR(32) raises on write and rolls
    # the upgrade back, which is how 006 stayed dead for months.
    version = _psql("SELECT version_num FROM alembic_version", scratch_database)
    assert version.returncode == 0, version.stderr
    recorded = version.stdout.strip()
    assert recorded and recorded != STALE_REVISION, (
        f"upgrade recorded no progress past {STALE_REVISION!r} (read {recorded!r})"
    )

    # The last migration's columns must be present, so a chain that "succeeded"
    # without applying anything cannot pass this test.
    cols = _psql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'invitations' "
        "AND column_name IN ('message', 'email_sent')",
        scratch_database,
    )
    assert cols.returncode == 0, cols.stderr
    assert set(cols.stdout.split()) == {"message", "email_sent"}
