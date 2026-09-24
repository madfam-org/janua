"""Wire contract for purpose-scoped delegation, as a consuming service calls it.

A consumer implements this contract byte for byte: the request shape, the
200 body fields, and the refusal reasons it branches on. Some reasons mean
the user withdrew consent, and the consumer deletes data on those. Any change
to a string or field pinned here is a breaking change for consumers and must
be coordinated with them, not made silently.
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
    add_connection,
    add_service_client,
    add_user,
    as_user,
    granted,
    mint_service_token,
    mint_user_token,
    mocked_google_revoke,
    sqlite_app,
    use_rs256,
)

from app.dependencies import get_current_user
from app.services.oauth import OAuthService, ProviderRefreshRejected, ProviderRefreshUnavailable

pytestmark = pytest.mark.asyncio

EXCHANGE_URL = "/api/v1/connections/token-exchange"
GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS = "urn:ietf:params:oauth:token-type:access_token"
EXCHANGE_ID = "jnc_contract_exchange"
OFFLINE_ID = "jnc_contract_offline"
STRANGER_ID = "jnc_contract_stranger"

#: Reasons a consumer treats as "the user withdrew consent" (it deletes data).
USER_WITHDRAWAL_REASONS = {
    "acting_user_mismatch",
    "connection_revoked",
    "connection_not_active",
    "connection_not_found",
    "purpose_provider_mismatch",
    "purpose_not_granted",
}


@pytest_asyncio.fixture
async def env(monkeypatch):
    use_rs256(monkeypatch)
    async with sqlite_app() as (client, factory):
        creator = await add_user(factory, "creator@example.com")
        other = await add_user(factory, "other@example.com")
        for name, cid in (
            ("creator-census", EXCHANGE_ID),
            ("creator-census-reauth", OFFLINE_ID),
            ("unrelated-service", STRANGER_ID),
        ):
            await add_service_client(factory, name=name, client_id=cid, created_by=creator.id)
        conn = await add_connection(factory, user_id=creator.id, purposes=granted())
        yield {
            "client": client,
            "factory": factory,
            "creator": creator,
            "other": other,
            "conn": conn,
        }


def _form(subject: str, actor: str, **overrides) -> dict:
    form = {
        "grant_type": GRANT,
        "subject_token": subject,
        "subject_token_type": ACCESS,
        "actor_token": actor,
        "actor_token_type": ACCESS,
        "purpose": YT_PURPOSE,
        "ttl_seconds": "120",  # the consumer sends a string
    }
    form.update(overrides)
    return form


async def _exchange(env, *, user="creator", subject=None, actor=None, **overrides):
    """Exactly what the consumer sends: form-encoded, NO Authorization header."""
    body = _form(
        subject if subject is not None else mint_user_token(env[user].id),
        actor if actor is not None else mint_service_token(EXCHANGE_ID),
        **overrides,
    )
    resp = await env["client"].post(EXCHANGE_URL, data=body)
    assert resp.request.headers.get("content-type") == "application/x-www-form-urlencoded"
    assert "authorization" not in {k.lower() for k in resp.request.headers}
    return resp


def _reason(resp) -> str:
    """Consumers read `error.message` (Janua's envelope) or a string `detail`."""
    body = resp.json()
    if isinstance(body.get("error"), dict) and isinstance(body["error"].get("message"), str):
        return body["error"]["message"]
    assert isinstance(body.get("detail"), str), body
    return body["detail"]


# ---- 200 body -------------------------------------------------------------------


async def test_exchange_200_body_matches_contract(env):
    resp = await _exchange(env)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert isinstance(body["access_token"], str) and body["access_token"]
    expires_at = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    assert expires_at.tzinfo is not None  # ISO 8601 with an explicit UTC marker
    assert isinstance(body["scopes"], list) and all(isinstance(s, str) for s in body["scopes"])
    assert body["scope"] == " ".join(body["scopes"])
    assert "https://www.googleapis.com/auth/youtube.readonly" in body["scopes"]
    assert body["purpose"] == YT_PURPOSE
    assert body["provider_type"] == "google"
    assert uuid.UUID(body["connection_id"]) == env["conn"].id
    # ttl_seconds="120" is honoured (never above what was asked).
    assert 0 < body["expires_in"] <= 120


async def test_authorization_header_is_ignored_on_exchange(env):
    """The actor authenticates by actor_token only; a stray header changes nothing."""
    body = _form(mint_user_token(env["creator"].id), mint_service_token(EXCHANGE_ID))
    resp = await env["client"].post(
        EXCHANGE_URL, data=body, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("ttl", ["59", "901"])
async def test_ttl_bounds_are_60_to_900(env, ttl):
    resp = await _exchange(env, ttl_seconds=ttl)
    assert resp.status_code == 422


async def test_json_body_is_not_accepted(env):
    body = _form(mint_user_token(env["creator"].id), mint_service_token(EXCHANGE_ID))
    resp = await env["client"].post(EXCHANGE_URL, json=body)
    assert resp.status_code == 422


# ---- exchange refusals ------------------------------------------------------------


async def test_purpose_not_granted_is_403(env):
    await add_connection(env["factory"], user_id=env["other"].id, scopes=GOOGLE_BASE_SCOPES)
    resp = await _exchange(env, user="other")
    assert (resp.status_code, _reason(resp)) == (403, "purpose_not_granted")


async def test_rejected_refresh_is_409_reauthorization_required(env):
    await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=-60),
    )
    rejected = AsyncMock(side_effect=ProviderRefreshRejected("invalid_grant"))
    with patch.object(OAuthService, "refresh_access_token", rejected):
        resp = await _exchange(env, user="other")
    assert (resp.status_code, _reason(resp)) == (409, "reauthorization_required")


async def test_provider_outage_is_503_provider_refresh_unavailable(env):
    await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=-60),
    )
    outage = AsyncMock(side_effect=ProviderRefreshUnavailable("provider_status_503"))
    with patch.object(OAuthService, "refresh_access_token", outage):
        resp = await _exchange(env, user="other")
    assert (resp.status_code, _reason(resp)) == (503, "provider_refresh_unavailable")


@pytest.mark.parametrize(
    "actor_factory",
    [
        lambda: "garbage",
        lambda: mint_service_token(EXCHANGE_ID, expires_in=timedelta(seconds=-30)),
        lambda: mint_service_token(EXCHANGE_ID, audience="some-other-api"),
    ],
    ids=["malformed", "expired", "wrong-audience"],
)
async def test_bad_or_expired_actor_is_401_invalid_service_token(env, actor_factory):
    resp = await _exchange(env, actor=actor_factory())
    assert (resp.status_code, _reason(resp)) == (401, "invalid_service_token")


async def test_actor_not_in_exchange_clients_is_403_client_not_permitted(env):
    for client_id in (OFFLINE_ID, STRANGER_ID):
        resp = await _exchange(env, actor=mint_service_token(client_id))
        assert (resp.status_code, _reason(resp)) == (403, "client_not_permitted")


@pytest.mark.parametrize(
    "case",
    ["malformed", "expired", "disallowed-audience", "service-token", "actor-replayed"],
)
async def test_bad_subject_is_invalid_subject_token(env, case):
    subject = {
        "malformed": lambda: "garbage",
        "expired": lambda: mint_user_token(env["creator"].id, expires_in=timedelta(seconds=-30)),
        "disallowed-audience": lambda: mint_user_token(env["creator"].id, audience="other-api"),
        "service-token": lambda: mint_service_token(EXCHANGE_ID, audience="creator-census-api"),
        "actor-replayed": lambda: mint_service_token(EXCHANGE_ID),
    }[case]()
    resp = await _exchange(env, subject=subject)
    assert resp.status_code in (401, 403)
    assert _reason(resp) == "invalid_subject_token"


# ---- offline path -----------------------------------------------------------------


async def _offline(env, connection_id, *, client_id=OFFLINE_ID, acting="creator"):
    return await env["client"].post(
        f"/api/v1/connections/{connection_id}/token",
        json={"purpose": YT_PURPOSE, "ttl_seconds": 120},
        headers={
            "Authorization": f"Bearer {mint_service_token(client_id)}",
            "X-Acting-User-Id": str(env[acting].id),
        },
    )


async def test_offline_200_body_matches_contract(env):
    resp = await _offline(env, env["conn"].id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["access_token"], str) and body["access_token"]
    datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    assert isinstance(body["scopes"], list)
    assert body["purpose"] == YT_PURPOSE
    assert body["provider_type"] == "google"
    assert uuid.UUID(body["connection_id"]) == env["conn"].id


async def test_offline_client_not_listed_is_403_user_binding_required(env):
    for client_id in (EXCHANGE_ID, STRANGER_ID):
        resp = await _offline(env, env["conn"].id, client_id=client_id)
        assert (resp.status_code, _reason(resp)) == (403, "user_binding_required")


# ---- user-withdrawal reasons (consumers delete data on these) ----------------------


async def test_offline_withdrawal_reasons_are_stable(env):
    factory = env["factory"]
    seen = {}

    resp = await _offline(env, env["conn"].id, acting="other")
    seen["acting_user_mismatch"] = (resp.status_code, _reason(resp))

    resp = await _offline(env, uuid.uuid4())
    seen["connection_not_found"] = (resp.status_code, _reason(resp))

    github = await add_connection(
        factory, user_id=env["creator"].id, provider_type="github", purposes=granted()
    )
    resp = await _offline(env, github.id)
    seen["purpose_provider_mismatch"] = (resp.status_code, _reason(resp))

    bare = await add_connection(factory, user_id=env["creator"].id, scopes=GOOGLE_BASE_SCOPES)
    resp = await _offline(env, bare.id)
    seen["purpose_not_granted"] = (resp.status_code, _reason(resp))

    assert seen == {
        "acting_user_mismatch": (403, "acting_user_mismatch"),
        "connection_not_found": (404, "connection_not_found"),
        "purpose_provider_mismatch": (403, "purpose_provider_mismatch"),
        "purpose_not_granted": (403, "purpose_not_granted"),
    }
    assert {r for _, r in seen.values()} <= USER_WITHDRAWAL_REASONS


async def test_revoked_connection_reads_as_withdrawal_on_both_paths(env):
    from app.main import app

    app.dependency_overrides[get_current_user] = as_user(env["creator"])
    try:
        with mocked_google_revoke():
            revoked = await env["client"].delete(f"/api/v1/connections/{env['conn'].id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert revoked.status_code == 200

    offline = await _offline(env, env["conn"].id)
    exchange = await _exchange(env)
    assert _reason(offline) in USER_WITHDRAWAL_REASONS
    assert _reason(exchange) in USER_WITHDRAWAL_REASONS


async def test_non_withdrawal_failures_never_use_a_withdrawal_reason(env):
    """Transient or credential failures must not make a consumer delete data."""
    await add_connection(
        env["factory"],
        user_id=env["other"].id,
        purposes=granted(),
        expires_in=timedelta(seconds=-60),
    )
    outage = AsyncMock(side_effect=ProviderRefreshUnavailable("provider_status_503"))
    with patch.object(OAuthService, "refresh_access_token", outage):
        outage_resp = await _exchange(env, user="other")
    bad_actor = await _exchange(env, actor="garbage")
    bad_subject = await _exchange(env, subject="garbage")
    wrong_client = await _exchange(env, actor=mint_service_token(STRANGER_ID))
    for resp in (outage_resp, bad_actor, bad_subject, wrong_client):
        assert _reason(resp) not in USER_WITHDRAWAL_REASONS, resp.text
