"""PostgreSQL parity for 023: reviewed operator SQL vs alembic, replay, cascades.

`docs/ops/sql/023_device_clients.sql` is what an operator applies by hand
(promote and the staging overlay run no migrations). It must produce the same
catalog as `alembic upgrade` of revision 023 for both tables, be safe to run
twice, refuse a database at the wrong revision, grant the app role no DELETE,
and leave foreign keys that cascade (or set NULL) as the models say.

Skips locally without `MIGRATION_TEST_DATABASE_URL`; CI's api-postgres-tests
job provides the service.
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
PARENT = "022_user_primary_organization"
HEAD = "023_device_clients"
TABLES = ("device_clients", "device_enrolments")
SQL = Path(__file__).resolve().parents[4] / "docs/ops/sql/023_device_clients.sql"


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
    names = {key: f"janua_device_clients_{key}_{uuid.uuid4().hex[:10]}" for key in ["head", "hand"]}
    created = []
    try:
        for name in names.values():
            ok(_psql(f'CREATE DATABASE "{name}"', base, autocommit=True))
            created.append(name)
        urls = {key: _with_database(base, name) for key, name in names.items()}
        for url in urls.values():
            ok(_alembic(["upgrade", PARENT], url))
        # Production shape for the hand-applied side: the migration role runs
        # the DDL under SET LOCAL ROLE and owns what it creates.
        ok(
            _psql(
                "GRANT CREATE, USAGE ON SCHEMA public TO enclii; "
                "GRANT SELECT, UPDATE ON alembic_version TO enclii; "
                "GRANT REFERENCES ON organizations, users, oauth_clients TO enclii",
                urls["hand"],
            )
        )
        yield urls
    finally:
        for name in created:
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def catalog(url):
    tables = ", ".join(f"'{table}'" for table in TABLES)
    regclasses = ", ".join(f"'public.{table}'::regclass" for table in TABLES)
    return {
        "columns": ok(
            _psql(
                "SELECT table_name, column_name, data_type, character_maximum_length, "
                "is_nullable, coalesce(column_default, '') FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name IN ({tables}) "
                "ORDER BY table_name, column_name",
                url,
            )
        ),
        "constraints": ok(
            _psql(
                "SELECT conrelid::regclass, conname, contype, convalidated, "
                "pg_get_constraintdef(oid) FROM pg_constraint "
                f"WHERE conrelid IN ({regclasses}) ORDER BY 1, 2",
                url,
            )
        ),
        "indexes": ok(
            _psql(
                "SELECT tablename, indexname, indexdef FROM pg_indexes "
                f"WHERE schemaname = 'public' AND tablename IN ({tables}) ORDER BY 1, 2",
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
    for definition in [
        "FOREIGN KEY (oauth_client_id) REFERENCES oauth_clients(id) ON DELETE CASCADE",
        "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE",
        "FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL",
        "FOREIGN KEY (device_id) REFERENCES device_clients(id) ON DELETE SET NULL",
        "UNIQUE (user_code)",
        "UNIQUE (oauth_client_id)",
    ]:
        assert definition in before["constraints"], definition
    for table in TABLES:
        assert (
            ok(_psql(f"SELECT tableowner FROM pg_tables WHERE tablename = '{table}'", hand))
            == "enclii"
        )
        grants = ok(
            _psql(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                f"WHERE table_name = '{table}' AND grantee = 'janua' ORDER BY 1",
                hand,
            )
        )
        assert grants.splitlines() == ["INSERT", "SELECT", "UPDATE"], table


def test_operator_sql_refuses_a_database_at_the_wrong_revision(databases):
    hand = databases["hand"]
    ok(_psql(operator_sql(), hand, autocommit=True))
    ok(_psql("UPDATE alembic_version SET version_num = '021_map_email_traceability'", hand))
    try:
        refused = _psql(operator_sql(), hand, autocommit=True)
        assert refused.returncode != 0
        assert "expected alembic_version" in refused.stderr
        assert (
            ok(_psql("SELECT version_num FROM alembic_version", hand))
            == "021_map_email_traceability"
        )
    finally:
        ok(_psql(f"UPDATE alembic_version SET version_num = '{HEAD}'", hand))


def _seed_device(url) -> dict:
    ids = {key: uuid.uuid4() for key in ["org", "user", "client", "device", "enrolment"]}
    ok(
        _psql(
            f"INSERT INTO organizations (id, name, slug) "
            f"VALUES ('{ids['org']}', 'Org', 'org-{ids['org'].hex[:8]}'); "
            "INSERT INTO users (id, email, is_service_account) "
            f"VALUES ('{ids['user']}', 'admin-{ids['user'].hex[:8]}@example.com', false); "
            "INSERT INTO oauth_clients (id, organization_id, created_by, client_id, "
            "client_secret_hash, client_secret_prefix, name) "
            f"VALUES ('{ids['client']}', '{ids['org']}', '{ids['user']}', "
            f"'jnd_{ids['client'].hex}', 'hash', '(device)', 'device-{ids['client'].hex[:8]}'); "
            "INSERT INTO device_clients (id, oauth_client_id, organization_id, template, label, "
            "status, approved_by, approved_at, created_at, updated_at) "
            f"VALUES ('{ids['device']}', '{ids['client']}', '{ids['org']}', 'nauta-edge-terminal', "
            f"'Terminal', 'active', '{ids['user']}', now(), now(), now()); "
            "INSERT INTO device_enrolments (id, organization_id, template, label, user_code, "
            "status, created_at, expires_at, approved_by, approved_at, device_id) "
            f"VALUES ('{ids['enrolment']}', '{ids['org']}', 'nauta-edge-terminal', 'Terminal', "
            f"'{ids['enrolment'].hex[:4].upper()}-{ids['enrolment'].hex[4:8].upper()}', "
            f"'approved', now(), now(), '{ids['user']}', now(), '{ids['device']}')",
            url,
        )
    )
    return ids


def test_foreign_keys_cascade_and_set_null(databases):
    head = databases["head"]
    ok(_alembic(["upgrade", HEAD], head))
    ids = _seed_device(head)
    assert (
        ok(
            _psql(
                f"SELECT boot_alternations FROM device_clients WHERE id = '{ids['device']}'", head
            )
        )
        == "0"
    )

    # Deleting the OAuth client removes its device record; the enrolment keeps
    # its history with the device pointer cleared.
    ok(_psql(f"DELETE FROM oauth_clients WHERE id = '{ids['client']}'", head))
    assert (
        ok(_psql(f"SELECT count(*) FROM device_clients WHERE id = '{ids['device']}'", head)) == "0"
    )
    assert (
        ok(
            _psql(
                f"SELECT device_id IS NULL FROM device_enrolments WHERE id = '{ids['enrolment']}'",
                head,
            )
        )
        == "True"
    )

    # Deleting the organization removes its enrolments.
    ok(_psql(f"DELETE FROM organizations WHERE id = '{ids['org']}'", head))
    assert (
        ok(_psql(f"SELECT count(*) FROM device_enrolments WHERE id = '{ids['enrolment']}'", head))
        == "0"
    )


def test_downgrade_removes_them_and_upgrade_is_reentrant(databases):
    head = databases["head"]
    ok(_alembic(["upgrade", HEAD], head))
    ok(_alembic(["downgrade", PARENT], head))
    for table in TABLES:
        assert ok(_psql(f"SELECT to_regclass('public.{table}') IS NULL", head)) == "True"
    ok(_alembic(["upgrade", HEAD], head))
    # Stamped back with the objects present: upgrade must skip, not collide.
    ok(_alembic(["stamp", PARENT], head))
    ok(_alembic(["upgrade", HEAD], head))
    assert ok(_psql("SELECT version_num FROM alembic_version", head)) == HEAD
