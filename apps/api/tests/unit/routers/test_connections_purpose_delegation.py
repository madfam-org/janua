"""Purpose-scoped delegation: the user-bound exchange and the offline path.

- `POST /connections/token-exchange`: `exchange_clients` only, subject = the
  user's own access token.
- `POST /connections/{id}/token` with a service token + `X-Acting-User-Id`:
  `offline_clients` only (user absent, background re-verification).
- The legacy static-token (Coupler) path still works for GitHub/Slack.
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
    get_connection,
    granted,
    mint_service_token,
    mint_user_token,
    reason,
    sqlite_app,
    use_rs256,
)

from app.config import settings
from app.models import UserStatus
from app.models.connected_account import ConnectedAccountStatus
from app.services.oauth import OAuthService, ProviderRefreshRejected, ProviderRefreshUnavailable

pytestmark = pytest.mark.asyncio

STATIC = "legacy-static-service-token-placeholder"
CENSUS_ID = "jnc_census_fixture"
OTHER_ID = "jnc_other_fixture"
REAUTH_ID = "jnc_reauth_fixture"
EXCHANGE = "/api/v1/connections/token-exchange"
GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
AT = "urn:ietf:params:oauth:token-type:access_token"


@pytest_asyncio.fixture
async def env(monkeypatch):
    use_rs256(monkeypatch)
    monkeypatch.setattr(settings, "JANUA_SERVICE_TOKEN", STATIC)
    async with sqlite_app() as (client, factory):
        creator = await add_user(factory, "creator@example.com")
        other = await add_user(factory, "other@example.com")
        await add_service_client(
            factory, name="creator-census", client_id=CENSUS_ID, created_by=creator.id
        )
        await add_service_client(
            factory, name="other-service", client_id=OTHER_ID, created_by=creator.id
        )
        await add_service_client(
            factory, name="creator-census-reauth", client_id=REAUTH_ID, created_by=creator.id
        )
        google = await add_connection(factory, user_id=creator.id, purposes=granted())
        yield {
            "client": client,
            "factory": factory,
            "creator": creator,
            "other": other,
            "google": google,
        }


async def _exchange(env, *, subject=None, actor=None, user="creator", **overrides):
    form = {
        "grant_type": GRANT,
        "subject_token": subject if subject is not None else mint_user_token(env[user].id),
        "subject_token_type": AT,
        "actor_token": actor if actor is not None else mint_service_token(CENSUS_ID),
        "actor_token_type": AT,
        "purpose": YT_PURPOSE,
    }
    form.update(overrides)
    return await env["client"].post(EXCHANGE, data=form)


# ---- allowed path ------------------------------------------------------------


async def test_exchange_returns_provider_token_and_audits_both_identities(env):
    resp = await _exchange(env)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] == "provider-access-placeholder"
    assert body["issued_token_type"] == AT
    assert body["purpose"] == YT_PURPOSE
    assert body["provider_type"] == "google"
    assert set(YT_SCOPES) <= set(body["scope"].split())
    assert 0 < body["expires_in"] <= 300
    assert body["connection_id"] == str(env["google"].id)

    (log,) = await activity(env["factory"], "tool.delegation.issued")
    meta = log.activity_metadata
    assert log.user_id == env["creator"].id
    assert log.resource_id == str(env["google"].id)
    assert meta["purpose"] == YT_PURPOSE
    assert meta["path"] == "exchange"
    assert meta["actor_client"] == "creator-census"
    assert meta["actor_client_id"] == CENSUS_ID
    assert meta["subject_user_id"] == str(env["creator"].id)
    assert meta["subject_audience"] == "creator-census-api"


async def test_janua_picks_the_granted_connection_itself(env):
    factory, other = env["factory"], env["other"]
    await add_connection(factory, user_id=other.id, provider_type="github", purposes=granted())
    await add_connection(factory, user_id=other.id, scopes=GOOGLE_BASE_SCOPES)
    chosen = await add_connection(
        factory, user_id=other.id, purposes=granted(), access_token="the-granted-one"
    )
    resp = await _exchange(env, user="other")
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"] == "the-granted-one"
    (log,) = await activity(factory, "tool.delegation.issued")
    assert log.resource_id == str(chosen.id)


async def test_ttl_is_bounded(env):
    resp = await _exchange(env, ttl_seconds="5000")
    assert resp.status_code == 422


# ---- subject rules --------------------------------------------------------------


async def test_subject_without_grant_is_refused(env):
    await add_connection(env["factory"], user_id=env["other"].id, scopes=GOOGLE_BASE_SCOPES)
    resp = await _exchange(env, user="other")
    assert resp.status_code == 403
    assert reason(resp) == "purpose_not_granted"


async def test_subject_whose_only_grant_is_expired_must_reauthorize(env):
    await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        status=ConnectedAccountStatus.EXPIRED.value,
    )
    resp = await _exchange(env, user="other")
    assert resp.status_code == 409
    assert reason(resp) == "reauthorization_required"


async def test_revoked_connection_does_not_count(env):
    await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        status=ConnectedAccountStatus.REVOKED.value,
    )
    resp = await _exchange(env, user="other")
    assert resp.status_code == 403
    assert reason(resp) == "purpose_not_granted"


async def test_subject_for_an_unlisted_audience_is_refused(env):
    token = mint_user_token(env["creator"].id, audience="some-other-api")
    resp = await _exchange(env, subject=token)
    assert resp.status_code == 401
    assert reason(resp) == "invalid_subject_token"


async def test_service_token_as_subject_is_refused(env):
    token = mint_service_token(CENSUS_ID, audience="creator-census-api")
    resp = await _exchange(env, subject=token)
    assert resp.status_code == 403
    assert reason(resp) == "subject_must_be_user"


async def test_actor_token_replayed_as_subject_is_refused(env):
    resp = await _exchange(env, subject=mint_service_token(CENSUS_ID))
    assert resp.status_code == 401
    assert reason(resp) == "invalid_subject_token"


async def test_expired_subject_is_refused(env):
    token = mint_user_token(env["creator"].id, expires_in=timedelta(seconds=-30))
    resp = await _exchange(env, subject=token)
    assert resp.status_code == 401
    assert reason(resp) == "invalid_subject_token"


async def test_suspended_subject_is_refused(env):
    suspended = await add_user(env["factory"], "gone@example.com", status=UserStatus.SUSPENDED)
    await add_connection(env["factory"], user_id=suspended.id, purposes=granted())
    resp = await _exchange(env, subject=mint_user_token(suspended.id))
    assert resp.status_code == 403
    assert reason(resp) == "subject_user_unavailable"


async def test_service_principal_subject_is_refused(env):
    bot = await add_user(env["factory"], "bot@example.com", service_account=True)
    resp = await _exchange(env, subject=mint_user_token(bot.id))
    assert resp.status_code == 403
    assert reason(resp) == "subject_user_unavailable"


# ---- actor rules ----------------------------------------------------------------


async def test_client_not_in_exchange_clients_is_refused(env):
    resp = await _exchange(env, actor=mint_service_token(OTHER_ID))
    assert resp.status_code == 403
    assert reason(resp) == "client_not_permitted"
    assert await activity(env["factory"], "tool.delegation.issued") == []


async def test_offline_client_cannot_use_the_exchange(env):
    resp = await _exchange(env, actor=mint_service_token(REAUTH_ID))
    assert resp.status_code == 403
    assert reason(resp) == "client_not_permitted"


async def test_actor_without_delegate_scope_is_refused(env):
    resp = await _exchange(env, actor=mint_service_token(CENSUS_ID, scope="openid"))
    assert resp.status_code == 403
    assert reason(resp) == "service_token_missing_scope"


async def test_actor_for_another_audience_is_refused(env):
    resp = await _exchange(env, actor=mint_service_token(CENSUS_ID, audience="karafiel-api"))
    assert resp.status_code == 401
    assert reason(resp) == "invalid_service_token"


async def test_user_token_as_actor_is_refused(env):
    resp = await _exchange(env, actor=mint_user_token(env["creator"].id))
    assert resp.status_code == 401
    assert reason(resp) == "invalid_service_token"


async def test_deactivated_actor_is_refused_even_with_live_token(env):
    from sqlalchemy import update

    from app.models import OAuthClient

    actor = mint_service_token(CENSUS_ID)
    async with env["factory"]() as db:
        await db.execute(
            update(OAuthClient).where(OAuthClient.client_id == CENSUS_ID).values(is_active=False)
        )
        await db.commit()
    resp = await _exchange(env, actor=actor)
    assert resp.status_code == 403
    assert reason(resp) == "service_client_grant_unavailable"


async def test_symmetric_jwt_manager_is_refused(env, monkeypatch):
    actor, subject = mint_service_token(CENSUS_ID), mint_user_token(env["creator"].id)
    from app.core.jwt_manager import jwt_manager

    monkeypatch.setattr(jwt_manager, "algorithm", "HS256")
    resp = await _exchange(env, actor=actor, subject=subject)
    assert resp.status_code == 401
    assert reason(resp) == "service_token_requires_rs256"


# ---- request shape -------------------------------------------------------------


async def test_unknown_purpose_is_refused(env):
    resp = await _exchange(env, purpose="made-up.purpose")
    assert resp.status_code == 403
    assert reason(resp) == "unknown_purpose"


async def test_wrong_grant_type_is_refused(env):
    resp = await _exchange(env, grant_type="client_credentials")
    assert resp.status_code == 400
    assert reason(resp) == "unsupported_grant_type"


async def test_wrong_token_type_is_refused(env):
    resp = await _exchange(env, subject_token_type="urn:ietf:params:oauth:token-type:id_token")
    assert resp.status_code == 400
    assert reason(resp) == "unsupported_token_type"


# ---- refresh -----------------------------------------------------------------------


async def _stale(env, **kw):
    return await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        expires_in=kw.pop("expires_in", timedelta(seconds=-60)),
        **kw,
    )


async def test_stale_google_token_is_refreshed_before_exchange(env):
    stale = await _stale(env, expires_in=timedelta(seconds=30), access_token="stale")
    fresh = {
        "access_token": "fresh-access-placeholder",
        "expires_in": 3599,
        "scope": " ".join(GOOGLE_BASE_SCOPES + YT_SCOPES),
    }
    with patch.object(
        OAuthService, "refresh_access_token", AsyncMock(return_value=fresh)
    ) as refresh:
        resp = await _exchange(env, user="other")
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"] == "fresh-access-placeholder"
    refresh.assert_awaited_once()
    row = await get_connection(env["factory"], stale.id)
    assert row.access_token_encrypted == "fresh-access-placeholder"
    assert row.oauth_expires_at > datetime.utcnow() + timedelta(minutes=50)


async def test_refresh_rejected_marks_expired_and_requires_reauthorization(env):
    stale = await _stale(env)
    rejected = AsyncMock(side_effect=ProviderRefreshRejected("invalid_grant"))
    with patch.object(OAuthService, "refresh_access_token", rejected):
        resp = await _exchange(env, user="other")
        assert resp.status_code == 409
        assert reason(resp) == "reauthorization_required"
        again = await _exchange(env, user="other")
        assert again.status_code == 409
        assert rejected.await_count == 1  # the provider is not asked again
    row = await get_connection(env["factory"], stale.id)
    assert row.status == ConnectedAccountStatus.EXPIRED.value
    assert await activity(env["factory"], "tool.delegation.issued") == []


async def test_refresh_that_drops_the_purpose_scope_requires_reauthorization(env):
    await _stale(env)
    narrowed = {"access_token": "fresh", "expires_in": 3599, "scope": "openid"}
    with patch.object(OAuthService, "refresh_access_token", AsyncMock(return_value=narrowed)):
        resp = await _exchange(env, user="other")
    assert resp.status_code == 409


async def test_missing_refresh_token_requires_reauthorization(env):
    stale = await _stale(env, expires_in=None, refresh_token=None)
    resp = await _exchange(env, user="other")
    assert resp.status_code == 409
    row = await get_connection(env["factory"], stale.id)
    assert row.status == ConnectedAccountStatus.EXPIRED.value


async def test_provider_outage_is_503_and_keeps_the_consent(env):
    stale = await _stale(env)
    outage = AsyncMock(side_effect=ProviderRefreshUnavailable("provider_status_503"))
    with patch.object(OAuthService, "refresh_access_token", outage):
        resp = await _exchange(env, user="other")
    assert resp.status_code == 503
    assert reason(resp) == "provider_refresh_unavailable"
    row = await get_connection(env["factory"], stale.id)
    assert row.status == ConnectedAccountStatus.ACTIVE.value


# ---- offline path: service token + X-Acting-User-Id -----------------------------


async def _delegate(
    env, connection_id, *, bearer=None, purpose=YT_PURPOSE, headers=None, acting="creator"
):
    hdrs = {"X-Acting-User-Id": str(env[acting].id)}
    if bearer is not None:
        hdrs["Authorization"] = f"Bearer {bearer}"
    hdrs.update(headers or {})
    return await env["client"].post(
        f"/api/v1/connections/{connection_id}/token",
        json={"purpose": purpose, "ttl_seconds": 300},
        headers=hdrs,
    )


async def test_offline_client_delegates_and_audits(env):
    resp = await _delegate(env, env["google"].id, bearer=mint_service_token(REAUTH_ID))
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"] == "provider-access-placeholder"
    assert resp.json()["purpose"] == YT_PURPOSE
    (log,) = await activity(env["factory"], "tool.delegation.issued")
    meta = log.activity_metadata
    assert meta["path"] == "offline"
    assert meta["actor_client"] == "creator-census-reauth"
    assert meta["subject_user_id"] == str(env["creator"].id)
    assert meta["purpose"] == YT_PURPOSE


async def test_exchange_client_is_refused_on_the_offline_path(env):
    resp = await _delegate(env, env["google"].id, bearer=mint_service_token(CENSUS_ID))
    assert resp.status_code == 403
    assert reason(resp) == "user_binding_required"
    assert await activity(env["factory"], "tool.delegation.issued") == []


async def test_unlisted_client_is_refused_on_the_offline_path(env):
    resp = await _delegate(env, env["google"].id, bearer=mint_service_token(OTHER_ID))
    assert resp.status_code == 403
    assert reason(resp) == "user_binding_required"


async def test_offline_unknown_purpose_is_refused(env):
    resp = await _delegate(
        env, env["google"].id, bearer=mint_service_token(REAUTH_ID), purpose="tool_execute"
    )
    assert resp.status_code == 403
    assert reason(resp) == "unknown_purpose"


async def test_offline_requires_the_users_grant(env):
    bare = await add_connection(env["factory"], user_id=env["other"].id, scopes=GOOGLE_BASE_SCOPES)
    resp = await _delegate(env, bare.id, bearer=mint_service_token(REAUTH_ID), acting="other")
    assert resp.status_code == 403
    assert reason(resp) == "purpose_not_granted"


async def test_offline_revoked_connection_is_not_granted(env):
    revoked = await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes={YT_PURPOSE: {"status": "revoked", "scopes": YT_SCOPES}},
        status=ConnectedAccountStatus.REVOKED.value,
    )
    resp = await _delegate(env, revoked.id, bearer=mint_service_token(REAUTH_ID), acting="other")
    assert resp.status_code == 403
    assert reason(resp) == "purpose_not_granted"


async def test_offline_expired_connection_requires_reauthorization(env):
    expired = await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        status=ConnectedAccountStatus.EXPIRED.value,
    )
    resp = await _delegate(env, expired.id, bearer=mint_service_token(REAUTH_ID), acting="other")
    assert resp.status_code == 409
    assert reason(resp) == "reauthorization_required"


async def test_offline_connection_must_belong_to_acting_user(env):
    resp = await _delegate(
        env, env["google"].id, bearer=mint_service_token(REAUTH_ID), acting="other"
    )
    assert resp.status_code == 403
    assert reason(resp) == "acting_user_mismatch"


async def test_offline_provider_mismatch_is_refused(env):
    github = await add_connection(
        env["factory"], user_id=env["creator"].id, provider_type="github", purposes=granted()
    )
    resp = await _delegate(env, github.id, bearer=mint_service_token(REAUTH_ID))
    assert resp.status_code == 403
    assert reason(resp) == "purpose_provider_mismatch"


async def test_offline_reverification_surfaces_google_side_revocation(env):
    """The real re-check: a Google refresh that is rejected -> 409 + EXPIRED."""
    stale = await _stale(env)
    rejected = AsyncMock(side_effect=ProviderRefreshRejected("invalid_grant"))
    with patch.object(OAuthService, "refresh_access_token", rejected):
        resp = await _delegate(env, stale.id, bearer=mint_service_token(REAUTH_ID), acting="other")
    assert resp.status_code == 409
    assert reason(resp) == "reauthorization_required"
    row = await get_connection(env["factory"], stale.id)
    assert row.status == ConnectedAccountStatus.EXPIRED.value


async def test_static_token_is_refused_for_registered_purpose(env):
    resp = await _delegate(env, env["google"].id, headers={"X-Service-Token": STATIC})
    assert resp.status_code == 403
    assert reason(resp) == "user_binding_required"


async def test_static_token_cannot_reach_google(env):
    resp = await _delegate(
        env, env["google"].id, purpose="tool_execute", headers={"X-Service-Token": STATIC}
    )
    assert resp.status_code == 403
    assert reason(resp) == "user_binding_required"


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
        env, github.id, purpose="tool_execute", headers={"X-Service-Token": STATIC}
    )
    assert via_header.status_code == 200, via_header.text
    assert via_header.json()["access_token"] == "github-access-placeholder"
    assert via_header.json()["purpose"] == "tool_execute"

    via_bearer = await _delegate(env, github.id, bearer=STATIC, purpose="tool_execute")
    assert via_bearer.status_code == 200

    logs = await activity(env["factory"], "tool.delegation.issued")
    assert {log.activity_metadata["caller"] for log in logs} == {"static_service_token"}


async def test_legacy_wrong_static_token_is_401(env):
    resp = await _delegate(
        env, env["google"].id, purpose="tool_execute", headers={"X-Service-Token": "nope"}
    )
    assert resp.status_code == 401
    assert reason(resp) == "invalid_service_credentials"


async def test_legacy_disabled_shape_is_unchanged(env, monkeypatch):
    monkeypatch.setattr(settings, "JANUA_SERVICE_TOKEN", "")
    resp = await _delegate(env, uuid.uuid4(), purpose="tool_execute")
    assert resp.status_code == 404
