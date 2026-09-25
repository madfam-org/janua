"""GET /e/o/{token}.gif and GET /e/c/{token}/{index}: constant, closed, minimal.

- The pixel is the same bytes and headers for every token (valid, unknown,
  malformed) and even when the database fails.
- A click goes ONLY to the target stored for (token, index); everything else
  (unknown token, bad index, a URL in the query, a DB failure) gets the same
  fallback, chosen by the request Host alone.
- Unknown or malformed tokens write nothing; known ones write one deduped,
  minimized row (no IP, no user agent) that the per-app feed serves.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.email_event import EmailEvent, EmailTrackingLink
from app.services import email_engagement
from app.services.email_engagement import PIXEL_GIF, hash_token, new_token

# The tracking host under test. In production it is e.g. enlaces.creatumundo.mx
# (CTM_TRACKING_HOST); TrustedHostMiddleware's list is fixed when app.main is
# imported, so the tests use a host the test environment already trusts and
# point CTM's tracking origin at it.
HOST = "testserver"
OTHER_HOST = "test"
INTERNAL_KEY = "test-internal-api-key-engagement"
LONG_AGO = datetime.utcnow() - timedelta(hours=1)
PERSON_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148"
TARGETS = ["https://map.creatumundo.mx/pagos?familia=1&mes=10", "https://www.creatumundo.mx/"]


@pytest_asyncio.fixture
async def env(monkeypatch):
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
    monkeypatch.setattr(settings, "CTM_TRACKING_HOST", f"https://{HOST}")
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)
    email_engagement.throttle.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"user-agent": PERSON_UA},
    ) as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    email_engagement.throttle.reset()
    await engine.dispose()


async def _seed(factory, *, email_id="resend-email-1", created_at=LONG_AGO) -> str:
    token, digest = new_token()
    async with factory() as session:
        session.add(
            EmailTrackingLink(
                token_hash=digest,
                cuenta="ctm",
                source_app="crea-map",
                org_id="org-ctm",
                email_id=email_id,
                links=json.dumps(TARGETS),
                created_at=created_at,
            )
        )
        await session.commit()
    return token


async def _events(factory):
    async with factory() as session:
        return list(
            (await session.execute(select(EmailEvent).order_by(EmailEvent.id))).scalars().all()
        )


async def _count(factory) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(EmailEvent))).scalar_one()


def _host(host: str = HOST):
    return {"host": host}


# ---------------------------------------------------------------------------
# Pixel
# ---------------------------------------------------------------------------


async def test_pixel_is_constant_for_valid_unknown_and_malformed_tokens(env):
    client, factory = env
    valid = await _seed(factory)
    unknown, _ = new_token()
    answers = []
    for token in (valid, unknown, "short", "x" * 43 + "!", "x" * 44):
        r = await client.get(f"/e/o/{token}.gif", headers=_host())
        answers.append(
            (r.status_code, r.content, r.headers["content-type"], r.headers["cache-control"])
        )
        assert "set-cookie" not in r.headers
    assert all(a == answers[0] for a in answers)
    assert answers[0][0] == 200 and answers[0][1] == PIXEL_GIF
    assert answers[0][2] == "image/gif" and "no-store" in answers[0][3]
    assert await _count(factory) == 1  # only the valid token wrote


async def test_pixel_records_one_minimized_open_and_dedupes(env):
    client, factory = env
    token = await _seed(factory)
    for _ in range(3):
        await client.get(f"/e/o/{token}.gif", headers=_host())
    email_engagement.throttle.reset()  # past the in-memory window, the DB still dedupes
    await client.get(f"/e/o/{token}.gif", headers=_host())
    [event] = await _events(factory)
    assert event.event_type == "email.opened"
    assert event.email_id == "resend-email-1"
    assert event.source == "first_party" and event.provider == "resend"
    assert event.possible_prefetch is False
    assert event.source_app == "crea-map" and event.org_id == "org-ctm" and event.cuenta == "ctm"
    assert event.click_link is None
    # Nothing request-derived beyond the flag: the table has no IP/UA columns.
    assert not {"ip", "ip_address", "user_agent"} & set(EmailEvent.__table__.columns.keys())


async def test_a_prefetch_does_not_hide_the_persons_open(env):
    client, factory = env
    token = await _seed(factory)
    await client.get(f"/e/o/{token}.gif", headers={**_host(), "user-agent": "Mozilla/5.0"})
    await client.get(f"/e/o/{token}.gif", headers={**_host(), "user-agent": "Mozilla/5.0"})
    await client.get(f"/e/o/{token}.gif", headers=_host())
    flags = [e.possible_prefetch for e in await _events(factory)]
    assert flags == [True, False]


async def test_a_hit_right_after_the_send_is_flagged(env):
    client, factory = env
    token = await _seed(factory, created_at=datetime.utcnow())
    await client.get(f"/e/o/{token}.gif", headers=_host())
    [event] = await _events(factory)
    assert event.possible_prefetch is True


async def test_pixel_for_an_unbound_message_writes_nothing(env):
    client, factory = env
    token = await _seed(factory, email_id=None)
    r = await client.get(f"/e/o/{token}.gif", headers=_host())
    assert r.status_code == 200 and r.content == PIXEL_GIF
    assert await _count(factory) == 0


async def test_pixel_survives_a_database_failure(env, monkeypatch):
    client, factory = env
    token = await _seed(factory)

    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.routers.v1.email_engagement.find_link", boom)
    r = await client.get(f"/e/o/{token}.gif", headers=_host())
    assert r.status_code == 200 and r.content == PIXEL_GIF


# ---------------------------------------------------------------------------
# Click
# ---------------------------------------------------------------------------


async def test_click_redirects_to_the_stored_target_and_records_it(env):
    client, factory = env
    token = await _seed(factory)
    r = await client.get(f"/e/c/{token}/0", headers=_host())
    assert r.status_code == 302
    assert r.headers["location"] == TARGETS[0]
    assert "no-store" in r.headers["cache-control"]
    assert "set-cookie" not in r.headers
    r = await client.get(f"/e/c/{token}/1", headers=_host())
    assert r.headers["location"] == TARGETS[1]
    events = await _events(factory)
    assert [(e.event_type, e.click_link) for e in events] == [
        ("email.clicked", "https://map.creatumundo.mx/pagos"),  # query dropped
        ("email.clicked", "https://www.creatumundo.mx/"),
    ]


async def test_click_dedupes_per_link(env):
    client, factory = env
    token = await _seed(factory)
    for _ in range(3):
        await client.get(f"/e/c/{token}/0", headers=_host())
    email_engagement.throttle.reset()
    await client.get(f"/e/c/{token}/0", headers=_host())
    assert await _count(factory) == 1


@pytest.mark.parametrize(
    "path",
    [
        "/e/c/{unknown}/0",
        "/e/c/{valid}/2",  # past the stored links
        "/e/c/{valid}/-1",
        "/e/c/{valid}/01",
        "/e/c/{valid}/1000",
        "/e/c/{valid}/abc",
        "/e/c/{valid}/0?url=https://evil.example/",
        "/e/c/{valid}/https:evil.example",
        "/e/c/short/0",
        "/e/c/{valid}x/0",
    ],
)
async def test_unresolvable_clicks_all_get_the_same_fallback_and_write_nothing(env, path):
    client, factory = env
    valid = await _seed(factory)
    unknown, _ = new_token()
    url = path.format(valid=valid, unknown=unknown)
    r = await client.get(url, headers=_host())
    if "?url=" in url:
        # A query string never chooses the target: index 0 of THIS token.
        assert r.headers["location"] == TARGETS[0]
        return
    assert r.status_code == 302
    assert r.headers["location"] == "https://creatumundo.mx"
    assert await _count(factory) == 0


async def test_fallback_is_decided_by_host_only(env):
    client, factory = env
    unknown, _ = new_token()
    ctm = await client.get(f"/e/c/{unknown}/0", headers=_host())
    other = await client.get(f"/e/c/{unknown}/0", headers=_host(OTHER_HOST))
    assert ctm.headers["location"] == "https://creatumundo.mx"
    assert other.headers["location"] == "https://madfam.io"


async def test_a_tampered_stored_target_is_never_followed(env):
    """Defence in depth: even a non-http(s) value in storage is not redirected to."""
    client, factory = env
    token, digest = new_token()
    async with factory() as session:
        session.add(
            EmailTrackingLink(
                token_hash=digest,
                cuenta="ctm",
                source_app="crea-map",
                email_id="e",
                links=json.dumps(["javascript:alert(1)"]),
                created_at=LONG_AGO,
            )
        )
        await session.commit()
    r = await client.get(f"/e/c/{token}/0", headers=_host())
    assert r.headers["location"] == "https://creatumundo.mx"
    assert await _count(factory) == 0


async def test_click_on_a_db_failure_is_the_fallback(env, monkeypatch):
    client, factory = env
    token = await _seed(factory)

    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.routers.v1.email_engagement.find_link", boom)
    r = await client.get(f"/e/c/{token}/0", headers=_host())
    assert r.status_code == 302 and r.headers["location"] == "https://creatumundo.mx"


async def test_head_is_answered_and_flagged(env):
    client, factory = env
    token = await _seed(factory)
    r = await client.head(f"/e/c/{token}/0", headers=_host())
    assert r.status_code == 302 and r.headers["location"] == TARGETS[0]
    [event] = await _events(factory)
    assert event.possible_prefetch is True


async def test_endpoints_are_not_in_the_openapi_schema():
    paths = app.openapi()["paths"]
    assert not [p for p in paths if p.startswith("/e/")]


# ---------------------------------------------------------------------------
# The per-app feed MAP reads
# ---------------------------------------------------------------------------


async def test_first_party_events_reach_the_feed_in_the_shape_map_reads(env):
    client, factory = env
    token = await _seed(factory)
    await client.get(f"/e/o/{token}.gif", headers=_host())
    await client.get(f"/e/c/{token}/0", headers=_host())
    # Past the 5 s settle window.
    async with factory() as session:
        for event in (await session.execute(select(EmailEvent))).scalars():
            event.received_at = LONG_AGO
        await session.commit()

    page = await client.get(
        "/api/v1/internal/email/events",
        params={"source_app": "crea-map"},
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert page.status_code == 200
    events = page.json()["events"]
    assert [e["type"] for e in events] == ["opened", "clicked"]
    for event in events:
        assert event["provider"] == "resend"  # MAP rejects any other provider
        assert event["email_id"] == "resend-email-1"
        assert event["source"] == "first_party"
        assert "possible_prefetch" not in event
        assert isinstance(event["cursor"], int)
    assert events[1]["click_link"] == "https://map.creatumundo.mx/pagos"

    other = await client.get(
        "/api/v1/internal/email/events",
        params={"source_app": "dhanam"},
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )
    assert other.json()["events"] == []


def test_token_hash_is_what_is_stored():
    token, digest = new_token()
    assert hash_token(token) == digest
