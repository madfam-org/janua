"""PostgreSQL parity for021: reviewed operator SQL, receipt constraints, replay."""

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
PARENT = "020_org_authentication_policy"
HEAD = "021_map_email_traceability"
SQL = Path(__file__).resolve().parents[4] / "docs/ops/sql/021_map_email_traceability.sql"


def ok(result):
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@pytest.fixture(scope="module")
def databases():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI") or os.environ.get("JANUA_REQUIRE_LOCAL_PG_TESTS"):
            pytest.fail(f"{URL_ENV_VAR} must reach the isolated PostgreSQL service")
        pytest.skip(f"{URL_ENV_VAR} is not configured locally")
    ok(
        _psql(
            "DO $$ BEGIN IF NOT EXISTS(SELECT1 FROM pg_roles WHERE rolname='enclii') THEN CREATE ROLE enclii NOLOGIN; END IF; IF NOT EXISTS(SELECT1 FROM pg_roles WHERE rolname='janua') THEN CREATE ROLE janua NOLOGIN; END IF; END $$".replace(
                "SELECT1", "SELECT 1"
            ),
            base,
            autocommit=True,
        )
    )
    names = {key: f"janua_mail_{key}_{uuid.uuid4().hex[:10]}" for key in ["head", "hand"]}
    created = []
    try:
        for name in names.values():
            ok(_psql(f'CREATE DATABASE "{name}"', base, autocommit=True))
            created.append(name)
        urls = {key: _with_database(base, name) for key, name in names.items()}
        for url in urls.values():
            ok(_alembic(["upgrade", PARENT], url))
        yield urls
    finally:
        for name in created:
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def catalog(url):
    result = {}
    for table in ["email_send_audits", "email_events", "payment_mail_dispatches"]:
        result[table] = ok(
            _psql(
                f"SELECT column_name,data_type,character_maximum_length,is_nullable,coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='public' AND table_name='{table}' ORDER BY column_name",
                url,
            )
        )
        result[table + ".constraints"] = ok(
            _psql(
                f"SELECT contype,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.{table}'::regclass ORDER BY contype,pg_get_constraintdef(oid)",
                url,
            )
        )
        result[table + ".indexes"] = ok(
            _psql(
                f"SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='{table}' ORDER BY indexname",
                url,
            )
        )
    return result


def test_native_operator_sql_matches_alembic_and_retains_receipts(databases):
    head, hand = databases["head"], databases["hand"]
    ok(_alembic(["upgrade", HEAD], head))
    ok(
        _psql(
            "GRANT CREATE,USAGE ON SCHEMA public TO enclii; GRANT SELECT,UPDATE ON alembic_version TO enclii; GRANT REFERENCES ON magic_links TO enclii; ALTER TABLE email_events OWNER TO enclii; ALTER TABLE payment_mail_dispatches OWNER TO enclii",
            hand,
        )
    )
    sql = "\n".join(
        line for line in SQL.read_text().splitlines() if not line.lstrip().startswith("\\")
    )
    ok(_psql(sql, hand, autocommit=True))
    assert catalog(head) == catalog(hand)
    before = catalog(hand)
    ok(_psql(sql, hand, autocommit=True))
    assert catalog(hand) == before
    assert ok(_psql("SELECT version_num FROM alembic_version", hand)) == HEAD
    identity = uuid.uuid4()
    ok(
        _psql(
            f"INSERT INTO email_send_audits(id,source_app,message_kind,trigger_kind,provenance,state,created_at) VALUES('{identity}','crea-map','magic_login','map_login_request','registered_map_login','pending',now())",
            hand,
        )
    )
    invalid = _psql(f"UPDATE email_send_audits SET state='accepted' WHERE id='{identity}'", hand)
    assert invalid.returncode != 0 and "ck_email_send_audit" in invalid.stderr
    ok(_alembic(["downgrade", PARENT], hand))
    assert ok(_psql("SELECT count(*) FROM email_send_audits", hand)) == "1"
    assert "email" not in {line.split("\t")[0] for line in before["email_send_audits"].splitlines()}
