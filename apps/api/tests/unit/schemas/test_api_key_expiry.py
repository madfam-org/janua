"""API key expiries are stored as naive UTC, whatever offset the client sends.

``api_keys.expires_at`` is a naive ``DateTime`` column compared with
``datetime.utcnow()``. An aware datetime reached asyncpg unchanged and was
refused for that column, so ``POST /api/v1/api-keys`` with an ISO expiry that
carried an offset (``Z`` or ``+00:00``, what most clients send) answered 503
instead of creating the key.
"""

from datetime import datetime

import pytest

from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate


@pytest.mark.parametrize(
    ("sent", "stored"),
    [
        ("2027-01-05T00:45:00Z", datetime(2027, 1, 5, 0, 45)),
        ("2027-01-05T00:45:00+00:00", datetime(2027, 1, 5, 0, 45)),
        ("2027-01-05T06:45:00+06:00", datetime(2027, 1, 5, 0, 45)),
        ("2027-01-04T18:45:00-06:00", datetime(2027, 1, 5, 0, 45)),
        ("2027-01-05T00:45:00", datetime(2027, 1, 5, 0, 45)),
    ],
)
@pytest.mark.parametrize("schema", [ApiKeyCreate, ApiKeyUpdate])
def test_expiry_is_naive_utc(schema, sent, stored):
    data = schema(name="ci key", scopes=["npm:install"], expires_at=sent)

    assert data.expires_at == stored
    assert data.expires_at.tzinfo is None
    # The service compares it with datetime.utcnow(); an aware value would raise.
    assert isinstance(data.expires_at < datetime.utcnow(), bool)


@pytest.mark.parametrize("schema", [ApiKeyCreate, ApiKeyUpdate])
def test_no_expiry_stays_none(schema):
    assert schema(name="ci key").expires_at is None
