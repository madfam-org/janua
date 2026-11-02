"""One-use browser transactions must consume their entire validated binding."""

import asyncio

import fakeredis.aioredis
import pytest

from app.core.redis_circuit_breaker import RedisUnavailableError, ResilientRedisClient


@pytest.mark.asyncio
async def test_bound_tuple_has_one_winner_across_independent_clients():
    server = fakeredis.FakeServer()
    clients = [fakeredis.aioredis.FakeRedis(server=server, decode_responses=True) for _ in range(2)]
    expected = {
        "F-001:transaction": "browser-bound",
        "F-001:code": "same-transaction",
        "F-001:issued": "same-code",
    }
    try:
        await clients[0].mset(expected)
        results = await asyncio.gather(
            *(ResilientRedisClient(client).strict_compare_delete(expected) for client in clients)
        )
        assert sorted(results) == [False, True]
        assert await clients[0].exists(*expected) == 0
    finally:
        for client in clients:
            await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["F-001:transaction", "F-001:code", "F-001:issued"])
async def test_any_changed_binding_preserves_every_key(changed):
    client = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    expected = {
        "F-001:transaction": "browser-bound",
        "F-001:code": "same-transaction",
        "F-001:issued": "same-code",
    }
    try:
        actual = {**expected, changed: "different"}
        await client.mset(actual)
        assert not await ResilientRedisClient(client).strict_compare_delete(expected)
        assert dict(zip(actual, await client.mget(actual))) == actual
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_missing_binding_preserves_remaining_keys():
    client = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    expected = {"F-001:transaction": "browser-bound", "F-001:code": "same-transaction"}
    try:
        await client.set("F-001:transaction", "browser-bound")
        assert await client.get("F-001:code") is None
        assert not await ResilientRedisClient(client).strict_compare_delete(expected)
        assert await client.get("F-001:transaction") == "browser-bound"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_no_redis_fails_closed_and_empty_tuple_cannot_succeed():
    client = ResilientRedisClient(None)
    with pytest.raises(RedisUnavailableError):
        await client.strict_compare_delete({"F-001:transaction": "browser-bound"})
    assert not await client.strict_compare_delete({})
