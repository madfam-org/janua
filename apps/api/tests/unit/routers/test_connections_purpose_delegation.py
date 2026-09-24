"""Purpose-scoped delegation on POST /api/v1/connections/{id}/token.

Every rule the service-token path enforces, plus proof that the legacy
static-token (Coupler) path still works and cannot reach purpose-scoped
credentials.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from consent_helpers import (
    GOOGLE_BASE_SCOPES,
    YT_PURPOSE,
    YT_SCOPES,
    activity,
    add_connection,
    add_service_client,
    add_user,
    as_user,
    get_connection,
    granted,
    mint_service_token,
    reason,
    sqlite_app,
    use_rs256,
)

from app.config import settings
from app.dependencies import get_current_user
from app.models.connected_account import ConnectedAccountStatus
from app.services.oauth import OAuthService, ProviderRefreshRejected, ProviderRefreshUnavailable

pytestmark = pytest.mark.asyncio

STATIC = "legacy-static-service-token-placeholder"
CENSUS_ID = "jnc_census_fixture"
OTHER_ID = "jnc_other_fixture"


@pytest_asyncio.fixture
async def env(monkeypatch):
    use_rs256(monkeypatch)
    monkeypatch.setattr(settings, "JANUA_SERVICE_TOKEN", STATIC)
    async with sqlite_app() as (client, factory):
        creator = await add_user(factory, "creator@example.com")
        stranger = await add_user(factory, "stranger@example.com")
        await add_service_client(
            factory, name="creator-census", client_id=CENSUS_ID, created_by=creator.id
        )
        await add_service_client(
            factory, name="other-service", client_id=OTHER_ID, created_by=creator.id
        )
        google = await add_connection(factory, user_id=creator.id, purposes=granted())
        yield {
            "client": client,
            "factory": factory,
            "creator": creator,
            "stranger": stranger,
            "google": google,
        }


async def _delegate(env, connection_id, token, *, purpose=YT_PURPOSE, acting=None, headers=None):
    hdrs = {"X-Acting-User-Id": str(acting or env["creator"].id)}
    if token is not None:
        hdrs["Authorization"] = f"Bearer {token}"
    hdrs.update(headers or {})
    return await env["client"].post(
        f"/api/v1/connections/{connection_id}/token",
        json={"purpose": purpose, "ttl_seconds": 300},
        headers=hdrs,
    )


# ---- allowed path ------------------------------------------------------------


async def test_allowed_client_with_granted_purpose_gets_token_and_audit(env):
    resp = await _delegate(env, env["google"].id, mint_service_token(CENSUS_ID))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] == "provider-access-placeholder"
    assert body["purpose"] == YT_PURPOSE
    assert body["provider_type"] == "google"
    assert set(YT_SCOPES) <= set(body["scopes"])

    logs = await activity(env["factory"], "tool.delegation.issued")
    assert len(logs) == 1
    meta = logs[0].activity_metadata
    assert meta["purpose"] == YT_PURPOSE
    assert meta["service_client"] == "creator-census"
    assert meta["caller"] == "service_client"


# ---- caller rules --------------------------------------------------------------


async def test_disallowed_client_is_refused(env):
    resp = await _delegate(env, env["google"].id, mint_service_token(OTHER_ID))
    assert resp.status_code == 403
    assert reason(resp) == "service_client_not_allowed_for_purpose"
    assert await activity(env["factory"], "tool.delegation.issued") == []


async def test_unknown_purpose_is_refused(env):
    resp = await _delegate(
        env, env["google"].id, mint_service_token(CENSUS_ID), purpose="made-up.purpose"
    )
    assert resp.status_code == 403
    assert reason(resp) == "unknown_purpose"


async def test_token_without_delegate_scope_is_refused(env):
    token = mint_service_token(CENSUS_ID, scope="openid")
    resp = await _delegate(env, env["google"].id, token)
    assert resp.status_code == 403
    assert reason(resp) == "service_token_missing_scope"


async def test_token_for_another_audience_is_refused(env):
    token = mint_service_token(CENSUS_ID, audience="karafiel-api")
    resp = await _delegate(env, env["google"].id, token)
    assert resp.status_code == 401
    assert reason(resp) == "invalid_service_token"


async def test_deactivated_client_is_refused_even_with_live_token(env):
    token = mint_service_token(CENSUS_ID)
    from sqlalchemy import update

    from app.models import OAuthClient

    async with env["factory"]() as db:
        await db.execute(
            update(OAuthClient).where(OAuthClient.client_id == CENSUS_ID).values(is_active=False)
        )
        await db.commit()
    resp = await _delegate(env, env["google"].id, token)
    assert resp.status_code == 403
    assert reason(resp) == "service_client_grant_unavailable"


async def test_symmetric_jwt_manager_is_refused(env, monkeypatch):
    token = mint_service_token(CENSUS_ID)
    from app.core.jwt_manager import jwt_manager

    monkeypatch.setattr(jwt_manager, "algorithm", "HS256")
    resp = await _delegate(env, env["google"].id, token)
    assert resp.status_code == 401
    assert reason(resp) == "service_token_requires_rs256"


# ---- consent rules --------------------------------------------------------------


async def test_purpose_not_granted_on_connection_is_refused(env):
    bare = await add_connection(
        env["factory"], user_id=env["stranger"].id, scopes=GOOGLE_BASE_SCOPES
    )
    resp = await _delegate(env, bare.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id)
    assert resp.status_code == 403
    assert reason(resp) == "purpose_not_granted"


async def test_grant_recorded_but_scopes_missing_is_refused(env):
    narrowed = await add_connection(
        env["factory"],
        user_id=env["stranger"].id,
        scopes=GOOGLE_BASE_SCOPES + YT_SCOPES[:1],
        purposes=granted(),
    )
    resp = await _delegate(
        env, narrowed.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
    )
    assert resp.status_code == 403
    assert reason(resp) == "purpose_not_granted"


async def test_connection_must_belong_to_acting_user(env):
    resp = await _delegate(
        env, env["google"].id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
    )
    assert resp.status_code == 403
    assert reason(resp) == "acting_user_mismatch"


async def test_purpose_for_another_provider_is_refused(env):
    github = await add_connection(
        env["factory"], user_id=env["creator"].id, provider_type="github", purposes=granted()
    )
    resp = await _delegate(env, github.id, mint_service_token(CENSUS_ID))
    assert resp.status_code == 403
    assert reason(resp) == "purpose_provider_mismatch"


async def test_unknown_connection_is_404(env):
    resp = await _delegate(env, uuid.uuid4(), mint_service_token(CENSUS_ID))
    assert resp.status_code == 404


# ---- refresh -----------------------------------------------------------------------


async def test_expired_google_token_is_refreshed_before_delegation(env):
    stale = await add_connection(
        env["factory"],
        user_id=env["stranger"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=30),
        access_token="stale-access-placeholder",
    )
    fresh = {
        "access_token": "fresh-access-placeholder",
        "expires_in": 3599,
        "scope": " ".join(GOOGLE_BASE_SCOPES + YT_SCOPES),
        "token_type": "Bearer",
    }
    with patch.object(
        OAuthService, "refresh_access_token", AsyncMock(return_value=fresh)
    ) as refresh:
        resp = await _delegate(
            env, stale.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"] == "fresh-access-placeholder"
    refresh.assert_awaited_once()
    row = await get_connection(env["factory"], stale.id)
    assert row.access_token_encrypted == "fresh-access-placeholder"
    assert row.oauth_expires_at > datetime.utcnow() + timedelta(minutes=50)


async def test_refresh_rejected_marks_expired_and_requires_reauthorization(env):
    stale = await add_connection(
        env["factory"],
        user_id=env["stranger"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=-60),
    )
    rejected = AsyncMock(side_effect=ProviderRefreshRejected("invalid_grant"))
    with patch.object(OAuthService, "refresh_access_token", rejected):
        resp = await _delegate(
            env, stale.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
        )
        assert resp.status_code == 409
        assert reason(resp) == "reauthorization_required"
        row = await get_connection(env["factory"], stale.id)
        assert row.status == ConnectedAccountStatus.EXPIRED.value

        # Stays refused; the provider is not asked again.
        again = await _delegate(
            env, stale.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
        )
        assert again.status_code == 409
        assert rejected.await_count == 1
    assert await activity(env["factory"], "tool.delegation.issued") == []


async def test_refresh_that_drops_purpose_scopes_requires_reauthorization(env):
    stale = await add_connection(
        env["factory"],
        user_id=env["stranger"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=-60),
    )
    narrowed = {"access_token": "fresh", "expires_in": 3599, "scope": "openid"}
    with patch.object(OAuthService, "refresh_access_token", AsyncMock(return_value=narrowed)):
        resp = await _delegate(
            env, stale.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
        )
    assert resp.status_code == 409
    assert reason(resp) == "reauthorization_required"


async def test_missing_refresh_token_requires_reauthorization(env):
    stale = await add_connection(
        env["factory"],
        user_id=env["stranger"].id,
        purposes=granted(),
        expires_in=None,
        refresh_token=None,
    )
    resp = await _delegate(env, stale.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id)
    assert resp.status_code == 409
    row = await get_connection(env["factory"], stale.id)
    assert row.status == ConnectedAccountStatus.EXPIRED.value


async def test_provider_outage_is_503_and_does_not_expire_the_consent(env):
    stale = await add_connection(
        env["factory"],
        user_id=env["stranger"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=-60),
    )
    outage = AsyncMock(side_effect=ProviderRefreshUnavailable("provider_status_503"))
    with patch.object(OAuthService, "refresh_access_token", outage):
        resp = await _delegate(
            env, stale.id, mint_service_token(CENSUS_ID), acting=env["stranger"].id
        )
    assert resp.status_code == 503
    assert reason(resp) == "provider_refresh_unavailable"
    row = await get_connection(env["factory"], stale.id)
    assert row.status == ConnectedAccountStatus.ACTIVE.value


# ---- revocation ------------------------------------------------------------------


async def test_revoking_connection_ends_purposes_and_blocks_delegation(env):
    from app.main import app

    app.dependency_overrides[get_current_user] = as_user(env["creator"])
    try:
        resp = await env["client"].delete(f"/api/v1/connections/{env['google'].id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200, resp.text
    assert resp.json()["purposes_ended"] == [YT_PURPOSE]

    row = await get_connection(env["factory"], env["google"].id)
    assert row.status == ConnectedAccountStatus.REVOKED.value
    assert row.account_metadata["purposes"][YT_PURPOSE]["status"] == "revoked"
    ended = await activity(env["factory"], "consent.purpose.revoked")
    assert [a.activity_metadata["purpose"] for a in ended] == [YT_PURPOSE]

    blocked = await _delegate(env, env["google"].id, mint_service_token(CENSUS_ID))
    assert blocked.status_code == 403
    assert reason(blocked) == "connection_revoked"


# ---- legacy static token (Coupler) -----------------------------------------------


async def test_legacy_static_token_still_delegates_github(env):
    github = await add_connection(
        env["factory"],
        user_id=env["creator"].id,
        provider_type="github",
        scopes=["repo"],
        expires_in=None,
        refresh_token=None,
        access_token="github-access-placeholder",
    )
    via_header = await _delegate(
        env, github.id, None, purpose="tool_execute", headers={"X-Service-Token": STATIC}
    )
    assert via_header.status_code == 200, via_header.text
    assert via_header.json()["access_token"] == "github-access-placeholder"
    assert via_header.json()["purpose"] == "tool_execute"

    via_bearer = await _delegate(env, github.id, STATIC, purpose="tool_execute")
    assert via_bearer.status_code == 200

    logs = await activity(env["factory"], "tool.delegation.issued")
    assert {log.activity_metadata["caller"] for log in logs} == {"static_service_token"}


async def test_legacy_static_token_cannot_reach_google(env):
    resp = await _delegate(
        env, env["google"].id, None, purpose="tool_execute", headers={"X-Service-Token": STATIC}
    )
    assert resp.status_code == 403
    assert reason(resp) == "provider_requires_service_token"


async def test_legacy_static_token_cannot_request_a_registered_purpose(env):
    resp = await _delegate(env, env["google"].id, None, headers={"X-Service-Token": STATIC})
    assert resp.status_code == 403
    assert reason(resp) == "purpose_requires_service_token"


async def test_wrong_static_token_is_401(env):
    resp = await _delegate(
        env, env["google"].id, None, purpose="tool_execute", headers={"X-Service-Token": "nope"}
    )
    assert resp.status_code == 401
    assert reason(resp) == "invalid_service_credentials"


async def test_service_token_path_works_without_static_token_configured(env, monkeypatch):
    monkeypatch.setattr(settings, "JANUA_SERVICE_TOKEN", "")
    resp = await _delegate(env, env["google"].id, mint_service_token(CENSUS_ID))
    assert resp.status_code == 200, resp.text
    # ...while the legacy "disabled" shape is unchanged for credential-less calls.
    missing = await _delegate(env, env["google"].id, None, purpose="tool_execute")
    assert missing.status_code == 404
