"""PostgreSQL proof for additive migration, guarded SQL and real version races."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.unit.test_migration_reentrancy import (
    URL_ENV_VAR,
    _alembic,
    _postgres_url,
    _psql,
    _with_database,
)

pytestmark = pytest.mark.database
HEAD = "020_org_authentication_policy"
PARENT = "019_email_first_party_engagement"
SQL_FILE = (
    Path(__file__).resolve().parents[4] / "docs/ops/sql/020_organization_authentication_policy.sql"
)
TABLES = ("organization_authentication_policies", "organization_authentication_policy_changes")


def ok(result):
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@pytest.fixture(scope="module")
def databases():
    base = _postgres_url()
    if base is None:
        if os.environ.get("CI"):
            pytest.fail(f"{URL_ENV_VAR} must reach the isolated PostgreSQL service")
        pytest.skip(f"{URL_ENV_VAR} not configured")
    ok(
        _psql(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='enclii') THEN CREATE ROLE enclii NOLOGIN; END IF; "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='janua') THEN CREATE ROLE janua NOLOGIN; END IF; "
            "END $$",
            base,
            autocommit=True,
        )
    )
    names = {key: f"janua_auth_{key}_{uuid.uuid4().hex[:8]}" for key in ("head", "hand", "race")}
    for name in names.values():
        ok(_psql(f'CREATE DATABASE "{name}"', base, autocommit=True))
    urls = {key: _with_database(base, name) for key, name in names.items()}
    try:
        for key in ("head", "hand"):
            ok(_alembic(["upgrade", PARENT], urls[key]))
            actor, session = uuid.uuid4(), uuid.uuid4()
            # An existing session must survive both upgrade paths without
            # acquiring invented authentication or second-factor evidence.
            ok(
                _psql(
                    f"INSERT INTO users (id,email) VALUES ('{actor}','legacy@example.invalid'); "
                    "INSERT INTO sessions (id,user_id,token,expires_at) "
                    f"VALUES ('{session}','{actor}','synthetic-legacy-session',now()+interval '1 hour')",
                    urls[key],
                )
            )
        ok(_alembic(["upgrade", HEAD], urls["head"]))
        ok(_alembic(["upgrade", HEAD], urls["race"]))
        yield urls
    finally:
        for name in names.values():
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def catalog(url):
    return {
        table: ok(
            _psql(
                "SELECT column_name,data_type,is_nullable,coalesce(column_default,'') "
                "FROM information_schema.columns "
                f"WHERE table_name='{table}' ORDER BY column_name",
                url,
            )
        )
        for table in (*TABLES, "sessions")
    } | {
        table
        + ".constraints": ok(
            _psql(
                # SQLAlchemy applies its naming convention to generated names;
                # compare constraint semantics, including every FK/check/unique key.
                "SELECT contype,pg_get_constraintdef(oid) FROM pg_constraint "
                f"WHERE conrelid='public.{table}'::regclass ORDER BY contype,pg_get_constraintdef(oid)",
                url,
            )
        )
        for table in TABLES
    }


def test_reviewed_sql_matches_alembic_is_reentrant_and_limits_journal_privileges(databases):
    head, hand = databases["head"], databases["hand"]
    ok(
        _psql(
            "GRANT CREATE,USAGE ON SCHEMA public TO enclii; "
            "GRANT SELECT,UPDATE ON alembic_version TO enclii; "
            "GRANT REFERENCES ON organizations,users TO enclii; "
            "ALTER TABLE sessions OWNER TO enclii",
            hand,
        )
    )
    sql = "\n".join(
        line for line in SQL_FILE.read_text().splitlines() if not line.lstrip().startswith("\\")
    )
    ok(_psql(sql, hand, autocommit=True))
    assert catalog(head) == catalog(hand)
    for url in (head, hand):
        assert (
            ok(
                _psql(
                    "SELECT authentication_methods::text,authenticated_at IS NULL,mfa_verified_at IS NULL "
                    "FROM sessions",
                    url,
                )
            )
            == "[]\tTrue\tTrue"
        )
    before = catalog(hand)
    ok(_psql(sql, hand, autocommit=True))
    assert catalog(hand) == before
    assert ok(_psql("SELECT version_num FROM alembic_version", hand)) == HEAD
    assert ok(
        _psql(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE table_name='organization_authentication_policy_changes' AND grantee='janua' "
            "ORDER BY privilege_type",
            hand,
        )
    ).splitlines() == ["INSERT", "SELECT"]
    # Populated objects with a stale ledger must not break upgrade.
    ok(_alembic(["stamp", PARENT], head))
    ok(_alembic(["upgrade", HEAD], head))
    assert catalog(head) == before


def test_wrong_sql_parent_is_refused_without_changing_the_ledger(databases):
    hand = databases["hand"]
    sql = "\n".join(
        line for line in SQL_FILE.read_text().splitlines() if not line.lstrip().startswith("\\")
    )
    ok(_psql("UPDATE alembic_version SET version_num='018_email_events'", hand))
    result = _psql(sql, hand, autocommit=True)
    assert result.returncode != 0 and "expected alembic_version" in result.stderr
    assert ok(_psql("SELECT version_num FROM alembic_version", hand)) == "018_email_events"
    ok(_psql(f"UPDATE alembic_version SET version_num='{HEAD}'", hand))


@pytest.mark.asyncio
async def test_postgres_compare_and_swap_has_one_winner_and_one_atomic_history_row(
    databases, monkeypatch
):
    from app.models import Organization, User, UserStatus
    from app.models.organization_authentication_policy import OrganizationAuthenticationPolicyChange
    from app.services import organization_authentication_policy as service

    engine = create_async_engine(databases["race"])
    sf = async_sessionmaker(engine, expire_on_commit=False)
    actor, org = uuid.uuid4(), uuid.uuid4()
    async with sf() as db:
        db.add(User(id=actor, email="policy-race@example.invalid", status=UserStatus.ACTIVE))
        db.add(Organization(id=org, name="Race", slug="auth-race"))
        await db.commit()
        await service.update_authentication_policy(
            db,
            org,
            mfa_mode="optional",
            expected_version=0,
            actor_id=actor,
            reason="Initial optional policy",
        )
    original = service.get_authentication_policy
    gate = asyncio.Barrier(2)

    async def same_version(db, organization_id):
        policy = await original(db, organization_id)
        await gate.wait()
        return policy

    monkeypatch.setattr(service, "get_authentication_policy", same_version)

    async def update(mode):
        async with sf() as db:
            try:
                return await service.update_authentication_policy(
                    db,
                    org,
                    mfa_mode=mode,
                    expected_version=1,
                    actor_id=actor,
                    reason="Concurrent reviewed version",
                )
            except service.PolicyVersionConflict:
                return "conflict"

    results = await asyncio.gather(update("required"), update("optional"))
    assert results.count("conflict") == 1
    async with sf() as db:
        policy = await original(db, org)
        assert policy.version == 2
        count = (
            await db.execute(
                select(func.count())
                .select_from(OrganizationAuthenticationPolicyChange)
                .where(OrganizationAuthenticationPolicyChange.organization_id == org)
            )
        ).scalar_one()
        assert count == 2
    # Refuse a schema downgrade while any row requires MFA.
    ok(
        _psql(
            "UPDATE organization_authentication_policies SET mfa_mode='required'", databases["race"]
        )
    )
    result = _alembic(["downgrade", PARENT], databases["race"])
    assert result.returncode != 0 and "Refuse downgrade" in result.stderr
    await engine.dispose()
