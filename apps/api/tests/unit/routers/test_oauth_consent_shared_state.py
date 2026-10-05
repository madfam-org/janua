"""OAuth consent security state is shared by every replica, never pod memory.

Incident (2026-10-04): a signed-in user pressed Allow on the consent screen of a
first-party relying party that is not pre-consented, and `POST /oauth/consent`
answered 403 "Invalid or expired CSRF token" within seconds. The API runs two
replicas behind one Service, and the consent page and its form post may land on
different replicas.

The CSRF token, the stored authorization request and the authorization code used
to go through the Redis circuit breaker's *fallback* operations. While a
replica's circuit was open — or while its client had never connected, because a
failed PING at first use dropped the client for the life of the process — a
"write" returned False and stored nothing, the consent form was rendered anyway,
and the token could then never validate on any replica.

These tests run two "replicas" (two ResilientRedisClient instances, each with
its own breaker and pod-local fallback cache) over ONE shared fake Redis server,
which is the production topology.
"""

from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis
import pytest
from fastapi import HTTPException

from app.core.redis_circuit_breaker import (
    CircuitState,
    RedisUnavailableError,
    ResilientRedisClient,
)
from app.routers.v1.oauth_provider import (
    _delete_auth_code,
    _get_auth_code,
    _store_auth_code,
    authorize_get,
    handle_consent,
)

pytestmark = pytest.mark.asyncio

USER_ID = uuid4()
REDIRECT_URI = "https://rp.example/api/auth/callback/janua"


def _replica(server: fakeredis.FakeServer) -> ResilientRedisClient:
    """One API replica: its own client, breaker and fallback cache; shared Redis."""
    return ResilientRedisClient(fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))


def _open_circuit(replica: ResilientRedisClient) -> None:
    """Put a replica's breaker in the state a burst of Redis errors leaves it in."""
    cb = replica.circuit_breaker
    cb.state = CircuitState.OPEN
    cb.failure_count = cb.failure_threshold
    from datetime import datetime

    cb.last_failure_time = datetime.utcnow()


def _third_party_client():
    # Not first-party: no madfam-/selva- name prefix, no madfam:silent_auth scope,
    # so the consent screen is shown (the incident's path).
    return SimpleNamespace(
        client_id="rp-client",
        name="Example Relying Party",
        is_active=True,
        is_confidential=True,
        allowed_scopes=["openid", "email", "profile", "offline_access"],
        redirect_uris=[REDIRECT_URI],
        audience=None,
        last_used_at=None,
    )


def _user():
    return SimpleNamespace(
        id=USER_ID, email="person@example.com", email_verified=True, created_at=None
    )


def _patches(client):
    return (
        patch(
            "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
            AsyncMock(return_value=_user()),
        ),
        patch("app.routers.v1.oauth_provider._get_oauth_client", AsyncMock(return_value=client)),
        patch(
            "app.routers.v1.oauth_provider.ConsentService.has_consent",
            AsyncMock(return_value=False),
        ),
        patch("app.routers.v1.oauth_provider.ConsentService.grant_consent", AsyncMock()),
        patch(
            "app.routers.v1.oauth_provider.settings",
            MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
        ),
    )


async def _render_consent(redis: ResilientRedisClient):
    """GET /oauth/authorize on one replica; return the consent page response."""
    client = _third_party_client()
    p = _patches(client)
    with p[0], p[1], p[2], p[3], p[4]:
        db = AsyncMock()
        return await authorize_get(
            request=MagicMock(),
            response_type="code",
            client_id=client.client_id,
            redirect_uri=REDIRECT_URI,
            scope="openid email profile offline_access",
            state="rp-state",
            nonce="rp-nonce",
            code_challenge="E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            code_challenge_method="S256",
            prompt=None,
            login_method=None,
            db=db,
            redis=redis,
        )


def _form_fields(html: str) -> tuple[str, str]:
    auth_request_id = re.search(r'name="auth_request_id" value="([^"]+)"', html).group(1)
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    return auth_request_id, csrf_token


async def _post_consent(redis: ResilientRedisClient, auth_request_id: str, csrf_token: str):
    """POST /oauth/consent (Allow) on one replica; the caller holds the patches."""
    return await handle_consent(
        request=MagicMock(),
        auth_request_id=auth_request_id,
        csrf_token=csrf_token,
        action="allow",
        db=AsyncMock(),
        redis=redis,
    )


async def _submit_consent(redis: ResilientRedisClient, auth_request_id: str, csrf_token: str):
    """POST /oauth/consent (Allow) on one replica."""
    p = _patches(_third_party_client())
    with p[0], p[1], p[2], p[3], p[4]:
        return await _post_consent(redis, auth_request_id, csrf_token)


class TestMechanism:
    """What the breaker's fallback does to a write — the incident's mechanism."""

    async def test_fallback_write_on_an_open_replica_reaches_no_other_replica(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        _open_circuit(pod_a)

        # The pre-fix CSRF write: `setex` through the breaker. It reports
        # failure by RETURN VALUE, which `_generate_csrf_token` never checked.
        assert await pod_a.setex("oauth:csrf:t", 600, str(USER_ID)) is False
        # Nothing reached Redis, so the other replica cannot validate it...
        assert await pod_b.get("oauth:csrf:t") is None
        # ...and neither can the replica that "wrote" it.
        assert await pod_a.get("oauth:csrf:t") is None

    async def test_a_replica_whose_client_never_connected_loses_every_write(self):
        # Pre-fix `init_redis`: a failed first PING set the raw client to None
        # for the life of the process; probes open their own connection, so
        # they kept reporting Redis healthy.
        server = fakeredis.FakeServer()
        pod_a, pod_b = ResilientRedisClient(None), _replica(server)
        assert await pod_a.setex("oauth:csrf:t", 600, str(USER_ID)) is False
        assert await pod_b.get("oauth:csrf:t") is None


class TestConsentAcrossReplicas:
    async def test_consent_rendered_on_one_replica_is_accepted_on_the_other(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)

        page = await _render_consent(pod_a)
        assert page.status_code == 200
        auth_request_id, csrf_token = _form_fields(page.body.decode())

        resp = await _submit_consent(pod_b, auth_request_id, csrf_token)
        assert resp.status_code == 302
        assert resp.headers["location"].startswith(REDIRECT_URI)
        assert "code=" in resp.headers["location"]
        assert "state=rp-state" in resp.headers["location"]

    async def test_open_circuit_on_the_rendering_replica_no_longer_breaks_consent(self):
        """The incident, replayed: the GET replica's breaker is open (an earlier
        blip) while Redis itself answers. Strict operations ignore the breaker
        and write to Redis, so the other replica validates the token."""
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        _open_circuit(pod_a)

        page = await _render_consent(pod_a)
        assert page.status_code == 200
        auth_request_id, csrf_token = _form_fields(page.body.decode())

        resp = await _submit_consent(pod_b, auth_request_id, csrf_token)
        assert resp.status_code == 302
        assert "code=" in resp.headers["location"]
        # Strict calls that reached Redis also let the open breaker recover.
        assert pod_a.circuit_breaker.state != CircuitState.OPEN

    async def test_open_circuit_on_the_posting_replica_no_longer_breaks_consent(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)

        page = await _render_consent(pod_a)
        auth_request_id, csrf_token = _form_fields(page.body.decode())
        _open_circuit(pod_b)

        resp = await _submit_consent(pod_b, auth_request_id, csrf_token)
        assert resp.status_code == 302

    async def test_authorization_code_issued_on_one_replica_is_redeemed_on_the_other(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        _open_circuit(pod_b)

        page = await _render_consent(pod_a)
        auth_request_id, csrf_token = _form_fields(page.body.decode())
        resp = await _submit_consent(pod_a, auth_request_id, csrf_token)
        code = re.search(r"code=([^&]+)", resp.headers["location"]).group(1)

        data = await _get_auth_code(code, pod_b)
        assert data is not None and data["client_id"] == "rp-client"
        assert await _delete_auth_code(code, pod_b) is True
        # Redeemed: gone for every replica, including the one that issued it.
        assert await _get_auth_code(code, pod_a) is None


class TestRedisUnavailable:
    async def test_authorize_refuses_to_render_a_consent_form_it_cannot_honour(self):
        server = fakeredis.FakeServer()
        pod_a = _replica(server)
        server.connected = False

        with pytest.raises(RedisUnavailableError):
            await _render_consent(pod_a)

    async def test_authorize_on_a_replica_without_a_client_answers_unavailable(self):
        with pytest.raises(RedisUnavailableError):
            await _render_consent(ResilientRedisClient(None))

    async def test_consent_post_is_unavailable_not_forbidden_when_redis_is_down(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        page = await _render_consent(pod_a)
        auth_request_id, csrf_token = _form_fields(page.body.decode())

        server.connected = False
        with pytest.raises(RedisUnavailableError):
            await _submit_consent(pod_b, auth_request_id, csrf_token)

        # Nothing was consumed: once Redis is back, the same submit succeeds.
        server.connected = True
        resp = await _submit_consent(pod_b, auth_request_id, csrf_token)
        assert resp.status_code == 302

    async def test_auth_code_store_failure_is_unavailable(self):
        server = fakeredis.FakeServer()
        pod = _replica(server)
        server.connected = False
        with pytest.raises(RedisUnavailableError):
            await _store_auth_code("c", {"client_id": "x"}, pod)


class TestRealRejectionsStay403:
    async def test_unknown_token_is_still_forbidden(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        page = await _render_consent(pod_a)
        auth_request_id, _ = _form_fields(page.body.decode())

        with pytest.raises(HTTPException) as exc:
            await _submit_consent(pod_b, auth_request_id, "not-a-token")
        assert exc.value.status_code == 403

    async def test_token_issued_to_another_user_is_forbidden(self):
        server = fakeredis.FakeServer()
        pod = _replica(server)
        await pod.strict_set("oauth:csrf:someone-else", str(uuid4()), ex=600)
        page = await _render_consent(pod)
        auth_request_id, _ = _form_fields(page.body.decode())

        with pytest.raises(HTTPException) as exc:
            await _submit_consent(pod, auth_request_id, "someone-else")
        assert exc.value.status_code == 403

    async def test_second_submit_of_the_same_form_is_forbidden(self):
        """A double-clicked Allow: the first post succeeds, the second one —
        whose response the browser shows — is the 403 from the incident. The
        page now submits once (below); the server stays strict."""
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        page = await _render_consent(pod_a)
        auth_request_id, csrf_token = _form_fields(page.body.decode())

        first = await _submit_consent(pod_a, auth_request_id, csrf_token)
        assert first.status_code == 302
        with pytest.raises(HTTPException) as exc:
            await _submit_consent(pod_b, auth_request_id, csrf_token)
        assert exc.value.status_code == 403

    async def test_concurrent_submits_issue_exactly_one_code(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        page = await _render_consent(pod_a)
        auth_request_id, csrf_token = _form_fields(page.body.decode())

        # Patches are entered ONCE around both requests: entering them per
        # coroutine would interleave enter/exit and leak a mock past the test.
        p = _patches(_third_party_client())
        with p[0], p[1], p[2], p[3], p[4]:
            results = await asyncio.gather(
                _post_consent(pod_a, auth_request_id, csrf_token),
                _post_consent(pod_b, auth_request_id, csrf_token),
                return_exceptions=True,
            )
        successes = [r for r in results if not isinstance(r, Exception)]
        refusals = [r for r in results if isinstance(r, HTTPException)]
        assert len(successes) == 1
        assert len(refusals) == 1 and refusals[0].status_code == 403

    async def test_consent_form_submits_only_once(self):
        server = fakeredis.FakeServer()
        page = await _render_consent(_replica(server))
        html = page.body.decode()
        assert 'onsubmit="if (this.dataset.submitted) { return false; }' in html
        # The buttons keep their `action` value (a disabled submitter drops it).
        assert 'name="action" value="allow"' in html
        assert "disabled" not in html


class TestAuthCodeSingleUse:
    async def test_only_one_of_two_redemptions_consumes_the_code(self):
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        await _store_auth_code("code-1", {"client_id": "x"}, pod_a)
        outcomes = await asyncio.gather(
            _delete_auth_code("code-1", pod_a), _delete_auth_code("code-1", pod_b)
        )
        assert sorted(outcomes) == [False, True]

    async def test_a_redeemed_code_is_not_served_from_pod_memory(self):
        """Pre-fix, `set` copied the code into the pod-local fallback cache and
        `delete` never evicted it: once that pod's circuit opened, `get` served
        the redeemed code again."""
        server = fakeredis.FakeServer()
        pod_a, pod_b = _replica(server), _replica(server)
        await _store_auth_code("code-2", {"client_id": "x"}, pod_a)
        assert await _delete_auth_code("code-2", pod_b) is True
        _open_circuit(pod_a)
        assert await _get_auth_code("code-2", pod_a) is None


class TestAuthCodeLogging:
    async def test_logs_never_carry_the_code_itself(self):
        server = fakeredis.FakeServer()
        pod = _replica(server)
        code = "secret-code-value-1234567890"
        log = MagicMock()
        with patch("app.routers.v1.oauth_provider.logger", log):
            await _store_auth_code(code, {"client_id": "x"}, pod)
            await _get_auth_code(code, pod)
            await _delete_auth_code(code, pod)
            await _get_auth_code(code, pod)
        rendered = repr(log.mock_calls)
        assert code not in rendered
        assert "code_ref" in rendered
