"""020_white_label_branding_columns: the Alembic revision and the owner SQL agree.

Same harness and skip/fail rule as test_email_engagement_migration.py (019):
skips without MIGRATION_TEST_DATABASE_URL locally, FAILS without it in CI. Two
scratch databases: `head` (Alembic to head) and `hand` (Alembic to 019, then the
owner SQL). It proves the SQL refuses a database at the wrong revision, or whose
table another role owns, without touching it; lands object-for-object on
Alembic's catalog; keeps an existing row's values; is idempotent; and leaves a
database a later `alembic upgrade head` treats as current. Then the branding
router runs against PostgreSQL itself (asyncpg, real UUID and VARCHAR widths),
and the revision downgrades and re-upgrades cleanly.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.test_migration_reentrancy import (
    URL_ENV_VAR,
    _alembic,
    _postgres_url,
    _psql,
    _with_database,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SQL_FILE = REPO_ROOT / "docs" / "ops" / "sql" / "020_white_label_branding_columns.sql"
HEAD = "020_white_label_branding_columns"
PARENT = "019_email_first_party_engagement"
GRANDPARENT = "018_email_events"
TABLE = "white_label_configurations"
NEW_COLUMNS = {
    "branding_level",
    "theme_mode",
    "logo_dark_url",
    "website_url",
    "accent_color",
    "background_color",
    "surface_color",
    "text_color",
    "font_family",
    "border_radius",
}


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


def _new_columns_present(url: str) -> set[str]:
    names = ", ".join(f"'{name}'" for name in sorted(NEW_COLUMNS))
    return set(
        _ok(
            _psql(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{TABLE}' AND column_name IN ({names})",
                url,
            )
        ).split()
    )


def _catalog(url: str) -> dict[str, str]:
    return {
        "columns": _ok(
            _psql(
                "SELECT column_name, data_type, character_maximum_length, is_nullable, "
                "coalesce(column_default, '') FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{TABLE}' ORDER BY column_name",
                url,
            )
        ),
        "indexes": _ok(
            _psql(
                "SELECT indexname, indexdef FROM pg_indexes "
                f"WHERE schemaname = 'public' AND tablename = '{TABLE}' ORDER BY indexname",
                url,
            )
        ),
        "constraints": _ok(
            _psql(
                "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
                f"WHERE conrelid = 'public.{TABLE}'::regclass ORDER BY conname",
                url,
            )
        ),
    }


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
    names = {kind: f"janua_white_label_{kind}_{uuid.uuid4().hex[:8]}" for kind in ("head", "hand")}
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


def test_owner_sql_refuses_then_matches_alembic_and_is_idempotent(databases) -> None:
    head, hand = databases["head"], databases["hand"]

    # One revision too far back: refuses and changes nothing.
    _ok(_alembic(["upgrade", GRANDPARENT], hand))
    _ok(_psql("GRANT SELECT, UPDATE ON alembic_version TO enclii", hand))
    refused = _psql(_sql_script(), hand, autocommit=True)
    assert refused.returncode != 0
    assert "expected alembic_version" in refused.stderr
    assert _version(hand) == GRANDPARENT
    assert _new_columns_present(hand) == set()

    # At 019 but the table belongs to another role: refuses and changes nothing.
    _ok(_alembic(["upgrade", PARENT], hand))
    refused = _psql(_sql_script(), hand, autocommit=True)
    assert refused.returncode != 0
    assert "expected enclii" in refused.stderr
    assert _version(hand) == PARENT
    assert _new_columns_present(hand) == set()

    # As production: the 000_init table is owned by enclii, and holds a row.
    org_id = uuid.uuid4()
    _ok(
        _psql(
            f"ALTER TABLE {TABLE} OWNER TO enclii; "
            "INSERT INTO organizations (id, name, slug) "
            f"VALUES ('{org_id}', 'Org', 'org-{org_id.hex[:8]}'); "
            f"INSERT INTO {TABLE} (id, organization_id, brand_name, primary_color, is_active) "
            f"VALUES ('{uuid.uuid4()}', '{org_id}', 'Org', '#2d2f86', true)",
            hand,
        )
    )
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _new_columns_present(hand) == NEW_COLUMNS
    assert _catalog(hand) == _catalog(head)
    row = _ok(
        _psql(
            f"SELECT brand_name, primary_color, is_active, accent_color IS NULL, "
            f"branding_level IS NULL FROM {TABLE}",
            hand,
        )
    )
    assert row == "Org\t#2d2f86\tTrue\tTrue\tTrue"

    # Re-running changes nothing and still succeeds.
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _ok(_psql("SELECT count(*) FROM alembic_version", hand)) == "1"
    assert _catalog(hand) == _catalog(head)

    # Alembic sees the hand-applied database as current.
    _ok(_alembic(["upgrade", HEAD], hand))
    assert _version(hand) == HEAD


async def test_branding_router_round_trips_on_postgresql(databases) -> None:
    """POST, PUT and GET through the real router and model on PostgreSQL."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.database import get_db
    from app.dependencies import get_current_user
    from app.models import Organization
    from app.routers.v1 import white_label

    url = databases["head"].replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        org_id = uuid.uuid4()
        async with factory() as db:
            db.add(Organization(id=org_id, name="Org PG", slug=f"org-pg-{org_id.hex[:8]}"))
            await db.commit()

        app = FastAPI()
        app.include_router(white_label.router, prefix="/api/v1")

        async def override_get_db():
            async with factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=uuid.uuid4(), is_admin=True
        )
        base = "/api/v1/white-label/branding"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            missing = await client.get(f"{base}/{org_id}")
            created = await client.post(
                base,
                params={"organization_id": str(org_id)},
                json={"company_name": "Org PG", "accent_color": "#f5a623"},
            )
            duplicate = await client.post(
                base, params={"organization_id": str(org_id)}, json={"company_name": "again"}
            )
            updated = await client.put(
                f"{base}/{org_id}",
                json={"company_website": "https://org.example.test", "border_radius": "4px"},
            )
            read = await client.get(f"{base}/{org_id}")
            malformed = await client.get(f"{base}/not-a-uuid")

        assert missing.status_code == 404
        assert created.status_code == 200, created.text
        assert duplicate.status_code == 400
        assert updated.status_code == 200, updated.text
        assert read.status_code == 200
        body = read.json()
        assert body["company_name"] == "Org PG"
        assert body["accent_color"] == "#f5a623"
        assert body["company_website"] == "https://org.example.test"
        assert body["border_radius"] == "4px"
        assert body["branding_level"] == "basic"
        assert body["is_enabled"] is True
        assert malformed.status_code == 404
    finally:
        await engine.dispose()


def test_alembic_downgrade_then_upgrade(databases) -> None:
    """Runs last: drops and re-adds the 020 columns on the `head` database."""
    url = databases["head"]
    assert _version(url) == HEAD
    _ok(_alembic(["downgrade", PARENT], url))
    assert _version(url) == PARENT
    assert _new_columns_present(url) == set()

    _ok(_alembic(["upgrade", HEAD], url))
    assert _version(url) == HEAD
    assert _new_columns_present(url) == NEW_COLUMNS
