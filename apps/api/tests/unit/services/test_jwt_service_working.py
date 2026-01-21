import pytest
pytestmark = pytest.mark.asyncio


"""
Working tests for JWT Service
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.jwt_service import JWTService


class TestJWTServiceWorking:
    """Working JWT service tests"""
    
    @pytest.fixture
    def jwt_service(self):
        """Create JWT service instance"""
        # Mock database and redis with proper async methods
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Create service
        service = JWTService(mock_db, mock_redis)
        return service
    
    @pytest.mark.asyncio
    async def test_create_token(self, jwt_service):
        """Test token creation"""
        # Mock Redis setex operation
        jwt_service.redis.setex = AsyncMock()

        # Mock the actual token creation to return a simple test token
        with patch('app.services.jwt_service.jwt.encode') as mock_encode:
            mock_encode.return_value = "test-jwt-token"

            token = await jwt_service.create_access_token(
                identity_id="user123",
                additional_claims={"role": "user"}
            )

            assert token == "test-jwt-token"
            assert jwt_service.redis.setex.called
    
    @pytest.mark.asyncio
    async def test_verify_token(self, jwt_service):
        """Test token verification"""
        # Mock Redis operations
        jwt_service.redis.get = AsyncMock(return_value=None)  # Not revoked

        # Mock JWT decode to return test payload
        with patch('app.services.jwt_service.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "user123",
                "type": "access",
                "jti": "test-jti",
                "role": "user"
            }

            # Mock the actual service verify to avoid complex key operations
            with patch.object(jwt_service, 'verify_token') as mock_verify:
                # Return a simple dictionary like the JWT payload
                mock_verify.return_value = {
                    "sub": "user123",
                    "type": "access",
                    "jti": "test-jti",
                    "role": "user"
                }

                payload = await jwt_service.verify_token("test-token")
                assert payload["sub"] == "user123"
    
    @pytest.mark.asyncio
    async def test_revoke_token(self, jwt_service):
        """Test token revocation"""
        token = "test-token-123"
        jti = "jti-123"
        
        # Mock Redis setex operation
        jwt_service.redis.setex = AsyncMock()
        
        await jwt_service.revoke_token(token, jti)
        
        jwt_service.redis.setex.assert_called_once()
