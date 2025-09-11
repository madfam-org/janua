"""
Main Plinto SDK client
"""

import os
from typing import Optional
from urllib.parse import urljoin

from .http_client import HTTPClient
from .auth import AuthModule
from .users import UsersModule
from .organizations import OrganizationsModule
from .webhooks import WebhooksModule
from .admin import AdminModule
from .exceptions import ConfigurationError


class PlintoClient:
    """
    Main Plinto SDK client
    
    Example usage:
        # Initialize client
        client = PlintoClient(base_url="https://api.plinto.com")
        
        # Sign in
        response = await client.auth.sign_in(SignInRequest(
            email="user@example.com",
            password="password123"
        ))
        
        # Get current user
        user = await client.users.get_current_user()
        
        # Create organization
        org = await client.organizations.create_organization(
            OrganizationCreateRequest(
                name="My Organization",
                slug="my-org"
            )
        )
        
        # Don't forget to close the client
        await client.close()
        
        # Or use as context manager
        async with PlintoClient(base_url="https://api.plinto.com") as client:
            # Use client here
            pass
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Plinto client
        
        Args:
            base_url: Base URL for the Plinto API (can also use PLINTO_BASE_URL env var)
            api_key: API key for authentication (can also use PLINTO_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        # Get base URL from parameter or environment
        self.base_url = base_url or os.getenv("PLINTO_BASE_URL")
        if not self.base_url:
            raise ConfigurationError(
                "Base URL is required. Provide it as a parameter or set PLINTO_BASE_URL environment variable."
            )
        
        # Ensure base URL doesn't end with slash
        self.base_url = self.base_url.rstrip('/')
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("PLINTO_API_KEY")
        
        # Initialize HTTP client
        self.http = HTTPClient(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        
        # Initialize modules
        self.auth = AuthModule(self.http)
        self.users = UsersModule(self.http)
        self.organizations = OrganizationsModule(self.http)
        self.webhooks = WebhooksModule(self.http)
        self.admin = AdminModule(self.http)
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the HTTP client and clean up resources"""
        await self.http.close()
    
    def set_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """
        Set authentication tokens manually
        
        Args:
            access_token: JWT access token
            refresh_token: JWT refresh token
            expires_in: Token expiration time in seconds
        """
        self.http.set_tokens(access_token, refresh_token, expires_in)
    
    def clear_tokens(self) -> None:
        """Clear stored authentication tokens"""
        self.http.clear_tokens()
    
    def get_access_token(self) -> Optional[str]:
        """
        Get current access token if valid
        
        Returns:
            Access token or None if expired/missing
        """
        return self.http.token_storage.get_access_token()
    
    def get_refresh_token(self) -> Optional[str]:
        """
        Get current refresh token
        
        Returns:
            Refresh token or None if missing
        """
        return self.http.token_storage.get_refresh_token()
    
    def is_authenticated(self) -> bool:
        """
        Check if client is authenticated
        
        Returns:
            True if client has valid tokens
        """
        return self.http.token_storage.get_access_token() is not None
    
    def is_token_expired(self) -> bool:
        """
        Check if access token is expired
        
        Returns:
            True if token is expired or missing
        """
        return self.http.token_storage.is_expired()
    
    @classmethod
    def from_environment(cls) -> "PlintoClient":
        """
        Create client from environment variables
        
        Environment variables:
            PLINTO_BASE_URL: Base URL for the API
            PLINTO_API_KEY: API key for authentication
            PLINTO_TIMEOUT: Request timeout (default: 30)
            PLINTO_MAX_RETRIES: Maximum retries (default: 3)
            PLINTO_RETRY_DELAY: Retry delay (default: 1.0)
        
        Returns:
            Configured Plinto client
        """
        return cls(
            base_url=os.getenv("PLINTO_BASE_URL"),
            api_key=os.getenv("PLINTO_API_KEY"),
            timeout=int(os.getenv("PLINTO_TIMEOUT", "30")),
            max_retries=int(os.getenv("PLINTO_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("PLINTO_RETRY_DELAY", "1.0")),
        )
    
    def get_api_url(self, path: str = "") -> str:
        """
        Get full API URL for a given path
        
        Args:
            path: API path
            
        Returns:
            Full URL
        """
        return urljoin(f"{self.base_url}/", path.lstrip('/'))