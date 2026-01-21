"""
Base SDK client classes and configuration for all platform SDKs.

Provides the foundation that will be translated to each platform's
idiomatic patterns during SDK generation.
"""

import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, HttpUrl

T = TypeVar('T')


class AuthenticationMethod(str, Enum):
    """Authentication methods supported by the SDK."""
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    OAUTH2 = "oauth2"
    MAGIC_LINK = "magic_link"


class Environment(str, Enum):
    """API environment configurations."""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    LOCAL = "local"


@dataclass
class RetryConfig:
    """
    Retry configuration for SDK operations.

    Platform-specific SDKs will translate this to appropriate retry logic.
    """
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    max_backoff: float = 60.0
    retryable_status_codes: List[int] = None
    retryable_exceptions: List[str] = None

    def __post_init__(self):
        if self.retryable_status_codes is None:
            self.retryable_status_codes = [429, 500, 502, 503, 504]
        if self.retryable_exceptions is None:
            self.retryable_exceptions = ["NetworkError", "TimeoutError"]


@dataclass
class RequestOptions:
    """
    Per-request configuration options.

    Allows SDK consumers to override default behavior on a per-request basis.
    """
    timeout: Optional[float] = None
    retries: Optional[RetryConfig] = None
    headers: Optional[Dict[str, str]] = None
    idempotency_key: Optional[str] = None


class ClientConfig(BaseModel):
    """
    SDK client configuration.

    This will be the primary configuration class for all platform SDKs.
    """
    # API Configuration
    base_url: HttpUrl = Field(default="https://api.janua.dev", description="API base URL")
    api_version: str = Field(default="v1", description="API version to use")
    environment: Environment = Field(default=Environment.PRODUCTION, description="API environment")

    # Authentication
    api_key: Optional[str] = Field(None, description="API key for authentication")
    access_token: Optional[str] = Field(None, description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    auth_method: AuthenticationMethod = Field(default=AuthenticationMethod.API_KEY, description="Authentication method")

    # Request Configuration
    timeout: float = Field(default=30.0, description="Default request timeout in seconds")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, description="Default retry configuration")

    # Rate Limiting
    rate_limit_per_second: Optional[float] = Field(None, description="Client-side rate limiting")

    # Debugging and Logging
    debug: bool = Field(default=False, description="Enable debug logging")
    log_requests: bool = Field(default=False, description="Log all requests")
    log_responses: bool = Field(default=False, description="Log all responses")

    # User Agent and Headers
    user_agent: Optional[str] = Field(None, description="Custom User-Agent header")
    default_headers: Dict[str, str] = Field(default_factory=dict, description="Default headers for all requests")

    class Config:
        arbitrary_types_allowed = True


class BaseAPIClient(ABC):
    """
    Abstract base class for all platform-specific SDK clients.

    This class defines the interface and common functionality that will be
    implemented in each platform's SDK (Python, TypeScript, Go, etc.).
    """

    def __init__(self, config: ClientConfig):
        self.config = config
        self._session = None
        self._token_manager = None
        self._rate_limiter = None
        self._last_request_time = 0.0

    @property
    def base_url(self) -> str:
        """Get the full API base URL with version."""
        return f"{self.config.base_url}/api/{self.config.api_version}"

    @abstractmethod
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        options: Optional[RequestOptions] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.

        This method will be implemented differently in each platform:
        - Python: Uses aiohttp or httpx
        - TypeScript: Uses fetch or axios
        - Go: Uses net/http
        - Java: Uses OkHttp or HttpClient
        - Swift: Uses URLSession
        - Kotlin: Uses OkHttp or Retrofit
        """

    @abstractmethod
    async def _handle_authentication(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Add authentication headers to the request.

        Platform-specific implementations will handle token management,
        refresh logic, and header formatting.
        """

    @abstractmethod
    async def _handle_rate_limiting(self) -> None:
        """
        Handle client-side rate limiting.

        Implements intelligent rate limiting to prevent hitting API limits.
        """

    async def _apply_retry_logic(
        self,
        request_func,
        retry_config: Optional[RetryConfig] = None
    ) -> Any:
        """
        Apply retry logic to a request function.

        This provides exponential backoff and intelligent retry handling
        that works across all platforms.
        """
        config = retry_config or self.config.retry_config
        last_exception = None

        for attempt in range(config.max_retries + 1):
            try:
                return await request_func()
            except Exception as e:
                last_exception = e

                # Check if this exception/status code is retryable
                if not self._is_retryable_error(e, config):
                    raise e

                if attempt == config.max_retries:
                    raise e

                # Calculate backoff delay
                delay = min(
                    config.backoff_multiplier ** attempt,
                    config.max_backoff
                )

                await asyncio.sleep(delay)

        raise last_exception

    def _is_retryable_error(self, error: Exception, config: RetryConfig) -> bool:
        """Determine if an error should be retried."""
        error_name = type(error).__name__
        return error_name in config.retryable_exceptions

    async def close(self) -> None:
        """
        Clean up client resources.

        Each platform will implement appropriate cleanup:
        - Close HTTP connections
        - Cancel background tasks
        - Clear caches
        """
        if self._session:
            await self._session.close()


class ResourceClient(ABC):
    """
    Base class for resource-specific clients (auth, users, organizations, etc.).

    Each API resource will have its own client class that inherits from this.
    """

    def __init__(self, api_client: BaseAPIClient):
        self.api_client = api_client

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        options: Optional[RequestOptions] = None
    ) -> Dict[str, Any]:
        """Make a request through the API client."""
        return await self.api_client._make_request(
            method=method,
            endpoint=endpoint,
            data=data,
            params=params,
            options=options
        )


class PaginatedResourceClient(ResourceClient):
    """
    Base class for resources that support pagination.

    Provides consistent pagination handling across all platforms.
    """

    async def _paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 20
    ) -> "PaginatedResult[T]":
        """
        Make a paginated request and return a paginated result object.

        The PaginatedResult will provide platform-appropriate iteration:
        - Python: async iterator
        - TypeScript: async generator or Promise-based pagination
        - Go: channel-based iteration
        - Java: Stream or Iterator
        """
        params = params or {}
        params.update({
            "page": 1,
            "per_page": page_size
        })

        response = await self._request("GET", endpoint, params=params)
        return PaginatedResult(self, endpoint, params, response)


class PaginatedResult(Generic[T]):
    """
    Paginated result wrapper that provides platform-appropriate iteration.

    Each platform SDK will implement this differently:
    - Python: async iterator with __aiter__ and __anext__
    - TypeScript: AsyncIterable or custom pagination methods
    - Go: channel-based iteration or slice batching
    - Java: Stream or Iterator interface
    """

    def __init__(
        self,
        client: PaginatedResourceClient,
        endpoint: str,
        params: Dict[str, Any],
        initial_response: Dict[str, Any]
    ):
        self.client = client
        self.endpoint = endpoint
        self.params = params
        self.current_page = initial_response["pagination"]["page"]
        self.total_pages = initial_response["pagination"]["pages"]
        self.items = initial_response["data"]
        self.pagination = initial_response["pagination"]

    async def next_page(self) -> Optional["PaginatedResult[T]"]:
        """Get the next page of results."""
        if not self.pagination["has_next"]:
            return None

        next_params = self.params.copy()
        next_params["page"] = self.current_page + 1

        response = await self.client._request("GET", self.endpoint, params=next_params)
        return PaginatedResult(self.client, self.endpoint, self.params, response)

    async def prev_page(self) -> Optional["PaginatedResult[T]"]:
        """Get the previous page of results."""
        if not self.pagination["has_prev"]:
            return None

        prev_params = self.params.copy()
        prev_params["page"] = self.current_page - 1

        response = await self.client._request("GET", self.endpoint, params=prev_params)
        return PaginatedResult(self.client, self.endpoint, self.params, prev_params)

    async def all_pages(self) -> List[T]:
        """
        Collect all pages into a single list.

        Use with caution for large datasets.
        """
        all_items = self.items.copy()
        current = self

        while current.pagination["has_next"]:
            current = await current.next_page()
            if current:
                all_items.extend(current.items)
            else:
                break

        return all_items


# Example resource client implementations that SDKs will generate
class AuthClient(ResourceClient):
    """Authentication resource client."""

    async def sign_up(self, email: str, password: str, **kwargs) -> Dict[str, Any]:
        """Sign up a new user."""
        data = {"email": email, "password": password, **kwargs}
        return await self._request("POST", "/auth/signup", data=data)

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in with email and password."""
        data = {"email": email, "password": password}
        return await self._request("POST", "/auth/signin", data=data)

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an access token."""
        data = {"refresh_token": refresh_token}
        return await self._request("POST", "/auth/refresh", data=data)


class UsersClient(PaginatedResourceClient):
    """Users resource client with pagination support."""

    async def get_me(self) -> Dict[str, Any]:
        """Get current user information."""
        return await self._request("GET", "/users/me")

    async def update_me(self, **kwargs) -> Dict[str, Any]:
        """Update current user information."""
        return await self._request("PATCH", "/users/me", data=kwargs)

    async def list_users(self, page_size: int = 20) -> PaginatedResult:
        """List users with pagination."""
        return await self._paginated_request("/users", page_size=page_size)


class OrganizationsClient(PaginatedResourceClient):
    """Organizations resource client."""

    async def create(self, name: str, slug: str, **kwargs) -> Dict[str, Any]:
        """Create a new organization."""
        data = {"name": name, "slug": slug, **kwargs}
        return await self._request("POST", "/organizations", data=data)

    async def get(self, org_id: str) -> Dict[str, Any]:
        """Get organization by ID."""
        return await self._request("GET", f"/organizations/{org_id}")

    async def list(self, page_size: int = 20) -> PaginatedResult:
        """List organizations with pagination."""
        return await self._paginated_request("/organizations", page_size=page_size)