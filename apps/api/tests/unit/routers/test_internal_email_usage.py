"""GET /api/v1/internal/email/usage: per-account quota usage crea-map reads.

Rows are inserted directly so the tests control the account, the event type
and the instant exactly. The window is Resend's: the UTC calendar day, and the
UTC calendar month.
"""

from __future__ import annotations

from datetime import datetime

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
from app.services.email_branding import CTM_ORG_ID
from app.services.email_usage import account_for_org, quota_error_code, usage_for_account

URL = "/api/v1/internal/email/usage"
INTERNAL_KEY = "test-internal-api-key-email-usage"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}
WEBHOOK_SECRET = "whsec_dGVzdC1zZWNyZXQtZm9yLXVzYWdl"


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
    previous_key = settings.INTERNAL_API_KEY
    previous_secret = getattr(settings, "RESEND_WEBHOOK_SECRET_CTM", None)
    settings.INTERNAL_API_KEY = INTERNAL_KEY
    settings.RESEND_WEBHOOK_SECRET_CTM = WEBHOOK_SECRET
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    settings.INTERNAL_API_KEY = previous_key
    settings.RESEND_WEBHOOK_SECRET_CTM = previous_secret
    await engine.dispose()


_counter = {"n": 0}


def _event(occurred_at, event_type="email.sent", cuenta="ctm", source_app="crea-map"):
    _counter["n"] += 1
    n = _counter["n"]
    return EmailEvent(
        provider="resend",
        cuenta=cuenta,
        svix_id=f"msg_usage_{n}",
        email_id=f"email-usage-{n}",
        event_type=event_type,
        occurred_at=occurred_at,
        source_app=source_app,
        org_id=None,
        received_at=occurred_at,
    )


async def _seed(factory, *events):
    async with factory() as session:
        session.add_all(events)
        await session.commit()


# --------------------------------------------------------------------------
# Auth and scope
# --------------------------------------------------------------------------


async def test_missing_key_is_rejected(env):
    client, _ = env
    assert (await client.get(URL, params={"org_id": CTM_ORG_ID})).status_code == 422


async def test_wrong_key_is_401(env):
    client, _ = env
    response = await client.get(
        URL, params={"org_id": CTM_ORG_ID}, headers={"X-Internal-API-Key": "wrong"}
    )
    assert response.status_code == 401


async def test_unknown_org_is_404(env):
    client, _ = env
    response = await client.get(
        URL, params={"org_id": "00000000-0000-0000-0000-000000000000"}, headers=AUTH
    )
    assert response.status_code == 404


async def test_account_without_webhook_is_404(env):
    client, _ = env
    settings.RESEND_WEBHOOK_SECRET_CTM = None
    response = await client.get(URL, params={"org_id": CTM_ORG_ID}, headers=AUTH)
    assert response.status_code == 404


def test_ctm_org_resolves_to_its_own_account():
    assert account_for_org(CTM_ORG_ID) == "ctm"
    assert account_for_org(CTM_ORG_ID.upper()) == "ctm"
    assert account_for_org(None) is None
    assert account_for_org("not-an-org") is None


# --------------------------------------------------------------------------
# Contract and counting
# --------------------------------------------------------------------------


async def test_contract_shape(env):
    client, factory = env
    await _seed(factory, _event(datetime.utcnow()))
    response = await client.get(URL, params={"org_id": CTM_ORG_ID, "days": 3}, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"cuenta", "window", "as_of", "today", "month", "days"}
    assert body["cuenta"] == "ctm"
    assert body["window"] == "utc_day"
    assert body["as_of"].endswith("Z")
    assert body["today"] == 1
    assert len(body["days"]) == 3
    assert body["days"][-1]["sent"] == 1
    assert set(body["days"][0]) == {"date", "sent"}


async def test_counts_only_sent_on_the_account_in_the_utc_windows(env):
    _, factory = env
    now = datetime(2026, 9, 28, 23, 40)  # 17:40 in CDMX
    await _seed(
        factory,
        # Today (UTC): three sends, from any app on the account.
        _event(datetime(2026, 9, 28, 0, 0)),
        _event(datetime(2026, 9, 28, 12, 0), source_app="crea-erp"),
        _event(datetime(2026, 9, 28, 23, 39), source_app=None),
        # Not sends, or not this account: never counted.
        _event(datetime(2026, 9, 28, 10, 0), event_type="email.delivered"),
        _event(datetime(2026, 9, 28, 10, 0), event_type="email.opened"),
        _event(datetime(2026, 9, 28, 10, 0), cuenta="platform"),
        # Yesterday, just before UTC midnight: this month, not today.
        _event(datetime(2026, 9, 27, 23, 59, 59)),
        # Earlier this month.
        _event(datetime(2026, 9, 1, 0, 0)),
        # Last month: inside the 14-day series? No (Sept 15 is the first day).
        _event(datetime(2026, 8, 31, 23, 59)),
    )
    async with factory() as session:
        usage = await usage_for_account(session, "ctm", days=14, now=now)
    assert usage.today == 3
    assert usage.month == 5
    assert [d["date"] for d in usage.days][0] == "2026-09-15"
    assert usage.days[-1] == {"date": "2026-09-28", "sent": 3}
    assert usage.days[-2] == {"date": "2026-09-27", "sent": 1}
    assert sum(d["sent"] for d in usage.days) == 4


async def test_series_crosses_the_month_boundary(env):
    _, factory = env
    now = datetime(2026, 10, 2, 1, 0)
    await _seed(
        factory,
        _event(datetime(2026, 9, 30, 20, 0)),
        _event(datetime(2026, 10, 1, 0, 0)),
        _event(datetime(2026, 10, 2, 0, 30)),
    )
    async with factory() as session:
        usage = await usage_for_account(session, "ctm", days=5, now=now)
    assert usage.today == 1
    assert usage.month == 2  # October only
    assert [d["sent"] for d in usage.days] == [0, 0, 1, 1, 1]


async def test_days_is_bounded(env):
    client, _ = env
    response = await client.get(URL, params={"org_id": CTM_ORG_ID, "days": 32}, headers=AUTH)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Quota refusals keep their provider code
# --------------------------------------------------------------------------


class _ProviderError(Exception):
    def __init__(self, error_type):
        super().__init__("provider refused")
        self.error_type = error_type


@pytest.mark.parametrize(
    "error_type,expected",
    [
        ("daily_quota_exceeded", "daily_quota_exceeded"),
        ("monthly_quota_exceeded", "monthly_quota_exceeded"),
        ("rate_limit_exceeded", None),
        ("validation_error", None),
        (None, None),
    ],
)
def test_quota_error_code(error_type, expected):
    assert quota_error_code(_ProviderError(error_type)) == expected
    assert quota_error_code(ValueError("plain")) is None
