"""Real ASGI boundaries with synthetic client metadata and isolated shared Redis.

Live SQL/session authority is covered separately; these tests isolate routing,
browser binding, client registration, Origin, one-use consumption and cookies.
"""

import base64
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.auth.session_bridge_authority import InvalidSessionProof
from app.core.error_handling import redis_unavailable_handler
from app.core.redis_circuit_breaker import RedisUnavailableError, ResilientRedisClient
from app.core.reserved_oauth_boundaries import SILENT_AUTH_SCOPE
from app.routers.v1 import oauth_provider
from app.routers.v1 import session_bridge as bridge

USER = "00000000-0000-4000-8000-000000000901"
SESSION = "00000000-0000-4000-8000-000000000902"
OTHER = "00000000-0000-4000-8000-000000000903"
SOURCE = "https://map.source.test/api/auth/session-bridge"
SOURCE_ORIGIN = "https://map.source.test"
CALLBACK = "https://erp.target.test/api/callback?fixed=U-901"
BASIC = "Basic " + base64.b64encode(b"jnc_U-901:synthetic-U-901").decode()


@pytest_asyncio.fixture
async def env(monkeypatch):
    monkeypatch.setattr(bridge.settings, "SESSION_BRIDGE_ENABLED", True)
    monkeypatch.setattr(bridge.settings, "COOKIE_DOMAIN", None)
    source = SimpleNamespace(
        client_id="jnc_U-901",
        audience="source-U-901",
        name="U-901-source",
        is_active=True,
        is_confidential=True,
        redirect_uris=[SOURCE],
        allowed_scopes=["openid", "profile", "email", SILENT_AUTH_SCOPE],
        grant_types=["authorization_code", "refresh_token"],
        verify_secret=lambda value: value == "synthetic-U-901",
    )
    target = SimpleNamespace(
        **{
            **source.__dict__,
            "client_id": "jnc_U-902",
            "audience": "target-U-902",
            "redirect_uris": [CALLBACK],
        }
    )
    clients = {source.client_id: source, target.client_id: target}
    lookup = AsyncMock(side_effect=lambda client_id, db: clients.get(client_id))
    monkeypatch.setattr(bridge, "_get_oauth_client", lookup)
    monkeypatch.setattr(oauth_provider, "_get_oauth_client", lookup)
    db = AsyncMock()
    rows = Mock()
    rows.scalars.return_value.all.return_value = [source]
    db.execute.return_value = rows
    user = SimpleNamespace(id=UUID(USER), status="active")
    parent = SimpleNamespace(
        id=UUID(SESSION),
        user_id=UUID(USER),
        refresh_token_family="U-904",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    proof = {
        "user_id": USER,
        "session_id": SESSION,
        "parent_family": "U-904",
        "proof_jti": "U-905",
        "proof_family": "U-904",
        "proof_type": "access",
        "proof_kind": "direct",
        "assurance_hash": "a" * 64,
        "source_client_id": source.client_id,
        "expires_at": int(time.time()) + 300,
    }
    verify, recheck = AsyncMock(return_value=proof), AsyncMock(return_value=(user, parent))
    monkeypatch.setattr(bridge, "verify_source_proof", verify)
    monkeypatch.setattr(bridge, "recheck_source_proof", recheck)
    estate, hosted = AsyncMock(return_value=(None, None)), AsyncMock(return_value=None)
    monkeypatch.setattr(bridge, "resolve_sso_cookie_session", estate)
    monkeypatch.setattr(bridge, "_verify_own_access_token", hosted)
    raw = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    redis = ResilientRedisClient(raw)
    app = FastAPI()
    app.include_router(bridge.router, prefix="/api/v1")
    app.dependency_overrides[bridge.get_db] = lambda: db
    app.dependency_overrides[bridge.get_redis] = lambda: redis
    app.add_exception_handler(RedisUnavailableError, redis_unavailable_handler)
    params = {
        "response_type": "code",
        "client_id": target.client_id,
        "redirect_uri": CALLBACK,
        "scope": f"openid profile email {SILENT_AUTH_SCOPE}",
        "audience": target.audience,
        "prompt": "none",
        "state": "U-901-" + "S" * 32,
        "nonce": "N" * 32,
        "code_challenge": "C" * 43,
        "code_challenge_method": "S256",
        "bridge_uri": SOURCE,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://auth.issuer.test"
    ) as client:
        yield SimpleNamespace(
            client=client,
            app=app,
            redis=redis,
            raw=raw,
            db=db,
            rows=rows,
            source=source,
            target=target,
            params=params,
            proof=proof,
            user=user,
            parent=parent,
            verify=verify,
            recheck=recheck,
            estate=estate,
            hosted=hosted,
            lookup=lookup,
        )
    await raw.aclose()


async def begin(env):
    response = await env.client.get("/api/v1/oauth/session-bridge/start", params=env.params)
    assert response.status_code == 303
    transaction = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    return transaction, response


async def issued(env):
    transaction, initial = await begin(env)
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/prepare",
        json={"state": transaction, "access_token": "synthetic-U-901-access"},
        headers={"authorization": BASIC},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"code"}
    assert "synthetic-U-901-access" not in response.text
    return transaction, response.json()["code"], initial


async def approve(env, transaction, code, **kwargs):
    return await env.client.post(
        "/api/v1/oauth/session-bridge/complete",
        data={"state": transaction, "code": code},
        headers={"origin": SOURCE_ORIGIN, **kwargs},
    )


async def finish(env, transaction, code, **kwargs):
    response = await approve(env, transaction, code, **kwargs)
    if response.status_code == 303 and response.headers["location"] == bridge.FINAL_PATH:
        return await env.client.get(bridge.FINAL_PATH)
    return response


@pytest.mark.asyncio
async def test_initializer_is_private_host_only_and_public_redirect_contains_no_proof(env):
    transaction, response = await begin(env)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(bridge.COOKIE + "=")
    for attribute in ("Secure", "HttpOnly", "Path=/", "SameSite=none", "Max-Age=120"):
        assert attribute in cookie
    assert "Domain=" not in cookie
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert set(parse_qs(urlsplit(response.headers["location"]).query)) == {"state"}
    assert len(transaction) == 43
    env.verify.assert_not_called()


@pytest.mark.asyncio
async def test_success_consumes_before_cookie_and_resumes_original_oidc_state(env, monkeypatch):
    transaction, code, _ = await issued(env)
    real_set = bridge.set_sso_cookie

    def checked_set(response, user_id, parent):
        # Async Redis is asserted after response; ordering is observed by the callback below.
        assert consumed.called
        return real_set(response, user_id, parent)

    real_consume = bridge.BridgeStateStore.consume_approval
    consumed = AsyncMock(wraps=real_consume)

    async def observe_consume(store, bound):
        return await consumed(store, bound)

    monkeypatch.setattr(bridge.BridgeStateStore, "consume_approval", observe_consume)
    monkeypatch.setattr(bridge, "set_sso_cookie", checked_set)
    response = await finish(env, transaction, code)
    assert response.status_code == 303
    location = urlsplit(response.headers["location"])
    assert location.path == "/api/v1/oauth/authorize"
    query = parse_qs(location.query)
    for key in (
        "state",
        "nonce",
        "code_challenge",
        "code_challenge_method",
        "client_id",
        "redirect_uri",
        "prompt",
    ):
        assert query[key] == [env.params[key]]
    assert await env.raw.dbsize() == 0
    names = [value.split("=", 1)[0] for value in response.headers.get_list("set-cookie")]
    assert names == ["janua_sso", bridge.COOKIE, bridge.FINAL_COOKIE]
    assert env.recheck.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin",
    [
        None,
        "null",
        "https://foreign.test",
        SOURCE_ORIGIN + "/path",
        SOURCE_ORIGIN + ",https://foreign.test",
    ],
)
async def test_foreign_or_absent_origin_cannot_consume_a_valid_code(env, origin):
    transaction, code, _ = await issued(env)
    headers = {} if origin is None else {"origin": origin}
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/complete",
        data={"state": transaction, "code": code},
        headers=headers,
    )
    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert await env.raw.dbsize() == 3
    env.recheck.assert_not_called()
    assert (await finish(env, transaction, code)).status_code == 303


@pytest.mark.asyncio
async def test_duplicate_origin_and_get_completion_never_grant(env):
    transaction, code, _ = await issued(env)
    get = await env.client.get(
        "/api/v1/oauth/session-bridge/complete", params={"state": transaction, "code": code}
    )
    assert get.status_code == 405 and "set-cookie" not in get.headers
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/complete",
        data={"state": transaction, "code": code},
        headers=[("origin", SOURCE_ORIGIN), ("origin", SOURCE_ORIGIN)],
    )
    assert response.status_code == 400 and "set-cookie" not in response.headers
    assert await env.raw.dbsize() == 3


@pytest.mark.asyncio
async def test_another_browser_and_replay_cannot_use_the_grant(env):
    transaction, code, _ = await issued(env)
    original = env.client.cookies.get(bridge.COOKIE)
    env.client.cookies.clear()
    assert (await finish(env, transaction, code)).status_code == 400
    assert await env.raw.dbsize() == 3
    env.client.cookies.set(bridge.COOKIE, original, domain="auth.issuer.test", path="/")
    assert (await finish(env, transaction, code)).status_code == 303
    replay = await env.client.post(
        "/api/v1/oauth/session-bridge/complete",
        data={"state": transaction, "code": code},
        headers={"origin": SOURCE_ORIGIN, "cookie": f"{bridge.COOKIE}={original}"},
    )
    assert replay.status_code == 400 and "set-cookie" not in replay.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["&state=", "&code=", "&error=", "&unexpected=U-901"])
async def test_blank_duplicate_or_unknown_form_fields_are_not_discarded(env, suffix):
    transaction, code, _ = await issued(env)
    body = urlencode({"state": transaction, "code": code}) + suffix
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/complete",
        content=body,
        headers={"origin": SOURCE_ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert await env.raw.dbsize() == 3
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "target_disabled",
        "source_disabled",
        "source_audience",
        "source_uri",
        "target_uri",
        "target_scope",
    ],
)
async def test_client_or_registration_change_after_prepare_is_rechecked(env, change):
    transaction, code, _ = await issued(env)
    if change == "target_disabled":
        env.target.is_active = False
    elif change == "source_disabled":
        env.source.is_active = False
    elif change == "source_audience":
        env.source.audience = "other-U-901"
    elif change == "source_uri":
        env.source.redirect_uris = []
    elif change == "target_uri":
        env.target.redirect_uris = []
    elif change == "target_scope":
        env.target.allowed_scopes = ["email"]
    response = await finish(env, transaction, code)
    assert response.status_code == 400 and "set-cookie" not in response.headers
    assert await env.raw.dbsize() == 3


@pytest.mark.asyncio
async def test_inactive_legacy_hosted_identity_cannot_outrank_the_restored_person(env):
    transaction, code, _ = await issued(env)
    env.client.cookies.set(
        "janua_access_token", "synthetic-hosted-U-903", domain="auth.issuer.test", path="/"
    )
    env.hosted.return_value = {"sub": OTHER}  # Legacy signed/unrevoked token has no sid.
    env.db.get.return_value = SimpleNamespace(id=UUID(OTHER), status="suspended")
    response = await finish(env, transaction, code)
    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["error"] == ["interaction_required"]
    assert query["state"] == [env.params["state"]] and query["fixed"] == ["U-901"]
    # Only private bridge cookies expire. Existing identity cookies are untouched.
    assert [v.split("=", 1)[0] for v in response.headers.get_list("set-cookie")] == [
        bridge.COOKIE,
        bridge.FINAL_COOKIE,
    ]


@pytest.mark.asyncio
async def test_both_live_cookie_identities_are_compared(env):
    transaction, code, _ = await issued(env)
    env.client.cookies.set(
        "janua_sso", "synthetic-estate-U-903", domain="auth.issuer.test", path="/"
    )
    env.client.cookies.set(
        "janua_access_token", "synthetic-hosted-U-901", domain="auth.issuer.test", path="/"
    )
    env.estate.return_value = (SimpleNamespace(id=UUID(OTHER)), env.parent)
    env.hosted.return_value = {"sub": USER}
    env.db.get.return_value = env.user
    response = await finish(env, transaction, code)
    assert parse_qs(urlsplit(response.headers["location"]).query)["error"] == [
        "interaction_required"
    ]
    env.estate.assert_awaited_once()
    env.hosted.assert_awaited_once()
    assert [v.split("=", 1)[0] for v in response.headers.get_list("set-cookie")] == [
        bridge.COOKIE,
        bridge.FINAL_COOKIE,
    ]


@pytest.mark.asyncio
async def test_revocation_after_issue_fails_closed_without_renewing_an_auth_cookie(env):
    transaction, code, _ = await issued(env)
    env.recheck.side_effect = InvalidSessionProof()
    response = await finish(env, transaction, code)
    assert parse_qs(urlsplit(response.headers["location"]).query)["error"] == [
        "interaction_required"
    ]
    assert [v.split("=", 1)[0] for v in response.headers.get_list("set-cookie")] == [
        bridge.COOKIE,
        bridge.FINAL_COOKIE,
    ]


@pytest.mark.asyncio
async def test_source_cancel_requires_browser_and_origin_and_preserves_callback_query(env):
    transaction, _ = await begin(env)
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/complete",
        data={"state": transaction, "error": "login_required"},
        headers={"origin": SOURCE_ORIGIN},
    )
    assert response.status_code == 303 and await env.raw.dbsize() == 0
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["error"] == ["login_required"] and query["fixed"] == ["U-901"]
    assert [v.split("=", 1)[0] for v in response.headers.get_list("set-cookie")] == [
        bridge.COOKIE,
        bridge.FINAL_COOKIE,
    ]


@pytest.mark.asyncio
async def test_client_secret_is_required_and_a_public_source_cannot_prepare(env):
    transaction, _ = await begin(env)
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/prepare",
        json={"state": transaction, "access_token": "synthetic-U-901"},
    )
    assert response.status_code == 401
    env.verify.assert_not_called()
    env.source.is_confidential = False
    response = await env.client.post(
        "/api/v1/oauth/session-bridge/prepare",
        json={"state": transaction, "access_token": "synthetic-U-901"},
        headers={"authorization": BASIC},
    )
    assert response.status_code == 403
    env.verify.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"prompt": "login"},
        {"code_challenge_method": "plain"},
        {"redirect_uri": "https://foreign.test/callback"},
        {"bridge_uri": SOURCE + "?code=U-901"},
        {"resource": "https://foreign.test"},
    ],
)
async def test_unsafe_or_unpreserved_authorization_intent_never_initializes(env, overrides):
    response = await env.client.get(
        "/api/v1/oauth/session-bridge/start", params={**env.params, **overrides}
    )
    assert response.status_code == 400 and await env.raw.dbsize() == 0
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_duplicate_authorization_input_or_ambiguous_source_never_initializes(env):
    response = await env.client.get(
        "/api/v1/oauth/session-bridge/start?" + urlencode(env.params) + "&state=other-U-901"
    )
    assert response.status_code == 400 and await env.raw.dbsize() == 0
    env.rows.scalars.return_value.all.return_value = [env.source, env.source]
    response = await env.client.get("/api/v1/oauth/session-bridge/start", params=env.params)
    assert response.status_code == 400 and await env.raw.dbsize() == 0


@pytest.mark.asyncio
async def test_default_off_and_shared_state_failure_do_not_issue_a_cookie(env, monkeypatch):
    monkeypatch.setattr(bridge.settings, "SESSION_BRIDGE_ENABLED", False)
    response = await env.client.get("/api/v1/oauth/session-bridge/start", params=env.params)
    assert response.status_code == 404 and await env.raw.dbsize() == 0
    assert "set-cookie" not in response.headers
    monkeypatch.setattr(bridge.settings, "SESSION_BRIDGE_ENABLED", True)
    env.app.dependency_overrides[bridge.get_redis] = lambda: ResilientRedisClient(None)
    response = await env.client.get("/api/v1/oauth/session-bridge/start", params=env.params)
    assert response.status_code == 503 and "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_post_only_stages_private_lax_finalizer_and_never_sets_auth(env):
    transaction, code, _ = await issued(env)
    response = await approve(env, transaction, code)
    assert response.status_code == 303 and response.headers["location"] == bridge.FINAL_PATH
    assert not urlsplit(response.headers["location"]).query
    cookies = response.headers.get_list("set-cookie")
    assert [v.split("=", 1)[0] for v in cookies] == [bridge.COOKIE, bridge.FINAL_COOKIE]
    final_cookie = cookies[1]
    for attr in ("Secure", "HttpOnly", "SameSite=lax", "Path=/"):
        assert attr in final_cookie
    assert "Domain=" not in final_cookie
    assert len(env.client.cookies.get(bridge.FINAL_COOKIE)) == 43
    assert await env.raw.dbsize() == 1
    env.estate.assert_not_called()
    env.hosted.assert_not_called()
    # Consumed old tuple cannot be presented as a grant to the safe endpoint.
    denied = await env.client.get(bridge.FINAL_PATH, params={"state": transaction, "code": code})
    assert denied.status_code == 400 and "set-cookie" not in denied.headers
    assert await env.raw.dbsize() == 1
    assert (await env.client.get(bridge.FINAL_PATH)).status_code == 303
    assert await env.raw.dbsize() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("cookie", [None, "W" * 43])
async def test_missing_or_wrong_final_cookie_cannot_spend_another_browsers_approval(env, cookie):
    transaction, code, _ = await issued(env)
    await approve(env, transaction, code)
    original = env.client.cookies.get(bridge.FINAL_COOKIE)
    env.client.cookies.clear()
    headers = {} if cookie is None else {"cookie": f"{bridge.FINAL_COOKIE}={cookie}"}
    response = await env.client.get(bridge.FINAL_PATH, headers=headers)
    assert response.status_code == 400 and "set-cookie" not in response.headers
    assert await env.raw.dbsize() == 1
    response = await env.client.get(
        bridge.FINAL_PATH, headers={"cookie": f"{bridge.FINAL_COOKIE}={original}"}
    )
    assert response.status_code == 303 and await env.raw.dbsize() == 0
    assert (
        await env.client.get(
            bridge.FINAL_PATH, headers={"cookie": f"{bridge.FINAL_COOKIE}={original}"}
        )
    ).status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("held", ["estate", "hosted"])
async def test_lax_identity_first_visible_on_get_or_switched_after_post_blocks_replacement(
    env, held
):
    transaction, code, _ = await issued(env)
    # Model the browser contract explicitly: no Lax auth is delivered on POST.
    response = await approve(env, transaction, code)
    assert response.headers["location"] == bridge.FINAL_PATH
    env.estate.assert_not_called()
    env.hosted.assert_not_called()
    if held == "estate":
        env.client.cookies.set("janua_sso", "synthetic-U-903", domain="auth.issuer.test", path="/")
        env.estate.return_value = (SimpleNamespace(id=UUID(OTHER)), env.parent)
    else:
        env.client.cookies.set(
            "janua_access_token", "synthetic-U-903", domain="auth.issuer.test", path="/"
        )
        env.hosted.return_value = {"sub": OTHER}
        env.db.get.return_value = SimpleNamespace(id=UUID(OTHER), status="active")
    response = await env.client.get(bridge.FINAL_PATH)
    assert parse_qs(urlsplit(response.headers["location"]).query)["error"] == [
        "interaction_required"
    ]
    assert [v.split("=", 1)[0] for v in response.headers.get_list("set-cookie")] == [
        bridge.COOKIE,
        bridge.FINAL_COOKIE,
    ]
    assert await env.raw.dbsize() == 0


@pytest.mark.asyncio
async def test_proof_revoked_between_post_and_get_cannot_establish_estate(env):
    transaction, code, _ = await issued(env)
    await approve(env, transaction, code)
    env.recheck.side_effect = InvalidSessionProof()
    response = await env.client.get(bridge.FINAL_PATH)
    assert parse_qs(urlsplit(response.headers["location"]).query)["error"] == [
        "interaction_required"
    ]
    assert all(
        not value.startswith("janua_sso=") for value in response.headers.get_list("set-cookie")
    )
    assert await env.raw.dbsize() == 0


@pytest.mark.asyncio
async def test_finalization_rechecks_policy_and_default_off_without_grant(env, monkeypatch):
    transaction, code, _ = await issued(env)
    await approve(env, transaction, code)
    monkeypatch.setattr(bridge.settings, "SESSION_BRIDGE_ENABLED", False)
    response = await env.client.get(bridge.FINAL_PATH)
    assert response.status_code == 404 and "set-cookie" not in response.headers
    assert await env.raw.dbsize() == 1
    monkeypatch.setattr(bridge.settings, "SESSION_BRIDGE_ENABLED", True)
    env.source.audience = "changed-U-901"
    response = await env.client.get(bridge.FINAL_PATH)
    assert response.status_code == 400 and await env.raw.dbsize() == 0
    assert all(
        not value.startswith("janua_sso=") for value in response.headers.get_list("set-cookie")
    )


@pytest.mark.asyncio
async def test_finalization_shared_state_outage_never_sets_auth(env):
    transaction, code, _ = await issued(env)
    await approve(env, transaction, code)
    env.app.dependency_overrides[bridge.get_redis] = lambda: ResilientRedisClient(None)
    response = await env.client.get(bridge.FINAL_PATH)
    assert response.status_code == 503 and "set-cookie" not in response.headers
    assert await env.raw.dbsize() == 1
