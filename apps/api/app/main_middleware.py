"""Middleware setup of the API application (split out of app/main.py).

Moved verbatim on 2026-11-19 to keep app/main.py under the repository's
800-line pre-commit limit; no behaviour change. `app.main` calls
`install_middleware(app)` at the point where these statements ran, so the
middleware stack and its order are unchanged.
"""

import os
from urllib.parse import urlparse

from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.core.error_handling import ErrorHandlingMiddleware
from app.core.performance import PerformanceMonitoringMiddleware
from app.core.tenant_context import TenantMiddleware
from app.middleware.global_rate_limit import create_rate_limit_middleware
from app.middleware.input_validation import create_input_validation_middleware


def install_middleware(app) -> None:
    """Add the API's middleware to `app`, in the order app/main.py always used."""
    # Performance Monitoring Middleware (add early for accurate timing)
    app.add_middleware(PerformanceMonitoringMiddleware, slow_threshold_ms=100.0)


    # Import standalone security headers middleware
    from app.middleware.security_headers import SecurityHeadersMiddleware

    # Add security middleware (order matters - add these first)
    # Disabled HTTPS redirect - Railway handles HTTPS termination at the proxy level
    # if not settings.DEBUG:
    #     app.add_middleware(HTTPSRedirectMiddleware)

    # Add trusted host middleware
    # Port 4100 per PORT_ALLOCATION.md in solarpunk-foundry (Janua block: 4100-4199)
    #
    # In Kubernetes environments (behind reverse proxy/ingress), host validation is
    # handled at the network layer. Use TRUST_ALL_HOSTS=true to allow all hosts.
    # This is safe because:
    # 1. Cloudflare tunnel handles external host validation
    # 2. K8s NetworkPolicy restricts internal access
    # 3. Health probes come from various internal IPs
    trust_all_hosts = os.getenv("TRUST_ALL_HOSTS", "false").lower() == "true"

    if trust_all_hosts:
        allowed_hosts = ["*"]
    else:
        allowed_hosts = [
            "janua.dev",
            "*.janua.dev",
            "api.janua.dev",
            "docs.janua.dev",
            "localhost",
            "localhost:4100",
            "localhost:8080",
            "127.0.0.1",
            "127.0.0.1:4100",
            "127.0.0.1:8080",
            # Docker internal hostnames for container-to-container communication
            "janua-api",
            "janua-api:4100",
            "janua-api:8080",
            # Kubernetes internal networking (service names)
            "janua-api.janua.svc.cluster.local",
            "janua-api.janua.svc.cluster.local:4100",
            "janua-api.janua.svc.cluster.local:8080",
        ]
        # Add custom domain aliases from environment (e.g., auth.madfam.io for MADFAM deployment)
        custom_domain = os.getenv("JANUA_CUSTOM_DOMAIN")
        if custom_domain:
            allowed_hosts.extend(
                [
                    custom_domain,
                    f"*.{custom_domain.split('.', 1)[-1] if '.' in custom_domain else custom_domain}",
                ]
            )
        # First-party tracking hosts (e.g. enlaces.creatumundo.mx), one per sender
        # binding with a tracking origin configured. Trusted here so /e/o and /e/c
        # answer on them; TrackingHostScopeMiddleware (below) keeps them to that.
        from app.services.sender_binding import tracking_bindings

        allowed_hosts.extend(tracking_bindings().keys())
        # Add test host for integration tests
        if settings.ENVIRONMENT == "test":
            allowed_hosts.extend(["test", "testserver", "testclient"])

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # A tracking host serves ONLY the first-party pixel and click redirect: trusting
    # it above is global, so without this it would also serve sign-in, password
    # reset and OIDC discovery under a tenant's marketing domain. Fixed at startup,
    # like the list above; applies with TRUST_ALL_HOSTS too.
    from app.middleware.tracking_host_scope import TrackingHostScopeMiddleware
    from app.services.sender_binding import tracking_bindings as _tracking_bindings

    app.add_middleware(TrackingHostScopeMiddleware, hosts=_tracking_bindings().keys())

    # Add security headers middleware (CSP connect-src uses the configured API host)
    _api_host = settings.JANUA_CUSTOM_DOMAIN or urlparse(settings.API_BASE_URL).netloc
    app.add_middleware(SecurityHeadersMiddleware, api_host=_api_host)

    # Add GLOBAL RATE LIMITING for 100% endpoint coverage
    # This ensures ALL endpoints have rate limiting, not just those with @limiter.limit decorators
    redis_url = os.getenv("REDIS_URL", settings.REDIS_URL if hasattr(settings, "REDIS_URL") else None)
    if redis_url or settings.ENVIRONMENT != "test":
        # Only enable in non-test environments or when Redis is available
        # Tests handle rate limiting via mocks in conftest.py
        create_rate_limit_middleware(app, redis_url)

    # Add COMPREHENSIVE INPUT VALIDATION for all endpoints
    # This provides defense-in-depth against injection attacks and malformed input
    if settings.ENVIRONMENT != "test":
        # Disable strict validation in test environment to avoid test complexity
        # Tests verify validation logic in unit tests
        create_input_validation_middleware(app, strict_mode=not settings.DEBUG)

    # Add tenant context middleware for multi-tenancy
    app.add_middleware(TenantMiddleware)

    # Add comprehensive error handling middleware (add last so it catches everything)
    app.add_middleware(ErrorHandlingMiddleware)

    # API Key Authentication Middleware (must be registered BEFORE CORS)
    # Intercepts X-API-Key / Bearer sk_live_* and injects X-Org-Id, X-Scopes, X-Key-Id
    from app.middleware.api_key_auth import ApiKeyAuthMiddleware

    app.add_middleware(ApiKeyAuthMiddleware)

    # Configure Dynamic CORS (loads origins from config + database)
    # This supports multi-tenant CORS origins managed via Admin API
    from app.middleware.dynamic_cors import DynamicCORSMiddleware

    app.add_middleware(
        DynamicCORSMiddleware,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-API-Key",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Mx-ReqToken",
            "Keep-Alive",
            "If-Modified-Since",
            "X-CSRF-Token",
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=600,
        enable_database_origins=True,
    )
