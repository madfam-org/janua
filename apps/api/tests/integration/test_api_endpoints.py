
pytestmark = pytest.mark.asyncio

"""
Integration tests for API endpoints
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


class TestHealthEndpointsIntegration:
    """Test health and status endpoint integration."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_health_endpoint_integration(self, test_client: AsyncClient):
        """Test health endpoint with realistic conditions."""
        response = await test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert response.headers["content-type"] == "application/json"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_ready_endpoint_healthy_services(self, test_client: AsyncClient):
        """Test readiness endpoint when all services are healthy."""
        with patch('app.main.engine') as mock_engine, \
             patch('app.main.redis_client') as mock_redis:
            
            # Mock successful database connection
            mock_conn = AsyncMock()
            mock_engine.connect.return_value.__aenter__.return_value = mock_conn
            mock_conn.execute.return_value = None
            
            # Mock successful Redis connection
            mock_redis.ping.return_value = True
            
            response = await test_client.get("/ready")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "ready"
            assert data["database"] is True
            assert data["redis"] is True
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_ready_endpoint_degraded_services(self, test_client: AsyncClient):
        """Test readiness endpoint when services are degraded."""
        with patch('app.main.engine') as mock_engine, \
             patch('app.main.redis_client') as mock_redis:
            
            # Mock failed database connection
            mock_engine.connect.side_effect = Exception("DB connection failed")
            
            # Mock failed Redis connection
            mock_redis.ping.side_effect = Exception("Redis connection failed")
            
            response = await test_client.get("/ready")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "degraded"
            assert data["database"] is False
            assert data["redis"] is False


class TestOpenIDEndpointsIntegration:
    """Test OpenID Connect endpoint integration."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_openid_configuration_integration(self, test_client: AsyncClient):
        """Test OpenID configuration endpoint with full validation."""
        response = await test_client.get("/.well-known/openid-configuration")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate required OpenID Connect fields
        required_fields = [
            "issuer",
            "authorization_endpoint", 
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
            "response_types_supported",
            "subject_types_supported",
            "id_token_signing_alg_values_supported"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate URL formats
        url_fields = ["authorization_endpoint", "token_endpoint", "userinfo_endpoint", "jwks_uri"]
        for field in url_fields:
            assert data[field].startswith(("http://", "https://")), f"Invalid URL format for {field}: {data[field]}"
        
        # Validate response types and algorithms
        assert "code" in data["response_types_supported"]
        assert "public" in data["subject_types_supported"]
        assert "RS256" in data["id_token_signing_alg_values_supported"]
        
        # Validate content type
        assert response.headers["content-type"] == "application/json"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_jwks_endpoint_integration(self, test_client: AsyncClient):
        """Test JWKS endpoint with validation."""
        response = await test_client.get("/.well-known/jwks.json")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate JWKS structure
        assert "keys" in data
        assert isinstance(data["keys"], list)
        
        # Validate content type
        assert response.headers["content-type"] == "application/json"


class TestTestEndpointsIntegration:
    """Test debugging/test endpoint integration."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_test_endpoint_integration(self, test_client: AsyncClient):
        """Test the test endpoint with full validation."""
        response = await test_client.get("/test")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "test endpoint working"
        assert "auth_router_included" in data
        assert isinstance(data["auth_router_included"], bool)
        
        # Validate response structure
        assert len(data) >= 2
        assert response.headers["content-type"] == "application/json"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_test_json_endpoint_integration(self, test_client: AsyncClient):
        """Test JSON test endpoint with various payloads."""
        test_cases = [
            {"test": "data", "number": 42},
            {"empty": {}},
            {"nested": {"level1": {"level2": "value"}}},
            {"array": [1, 2, 3, 4, 5]},
            {"unicode": "héllo wörld 🌍"},
            {"boolean": True, "null": None}
        ]
        
        for test_data in test_cases:
            response = await test_client.post("/test-json", json=test_data)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["received"] == test_data
            assert response.headers["content-type"] == "application/json"


class TestMiddlewareIntegration:
    """Test middleware behavior in integration scenarios."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_cors_middleware_integration(self, test_client: AsyncClient):
        """Test CORS middleware with various scenarios."""
        # Test preflight request
        response = await test_client.options("/health")
        assert "access-control-allow-origin" in response.headers
        
        # Test actual request with CORS headers
        response = await test_client.get("/health")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_process_time_header_integration(self, test_client: AsyncClient):
        """Test process time header across different endpoints."""
        endpoints = ["/health", "/ready", "/test", "/.well-known/openid-configuration"]
        
        for endpoint in endpoints:
            response = await test_client.get(endpoint)
            
            assert "x-process-time" in response.headers
            process_time = float(response.headers["x-process-time"])
            assert process_time >= 0
            assert process_time < 10  # Should be reasonably fast
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_trusted_host_middleware_integration(self, test_client: AsyncClient):
        """Test trusted host middleware behavior."""
        # Test with default test client (should be trusted)
        response = await test_client.get("/health")
        assert response.status_code == 200
        
        # Test that middleware is present and configured
        # Note: Specific host rejection testing would require custom client configuration


class TestErrorHandlingIntegration:
    """Test application-wide error handling."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_404_error_handling(self, test_client: AsyncClient):
        """Test 404 error handling for non-existent endpoints."""
        response = await test_client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not Found"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_method_not_allowed_handling(self, test_client: AsyncClient):
        """Test method not allowed error handling."""
        # Try POST on GET-only endpoint
        response = await test_client.post("/health")
        assert response.status_code == 405
        
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Method Not Allowed"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_large_payload_handling(self, test_client: AsyncClient):
        """Test handling of large payloads."""
        # Create a reasonably large payload
        large_data = {"data": "x" * 10000}  # 10KB of data
        
        response = await test_client.post("/test-json", json=large_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["received"] == large_data


class TestSecurityIntegration:
    """Test security-related integration scenarios."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_security_headers_integration(self, test_client: AsyncClient):
        """Test that security headers are properly set."""
        response = await test_client.get("/health")
        
        # Check for important security headers
        headers = response.headers
        
        # CORS headers should be present
        assert "access-control-allow-origin" in headers
        
        # Process time header should be present (indicates middleware is working)
        assert "x-process-time" in headers
        
        # Content type should be properly set
        assert headers["content-type"] == "application/json"
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_auth_endpoint_security(self, test_client: AsyncClient):
        """Test security of authentication endpoints."""
        # Test that protected endpoints require authentication
        protected_endpoints = ["/api/v1/auth/me", "/api/v1/auth/signout"]
        
        for endpoint in protected_endpoints:
            response = await test_client.get(endpoint)
            assert response.status_code == 403
            
            data = response.json()
            assert "Not authenticated" in data["detail"]
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_rate_limiting_security_integration(self, test_client: AsyncClient, mock_redis):
        """Test that rate limiting provides security protection."""
        # Simulate rate limit exceeded scenario
        mock_redis.get.return_value = "100"  # Way over any reasonable limit
        
        signup_data = {"email": "test@example.com", "password": "SecurePassword123!"}
        response = await test_client.post("/api/v1/auth/signup", json=signup_data)
        
        assert response.status_code == 429
        data = response.json()
        assert "Too many" in data["detail"]


class TestPerformanceIntegration:
    """Test performance-related integration scenarios."""
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, test_client: AsyncClient):
        """Test handling of concurrent requests."""
        import asyncio
        
        # Create multiple concurrent requests
        tasks = [
            test_client.get("/health"),
            test_client.get("/ready"),
            test_client.get("/test"),
            test_client.get("/.well-known/openid-configuration"),
            test_client.get("/.well-known/jwks.json")
        ]
        
        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
        
        # All should have process time headers
        for response in responses:
            assert "x-process-time" in response.headers
            process_time = float(response.headers["x-process-time"])
            assert process_time >= 0
    
    @pytest_asyncio.fixture
    @pytest.mark.asyncio
    async def test_response_time_consistency(self, test_client: AsyncClient):
        """Test that response times are consistent."""
        response_times = []
        
        # Make multiple requests to the same endpoint
        for _ in range(5):
            response = await test_client.get("/health")
            assert response.status_code == 200
            
            process_time = float(response.headers["x-process-time"])
            response_times.append(process_time)
        
        # Calculate variance to ensure consistency
        avg_time = sum(response_times) / len(response_times)
        
        # All response times should be reasonably close to average
        for time in response_times:
            assert abs(time - avg_time) < 1.0  # Within 1 second variance