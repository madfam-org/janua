"""
Authentication management for SDK clients.

Handles token management, refresh logic, and authentication flows
in a way that translates well to all platform SDKs.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Protocol

import structlog

from .error_handling import AuthenticationError, ConfigurationError

logger = structlog.get_logger(__name__)


class TokenType(str, Enum):
    """Token types supported by the authentication system."""

    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    API_KEY = "api_key"


class TokenRefreshStrategy(str, Enum):
    """Strategies for refreshing tokens."""

    AUTOMATIC = "automatic"  # Refresh automatically when near expiration
    ON_DEMAND = "on_demand"  # Refresh only when request fails with 401
    MANUAL = "manual"  # Never refresh automatically


class TokenStorage(Protocol):
    """
    Protocol for token storage backends.

    Each platform will implement this differently:
    - Python: In-memory dict, SQLite, or keyring
    - TypeScript: localStorage, sessionStorage, or secure storage
    - Mobile: Keychain (iOS) or Android Keystore
    - Desktop: OS credential manager
    """

    async def store_token(
        self, token_type: TokenType, token: str, expires_at: Optional[datetime] = None
    ) -> None:
        """Store a token securely."""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes

    async def get_token(self, token_type: TokenType) -> Optional[str]:
        """Retrieve a stored token."""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes

    async def remove_token(self, token_type: TokenType) -> None:
        """Remove a token from storage."""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes

    async def clear_all_tokens(self) -> None:
        """Clear all stored tokens."""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes


class InMemoryTokenStorage:
    """
    Simple in-memory token storage for development and testing.

    Production SDKs should use platform-appropriate secure storage.
    """

    def __init__(self):
        self._tokens: Dict[TokenType, Dict[str, Any]] = {}

    async def store_token(
        self, token_type: TokenType, token: str, expires_at: Optional[datetime] = None
    ) -> None:
        self._tokens[token_type] = {
            "token": token,
            "expires_at": expires_at,
            "stored_at": datetime.utcnow(),
        }

    async def get_token(self, token_type: TokenType) -> Optional[str]:
        token_data = self._tokens.get(token_type)
        if not token_data:
            return None

        # Check if token is expired
        expires_at = token_data.get("expires_at")
        if expires_at and datetime.utcnow() >= expires_at:
            await self.remove_token(token_type)
            return None

        return token_data["token"]

    async def remove_token(self, token_type: TokenType) -> None:
        self._tokens.pop(token_type, None)

    async def clear_all_tokens(self) -> None:
        self._tokens.clear()

    def get_token_info(self, token_type: TokenType) -> Optional[Dict[str, Any]]:
        """Get full token information including metadata."""
        return self._tokens.get(token_type)


class TokenManager:
    """
    Manages authentication tokens with automatic refresh capabilities.

    This class provides the core token management logic that will be
    implemented in each platform SDK with appropriate platform-specific
    storage and HTTP handling.
    """

    def __init__(
        self,
        storage: Optional[TokenStorage] = None,
        refresh_strategy: TokenRefreshStrategy = TokenRefreshStrategy.AUTOMATIC,
        refresh_buffer_seconds: int = 300,  # Refresh 5 minutes before expiration
    ):
        self.storage = storage or InMemoryTokenStorage()
        self.refresh_strategy = refresh_strategy
        self.refresh_buffer_seconds = refresh_buffer_seconds
        self._refresh_lock = asyncio.Lock()
        self._refresh_callbacks: Dict[str, callable] = {}

    async def store_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> None:
        """
        Store authentication tokens.

        Args:
            access_token: JWT access token
            refresh_token: JWT refresh token (optional)
            expires_in: Access token expiration time in seconds
        """
        # Calculate expiration time
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Store access token
        await self.storage.store_token(TokenType.ACCESS_TOKEN, access_token, expires_at)

        # Store refresh token if provided
        if refresh_token:
            await self.storage.store_token(TokenType.REFRESH_TOKEN, refresh_token)

    async def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token or None if authentication is required
        """
        # Try to get current access token
        access_token = await self.storage.get_token(TokenType.ACCESS_TOKEN)

        # Check if token needs refresh
        if await self._should_refresh_token():
            if self.refresh_strategy == TokenRefreshStrategy.AUTOMATIC:
                try:
                    await self._refresh_access_token()
                    access_token = await self.storage.get_token(TokenType.ACCESS_TOKEN)
                except Exception:
                    # If refresh fails, return current token (if any) and let request fail
                    pass

        return access_token

    async def get_refresh_token(self) -> Optional[str]:
        """Get the stored refresh token."""
        return await self.storage.get_token(TokenType.REFRESH_TOKEN)

    async def refresh_access_token(self) -> bool:
        """
        Manually refresh the access token.

        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            await self._refresh_access_token()
            return True
        except Exception:
            return False

    async def _refresh_access_token(self) -> None:
        """
        Internal method to refresh the access token.

        This method will be called by the SDK when refresh is needed.
        Platform-specific implementations will make the actual HTTP request.
        """
        async with self._refresh_lock:
            refresh_token = await self.get_refresh_token()
            if not refresh_token:
                raise AuthenticationError("No refresh token available")

            # Call the registered refresh callback
            refresh_callback = self._refresh_callbacks.get("refresh_token")
            if not refresh_callback:
                raise ConfigurationError("No token refresh callback registered")

            try:
                token_response = await refresh_callback(refresh_token)
                await self._handle_token_response(token_response)
            except Exception as e:
                # Clear tokens if refresh fails
                await self.clear_tokens()
                raise AuthenticationError(f"Token refresh failed: {str(e)}")

    async def _handle_token_response(self, response: Dict[str, Any]) -> None:
        """Handle a token response and store the new tokens."""
        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")
        expires_in = response.get("expires_in")

        if not access_token:
            raise AuthenticationError("Invalid token response: missing access_token")

        await self.store_tokens(access_token, refresh_token, expires_in)

    async def _should_refresh_token(self) -> bool:
        """Check if the access token should be refreshed."""
        if self.refresh_strategy != TokenRefreshStrategy.AUTOMATIC:
            return False

        # Get token info from storage
        storage_with_info = getattr(self.storage, "get_token_info", None)
        if not storage_with_info:
            return False

        token_info = storage_with_info(TokenType.ACCESS_TOKEN)
        if not token_info:
            return False

        expires_at = token_info.get("expires_at")
        if not expires_at:
            return False

        # Check if token expires within the buffer period
        buffer_time = datetime.utcnow() + timedelta(seconds=self.refresh_buffer_seconds)
        return expires_at <= buffer_time

    async def clear_tokens(self) -> None:
        """Clear all stored tokens."""
        await self.storage.clear_all_tokens()

    def register_refresh_callback(self, callback_name: str, callback: callable) -> None:
        """
        Register a callback for token operations.

        This allows the SDK to provide the actual HTTP implementation
        while keeping the token management logic platform-agnostic.
        """
        self._refresh_callbacks[callback_name] = callback

    async def handle_authentication_error(self, error_code: str) -> bool:
        """
        Handle authentication errors and attempt recovery.

        Returns:
            True if recovery was attempted, False if manual intervention is needed
        """
        if error_code == "ACCESS_TOKEN_EXPIRED":
            if self.refresh_strategy in [
                TokenRefreshStrategy.AUTOMATIC,
                TokenRefreshStrategy.ON_DEMAND,
            ]:
                try:
                    await self._refresh_access_token()
                    return True
                except Exception as e:
                    logger.warning(
                        "Failed to automatically refresh access token",
                        error=str(e),
                        error_type=type(e).__name__,
                        refresh_strategy=self.refresh_strategy.value,
                    )

        # For other errors or failed refresh, clear tokens
        await self.clear_tokens()
        return False


class AuthenticationFlow:
    """
    Manages different authentication flows supported by Janua.

    Each flow represents a different way to authenticate with the API:
    - Email/password
    - Magic link
    - OAuth providers
    - API key
    """

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self._auth_callbacks: Dict[str, callable] = {}

    def register_auth_callback(self, flow_name: str, callback: callable) -> None:
        """Register a callback for an authentication flow."""
        self._auth_callbacks[flow_name] = callback

    async def authenticate_with_password(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate using email and password."""
        callback = self._auth_callbacks.get("password_auth")
        if not callback:
            raise ConfigurationError("Password authentication not configured")

        response = await callback(email, password)
        await self.token_manager._handle_token_response(response)
        return response

    async def authenticate_with_magic_link(self, token: str) -> Dict[str, Any]:
        """Authenticate using a magic link token."""
        callback = self._auth_callbacks.get("magic_link_auth")
        if not callback:
            raise ConfigurationError("Magic link authentication not configured")

        response = await callback(token)
        await self.token_manager._handle_token_response(response)
        return response

    async def authenticate_with_oauth(
        self, provider: str, code: str, state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Authenticate using OAuth provider."""
        callback = self._auth_callbacks.get("oauth_auth")
        if not callback:
            raise ConfigurationError("OAuth authentication not configured")

        response = await callback(provider, code, state)
        await self.token_manager._handle_token_response(response)
        return response

    async def sign_out(self) -> None:
        """Sign out and clear all tokens."""
        # Call sign out callback if available
        callback = self._auth_callbacks.get("sign_out")
        if callback:
            try:
                await callback()
            except Exception as e:
                # Continue with local sign out even if API call fails
                logger.warning(
                    "Sign out callback failed, continuing with local token clearance",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Clear local tokens
        await self.token_manager.clear_tokens()


class APIKeyAuth:
    """
    Simple API key authentication for server-to-server communications.

    This is simpler than token-based auth and doesn't require refresh logic.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ConfigurationError("API key is required")
        self.api_key = api_key

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API key auth."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,  # Some APIs prefer this header
        }

    def is_valid(self) -> bool:
        """Check if the API key is valid (not empty)."""
        return bool(self.api_key and self.api_key.strip())


# Helper functions for SDK implementations
async def create_token_manager(
    storage_type: str = "memory",
    refresh_strategy: TokenRefreshStrategy = TokenRefreshStrategy.AUTOMATIC,
    **storage_kwargs,
) -> TokenManager:
    """
    Factory function to create a token manager with appropriate storage.

    Each platform SDK will implement platform-specific storage options.
    """
    if storage_type == "memory":
        storage = InMemoryTokenStorage()
    else:
        # Platform SDKs will implement other storage types
        # - "keychain" for iOS
        # - "keystore" for Android
        # - "credential_manager" for Windows
        # - "keyring" for Linux
        # - "localStorage" for browser
        raise ConfigurationError(f"Unsupported storage type: {storage_type}")

    return TokenManager(storage=storage, refresh_strategy=refresh_strategy)


def create_auth_flow(token_manager: TokenManager) -> AuthenticationFlow:
    """Create an authentication flow with the given token manager."""
    return AuthenticationFlow(token_manager)
