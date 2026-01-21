"""Tests for the main Janua client."""

import os
import pytest
from unittest.mock import Mock, patch
from janua import JanuaClient, create_client
from janua.exceptions import ConfigurationError


class TestJanuaClient:
    """Test the main JanuaClient class."""
    
    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = JanuaClient(api_key="test_api_key")
        assert client.api_key == "test_api_key"
        assert client.base_url == "https://api.janua.dev"
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.environment == "production"
        assert client.debug is False
    
    def test_init_with_custom_config(self):
        """Test client initialization with custom configuration."""
        client = JanuaClient(
            api_key="test_api_key",
            base_url="https://staging.api.janua.dev",
            timeout=60.0,
            max_retries=5,
            environment="staging",
            debug=True,
        )
        assert client.api_key == "test_api_key"
        assert client.base_url == "https://staging.api.janua.dev"
        assert client.timeout == 60.0
        assert client.max_retries == 5
        assert client.environment == "staging"
        assert client.debug is True
    
    @patch.dict(os.environ, {"JANUA_API_KEY": "env_api_key"})
    def test_init_with_env_api_key(self):
        """Test client initialization with API key from environment."""
        client = JanuaClient()
        assert client.api_key == "env_api_key"
    
    @patch.dict(os.environ, {
        "JANUA_API_KEY": "env_api_key",
        "JANUA_BASE_URL": "https://custom.api.janua.dev",
        "JANUA_ENVIRONMENT": "development"
    })
    def test_init_with_env_config(self):
        """Test client initialization with configuration from environment."""
        client = JanuaClient()
        assert client.api_key == "env_api_key"
        assert client.base_url == "https://custom.api.janua.dev"
        assert client.environment == "development"
    
    def test_init_without_api_key_raises_error(self):
        """Test that initialization without API key raises error."""
        with pytest.raises(ConfigurationError) as exc_info:
            JanuaClient()
        assert "API key is required" in str(exc_info.value)
    
    def test_service_clients_initialized(self):
        """Test that all service clients are initialized."""
        client = JanuaClient(api_key="test_api_key")
        assert client.auth is not None
        assert client.users is not None
        assert client.organizations is not None
        assert client.sessions is not None
        assert client.webhooks is not None
        assert client.mfa is not None
        assert client.passkeys is not None
    
    def test_set_api_key(self):
        """Test updating the API key."""
        client = JanuaClient(api_key="old_key")
        client.set_api_key("new_key")
        assert client.api_key == "new_key"
        assert client.config.api_key == "new_key"
        assert client.http.api_key == "new_key"
        assert client.http.headers["Authorization"] == "Bearer new_key"
    
    def test_set_environment(self):
        """Test updating the environment."""
        client = JanuaClient(api_key="test_key")
        client.set_environment("staging")
        assert client.environment == "staging"
        assert client.config.environment == "staging"
    
    def test_enable_disable_debug(self):
        """Test enabling and disabling debug mode."""
        client = JanuaClient(api_key="test_key", debug=False)
        assert client.debug is False
        
        client.enable_debug()
        assert client.debug is True
        assert client.config.debug is True
        
        client.disable_debug()
        assert client.debug is False
        assert client.config.debug is False
    
    @patch('janua.client.HTTPClient')
    def test_health_check(self, mock_http_class):
        """Test health check method."""
        mock_http = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_http.get.return_value = mock_response
        mock_http_class.return_value = mock_http
        
        client = JanuaClient(api_key="test_key")
        client.http = mock_http
        
        result = client.health_check()
        assert result == {"status": "healthy", "version": "1.0.0"}
        mock_http.get.assert_called_once_with("/health")
    
    @patch('janua.client.HTTPClient')
    def test_get_api_version(self, mock_http_class):
        """Test get API version method."""
        mock_http = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"version": "2.0.0"}
        mock_http.get.return_value = mock_response
        mock_http_class.return_value = mock_http
        
        client = JanuaClient(api_key="test_key")
        client.http = mock_http
        
        version = client.get_api_version()
        assert version == "2.0.0"
        mock_http.get.assert_called_once_with("/version")
    
    def test_context_manager(self):
        """Test using client as context manager."""
        with JanuaClient(api_key="test_key") as client:
            assert client.api_key == "test_key"
            # Mock the close method to verify it's called
            client.close = Mock()
        
        client.close.assert_called_once()
    
    def test_repr(self):
        """Test string representation of client."""
        client = JanuaClient(
            api_key="test_key",
            base_url="https://api.janua.dev",
            environment="production",
            debug=True
        )
        repr_str = repr(client)
        assert "JanuaClient" in repr_str
        assert "base_url=https://api.janua.dev" in repr_str
        assert "environment=production" in repr_str
        assert "debug=True" in repr_str


class TestCreateClient:
    """Test the create_client convenience function."""
    
    def test_create_client_basic(self):
        """Test basic client creation."""
        client = create_client(api_key="test_key")
        assert isinstance(client, JanuaClient)
        assert client.api_key == "test_key"
    
    def test_create_client_with_kwargs(self):
        """Test client creation with additional arguments."""
        client = create_client(
            api_key="test_key",
            base_url="https://staging.api.janua.dev",
            timeout=45.0,
            debug=True
        )
        assert client.api_key == "test_key"
        assert client.base_url == "https://staging.api.janua.dev"
        assert client.timeout == 45.0
        assert client.debug is True
    
    @patch.dict(os.environ, {"JANUA_API_KEY": "env_key"})
    def test_create_client_from_env(self):
        """Test client creation with API key from environment."""
        client = create_client()
        assert client.api_key == "env_key"