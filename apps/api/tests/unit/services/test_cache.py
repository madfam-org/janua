import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive tests for app.services.cache module
"""

import pytest
import json
import pickle
from unittest.mock import AsyncMock, patch
from datetime import timedelta

from app.services.cache import CacheService


class TestCacheService:
    """Test CacheService class"""

    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance for testing"""
        # Reset singleton for testing
        CacheService._instance = None
        CacheService._redis_client = None
        return CacheService()

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client"""
        return AsyncMock()

    def test_cache_service_singleton(self):
        """Test CacheService singleton behavior"""
        # Reset singleton
        CacheService._instance = None

        service1 = CacheService()
        service2 = CacheService()

        assert service1 is service2
        assert id(service1) == id(service2)

    @pytest.mark.asyncio
    async def test_get_client_creates_redis_connection(self, cache_service):
        """Test get_client creates Redis connection"""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            client = await cache_service.get_client()

            assert client == mock_redis
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_connection(self, cache_service):
        """Test get_client reuses existing Redis connection"""
        mock_redis = AsyncMock()
        cache_service._redis_client = mock_redis

        client = await cache_service.get_client()

        assert client == mock_redis

    @pytest.mark.asyncio
    async def test_close_connection(self, cache_service):
        """Test closing Redis connection"""
        mock_redis = AsyncMock()
        cache_service._redis_client = mock_redis

        await cache_service.close()

        mock_redis.close.assert_called_once()
        assert cache_service._redis_client is None

    @pytest.mark.asyncio
    async def test_close_no_connection(self, cache_service):
        """Test closing when no connection exists"""
        cache_service._redis_client = None

        # Should not raise exception
        await cache_service.close()

    @pytest.mark.asyncio
    async def test_set_string_value(self, cache_service, mock_redis_client):
        """Test setting string value in cache"""
        cache_service._redis_client = mock_redis_client

        await cache_service.set("test_key", "test_value")

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_expiration(self, cache_service, mock_redis_client):
        """Test setting value with expiration"""
        cache_service._redis_client = mock_redis_client

        await cache_service.set("test_key", "test_value", ex=300)

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[1]['ex'] == 300

    @pytest.mark.asyncio
    async def test_set_with_timedelta_expiration(self, cache_service, mock_redis_client):
        """Test setting value with timedelta expiration"""
        cache_service._redis_client = mock_redis_client

        expiration = timedelta(minutes=5)
        await cache_service.set("test_key", "test_value", ex=expiration)

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[1]['ex'] == expiration

    @pytest.mark.asyncio
    async def test_set_dict_value_json_serialization(self, cache_service, mock_redis_client):
        """Test setting dictionary value (JSON serialization)"""
        cache_service._redis_client = mock_redis_client

        test_dict = {"key": "value", "number": 123}
        await cache_service.set("test_key", test_dict)

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        stored_value = call_args[0][1]

        # Should be JSON string
        assert isinstance(stored_value, str)
        assert json.loads(stored_value) == test_dict

    @pytest.mark.asyncio
    async def test_set_complex_object_pickle_serialization(self, cache_service, mock_redis_client):
        """Test setting complex object (pickle serialization)"""
        cache_service._redis_client = mock_redis_client

        class TestObject:
            def __init__(self, value):
                self.value = value

        test_obj = TestObject("test")
        await cache_service.set("test_key", test_obj)

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        stored_value = call_args[0][1]

        # Should be pickled bytes
        assert isinstance(stored_value, bytes)
        unpickled = pickle.loads(stored_value)
        assert unpickled.value == "test"

    @pytest.mark.asyncio
    async def test_get_string_value(self, cache_service, mock_redis_client):
        """Test getting string value from cache"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.get.return_value = "test_value"

        result = await cache_service.get("test_key")

        assert result == "test_value"
        mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_json_value(self, cache_service, mock_redis_client):
        """Test getting JSON value from cache"""
        cache_service._redis_client = mock_redis_client
        test_dict = {"key": "value", "number": 123}
        mock_redis_client.get.return_value = json.dumps(test_dict)

        result = await cache_service.get("test_key")

        assert result == test_dict
        mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_pickled_value(self, cache_service, mock_redis_client):
        """Test getting pickled value from cache"""
        cache_service._redis_client = mock_redis_client

        class TestObject:
            def __init__(self, value):
                self.value = value

        test_obj = TestObject("test")
        pickled_data = pickle.dumps(test_obj)
        mock_redis_client.get.return_value = pickled_data

        result = await cache_service.get("test_key")

        assert result.value == "test"
        mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache_service, mock_redis_client):
        """Test getting non-existent key"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.get.return_value = None

        result = await cache_service.get("nonexistent_key")

        assert result is None
        mock_redis_client.get.assert_called_once_with("nonexistent_key")

    @pytest.mark.asyncio
    async def test_get_with_default_value(self, cache_service, mock_redis_client):
        """Test getting key with default value"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.get.return_value = None

        result = await cache_service.get("nonexistent_key", default="default_value")

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_delete_key(self, cache_service, mock_redis_client):
        """Test deleting key from cache"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 1

        result = await cache_service.delete("test_key")

        assert result == 1
        mock_redis_client.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_multiple_keys(self, cache_service, mock_redis_client):
        """Test deleting multiple keys from cache"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 2

        result = await cache_service.delete("key1", "key2")

        assert result == 2
        mock_redis_client.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.asyncio
    async def test_exists_key_exists(self, cache_service, mock_redis_client):
        """Test checking if key exists (key exists)"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.exists.return_value = 1

        result = await cache_service.exists("test_key")

        assert result is True
        mock_redis_client.exists.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_exists_key_not_exists(self, cache_service, mock_redis_client):
        """Test checking if key exists (key doesn't exist)"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.exists.return_value = 0

        result = await cache_service.exists("test_key")

        assert result is False
        mock_redis_client.exists.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_expire_key(self, cache_service, mock_redis_client):
        """Test setting expiration on key"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.expire.return_value = True

        result = await cache_service.expire("test_key", 300)

        assert result is True
        mock_redis_client.expire.assert_called_once_with("test_key", 300)

    @pytest.mark.asyncio
    async def test_expire_key_timedelta(self, cache_service, mock_redis_client):
        """Test setting expiration with timedelta"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.expire.return_value = True

        expiration = timedelta(minutes=5)
        result = await cache_service.expire("test_key", expiration)

        assert result is True
        mock_redis_client.expire.assert_called_once_with("test_key", expiration)

    @pytest.mark.asyncio
    async def test_ttl_key(self, cache_service, mock_redis_client):
        """Test getting TTL of key"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = 300

        result = await cache_service.ttl("test_key")

        assert result == 300
        mock_redis_client.ttl.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_keys_pattern(self, cache_service, mock_redis_client):
        """Test getting keys by pattern"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.keys.return_value = ["session:123", "session:456"]

        result = await cache_service.keys("session:*")

        assert result == ["session:123", "session:456"]
        mock_redis_client.keys.assert_called_once_with("session:*")

    @pytest.mark.asyncio
    async def test_flushdb(self, cache_service, mock_redis_client):
        """Test flushing database"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.flushdb.return_value = True

        result = await cache_service.flushdb()

        assert result is True
        mock_redis_client.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_operations(self, cache_service, mock_redis_client):
        """Test pipeline operations"""
        cache_service._redis_client = mock_redis_client
        mock_pipeline = AsyncMock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = ["OK", "OK", 2]

        async with cache_service.pipeline() as pipe:
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")
            pipe.delete("key3")

        mock_redis_client.pipeline.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_hash_operations_hset(self, cache_service, mock_redis_client):
        """Test hash set operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.hset.return_value = 1

        result = await cache_service.hset("hash_key", "field", "value")

        assert result == 1
        mock_redis_client.hset.assert_called_once_with("hash_key", "field", "value")

    @pytest.mark.asyncio
    async def test_hash_operations_hget(self, cache_service, mock_redis_client):
        """Test hash get operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.hget.return_value = "value"

        result = await cache_service.hget("hash_key", "field")

        assert result == "value"
        mock_redis_client.hget.assert_called_once_with("hash_key", "field")

    @pytest.mark.asyncio
    async def test_hash_operations_hgetall(self, cache_service, mock_redis_client):
        """Test hash get all operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.hgetall.return_value = {"field1": "value1", "field2": "value2"}

        result = await cache_service.hgetall("hash_key")

        assert result == {"field1": "value1", "field2": "value2"}
        mock_redis_client.hgetall.assert_called_once_with("hash_key")

    @pytest.mark.asyncio
    async def test_hash_operations_hdel(self, cache_service, mock_redis_client):
        """Test hash delete operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.hdel.return_value = 1

        result = await cache_service.hdel("hash_key", "field")

        assert result == 1
        mock_redis_client.hdel.assert_called_once_with("hash_key", "field")

    @pytest.mark.asyncio
    async def test_list_operations_lpush(self, cache_service, mock_redis_client):
        """Test list left push operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.lpush.return_value = 2

        result = await cache_service.lpush("list_key", "value")

        assert result == 2
        mock_redis_client.lpush.assert_called_once_with("list_key", "value")

    @pytest.mark.asyncio
    async def test_list_operations_rpop(self, cache_service, mock_redis_client):
        """Test list right pop operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.rpop.return_value = "value"

        result = await cache_service.rpop("list_key")

        assert result == "value"
        mock_redis_client.rpop.assert_called_once_with("list_key")

    @pytest.mark.asyncio
    async def test_list_operations_lrange(self, cache_service, mock_redis_client):
        """Test list range operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.lrange.return_value = ["value1", "value2", "value3"]

        result = await cache_service.lrange("list_key", 0, -1)

        assert result == ["value1", "value2", "value3"]
        mock_redis_client.lrange.assert_called_once_with("list_key", 0, -1)

    @pytest.mark.asyncio
    async def test_set_operations_sadd(self, cache_service, mock_redis_client):
        """Test set add operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.sadd.return_value = 1

        result = await cache_service.sadd("set_key", "member")

        assert result == 1
        mock_redis_client.sadd.assert_called_once_with("set_key", "member")

    @pytest.mark.asyncio
    async def test_set_operations_smembers(self, cache_service, mock_redis_client):
        """Test set members operation"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.smembers.return_value = {"member1", "member2"}

        result = await cache_service.smembers("set_key")

        assert result == {"member1", "member2"}
        mock_redis_client.smembers.assert_called_once_with("set_key")

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, cache_service):
        """Test Redis connection error handling"""
        with patch.object(cache_service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection error")
            mock_get_client.return_value = mock_client

            # Should handle connection errors gracefully
            result = await cache_service.get("test_key")
            assert result is None  # Should return None on error

    @pytest.mark.asyncio
    async def test_serialization_error_handling(self, cache_service, mock_redis_client):
        """Test serialization error handling"""
        cache_service._redis_client = mock_redis_client

        # Create object that can't be pickled
        class UnpicklableObject:
            def __reduce__(self):
                raise TypeError("Cannot pickle this object")

        obj = UnpicklableObject()

        # Should handle serialization errors gracefully
        result = await cache_service.set("test_key", obj)
        assert result is None  # Should return None on serialization error

    @pytest.mark.asyncio
    async def test_deserialization_error_handling(self, cache_service, mock_redis_client):
        """Test deserialization error handling"""
        cache_service._redis_client = mock_redis_client
        # Return corrupted data that can't be deserialized
        mock_redis_client.get.return_value = b"corrupted_pickle_data"

        # Should handle deserialization errors gracefully
        result = await cache_service.get("test_key")
        assert result == b"corrupted_pickle_data"  # Should return raw data if can't deserialize

    def test_cache_key_generation(self, cache_service):
        """Test cache key generation utility"""
        # Test key generation if implemented
        key = cache_service._generate_key("prefix", "suffix", 123)
        assert isinstance(key, str)
        assert "prefix" in key

    @pytest.mark.asyncio
    async def test_cache_invalidation_pattern(self, cache_service, mock_redis_client):
        """Test cache invalidation by pattern"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.keys.return_value = ["session:123", "session:456"]
        mock_redis_client.delete.return_value = 2

        # Test invalidating all session keys
        deleted_count = await cache_service.invalidate_pattern("session:*")

        assert deleted_count == 2
        mock_redis_client.keys.assert_called_once_with("session:*")
        mock_redis_client.delete.assert_called_once_with("session:123", "session:456")

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_service, mock_redis_client):
        """Test cache statistics"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.info.return_value = {
            "used_memory": "1024",
            "keyspace_hits": "100",
            "keyspace_misses": "10"
        }

        stats = await cache_service.get_stats()

        assert stats["used_memory"] == "1024"
        assert stats["keyspace_hits"] == "100"
        assert stats["keyspace_misses"] == "10"
        mock_redis_client.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_health_check(self, cache_service, mock_redis_client):
        """Test cache health check"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.ping.return_value = True

        is_healthy = await cache_service.health_check()

        assert is_healthy is True
        mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_health_check_failure(self, cache_service, mock_redis_client):
        """Test cache health check failure"""
        cache_service._redis_client = mock_redis_client
        mock_redis_client.ping.side_effect = Exception("Connection failed")

        is_healthy = await cache_service.health_check()

        assert is_healthy is False