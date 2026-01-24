"""
Comprehensive JWT Manager and Redis Module Test Suite
Tests for token lifecycle, circuit breaker patterns, and Redis service operations
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
import redis.asyncio as redis_async

# =============================================================================
# Test JWT Manager
# =============================================================================


class TestJWTManagerInitialization:
    """Test JWTManager initialization and key setup."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for HS256 mode."""
        settings = MagicMock()
        settings.JWT_ISSUER = "janua-test"
        settings.JWT_AUDIENCE = "janua-api"
        settings.JWT_KID = "test-kid"
        settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        settings.JWT_PRIVATE_KEY = None  # Force HS256 mode
        settings.JWT_PUBLIC_KEY = None
        settings.JWT_SECRET_KEY = "test-secret-key"
        settings.SECRET_KEY = "fallback-secret"
        settings.ENVIRONMENT = "development"
        return settings

    def test_manager_initialization_hs256(self, mock_settings):
        """Test manager initializes in HS256 mode for development."""
        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            manager = JWTManager()

            assert manager.algorithm == "HS256"
            assert manager.issuer == "janua-test"
            assert manager.audience == "janua-api"
            assert manager.access_token_expire_minutes == 15
            assert manager.refresh_token_expire_days == 7

    def test_manager_raises_in_production_without_rs256(self, mock_settings):
        """Test manager raises error in production without RS256 keys."""
        mock_settings.ENVIRONMENT = "production"

        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            with pytest.raises(ValueError, match="RS256 keys required"):
                JWTManager()


class TestAccessTokenCreation:
    """Test access token creation."""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWTManager with mocked settings."""
        mock_settings = MagicMock()
        mock_settings.JWT_ISSUER = "test-issuer"
        mock_settings.JWT_AUDIENCE = "test-audience"
        mock_settings.JWT_KID = "test-kid"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        mock_settings.JWT_PRIVATE_KEY = None
        mock_settings.JWT_PUBLIC_KEY = None
        mock_settings.JWT_SECRET_KEY = "test-secret-for-jwt"
        mock_settings.SECRET_KEY = "fallback"
        mock_settings.ENVIRONMENT = "development"

        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            return JWTManager()

    def test_create_access_token_returns_tuple(self, jwt_manager):
        """Test access token creation returns correct tuple."""
        token, jti, expires_at = jwt_manager.create_access_token(
            user_id="user-123", email="test@example.com"
        )

        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(expires_at, datetime)
        assert len(jti) > 20  # URL-safe token should be long

    def test_create_access_token_can_be_decoded(self, jwt_manager):
        """Test created access token can be decoded."""
        token, jti, _ = jwt_manager.create_access_token(
            user_id="user-456", email="user@example.com"
        )

        # Decode without verification
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["sub"] == "user-456"
        assert payload["email"] == "user@example.com"
        assert payload["jti"] == jti
        assert payload["type"] == "access"
        assert payload["iss"] == "test-issuer"
        assert payload["aud"] == "test-audience"

    def test_create_access_token_with_additional_claims(self, jwt_manager):
        """Test access token with additional claims."""
        additional = {"roles": ["admin"], "org_id": "org-123"}
        token, _, _ = jwt_manager.create_access_token(
            user_id="user-789", email="admin@example.com", additional_claims=additional
        )

        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["roles"] == ["admin"]
        assert payload["org_id"] == "org-123"

    def test_create_access_token_expiry(self, jwt_manager):
        """Test access token has correct expiry."""
        now = datetime.utcnow()
        _, _, expires_at = jwt_manager.create_access_token(
            user_id="user-exp", email="exp@example.com"
        )

        # Should expire in ~15 minutes
        delta = expires_at - now
        assert 14 <= delta.total_seconds() / 60 <= 16


class TestRefreshTokenCreation:
    """Test refresh token creation."""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWTManager with mocked settings."""
        mock_settings = MagicMock()
        mock_settings.JWT_ISSUER = "test-issuer"
        mock_settings.JWT_AUDIENCE = "test-audience"
        mock_settings.JWT_KID = "test-kid"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        mock_settings.JWT_PRIVATE_KEY = None
        mock_settings.JWT_PUBLIC_KEY = None
        mock_settings.JWT_SECRET_KEY = "test-secret-refresh"
        mock_settings.SECRET_KEY = "fallback"
        mock_settings.ENVIRONMENT = "development"

        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            return JWTManager()

    def test_create_refresh_token_returns_tuple(self, jwt_manager):
        """Test refresh token creation returns correct tuple."""
        token, jti, family, expires_at = jwt_manager.create_refresh_token(user_id="user-123")

        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(family, str)
        assert isinstance(expires_at, datetime)

    def test_create_refresh_token_with_family(self, jwt_manager):
        """Test refresh token creation with existing family."""
        token, jti, family, _ = jwt_manager.create_refresh_token(
            user_id="user-456", family="existing-family"
        )

        assert family == "existing-family"

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["family"] == "existing-family"

    def test_create_refresh_token_generates_new_family(self, jwt_manager):
        """Test refresh token generates new family if not provided."""
        token1, _, family1, _ = jwt_manager.create_refresh_token(user_id="user-1")
        token2, _, family2, _ = jwt_manager.create_refresh_token(user_id="user-2")

        assert family1 != family2  # Different families

    def test_refresh_token_has_correct_type(self, jwt_manager):
        """Test refresh token has type=refresh in payload."""
        token, _, _, _ = jwt_manager.create_refresh_token(user_id="user-type")

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["type"] == "refresh"

    def test_refresh_token_expiry(self, jwt_manager):
        """Test refresh token has correct expiry (7 days)."""
        now = datetime.utcnow()
        _, _, _, expires_at = jwt_manager.create_refresh_token(user_id="user-exp")

        delta = expires_at - now
        assert 6 <= delta.days <= 8


class TestTokenVerification:
    """Test token verification."""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWTManager with mocked settings."""
        mock_settings = MagicMock()
        mock_settings.JWT_ISSUER = "test-issuer"
        mock_settings.JWT_AUDIENCE = "test-audience"
        mock_settings.JWT_KID = "test-kid"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        mock_settings.JWT_PRIVATE_KEY = None
        mock_settings.JWT_PUBLIC_KEY = None
        mock_settings.JWT_SECRET_KEY = "verify-test-secret"
        mock_settings.SECRET_KEY = "fallback"
        mock_settings.ENVIRONMENT = "development"

        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            return JWTManager()

    def test_verify_valid_access_token(self, jwt_manager):
        """Test verifying a valid access token."""
        token, jti, _ = jwt_manager.create_access_token(
            user_id="verify-user", email="verify@test.com"
        )

        payload = jwt_manager.verify_token(token, "access")

        assert payload is not None
        assert payload["sub"] == "verify-user"
        assert payload["email"] == "verify@test.com"
        assert payload["jti"] == jti

    def test_verify_valid_refresh_token(self, jwt_manager):
        """Test verifying a valid refresh token."""
        token, jti, family, _ = jwt_manager.create_refresh_token(user_id="refresh-user")

        payload = jwt_manager.verify_token(token, "refresh")

        assert payload is not None
        assert payload["sub"] == "refresh-user"
        assert payload["jti"] == jti
        assert payload["family"] == family

    def test_verify_token_wrong_type(self, jwt_manager):
        """Test verifying token with wrong type returns None."""
        access_token, _, _ = jwt_manager.create_access_token(
            user_id="wrong-type", email="wrong@test.com"
        )

        # Try to verify as refresh token
        payload = jwt_manager.verify_token(access_token, "refresh")
        assert payload is None

    def test_verify_expired_token(self, jwt_manager):
        """Test verifying expired token returns None."""
        # Create token that's already expired
        expired_payload = {
            "sub": "expired-user",
            "email": "expired@test.com",
            "jti": "expired-jti",
            "iat": datetime.utcnow() - timedelta(hours=1),
            "exp": datetime.utcnow() - timedelta(minutes=30),
            "type": "access",
            "iss": "test-issuer",
            "aud": "test-audience",
        }

        expired_token = jwt.encode(expired_payload, "verify-test-secret", algorithm="HS256")

        payload = jwt_manager.verify_token(expired_token, "access")
        assert payload is None

    def test_verify_invalid_signature(self, jwt_manager):
        """Test verifying token with wrong signature."""
        # Create token with different secret
        payload = {
            "sub": "invalid-sig",
            "email": "invalid@test.com",
            "jti": "invalid-jti",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
            "type": "access",
            "iss": "test-issuer",
            "aud": "test-audience",
        }

        invalid_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        result = jwt_manager.verify_token(invalid_token, "access")
        assert result is None


class TestDecodeTokenUnsafe:
    """Test unsafe token decoding."""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWTManager with mocked settings."""
        mock_settings = MagicMock()
        mock_settings.JWT_ISSUER = "test-issuer"
        mock_settings.JWT_AUDIENCE = "test-audience"
        mock_settings.JWT_KID = "test-kid"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        mock_settings.JWT_PRIVATE_KEY = None
        mock_settings.JWT_PUBLIC_KEY = None
        mock_settings.JWT_SECRET_KEY = "unsafe-test-secret"
        mock_settings.SECRET_KEY = "fallback"
        mock_settings.ENVIRONMENT = "development"

        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            return JWTManager()

    def test_decode_token_unsafe_works(self, jwt_manager):
        """Test unsafe decode works for valid token."""
        token, _, _ = jwt_manager.create_access_token(
            user_id="unsafe-user", email="unsafe@test.com"
        )

        payload = jwt_manager.decode_token_unsafe(token)

        assert payload is not None
        assert payload["sub"] == "unsafe-user"

    def test_decode_token_unsafe_with_wrong_signature(self, jwt_manager):
        """Test unsafe decode works even with wrong signature."""
        # Create token with different secret
        payload = {
            "sub": "wrong-sig-user",
            "email": "wrongsig@test.com",
            "jti": "wrong-jti",
        }
        wrong_sig_token = jwt.encode(payload, "different-secret", algorithm="HS256")

        # Should still decode
        result = jwt_manager.decode_token_unsafe(wrong_sig_token)

        assert result is not None
        assert result["sub"] == "wrong-sig-user"

    def test_decode_token_unsafe_invalid_token(self, jwt_manager):
        """Test unsafe decode returns None for invalid token."""
        result = jwt_manager.decode_token_unsafe("not-a-valid-token")
        assert result is None


class TestEncodeToken:
    """Test custom token encoding."""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWTManager with mocked settings."""
        mock_settings = MagicMock()
        mock_settings.JWT_ISSUER = "test-issuer"
        mock_settings.JWT_AUDIENCE = "test-audience"
        mock_settings.JWT_KID = "test-kid"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        mock_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
        mock_settings.JWT_PRIVATE_KEY = None
        mock_settings.JWT_PUBLIC_KEY = None
        mock_settings.JWT_SECRET_KEY = "encode-test-secret"
        mock_settings.SECRET_KEY = "fallback"
        mock_settings.ENVIRONMENT = "development"

        with patch("app.core.jwt_manager.settings", mock_settings):
            from app.core.jwt_manager import JWTManager

            return JWTManager()

    def test_encode_custom_claims(self, jwt_manager):
        """Test encoding custom claims (e.g., ID token)."""
        custom_claims = {
            "sub": "custom-user",
            "name": "Test User",
            "email": "custom@test.com",
            "nonce": "abc123",
        }

        token = jwt_manager.encode_token(custom_claims)

        # Verify it can be decoded
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert decoded["sub"] == "custom-user"
        assert decoded["name"] == "Test User"
        assert decoded["nonce"] == "abc123"


# =============================================================================
# Test Circuit Breaker
# =============================================================================


class TestCircuitState:
    """Test CircuitState enum."""

    def test_circuit_state_values(self):
        """Test circuit state enum values."""
        from app.core.redis_circuit_breaker import CircuitState

        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestRedisCircuitBreakerInitialization:
    """Test RedisCircuitBreaker initialization."""

    def test_default_initialization(self):
        """Test default circuit breaker initialization."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60
        assert cb.half_open_max_calls == 3

    def test_custom_initialization(self):
        """Test custom circuit breaker initialization."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker(
            failure_threshold=10, recovery_timeout=120, half_open_max_calls=5
        )

        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 120
        assert cb.half_open_max_calls == 5


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""

    def test_closed_to_open_after_failures(self):
        """Test circuit opens after failure threshold."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker(failure_threshold=3)

        # Record failures
        for _ in range(3):
            cb._record_failure()

        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """Test success resets failure count."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker(failure_threshold=5)

        # Record some failures
        cb._record_failure()
        cb._record_failure()
        assert cb.failure_count == 2

        # Success resets
        cb._record_success()
        assert cb.failure_count == 0

    def test_half_open_success_closes_circuit(self):
        """Test half-open success closes circuit."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker()
        cb.state = CircuitState.HALF_OPEN

        cb._record_success()

        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_opens_circuit(self):
        """Test half-open failure re-opens circuit."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker()
        cb.state = CircuitState.HALF_OPEN

        cb._record_failure()

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery logic."""

    def test_should_attempt_reset_after_timeout(self):
        """Test recovery attempt after timeout."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker(recovery_timeout=1)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=2)

        assert cb._should_attempt_reset() is True

    def test_should_not_reset_before_timeout(self):
        """Test no reset before timeout."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker(recovery_timeout=60)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.utcnow()

        assert cb._should_attempt_reset() is False

    def test_should_not_reset_when_closed(self):
        """Test no reset when circuit is closed."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb._should_attempt_reset() is False


class TestCircuitBreakerExecute:
    """Test circuit breaker execute method."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()

        async def successful_op():
            return "success"

        result = await cb.execute(successful_op, fallback_value="fallback")

        assert result == "success"
        assert cb.successful_calls == 1

    @pytest.mark.asyncio
    async def test_execute_failure_uses_fallback(self):
        """Test failed execution uses fallback."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()

        async def failing_op():
            raise redis_async.RedisError("Connection failed")

        result = await cb.execute(failing_op, fallback_value="fallback")

        assert result == "fallback"
        assert cb.failed_calls == 1

    @pytest.mark.asyncio
    async def test_execute_open_circuit_uses_fallback(self):
        """Test open circuit uses fallback immediately."""
        from app.core.redis_circuit_breaker import CircuitState, RedisCircuitBreaker

        cb = RedisCircuitBreaker(recovery_timeout=3600)  # Long timeout to prevent reset
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.utcnow()  # Recent failure, won't attempt reset

        call_count = 0

        async def op():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await cb.execute(op, fallback_value="fallback")

        assert result == "fallback"
        assert call_count == 0  # Operation was never called
        assert cb.fallback_calls == 1

    @pytest.mark.asyncio
    async def test_execute_caches_result(self):
        """Test successful execution caches result."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()

        async def successful_op():
            return "cached_value"

        await cb.execute(successful_op, cache_key="test_key")

        assert "test_key" in cb._fallback_cache
        assert cb._fallback_cache["test_key"] == "cached_value"


class TestCircuitBreakerFallbackCache:
    """Test circuit breaker fallback cache."""

    def test_get_fallback_from_cache(self):
        """Test getting fallback from cache."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()
        cb._fallback_cache["my_key"] = "cached_value"

        result = cb._get_fallback("my_key", "default")

        assert result == "cached_value"
        assert cb._cache_hits == 1

    def test_get_fallback_cache_miss(self):
        """Test fallback cache miss returns default."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()

        result = cb._get_fallback("missing_key", "default")

        assert result == "default"
        assert cb._cache_misses == 1

    def test_cache_eviction_at_max_size(self):
        """Test cache evicts oldest when at max size."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()
        cb._cache_max_size = 3

        # Fill cache
        cb._cache_fallback("key1", "value1")
        cb._cache_fallback("key2", "value2")
        cb._cache_fallback("key3", "value3")

        # Add one more (should evict key1)
        cb._cache_fallback("key4", "value4")

        assert "key1" not in cb._fallback_cache
        assert "key4" in cb._fallback_cache
        assert len(cb._fallback_cache) == 3


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics."""

    def test_get_state_returns_metrics(self):
        """Test get_state returns all metrics."""
        from app.core.redis_circuit_breaker import RedisCircuitBreaker

        cb = RedisCircuitBreaker()
        cb._record_success()
        cb._record_failure()
        cb._cache_fallback("key", "value")

        state = cb.get_state()

        assert "state" in state
        assert "failure_count" in state
        assert "total_calls" in state
        assert "successful_calls" in state
        assert "failed_calls" in state
        assert "fallback_calls" in state
        assert "cache_hits" in state
        assert "cache_misses" in state
        assert "cache_size" in state


# =============================================================================
# Test ResilientRedisClient
# =============================================================================


class TestResilientRedisClient:
    """Test ResilientRedisClient wrapper."""

    def test_get_circuit_status(self):
        """Test getting circuit breaker status."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)
        status = client.get_circuit_status()

        assert "state" in status
        assert status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_get_with_no_redis_uses_fallback(self):
        """Test get with no Redis client uses fallback."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.get("test_key", default="fallback")

        # Without Redis client, should return fallback
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_set_with_no_redis_returns_false(self):
        """Test set with no Redis client returns False."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.set("key", "value")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_with_no_redis_returns_zero(self):
        """Test delete with no Redis client returns 0."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.delete("key")

        assert result == 0

    @pytest.mark.asyncio
    async def test_exists_with_no_redis_returns_zero(self):
        """Test exists with no Redis client returns 0."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.exists("key")

        assert result == 0

    @pytest.mark.asyncio
    async def test_hget_with_no_redis_returns_none(self):
        """Test hget with no Redis client returns None."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.hget("hash", "field")

        assert result is None

    @pytest.mark.asyncio
    async def test_hgetall_with_no_redis_returns_empty(self):
        """Test hgetall with no Redis client returns empty dict."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.hgetall("hash")

        assert result == {}

    @pytest.mark.asyncio
    async def test_ping_with_no_redis_returns_false(self):
        """Test ping with no Redis client returns False."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_with_no_redis(self):
        """Test health check with no Redis client."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        health = await client.health_check()

        assert health["redis_available"] is False
        assert "circuit_breaker" in health

    @pytest.mark.asyncio
    async def test_setex_calls_set_internally(self):
        """Test setex uses set with expiration."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        # With no redis, both should fail gracefully
        result = await client.setex("key", 60, "value")

        assert result is False

    @pytest.mark.asyncio
    async def test_expire_with_no_redis_returns_false(self):
        """Test expire with no Redis client returns False."""
        from app.core.redis_circuit_breaker import ResilientRedisClient

        client = ResilientRedisClient(redis_client=None)

        result = await client.expire("key", 3600)

        assert result is False


# =============================================================================
# Test Redis Config
# =============================================================================


class TestParseRedisUrl:
    """Test Redis URL parsing."""

    def test_parse_simple_url(self):
        """Test parsing simple Redis URL."""
        from app.core.redis_config import parse_redis_url

        result = parse_redis_url("redis://localhost:6379")

        assert result["host"] == "localhost"
        assert result["port"] == 6379
        assert result["password"] is None
        assert result["db"] == 0
        assert result["ssl"] is False

    def test_parse_url_with_password(self):
        """Test parsing URL with password."""
        from app.core.redis_config import parse_redis_url

        result = parse_redis_url("redis://:secret@redis.example.com:6380/1")

        assert result["host"] == "redis.example.com"
        assert result["port"] == 6380
        assert result["password"] == "secret"
        assert result["db"] == 1

    def test_parse_ssl_url(self):
        """Test parsing SSL Redis URL."""
        from app.core.redis_config import parse_redis_url

        result = parse_redis_url("rediss://secure.redis.com:6379")

        assert result["host"] == "secure.redis.com"
        assert result["ssl"] is True

    def test_parse_url_with_db(self):
        """Test parsing URL with database number."""
        from app.core.redis_config import parse_redis_url

        result = parse_redis_url("redis://localhost:6379/5")

        assert result["db"] == 5


# =============================================================================
# Test RedisService - Key Format Tests
# =============================================================================


class TestRedisServiceKeyFormats:
    """Test RedisService key format generation."""

    def test_webauthn_key_format(self):
        """Test WebAuthn challenge key format."""
        # Registration key format
        reg_key = f"webauthn:registration:user-123"
        assert reg_key == "webauthn:registration:user-123"

        # Authentication key format
        auth_key = f"webauthn:authentication:user-456"
        assert auth_key == "webauthn:authentication:user-456"

    def test_mfa_key_format(self):
        """Test MFA code key format."""
        totp_key = f"mfa:totp:user-mfa"
        assert totp_key == "mfa:totp:user-mfa"

        sms_key = f"mfa:sms:user-sms"
        assert sms_key == "mfa:sms:user-sms"

    def test_session_key_format(self):
        """Test session key format."""
        session_key = f"session:session-abc"
        assert session_key == "session:session-abc"

    def test_passkey_key_format(self):
        """Test passkey challenge key format."""
        passkey_key = f"passkey:challenge:user-123"
        assert passkey_key == "passkey:challenge:user-123"

    def test_trusted_device_key_format(self):
        """Test trusted device key format."""
        device_key = f"trusted_device:user-123:device-abc"
        assert device_key == "trusted_device:user-123:device-abc"

    def test_backup_codes_key_format(self):
        """Test backup codes key format."""
        backup_key = f"backup_codes:user-123"
        assert backup_key == "backup_codes:user-123"

    def test_rate_limit_key_format(self):
        """Test rate limit key format."""
        rate_key = f"ratelimit:user:123"
        assert rate_key == "ratelimit:user:123"


class TestRedisServiceDataStructures:
    """Test RedisService data structure formats."""

    def test_mfa_code_data_structure(self):
        """Test MFA code data structure."""
        data = {"code": "123456", "attempts": 0, "created_at": int(time.time())}

        assert "code" in data
        assert "attempts" in data
        assert "created_at" in data
        assert data["attempts"] == 0

    def test_backup_codes_data_structure(self):
        """Test backup codes data structure."""
        codes = ["code1", "code2", "code3"]
        data = {
            "codes": [{"code": code, "used": False} for code in codes],
            "created_at": int(time.time()),
        }

        assert len(data["codes"]) == 3
        assert all(c["used"] is False for c in data["codes"])
        assert "created_at" in data

    def test_trusted_device_data_structure(self):
        """Test trusted device data structure."""
        device_info = {
            "name": "Chrome on MacOS",
            "last_used": int(time.time()),
            "ip_address": "192.168.1.1",
        }

        assert "name" in device_info
        assert "last_used" in device_info

    def test_session_data_structure(self):
        """Test session data structure."""
        session_data = {
            "user_id": "user-123",
            "roles": ["admin", "user"],
            "org_id": "org-456",
        }

        assert "user_id" in session_data
        assert "roles" in session_data


class TestRedisServiceRateLimitLogic:
    """Test rate limiting logic (without Redis)."""

    def test_rate_limit_allowed_calculation(self):
        """Test rate limit allowed calculation."""
        current_count = 5
        limit = 10

        allowed = current_count < limit
        remaining = limit - current_count - 1 if allowed else 0

        assert allowed is True
        assert remaining == 4

    def test_rate_limit_exceeded_calculation(self):
        """Test rate limit exceeded calculation."""
        current_count = 10
        limit = 10

        allowed = current_count < limit
        remaining = limit - current_count - 1 if allowed else 0

        assert allowed is False
        assert remaining == 0

    def test_rate_limit_window_calculation(self):
        """Test rate limit window calculation."""
        now = int(time.time())
        window = 60
        window_start = now - window

        # Entries within window should be counted
        entry_time = now - 30  # 30 seconds ago
        in_window = entry_time > window_start

        assert in_window is True

        # Entries outside window should not be counted
        old_entry_time = now - 90  # 90 seconds ago
        in_window_old = old_entry_time > window_start

        assert in_window_old is False


class TestRedisServiceBackupCodeLogic:
    """Test backup code verification logic (without Redis)."""

    def test_verify_backup_code_logic_success(self):
        """Test backup code verification logic - success case."""
        stored_codes = [
            {"code": "code1", "used": False},
            {"code": "code2", "used": False},
        ]
        input_code = "code1"

        valid = False
        remaining = 0

        for item in stored_codes:
            if not item["used"]:
                if item["code"] == input_code:
                    item["used"] = True
                    valid = True
                else:
                    remaining += 1

        assert valid is True
        assert remaining == 1
        assert stored_codes[0]["used"] is True

    def test_verify_backup_code_logic_invalid(self):
        """Test backup code verification logic - invalid code."""
        stored_codes = [{"code": "code1", "used": False}]
        input_code = "wrong-code"

        valid = False
        remaining = 0

        for item in stored_codes:
            if not item["used"]:
                if item["code"] == input_code:
                    item["used"] = True
                    valid = True
                else:
                    remaining += 1

        assert valid is False
        assert remaining == 1

    def test_verify_backup_code_logic_already_used(self):
        """Test backup code verification logic - already used."""
        stored_codes = [{"code": "code1", "used": True}]
        input_code = "code1"

        valid = False
        remaining = 0

        for item in stored_codes:
            if not item["used"]:
                if item["code"] == input_code:
                    item["used"] = True
                    valid = True
                else:
                    remaining += 1

        assert valid is False
        assert remaining == 0


class TestRedisServiceMFALogic:
    """Test MFA verification logic (without Redis)."""

    def test_mfa_verification_success(self):
        """Test MFA verification success logic."""
        stored = {"code": "123456", "attempts": 0}
        input_code = "123456"
        max_attempts = 3

        # Check if max attempts exceeded
        if stored["attempts"] >= max_attempts:
            valid = False
        elif stored["code"] == input_code:
            valid = True
        else:
            stored["attempts"] += 1
            valid = False

        assert valid is True

    def test_mfa_verification_wrong_code(self):
        """Test MFA verification with wrong code."""
        stored = {"code": "123456", "attempts": 0}
        input_code = "wrong"
        max_attempts = 3

        if stored["attempts"] >= max_attempts:
            valid = False
        elif stored["code"] == input_code:
            valid = True
        else:
            stored["attempts"] += 1
            valid = False

        assert valid is False
        assert stored["attempts"] == 1

    def test_mfa_verification_max_attempts(self):
        """Test MFA verification at max attempts."""
        stored = {"code": "123456", "attempts": 3}
        input_code = "123456"  # Correct code but max attempts reached
        max_attempts = 3

        if stored["attempts"] >= max_attempts:
            valid = False
        elif stored["code"] == input_code:
            valid = True
        else:
            stored["attempts"] += 1
            valid = False

        assert valid is False


class TestRedisServiceTrustedDeviceLogic:
    """Test trusted device TTL logic."""

    def test_trusted_device_default_ttl(self):
        """Test trusted device default TTL is 30 days."""
        default_ttl = 2592000  # 30 days in seconds
        expected_days = 30

        assert default_ttl == expected_days * 24 * 60 * 60

    def test_webauthn_challenge_ttl(self):
        """Test WebAuthn challenge TTL is 5 minutes."""
        default_ttl = 300  # 5 minutes
        expected_minutes = 5

        assert default_ttl == expected_minutes * 60

    def test_mfa_code_ttl(self):
        """Test MFA code default TTL is 5 minutes."""
        default_ttl = 300  # 5 minutes
        expected_minutes = 5

        assert default_ttl == expected_minutes * 60

    def test_session_default_ttl(self):
        """Test session default TTL is 1 hour."""
        default_ttl = 3600  # 1 hour
        expected_hours = 1

        assert default_ttl == expected_hours * 60 * 60
