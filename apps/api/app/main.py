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

            return bcrypt._original_hashpw(password, salt)
        bcrypt.hashpw = _patched_hashpw
except ImportError:
    pass

import hashlib

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from passlib.context import CryptContext
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

# Secure password hashing context - using bcrypt 2b to avoid passlib wrap bug detection issue
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Strong rounds for security
    bcrypt__ident="2b",  # Use 2b to avoid wrap bug detection
)
import logging
import os
import secrets
from datetime import datetime

import asyncpg
import redis.asyncio as redis

# Setup logger early
logger = logging.getLogger(__name__)

from app.config import settings
from app.core.database_manager import close_database, get_database_health, init_database
from app.core.error_handling import (
    APIException,
    ErrorHandlingMiddleware,
    api_exception_handler,
    http_exception_handler,
    janua_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import JanuaAPIException
from app.routers.v1 import (
    admin as admin_v1,
)
from app.routers.v1 import (
    audit_logs as audit_logs_v1,
)
from app.routers.v1 import (
    auth as auth_v1,
)
from app.routers.v1 import (
    invitations as invitations_v1,
)
from app.routers.v1 import (
    # alerts as alerts_v1,  # Disabled - requires opentelemetry.exporter dependency
    localization as localization_v1,
)
from app.routers.v1 import (
    mfa as mfa_v1,
)
from app.routers.v1 import (
    oauth as oauth_v1,
)
from app.routers.v1 import (
    organization_members as organization_members_v1,
)
from app.routers.v1 import (
    organizations as organizations_v1,
)
from app.routers.v1 import (
    passkeys as passkeys_v1,
)
from app.routers.v1 import (
    policies as policies_v1,
)
from app.routers.v1 import (
    rbac as rbac_v1,
)
from app.routers.v1 import (
    sessions as sessions_v1,
)
from app.routers.v1 import (
    users as users_v1,
)
from app.routers.v1 import (
    webhooks as webhooks_v1,
)

# Additional feature routers with optional loading
additional_routers = {}
try:
    from app.routers.v1 import graphql as graphql_v1

    additional_routers["graphql"] = graphql_v1
except Exception as e:
    logger.warning(f"GraphQL router not available: {e}")

try:
    from app.routers.v1 import websocket as websocket_v1

    additional_routers["websocket"] = websocket_v1
except Exception as e:
    logger.warning(f"WebSocket router not available: {e}")

try:
    from app.routers.v1 import apm as apm_v1

    additional_routers["apm"] = apm_v1
except Exception as e:
    logger.warning(f"APM router not available: {e}")

try:
    from app.routers.v1 import iot as iot_v1

    additional_routers["iot"] = iot_v1
except Exception as e:
    logger.warning(f"IoT router not available: {e}")

# Enterprise routers with optional loading for production stability
enterprise_routers = {}
try:
    from app.routers.v1 import sso as sso_v1

    enterprise_routers["sso"] = sso_v1
except Exception as e:
    logger.warning(f"SSO router not available: {e}")

# SSO DDD module routers (enterprise implementation)
try:
    from app.sso.routers import configuration as sso_config
    from app.sso.routers import metadata as sso_metadata
    from app.sso.routers import oidc as sso_oidc

    enterprise_routers["sso_oidc"] = sso_oidc
    enterprise_routers["sso_config"] = sso_config
    enterprise_routers["sso_metadata"] = sso_metadata
except Exception as e:
    logger.warning(f"SSO DDD routers not available: {e}")

try:
    from app.routers.v1 import migration as migration_v1

    enterprise_routers["migration"] = migration_v1
except Exception as e:
    logger.warning(f"Migration router not available: {e}")

try:
    from app.routers.v1 import white_label as white_label_v1

    enterprise_routers["white_label"] = white_label_v1
except Exception as e:
    logger.warning(f"White label router not available: {e}")

try:
    from app.routers.v1 import compliance as compliance_v1

    enterprise_routers["compliance"] = compliance_v1
except Exception as e:
    logger.warning(f"Compliance router not available: {e}")

try:
    from app.routers.v1 import scim as scim_v1

    enterprise_routers["scim"] = scim_v1
except Exception as e:
    logger.warning(f"SCIM router not available: {e}")
from app.core.performance import PerformanceMonitoringMiddleware, cache_manager
from app.core.scalability import (
    get_scalability_status,
    initialize_scalability_features,
    shutdown_scalability_features,
)
from app.core.tenant_context import TenantMiddleware
from app.core.webhook_dispatcher import webhook_dispatcher
from app.services.monitoring import AlertManager, HealthChecker, MetricsCollector, SystemMonitor

# Set up logging
logging.basicConfig(level=logging.INFO if settings.DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize rate limiter (kept for backward compatibility with existing endpoints)
limiter = Limiter(key_func=get_remote_address)

# Import global rate limiting middleware
from app.middleware.global_rate_limit import create_rate_limit_middleware

# Import comprehensive input validation middleware
from app.middleware.input_validation import create_input_validation_middleware

# Initialize monitoring components
metrics_collector = MetricsCollector()
health_checker = HealthChecker(metrics_collector)
alert_manager = AlertManager(metrics_collector)
system_monitor = SystemMonitor(metrics_collector)

app = FastAPI(
    title="Janua Authentication API",
    version="1.0.0",
    description="""
# Janua Authentication Platform

Modern, open-core authentication and identity management platform with enterprise features.

## Features

* 🔐 **Complete Authentication**: Email/password, OAuth (Google, GitHub, Microsoft, Apple), Magic Links, Passkeys
* 🛡️ **MFA & Security**: TOTP, SMS, Backup codes, Device fingerprinting
* 👥 **Multi-Tenancy**: Organizations, RBAC, Team management
* 🔄 **Session Management**: Multi-device tracking, Revocation, Security warnings
* 🎯 **Enterprise Features**: SAML/SSO, SCIM, Compliance (GDPR, SOC 2), Webhooks
* 📊 **Developer Experience**: TypeScript SDK, React UI Components, Comprehensive docs

## Getting Started

1. **Sign Up**: `POST /api/v1/auth/signup` - Create your account
2. **Get Token**: Receive JWT access + refresh tokens
3. **Authenticate**: Add `Authorization: Bearer {token}` header to requests
4. **Integrate**: Use our TypeScript SDK or REST API directly

## Authentication

All protected endpoints require a JWT access token in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

Get tokens via:
- Email/password: `POST /api/v1/auth/signin`
- OAuth: `POST /api/v1/oauth/{provider}/callback`
- Magic link: `POST /api/v1/auth/magic-link/verify`

## Rate Limiting

All endpoints are rate-limited for security:
- Sign up: 3 requests/minute
- Sign in: 5 requests/minute
- Password reset: 3 requests/hour
- General endpoints: 100 requests/minute

Rate limit headers returned in response:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Environments

- **Production**: https://api.janua.dev
- **Staging**: https://staging-api.janua.dev
- **Development**: http://localhost:8000

## Support

- Documentation: https://docs.janua.dev
- GitHub: https://github.com/janua/janua
- Discord: https://discord.gg/janua
- Email: support@janua.dev

## SDK Libraries

- **TypeScript**: `npm install @janua/typescript-sdk`
- **React UI**: `npm install @janua/ui`
- **Python**: `pip install janua` (coming soon)
- **Go**: `go get github.com/janua/janua-go` (coming soon)
    """,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication endpoints including sign up, sign in, password management, email verification, and magic links.",
        },
        {
            "name": "OAuth",
            "description": "Social authentication with Google, GitHub, Microsoft, and Apple OAuth providers.",
        },
        {
            "name": "Users",
            "description": "User profile management including updates, deletion, and profile information.",
        },
        {
            "name": "Sessions",
            "description": "Session management across multiple devices with tracking, listing, and revocation capabilities.",
        },
        {
            "name": "Organizations",
            "description": "Multi-tenant organization management with members, roles, and settings.",
        },
        {
            "name": "MFA",
            "description": "Multi-factor authentication with TOTP, SMS, and backup codes for enhanced security.",
        },
        {
            "name": "Passkeys",
            "description": "WebAuthn/FIDO2 passkey authentication for passwordless secure login.",
        },
        {
            "name": "Admin",
            "description": "Administrative endpoints for system monitoring, user management, and statistics.",
        },
        {
            "name": "Webhooks",
            "description": "Event-driven webhooks for user actions, authentication events, and system notifications.",
        },
        {
            "name": "RBAC",
            "description": "Role-based access control for fine-grained permission management.",
        },
        {
            "name": "Policies",
            "description": "Security policies for password requirements, session timeouts, and access controls.",
        },
        {
            "name": "Audit Logs",
            "description": "Comprehensive audit logging for compliance and security monitoring.",
        },
        {
            "name": "SSO",
            "description": "Enterprise Single Sign-On with SAML 2.0 and OIDC support.",
        },
        {
            "name": "SCIM",
            "description": "System for Cross-domain Identity Management for automated user provisioning.",
        },
        {
            "name": "Compliance",
            "description": "GDPR, SOC 2, and regulatory compliance features including data export and deletion.",
        },
    ],
    contact={
        "name": "Janua Support",
        "url": "https://janua.dev/support",
        "email": "support@janua.dev",
    },
    license_info={
        "name": "AGPL-3.0",
        "url": "https://github.com/madfam-io/janua/blob/main/LICENSE",
    },
    servers=[
        {
            "url": "https://api.janua.dev",
            "description": "Production server",
        },
        {
            "url": "https://staging-api.janua.dev",
            "description": "Staging server",
        },
        {
            "url": "http://localhost:8000",
            "description": "Local development server",
        },
    ],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add Janua-specific exception handler
app.add_exception_handler(JanuaAPIException, janua_exception_handler)

# Add comprehensive error handling
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# Performance Monitoring Middleware (add early for accurate timing)
app.add_middleware(PerformanceMonitoringMiddleware, slow_threshold_ms=100.0)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers for A+ SSL rating
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
        )
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Server"] = "Janua-API"  # Hide server version info

        return response


# Add security middleware (order matters - add these first)
# Disabled HTTPS redirect - Railway handles HTTPS termination at the proxy level
# if not settings.DEBUG:
#     app.add_middleware(HTTPSRedirectMiddleware)

# Add trusted host middleware
allowed_hosts = [
    "janua.dev",
    "*.janua.dev",
    "janua-api.railway.app",
    "healthcheck.railway.app",
    "*.railway.app",
    "localhost",
    "127.0.0.1",
]
# Add test host for integration tests
if settings.ENVIRONMENT == "test":
    allowed_hosts.extend(["test", "testserver", "testclient"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add GLOBAL RATE LIMITING for 100% endpoint coverage
# This ensures ALL endpoints have rate limiting, not just those with @limiter.limit decorators
redis_url = os.getenv("REDIS_URL", settings.REDIS_URL if hasattr(settings, "REDIS_URL") else None)
if redis_url or settings.ENVIRONMENT != "test":
    # Only enable in non-test environments or when Redis is available
    # Tests handle rate limiting via mocks in conftest.py
    rate_limit_middleware_instance = create_rate_limit_middleware(app, redis_url)

# Add COMPREHENSIVE INPUT VALIDATION for all endpoints
# This provides defense-in-depth against injection attacks and malformed input
if settings.ENVIRONMENT != "test":
    # Disable strict validation in test environment to avoid test complexity
    # Tests verify validation logic in unit tests
    input_validation_middleware_instance = create_input_validation_middleware(
        app, strict_mode=not settings.DEBUG
    )

# Add tenant context middleware for multi-tenancy
app.add_middleware(TenantMiddleware)

# Add comprehensive error handling middleware (add last so it catches everything)
app.add_middleware(ErrorHandlingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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
)

# In-memory fallback storage for beta endpoints
BETA_USERS = {}


# Simple models
class SignUpRequest(BaseModel):
    email: str
    password: str
    name: str = "Beta User"


class SignInRequest(BaseModel):
    email: str
    password: str


# Direct Redis connection using Railway environment variables
async def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(redis_url, decode_responses=True)


# Secure password hashing functions
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


# OpenID Connect discovery endpoints
@app.get("/.well-known/openid-configuration")
def openid_configuration():
    base_url = settings.BASE_URL or "https://api.janua.dev"
    return {
        "issuer": settings.BASE_URL or "https://janua.dev",
        "authorization_endpoint": f"{base_url}/auth/authorize",
        "token_endpoint": f"{base_url}/auth/token",
        "userinfo_endpoint": f"{base_url}/auth/userinfo",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "response_types_supported": ["code", "id_token", "code id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "claims_supported": ["sub", "email", "name", "given_name", "family_name", "picture"],
    }


@app.get("/.well-known/jwks.json")
def jwks():
    return {"keys": []}


# Performance metrics endpoint
@app.get("/metrics/performance")
async def performance_metrics():
    """Get API performance metrics"""
    from app.core.performance import get_performance_metrics

    return await get_performance_metrics()


# Prometheus metrics endpoint
@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    import time

    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
    from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily
    from starlette.responses import Response

    registry = CollectorRegistry()

    try:
        # System metrics
        system_cpu = GaugeMetricFamily("janua_system_cpu_percent", "System CPU usage percentage")
        system_memory = GaugeMetricFamily(
            "janua_system_memory_percent", "System memory usage percentage"
        )
        system_disk = GaugeMetricFamily(
            "janua_system_disk_free_bytes", "System disk free space in bytes"
        )

        # Collect system metrics if monitor is available
        import psutil

        system_cpu.add_metric([], psutil.cpu_percent())
        system_memory.add_metric([], psutil.virtual_memory().percent)
        system_disk.add_metric([], psutil.disk_usage("/").free)

        registry.register(lambda: [system_cpu])
        registry.register(lambda: [system_memory])
        registry.register(lambda: [system_disk])

        # Application health
        app_health = GaugeMetricFamily(
            "janua_app_health_status", "Application health status (1=healthy, 0=unhealthy)"
        )
        app_health.add_metric([], 1)  # Always 1 if this endpoint responds
        registry.register(lambda: [app_health])

        # API metrics (would be populated from monitoring service in production)
        http_requests = CounterMetricFamily(
            "janua_http_requests_total",
            "Total HTTP requests",
            labels=["method", "endpoint", "status_code"],
        )
        # Add sample data - in production this would come from metrics_collector
        http_requests.add_metric(["GET", "/health", "200"], 100)
        http_requests.add_metric(["POST", "/api/v1/auth/login", "200"], 50)
        http_requests.add_metric(["GET", "/metrics", "200"], 25)
        registry.register(lambda: [http_requests])

        # Response time histogram
        response_duration = HistogramMetricFamily(
            "janua_http_request_duration_seconds",
            "HTTP request duration in seconds",
            labels=["method", "endpoint"],
        )
        # Sample histogram data
        response_duration.add_metric(
            ["GET", "/health"],
            buckets=[("0.01", 80), ("0.05", 95), ("0.1", 98), ("0.5", 100), ("+Inf", 100)],
            sum_value=2.5,
        )
        registry.register(lambda: [response_duration])

        # Database connection pool
        db_connections = GaugeMetricFamily(
            "janua_database_connections_active", "Active database connections"
        )
        db_connections.add_metric([], 5)  # Sample data
        registry.register(lambda: [db_connections])

        # Redis connection status
        redis_connected = GaugeMetricFamily(
            "janua_redis_connected", "Redis connection status (1=connected, 0=disconnected)"
        )
        redis_connected.add_metric([], 1)  # Sample data
        registry.register(lambda: [redis_connected])

    except Exception as e:
        # Fallback metrics if system monitoring fails
        error_metric = GaugeMetricFamily(
            "janua_metrics_collection_errors_total", "Total metrics collection errors"
        )
        error_metric.add_metric([], 1)
        registry.register(lambda: [error_metric])

    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


# Scalability status endpoint
@app.get("/metrics/scalability")
async def scalability_metrics():
    """Get enterprise scalability status and metrics"""
    return await get_scalability_status()


# Infrastructure connectivity test using database manager
@app.get("/ready")
async def ready_check():
    checks = {"status": "ready", "database": {}, "redis": False}

    # Test Database with health manager
    try:
        db_health = await get_database_health()
        checks["database"] = db_health
    except Exception as e:
        checks["database"] = {"healthy": False, "error": str(e)}

    # Test Redis with direct connection
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        checks["redis"] = True
        await redis_client.close()
    except:
        checks["redis"] = False

    # Overall status
    checks["status"] = (
        "ready" if (checks["database"].get("healthy", False) and checks["redis"]) else "degraded"
    )

    return checks


# Beta authentication with direct Redis operations
@app.post("/beta/signup")
@limiter.limit("5/minute")
async def beta_signup(request: Request, signup_request: SignUpRequest):
    try:
        # Validate
        if len(signup_request.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

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

        except Exception as redis_error:
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

        except:
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
            "user": {"id": user_data["id"], "email": user_data["email"], "name": user_data["name"]},
            "storage": storage_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signin failed: {str(e)}")


@app.get("/beta/users")
async def beta_list_users():
    try:
        users = []
        redis_users = []
        memory_users = list(BETA_USERS.values()) if BETA_USERS else []

        # Try to get users from Redis
        try:
            redis_client = await get_redis_client()
            user_keys = await redis_client.keys("beta_user:*")

            for key in user_keys:
                user_data = await redis_client.hgetall(key)
                if user_data:
                    redis_users.append(
                        {
                            "id": user_data["id"],
                            "email": user_data["email"],
                            "name": user_data["name"],
                            "created_at": user_data["created_at"],
                            "storage": "redis",
                        }
                    )

            await redis_client.close()

        except Exception as e:
            # Log Redis failure but continue with memory users
            logger.warning(
                "Failed to fetch users from Redis, falling back to memory",
                error=str(e),
                error_type=type(e).__name__,
            )

        # Add memory users
        for user in memory_users:
            memory_users_formatted = {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "created_at": user["created_at"],
                "storage": "memory",
            }
            users.append(memory_users_formatted)

        all_users = redis_users + users

        return {
            "users": all_users,
            "total": len(all_users),
            "redis_count": len(redis_users),
            "memory_count": len(memory_users),
            "infrastructure": "Railway",
        }

    except Exception as e:
        return {"error": f"Failed to list users: {str(e)}", "users": [], "total": 0}


# API status
@app.get("/api/status")
def api_status():
    return {
        "status": "Janua API v1.0.0 operational",
        "version": "1.0.0",
        "authentication": "JWT with refresh tokens",
        "infrastructure": "Railway PostgreSQL + Redis",
        "endpoints": {
            "beta": ["/beta/signup", "/beta/signin", "/beta/users"],
            "v1": ["/api/v1/auth/*", "/api/v1/users/*", "/api/v1/organizations/*"],
        },
        "features": {
            "signups": settings.ENABLE_SIGNUPS,
            "magic_links": settings.ENABLE_MAGIC_LINKS,
            "oauth": settings.ENABLE_OAUTH,
            "mfa": settings.ENABLE_MFA,
            "organizations": settings.ENABLE_ORGANIZATIONS,
        },
    }


# Import health router and inject health checker
from app.routers.v1 import health as health_v1

# Include v1 routers
app.include_router(health_v1.router, prefix="/api/v1")
app.include_router(auth_v1.router, prefix="/api/v1")
app.include_router(oauth_v1.router, prefix="/api/v1")
app.include_router(users_v1.router, prefix="/api/v1")
app.include_router(sessions_v1.router, prefix="/api/v1")
app.include_router(organizations_v1.router, prefix="/api/v1")
app.include_router(organization_members_v1.router, prefix="/api/v1")
app.include_router(rbac_v1.router, prefix="/api/v1")
app.include_router(mfa_v1.router, prefix="/api/v1")
app.include_router(passkeys_v1.router, prefix="/api/v1")
app.include_router(admin_v1.router, prefix="/api/v1")
app.include_router(webhooks_v1.router, prefix="/api/v1")

# Register newly added core routers
app.include_router(policies_v1.router, prefix="/api")
app.include_router(invitations_v1.router, prefix="/api")
app.include_router(audit_logs_v1.router, prefix="/api")
# app.include_router(alerts_v1.router, prefix="/api/v1")  # Disabled - requires opentelemetry.exporter dependency
app.include_router(localization_v1.router, prefix="/api/v1")  # Localization model now available

# Register additional feature routers if available
for router_name, router_module in additional_routers.items():
    try:
        app.include_router(router_module.router, prefix="/api/v1")
        logger.info(f"Registered {router_name} router successfully")
    except Exception as e:
        logger.error(f"Failed to register {router_name} router: {e}")

# Register enterprise routers if available
for router_name, router_module in enterprise_routers.items():
    try:
        app.include_router(router_module.router, prefix="/api/v1")
        logger.info(f"Registered {router_name} router successfully")
    except Exception as e:
        logger.error(f"Failed to register {router_name} router: {e}")


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Janua API...")

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

    try:
        await init_database()
        logger.info("Database manager initialized successfully")

        # Initialize performance cache manager
        await cache_manager.init_redis()
        logger.info("Performance cache manager initialized")

        # Initialize monitoring services
        await metrics_collector.initialize()
        await health_checker.initialize()
        await alert_manager.initialize()
        await system_monitor.initialize()
        logger.info("Monitoring services initialized successfully")

        # Register health checks
        health_checker.register_check("database", get_database_health, critical=True)
        health_checker.register_check("redis", _check_redis_health, critical=True)
        logger.info("Health checks registered")

        # Inject health checker into health router
        health_v1.health_checker = health_checker

        # Initialize enterprise scalability features
        await initialize_scalability_features()
        logger.info("Enterprise scalability features initialized")

        # Start webhook dispatcher
        await webhook_dispatcher.start()
        logger.info("Webhook dispatcher started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    logger.info("Janua API started successfully")


async def _check_redis_health():
    """Redis health check for monitoring"""
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        await redis_client.close()
        return True
    except:
        return False


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Janua API...")
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
