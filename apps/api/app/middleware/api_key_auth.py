"""
API Key Authentication Middleware

Intercepts requests carrying an API key (via X-API-Key header or
Authorization: Bearer sk_live_*) and resolves them to org_id + scopes
before the request reaches the route handler.

If a valid API key is found:
  - Injects X-Org-Id, X-Scopes, X-Key-Id headers into the request
  - Enforces per-key rate limiting (rate_limit_per_min column)
  - Lets the request continue to the route handler

If the key is invalid or revoked: returns 401.
If the key is rate-limited: returns 429.
If no API key is present: passes through so JWT auth can handle it.

Must be registered BEFORE DynamicCORSMiddleware in main.py so that
the injected headers are available to route handlers.
"""

import hashlib
import logging
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# In-memory sliding-window rate limiter keyed by key_id.
# For production scale, replace with Redis-backed counters.
_rate_limit_buckets: Dict[str, list] = defaultdict(list)

# Paths that should never be intercepted by API key auth
SKIP_PATHS = frozenset({
    "/health",
    "/health/detailed",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/.well-known/openid-configuration",
    "/.well-known/jwks.json",
    "/metrics",
    "/metrics/performance",
    "/metrics/scalability",
    "/api/v1/api-keys/verify",
})

# Prefixes that should also be skipped
SKIP_PREFIXES = (
    "/docs",
    "/redoc",
)

# Key prefix that identifies a modern sk_live_ key in a Bearer token
SK_LIVE_PREFIX = "sk_live_"


def _extract_api_key(request: Request) -> Optional[str]:
    """
    Extract an API key from the request.

    Checks in order:
    1. X-API-Key header
    2. Authorization: Bearer sk_live_* (only if the token starts with sk_live_)

    Returns the plain key string, or None if no API key is present.
    """
    # 1. Explicit header
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()

    # 2. Bearer token that looks like an API key (sk_live_ or jnk_ prefix)
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token.startswith(SK_LIVE_PREFIX) or token.startswith("jnk_"):
            return token

    return None


def _check_rate_limit(key_id: str, limit_per_min: int) -> Tuple[bool, int]:
    """
    Sliding-window rate limiter (in-memory).

    Returns:
        (allowed: bool, retry_after_seconds: int)
    """
    now = time.monotonic()
    window_start = now - 60.0

    # Prune old entries
    bucket = _rate_limit_buckets[key_id]
    _rate_limit_buckets[key_id] = [t for t in bucket if t > window_start]
    bucket = _rate_limit_buckets[key_id]

    if len(bucket) >= limit_per_min:
        # Find when the oldest entry in the window will expire
        retry_after = int(bucket[0] - window_start) + 1
        return False, max(retry_after, 1)

    bucket.append(now)
    return True, 0


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that authenticates requests bearing API keys.

    Injects X-Org-Id, X-Scopes, and X-Key-Id headers on success so that
    downstream route handlers can extract the caller identity without
    hitting the database again.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Skip paths that should not be intercepted
        path = request.url.path.rstrip("/")
        if path in SKIP_PATHS or any(path.startswith(p) for p in SKIP_PREFIXES):
            return await call_next(request)

        # Try to extract an API key
        plain_key = _extract_api_key(request)
        if not plain_key:
            # No API key present -- fall through to JWT auth
            return await call_next(request)

        # Resolve the key against the database
        try:
            from app.database import get_db

            async for db in get_db():
                try:
                    from app.services.api_key_service import ApiKeyService

                    service = ApiKeyService(db)
                    api_key = await service.verify_key_for_service(plain_key)
                finally:
                    # Ensure session is returned to pool
                    await db.close()
        except Exception:
            logger.exception("Failed to verify API key")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal error during API key verification"},
            )

        if api_key is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or revoked API key"},
            )

        # Enforce per-key rate limit
        rate_limit = api_key.rate_limit_per_min or 60
        allowed, retry_after = _check_rate_limit(str(api_key.id), rate_limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded for this API key"},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Inject identity headers into the request scope so route handlers
        # can read them via request.headers.
        scopes_csv = ",".join(api_key.scopes or [])
        headers = dict(request.scope["headers"])
        # Starlette stores headers as list of (name_bytes, value_bytes) tuples
        extra_headers = [
            (b"x-org-id", str(api_key.organization_id).encode()),
            (b"x-scopes", scopes_csv.encode()),
            (b"x-key-id", str(api_key.id).encode()),
        ]
        request.scope["headers"] = list(request.scope["headers"]) + extra_headers

        response = await call_next(request)

        # Add rate limit info to response headers
        remaining = max(0, rate_limit - len(_rate_limit_buckets.get(str(api_key.id), [])))
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
