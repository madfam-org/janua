"""
Enhanced JWT Service Test Suite
Comprehensive coverage for JWT token management
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.jwt_service import JWTService

pytestmark = pytest.mark.asyncio


class TestJWTServiceInitialization:
    """Test JWT service initialization and properties"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock()
        db.execute = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        service = JWTService(mock_db, mock_redis)
        return service

    def test_service_initialization(self, mock_db, mock_redis):
        """Test service basic initialization"""
        service = JWTService(mock_db, mock_redis)

        assert service.db is mock_db
        assert service.redis is mock_redis
        assert service._private_key is None
        assert service._public_key is None
        assert service._kid is None

    def test_service_has_db(self, jwt_service, mock_db):
        """Test service has db reference"""
        assert jwt_service.db is mock_db

    def test_service_has_redis(self, jwt_service, mock_redis):
        """Test service has redis reference"""
        assert jwt_service.redis is mock_redis

    def test_private_key_property(self, jwt_service):
        """Test private_key property returns secret key"""
        assert jwt_service.private_key == settings.JWT_SECRET_KEY

    def test_public_key_property(self, jwt_service):
        """Test public_key property returns secret key"""
        assert jwt_service.public_key == settings.JWT_SECRET_KEY

    def test_algorithm_property(self, jwt_service):
        """Test algorithm property returns configured algorithm"""
        assert jwt_service.algorithm == settings.JWT_ALGORITHM

    def test_initial_kid_is_none(self, jwt_service):
        """Test initial KID is None"""
        assert jwt_service._kid is None


class TestTokenCreationMethodSignatures:
    """Test token creation method signatures (without actual token generation due to RS256 config)."""

    @pytest.fixture
    def jwt_service(self):
        return JWTService(AsyncMock(), AsyncMock())

    def test_create_access_token_accepts_identity_id(self, jwt_service):
        """Test create_access_token method signature accepts identity_id"""
        import inspect

        sig = inspect.signature(jwt_service.create_access_token)
        assert "identity_id" in sig.parameters

    def test_create_access_token_accepts_additional_claims(self, jwt_service):
        """Test create_access_token method signature accepts additional_claims"""
        import inspect

        sig = inspect.signature(jwt_service.create_access_token)
        assert "additional_claims" in sig.parameters

    def test_create_access_token_accepts_expires_delta(self, jwt_service):
        """Test create_access_token method signature accepts expires_delta"""
        import inspect

        sig = inspect.signature(jwt_service.create_access_token)
        assert "expires_delta" in sig.parameters

    def test_create_refresh_token_accepts_identity_id(self, jwt_service):
        """Test create_refresh_token method signature accepts identity_id"""
        import inspect

        sig = inspect.signature(jwt_service.create_refresh_token)
        assert "identity_id" in sig.parameters

    def test_create_tokens_accepts_identity_id(self, jwt_service):
        """Test create_tokens method signature accepts identity_id"""
        import inspect

        sig = inspect.signature(jwt_service.create_tokens)
        assert "identity_id" in sig.parameters

    def test_create_tokens_accepts_tenant_id(self, jwt_service):
        """Test create_tokens method signature accepts tenant_id"""
        import inspect

        sig = inspect.signature(jwt_service.create_tokens)
        assert "tenant_id" in sig.parameters


class TestTokenBlacklist:
    """Test token blacklisting functionality"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.keys = AsyncMock(return_value=[])
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_is_token_blacklisted_false(self, jwt_service, mock_redis):
        """Test token not blacklisted when redis.exists returns 0"""
        mock_redis.exists.return_value = 0
        result = await jwt_service.is_token_blacklisted("some-jti")
        assert result is False

    async def test_is_token_blacklisted_true(self, jwt_service, mock_redis):
        """Test token is blacklisted when redis.exists returns 1"""
        mock_redis.exists.return_value = 1
        result = await jwt_service.is_token_blacklisted("blacklisted-jti")
        assert result is True

    async def test_is_user_revoked_false(self, jwt_service, mock_redis):
        """Test user not revoked when redis.exists returns 0"""
        mock_redis.exists.return_value = 0
        result = await jwt_service.is_user_revoked("user-123")
        assert result is False

    async def test_is_user_revoked_true(self, jwt_service, mock_redis):
        """Test user is revoked when redis.exists returns 1"""
        mock_redis.exists.return_value = 1
        result = await jwt_service.is_user_revoked("user-123")
        assert result is True

    async def test_revoke_token(self, jwt_service, mock_redis):
        """Test revoking a token"""
        await jwt_service.revoke_token("token-value", "jti-123")
        mock_redis.setex.assert_called()


class TestTokenClaims:
    """Test token claims storage and retrieval"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_store_token_claims(self, jwt_service, mock_redis):
        """Test storing token claims"""
        claims = {"user_id": "123", "role": "admin"}
        await jwt_service.store_token_claims("jti-123", claims, ttl=3600)
        mock_redis.setex.assert_called_once()


class TestKeyRotationInterval:
    """Test JWT key rotation interval (SOC 2 CF-07)."""

    def test_key_rotation_interval_defined(self):
        """Test KEY_ROTATION_INTERVAL_DAYS is defined."""
        assert hasattr(JWTService, "KEY_ROTATION_INTERVAL_DAYS")
        assert JWTService.KEY_ROTATION_INTERVAL_DAYS == 90

    def test_check_key_age_method_exists(self):
        """Test _check_key_age method exists."""
        service = JWTService(AsyncMock(), AsyncMock())
        assert hasattr(service, "_check_key_age")
        assert callable(service._check_key_age)

    async def test_check_key_age_no_key(self):
        """Test _check_key_age handles no active key gracefully."""
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        service = JWTService(db, AsyncMock())
        # Should not raise
        await service._check_key_age()

    async def test_check_key_age_fresh_key(self):
        """Test _check_key_age does not rotate a fresh key."""
        from datetime import datetime

        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={
            "kid": "test-kid",
            "created_at": datetime.utcnow(),
        })
        service = JWTService(db, AsyncMock())
        with patch.object(service, "rotate_keys", new_callable=AsyncMock) as mock_rotate:
            await service._check_key_age()
            mock_rotate.assert_not_called()

    async def test_check_key_age_old_key_triggers_rotation(self):
        """Test _check_key_age triggers rotation for old keys."""
        from datetime import datetime, timedelta

        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={
            "kid": "old-kid",
            "created_at": datetime.utcnow() - timedelta(days=100),
        })
        db.execute = AsyncMock()
        service = JWTService(db, AsyncMock())
        with patch.object(service, "rotate_keys", new_callable=AsyncMock) as mock_rotate:
            await service._check_key_age()
            mock_rotate.assert_called_once()


class TestTokenClaimsRetrieval:
    """Test token claims retrieval."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_get_token_claims_not_found(self, jwt_service, mock_redis):
        """Test getting non-existent claims"""
        mock_redis.get.return_value = None
        result = await jwt_service.get_token_claims("jti-123")
        assert result is None

    async def test_get_token_claims_found(self, jwt_service, mock_redis):
        """Test getting existing claims"""
        import json

        claims = {"user_id": "123", "role": "admin"}
        mock_redis.get.return_value = json.dumps(claims)
        result = await jwt_service.get_token_claims("jti-123")
        assert result == claims


class TestJWKS:
    """Test JWKS endpoint functionality"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        service = JWTService(mock_db, mock_redis)
        service._private_key = settings.JWT_SECRET_KEY
        service._public_key = settings.JWT_SECRET_KEY
        service._kid = "test-kid-123"
        return service

    async def test_get_public_jwks_returns_dict(self, jwt_service):
        """Test getting public JWKS returns dict"""
        jwks = await jwt_service.get_public_jwks()
        assert isinstance(jwks, dict)
        assert "keys" in jwks

    async def test_get_public_jwks_keys_list(self, jwt_service):
        """Test JWKS contains keys list"""
        jwks = await jwt_service.get_public_jwks()
        assert isinstance(jwks["keys"], list)


class TestHelperMethods:
    """Test helper and utility methods"""

    def test_encode_int_static_method(self):
        """Test _encode_int static method"""
        result = JWTService._encode_int(65537)
        assert isinstance(result, str)

    def test_encode_int_values(self):
        """Test _encode_int with different values"""
        result = JWTService._encode_int(65537)
        assert len(result) > 0

    def test_encode_int_zero(self):
        """Test _encode_int with zero"""
        result = JWTService._encode_int(0)
        assert isinstance(result, str)

    def test_encode_int_large_number(self):
        """Test _encode_int with large number"""
        large_num = 2 ** 2048 - 1
        result = JWTService._encode_int(large_num)
        assert isinstance(result, str)


class TestServiceMethods:
    """Test service methods exist and are callable"""

    @pytest.fixture
    def jwt_service(self):
        return JWTService(AsyncMock(), AsyncMock())

    def test_has_initialize_method(self, jwt_service):
        """Test service has initialize method"""
        assert hasattr(jwt_service, "initialize")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.initialize)

    def test_has_create_access_token_method(self, jwt_service):
        """Test service has create_access_token method"""
        assert hasattr(jwt_service, "create_access_token")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.create_access_token)

    def test_has_create_refresh_token_method(self, jwt_service):
        """Test service has create_refresh_token method"""
        assert hasattr(jwt_service, "create_refresh_token")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.create_refresh_token)

    def test_has_create_tokens_method(self, jwt_service):
        """Test service has create_tokens method"""
        assert hasattr(jwt_service, "create_tokens")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.create_tokens)

    def test_has_verify_token_method(self, jwt_service):
        """Test service has verify_token method"""
        assert hasattr(jwt_service, "verify_token")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.verify_token)

    def test_has_refresh_tokens_method(self, jwt_service):
        """Test service has refresh_tokens method"""
        assert hasattr(jwt_service, "refresh_tokens")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.refresh_tokens)

    def test_has_revoke_token_method(self, jwt_service):
        """Test service has revoke_token method"""
        assert hasattr(jwt_service, "revoke_token")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.revoke_token)

    def test_has_revoke_all_tokens_method(self, jwt_service):
        """Test service has revoke_all_tokens method"""
        assert hasattr(jwt_service, "revoke_all_tokens")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.revoke_all_tokens)

    def test_has_get_public_jwks_method(self, jwt_service):
        """Test service has get_public_jwks method"""
        assert hasattr(jwt_service, "get_public_jwks")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.get_public_jwks)

    def test_has_rotate_keys_method(self, jwt_service):
        """Test service has rotate_keys method"""
        assert hasattr(jwt_service, "rotate_keys")
        import asyncio

        assert asyncio.iscoroutinefunction(jwt_service.rotate_keys)
