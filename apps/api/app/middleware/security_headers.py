"""Security Headers Middleware for Janua API"""
from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import structlog

logger = structlog.get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    def __init__(self, app, strict: bool = True):
        super().__init__(app)
        self.strict = strict

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response"""
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Strict Transport Security (HSTS) - only on HTTPS
        if request.url.scheme == "https" or self.strict:
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains; preload"

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # For Swagger UI
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # For Swagger UI
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' https://api.janua.dev",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "upgrade-insecure-requests",
        ]

        # Relax CSP for Swagger docs
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            csp_directives[1] = "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:"
            csp_directives[2] = "style-src 'self' 'unsafe-inline' https:"

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Remove server header if present
        if "server" in response.headers:
            del response.headers["server"]

        # Add custom server header
        response.headers["X-Powered-By"] = "Janua Identity Platform"

        return response
