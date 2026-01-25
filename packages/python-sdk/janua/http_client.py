"""HTTP client for making API requests with retry logic and error handling."""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
import httpx
from httpx import Response, TimeoutException, NetworkError, AsyncClient

from .exceptions import (
    JanuaError,
    APIError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
    NetworkConnectionError,
)
from .types import BaseResponse

T = TypeVar('T', bound=BaseResponse)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts (including initial request)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Whether to add random jitter to delay (prevents thundering herd)
        retry_on_status: HTTP status codes that should trigger a retry
        on_retry: Optional callback called before each retry
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    on_retry: Optional[Callable[[int, Exception, float], None]] = None

    def calculate_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        """Calculate delay before retry using exponential backoff with jitter.

        Args:
            attempt: Current attempt number (0-indexed)
            error: The exception that triggered the retry

        Returns:
            Delay in seconds
        """
        # Check for rate limit retry-after header
        if isinstance(error, RateLimitError) and error.retry_after:
            try:
                return float(error.retry_after)
            except (TypeError, ValueError):
                pass

        # Calculate exponential backoff
        delay = self.base_delay * (self.exponential_base ** attempt)

        # Apply max delay cap
        delay = min(delay, self.max_delay)

        # Apply jitter if enabled (±25%)
        if self.jitter:
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)

        return max(0, delay)  # Ensure non-negative

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if a request should be retried.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_attempts - 1:
            return False

        # Always retry on network errors
        if isinstance(error, (NetworkError, TimeoutException, NetworkConnectionError)):
            return True

        # Retry on server errors
        if isinstance(error, ServerError):
            return True

        # Retry on rate limit
        if isinstance(error, RateLimitError):
            return True

        # Check if it's an API error with a retryable status
        if isinstance(error, APIError) and error.status_code in self.retry_on_status:
            return True

        return False


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig()

# User-friendly error messages
USER_MESSAGES: Dict[str, str] = {
    'AUTHENTICATION_ERROR': 'Invalid email or password. Please try again.',
    'TOKEN_ERROR': 'Your session is invalid. Please sign in again.',
    'EMAIL_NOT_VERIFIED': 'Please verify your email address to continue.',
    'MFA_REQUIRED': 'Please complete two-factor authentication.',
    'PASSWORD_EXPIRED': 'Your password has expired. Please reset it.',
    'ACCOUNT_LOCKED': 'Your account is temporarily locked. Please try again later.',
    'SESSION_EXPIRED': 'Your session has expired. Please sign in again.',
    'AUTHORIZATION_ERROR': "You don't have permission to perform this action.",
    'INSUFFICIENT_PERMISSIONS': 'You need additional permissions for this action.',
    'VALIDATION_ERROR': 'Please check your input and try again.',
    'NOT_FOUND_ERROR': 'The requested resource was not found.',
    'CONFLICT_ERROR': 'This action conflicts with existing data.',
    'RATE_LIMIT_ERROR': 'Too many requests. Please wait a moment and try again.',
    'INTERNAL_ERROR': 'An unexpected error occurred. Please try again later.',
    'NETWORK_ERROR': 'Unable to connect. Please check your internet connection.',
}


def get_user_message(error: Union[Exception, str]) -> str:
    """Get a user-friendly error message.

    Args:
        error: Exception or error code string

    Returns:
        User-friendly message
    """
    if isinstance(error, str):
        return USER_MESSAGES.get(error, 'An unexpected error occurred.')

    if isinstance(error, JanuaError) and error.code:
        return USER_MESSAGES.get(error.code, error.message)

    if isinstance(error, Exception):
        return str(error)

    return 'An unexpected error occurred.'


class HTTPClient:
    """HTTP client for making API requests to the Janua API."""

    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_config: Optional[RetryConfig] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        # Legacy parameters for backwards compatibility
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ):
        """
        Initialize the HTTP client.

        Args:
            base_url: Base URL for the API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            retry_config: Retry configuration (preferred)
            custom_headers: Additional headers to include in requests
            max_retries: (Deprecated) Use retry_config instead
            retry_delay: (Deprecated) Use retry_config instead
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

        # Handle legacy parameters
        if retry_config:
            self.retry_config = retry_config
        elif max_retries is not None or retry_delay is not None:
            self.retry_config = RetryConfig(
                max_attempts=max_retries or DEFAULT_RETRY_CONFIG.max_attempts,
                base_delay=retry_delay or DEFAULT_RETRY_CONFIG.base_delay,
            )
        else:
            self.retry_config = DEFAULT_RETRY_CONFIG

        # Keep legacy attributes for backwards compatibility
        self.max_retries = self.retry_config.max_attempts
        self.retry_delay = self.retry_config.base_delay
        
        # Set up default headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Janua-Python-SDK/1.0.0',
        }
        
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
        
        if custom_headers:
            self.headers.update(custom_headers)
        
        # Create HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers=self.headers,
            follow_redirects=True,
        )
    
    def _get_url(self, endpoint: str) -> str:
        """Construct full URL for an endpoint."""
        endpoint = endpoint.lstrip('/')
        return f"{self.base_url}/{endpoint}"
    
    def _handle_response_error(self, response: Response) -> None:
        """
        Handle HTTP response errors.
        
        Args:
            response: The HTTP response object
            
        Raises:
            Various JanuaError subclasses based on status code
        """
        try:
            error_data = response.json()
            message = error_data.get('message', response.text)
            code = error_data.get('code')
            details = error_data.get('details')
        except Exception:
            message = response.text or f"HTTP {response.status_code}"
            code = None
            details = None
        
        status_code = response.status_code
        
        # Map status codes to specific exceptions
        if status_code == 401:
            raise AuthenticationError(message, code=code, details=details)
        elif status_code == 403:
            raise AuthorizationError(message, code=code, details=details)
        elif status_code == 404:
            raise NotFoundError(message, code=code, details=details)
        elif status_code == 422 or status_code == 400:
            raise ValidationError(message, code=code, details=details)
        elif status_code == 429:
            # Extract retry-after header if available
            retry_after = response.headers.get('Retry-After')
            details = details or {}
            if retry_after:
                details['retry_after'] = retry_after
            raise RateLimitError(message, code=code, details=details)
        elif 500 <= status_code < 600:
            raise ServerError(message, code=code, details=details)
        else:
            raise APIError(message, status_code=status_code, code=code, details=details)
    
    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if a request should be retried.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry, False otherwise
        """
        return self.retry_config.should_retry(error, attempt)

    def _calculate_retry_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        """
        Calculate delay before retry using exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            error: The exception that occurred

        Returns:
            Delay in seconds
        """
        return self.retry_config.calculate_delay(attempt, error)
    
    def request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """
        Make an HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path
            json: JSON body for the request
            params: Query parameters
            headers: Additional headers for this request
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            HTTP response object
            
        Raises:
            Various JanuaError subclasses based on error type
        """
        url = self._get_url(endpoint)
        
        # Merge headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
        
        attempt = 0
        last_error = None

        while attempt < self.retry_config.max_attempts:
            try:
                response = self.client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=request_headers,
                    **kwargs
                )
                
                # Check for HTTP errors
                if response.status_code >= 400:
                    self._handle_response_error(response)
                
                return response
                
            except (NetworkError, TimeoutException) as e:
                last_error = NetworkConnectionError(
                    f"Network error during {method} {url}: {str(e)}"
                )
                
                if not self._should_retry(last_error, attempt):
                    raise last_error
                
            except (AuthenticationError, AuthorizationError, NotFoundError, ValidationError):
                # Don't retry client errors
                raise
                
            except (RateLimitError, ServerError, APIError) as e:
                last_error = e
                
                if not self._should_retry(e, attempt):
                    raise
                
            except Exception as e:
                # Unexpected error
                raise JanuaError(f"Unexpected error during {method} {url}: {str(e)}")
            
            # Calculate retry delay and wait
            if last_error and attempt < self.retry_config.max_attempts - 1:
                delay = self._calculate_retry_delay(attempt, last_error)

                # Call on_retry callback if configured
                if self.retry_config.on_retry:
                    self.retry_config.on_retry(attempt, last_error, delay)

                time.sleep(delay)

            attempt += 1

        # If we get here, we've exhausted retries
        if last_error:
            raise last_error
        else:
            raise JanuaError(f"Failed to complete request after {self.retry_config.max_attempts} retries")
    
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Response:
        """Make a GET request."""
        return self.request('GET', endpoint, params=params, **kwargs)
    
    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Response:
        """Make a POST request."""
        return self.request('POST', endpoint, json=json, **kwargs)
    
    def put(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Response:
        """Make a PUT request."""
        return self.request('PUT', endpoint, json=json, **kwargs)
    
    def patch(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Response:
        """Make a PATCH request."""
        return self.request('PATCH', endpoint, json=json, **kwargs)
    
    def delete(
        self,
        endpoint: str,
        **kwargs
    ) -> Response:
        """Make a DELETE request."""
        return self.request('DELETE', endpoint, **kwargs)
    
    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()