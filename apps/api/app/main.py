from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
import structlog
import time

from app.config import settings
from app.auth.router import router as auth_router
from app.core.database import init_db
from app.core.redis import init_redis
from app.core.errors import (
    PlintoAPIException,
    plinto_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Plinto API", version=settings.VERSION, env=settings.ENVIRONMENT)
    
    # Initialize database
    await init_db()
    
    # Initialize Redis
    await init_redis()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Plinto API")


# Create FastAPI app
app = FastAPI(
    title="Plinto API",
    description="Secure identity platform API",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure allowed hosts - be permissive for Railway health checks
if settings.ENVIRONMENT == "production":
    # In production, allow Railway patterns but be permissive for health checks
    allowed_hosts = ["*"]  # Railway health checks come from internal IPs
else:
    # For development
    allowed_hosts = ["localhost", "127.0.0.1", ".plinto.dev", "*"]

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


# Simple test endpoint for debugging JSON parsing
@app.post("/test-json")
async def test_json(data: dict):
    """Simple test endpoint to verify JSON parsing works"""
    return {"received": data}


# Ready check
@app.get("/ready")
async def ready_check():
    """Health check endpoint with database and Redis connectivity"""
    from app.core.database import engine
    from app.core.redis import redis_client
    
    checks = {
        "status": "ready",
        "database": False,
        "redis": False
    }
    
    # Check database connectivity
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # Check Redis connectivity
    try:
        if redis_client:
            await redis_client.ping()
            checks["redis"] = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
    
    # Overall status
    if not all([checks["database"], checks["redis"]]):
        checks["status"] = "degraded"
    
    return checks


# JWKS endpoint
@app.get("/.well-known/jwks.json")
async def get_jwks():
    """Return JSON Web Key Set for token verification"""
    try:
        # For now, return empty JWKS until proper JWT key management is implemented
        # This prevents the 500 error while maintaining OpenID Connect compliance
        return {
            "keys": []
        }
    except Exception as e:
        logger.error("JWKS endpoint error", error=str(e))
        return {
            "keys": []
        }


# OpenID Configuration
@app.get("/.well-known/openid-configuration")
async def get_openid_configuration():
    base_url = settings.BASE_URL
    return {
        "issuer": settings.JWT_ISSUER,
        "authorization_endpoint": f"{base_url}/auth/authorize",
        "token_endpoint": f"{base_url}/auth/token",
        "userinfo_endpoint": f"{base_url}/auth/userinfo",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "response_types_supported": ["code", "token", "id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "claims_supported": ["sub", "name", "email", "email_verified", "picture"]
    }


# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


# Register error handlers
app.add_exception_handler(PlintoAPIException, plinto_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)