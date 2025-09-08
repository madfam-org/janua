"""
Plinto Core API - FastAPI Application
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import Database
from app.cache import RedisCache
from app.routers import (
    auth_router,
    identities_router,
    sessions_router,
    passkeys_router,
    organizations_router,
    policies_router,
    webhooks_router,
    audit_router,
    health_router
)
from app.middleware import (
    RequestIdMiddleware,
    TenantContextMiddleware,
    SecurityHeadersMiddleware,
    MetricsMiddleware
)
from app.exceptions import PlintoException, handle_plinto_exception

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    """
    # Startup
    logger.info("Starting Plinto API", version=settings.VERSION)
    
    # Initialize database
    app.state.db = Database(settings.DATABASE_URL)
    await app.state.db.connect()
    
    # Initialize Redis cache
    app.state.redis = RedisCache(settings.REDIS_URL)
    await app.state.redis.connect()
    
    # Run migrations if needed
    if settings.AUTO_MIGRATE:
        logger.info("Running database migrations")
        # await run_migrations()
    
    logger.info("Plinto API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Plinto API")
    
    await app.state.db.disconnect()
    await app.state.redis.disconnect()
    
    logger.info("Plinto API shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="Plinto Identity Platform",
    description="Secure substrate for identity - Edge-fast verification with full control",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/api/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/api/openapi.json" if settings.ENABLE_DOCS else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-RateLimit-*"],
)

# Add custom middleware
app.add_middleware(RequestIdMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Exception handlers
app.add_exception_handler(PlintoException, handle_plinto_exception)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unexpected errors
    """
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        request_id=getattr(request.state, "request_id", None)
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )

# Include routers
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(identities_router, prefix="/api/v1/identities", tags=["identities"])
app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(passkeys_router, prefix="/api/v1/passkeys", tags=["passkeys"])
app.include_router(organizations_router, prefix="/api/v1/organizations", tags=["organizations"])
app.include_router(policies_router, prefix="/api/v1/policies", tags=["policies"])
app.include_router(webhooks_router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(audit_router, prefix="/api/v1/audit", tags=["audit"])

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "name": "Plinto Identity Platform",
        "version": settings.VERSION,
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

# Well-known endpoints
@app.get("/.well-known/jwks.json")
async def get_jwks():
    """
    JWKS endpoint for token verification
    """
    from app.services.jwk_service import JWKService
    jwk_service = JWKService(app.state.db, app.state.redis)
    return await jwk_service.get_public_keys()

@app.get("/.well-known/openid-configuration")
async def get_openid_configuration():
    """
    OpenID Connect discovery endpoint
    """
    return {
        "issuer": settings.JWT_ISSUER,
        "authorization_endpoint": f"{settings.BASE_URL}/api/v1/auth/authorize",
        "token_endpoint": f"{settings.BASE_URL}/api/v1/auth/token",
        "userinfo_endpoint": f"{settings.BASE_URL}/api/v1/auth/userinfo",
        "jwks_uri": f"{settings.BASE_URL}/.well-known/jwks.json",
        "registration_endpoint": f"{settings.BASE_URL}/api/v1/auth/register",
        "scopes_supported": ["openid", "profile", "email", "phone"],
        "response_types_supported": ["code", "token", "id_token"],
        "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "claims_supported": [
            "sub", "iss", "aud", "exp", "iat", "auth_time",
            "email", "email_verified", "phone", "phone_verified",
            "name", "given_name", "family_name", "picture"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )