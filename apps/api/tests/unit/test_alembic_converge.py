"""Guards for scripts/alembic_converge.py — the script that stamps production.

TWO KINDS OF TEST LIVE HERE, and the first matters more than it looks.

1. DRIFT (no database). `alembic_converge.REVISIONS` is a hand-written copy of
   what migrations 012-016 create. A copy of a fact is a fact that can go
   stale, and this one goes stale silently in the worst possible direction: if
   someone adds an index to 016 and not to the table here, the script decides
   016 is "fully present" while an object is missing, and stamps -- recording
   the exact lie the whole design refuses to record. So the expectations are
   re-derived from the migration sources with `ast` and compared. Parsing
   rather than importing, matching test_alembic_revision_graph.py: no database,
   no settings, no app import, and no way for an unimportable environment to
   turn this guard into a skip.

2. BEHAVIOUR (PostgreSQL, skipped when absent). Partial detection, the
   prefix rule, and the stamp path are the logic that decides whether
   production's version row gets written, so they are exercised against a real
   schema built by the real migrations. Follows test_migration_reentrancy.py:
   scratch database from MIGRATION_TEST_DATABASE_URL, dropped afterwards, and
   a hard failure rather than a skip when CI forgets to provide a server.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = API_ROOT / "alembic" / "versions"
SCRIPT_PATH = API_ROOT / "scripts" / "alembic_converge.py"

URL_ENV_VAR = "MIGRATION_TEST_DATABASE_URL"


def _load_script():
    """Import the script by path — `scripts/` is not an importable package.

    Registered in sys.modules BEFORE exec: the script declares dataclasses, and
    @dataclass resolves annotations through sys.modules[cls.__module__], which
    raises AttributeError on a module that is not there yet.
    """
    spec = importlib.util.spec_from_file_location("alembic_converge", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["alembic_converge"] = module
    spec.loader.exec_module(module)
    return module


converge = _load_script()


# ---------------------------------------------------------------------------
# 1. Drift: the expectation table vs. the migrations themselves
# ---------------------------------------------------------------------------


def _migration_source(revision_id: str) -> ast.Module:
    """Parse the file whose module-level `revision` equals revision_id."""
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        module = ast.parse(path.read_text(), filename=str(path))
        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "revision":
                    try:
                        if ast.literal_eval(node.value) == revision_id:
                            return module
                    except ValueError:
                        pass
    raise AssertionError(f"no migration defines revision {revision_id!r}")


def _string_constants(module: ast.Module) -> set:
    """Every string literal in the file, plus the module-level string names.

    Deliberately coarse. The point is not to re-implement alembic's operation
    parser -- it is to prove that each object name this script looks for is
    literally mentioned by the migration that is supposed to create it. A
    migration that stops creating an object almost always stops naming it too;
    one that adds an object always names it, which is what the reverse
    direction below catches.
    """
    return {
        node.value
        for node in ast.walk(module)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _created_object_names(module: ast.Module) -> set:
    """Names passed to op.create_table / create_index / add_column in this file.

    This is the strict direction: anything the migration CREATES must appear in
    the script's expectations, or the script would call the revision complete
    while that object is missing.
    """
    created = set()
    aliases = {}

    # `TABLE = "capability_links"` style module constants, so a create_index
    # call written against the constant still resolves to a name.
    for node in module.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    aliases[target.id] = node.value.value

    def _resolve(node) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return aliases.get(node.id)
        return None

    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        func = node.func.attr
        if func == "create_table" and node.args:
            name = _resolve(node.args[0])
            if name:
                created.add(name)
        elif func == "create_index" and node.args:
            name = _resolve(node.args[0])
            if name:
                created.add(name)
        elif func == "add_column" and len(node.args) >= 2:
            column = node.args[1]
            if isinstance(column, ast.Call) and column.args:
                name = _resolve(column.args[0])
                if name:
                    created.add(name)
    return created


@pytest.mark.parametrize("revision", converge.REVISIONS, ids=lambda r: r.revision)
def test_every_expected_object_is_named_by_its_migration(revision) -> None:
    """No expectation may invent an object its migration never mentions."""
    module = _migration_source(revision.revision)
    literals = _string_constants(module)
    for expectation in revision.expects:
        needle = expectation.table if expectation.kind == "table" else expectation.name
        assert needle in literals, (
            f"{revision.revision} expects {expectation.describe()!r}, but the migration "
            f"file never mentions {needle!r}. The expectation table in "
            "scripts/alembic_converge.py has drifted from the migration."
        )


@pytest.mark.parametrize("revision", converge.REVISIONS, ids=lambda r: r.revision)
def test_every_created_object_is_expected(revision) -> None:
    """The dangerous direction: a created object missing from the expectations.

    If a migration grows an object the script does not check for, the script
    can call that revision fully present while the object is absent -- and
    stamp. That is the one outcome the whole design exists to prevent.
    """
    module = _migration_source(revision.revision)
    created = _created_object_names(module)
    expected = {e.table if e.kind == "table" else e.name for e in revision.expects}

    # 013 drops ix_users_email; its downgrade() re-creates it. That name is a
    # creation only in the reverse direction, so it is not an upgrade artefact.
    created -= {converge.LEGACY_GLOBAL_EMAIL_INDEX}

    missing = created - expected
    assert not missing, (
        f"{revision.revision} creates {sorted(missing)}, which scripts/alembic_converge.py "
        "does not check for. Add it to REVISIONS, or the script will stamp the revision "
        "as applied while that object is absent."
    )


def test_revisions_are_the_hand_applied_span_in_order() -> None:
    """The table covers 012-016 and its order is the stamp order."""
    ids = [r.revision for r in converge.REVISIONS]
    assert ids == [
        "012_user_spanish_formality",
        "013_per_tenant_email_uniqueness",
        "014_capability_links",
        "015_user_is_service_acct",
        "016_org_member_app_roles",
    ]


def test_revision_ids_match_the_migration_chain() -> None:
    """Each expectation's revision id exists and its parent is the previous one."""
    previous = None
    for revision in converge.REVISIONS:
        module = _migration_source(revision.revision)
        down = None
        for node in module.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == "down_revision":
                    down = ast.literal_eval(node.value)
        if previous is not None:
            assert down == previous, (
                f"{revision.revision}.down_revision is {down!r}, but alembic_converge "
                f"stamps it straight after {previous!r}. A stamp order that disagrees "
                "with the chain would record an unreachable revision."
            )
        previous = revision.revision


# ---------------------------------------------------------------------------
# Pure-logic tests (no database)
# ---------------------------------------------------------------------------


class _FakeProbe:
    """A SchemaProbe stand-in over a fixed set of `describe()` strings."""

    def __init__(self, present) -> None:
        self._present = set(present)

    def has(self, expectation) -> bool:
        return expectation.describe() in self._present


def _all_object_descriptions(up_to: str | None = None) -> list:
    names = []
    for revision in converge.REVISIONS:
        names.extend(e.describe() for e in revision.expects)
        if up_to and revision.revision == up_to:
            break
    return names


def test_highest_stampable_is_a_prefix_not_a_max() -> None:
    """A gap stops the walk even when a LATER revision is complete.

    Stamping 016 asserts 012-015 are true as well -- alembic records one
    version and infers the rest of the chain -- so a hole anywhere below the
    target makes the target unstampable.
    """
    present = _all_object_descriptions("013_per_tenant_email_uniqueness")
    # 014 absent entirely, 015 + 016 fully present.
    present += [e.describe() for e in converge.REVISIONS[3].expects]
    present += [e.describe() for e in converge.REVISIONS[4].expects]

    statuses = converge.inspect_revisions(_FakeProbe(present))
    assert converge.highest_stampable(statuses) == "013_per_tenant_email_uniqueness"
    assert not converge.find_partial(statuses), "a wholly absent revision is not partial"


def test_partial_revision_is_detected() -> None:
    present = _all_object_descriptions("013_per_tenant_email_uniqueness")
    # 014's table but none of its indexes: a state no migration produces.
    present.append(converge.REVISIONS[2].expects[0].describe())

    statuses = converge.inspect_revisions(_FakeProbe(present))
    partial = converge.find_partial(statuses)
    assert [s.revision.revision for s in partial] == ["014_capability_links"]
    assert converge.highest_stampable(statuses) == "013_per_tenant_email_uniqueness"


def test_stamp_path_skips_what_is_already_recorded() -> None:
    statuses = converge.inspect_revisions(_FakeProbe(_all_object_descriptions()))
    path = converge.stamp_path(
        statuses, "013_per_tenant_email_uniqueness", "016_org_member_app_roles"
    )
    assert path == [
        "014_capability_links",
        "015_user_is_service_acct",
        "016_org_member_app_roles",
    ]


def test_stamp_path_from_a_pre_012_version_covers_the_whole_span() -> None:
    """Production's actual state: recorded 011, schema at 016."""
    statuses = converge.inspect_revisions(_FakeProbe(_all_object_descriptions()))
    path = converge.stamp_path(statuses, "011_invitation_columns", "016_org_member_app_roles")
    assert path == [r.revision for r in converge.REVISIONS]


def test_stamp_path_is_empty_when_already_converged() -> None:
    statuses = converge.inspect_revisions(_FakeProbe(_all_object_descriptions()))
    assert (
        converge.stamp_path(statuses, "016_org_member_app_roles", "016_org_member_app_roles") == []
    )


def test_redact_never_leaks_credentials() -> None:
    """Every diagnostic goes through redact(); a password must not survive it."""
    url = "postgresql+asyncpg://janua:sup3r-s3cret@db.internal:5432/janua_prod"
    rendered = converge.redact(url)
    assert "sup3r-s3cret" not in rendered
    assert "janua:" not in rendered
    assert rendered == "db.internal:5432/janua_prod"


def test_resolve_database_url_prefers_direct(monkeypatch) -> None:
    """Same precedence as alembic/env.py, or we inspect one DB and stamp another."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://a/one")
    monkeypatch.setenv("DIRECT_DATABASE_URL", "postgresql://b/two")
    assert converge.resolve_database_url() == "postgresql://b/two"

    monkeypatch.delenv("DIRECT_DATABASE_URL")
    assert converge.resolve_database_url() == "postgresql://a/one"


def test_resolve_database_url_refuses_to_guess(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DIRECT_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit):
        converge.resolve_database_url()


def test_render_table_lists_every_object_with_a_verdict() -> None:
    statuses = converge.inspect_revisions(
        _FakeProbe(_all_object_descriptions("012_user_spanish_formality"))
    )
    rendered = converge.render_table(statuses)
    assert "revision" in rendered and "¿presente?" in rendered
    for revision in converge.REVISIONS:
        for expectation in revision.expects:
            assert expectation.describe() in rendered
    assert "PRESENTE" in rendered and "AUSENTE" in rendered


# ---------------------------------------------------------------------------
# 2. Behaviour against a real PostgreSQL schema
# ---------------------------------------------------------------------------


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", "", ""))


def _psql(sql: str, url: str, autocommit: bool = False) -> subprocess.CompletedProcess:
    """SQL in a subprocess: psycopg2 is a Mock in this process.

    tests/fixtures/external_mocks.py installs a session-scoped
    patch.dict("sys.modules") replacing psycopg2 for the whole run, so the
    driver is only real on the far side of a fork+exec. Same reason
    test_migration_reentrancy.py does this.
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


def _postgres_url():
    url = os.environ.get(URL_ENV_VAR, "")
    if "postgresql" not in url:
        return None
    if _psql("SELECT 1", url).returncode != 0:  # pragma: no cover - no server
        return None
    return url


def _alembic(args, url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "DIRECT_DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(API_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _converge(args, url: str) -> subprocess.CompletedProcess:
    """Run the script itself, in a subprocess, for the same psycopg2 reason."""
    env = {**os.environ, "DATABASE_URL": url, "DIRECT_DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(API_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.fixture
def migrated_database():
    """A scratch database upgraded to head, then stamped back to 011.

    This is production's exact condition: the schema carries 012-016 while
    alembic_version still reads 011, because the migrations were applied
    outside alembic and promote runs none.
    """
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI"):
            pytest.fail(
                f"{URL_ENV_VAR} is unset or unreachable in CI. The api-postgres-tests job runs a "
                "postgres service; point this variable at it, or this guard runs nowhere."
            )
        pytest.skip(f"{URL_ENV_VAR} not set to a reachable PostgreSQL")

    name = f"janua_converge_{uuid.uuid4().hex[:12]}"
    created = _psql(f'CREATE DATABASE "{name}"', base, autocommit=True)
    assert created.returncode == 0, f"could not create scratch database:\n{created.stderr}"

    url = _with_database(base, name)
    try:
        upgraded = _alembic(["upgrade", "head"], url)
        assert upgraded.returncode == 0, f"upgrade failed:\n{upgraded.stdout}\n{upgraded.stderr}"
        stamped = _alembic(["stamp", "011_invitation_columns"], url)
        assert stamped.returncode == 0, f"stamp failed:\n{stamped.stdout}\n{stamped.stderr}"
        yield url
    finally:
        _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def _recorded_version(url: str) -> str:
    result = _psql("SELECT version_num FROM alembic_version", url)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.database
def test_check_reports_drift_and_changes_nothing(migrated_database: str) -> None:
    result = _converge(["--check"], migrated_database)

    assert result.returncode == converge.EXIT_BEHIND, (
        "a version row five revisions behind a complete schema must report drift.\n"
        f"{result.stdout}\n{result.stderr}"
    )
    for revision in converge.REVISIONS:
        assert revision.revision in result.stdout
    assert "PRESENTE" in result.stdout
    assert (
        _recorded_version(migrated_database) == "011_invitation_columns"
    ), "--check must not write the version table"


@pytest.mark.database
def test_check_never_prints_the_password(migrated_database: str) -> None:
    """Output is meant to be pasteable into a ticket."""
    parts = urlsplit(_sync_url(migrated_database))
    if not parts.password:  # pragma: no cover - depends on CI's service config
        pytest.skip("configured PostgreSQL URL carries no password to leak")
    combined = (
        _converge(["--check"], migrated_database).stdout
        + _converge(["--check"], migrated_database).stderr
    )
    assert parts.password not in combined


@pytest.mark.database
def test_stamp_walks_to_head_and_upgrade_becomes_a_noop(migrated_database: str) -> None:
    result = _converge(["--stamp", "--yes"], migrated_database)
    assert result.returncode == converge.EXIT_OK, f"{result.stdout}\n{result.stderr}"
    assert _recorded_version(migrated_database) == "016_org_member_app_roles"

    # Each step is its own stamp, so a failure halfway leaves a true version.
    for revision in converge.REVISIONS:
        assert f"alembic stamp {revision.revision}" in result.stdout

    # The point of the exercise: alembic and the schema now agree, so the
    # thing nobody dared run is a no-op.
    current = _alembic(["current"], migrated_database)
    assert current.returncode == 0, current.stderr
    assert "016_org_member_app_roles" in current.stdout

    again = _converge(["--check"], migrated_database)
    assert again.returncode == converge.EXIT_OK
    assert "Convergente" in again.stdout


@pytest.mark.database
def test_partial_revision_blocks_and_writes_nothing(migrated_database: str) -> None:
    """Drop one index of 016 — the script must refuse the whole operation."""
    dropped = _psql("DROP INDEX uq_org_member_app_roles_live", migrated_database)
    assert dropped.returncode == 0, dropped.stderr

    result = _converge(["--stamp", "--yes"], migrated_database)
    assert result.returncode == converge.EXIT_PARTIAL, f"{result.stdout}\n{result.stderr}"
    assert "PARCIAL" in result.stdout or "PARCIAL" in result.stderr
    assert "uq_org_member_app_roles_live" in result.stderr
    assert _recorded_version(migrated_database) == "011_invitation_columns", (
        "a partial revision anywhere must leave the version table untouched — "
        "including the four complete revisions below it"
    )


@pytest.mark.database
def test_stamp_stops_at_the_gap_when_a_later_revision_is_complete(migrated_database: str) -> None:
    """014 absent entirely, 015/016 present: stamp reaches 013 and no further."""
    dropped = _psql("DROP TABLE capability_links", migrated_database)
    assert dropped.returncode == 0, dropped.stderr

    result = _converge(["--stamp", "--yes"], migrated_database)
    assert result.returncode == converge.EXIT_OK, f"{result.stdout}\n{result.stderr}"
    assert _recorded_version(migrated_database) == "013_per_tenant_email_uniqueness"
