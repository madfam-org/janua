"""HTTP client for making API requests with retry logic and error handling."""

import time
from typing import Any, Dict, Optional, TypeVar
import httpx
from httpx import Response, TimeoutException, NetworkError

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


class HTTPClient:
    """HTTP client for making API requests to the Janua API."""
    
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        custom_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the HTTP client.
        
        Args:
            base_url: Base URL for the API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            custom_headers: Additional headers to include in requests
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
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
            attempt: Current attempt number
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False
        
        # Retry on network errors
        if isinstance(error, (NetworkError, TimeoutException)):
            return True
        
        # Retry on server errors (5xx)
        if isinstance(error, ServerError):
            return True
        
        # Retry on rate limit with exponential backoff
        if isinstance(error, RateLimitError):
            return True
        
        return False
    
    def _calculate_retry_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        """
        Calculate delay before retry using exponential backoff.
        
        Args:
            attempt: Current attempt number
            error: The exception that occurred
            
        Returns:
            Delay in seconds
        """
        # Check for rate limit retry-after header
        if isinstance(error, RateLimitError) and error.details:
            retry_after = error.details.get('retry_after')
            if retry_after:
                try:
                    return float(retry_after)
                except (TypeError, ValueError):
                    pass
        
        # Exponential backoff with jitter
        base_delay = self.retry_delay * (2 ** attempt)
        jitter = base_delay * 0.1 * (0.5 - time.time() % 1)
        return min(base_delay + jitter, 60.0)  # Cap at 60 seconds
    
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
        
        while attempt <= self.max_retries:
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
            if last_error and attempt < self.max_retries:
                delay = self._calculate_retry_delay(attempt, last_error)
                time.sleep(delay)
            
            attempt += 1
        
        # If we get here, we've exhausted retries
        if last_error:
            raise last_error
        else:
            raise JanuaError(f"Failed to complete request after {self.max_retries} retries")
    
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