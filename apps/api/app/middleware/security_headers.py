"""Security Headers Middleware for Janua API"""
from typing import Callable

import structlog
from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.protected_resources import protected_resource_redirect_origins

logger = structlog.get_logger()

#: "https://claude.ai " — space-terminated, ready to splice into form-action.
_PROTECTED_RESOURCE_FORM_ACTIONS = "".join(
    f"{origin} " for origin in protected_resource_redirect_origins()
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    def __init__(self, app, strict: bool = True, api_host: str = "api.janua.dev"):
        super().__init__(app)
        self.strict = strict
        self.api_host = api_host

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
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com",  # For Swagger UI + CF Insights
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # For Swagger UI
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            f"connect-src 'self' https://{self.api_host} https://cloudflareinsights.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            # form-action: applies to entire redirect chain, including the
            # final destination after OAuth callback redirects. The login
            # form posts to /api/v1/auth/login-form, which 302s to the
            # OAuth authorize endpoint, which 302s to the registered
            # client redirect_uri (e.g. https://app.enclii.dev/auth/callback).
            # If the final URL isn't in this list, Chrome blocks the entire
            # form submit silently (the "Sign In does nothing" UX bug).
            #
            # OAuth clients are registered in the database with their
            # validated redirect_uris; rather than dynamically reading
            # all of them on every request, we list the trusted parent
            # domains here. The OAuth authorize endpoint still validates
            # the specific redirect_uri against the client's registered
            # list — this CSP entry just permits the browser to follow.
            f"form-action 'self' https://{self.api_host} "
            "https://*.enclii.dev https://*.madfam.io https://*.dhan.am "
            "https://*.tezca.mx https://*.karafiel.mx "
            # 2026-08-26: forgesight migrated forgesight.quest -> forgesight.app.
            # 2026-08-27: the .quest registration EXPIRED and the zone is
            # retired. Its form-action entry is removed and must not be
            # restored: an expired domain in a form-action allowlist lets a
            # re-registrant receive OAuth form submissions from auth.madfam.io.
            "https://forgesight.app https://*.forgesight.app "
            "https://*.fortuna.tube https://*.avala.studio "
            "https://*.cotiza.studio https://*.almanac.solar https://*.yantra4d.com "
            "https://*.coforma.studio https://*.routecraft.app https://*.solar "
            # 2026-05-04: added the remaining MADFAM ecosystem domains. Login
            # via Janua SSO from these origins was browser-blocked by CSP
            # form-action because the post-login redirect URL wasn't in the
            # allowlist. Same bug class as the forgesight CORS regression
            # fixed earlier (PR enclii#228 for CORS_ORIGINS).
            "https://selva.town https://*.selva.town "
            "https://rondel.io https://*.rondel.io "
            "https://phyndcrm.com https://*.phyndcrm.com "
            "https://pravara.mx https://*.pravara.mx "
            "https://sim4d.io https://*.sim4d.io "
            "https://aureo.studio https://*.aureo.studio "
            "https://ceq.studio https://*.ceq.studio "
            "https://4d-admin.madfam.io https://sniper.madfam.io "
            # 2026-09-06: the Crea Tu Mundo brand zone. The MAP and the ERP
            # portal also serve on map./erp.creatumundo.mx; a hosted-login
            # POST 302s to those hosts, and form-action applies to the whole
            # post-submit redirect chain, so without them the browser blocks
            # the submit silently (same bug class as the enclii/forgesight
            # regressions above).
            "https://creatumundo.mx https://*.creatumundo.mx "
            # 2026-10: the exact redirect URIs of the protected-resource
            # client policies (app/core/protected_resources.py) — today
            # https://claude.ai, where the MAP connector's consent POST 302s.
            # Derived from the registry so a callback added there cannot be
            # forgotten here ("Permitir" would silently do nothing).
            f"{_PROTECTED_RESOURCE_FORM_ACTIONS}http://127.0.0.1:* http://localhost:*",
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

        # Hide server version info
        response.headers["Server"] = "Janua-API"

        return response
