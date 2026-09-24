"""Purpose-aware provider linking: POST /auth/oauth/link/{provider}?purpose=...

Covers link-time validation, the scope-upgrade re-link, grant recording on
callback (and refusing a partial grant), the unchanged no-purpose behaviour,
and unlink ending purposes.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from consent_helpers import (
    GOOGLE_BASE_SCOPES,
    YT_PURPOSE,
    YT_SCOPES,
    activity,
    add_user,
    as_user,
    reason,
    sqlite_app,
)
from sqlalchemy import select

from app.config import settings
from app.dependencies import get_current_user
from app.models import OAuthAccount, OAuthProvider
from app.models.connected_account import ConnectedAccount, ConnectedAccountStatus
from app.services.oauth import OAuthService

pytestmark = pytest.mark.asyncio

GOOGLE_SUB = "google-sub-fixture"


@pytest_asyncio.fixture
async def env(monkeypatch):
    monkeypatch.setattr(settings, "OAUTH_GOOGLE_CLIENT_ID", "google-client-placeholder")
    monkeypatch.setattr(settings, "OAUTH_GOOGLE_CLIENT_SECRET", "google-secret-placeholder")
    monkeypatch.setattr(settings, "OAUTH_GITHUB_CLIENT_ID", "github-client-placeholder")
    monkeypatch.setattr(settings, "OAUTH_GITHUB_CLIENT_SECRET", "github-secret-placeholder")
    async with sqlite_app() as (client, factory):
        creator = await add_user(factory, "creator@example.com")
        from app.main import app

        app.dependency_overrides[get_current_user] = as_user(creator)
        yield {"client": client, "factory": factory, "creator": creator}


async def _link_google(env, factory_account: bool = False, sub: str = GOOGLE_SUB):
    if factory_account:
        async with env["factory"]() as db:
            db.add(
                OAuthAccount(
                    id=uuid.uuid4(),
                    user_id=env["creator"].id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=sub,
                    provider_email="creator@example.com",
                    access_token="old-access-placeholder",
                    refresh_token="old-refresh-placeholder",
                    provider_data={"scopes": GOOGLE_BASE_SCOPES},
                )
            )
            await db.commit()


def _tokens(scopes):
    return {
        "access_token": "new-access-placeholder",
        "refresh_token": "new-refresh-placeholder",
        "expires_in": 3599,
        "scope": " ".join(scopes),
        "token_type": "Bearer",
    }


def _user_info(sub: str = GOOGLE_SUB):
    return {
        "provider": "google",
        "provider_user_id": sub,
        "email": "creator@example.com",
        "email_verified": True,
        "raw_data": {"id": sub},
    }


async def _callback(env, state, *, scopes, sub=GOOGLE_SUB):
    with (
        patch.object(
            OAuthService, "exchange_code_for_tokens", AsyncMock(return_value=_tokens(scopes))
        ),
        patch.object(OAuthService, "get_user_info", AsyncMock(return_value=_user_info(sub))),
    ):
        return await env["client"].get(
            "/api/v1/auth/oauth/link/callback/google",
            params={"code": "code-placeholder", "state": state},
        )


async def _connections(env):
    async with env["factory"]() as db:
        result = await db.execute(select(ConnectedAccount))
        return list(result.scalars().all())


# ---- link-time validation -------------------------------------------------------


async def test_unknown_purpose_is_refused(env):
    resp = await env["client"].post("/api/v1/auth/oauth/link/google?purpose=made-up.purpose")
    assert resp.status_code == 400
    assert reason(resp) == "unknown_purpose"


async def test_purpose_for_another_provider_is_refused(env):
    resp = await env["client"].post(f"/api/v1/auth/oauth/link/github?purpose={YT_PURPOSE}")
    assert resp.status_code == 400
    assert reason(resp) == "purpose_provider_mismatch"


async def test_without_purpose_an_existing_link_is_still_refused(env):
    await _link_google(env, factory_account=True)
    resp = await env["client"].post("/api/v1/auth/oauth/link/google")
    assert resp.status_code == 400


async def test_purpose_link_requests_scopes_incrementally(env):
    resp = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["purpose"] == YT_PURPOSE
    assert body["scope_upgrade"] is False
    query = parse_qs(urlparse(body["authorization_url"]).query)
    requested = query["scope"][0].split()
    assert set(YT_SCOPES) <= set(requested)
    assert query["include_granted_scopes"] == ["true"]
    assert query["access_type"] == ["offline"]


async def test_purpose_link_on_already_linked_provider_is_a_scope_upgrade(env):
    await _link_google(env, factory_account=True)
    resp = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["scope_upgrade"] is True


# ---- callback ----------------------------------------------------------------------


async def test_scope_upgrade_callback_records_grant_and_refreshes_link(env):
    await _link_google(env, factory_account=True)
    start = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    resp = await _callback(env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES + YT_SCOPES)
    assert resp.status_code == 200, resp.text

    async with env["factory"]() as db:
        links = (await db.execute(select(OAuthAccount))).scalars().all()
    assert len(links) == 1  # upgraded in place, not duplicated
    assert links[0].access_token == "new-access-placeholder"
    assert links[0].refresh_token == "new-refresh-placeholder"
    assert links[0].token_expires_at is not None

    (conn,) = await _connections(env)
    assert conn.provider_type == "google"
    assert conn.status == ConnectedAccountStatus.ACTIVE.value
    assert set(YT_SCOPES) <= set(conn.oauth_scopes)
    grant = conn.account_metadata["purposes"][YT_PURPOSE]
    assert grant["status"] == "granted"
    assert grant["scopes"] == YT_SCOPES
    assert conn.refresh_token_encrypted == "new-refresh-placeholder"

    (log,) = await activity(env["factory"], "consent.purpose.granted")
    assert log.activity_metadata["purpose"] == YT_PURPOSE
    assert log.activity_metadata["scope_upgrade"] is True
    assert log.resource_id == str(conn.id)


async def test_first_link_with_purpose_creates_link_and_grant(env):
    start = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    resp = await _callback(env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES + YT_SCOPES)
    assert resp.status_code == 200, resp.text
    async with env["factory"]() as db:
        (link,) = (await db.execute(select(OAuthAccount))).scalars().all()
    assert link.provider_user_id == GOOGLE_SUB
    (conn,) = await _connections(env)
    assert conn.account_metadata["purposes"][YT_PURPOSE]["status"] == "granted"
    assert len(await activity(env["factory"], "oauth_linked")) == 1


async def test_partial_grant_is_not_recorded(env):
    await _link_google(env, factory_account=True)
    start = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    resp = await _callback(env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES + YT_SCOPES[:1])
    assert resp.status_code == 400
    assert reason(resp) == "purpose_scopes_not_granted"
    assert await _connections(env) == []
    assert await activity(env["factory"], "consent.purpose.granted") == []


async def test_partial_grant_redirects_with_error_when_redirect_given(env):
    start = await env["client"].post(
        f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}&redirect_uri=/settings/connections"
    )
    resp = await _callback(env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/settings/connections?error=purpose_scopes_not_granted"


async def test_upgrade_with_a_different_provider_account_is_refused(env):
    await _link_google(env, factory_account=True)
    start = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    resp = await _callback(
        env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES + YT_SCOPES, sub="someone-else"
    )
    assert resp.status_code == 400
    assert reason(resp) == "provider_account_mismatch"
    assert await _connections(env) == []


async def test_plain_link_callback_succeeds_and_stores_real_provider_id(env):
    """Regression: the no-purpose path used to 400 after commit and store "None"."""
    start = await env["client"].post("/api/v1/auth/oauth/link/google")
    assert start.status_code == 200
    assert "include_granted_scopes" not in start.json()["authorization_url"]
    resp = await _callback(env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"
    async with env["factory"]() as db:
        (link,) = (await db.execute(select(OAuthAccount))).scalars().all()
    assert link.provider_user_id == GOOGLE_SUB
    assert await _connections(env) == []  # no purpose, no grant recorded


# ---- unlink ----------------------------------------------------------------------


async def test_unlink_revokes_connection_and_ends_purposes(env):
    await _link_google(env, factory_account=True)
    start = await env["client"].post(f"/api/v1/auth/oauth/link/google?purpose={YT_PURPOSE}")
    await _callback(env, start.json()["state"], scopes=GOOGLE_BASE_SCOPES + YT_SCOPES)

    resp = await env["client"].delete("/api/v1/auth/oauth/unlink/google")
    assert resp.status_code == 200, resp.text
    (conn,) = await _connections(env)
    assert conn.status == ConnectedAccountStatus.REVOKED.value
    assert conn.account_metadata["purposes"][YT_PURPOSE]["status"] == "revoked"
    (log,) = await activity(env["factory"], "consent.purpose.revoked")
    assert log.activity_metadata == {"purpose": YT_PURPOSE, "reason": "provider_unlinked"}
