import pytest

pytestmark = pytest.mark.asyncio

"""
Integration tests for health and status endpoints
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from app.main import app


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_endpoint_success(self, test_client):
        """Test health endpoint returns success."""
        response = await test_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_ready_endpoint_all_services_healthy(self, test_client):
        """Test ready endpoint when all services are healthy."""
        with patch("app.main.get_database_health") as mock_db_health, patch(
            "app.main.get_redis_client"
        ) as mock_redis_client:
            # Mock successful database health check
            mock_db_health.return_value = {"healthy": True}

            # Mock successful Redis connection
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.close = AsyncMock()
            mock_redis_client.return_value = mock_redis

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "ready"
            assert data["database"]["healthy"] is True
            assert data["redis"] is True

    @pytest.mark.asyncio
    async def test_ready_endpoint_database_unhealthy(self, test_client):
        """Test ready endpoint when database is unhealthy."""
        with patch("app.main.get_database_health") as mock_db_health, patch(
            "app.main.get_redis_client"
        ) as mock_redis_client:
            # Mock failed database health check
            mock_db_health.side_effect = Exception("Database connection failed")

            # Mock successful Redis connection
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.close = AsyncMock()
            mock_redis_client.return_value = mock_redis

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["database"]["healthy"] is False
            assert data["redis"] is True

    @pytest.mark.asyncio
    async def test_ready_endpoint_redis_unhealthy(self, test_client):
        """Test ready endpoint when Redis is unhealthy."""
        with patch("app.main.get_database_health") as mock_db_health, patch(
            "app.main.get_redis_client"
        ) as mock_redis_client:
            # Mock successful database health check
            mock_db_health.return_value = {"healthy": True}

            # Mock failed Redis connection
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=Exception("Redis connection failed"))
            mock_redis.close = AsyncMock()
            mock_redis_client.return_value = mock_redis

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["database"]["healthy"] is True
            assert data["redis"] is False

    @pytest.mark.asyncio
    async def test_ready_endpoint_all_services_unhealthy(self, test_client):
        """Test ready endpoint when all services are unhealthy."""
        with patch("app.main.get_database_health") as mock_db_health, patch(
            "app.main.get_redis_client"
        ) as mock_redis_client:
            # Mock failed database health check
            mock_db_health.side_effect = Exception("Database connection failed")

            # Mock failed Redis connection
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=Exception("Redis connection failed"))
            mock_redis.close = AsyncMock()
            mock_redis_client.return_value = mock_redis

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["database"]["healthy"] is False
            assert data["redis"] is False

    @pytest.mark.asyncio
    async def test_ready_endpoint_no_redis_client(self, test_client):
        """Test ready endpoint when Redis client is None."""
        with patch("app.main.get_database_health") as mock_db_health, patch(
            "app.main.get_redis_client"
        ) as mock_redis_client:
            # Mock successful database health check
            mock_db_health.return_value = {"healthy": True}

            # Mock get_redis_client returning None or raising exception
            mock_redis_client.side_effect = Exception("Redis not available")

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["database"]["healthy"] is True
            assert data["redis"] is False


class TestOpenIDEndpoints:
    """Test OpenID Connect endpoints."""

    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_openid_configuration(self, test_client):
        """Test OpenID Connect configuration endpoint."""
        response = await test_client.get("/.well-known/openid-configuration")

        assert response.status_code == 200
        data = response.json()

        # Check required OpenID Connect fields
        required_fields = [
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
            "response_types_supported",
            "subject_types_supported",
            "id_token_signing_alg_values_supported",
            "scopes_supported",
            "token_endpoint_auth_methods_supported",
            "claims_supported",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check specific values
        assert data["issuer"] == "https://janua.dev"
        assert "code" in data["response_types_supported"]
        assert "public" in data["subject_types_supported"]
        assert "RS256" in data["id_token_signing_alg_values_supported"]
        assert "openid" in data["scopes_supported"]
        assert "profile" in data["scopes_supported"]
        assert "email" in data["scopes_supported"]

        # Check endpoint URLs are properly formatted
        base_url = "https://janua.dev"  # Should match settings.BASE_URL
        assert data["authorization_endpoint"] == f"{base_url}/auth/authorize"
        assert data["token_endpoint"] == f"{base_url}/auth/token"
        assert data["userinfo_endpoint"] == f"{base_url}/auth/userinfo"
        assert data["jwks_uri"] == f"{base_url}/.well-known/jwks.json"

    @pytest.mark.asyncio
    async def test_jwks_endpoint(self, test_client):
        """Test JWKS endpoint."""
        response = await test_client.get("/.well-known/jwks.json")

        assert response.status_code == 200
        data = response.json()

        # Should return valid JWKS structure
        assert "keys" in data
        assert isinstance(data["keys"], list)

        # For now, keys array can be empty (simplified implementation)
        # In production, this would contain actual public keys

    @pytest.mark.asyncio
    async def test_openid_configuration_with_custom_base_url(self, test_client):
        """Test OpenID configuration with custom BASE_URL."""
        with patch("app.main.settings") as mock_settings:
            mock_settings.BASE_URL = "https://custom.domain.com"
            mock_settings.JWT_ISSUER = "https://custom.domain.com"

            response = await test_client.get("/.well-known/openid-configuration")

            assert response.status_code == 200
            data = response.json()

            # Endpoints should use custom base URL
            base_url = "https://custom.domain.com"
            assert data["authorization_endpoint"] == f"{base_url}/auth/authorize"
            assert data["token_endpoint"] == f"{base_url}/auth/token"
            assert data["userinfo_endpoint"] == f"{base_url}/auth/userinfo"
            assert data["jwks_uri"] == f"{base_url}/.well-known/jwks.json"

    @pytest.mark.asyncio
    async def test_openid_configuration_empty_base_url(self, test_client):
        """Test OpenID configuration with empty BASE_URL fallback."""
        with patch("app.main.settings") as mock_settings:
            mock_settings.BASE_URL = ""
            mock_settings.JWT_ISSUER = "https://janua.dev"

            response = await test_client.get("/.well-known/openid-configuration")

            assert response.status_code == 200
            data = response.json()

            # Should fallback to default
            fallback_url = "https://api.janua.dev"
            assert data["authorization_endpoint"] == f"{fallback_url}/auth/authorize"


class TestTestEndpoints:
    """Test debugging/test endpoints."""

    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_test_endpoint(self, test_client):
        """Test the simple test endpoint."""
        response = await test_client.get("/test")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "test endpoint working"
        assert data["auth_router_included"] is True

    @pytest.mark.asyncio
    async def test_test_json_endpoint(self, test_client):
        """Test the JSON test endpoint."""
        test_data = {"test": "data", "number": 42, "array": [1, 2, 3], "nested": {"key": "value"}}

        response = await test_client.post("/test-json", json=test_data)

        assert response.status_code == 200
        data = response.json()

        assert data["received"] == test_data

    @pytest.mark.asyncio
    async def test_test_json_endpoint_empty_data(self, test_client):
        """Test JSON endpoint with empty data."""
        response = await test_client.post("/test-json", json={})

        assert response.status_code == 200
        data = response.json()

        assert data["received"] == {}

    @pytest.mark.asyncio
    async def test_test_json_endpoint_invalid_json(self, test_client):
        """Test JSON endpoint with invalid JSON."""
        response = await test_client.post(
            "/test-json", content="invalid json", headers={"content-type": "application/json"}
        )

        # FastAPI should return 422 for invalid JSON
        assert response.status_code == 422
