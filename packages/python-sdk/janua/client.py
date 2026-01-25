"""Main Janua SDK client for authentication and user management."""

import os
from typing import Optional, Dict, Any

from .http_client import HTTPClient
from .auth import AuthClient
from .users import UsersClient
from .organizations import OrganizationsClient
from .sessions import SessionsClient
from .webhooks import WebhooksClient
from .mfa import MFAClient
from .passkeys import PasskeysClient
from .types import (
    JanuaConfig,
)
from .exceptions import ConfigurationError


class JanuaClient:
    """
    Main client for interacting with the Janua API.

    This client provides access to all Janua services including authentication,
    user management, organizations, sessions, MFA, passkeys, and webhooks.

    Example:
        ```python
        from janua import JanuaClient

        # Initialize with API key
        client = JanuaClient(api_key="your_api_key")

        # Or with custom configuration
        client = JanuaClient(
            api_key="your_api_key",
            base_url="https://api.janua.dev",
            timeout=30.0,
            max_retries=3
        )

        # Use the client
        result = client.auth.sign_in(
            email="user@example.com",
            password="secure_password"
        )

        # Access tokens after authentication
        access_token = client.get_access_token()
        id_token = client.get_id_token()

        # Check authentication status
        if client.is_authenticated():
            user = client.auth.get_current_user()
        ```
    """

    DEFAULT_BASE_URL = "https://api.janua.dev"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_RETRIES = 3
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        environment: Optional[str] = None,
        debug: bool = False,
        custom_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the Janua client.
        
        Args:
            api_key: Your Janua API key. Can also be set via JANUA_API_KEY env var
            base_url: Base URL for the API. Defaults to https://api.janua.dev
            timeout: Request timeout in seconds. Defaults to 30
            max_retries: Maximum number of retry attempts. Defaults to 3
            environment: Environment name (production, staging, development)
            debug: Enable debug mode for detailed logging
            custom_headers: Additional headers to include in all requests
            
        Raises:
            ConfigurationError: If API key is not provided and not in environment
        """
        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get('JANUA_API_KEY')
        if not self.api_key:
            raise ConfigurationError(
                "API key is required. Provide it as a parameter or set JANUA_API_KEY environment variable"
            )
        
        # Get base URL from parameter, environment, or default
        self.base_url = (
            base_url or 
            os.environ.get('JANUA_BASE_URL') or 
            self.DEFAULT_BASE_URL
        )
        
        # Configure client settings
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self.environment = environment or os.environ.get('JANUA_ENVIRONMENT', 'production')
        self.debug = debug
        
        # Create configuration object
        self.config = JanuaConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            environment=self.environment,
            debug=self.debug,
        )
        
        # Initialize HTTP client
        self.http = HTTPClient(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
            custom_headers=custom_headers,
        )
        
        # Initialize service clients
        self._init_service_clients()
    
    def _init_service_clients(self) -> None:
        """Initialize all service clients."""
        self.auth = AuthClient(self.http, self.config, self)
        self.users = UsersClient(self.http, self.config)
        self.organizations = OrganizationsClient(self.http, self.config)
        self.sessions = SessionsClient(self.http, self.config)
        self.webhooks = WebhooksClient(self.http, self.config)
        self.mfa = MFAClient(self.http, self.config)
        self.passkeys = PasskeysClient(self.http, self.config)

        # Token storage
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._id_token: Optional[str] = None

    def get_access_token(self) -> Optional[str]:
        """
        Get the current access token.

        Returns:
            The access token if authenticated, None otherwise
        """
        return self._access_token

    def get_id_token(self) -> Optional[str]:
        """
        Get the current ID token.

        Returns:
            The ID token if available, None otherwise
        """
        return self._id_token

    def get_refresh_token(self) -> Optional[str]:
        """
        Get the current refresh token.

        Returns:
            The refresh token if authenticated, None otherwise
        """
        return self._refresh_token

    def set_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        id_token: Optional[str] = None,
    ) -> None:
        """
        Store authentication tokens and update the HTTP client authorization header.

        Args:
            access_token: The access token
            refresh_token: The refresh token (optional)
            id_token: The ID token (optional)
        """
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._id_token = id_token
        self.http.headers['Authorization'] = f'Bearer {access_token}'

    def clear_tokens(self) -> None:
        """Clear all stored tokens and remove the authorization header."""
        self._access_token = None
        self._refresh_token = None
        self._id_token = None
        self.http.headers.pop('Authorization', None)

    def is_authenticated(self) -> bool:
        """
        Check if the client has a valid access token.

        Returns:
            True if an access token is stored, False otherwise
        """
        return self._access_token is not None
    
    def set_api_key(self, api_key: str) -> None:
        """
        Update the API key used for authentication.
        
        Args:
            api_key: The new API key
        """
        self.api_key = api_key
        self.config.api_key = api_key
        self.http.api_key = api_key
        self.http.headers['Authorization'] = f'Bearer {api_key}'
    
    def set_environment(self, environment: str) -> None:
        """
        Set the environment for the client.
        
        Args:
            environment: Environment name (production, staging, development)
        """
        self.environment = environment
        self.config.environment = environment
    
    def enable_debug(self) -> None:
        """Enable debug mode for detailed logging."""
        self.debug = True
        self.config.debug = True
    
    def disable_debug(self) -> None:
        """Disable debug mode."""
        self.debug = False
        self.config.debug = False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the Janua API.
        
        Returns:
            Dictionary containing health status information
            
        Raises:
            JanuaError: If health check fails
        """
        response = self.http.get('/health')
        return response.json()
    
    def get_api_version(self) -> str:
        """
        Get the current API version.
        
        Returns:
            API version string
            
        Raises:
            JanuaError: If request fails
        """
        response = self.http.get('/version')
        data = response.json()
        return data.get('version', 'unknown')
    
    def close(self) -> None:
        """Close the client and release resources."""
        self.http.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __repr__(self) -> str:
        """String representation of the client."""
        return (
            f"JanuaClient("
            f"base_url={self.base_url}, "
            f"environment={self.environment}, "
            f"debug={self.debug}"
            f")"
        )


# Convenience function for quick initialization
def create_client(
    api_key: Optional[str] = None,
    **kwargs
) -> JanuaClient:
    """
    Create a Janua client instance.
    
    This is a convenience function for quickly creating a client.
    
    Args:
        api_key: Your Janua API key
        **kwargs: Additional arguments to pass to JanuaClient
        
    Returns:
        Configured JanuaClient instance
        
    Example:
        ```python
        from janua import create_client
        
        client = create_client("your_api_key")
        ```
    """
    return JanuaClient(api_key=api_key, **kwargs)