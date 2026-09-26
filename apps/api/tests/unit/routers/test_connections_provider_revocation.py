"""Revocation reaches Google: DELETE /connections/{id} and unlinking Google.

Google's revoke endpoint is mocked with respx (no real network). The local
revocation must always win; Google's outcome is audited, never blocking.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from consent_helpers import (
    activity,
    add_connection,
    add_user,
    as_user,
    get_connection,
    granted,
    mocked_google_revoke,
    revoked_token,
    sqlite_app,
)
from sqlalchemy import select

from app.dependencies import get_current_user
from app.models import OAuthAccount, OAuthProvider
from app.models.connected_account import ConnectedAccountStatus
from app.services.oauth import OAuthService

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def env():
    async with sqlite_app() as (client, factory):
        creator = await add_user(factory, "creator@example.com")
        from app.main import app

        app.dependency_overrides[get_current_user] = as_user(creator)
        google = await add_connection(
            factory,
            user_id=creator.id,
            purposes=granted(),
            access_token="access-placeholder",
            refresh_token="refresh-placeholder",
        )
        yield {"client": client, "factory": factory, "creator": creator, "google": google}


async def _revoke(env, connection_id):
    return await env["client"].delete(f"/api/v1/connections/{connection_id}")


async def _provider_logs(env):
    return await activity(env["factory"], "consent.provider.revoked")


# ---- DELETE /connections/{id} ------------------------------------------------------


async def test_revoke_sends_the_refresh_token_to_google_and_wipes_the_vault(env):
    with mocked_google_revoke() as (route, sleep):
        resp = await _revoke(env, env["google"].id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider_revocation"] == [
        {"provider": "google", "outcome": "revoked", "attempts": 1}
    ]
    assert route.call_count == 1
    assert revoked_token(route) == "refresh-placeholder"
    sleep.assert_not_awaited()

    row = await get_connection(env["factory"], env["google"].id)
    assert row.status == ConnectedAccountStatus.REVOKED.value
    assert row.access_token_encrypted is None
    assert row.refresh_token_encrypted is None
    assert row.account_metadata["provider_revocation"]["status"] == "revoked"

    (log,) = await _provider_logs(env)
    assert log.resource_id == str(env["google"].id)
    assert log.activity_metadata["outcome"] == "revoked"
    assert log.activity_metadata["token_kind"] == "refresh"
    assert "refresh-placeholder" not in str(log.activity_metadata)  # no token in the trail


async def test_access_token_is_used_when_there_is_no_refresh_token(env):
    conn = await add_connection(
        env["factory"], user_id=env["creator"].id, refresh_token=None, access_token="only-access"
    )
    with mocked_google_revoke() as (route, _):
        resp = await _revoke(env, conn.id)
    assert resp.status_code == 200
    assert revoked_token(route) == "only-access"
    (log,) = await _provider_logs(env)
    assert log.activity_metadata["token_kind"] == "access"


async def test_transient_google_failures_are_retried_with_backoff(env):
    responses = (httpx.Response(503), httpx.ConnectError("reset"), httpx.Response(200))
    with mocked_google_revoke(*responses) as (route, sleep):
        resp = await _revoke(env, env["google"].id)
    assert resp.status_code == 200
    assert route.call_count == 3
    assert [c.args[0] for c in sleep.await_args_list] == [0.5, 1.5]
    (log,) = await _provider_logs(env)
    assert log.activity_metadata["outcome"] == "revoked"
    assert log.activity_metadata["attempts"] == 3


async def test_google_down_never_blocks_the_local_revocation(env):
    with mocked_google_revoke(*(httpx.Response(503),) * 3) as (route, _):
        resp = await _revoke(env, env["google"].id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] is True
    assert resp.json()["provider_revocation"][0]["outcome"] == "failed"
    assert route.call_count == 3

    row = await get_connection(env["factory"], env["google"].id)
    assert row.status == ConnectedAccountStatus.REVOKED.value
    assert row.account_metadata["purposes"]["creator-census.youtube"]["status"] == "revoked"
    # Kept (on a never-delegable row) so an operator can retry the revocation.
    assert row.refresh_token_encrypted == "refresh-placeholder"
    failure = row.account_metadata["provider_revocation"]
    assert failure["status"] == "failed"
    assert failure["error"] == "provider_status_503"
    (log,) = await _provider_logs(env)
    assert log.activity_metadata["outcome"] == "failed"
    assert len(await activity(env["factory"], "connection.revoked")) == 1


async def test_already_invalid_token_counts_as_done_without_retry(env):
    with mocked_google_revoke(httpx.Response(400, json={"error": "invalid_token"})) as (route, _):
        resp = await _revoke(env, env["google"].id)
    assert resp.status_code == 200
    assert route.call_count == 1
    row = await get_connection(env["factory"], env["google"].id)
    assert row.refresh_token_encrypted is None
    (log,) = await _provider_logs(env)
    assert log.activity_metadata["outcome"] == "already_invalid"


async def test_other_google_4xx_fails_without_retry(env):
    with mocked_google_revoke(httpx.Response(400, json={"error": "invalid_request"})) as (
        route,
        _,
    ):
        resp = await _revoke(env, env["google"].id)
    assert resp.status_code == 200
    assert route.call_count == 1
    (log,) = await _provider_logs(env)
    assert log.activity_metadata["outcome"] == "failed"
    assert log.activity_metadata["error"] == "invalid_request"


async def test_unexpected_error_in_provider_step_still_returns_revoked(env):
    boom = AsyncMock(side_effect=RuntimeError("unexpected"))
    with patch.object(OAuthService, "revoke_provider_token", boom):
        resp = await _revoke(env, env["google"].id)
    assert resp.status_code == 200
    row = await get_connection(env["factory"], env["google"].id)
    assert row.status == ConnectedAccountStatus.REVOKED.value


async def test_expired_connection_can_be_revoked_too(env):
    expired = await add_connection(
        env["factory"],
        user_id=env["creator"].id,
        purposes=granted(),
        status=ConnectedAccountStatus.EXPIRED.value,
    )
    with mocked_google_revoke() as (route, _):
        resp = await _revoke(env, expired.id)
    assert resp.status_code == 200
    assert route.call_count == 1


async def test_github_connection_is_not_sent_to_google(env):
    github = await add_connection(
        env["factory"], user_id=env["creator"].id, provider_type="github", refresh_token=None
    )
    with mocked_google_revoke() as (route, _):
        resp = await _revoke(env, github.id)
    assert resp.status_code == 200
    assert route.call_count == 0
    assert resp.json()["provider_revocation"] == []
    assert await _provider_logs(env) == []


# ---- unlink Google ------------------------------------------------------------------


async def _add_google_link(env, refresh_token="refresh-placeholder"):
    async with env["factory"]() as db:
        link = OAuthAccount(
            id=uuid.uuid4(),
            user_id=env["creator"].id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-sub-fixture",
            access_token="link-access",
            refresh_token=refresh_token,
            provider_data={},
        )
        db.add(link)
        await db.commit()
        return link


async def test_unlink_revokes_link_and_connection_once_per_distinct_token(env):
    await _add_google_link(env, refresh_token="link-refresh")
    with mocked_google_revoke() as (route, _):
        resp = await env["client"].delete("/api/v1/auth/oauth/unlink/google")
    assert resp.status_code == 200, resp.text
    assert route.call_count == 2
    assert {revoked_token(route, 0), revoked_token(route, 1)} == {
        "refresh-placeholder",
        "link-refresh",
    }
    logs = await _provider_logs(env)
    assert sorted(log.resource_type for log in logs) == ["connected_account", "oauth_account"]
    assert {log.activity_metadata["outcome"] for log in logs} == {"revoked"}


async def test_unlink_succeeds_even_when_google_is_down(env):
    await _add_google_link(env)
    with mocked_google_revoke(httpx.ConnectError("down"), *(httpx.Response(502),) * 2):
        resp = await env["client"].delete("/api/v1/auth/oauth/unlink/google")
    assert resp.status_code == 200, resp.text
    async with env["factory"]() as db:
        assert (await db.execute(select(OAuthAccount))).scalars().all() == []
    row = await get_connection(env["factory"], env["google"].id)
    assert row.status == ConnectedAccountStatus.REVOKED.value
    logs = await _provider_logs(env)
    assert logs and {log.activity_metadata["outcome"] for log in logs} == {"failed"}
