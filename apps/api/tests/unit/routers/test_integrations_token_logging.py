"""GET /integrations/{provider}/token — logging must not break the response.

The router logs through a stdlib `logging.getLogger(__name__)` logger. It used
to pass structlog-style keyword fields (`user_id=…`, `provider=…`), which stdlib
`Logger._log()` rejects with TypeError. The success log runs after the audit
row is committed, so every successful token read raised; the `except Exception`
handler then logged with keyword fields too, raised again, and the caller got a
bare 500. These tests run the real logger (no patching) at INFO.
"""

from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers.v1.integrations import get_integration_token

pytestmark = pytest.mark.asyncio

LOGGER_NAME = "app.routers.v1.integrations"


def _db_with_account(account):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = account
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _linked_account():
    return SimpleNamespace(
        access_token="synthetic-access-token",
        refresh_token=None,
        token_expires_at=None,
        provider_user_id="synthetic-provider-user",
        provider_email="user@example.test",
        created_at=datetime(2026, 1, 1),
    )


async def test_token_read_returns_the_token_and_logs_fields_in_extra(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    user = SimpleNamespace(id=uuid4())
    db = _db_with_account(_linked_account())

    response = await get_integration_token("github", db=db, current_user=user)

    assert response.access_token == "synthetic-access-token"
    db.commit.assert_awaited_once()
    records = [r for r in caplog.records if r.getMessage() == "Integration token accessed"]
    assert len(records) == 1
    assert records[0].user_id == str(user.id)
    assert records[0].provider == "github"


async def test_unexpected_error_is_logged_and_becomes_the_documented_500(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("synthetic database failure"))

    with pytest.raises(HTTPException) as exc_info:
        await get_integration_token("github", db=db, current_user=SimpleNamespace(id=uuid4()))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to retrieve integration token"
    records = [r for r in caplog.records if r.getMessage() == "Error retrieving integration token"]
    assert len(records) == 1
    assert records[0].error == "synthetic database failure"
