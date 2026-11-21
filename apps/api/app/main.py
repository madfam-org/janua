# Fix passlib/bcrypt 5.x compatibility issue BEFORE any imports
# This must be at the very top of the file
import os

os.environ["PASSLIB_BUILTIN_BCRYPT"] = "enabled"

# Patch bcrypt to handle the wrap bug detection issue with bcrypt >= 4.1
try:
    import bcrypt

    if not hasattr(bcrypt, "_original_hashpw"):
        bcrypt._original_hashpw = bcrypt.hashpw

        def _patched_hashpw(password, salt):
            if isinstance(password, str):
                password = password.encode("utf-8")
            if len(password) > 72:
                password = password[:72]
            return bcrypt._original_hashpw(password, salt)

        bcrypt.hashpw = _patched_hashpw
except ImportError:
    pass  # bcrypt not installed, passlib will use fallback implementation

# Initialize Sentry early, before other imports
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.environ.get(
                "SENTRY_ENVIRONMENT", os.environ.get("ENVIRONMENT", "development")
            ),
            traces_sample_rate=0.1,
            integrations=[FastApiIntegration()],
        )
    except ImportError:
        pass  # sentry-sdk not installed



from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from passlib.context import CryptContext
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.rate_limit_keys import client_ip_key
from app.main_middleware import install_middleware
from app.main_openapi import API_METADATA

# Secure password hashing context - using bcrypt 2b to avoid passlib wrap bug detection issue
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Strong rounds for security
    bcrypt__ident="2b",  # Use 2b to avoid wrap bug detection
)
import asyncio
import logging
import os
import secrets
from datetime import datetime

import redis.asyncio as redis

# Setup logger early
logger = logging.getLogger(__name__)

from app.config import settings
from app.core.database_manager import close_database, get_database_health, init_database
from app.core.error_handling import (
    APIException,
    api_exception_handler,
    http_exception_handler,
    janua_exception_handler,
    rate_limit_exceeded_handler,
    redis_unavailable_handler,
    validation_exception_handler,
)
from app.core.exceptions import JanuaAPIException
from app.core.oauth_metadata import authorization_server_metadata
from app.core.performance import cache_manager
from app.core.redis import get_redis, get_redis_public_status
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.core.scalability import (
    get_scalability_status,
    initialize_scalability_features,
    shutdown_scalability_features,
)
from app.core.webhook_dispatcher import webhook_dispatcher

# Routers: imported here (same import order as before the split), included below.
from app.main_routers import include_routers  # noqa: E402
from app.services.monitoring import (
    AlertManager,
    HealthChecker,
    MetricsCollector,
    SystemMonitor,
    redact_error_text,
)

# Set up logging
logging.basicConfig(level=logging.INFO if settings.DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize rate limiter (kept for backward compatibility with existing endpoints)
limiter = Limiter(key_func=client_ip_key)

# Import global rate limiting middleware

# Import comprehensive input validation middleware

# Initialize monitoring components
metrics_collector = MetricsCollector()
health_checker = HealthChecker(metrics_collector)
alert_manager = AlertManager(metrics_collector)
system_monitor = SystemMonitor(metrics_collector)

app = FastAPI(**API_METADATA)
app.state.limiter = limiter
# A browser navigation on a hosted route gets the hosted 429 page, not slowapi's body.
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add Janua-specific exception handler
app.add_exception_handler(JanuaAPIException, janua_exception_handler)

# Add comprehensive error handling
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
# Strict Redis operations (OAuth consent/authorize/token security state) answer a
# retryable 503 instead of silently degrading — see redis_unavailable_handler.
app.add_exception_handler(RedisUnavailableError, redis_unavailable_handler)

install_middleware(app)


# Direct Redis connection using Railway environment variables
async def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(redis_url, decode_responses=True)


# Beta endpoint support (only when ENABLE_BETA_ENDPOINTS=true)
# SECURITY: These are disabled by default and should only be used for development/testing
if settings.ENABLE_BETA_ENDPOINTS:
    # In-memory fallback storage for beta endpoints
    BETA_USERS: dict = {}

    # Simple models for beta endpoints
    class SignUpRequest(BaseModel):
        email: str
        password: str
        name: str = "Beta User"

    class SignInRequest(BaseModel):
        email: str
        password: str

    # Secure password hashing functions for beta endpoints
    def hash_password(password: str) -> str:
        """Hash password using bcrypt with salt"""
        return pwd_context.hash(password)

    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against bcrypt hash"""
        return pwd_context.verify(password, hashed)


# Root endpoint
@app.get("/")
def root():
    return {"status": "ok", "message": "Ultra-minimal beta API", "version": "0.1.0"}


# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.VERSION, "environment": settings.ENVIRONMENT}


# Test endpoints for debugging
@app.get("/test")
def test_endpoint():
    return {"status": "test endpoint working", "auth_router_included": True}


@app.post("/test-json")
async def test_json_endpoint(data: dict):
    return {"received": data}


# OpenID Connect discovery and RFC 8414 authorization-server metadata.
# One document, two well-known paths (app/core/oauth_metadata.py): MCP clients
# such as Claude read /.well-known/oauth-authorization-server first, OIDC
# relying parties read /.well-known/openid-configuration.
@app.get("/.well-known/openid-configuration")
def openid_configuration():
    """
    OpenID Connect Discovery endpoint.

    Returns the OIDC provider configuration document (OpenID Connect
    Discovery 1.0). Used by clients to automatically configure OAuth2/OIDC
    integration. The issuer and every endpoint use JANUA_CUSTOM_DOMAIN when it
    is set (white-label deployments like auth.madfam.io), else API_BASE_URL.
    """
    return authorization_server_metadata()


@app.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server():
    """
    OAuth 2.0 Authorization Server Metadata (RFC 8414).

    The same document as the OpenID configuration. The issuer has no path
    component, so this is the only RFC 8414 well-known location.
    """
    return authorization_server_metadata()


@app.get("/.well-known/jwks.json")
def jwks():
    """
    JSON Web Key Set (JWKS) endpoint for public key distribution.
    Used by edge workers and clients to verify JWT signatures.
    """
    from app.core.jwt_manager import jwt_manager

    return jwt_manager.get_jwks()


# ---------------------------------------------------------------------------
# Metrics auth guard
#
# /metrics/performance and /metrics/scalability (JSON, on the public app)
# disclose endpoint inventory, latency profiles, and per-path call counters
# (including paths probed by attackers). Public exposure on
# api.janua.dev is an information-disclosure risk, so we gate them
# behind a service-to-service token distinct from user auth.
#
# Prometheus text is not served on the public app at all: see the internal
# metrics listener (app/monitoring/metrics_server.py, METRICS_PORT 9464).
#
# Set METRICS_TOKEN in the API deployment env; callers must send it as
# `Authorization: Bearer <METRICS_TOKEN>`.
# If METRICS_TOKEN is unset (e.g., local dev), the endpoints are open
# only when ENVIRONMENT in {"development", "test"}; in any other
# environment an unset token causes a 404 (fail-closed).
# ---------------------------------------------------------------------------
def _require_metrics_token(request: Request) -> None:
    expected = os.getenv("METRICS_TOKEN", "").strip()
    if not expected:
        # Fail-open only in non-prod-like environments.
        if settings.ENVIRONMENT in {"development", "test"}:
            return
        # Treat as not-configured -> 404 to avoid signalling existence.
        raise HTTPException(status_code=404, detail="Not Found")

    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        # 404 (not 401) so unauthenticated probes cannot fingerprint /metrics*.
        raise HTTPException(status_code=404, detail="Not Found")

    presented = auth.split(" ", 1)[1].strip()
    if not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=404, detail="Not Found")


# Performance metrics endpoint
@app.get("/metrics/performance", dependencies=[Depends(_require_metrics_token)])
async def performance_metrics():
    """Get API performance metrics"""
    from app.core.performance import get_performance_metrics

    return await get_performance_metrics()


# Prometheus exposition is NOT served here. The public app (8080) has no
# /metrics route; the real default registry is served by the internal-only
# listener on METRICS_PORT (9464), started in startup_event below. See
# app/monitoring/metrics_server.py.


# Scalability status endpoint
@app.get("/metrics/scalability", dependencies=[Depends(_require_metrics_token)])
async def scalability_metrics():
    """Get enterprise scalability status and metrics"""
    return await get_scalability_status()


# Infrastructure connectivity summary. Unauthenticated, so it publishes status
# fields only (J4-002): the database and Redis checks below never return error
# text, hostnames or DSNs; the detail goes to the server log, redacted. Same
# rules and fields as /api/v1/health/ready (see READINESS_REPORTED_ONLY there):
# it reports the database and Redis and answers 200 while they are down.
@app.get("/ready")
async def ready_check():
    database_healthy = await _check_database_health()
    # THIS process's own Redis client (the one every request uses), bounded:
    # a fresh connection can succeed while this replica's client is broken.
    redis_healthy = await _check_redis_health()

    degraded = [
        name
        for name, healthy in (("database", database_healthy), ("redis", redis_healthy))
        if not healthy
    ]
    return {
        "status": "degraded" if degraded else "ready",
        "database": {
            "healthy": database_healthy,
            "status": "healthy" if database_healthy else "unhealthy",
        },
        "redis": redis_healthy,
        # Per-pod breaker state: state, last failure time and counters only.
        "redis_circuit": get_redis_public_status(),
        "degraded": degraded,
    }


# Beta endpoints - SECURITY: Gated behind ENABLE_BETA_ENDPOINTS flag
# These endpoints bypass standard auth flows and should only be enabled for development/testing
# NOTE: /beta/users endpoint has been REMOVED entirely (major security risk - lists all users)
if settings.ENABLE_BETA_ENDPOINTS:
    logger.warning(
        "⚠️  SECURITY WARNING: Beta endpoints are ENABLED. "
        "These bypass standard authentication and should only be used for development/testing."
    )

    @app.post("/beta/signup")
    @limiter.limit("5/minute")
    async def beta_signup(request: Request, signup_request: SignUpRequest):
        try:
            # Validate
            if len(signup_request.password) < 8:
                raise HTTPException(
                    status_code=400, detail="Password must be at least 8 characters"
                )

            # Try Redis first, fallback to memory
            user_id = secrets.token_hex(16)
            user_data = {
                "id": user_id,
                "email": signup_request.email,
                "name": signup_request.name,
                "password_hash": hash_password(signup_request.password),
                "created_at": datetime.utcnow().isoformat(),
            }

            try:
                redis_client = await get_redis_client()
                user_key = f"beta_user:{signup_request.email}"

                # Check if exists
                if await redis_client.exists(user_key):
                    await redis_client.close()
                    raise HTTPException(status_code=400, detail="User already exists")

                # Store in Redis
                await redis_client.hset(user_key, mapping=user_data)
                await redis_client.expire(user_key, 30 * 24 * 60 * 60)  # 30 days
                await redis_client.close()

                return {
                    "id": user_id,
                    "email": signup_request.email,
                    "name": signup_request.name,
                    "message": "User created in Railway Redis",
                    "storage": "redis",
                }

            except Exception:
                # Fallback to memory storage
                if signup_request.email in BETA_USERS:
                    raise HTTPException(status_code=400, detail="User already exists")

                BETA_USERS[signup_request.email] = user_data

                return {
                    "id": user_id,
                    "email": signup_request.email,
                    "name": signup_request.name,
                    "message": "User created in memory (Redis fallback)",
                    "storage": "memory",
                }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

    @app.post("/beta/signin")
    @limiter.limit("10/minute")
    async def beta_signin(request: Request, signin_request: SignInRequest):
        try:
            user_data = None
            storage_type = "unknown"

            # Try Redis first
            try:
                redis_client = await get_redis_client()
                user_key = f"beta_user:{signin_request.email}"
                user_data = await redis_client.hgetall(user_key)
                await redis_client.close()

                if user_data:
                    storage_type = "redis"

            except Exception:
                # Fallback to memory
                user_data = BETA_USERS.get(signin_request.email)
                if user_data:
                    storage_type = "memory"

            if not user_data:
                raise HTTPException(status_code=401, detail="Invalid credentials")

            # Verify password
            if not verify_password(signin_request.password, user_data["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            # Create simple token
            access_token = secrets.token_hex(32)

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_data["id"],
                    "email": user_data["email"],
                    "name": user_data["name"],
                },
                "storage": storage_type,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Signin failed: {str(e)}")


# API status
@app.get("/api/status")
def api_status():
    # Build beta endpoints list dynamically based on feature flag
    beta_endpoints = []
    if settings.ENABLE_BETA_ENDPOINTS:
        beta_endpoints = ["/beta/signup", "/beta/signin"]

    return {
        "status": "Janua API v0.1.0 operational",
        "version": "0.1.0",
        "authentication": "JWT with refresh tokens",
        "infrastructure": "Railway PostgreSQL + Redis",
        "endpoints": {
            "beta": beta_endpoints,
            "v1": ["/api/v1/auth/*", "/api/v1/users/*", "/api/v1/organizations/*"],
        },
        "features": {
            "signups": settings.ENABLE_SIGNUPS,
            "magic_links": settings.ENABLE_MAGIC_LINKS,
            "oauth": settings.ENABLE_OAUTH,
            "mfa": settings.ENABLE_MFA,
            "organizations": settings.ENABLE_ORGANIZATIONS,
            "beta_endpoints": settings.ENABLE_BETA_ENDPOINTS,
        },
    }


include_routers(app)
# The startup hook injects the health checker into the health router.
from app.routers.v1 import health as health_v1  # noqa: E402


def _start_metrics_listener() -> None:
    """Start the internal-only Prometheus listener (METRICS_PORT, default 9464).

    Fatal on misconfiguration or a failed bind, unlike the degraded-mode
    blocks in startup_event: a pod that serves traffic but no metrics reads as
    down to every `up` alert. Skipped under ENVIRONMENT=test, where tests
    start their own listener on an ephemeral port.
    """
    if settings.ENVIRONMENT == "test":
        return
    from app.monitoring.metrics_server import resolve_metrics_port, start_metrics_server

    metrics_port = resolve_metrics_port()
    app.state.metrics_server = start_metrics_server(metrics_port)
    logger.info(f"Metrics listener serving GET /metrics on port {metrics_port}")


def _stop_metrics_listener() -> None:
    metrics_server = getattr(app.state, "metrics_server", None)
    if metrics_server is not None:
        metrics_server.close()
        app.state.metrics_server = None


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Janua API...")

    _start_metrics_listener()

    # Initialize PostHog analytics (no-op if POSTHOG_API_KEY is not set)
    from app.analytics import init_posthog

    init_posthog()

    # CRITICAL: Validate SECRET_KEY in production
    if settings.ENVIRONMENT == "production":
        default_secret = "development-secret-key-change-in-production"
        if settings.SECRET_KEY == default_secret:
            logger.critical(
                "FATAL: Using default SECRET_KEY in production! This is a critical security vulnerability."
            )
            raise RuntimeError(
                "Production deployment detected with default SECRET_KEY. "
                "Set SECRET_KEY environment variable to a secure random value. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        logger.info("✅ SECRET_KEY validation passed")

    # Validate JWT_SECRET_KEY if set
    if hasattr(settings, "JWT_SECRET_KEY") and settings.JWT_SECRET_KEY:
        if settings.ENVIRONMENT == "production" and len(settings.JWT_SECRET_KEY) < 32:
            logger.critical("FATAL: JWT_SECRET_KEY too weak for production (minimum 32 characters)")
            raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters in production")
        logger.info("✅ JWT_SECRET_KEY validation passed")

    # Database and Redis initialization — non-fatal so the app can start
    # and serve /health (degraded) even if DB/Redis are temporarily unavailable.
    try:
        await init_database()
        logger.info("Database manager initialized successfully")

        # Bootstrap admin user if ADMIN_BOOTSTRAP_PASSWORD is set
        from app.core.database import bootstrap_admin_user

        await bootstrap_admin_user()
    except Exception as e:
        logger.error(f"Database initialization failed (app will start degraded): {e}")

    try:
        # Initialize performance cache manager
        await cache_manager.init_redis()
        logger.info("Performance cache manager initialized")
    except Exception as e:
        logger.error(f"Redis initialization failed (app will start degraded): {e}")

    try:
        # Initialize monitoring services
        await metrics_collector.initialize()
        await health_checker.initialize()
        await alert_manager.initialize()
        await system_monitor.initialize()
        logger.info("Monitoring services initialized successfully")

        # Register health checks
        # critical=True keeps /health/detailed honest ("unhealthy" while the
        # database or Redis is down). The readiness probe reports both checks
        # but gates on neither: see READINESS_REPORTED_ONLY in
        # routers/v1/health.py.
        health_checker.register_check("database", _check_database_health, critical=True)
        health_checker.register_check("redis", _check_redis_health, critical=True)
        logger.info("Health checks registered")

        # Inject health checker into health router
        health_v1.health_checker = health_checker

        # SOC 2 CF-09: Register encryption key health check
        health_checker.register_check(
            "encryption_key", health_v1.check_encryption_key_health, critical=False
        )

        # Initialize enterprise scalability features
        await initialize_scalability_features()
        logger.info("Enterprise scalability features initialized")

        # Start webhook dispatcher
        await webhook_dispatcher.start()
        logger.info("Webhook dispatcher started successfully")
    except Exception as e:
        logger.error(f"Service initialization failed (app will start degraded): {e}")
    logger.info("Janua API started successfully")


# Each dependency check the readiness probe runs is bounded. The kubelet gives
# the probe 5 s (`timeoutSeconds`, k8s/base/deployments/janua-api.yaml) and the
# checks run one after another. A dependency that hangs instead of refusing
# (a dropped route, a full connection pool) would otherwise outlast the probe,
# and a probe that times out counts as failed: the pod would leave the Service
# even though the check is only reported. A check that times out reports
# "unhealthy".
READINESS_CHECK_TIMEOUT_SECONDS = 2.0


async def _check_database_health() -> bool:
    """Can this replica reach the database right now? Reported, not gated.

    `get_database_health()` returns a dict whose `healthy` says whether a
    `SELECT 1` succeeded; only `healthy is True` counts (J3-001: the dict
    itself is always truthy, so the check used to report `healthy` through
    every outage). Owner decision 2026-10-04: readiness reports the database
    but does not gate on it, so JWKS, discovery and health stay up during a
    database outage while database-backed routes fail on their own (see
    READINESS_REPORTED_ONLY in routers/v1/health.py). Bounded by
    READINESS_CHECK_TIMEOUT_SECONDS. No error text leaves this function.
    """
    try:
        result = await asyncio.wait_for(get_database_health(), READINESS_CHECK_TIMEOUT_SECONDS)
    except Exception as e:  # includes the timeout
        logger.warning(
            "Database health check failed: %s: %s", type(e).__name__, redact_error_text(str(e))
        )
        return False
    healthy = isinstance(result, dict) and result.get("healthy") is True
    if not healthy:
        detail = result.get("error", "") if isinstance(result, dict) else ""
        # Server-side only, redacted (J4-002); callers publish the bool.
        logger.warning("Database health check unhealthy: %s", redact_error_text(str(detail)))
    return healthy


async def _check_redis_health():
    """Can THIS replica's own Redis client reach Redis right now?

    Reported by the readiness probe, not gated on (owner decision 2026-10-04;
    see READINESS_REPORTED_ONLY in routers/v1/health.py).

    Deliberately not "is the breaker closed": a strict PING through the pod's
    own client reports what matters (this replica cannot reach Redis, whether
    Redis is down or only this replica's client is broken) and recovers on the
    next probe. The strict ping also moves an OPEN breaker to half-open, so a
    replica stops serving fallbacks within one probe period of Redis answering
    again; the readiness probe keeps running it every period for that reason.
    """

    async def ping() -> None:
        await (await get_redis()).strict_ping()

    try:
        # Bounded (READINESS_CHECK_TIMEOUT_SECONDS): the client's own connect
        # timeout (REDIS_CONNECTION_TIMEOUT, 5 s by default) equals the probe's.
        await asyncio.wait_for(ping(), READINESS_CHECK_TIMEOUT_SECONDS)
        return True
    except Exception as e:
        logger.debug("Redis ping check failed: %s", type(e).__name__)
        return False


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Janua API...")

    _stop_metrics_listener()

    # Flush pending PostHog events
    from app.analytics import shutdown as posthog_shutdown

    posthog_shutdown()

    try:
        # Graceful shutdown of scalability features
        await shutdown_scalability_features()
        logger.info("Enterprise scalability features shutdown")

        # Stop webhook dispatcher
        await webhook_dispatcher.stop()
        logger.info("Webhook dispatcher stopped")

        # Close monitoring services (they have internal cleanup tasks)
        # The monitoring services will automatically stop their background tasks
        logger.info("Monitoring services stopped")

        # Close cache manager
        await cache_manager.close_redis()
        logger.info("Performance cache manager closed")

        await close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    logger.info("Janua API shutdown complete")


def create_app(
    title: str = "Janua API",
    description: str = "Modern authentication and identity platform API",
    version: str = "1.0.0",
    **kwargs,
) -> FastAPI:
    """
    Create and configure a FastAPI application with Janua authentication.

    Args:
        title: Application title
        description: Application description
        version: Application version
        **kwargs: Additional FastAPI constructor arguments

    Returns:
        FastAPI: Configured FastAPI application
    """
    # Return the existing configured app instance
    # In a production package, this would be refactored to create a new instance
    app.title = title
    app.description = description
    app.version = version

    # Apply any additional kwargs
    for key, value in kwargs.items():
        if hasattr(app, key):
            setattr(app, key, value)

    return app
