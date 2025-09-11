import httpx
from typing import Optional, Dict, Any, Union
from .exceptions import (
    PlintoAPIError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    RateLimitError,
    PermissionError,
    ConflictError,
    ServerError,
)


class HttpClient:
    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        debug: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.debug = debug
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=timeout,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()

    def _handle_error(self, response: httpx.Response):
        """Handle HTTP errors and raise appropriate exceptions"""
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
            code = error_data.get("code", "UNKNOWN_ERROR")
            details = error_data.get("details", {})
        except:
            message = response.text or response.reason_phrase
            code = "UNKNOWN_ERROR"
            details = {}

        status_code = response.status_code

        if status_code == 400:
            raise ValidationError(message, details=details)
        elif status_code == 401:
            raise AuthenticationError(message, details=details)
        elif status_code == 403:
            raise PermissionError(message, details=details)
        elif status_code == 404:
            raise NotFoundError(message, details=details)
        elif status_code == 409:
            raise ConflictError(message, details=details)
        elif status_code == 429:
            raise RateLimitError(message, details=details)
        elif status_code >= 500:
            raise ServerError(message, details=details)
        else:
            raise PlintoAPIError(message, code=code, status_code=status_code, details=details)

    def _log(self, method: str, url: str, **kwargs):
        """Log HTTP requests when debug mode is enabled"""
        if self.debug:
            print(f"[Plinto SDK] {method} {url}")
            if kwargs:
                print(f"  Options: {kwargs}")

    async def request(
        self,
        method: str,
        path: str,
        json: Optional[Any] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Union[Dict, list, str, bytes]:
        """Make an HTTP request"""
        url = f"{self.base_url}{path}"
        
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)

        self._log(method, url, json=json, params=params)

        response = await self.client.request(
            method=method,
            url=path,
            json=json,
            params=params,
            headers=request_headers,
            **kwargs,
        )

        if not response.is_success:
            self._handle_error(response)

        if response.status_code == 204:
            return {}

        content_type = response.headers.get("content-type", "")
        
        if "application/json" in content_type:
            return response.json()
        elif "text/" in content_type:
            return response.text
        else:
            return response.content

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """Make a GET request"""
        return await self.request("GET", path, params=params, headers=headers, **kwargs)

    async def post(
        self,
        path: str,
        json: Optional[Any] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """Make a POST request"""
        return await self.request("POST", path, json=json, params=params, headers=headers, **kwargs)

    async def put(
        self,
        path: str,
        json: Optional[Any] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """Make a PUT request"""
        return await self.request("PUT", path, json=json, params=params, headers=headers, **kwargs)

    async def patch(
        self,
        path: str,
        json: Optional[Any] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """Make a PATCH request"""
        return await self.request("PATCH", path, json=json, params=params, headers=headers, **kwargs)

    async def delete(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """Make a DELETE request"""
        return await self.request("DELETE", path, params=params, headers=headers, **kwargs)

    def set_header(self, key: str, value: str):
        """Set a header for all requests"""
        self.headers[key] = value
        self.client.headers[key] = value

    def remove_header(self, key: str):
        """Remove a header"""
        self.headers.pop(key, None)
        self.client.headers.pop(key, None)