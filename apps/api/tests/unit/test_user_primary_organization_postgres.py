"""PostgreSQL parity for 022: reviewed operator SQL vs alembic, replay, SET NULL.

`docs/ops/sql/022_user_primary_organization.sql` is what an operator applies by
hand (promote and the staging overlay run no migrations). It must produce the
same catalog as `alembic upgrade` of revision 022, be safe to run twice, refuse
a database at the wrong revision, and leave a foreign key that clears the
pointer when its organization is deleted.
"""

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

pytestmark = pytest.mark.database
PARENT = "021_map_email_traceability"
HEAD = "022_user_primary_organization"
SQL = Path(__file__).resolve().parents[4] / "docs/ops/sql/022_user_primary_organization.sql"


def ok(result):
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def operator_sql() -> str:
    # psql meta-commands (`\set ON_ERROR_STOP on`) are not SQL; the driver
    # stops on the first error anyway.
    return "\n".join(
        line for line in SQL.read_text().splitlines() if not line.lstrip().startswith("\\")
    )


@pytest.fixture(scope="module")
def databases():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI") or os.environ.get("JANUA_REQUIRE_LOCAL_PG_TESTS"):
            pytest.fail(f"{URL_ENV_VAR} must reach the isolated PostgreSQL service")
        pytest.skip(f"{URL_ENV_VAR} is not configured locally")
    ok(
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
    )
    names = {key: f"janua_primary_org_{key}_{uuid.uuid4().hex[:10]}" for key in ["head", "hand"]}
    created = []
    try:
        for name in names.values():
            ok(_psql(f'CREATE DATABASE "{name}"', base, autocommit=True))
            created.append(name)
        urls = {key: _with_database(base, name) for key, name in names.items()}
        for url in urls.values():
            ok(_alembic(["upgrade", PARENT], url))
            # The app role's table privileges on `users`, as production has
            # them; the operator SQL checks they cover the new column.
            ok(_psql("GRANT SELECT, INSERT, UPDATE ON users TO janua", url))
        # Production shape for the hand-applied side: `users` owned by the
        # migration role, which runs the DDL under SET LOCAL ROLE.
        ok(
            _psql(
                "GRANT CREATE, USAGE ON SCHEMA public TO enclii; "
                "GRANT SELECT, UPDATE ON alembic_version TO enclii; "
                "GRANT REFERENCES ON organizations TO enclii; "
                "ALTER TABLE users OWNER TO enclii",
                urls["hand"],
            )
        )
        yield urls
    finally:
        for name in created:
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def catalog(url):
    return {
        "columns": ok(
            _psql(
                "SELECT column_name, data_type, is_nullable, coalesce(column_default, '') "
                "FROM information_schema.columns WHERE table_schema = 'public' "
                "AND table_name = 'users' ORDER BY column_name",
                url,
            )
        ),
        "constraints": ok(
            _psql(
                "SELECT conname, contype, convalidated, pg_get_constraintdef(oid) "
                "FROM pg_constraint WHERE conrelid = 'public.users'::regclass "
                "ORDER BY conname",
                url,
            )
        ),
        "indexes": ok(
            _psql(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' "
                "AND tablename = 'users' ORDER BY indexname",
                url,
            )
        ),
    }


def test_operator_sql_matches_alembic_and_replays_cleanly(databases):
    head, hand = databases["head"], databases["hand"]
    ok(_alembic(["upgrade", HEAD], head))

    ok(_psql(operator_sql(), hand, autocommit=True))
    assert catalog(head) == catalog(hand)

    before = catalog(hand)
    ok(_psql(operator_sql(), hand, autocommit=True))
    assert catalog(hand) == before
    assert ok(_psql("SELECT version_num FROM alembic_version", hand)) == HEAD

    constraint = ok(
        _psql(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'fk_users_primary_organization_id'",
            hand,
        )
    )
    assert constraint == (
        "FOREIGN KEY (primary_organization_id) REFERENCES organizations(id) ON DELETE SET NULL"
    )
    assert (
        ok(_psql("SELECT count(*) FROM users WHERE primary_organization_id IS NOT NULL", hand))
        == "0"
    )


def test_operator_sql_refuses_a_database_at_the_wrong_revision(databases):
    hand = databases["hand"]
    ok(_psql(operator_sql(), hand, autocommit=True))
    ok(_psql("UPDATE alembic_version SET version_num = '020_org_authentication_policy'", hand))
    try:
        refused = _psql(operator_sql(), hand, autocommit=True)
        assert refused.returncode != 0
        assert "expected alembic_version" in refused.stderr
        # Rolled back: the revision it refused is untouched.
        assert (
            ok(_psql("SELECT version_num FROM alembic_version", hand))
            == "020_org_authentication_policy"
        )
    finally:
        ok(_psql(f"UPDATE alembic_version SET version_num = '{HEAD}'", hand))


def test_deleting_the_organization_clears_the_pointer(databases):
    head = databases["head"]
    ok(_alembic(["upgrade", HEAD], head))
    org, user = uuid.uuid4(), uuid.uuid4()
    ok(
        _psql(
            f"INSERT INTO organizations (id, name, slug) VALUES ('{org}', 'Org', 'org-{org.hex[:8]}'); "
            f"INSERT INTO users (id, email, primary_organization_id, is_service_account) "
            f"VALUES ('{user}', 'staff-{user.hex[:8]}@example.com', '{org}', false)",
            head,
        )
    )
    unknown = _psql(
        f"UPDATE users SET primary_organization_id = '{uuid.uuid4()}' WHERE id = '{user}'", head
    )
    assert unknown.returncode != 0 and "fk_users_primary_organization_id" in unknown.stderr

    ok(_psql(f"DELETE FROM organizations WHERE id = '{org}'", head))

    assert ok(_psql(f"SELECT primary_organization_id FROM users WHERE id = '{user}'", head)) == (
        "None"
    )


def test_downgrade_removes_it_and_upgrade_is_reentrant(databases):
    head = databases["head"]
    ok(_alembic(["upgrade", HEAD], head))
    ok(_alembic(["downgrade", PARENT], head))
    columns = ok(
        _psql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'primary_organization_id'",
            head,
        )
    )
    assert columns == ""
    ok(_alembic(["upgrade", HEAD], head))
    # Stamped back with the objects present: upgrade must skip, not collide.
    ok(_alembic(["stamp", PARENT], head))
    ok(_alembic(["upgrade", HEAD], head))
    assert ok(_psql("SELECT version_num FROM alembic_version", head)) == HEAD
