"""
Comprehensive JWT Service Test Suite
Targeting 95%+ coverage - streamlined and focused on actual implementation
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from jose import jwt

from app.config import settings
from app.exceptions import AuthenticationError, TokenError
from app.services.jwt_service import JWTService

pytestmark = pytest.mark.asyncio


class TestJWTServiceBasics:
    """Test basic JWT service functionality"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)  # Default: not blacklisted
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_service_properties(self, jwt_service):
        """Test service has correct properties"""
        assert jwt_service.private_key == settings.JWT_SECRET_KEY
        assert jwt_service.public_key == settings.JWT_SECRET_KEY
        assert jwt_service.algorithm == settings.JWT_ALGORITHM

    async def test_initialize_loads_keys(self, jwt_service, mock_db):
        """Test initialize method"""
        mock_db.fetchrow = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock()

        await jwt_service.initialize()

        assert mock_db.fetchrow.called

    async def test_create_access_token_basic(self, jwt_service):
        """Test creating basic access token"""
        jwt_service.redis.setex = AsyncMock()

        token = await jwt_service.create_access_token(identity_id="user-123")

        assert isinstance(token, str)
        assert len(token) > 0
        assert jwt_service.redis.setex.called

    async def test_create_access_token_with_claims(self, jwt_service):
        """Test creating access token with additional claims"""
        jwt_service.redis.setex = AsyncMock()

        token = await jwt_service.create_access_token(
            identity_id="user-123", additional_claims={"role": "admin"}
        )

        # Decode and verify
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "admin"
        assert decoded["type"] == "access"

    async def test_create_refresh_token_basic(self, jwt_service):
        """Test creating basic refresh token"""
        jwt_service.redis.setex = AsyncMock()

        token = await jwt_service.create_refresh_token(identity_id="user-456")

        assert isinstance(token, str)
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        assert decoded["type"] == "refresh"

    async def test_create_tokens_with_tenant(self, jwt_service):
        """Test creating token pair with tenant ID"""
        jwt_service.redis.setex = AsyncMock()

        # Ensure keys are set for token creation
        jwt_service._private_key = settings.JWT_SECRET_KEY
        jwt_service._public_key = settings.JWT_SECRET_KEY
        jwt_service._kid = "test-kid"

        tokens = await jwt_service.create_tokens(identity_id="user-789", tenant_id="tenant-123")

        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "Bearer"


class TestTokenVerification:
    """Test token verification functionality"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.get = AsyncMock(return_value=None)
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        service = JWTService(mock_db, mock_redis)
        # Mock the key properties
        service._public_key = settings.JWT_SECRET_KEY
        service._private_key = settings.JWT_SECRET_KEY
        return service

    async def test_verify_valid_token(self, jwt_service):
        """Test verifying a valid token"""
        jwt_service.redis.setex = AsyncMock()

        # Mock Redis to return proper values for different keys
        async def redis_get_side_effect(key):
            if key.startswith("revoked:"):
                return None  # Not revoked
            if key.startswith("jti:"):
                return b"1"  # JTI exists
            return None

        jwt_service.redis.get = AsyncMock(side_effect=redis_get_side_effect)

        # Create a token
        token = await jwt_service.create_access_token(identity_id="user-123")

        # Verify it
        claims = await jwt_service.verify_token(token)

        assert claims["sub"] == "user-123"
        assert claims["type"] == "access"

    async def test_verify_wrong_type(self, jwt_service):
        """Test verifying token with wrong type"""
        jwt_service.redis.setex = AsyncMock()
        jwt_service.redis.get = AsyncMock(return_value=b"1")

        # Create refresh token
        token = await jwt_service.create_refresh_token(identity_id="user-123")

        # Try to verify as access token
        with pytest.raises(TokenError, match="Invalid token type"):
            await jwt_service.verify_token(token, token_type="access")

    async def test_verify_revoked_token(self, jwt_service):
        """Test verifying a revoked token"""
        jwt_service.redis.setex = AsyncMock()

        # Create token
        token = await jwt_service.create_access_token(identity_id="user-123")

        # Mock as revoked
        async def redis_get(key):
            if "revoked:" in key:
                return b"1"  # Revoked
            return b"1"  # JTI exists

        jwt_service.redis.get = AsyncMock(side_effect=redis_get)

        with pytest.raises(TokenError, match="revoked"):
            await jwt_service.verify_token(token)

    async def test_verify_expired_token(self, jwt_service):
        """Test verifying an expired token"""
        jwt_service.redis.setex = AsyncMock()

        # Create expired token
        token = await jwt_service.create_access_token(
            identity_id="user-123", expires_delta=timedelta(seconds=-10)
        )

        # Should raise AuthenticationError (wraps JWTError)
        with pytest.raises(AuthenticationError):
            await jwt_service.verify_token(token)

    async def test_verify_malformed_token(self, jwt_service):
        """Test verifying malformed token"""
        with pytest.raises((TokenError, AuthenticationError)):
            await jwt_service.verify_token("not.a.valid.token")


class TestTokenRevocation:
    """Test token revocation"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_revoke_token(self, jwt_service):
        """Test revoking a single token"""
        jwt_service.redis.setex = AsyncMock()

        await jwt_service.revoke_token("token-string", "jti-123")

        # Verify Redis was called
        assert jwt_service.redis.setex.called
        call_args = jwt_service.redis.setex.call_args[0]
        assert "jti-123" in call_args[0]

    async def test_revoke_all_tokens(self, jwt_service, mock_db):
        """Test revoking all user tokens"""
        # Mock database to return no sessions
        mock_db.fetch = AsyncMock(return_value=[])

        await jwt_service.revoke_all_tokens("user-123")

        # Should query database for sessions
        assert mock_db.fetch.called

    async def test_is_token_blacklisted_true(self, jwt_service):
        """Test checking blacklisted token"""
        jwt_service.redis.exists = AsyncMock(return_value=1)

        result = await jwt_service.is_token_blacklisted("jti-123")

        assert result is True

    async def test_is_token_blacklisted_false(self, jwt_service):
        """Test checking non-blacklisted token"""
        jwt_service.redis.exists = AsyncMock(return_value=0)

        result = await jwt_service.is_token_blacklisted("jti-456")

        assert result is False

    async def test_is_user_revoked_true(self, jwt_service):
        """Test checking revoked user"""
        jwt_service.redis.exists = AsyncMock(return_value=1)

        result = await jwt_service.is_user_revoked("user-123")

        assert result is True

    async def test_is_user_revoked_false(self, jwt_service):
        """Test checking non-revoked user"""
        jwt_service.redis.exists = AsyncMock(return_value=0)

        result = await jwt_service.is_user_revoked("user-456")

        assert result is False


class TestTokenRefresh:
    """Test token refresh functionality"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.get = AsyncMock(return_value=b"1")  # JTI exists
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        service = JWTService(mock_db, mock_redis)
        service._public_key = settings.JWT_SECRET_KEY
        service._private_key = settings.JWT_SECRET_KEY
        return service

    async def test_refresh_tokens_success(self, jwt_service):
        """Test successful token refresh"""
        jwt_service.redis.setex = AsyncMock()

        # Mock Redis for proper token verification
        async def redis_get_side_effect(key):
            if key.startswith("revoked:"):
                return None  # Not revoked
            if key.startswith("jti:"):
                return b"1"  # JTI exists
            if key.startswith("used:"):
                return None  # Not used yet
            return None

        jwt_service.redis.get = AsyncMock(side_effect=redis_get_side_effect)

        # Create initial refresh token
        old_token = await jwt_service.create_refresh_token(identity_id="user-123")

        # Refresh it
        new_tokens = await jwt_service.refresh_tokens(old_token)

        assert new_tokens.access_token
        assert new_tokens.refresh_token
        assert new_tokens.token_type == "Bearer"

    async def test_refresh_with_access_token_fails(self, jwt_service):
        """Test refresh fails with access token"""
        jwt_service.redis.setex = AsyncMock()

        # Create access token
        access_token = await jwt_service.create_access_token(identity_id="user-123")

        # Try to refresh with access token
        with pytest.raises(TokenError, match="Invalid token type"):
            await jwt_service.refresh_tokens(access_token)


class TestHelperMethods:
    """Test helper methods"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_store_token_claims(self, jwt_service):
        """Test storing token claims"""
        jwt_service.redis.setex = AsyncMock()

        claims = {"sub": "user-123", "role": "admin"}
        await jwt_service.store_token_claims("jti-123", claims, ttl=3600)

        jwt_service.redis.setex.assert_called_once()
        call_args = jwt_service.redis.setex.call_args[0]
        assert "jti-123" in call_args[0]
        assert call_args[1] == 3600

    async def test_get_token_claims_found(self, jwt_service):
        """Test retrieving stored claims"""
        claims_data = json.dumps({"sub": "user-456", "role": "user"})
        jwt_service.redis.get = AsyncMock(return_value=claims_data.encode())

        claims = await jwt_service.get_token_claims("jti-456")

        assert claims["sub"] == "user-456"
        assert claims["role"] == "user"

    async def test_get_token_claims_not_found(self, jwt_service):
        """Test retrieving non-existent claims"""
        jwt_service.redis.get = AsyncMock(return_value=None)

        claims = await jwt_service.get_token_claims("jti-999")

        assert claims is None


class TestEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def jwt_service(self, mock_db, mock_redis):
        return JWTService(mock_db, mock_redis)

    async def test_create_token_redis_failure(self, jwt_service):
        """Test token creation handles Redis failure"""
        jwt_service.redis.setex = AsyncMock(side_effect=Exception("Redis error"))

        with pytest.raises(Exception, match="Redis error"):
            await jwt_service.create_access_token("user-123")

    async def test_create_token_empty_identity(self, jwt_service):
        """Test creating token with empty identity"""
        jwt_service.redis.setex = AsyncMock()

        token = await jwt_service.create_access_token(identity_id="")

        assert isinstance(token, str)

    async def test_custom_expiry_delta(self, jwt_service):
        """Test token with custom expiry"""
        jwt_service.redis.setex = AsyncMock()

        token = await jwt_service.create_access_token(
            identity_id="user-123", expires_delta=timedelta(hours=2)
        )

        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False, "verify_exp": False},
        )

        exp_time = datetime.fromtimestamp(decoded["exp"])
        iat_time = datetime.fromtimestamp(decoded["iat"])
        delta = exp_time - iat_time

        # Should be approximately 2 hours
        assert abs(delta.total_seconds() - 7200) < 10

    async def test_verify_skip_expiry(self, jwt_service):
        """Test verifying with expiry check disabled"""
        jwt_service.redis.setex = AsyncMock()

        # Mock Redis for proper verification
        async def redis_get_side_effect(key):
            if key.startswith("revoked:"):
                return None  # Not revoked
            if key.startswith("jti:"):
                return b"1"  # JTI exists
            return None

        jwt_service.redis.get = AsyncMock(side_effect=redis_get_side_effect)
        jwt_service._public_key = settings.JWT_SECRET_KEY

        # Create expired token
        token = await jwt_service.create_access_token(
            identity_id="user-123", expires_delta=timedelta(seconds=-10)
        )

        # Should not raise when verify_exp=False
        claims = await jwt_service.verify_token(token, verify_exp=False)
        assert claims["sub"] == "user-123"
