"""019_email_first_party_engagement: the Alembic revision and the owner SQL agree.

Same harness, same skip/fail rule and same shape as test_email_events_migration.py
(018): skips without MIGRATION_TEST_DATABASE_URL locally, FAILS without it in CI.
Two scratch databases: `head` (Alembic to head) and `hand` (Alembic to 018, then
the owner SQL). It proves the SQL refuses a database at the wrong revision
without touching it, lands object-for-object on Alembic's catalog for BOTH tables
it touches, grants exactly what it says, is idempotent, and leaves a database a
later `alembic upgrade head` treats as current; that the receiver's and the
first-party insert paths and the token-row UPDATE work on PostgreSQL; and that
the revision downgrades and re-upgrades cleanly.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
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
SQL_FILE = REPO_ROOT / "docs" / "ops" / "sql" / "019_email_first_party_engagement.sql"
HEAD = "019_email_first_party_engagement"
PARENT = "018_email_events"
GRANDPARENT = "017_payment_mail_dispatch"
TABLES = ("email_events", "email_tracking_links")


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


def _links_absent(url: str) -> bool:
    return _ok(_psql("SELECT to_regclass('public.email_tracking_links')", url)) in ("", "None")


def _catalog(url: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for table in TABLES:
        catalog[f"{table}.columns"] = _ok(
            _psql(
                "SELECT column_name, data_type, character_maximum_length, is_nullable, "
                "coalesce(column_default, '') FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{table}' ORDER BY column_name",
                url,
            )
        )
        catalog[f"{table}.indexes"] = _ok(
            _psql(
                "SELECT indexname, indexdef FROM pg_indexes "
                f"WHERE schemaname = 'public' AND tablename = '{table}' ORDER BY indexname",
                url,
            )
        )
        catalog[f"{table}.constraints"] = _ok(
            _psql(
                "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
                f"WHERE conrelid = 'public.{table}'::regclass ORDER BY conname",
                url,
            )
        )
    return catalog


def _grants(url: str, table: str) -> list[str]:
    return _ok(
        _psql(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            f"WHERE table_name = '{table}' AND grantee = 'janua' ORDER BY 1",
            url,
        )
    ).split()


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
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janua') "
        "THEN CREATE ROLE janua NOLOGIN; END IF; "
        "END $$",
        base,
        autocommit=True,
    )
    names = {kind: f"janua_engagement_{kind}_{uuid.uuid4().hex[:8]}" for kind in ("head", "hand")}
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


def test_owner_sql_refuses_wrong_revision_then_matches_alembic_and_is_idempotent(
    databases,
) -> None:
    head, hand = databases["head"], databases["hand"]

    # One revision too far back: refuses and changes nothing.
    _ok(_alembic(["upgrade", GRANDPARENT], hand))
    _ok(
        _psql(
            "GRANT CREATE, USAGE ON SCHEMA public TO enclii; "
            "GRANT SELECT, UPDATE ON alembic_version TO enclii",
            hand,
        )
    )
    refused = _psql(_sql_script(), hand, autocommit=True)
    assert refused.returncode != 0
    assert "expected alembic_version" in refused.stderr
    assert _version(hand) == GRANDPARENT
    assert _links_absent(hand)

    # At 018, as production is after the 018 SQL: 018's objects are owned by
    # enclii there, so reproduce that before applying 019 as enclii.
    _ok(_alembic(["upgrade", PARENT], hand))
    _ok(
        _psql(
            "ALTER TABLE email_events OWNER TO enclii; "
            "GRANT SELECT, INSERT ON email_events TO janua",
            hand,
        )
    )
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _catalog(hand) == _catalog(head)

    owner = _psql("SELECT tableowner FROM pg_tables WHERE tablename = 'email_tracking_links'", hand)
    assert _ok(owner) == "enclii"
    assert _grants(hand, "email_tracking_links") == ["INSERT", "SELECT", "UPDATE"]
    # email_events stays append-only for the app role.
    assert _grants(hand, "email_events") == ["INSERT", "SELECT"]

    # Re-running changes nothing and still succeeds.
    _ok(_psql(_sql_script(), hand, autocommit=True))
    assert _version(hand) == HEAD
    assert _ok(_psql("SELECT count(*) FROM alembic_version", hand)) == "1"
    assert _catalog(hand) == _catalog(head)

    # Alembic sees the hand-applied database as current.
    _ok(_alembic(["upgrade", HEAD], hand))
    assert _version(hand) == HEAD


def test_existing_webhook_rows_read_as_webhook_after_the_sql(databases) -> None:
    hand = databases["hand"]
    _ok(
        _psql(
            "INSERT INTO email_events (cuenta, svix_id, email_id, event_type, occurred_at, "
            "received_at) VALUES ('ctm', 'msg_pre', 'e1', 'email.delivered', now(), now())",
            hand,
        )
    )
    assert (
        _ok(_psql("SELECT source FROM email_events WHERE svix_id = 'msg_pre'", hand)) == "webhook"
    )


async def test_insert_paths_and_token_binding_on_postgresql(databases, monkeypatch) -> None:
    """The production inserts (ON CONFLICT DO NOTHING ... RETURNING on asyncpg)
    for a webhook row and a first-party row, the token-row insert + UPDATE the
    send path does, and the feed reading both back."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.services import email_engagement
    from app.services.email_events import (
        ParsedEvent,
        feed_page,
        list_events,
        record_event,
    )
    from app.services.sender_binding import CTM_BINDING

    url = databases["head"]
    engine = create_async_engine(url.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr(email_engagement, "session_factory", factory)
        from app.config import settings

        monkeypatch.setattr(settings, "CTM_TRACKING_HOST", "https://enlaces.creatumundo.mx")
        email_engagement.throttle.reset()

        webhook = ParsedEvent(
            email_id="email-1",
            event_type="email.delivered",
            occurred_at=datetime(2026, 9, 25, 15, 0, 0),
            source_app="crea-map",
            org_id=None,
        )
        async with factory() as session:
            assert await record_event(session, "ctm", "msg_pg_1", webhook) is True
        async with factory() as session:
            assert await record_event(session, "ctm", "msg_pg_1", webhook) is False

        prepared = await email_engagement.prepare_engagement(
            requested=True,
            html='<html><body><a href="https://map.creatumundo.mx/pagos">Pagar</a></body></html>',
            token_link=False,
            binding=CTM_BINDING,
            sender_address="hola@creatumundo.mx",
            tags=[{"name": "source_app", "value": "crea-map"}],
        )
        assert prepared is not None
        assert await email_engagement.bind_email_id(prepared.token_hash, "email-1") is True
        token = prepared.html.split("/e/c/")[1].split("/")[0]
        async with factory() as session:
            link = await email_engagement.find_link(session, token)
            assert link is not None and link.email_id == "email-1"
            assert await email_engagement.record_hit(
                session,
                link,
                kind="c",
                index=0,
                prefetch=False,
                target="https://map.creatumundo.mx/pagos",
            )
        email_engagement.throttle.reset()
        async with factory() as session:
            link = await email_engagement.find_link(session, token)
            assert link is not None
            assert not await email_engagement.record_hit(
                session,
                link,
                kind="c",
                index=0,
                prefetch=False,
                target="https://map.creatumundo.mx/pagos",
            )

        async with factory() as session:
            rows = await list_events(session, "crea-map", 0, 10, settle_seconds=-60)
            page = feed_page(list(rows), 0)
        types = [(e["type"], e.get("source")) for e in page["events"]]
        assert types == [("delivered", None), ("clicked", "first_party")]
        assert page["events"][1]["click_link"] == "https://map.creatumundo.mx/pagos"
        assert page["events"][1]["provider"] == "resend"
    finally:
        await engine.dispose()


def test_alembic_downgrade_then_upgrade(databases) -> None:
    """Runs last: drops and recreates the 019 objects on the `head` database."""
    url = databases["head"]
    assert _version(url) == HEAD
    _ok(_alembic(["downgrade", PARENT], url))
    assert _version(url) == PARENT
    assert _links_absent(url)
    columns = _ok(
        _psql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'email_events' AND column_name IN ('source', 'possible_prefetch')",
            url,
        )
    )
    assert columns == ""

    _ok(_alembic(["upgrade", HEAD], url))
    assert _version(url) == HEAD
    assert not _links_absent(url)
