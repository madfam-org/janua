"""
Janua Middleware Stack

Provides a pre-configured middleware stack for FastAPI applications
integrating Janua authentication and security features.
"""

from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.config import get_settings


def get_middleware_stack() -> List[tuple]:
    """
    Get the default Janua middleware stack.

    Returns:
        List of (middleware_class, kwargs) tuples
    """
    settings = get_settings()

    middleware_stack = [
        # Security headers (applied last, so first in stack)
        (SecurityHeadersMiddleware, {}),

        # Rate limiting
        (RateLimitMiddleware, {}),

        # Logging middleware
        (LoggingMiddleware, {}),

        # CORS middleware
        (
            CORSMiddleware,
            {
                "allow_origins": settings.CORS_ORIGINS,
                "allow_credentials": True,
                "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                "allow_headers": [
                    "Authorization",
                    "Content-Type",
                    "X-Requested-With",
                    "X-API-Key",
                    "X-Organization-ID",
                    "X-Tenant-ID",
                ],
            }
        ),

        # Trusted host middleware
        (
            TrustedHostMiddleware,
            {
                "allowed_hosts": ["*"] if settings.DEBUG else [settings.DOMAIN]
            }
        ),
    ]

    return middleware_stack


def apply_middleware_stack(app: FastAPI, custom_middleware: List[tuple] = None) -> FastAPI:
    """
    Apply the Janua middleware stack to a FastAPI application.

    Args:
        app: FastAPI application instance
        custom_middleware: Additional middleware to apply (optional)

    Returns:
        FastAPI application with middleware applied
    """
    # Apply custom middleware first (if any)
    if custom_middleware:
        for middleware_class, kwargs in custom_middleware:
            app.add_middleware(middleware_class, **kwargs)

    # Apply default Janua middleware stack
    middleware_stack = get_middleware_stack()
    for middleware_class, kwargs in middleware_stack:
        app.add_middleware(middleware_class, **kwargs)

    return app


class JanuaMiddlewareConfig:
    """Configuration class for Janua middleware."""

    def __init__(
        self,
        enable_rate_limiting: bool = True,
        enable_security_headers: bool = True,
        enable_logging: bool = True,
        enable_cors: bool = True,
        enable_trusted_host: bool = True,
        custom_cors_origins: List[str] = None,
        custom_allowed_hosts: List[str] = None,
    ):
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_security_headers = enable_security_headers
        self.enable_logging = enable_logging
        self.enable_cors = enable_cors
        self.enable_trusted_host = enable_trusted_host
        self.custom_cors_origins = custom_cors_origins
        self.custom_allowed_hosts = custom_allowed_hosts

    def get_middleware_stack(self) -> List[tuple]:
        """Get middleware stack based on configuration."""
        settings = get_settings()
        middleware_stack = []

        if self.enable_security_headers:
            middleware_stack.append((SecurityHeadersMiddleware, {}))

        if self.enable_rate_limiting:
            middleware_stack.append((RateLimitMiddleware, {}))

        if self.enable_logging:
            middleware_stack.append((LoggingMiddleware, {}))

        if self.enable_cors:
            cors_origins = self.custom_cors_origins or settings.CORS_ORIGINS
            middleware_stack.append((
                CORSMiddleware,
                {
                    "allow_origins": cors_origins,
                    "allow_credentials": True,
                    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                    "allow_headers": [
                        "Authorization",
                        "Content-Type",
                        "X-Requested-With",
                        "X-API-Key",
                        "X-Organization-ID",
                        "X-Tenant-ID",
                    ],
                }
            ))

        if self.enable_trusted_host:
            allowed_hosts = self.custom_allowed_hosts or (
                ["*"] if settings.DEBUG else [settings.DOMAIN]
            )
            middleware_stack.append((
                TrustedHostMiddleware,
                {"allowed_hosts": allowed_hosts}
            ))

        return middleware_stack


def create_janua_app(
    title: str = "Janua Application",
    description: str = "Application powered by Janua",
    version: str = "1.0.0",
    middleware_config: JanuaMiddlewareConfig = None,
    **fastapi_kwargs
) -> FastAPI:
    """
    Create a FastAPI application with Janua middleware and configuration.

    Args:
        title: Application title
        description: Application description
        version: Application version
        middleware_config: Custom middleware configuration
        **fastapi_kwargs: Additional FastAPI constructor arguments

    Returns:
        Configured FastAPI application with Janua middleware
    """
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        **fastapi_kwargs
    )

    # Apply middleware stack
    if middleware_config:
        middleware_stack = middleware_config.get_middleware_stack()
        for middleware_class, kwargs in middleware_stack:
            app.add_middleware(middleware_class, **kwargs)
    else:
        apply_middleware_stack(app)

    return app