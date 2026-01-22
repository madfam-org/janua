import pytest

pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for JWT service
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError

from app.exceptions import TokenError
from app.services.jwt_service import JWTService


class TestJWTServiceInitialization:
    """Test JWT service initialization."""

    @pytest.mark.asyncio
    async def test_init_creates_service(self):
        """Test JWT service initialization."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        service = JWTService(mock_db, mock_redis)

        assert service.db == mock_db
        assert service.redis == mock_redis
        assert service._private_key is None
        assert service._public_key is None
        assert service._kid is None

    @pytest.mark.asyncio
    async def test_initialize_loads_existing_keys(self):
        """Test initialization loads existing keys from database."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock existing key data
        key_data = {
            "kid": "test_key_id",
            "private_key": "private_key_pem",
            "public_key": "public_key_pem",
        }
        mock_db.fetchrow.return_value = key_data

        with patch.object(JWTService, "_deserialize_keys") as mock_deserialize:
            service = JWTService(mock_db, mock_redis)
            await service.initialize()

            mock_db.fetchrow.assert_called_once()
            mock_deserialize.assert_called_once_with(
                key_data["private_key"], key_data["public_key"]
            )
            assert service._kid == "test_key_id"


class TestTokenCreation:
    """Test JWT token creation."""

    @pytest.mark.asyncio
    async def test_create_access_token(self):
        """Test access token creation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)
        service._private_key = MagicMock()
        service._kid = "test_key_id"

        # Test data - use real values instead of MagicMock
        identity_id = "user_123"
        additional_claims = {
            "email": "test@example.com",
            "tenant_id": "tenant_123",
            "scopes": ["read", "write"],
        }

        expected_token = "jwt_access_token"

        # Mock Redis setex for token storage
        mock_redis.setex = AsyncMock()

        with patch("jose.jwt.encode", return_value=expected_token) as mock_encode:
            token = await service.create_access_token(identity_id, additional_claims)

            assert token == expected_token
            mock_encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_refresh_token(self):
        """Test refresh token creation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)
        service._private_key = MagicMock()
        service._kid = "test_key_id"

        user_id = "user_123"
        session_id = "session_123"
        expected_token = "jwt_refresh_token"

        with patch("jose.jwt.encode", return_value=expected_token) as mock_encode:
            token = await service.create_refresh_token(user_id, session_id)

            assert token == expected_token
            mock_encode.assert_called_once()


class TestTokenValidation:
    """Test JWT token validation."""

    @pytest.mark.asyncio
    async def test_verify_access_token_valid(self):
        """Test verification of valid access token."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)
        service._public_key = MagicMock()

        token = "valid_access_token"
        expected_claims = {
            "sub": "user_123",
            "email": "test@example.com",
            "type": "access",
            "exp": (datetime.utcnow() + timedelta(minutes=15)).timestamp(),
        }

        with (
            patch("jose.jwt.decode", return_value=expected_claims) as mock_decode,
            patch("app.models.TokenClaims") as mock_token_claims,
        ):
            mock_redis.get.return_value = None  # Token not blacklisted
            mock_claims_instance = MagicMock()
            mock_token_claims.return_value = mock_claims_instance

            claims = await service.verify_token(token)

            assert claims == mock_claims_instance
            mock_decode.assert_called_once()
            mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_access_token_invalid(self):
        """Test verification of invalid access token."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)
        service._public_key = MagicMock()

        token = "invalid_token"

        with patch("jose.jwt.decode", side_effect=JWTError("Invalid token")):
            with pytest.raises(TokenError, match="Invalid token"):
                await service.verify_token(token)


class TestTokenRevocation:
    """Test token revocation functionality."""

    @pytest.mark.asyncio
    async def test_revoke_token(self):
        """Test token revocation."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)

        token = "token_to_revoke"
        token_id = "token_123"
        expiry = datetime.utcnow() + timedelta(minutes=15)

        with patch.object(service, "_decode_token_unsafe") as mock_decode:
            mock_decode.return_value = {"jti": token_id, "exp": expiry.timestamp()}

            await service.revoke_token(token, token_id)

            mock_redis.setex.assert_called_once()


class TestJWKS:
    """Test JWKS (JSON Web Key Set) functionality."""

    @pytest.mark.asyncio
    async def test_get_public_jwks(self):
        """Test JWKS endpoint response."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)
        service._public_key = MagicMock()
        service._kid = "test_key_id"

        # Mock JWK conversion
        mock_jwk_dict = {
            "kty": "RSA",
            "use": "sig",
            "kid": "test_key_id",
            "n": "modulus",
            "e": "AQAB",
        }

        with patch("jose.jwk.construct") as mock_construct:
            mock_jwk = MagicMock()
            mock_jwk.to_dict.return_value = mock_jwk_dict
            mock_construct.return_value = mock_jwk

            jwks = await service.get_public_jwks()

            assert "keys" in jwks
            assert len(jwks["keys"]) == 1
            assert jwks["keys"][0] == mock_jwk_dict

    @pytest.mark.asyncio
    async def test_get_public_jwks_no_keys(self):
        """Test JWKS endpoint when no keys are available."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        service = JWTService(mock_db, mock_redis)
        service._public_key = None

        jwks = await service.get_public_jwks()

        assert jwks == {"keys": []}


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_decode_token_unsafe(self):
        """Test unsafe token decoding (without verification)."""
        service = JWTService(AsyncMock(), AsyncMock())

        token = "jwt.token.here"
        expected_payload = {"sub": "user_123", "exp": 1234567890}

        with patch("jose.jwt.get_unverified_claims", return_value=expected_payload) as mock_decode:
            payload = service._decode_token_unsafe(token)

            assert payload == expected_payload
            mock_decode.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_true(self):
        """Test checking if token is blacklisted - blacklisted case."""
        mock_redis = AsyncMock()
        service = JWTService(AsyncMock(), mock_redis)

        token_id = "token_123"
        mock_redis.get.return_value = b"blacklisted"

        is_blacklisted = await service._is_token_blacklisted(token_id)

        assert is_blacklisted is True
        mock_redis.get.assert_called_once_with(f"blacklist:{token_id}")

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_false(self):
        """Test checking if token is blacklisted - not blacklisted case."""
        mock_redis = AsyncMock()
        service = JWTService(AsyncMock(), mock_redis)

        token_id = "token_123"
        mock_redis.get.return_value = None

        is_blacklisted = await service._is_token_blacklisted(token_id)

        assert is_blacklisted is False
        mock_redis.get.assert_called_once_with(f"blacklist:{token_id}")

    def test_get_token_ttl(self):
        """Test calculating token TTL from expiry timestamp."""
        service = JWTService(AsyncMock(), AsyncMock())

        future_timestamp = (datetime.utcnow() + timedelta(minutes=15)).timestamp()

        ttl = service._get_token_ttl(future_timestamp)

        # Should be approximately 15 minutes (900 seconds), allowing for small time diff
        assert 890 <= ttl <= 910
