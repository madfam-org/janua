"""A continuation code is usable only with its original browser transaction."""

import asyncio
import time
from types import SimpleNamespace

import fakeredis.aioredis
import pytest

from app.auth import session_bridge_state as bridge
from app.auth.session_bridge_state import BridgeStateStore, InvalidBridgeState
from app.core.redis_circuit_breaker import RedisUnavailableError, ResilientRedisClient


def _client(decode=True):
    return fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=decode)


async def _start(store):
    return await store.start(
        source_client_id="jnc_source_F-001",
        source_uri="https://map.example.test/bridge",
        source_audience="source-F-001",
        target_client_id="jnc_target_F-002",
        authorization={
            "client_id": "jnc_target_F-002",
            "state": "F-003",
            "code_challenge": "F" * 43,
        },
    )


def _proof(**overrides):
    return {
        "user_id": "F-001",
        "session_id": "F-002",
        "parent_family": "F-003",
        "proof_jti": "F-004",
        "proof_family": "F-005",
        "proof_type": "refresh",
        "source_client_id": "jnc_source_F-001",
        "proof_kind": "direct",
        "assurance_hash": "a" * 64,
        "expires_at": int(time.time()) + 60,
        **overrides,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("decode", [True, False])
async def test_code_consumes_its_whole_browser_binding_once(decode):
    client = _client(decode)
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof())
        bound = await store.bound(start.state, issued.code, start.browser_secret)
        assert bound.proof["user_id"] == "F-001"
        assert bound.transaction["authorization"]["state"] == "F-003"
        await store.consume(bound)
        assert await client.dbsize() == 0
        with pytest.raises(InvalidBridgeState):
            await store.consume(bound)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_wrong_browser_cannot_spend_the_original_code():
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start, other = await _start(store), await _start(store)
        issued = await store.issue(start.state, _proof())
        with pytest.raises(InvalidBridgeState):
            await store.bound(start.state, issued.code, other.browser_secret)
        await store.consume(await store.bound(start.state, issued.code, start.browser_secret))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_code_from_another_transaction_cannot_be_injected():
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        first, second = await _start(store), await _start(store)
        code_one = await store.issue(first.state, _proof())
        code_two = await store.issue(second.state, _proof(user_id="F-006"))
        with pytest.raises(InvalidBridgeState):
            await store.bound(first.state, code_two.code, first.browser_secret)
        await store.consume(await store.bound(first.state, code_one.code, first.browser_secret))
        await store.consume(await store.bound(second.state, code_two.code, second.browser_secret))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_only_one_code_is_issued_per_transaction():
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof())
        with pytest.raises(InvalidBridgeState):
            await store.issue(start.state, _proof())
        await store.consume(await store.bound(start.state, issued.code, start.browser_secret))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_two_consumers_have_exactly_one_success():
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof())
        bound = await store.bound(start.state, issued.code, start.browser_secret)
        results = await asyncio.gather(
            store.consume(bound), store.consume(bound), return_exceptions=True
        )
        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, InvalidBridgeState) for result in results) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_expiration_after_validation_still_prevents_consumption(monkeypatch):
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof())
        bound = await store.bound(start.state, issued.code, start.browser_secret)
        monkeypatch.setattr(bridge, "time", SimpleNamespace(time=lambda: issued.expires_at + 1))
        with pytest.raises(InvalidBridgeState):
            await store.consume(bound)
        assert await client.dbsize() == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": 0},
        {"parent_family": ""},
        {"source_client_id": "jnc_other_F-007"},
        {"proof_kind": "unknown"},
        {"assurance_hash": "not-a-hash"},
        {"proof_kind": "oidc", "proof_type": "access"},
    ],
)
async def test_invalid_proof_cannot_issue_or_destroy_a_transaction(changes):
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        with pytest.raises(InvalidBridgeState):
            await store.issue(start.state, _proof(**changes))
        assert await client.dbsize() == 1
        assert (await store.read(start.state))[1]["source_client_id"] == "jnc_source_F-001"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_raw_credentials_are_never_persisted_with_the_grant():
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        await store.issue(
            start.state,
            _proof(access_token="F-008-synthetic-only", refresh_token="F-009-synthetic-only"),
        )
        stored = " ".join(await client.mget(await client.keys("*")))
        assert "F-008-synthetic-only" not in stored
        assert "F-009-synthetic-only" not in stored
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cache_unavailable_never_creates_a_local_continuation():
    with pytest.raises(RedisUnavailableError):
        await _start(BridgeStateStore(ResilientRedisClient(None)))


@pytest.mark.asyncio
@pytest.mark.parametrize("decode", [True, False])
async def test_approval_burns_source_tuple_and_final_secret_is_one_use(decode):
    client = _client(decode)
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof(access_token="synthetic-F-008"))
        bound = await store.bound(start.state, issued.code, start.browser_secret)
        approval = await store.approve(bound)
        assert approval.expires_at <= issued.expires_at
        assert approval.expires_at <= time.time() + bridge.FINALIZATION_TTL
        assert await client.dbsize() == 1
        with pytest.raises(InvalidBridgeState):
            await store.bound(start.state, issued.code, start.browser_secret)
        with pytest.raises(InvalidBridgeState):
            await store.approved(start.state)
        stored = (await client.mget(await client.keys("*")))[0]
        text = stored.decode() if isinstance(stored, bytes) else stored
        assert approval.code not in text and "synthetic-F-008" not in text
        final = await store.approved(approval.code)
        results = await asyncio.gather(
            store.consume_approval(final), store.consume_approval(final), return_exceptions=True
        )
        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, InvalidBridgeState) for result in results) == 1
        assert await client.dbsize() == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_final_approval_expiry_checked_again_at_consumption(monkeypatch):
    client = _client()
    store = BridgeStateStore(ResilientRedisClient(client))
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof())
        approved = await store.approve(
            await store.bound(start.state, issued.code, start.browser_secret)
        )
        final = await store.approved(approved.code)
        monkeypatch.setattr(bridge, "time", SimpleNamespace(time=lambda: approved.expires_at + 1))
        with pytest.raises(InvalidBridgeState):
            await store.consume_approval(final)
        assert await client.dbsize() == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_approval_write_outage_burns_source_without_local_fallback(monkeypatch):
    client = _client()
    redis = ResilientRedisClient(client)
    store = BridgeStateStore(redis)
    try:
        start = await _start(store)
        issued = await store.issue(start.state, _proof())
        bound = await store.bound(start.state, issued.code, start.browser_secret)

        async def unavailable(*args, **kwargs):
            raise RedisUnavailableError("unavailable")

        monkeypatch.setattr(redis, "strict_set_nx", unavailable)
        with pytest.raises(RedisUnavailableError):
            await store.approve(bound)
        assert await client.dbsize() == 0
        with pytest.raises(InvalidBridgeState):
            await store.approve(bound)
    finally:
        await client.aclose()
