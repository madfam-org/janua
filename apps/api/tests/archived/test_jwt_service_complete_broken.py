import pytest
pytestmark = pytest.mark.asyncio


"""
Complete unit tests for JWTService to achieve 100% coverage
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.jwt_service import JWTService
from app.exceptions import TokenError


class TestJWTServiceInitialization:
    """Test JWT service initialization and setup."""

    def test_jwt_service_init(self):
        """Test JWT service initialization."""
        db = Mock()
        redis = Mock()
        service = JWTService(db, redis)

        assert service.db == db
        assert service.redis == redis
        assert service._private_key is None
        assert service._public_key is None
        assert service._kid is None

    @pytest.mark.asyncio
    async def test_initialize_with_existing_keys(self):
        """Test initialization with existing keys in database."""
        db = Mock()
        redis = Mock()
        service = JWTService(db, redis)

        # Mock existing key data
        _key_data = {
            'kid': 'test-kid-123',
            'private_key': 'test-private-key',
            'public_key': 'test-public-key'
        }

        with patch.object(service, '_load_or_generate_keys') as mock_load:
            mock_load.return_value = None

            await service.initialize()

            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_existing_keys(self):
        """Test loading existing keys from database."""
        db = Mock()
        redis = Mock()
        service = JWTService(db, redis)

        mock_key_data = {
            'kid': 'existing-kid',
            'private_key': 'existing-private-key',
            'public_key': 'existing-public-key'
        }

        db.fetchrow = AsyncMock(return_value=mock_key_data)

        with patch('app.services.jwt_service.serialization') as mock_serialization:
            mock_private_key = MagicMock()
            mock_public_key = MagicMock()

            mock_serialization.load_pem_private_key.return_value = mock_private_key
            mock_serialization.load_pem_public_key.return_value = mock_public_key

            await service._load_or_generate_keys()

            assert service._kid == 'existing-kid'
            assert service._private_key == mock_private_key
            assert service._public_key == mock_public_key

    @pytest.mark.asyncio
    async def test_generate_new_keys(self):
        """Test generating new keys when none exist."""
        db = Mock()
        redis = Mock()
        service = JWTService(db, redis)

        db.fetchrow = AsyncMock(return_value=None)
        db.execute = AsyncMock()

        with patch('app.services.jwt_service.rsa.generate_private_key') as mock_rsa, \
             patch('app.services.jwt_service.uuid4') as mock_uuid:

            mock_uuid.return_value.hex = 'new-kid-123'
            mock_private_key = MagicMock()
            mock_public_key = MagicMock()

            mock_private_key.public_key.return_value = mock_public_key
            mock_private_key.private_bytes.return_value = b'private-key-pem'
            mock_public_key.public_bytes.return_value = b'public-key-pem'

            mock_rsa.return_value = mock_private_key

            await service._load_or_generate_keys()

            assert service._kid == 'new-kid-123'
            assert service._private_key == mock_private_key
            assert service._public_key == mock_public_key

            db.execute.assert_called_once()


class TestTokenCreation:
    """Test JWT token creation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock()
        self.redis = Mock()
        self.service = JWTService(self.db, self.redis)
        self.service._private_key = Mock()
        self.service._public_key = Mock()
        self.service._kid = 'test-kid'

    @pytest.mark.asyncio
    async def test_create_access_token(self):
        """Test creating access token."""
        user_id = str(uuid4())
        organization_id = str(uuid4())

        with patch('app.services.jwt_service.jwt.encode') as mock_encode:
            mock_encode.return_value = 'encoded-token'

            token = await self.service.create_access_token(
                user_id=user_id,
                organization_id=organization_id,
                scopes=['read', 'write']
            )

            assert token == 'encoded-token'
            mock_encode.assert_called_once()

            # Check the payload structure
            call_args = mock_encode.call_args
            payload = call_args[0][0]

            assert payload['sub'] == user_id
            assert payload['org'] == organization_id
            assert payload['scopes'] == ['read', 'write']
            assert 'exp' in payload
            assert 'iat' in payload
            assert 'jti' in payload

    @pytest.mark.asyncio
    async def test_create_refresh_token(self):
        """Test creating refresh token."""
        user_id = str(uuid4())

        with patch('app.services.jwt_service.jwt.encode') as mock_encode:
            mock_encode.return_value = 'refresh-token'

            token = await self.service.create_refresh_token(user_id=user_id)

            assert token == 'refresh-token'
            mock_encode.assert_called_once()

            # Check the payload structure
            call_args = mock_encode.call_args
            payload = call_args[0][0]

            assert payload['sub'] == user_id
            assert payload['type'] == 'refresh'
            assert 'exp' in payload
            assert 'iat' in payload

    @pytest.mark.asyncio
    async def test_create_token_with_custom_expiry(self):
        """Test creating token with custom expiry."""
        user_id = str(uuid4())
        custom_expiry = timedelta(hours=2)

        with patch('app.services.jwt_service.jwt.encode') as mock_encode:
            mock_encode.return_value = 'custom-token'

            token = await self.service.create_access_token(
                user_id=user_id,
                expires_delta=custom_expiry
            )

            assert token == 'custom-token'

            # Check expiry is set correctly
            call_args = mock_encode.call_args
            payload = call_args[0][0]
            exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
            expected_exp = datetime.now(timezone.utc) + custom_expiry

            # Allow for some time difference in test execution
            assert abs((exp_time - expected_exp).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_create_token_stores_claims(self):
        """Test that token creation stores claims in database."""
        user_id = str(uuid4())

        self.db.execute = AsyncMock()

        with patch('app.services.jwt_service.jwt.encode') as mock_encode:
            mock_encode.return_value = 'test-token'

            await self.service.create_access_token(user_id=user_id)

            self.db.execute.assert_called_once()


class TestTokenVerification:
    """Test JWT token verification functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock()
        self.redis = Mock()
        self.service = JWTService(self.db, self.redis)
        self.service._private_key = Mock()
        self.service._public_key = Mock()
        self.service._kid = 'test-kid'

    @pytest.mark.asyncio
    async def test_verify_token_valid(self):
        """Test verifying valid token."""
        token = 'valid-token'
        expected_payload = {
            'sub': str(uuid4()),
            'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            'iat': int(datetime.now(timezone.utc).timestamp()),
            'jti': str(uuid4())
        }

        with patch('app.services.jwt_service.jwt.decode') as mock_decode, \
             patch.object(self.service, 'is_token_blacklisted') as mock_blacklisted:

            mock_decode.return_value = expected_payload
            mock_blacklisted.return_value = False

            payload = await self.service.verify_token(token)

            assert payload == expected_payload
            mock_decode.assert_called_once_with(
                token,
                self.service._public_key,
                algorithms=['RS256']
            )

    @pytest.mark.asyncio
    async def test_verify_token_invalid_signature(self):
        """Test verifying token with invalid signature."""
        token = 'invalid-token'

        with patch('app.services.jwt_service.jwt.decode') as mock_decode:
            mock_decode.side_effect = Exception("Invalid signature")

            with pytest.raises(TokenError, match="Invalid token"):
                await self.service.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_expired(self):
        """Test verifying expired token."""
        token = 'expired-token'

        with patch('app.services.jwt_service.jwt.decode') as mock_decode:
            mock_decode.side_effect = Exception("Token has expired")

            with pytest.raises(TokenError, match="Invalid token"):
                await self.service.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_blacklisted(self):
        """Test verifying blacklisted token."""
        token = 'blacklisted-token'
        payload = {
            'sub': str(uuid4()),
            'jti': 'blacklisted-jti'
        }

        with patch('app.services.jwt_service.jwt.decode') as mock_decode, \
             patch.object(self.service, 'is_token_blacklisted') as mock_blacklisted:

            mock_decode.return_value = payload
            mock_blacklisted.return_value = True

            with pytest.raises(TokenError, match="Token has been revoked"):
                await self.service.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_refresh_token(self):
        """Test verifying refresh token."""
        token = 'refresh-token'
        payload = {
            'sub': str(uuid4()),
            'type': 'refresh',
            'exp': int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        }

        with patch('app.services.jwt_service.jwt.decode') as mock_decode, \
             patch.object(self.service, 'is_token_blacklisted') as mock_blacklisted:

            mock_decode.return_value = payload
            mock_blacklisted.return_value = False

            result = await self.service.verify_refresh_token(token)

            assert result == payload

    @pytest.mark.asyncio
    async def test_verify_refresh_token_wrong_type(self):
        """Test verifying refresh token with wrong type."""
        token = 'access-token'
        payload = {
            'sub': str(uuid4()),
            'type': 'access'
        }

        with patch('app.services.jwt_service.jwt.decode') as mock_decode, \
             patch.object(self.service, 'is_token_blacklisted') as mock_blacklisted:

            mock_decode.return_value = payload
            mock_blacklisted.return_value = False

            with pytest.raises(TokenError, match="Invalid refresh token"):
                await self.service.verify_refresh_token(token)


class TestTokenRevocation:
    """Test JWT token revocation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock()
        self.redis = Mock()
        self.service = JWTService(self.db, self.redis)

    @pytest.mark.asyncio
    async def test_revoke_token_by_jti(self):
        """Test revoking token by JTI."""
        jti = str(uuid4())

        self.redis.sadd = AsyncMock()
        self.redis.expire = AsyncMock()

        await self.service.revoke_token(jti)

        self.redis.sadd.assert_called_once_with('blacklisted_tokens', jti)
        self.redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_token_with_parsed_payload(self):
        """Test revoking token with parsed payload."""
        token = 'test-token'

        with patch.object(self.service, 'decode_token_unsafe') as mock_decode:
            mock_decode.return_value = {'jti': 'test-jti'}
            self.redis.sadd = AsyncMock()
            self.redis.expire = AsyncMock()

            await self.service.revoke_token(token)

            self.redis.sadd.assert_called_once_with('blacklisted_tokens', 'test-jti')

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self):
        """Test revoking all tokens for a user."""
        user_id = str(uuid4())

        self.redis.sadd = AsyncMock()

        await self.service.revoke_all_user_tokens(user_id)

        self.redis.sadd.assert_called_once_with('revoked_users', user_id)

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_true(self):
        """Test checking if token is blacklisted (true case)."""
        jti = 'blacklisted-jti'

        self.redis.sismember = AsyncMock(return_value=True)

        result = await self.service.is_token_blacklisted(jti)

        assert result is True
        self.redis.sismember.assert_called_once_with('blacklisted_tokens', jti)

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_false(self):
        """Test checking if token is blacklisted (false case)."""
        jti = 'valid-jti'

        self.redis.sismember = AsyncMock(return_value=False)

        result = await self.service.is_token_blacklisted(jti)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_user_revoked_true(self):
        """Test checking if user tokens are revoked (true case)."""
        user_id = str(uuid4())

        self.redis.sismember = AsyncMock(return_value=True)

        result = await self.service.is_user_revoked(user_id)

        assert result is True
        self.redis.sismember.assert_called_once_with('revoked_users', user_id)

    @pytest.mark.asyncio
    async def test_is_user_revoked_false(self):
        """Test checking if user tokens are revoked (false case)."""
        user_id = str(uuid4())

        self.redis.sismember = AsyncMock(return_value=False)

        result = await self.service.is_user_revoked(user_id)

        assert result is False


class TestJWKS:
    """Test JWKS (JSON Web Key Set) functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock()
        self.redis = Mock()
        self.service = JWTService(self.db, self.redis)
        self.service._kid = 'test-kid'
        self.service._public_key = Mock()

    def test_get_public_jwks_with_keys(self):
        """Test getting JWKS when keys exist."""
        mock_public_numbers = AsyncMock()
        mock_public_numbers.n = 12345
        mock_public_numbers.e = 65537

        self.service._public_key.public_numbers.return_value = mock_public_numbers

        with patch('app.services.jwt_service.jwk.RSAKey') as mock_rsa_key:
            mock_key_dict = {
                'kty': 'RSA',
                'kid': 'test-kid',
                'use': 'sig',
                'n': 'base64-n',
                'e': 'base64-e'
            }
            mock_rsa_key.return_value.to_dict.return_value = mock_key_dict

            jwks = self.service.get_public_jwks()

            assert 'keys' in jwks
            assert len(jwks['keys']) == 1
            assert jwks['keys'][0] == mock_key_dict

    def test_get_public_jwks_no_keys(self):
        """Test getting JWKS when no keys exist."""
        self.service._public_key = None

        jwks = self.service.get_public_jwks()

        assert jwks == {'keys': []}


class TestUtilityMethods:
    """Test utility methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock()
        self.redis = Mock()
        self.service = JWTService(self.db, self.redis)

    def test_decode_token_unsafe(self):
        """Test unsafe token decoding."""
        token = 'test-token'
        expected_payload = {'sub': 'user-123', 'exp': 1234567890}

        with patch('app.services.jwt_service.jwt.decode') as mock_decode:
            mock_decode.return_value = expected_payload

            payload = self.service.decode_token_unsafe(token)

            assert payload == expected_payload
            mock_decode.assert_called_once_with(
                token,
                options={"verify_signature": False}
            )

    def test_decode_token_unsafe_invalid(self):
        """Test unsafe token decoding with invalid token."""
        token = 'invalid-token'

        with patch('app.services.jwt_service.jwt.decode') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            payload = self.service.decode_token_unsafe(token)

            assert payload is None

    @pytest.mark.asyncio
    async def test_get_token_ttl_valid(self):
        """Test getting TTL for valid token."""
        jti = 'test-jti'

        self.redis.ttl = AsyncMock(return_value=3600)

        ttl = await self.service.get_token_ttl(jti)

        assert ttl == 3600
        self.redis.ttl.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_token_ttl_expired(self):
        """Test getting TTL for expired token."""
        jti = 'expired-jti'

        self.redis.ttl = AsyncMock(return_value=-1)

        ttl = await self.service.get_token_ttl(jti)

        assert ttl == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self):
        """Test cleaning up expired tokens."""
        self.redis.eval = AsyncMock()

        await self.service.cleanup_expired_tokens()

        self.redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_sessions_count(self):
        """Test getting active sessions count."""
        user_id = str(uuid4())

        self.redis.scard = AsyncMock(return_value=5)

        count = await self.service.get_active_sessions_count(user_id)

        assert count == 5
        self.redis.scard.assert_called_once()


class TestErrorHandling:
    """Test error handling scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock()
        self.redis = Mock()
        self.service = JWTService(self.db, self.redis)

    @pytest.mark.asyncio
    async def test_redis_connection_error(self):
        """Test handling Redis connection errors."""
        self.redis.sadd = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Should not raise exception, but log error
        await self.service.revoke_token('test-jti')

    @pytest.mark.asyncio
    async def test_database_error_during_key_generation(self):
        """Test handling database errors during key generation."""
        self.db.fetchrow = AsyncMock(return_value=None)
        self.db.execute = AsyncMock(side_effect=Exception("Database error"))

        with patch('app.services.jwt_service.rsa.generate_private_key'):
            with pytest.raises(Exception, match="Database error"):
                await self.service._load_or_generate_keys()

    @pytest.mark.asyncio
    async def test_invalid_private_key_format(self):
        """Test handling invalid private key format."""
        self.db.fetchrow = AsyncMock(return_value={
            'kid': 'test-kid',
            'private_key': 'invalid-key-format',
            'public_key': 'invalid-public-key'
        })

        with patch('app.services.jwt_service.serialization.load_pem_private_key') as mock_load:
            mock_load.side_effect = Exception("Invalid key format")

            with pytest.raises(Exception, match="Invalid key format"):
                await self.service._load_or_generate_keys()