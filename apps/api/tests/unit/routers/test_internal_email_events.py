"""GET /api/v1/internal/email/events: the per-app feed contract MAP codes against.

Auth matrix mirrors the other internal routes (422 missing header / 401 wrong
key / 503 unconfigured). Rows are inserted directly so the tests control the
cursor, the scope and the settle window exactly.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.email_event import EmailEvent

URL = "/api/v1/internal/email/events"
INTERNAL_KEY = "test-internal-api-key-email-events"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}
OLD = datetime.utcnow() - timedelta(minutes=10)


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    previous = settings.INTERNAL_API_KEY
    settings.INTERNAL_API_KEY = INTERNAL_KEY
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    settings.INTERNAL_API_KEY = previous
    await engine.dispose()


_counter = {"n": 0}


def _event(source_app, event_type="email.delivered", received_at=OLD, **extra):
    _counter["n"] += 1
    n = _counter["n"]
    return EmailEvent(
        provider="resend",
        cuenta="ctm",
        svix_id=f"msg_{n}",
        email_id=f"email-{n}",
        event_type=event_type,
        occurred_at=datetime(2026, 9, 23, 15, 0, n % 60),
        source_app=source_app,
        org_id=None,
        received_at=received_at,
        **extra,
    )


async def _seed(factory, *events):
    async with factory() as session:
        session.add_all(events)
        await session.commit()
        return [e.id for e in events]


# --------------------------------------------------------------------------
# Auth: the same X-Internal-API-Key dependency as /internal/email/send
# --------------------------------------------------------------------------


async def test_missing_key_is_rejected(env):
    client, _ = env
    assert (await client.get(URL, params={"source_app": "crea-map"})).status_code == 422


async def test_wrong_key_is_401(env):
    client, _ = env
    response = await client.get(
        URL, params={"source_app": "crea-map"}, headers={"X-Internal-API-Key": "wrong"}
    )
    assert response.status_code == 401


async def test_unconfigured_internal_api_is_503(env):
    client, _ = env
    settings.INTERNAL_API_KEY = None
    response = await client.get(URL, params={"source_app": "crea-map"}, headers=AUTH)
    assert response.status_code == 503


# --------------------------------------------------------------------------
# Contract, scoping, ordering, pagination
# --------------------------------------------------------------------------


async def test_contract_shape_and_type_prefix(env):
    client, factory = env
    ids = await _seed(
        factory,
        _event("crea-map", "email.delivered"),
        _event("crea-map", "email.bounced", bounce_type="Permanent", bounce_subtype="General"),
        _event("crea-map", "email.clicked", click_link="https://map.creatumundo.mx/agenda"),
    )
    response = await client.get(URL, params={"source_app": "crea-map"}, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"events", "next_cursor"}
    delivered, bounced, clicked = body["events"]
    # Optional keys are omitted, never null.
    assert set(delivered) == {"cursor", "provider", "email_id", "type", "occurred_at"}
    assert delivered["type"] == "delivered"
    assert delivered["provider"] == "resend"
    assert delivered["cursor"] == ids[0]
    assert delivered["occurred_at"].endswith("Z")
    assert bounced["type"] == "bounced"
    assert (bounced["bounce_type"], bounced["bounce_subtype"]) == ("Permanent", "General")
    assert "click_link" not in bounced
    assert clicked["type"] == "clicked"
    assert clicked["click_link"] == "https://map.creatumundo.mx/agenda"
    assert body["next_cursor"] == ids[-1]


async def test_scoped_to_source_app(env):
    client, factory = env
    ids = await _seed(
        factory,
        _event("crea-map"),
        _event("dhanam"),
        _event(None),
        _event("crea-map"),
        _event("crea-map-staging"),
    )
    body = (await client.get(URL, params={"source_app": "crea-map"}, headers=AUTH)).json()
    assert [e["cursor"] for e in body["events"]] == [ids[0], ids[3]]


async def test_ordered_by_cursor_and_paginated(env):
    client, factory = env
    ids = await _seed(factory, *[_event("crea-map") for _ in range(7)])
    seen = []
    after = 0
    pages = 0
    while True:
        body = (
            await client.get(
                URL, params={"source_app": "crea-map", "after": after, "limit": 3}, headers=AUTH
            )
        ).json()
        pages += 1
        if not body["events"]:
            assert body["next_cursor"] == after  # empty page: keep your cursor
            break
        cursors = [e["cursor"] for e in body["events"]]
        assert cursors == sorted(cursors)
        assert all(c > after for c in cursors)
        seen.extend(cursors)
        after = body["next_cursor"]
    assert seen == ids
    assert pages == 4  # 3 + 3 + 1 + empty


async def test_after_skips_what_was_already_read(env):
    client, factory = env
    ids = await _seed(factory, *[_event("crea-map") for _ in range(4)])
    body = (
        await client.get(URL, params={"source_app": "crea-map", "after": ids[1]}, headers=AUTH)
    ).json()
    assert [e["cursor"] for e in body["events"]] == ids[2:]


async def test_events_inside_the_settle_window_are_held_back(env):
    """A just-received row is invisible for a few seconds so a concurrent insert
    with a lower cursor cannot commit behind a poller's back."""
    client, factory = env
    old_id, fresh_id = await _seed(
        factory, _event("crea-map"), _event("crea-map", received_at=datetime.utcnow())
    )
    body = (await client.get(URL, params={"source_app": "crea-map"}, headers=AUTH)).json()
    assert [e["cursor"] for e in body["events"]] == [old_id]
    assert body["next_cursor"] == old_id


async def test_empty_feed(env):
    client, _ = env
    body = (
        await client.get(URL, params={"source_app": "crea-map", "after": 42}, headers=AUTH)
    ).json()
    assert body == {"events": [], "next_cursor": 42}


@pytest.mark.parametrize(
    "params",
    [
        {"source_app": "crea-map", "limit": 0},
        {"source_app": "crea-map", "limit": 501},
        {"source_app": "crea-map", "limit": -1},
        {"source_app": "crea-map", "after": -1},
        {"source_app": ""},
        {},
    ],
)
async def test_bounds_are_enforced(env, params):
    client, _ = env
    assert (await client.get(URL, params=params, headers=AUTH)).status_code == 422


async def test_limit_500_is_the_maximum_and_is_honoured(env):
    client, factory = env
    await _seed(factory, *[_event("crea-map") for _ in range(3)])
    body = (
        await client.get(URL, params={"source_app": "crea-map", "limit": 500}, headers=AUTH)
    ).json()
    assert len(body["events"]) == 3
    body = (
        await client.get(URL, params={"source_app": "crea-map", "limit": 1}, headers=AUTH)
    ).json()
    assert len(body["events"]) == 1
