"""
HTTP client for the Plinto SDK with automatic token refresh and error handling
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

import httpx
from httpx import Response

from .exceptions import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ServerError,
    ValidationError,
    PlintoError,
)


class TokenStorage:
    """Simple in-memory token storage"""
    
    def __init__(self):
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: Optional[float] = None
    
    def set_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """Store tokens with expiration time"""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = time.time() + expires_in - 60  # Refresh 1 minute early
    
    def get_access_token(self) -> Optional[str]:
        """Get access token if not expired"""
        if self._access_token and self._expires_at:
            if time.time() < self._expires_at:
                return self._access_token
        return None
    
    def get_refresh_token(self) -> Optional[str]:
        """Get refresh token"""
        return self._refresh_token
    
    def clear_tokens(self) -> None:
        """Clear all stored tokens"""
        self._access_token = None
        self._refresh_token = None
        self._expires_at = None
    
    def is_expired(self) -> bool:
        """Check if access token is expired"""
        if not self._expires_at:
            return True
        return time.time() >= self._expires_at


class HTTPClient:
    """HTTP client with authentication and error handling"""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.token_storage = TokenStorage()
        
        # Create httpx client
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "Plinto-Python-SDK/1.0.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        
        # Rate limiting
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[float] = None
        self._rate_limit_lock = asyncio.Lock()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
    
    def set_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """Set authentication tokens"""
        self.token_storage.set_tokens(access_token, refresh_token, expires_in)
    
    def clear_tokens(self) -> None:
        """Clear authentication tokens"""
        self.token_storage.clear_tokens()
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}
        
        # Try access token first
        access_token = self.token_storage.get_access_token()
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        
        return headers
    
    async def _handle_rate_limit(self, response: Response) -> None:
        """Handle rate limiting"""
        # Update rate limit info from headers
        if "X-RateLimit-Remaining" in response.headers:
            self._rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        
        if "X-RateLimit-Reset" in response.headers:
            self._rate_limit_reset = float(response.headers["X-RateLimit-Reset"])
        
        # If rate limited, wait for reset
        if response.status_code == 429:
            retry_after = None
            if "Retry-After" in response.headers:
                retry_after = int(response.headers["Retry-After"])
            elif self._rate_limit_reset:
                retry_after = max(0, int(self._rate_limit_reset - time.time()))
            
            raise RateLimitError(
                "Rate limit exceeded",
                status_code=429,
                response_data=await self._safe_json(response),
                retry_after=retry_after,
            )
    
    async def _refresh_token(self) -> bool:
        """Attempt to refresh the access token"""
        refresh_token = self.token_storage.get_refresh_token()
        if not refresh_token:
            return False
        
        try:
            response = await self._client.post(
                f"{self.base_url}/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token_storage.set_tokens(
                    data["access_token"],
                    data["refresh_token"],
                    data["expires_in"],
                )
                return True
        except Exception:
            pass
        
        # If refresh failed, clear tokens
        self.token_storage.clear_tokens()
        return False
    
    async def _safe_json(self, response: Response) -> Dict[str, Any]:
        """Safely parse JSON response"""
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            return {"message": response.text or "Unknown error"}
    
    def _handle_error_response(self, response: Response, data: Dict[str, Any]) -> None:
        """Handle error responses and raise appropriate exceptions"""
        status_code = response.status_code
        message = data.get("detail") or data.get("message") or f"HTTP {status_code}"
        
        if status_code == 400:
            # Check for validation errors
            if "errors" in data:
                raise ValidationError(
                    message,
                    status_code,
                    data,
                    field_errors=data.get("errors", {}),
                )
            raise ValidationError(message, status_code, data)
        elif status_code == 401:
            raise AuthenticationError(message, status_code, data)
        elif status_code == 403:
            raise PermissionError(message, status_code, data)
        elif status_code == 404:
            raise NotFoundError(message, status_code, data)
        elif status_code == 429:
            retry_after = None
            if "Retry-After" in response.headers:
                retry_after = int(response.headers["Retry-After"])
            raise RateLimitError(message, status_code, data, retry_after)
        elif 500 <= status_code < 600:
            raise ServerError(message, status_code, data)
        else:
            raise PlintoError(message, status_code, data)
    
    async def _make_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Make HTTP request with authentication and error handling"""
        url = urljoin(f"{self.base_url}/", path.lstrip('/'))
        
        # Prepare headers
        request_headers = {**self._get_auth_headers()}
        if headers:
            request_headers.update(headers)
        
        # Handle file uploads
        if files:
            # Remove content-type for multipart uploads
            request_headers.pop("Content-Type", None)
        
        for attempt in range(self.max_retries + 1):
            try:
                # Check rate limit before making request
                async with self._rate_limit_lock:
                    if (
                        self._rate_limit_remaining is not None
                        and self._rate_limit_remaining <= 0
                        and self._rate_limit_reset
                        and time.time() < self._rate_limit_reset
                    ):
                        wait_time = max(0, self._rate_limit_reset - time.time())
                        await asyncio.sleep(wait_time)
                
                # Make the request
                response = await self._client.request(
                    method,
                    url,
                    json=json_data,
                    params=params,
                    headers=request_headers,
                    files=files,
                )
                
                # Handle rate limiting
                await self._handle_rate_limit(response)
                
                # If unauthorized and we have a refresh token, try to refresh
                if response.status_code == 401 and self.token_storage.get_refresh_token():
                    if await self._refresh_token():
                        # Update headers with new token and retry
                        request_headers.update(self._get_auth_headers())
                        response = await self._client.request(
                            method,
                            url,
                            json=json_data,
                            params=params,
                            headers=request_headers,
                            files=files,
                        )
                
                # Handle errors
                if not response.is_success:
                    data = await self._safe_json(response)
                    self._handle_error_response(response, data)
                
                return response
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == self.max_retries:
                    raise NetworkError(f"Network error: {str(e)}", e)
                
                # Exponential backoff
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
            
            except (RateLimitError, AuthenticationError, ValidationError) as e:
                # Don't retry these errors
                raise e
            
            except Exception as e:
                if attempt == self.max_retries:
                    raise NetworkError(f"Unexpected error: {str(e)}", e)
                
                await asyncio.sleep(self.retry_delay)
        
        raise NetworkError("Max retries exceeded")
    
    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make GET request"""
        return await self._make_request("GET", path, params=params, headers=headers)
    
    async def post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Make POST request"""
        return await self._make_request(
            "POST", path, json_data=json_data, params=params, headers=headers, files=files
        )
    
    async def patch(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make PATCH request"""
        return await self._make_request("PATCH", path, json_data=json_data, params=params, headers=headers)
    
    async def put(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make PUT request"""
        return await self._make_request("PUT", path, json_data=json_data, params=params, headers=headers)
    
    async def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make DELETE request"""
        return await self._make_request("DELETE", path, params=params, headers=headers)