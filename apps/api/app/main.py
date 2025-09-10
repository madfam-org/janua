from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
import structlog
import time
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

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
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger()

# Initialize Sentry for error tracking
if SENTRY_AVAILABLE and settings.ENVIRONMENT in ["production", "staging"]:
    sentry_dsn = getattr(settings, "SENTRY_DSN", None)
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=settings.ENVIRONMENT,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% of transactions for profiling
            send_default_pii=False,  # Don't send personally identifiable information
            attach_stacktrace=True,
            before_send=lambda event, hint: event if settings.ENVIRONMENT == "production" else None,
        )
        logger.info("Sentry error tracking initialized")
    else:
        logger.warning("Sentry DSN not configured - error tracking disabled")


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

# Security headers middleware (add first so it applies to all responses)
app.add_middleware(SecurityHeadersMiddleware, strict=settings.ENVIRONMENT == "production")

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# CORS middleware - properly configured for production
cors_origins = [
    "https://plinto.dev",
    "https://www.plinto.dev",
    "https://app.plinto.dev",
    "https://demo.plinto.dev",
    "https://docs.plinto.dev",
    "https://admin.plinto.dev",
]

if settings.ENVIRONMENT == "development":
    cors_origins.extend([
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:4000",
        "http://localhost:8000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
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


# Test endpoints for debugging
@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify routing works"""
    return {"status": "test endpoint working", "auth_router_included": True}

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


# JWKS endpoint - simplified implementation
@app.get("/.well-known/jwks.json")  
def get_jwks():
    """Return JSON Web Key Set for token verification"""
    # Return empty JWKS for now - this is valid according to RFC 7517
    # In a real implementation, this would contain public keys for JWT verification
    return {"keys": []}


# OpenID Configuration
@app.get("/.well-known/openid-configuration")
async def get_openid_configuration():
    # Ensure proper BASE_URL with multiple fallbacks
    base_url = settings.BASE_URL
    if not base_url or base_url.strip() == "":
        base_url = "https://api.plinto.dev"
    # Remove trailing slash if present
    base_url = base_url.rstrip("/")
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