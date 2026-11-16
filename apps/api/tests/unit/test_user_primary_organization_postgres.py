"""PostgreSQL parity for 022: reviewed operator SQL vs alembic, replay, cascades.

`docs/ops/sql/022_user_primary_organization.sql` is what an operator applies by
hand (promote and the staging overlay run no migrations). It must produce the
same catalog as `alembic upgrade` of revision 022, be safe to run twice, refuse
a database at the wrong revision, grant the app role no DELETE, and leave
foreign keys that cascade when a user or an organization is deleted.

The availability half — an image with this code on a database WITHOUT the
table still mints tokens — is pinned against SQLite in
tests/unit/services/test_primary_organization_claims.py; the last test here
repeats it on PostgreSQL, where a failed statement aborts the transaction.
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
        # Production shape for the hand-applied side: the migration role runs
        # the DDL under SET LOCAL ROLE and owns what it creates.
        ok(
            _psql(
                "GRANT CREATE, USAGE ON SCHEMA public TO enclii; "
                "GRANT SELECT, UPDATE ON alembic_version TO enclii; "
                "GRANT REFERENCES ON organizations, users TO enclii",
                urls["hand"],
            )
        )
        yield urls
    finally:
        for name in created:
            _psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', base, autocommit=True)


def catalog(url):
    table = "user_primary_organizations"
    return {
        "columns": ok(
            _psql(
                "SELECT column_name, data_type, character_maximum_length, is_nullable, "
                "coalesce(column_default, '') FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{table}' ORDER BY column_name",
                url,
            )
        ),
        "constraints": ok(
            _psql(
                "SELECT conname, contype, convalidated, pg_get_constraintdef(oid) "
                f"FROM pg_constraint WHERE conrelid = 'public.{table}'::regclass "
                "ORDER BY conname",
                url,
            )
        ),
        "indexes": ok(
            _psql(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' "
                f"AND tablename = '{table}' ORDER BY indexname",
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
    assert "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE" in before["constraints"]
    assert (
        "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE"
        in before["constraints"]
    )
    assert ok(
        _psql(
            "SELECT tableowner FROM pg_tables WHERE tablename = 'user_primary_organizations'",
            hand,
        )
    ) == "enclii"
    privileges = ok(
        _psql(
            "SELECT has_table_privilege('janua', 'user_primary_organizations', 'SELECT'), "
            "has_table_privilege('janua', 'user_primary_organizations', 'INSERT'), "
            "has_table_privilege('janua', 'user_primary_organizations', 'UPDATE'), "
            "has_table_privilege('janua', 'user_primary_organizations', 'DELETE')",
            hand,
        )
    )
    # `janua` is the CI service's superuser, so these read True there; the
    # grant itself is checked by name below, which a superuser does not mask.
    assert privileges.split("\t")[:3] == ["True", "True", "True"]
    grants = ok(
        _psql(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE table_name = 'user_primary_organizations' AND grantee = 'janua' "
            "ORDER BY 1",
            hand,
        )
    )
    assert grants.splitlines() == ["INSERT", "SELECT", "UPDATE"]


def test_operator_sql_refuses_a_database_at_the_wrong_revision(databases):
    hand = databases["hand"]
    ok(_psql(operator_sql(), hand, autocommit=True))
    ok(_psql("UPDATE alembic_version SET version_num = '020_org_authentication_policy'", hand))
    try:
        refused = _psql(operator_sql(), hand, autocommit=True)
        assert refused.returncode != 0
        assert "expected alembic_version" in refused.stderr
        assert (
            ok(_psql("SELECT version_num FROM alembic_version", hand))
            == "020_org_authentication_policy"
        )
    finally:
        ok(_psql(f"UPDATE alembic_version SET version_num = '{HEAD}'", hand))


def _seed_pointer(url) -> tuple[uuid.UUID, uuid.UUID]:
    org, user = uuid.uuid4(), uuid.uuid4()
    ok(
        _psql(
            f"INSERT INTO organizations (id, name, slug) VALUES ('{org}', 'Org', 'org-{org.hex[:8]}'); "
            "INSERT INTO users (id, email, is_service_account) "
            f"VALUES ('{user}', 'staff-{user.hex[:8]}@example.com', false); "
            "INSERT INTO user_primary_organizations (user_id, organization_id, set_by, set_at) "
            f"VALUES ('{user}', '{org}', 'test', now())",
            url,
        )
    )
    return org, user


def test_foreign_keys_refuse_unknown_rows_and_cascade_deletes(databases):
    head = databases["head"]
    ok(_alembic(["upgrade", HEAD], head))
    org, user = _seed_pointer(head)

    unknown = _psql(
        "UPDATE user_primary_organizations "
        f"SET organization_id = '{uuid.uuid4()}' WHERE user_id = '{user}'",
        head,
    )
    assert unknown.returncode != 0 and "foreign key" in unknown.stderr.lower()

    ok(_psql(f"DELETE FROM organizations WHERE id = '{org}'", head))
    assert ok(
        _psql(f"SELECT count(*) FROM user_primary_organizations WHERE user_id = '{user}'", head)
    ) == "0"

    org, user = _seed_pointer(head)
    ok(_psql(f"DELETE FROM users WHERE id = '{user}'", head))
    assert ok(
        _psql(f"SELECT count(*) FROM user_primary_organizations WHERE user_id = '{user}'", head)
    ) == "0"


def test_downgrade_removes_it_and_upgrade_is_reentrant(databases):
    head = databases["head"]
    ok(_alembic(["upgrade", HEAD], head))
    ok(_alembic(["downgrade", PARENT], head))
    assert ok(
        _psql("SELECT to_regclass('public.user_primary_organizations') IS NULL", head)
    ) == "True"
    ok(_alembic(["upgrade", HEAD], head))
    # Stamped back with the objects present: upgrade must skip, not collide.
    ok(_alembic(["stamp", PARENT], head))
    ok(_alembic(["upgrade", HEAD], head))
    assert ok(_psql("SELECT version_num FROM alembic_version", head)) == HEAD


@pytest.mark.asyncio
async def test_without_the_table_a_multi_org_login_still_mints_on_postgresql(databases):
    """PostgreSQL aborts a transaction on a failed statement; the savepoint is
    what keeps the caller's transaction usable. Real resolver, real session
    mint, database at 021 (no table)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import jwt as pyjwt
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Organization, OrganizationMember, User, UserStatus
    from app.services.auth_service import AuthService

    url = databases["hand"]
    ok(_alembic(["downgrade", PARENT], url))
    try:
        engine = create_async_engine(url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        user_id = uuid.uuid4()
        async with factory() as db:
            db.add(
                User(
                    id=user_id,
                    email=f"staff-{user_id.hex[:8]}@example.com",
                    status=UserStatus.ACTIVE,
                    user_metadata={},
                )
            )
            for _ in range(2):
                org_id = uuid.uuid4()
                db.add(Organization(id=org_id, name="O", slug=f"o-{org_id.hex[:8]}"))
                await db.flush()
                db.add(
                    OrganizationMember(
                        id=uuid.uuid4(), organization_id=org_id, user_id=user_id,
                        role="member", status="active",
                    )
                )
            await db.commit()

        async with factory() as db:
            user = await db.get(User, user_id)
            with (
                patch(
                    "app.services.entitlements_service.get_user_entitlements",
                    AsyncMock(return_value=[]),
                ),
                patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
                patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
            ):
                access_token, _refresh, session = await AuthService.create_session(
                    db=db, user=user, enforce_session_limit=False
                )
        claims = pyjwt.decode(access_token, options={"verify_signature": False})
        assert len(claims["orgs"]) == 2
        assert "org_id" not in claims and "roles" not in claims

        # The session row the mint wrote AFTER the failed read was committed.
        async with factory() as db:
            from app.models import Session

            assert await db.get(Session, session.id) is not None
        await engine.dispose()
    finally:
        ok(_alembic(["upgrade", HEAD], url))
