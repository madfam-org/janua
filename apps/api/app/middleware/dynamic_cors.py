"""
Dynamic CORS Middleware
Loads CORS origins from both configuration and database.
Supports multi-tenant origins (system-level + organization-level).
"""

import logging
import time
from typing import List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level cache for CORS origins
_cors_origins_cache: Optional[Set[str]] = None
_cors_cache_timestamp: float = 0
CORS_CACHE_TTL_SECONDS = 60  # Refresh every minute


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    CORS middleware that supports dynamic origin loading from database.

    Origins are loaded from:
    1. Config file (CORS_ORIGINS environment variable) - always included
    2. Database system_settings table (if enabled)
    3. Database allowed_cors_origins table (if enabled)

    Caches origins with TTL for performance.
    """

    def __init__(
        self,
        app: ASGIApp,
        allow_credentials: bool = True,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        expose_headers: List[str] = None,
        max_age: int = 600,
        enable_database_origins: bool = True,
    ):
        super().__init__(app)
        self.allow_credentials = allow_credentials
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.expose_headers = expose_headers or []
        self.max_age = max_age
        self.enable_database_origins = enable_database_origins

        # Initialize with config origins
        self._static_origins = set(settings.cors_origins_list)
        logger.info(
            f"DynamicCORSMiddleware initialized with {len(self._static_origins)} config origins"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        """Handle CORS preflight and actual requests"""
        origin = request.headers.get("origin")

        # No origin header = not a CORS request
        if not origin:
            return await call_next(request)

        # Get allowed origins (from cache or fresh)
        allowed_origins = await self._get_allowed_origins()

        # Check if origin is allowed
        origin_allowed = self._is_origin_allowed(origin, allowed_origins)

        # Handle preflight (OPTIONS) request
        if request.method == "OPTIONS":
            response = Response(status_code=204)
            if origin_allowed:
                self._add_cors_headers(response, origin)
            return response

        # Handle actual request
        response = await call_next(request)

        if origin_allowed:
            self._add_cors_headers(response, origin)

        return response

    def _is_origin_allowed(self, origin: str, allowed_origins: Set[str]) -> bool:
        """Check if origin is in allowed list"""
        # Exact match
        if origin in allowed_origins:
            return True

        # Wildcard match (e.g., *.janua.dev)
        for allowed in allowed_origins:
            if allowed.startswith("*."):
                domain = allowed[2:]  # Remove "*."
                # Check if origin ends with the domain (e.g., sub.janua.dev matches *.janua.dev)
                origin_domain = origin.replace("https://", "").replace("http://", "")
                if origin_domain.endswith(domain) or origin_domain == domain.lstrip("."):
                    return True

        return False

    def _add_cors_headers(self, response: Response, origin: str):
        """Add CORS headers to response"""
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = str(self.allow_credentials).lower()

        if self.allow_methods:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)

        if self.allow_headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)

        if self.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)

        response.headers["Access-Control-Max-Age"] = str(self.max_age)

        # Add Vary header for proper caching
        vary = response.headers.get("Vary", "")
        if "Origin" not in vary:
            response.headers["Vary"] = f"{vary}, Origin".strip(", ") if vary else "Origin"

    async def _get_allowed_origins(self) -> Set[str]:
        """Get allowed origins from cache or fresh load"""
        global _cors_origins_cache, _cors_cache_timestamp

        current_time = time.time()

        # Check cache validity
        if (
            _cors_origins_cache is not None
            and (current_time - _cors_cache_timestamp) < CORS_CACHE_TTL_SECONDS
        ):
            return _cors_origins_cache

        # Reload origins
        origins = set(self._static_origins)

        # Load from database if enabled
        if self.enable_database_origins:
            try:
                db_origins = await self._load_database_origins()
                origins.update(db_origins)
            except Exception as e:
                logger.warning(f"Failed to load CORS origins from database: {e}")

        # Update cache
        _cors_origins_cache = origins
        _cors_cache_timestamp = current_time

        return origins

    async def _load_database_origins(self) -> Set[str]:
        """Load CORS origins from database"""
        from app.core.database import get_db_session
        from sqlalchemy import select

        origins = set()

        try:
            async with get_db_session() as db:
                # Import here to avoid circular imports
                from app.models.system_settings import AllowedCorsOrigin

                # Load active system-level origins (organization_id is NULL)
                result = await db.execute(
                    select(AllowedCorsOrigin.origin)
                    .where(AllowedCorsOrigin.is_active == True)
                    .where(AllowedCorsOrigin.organization_id.is_(None))
                )

                for row in result.scalars().all():
                    if row:
                        origins.add(row)

                logger.debug(f"Loaded {len(origins)} CORS origins from database")

        except Exception as e:
            # Log but don't fail - database might not have the table yet
            logger.debug(f"Could not load CORS origins from database: {e}")

        return origins


def invalidate_cors_cache():
    """
    Invalidate the CORS origins cache.
    Call this when origins are added/removed via API.
    """
    global _cors_origins_cache, _cors_cache_timestamp
    _cors_origins_cache = None
    _cors_cache_timestamp = 0
    logger.info("CORS origins cache invalidated")


def get_cors_cache_status() -> dict:
    """Get current CORS cache status for debugging"""
    global _cors_origins_cache, _cors_cache_timestamp

    current_time = time.time()
    age = current_time - _cors_cache_timestamp if _cors_cache_timestamp else None

    return {
        "cached": _cors_origins_cache is not None,
        "origins_count": len(_cors_origins_cache) if _cors_origins_cache else 0,
        "cache_age_seconds": age,
        "cache_ttl_seconds": CORS_CACHE_TTL_SECONDS,
        "cache_valid": age is not None and age < CORS_CACHE_TTL_SECONDS,
    }


def create_dynamic_cors_middleware(app: ASGIApp) -> DynamicCORSMiddleware:
    """
    Factory function to create DynamicCORSMiddleware with standard config.
    """
    return DynamicCORSMiddleware(
        app,
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
            "X-Requested-With",
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
