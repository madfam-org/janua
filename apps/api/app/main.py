from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
import hashlib
from passlib.context import CryptContext

# Secure password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Strong rounds for security
)
import secrets
import os
import redis.asyncio as redis
import asyncpg
from datetime import datetime
import logging

from app.config import settings
from app.core.database_manager import init_database, close_database, get_database_health
from app.core.error_handling import (
    ErrorHandlingMiddleware,
    APIException,
    api_exception_handler,
    validation_exception_handler,
    http_exception_handler
)
from app.routers.v1 import (
    auth as auth_v1,
    oauth as oauth_v1,
    users as users_v1,
    sessions as sessions_v1,
    organizations as organizations_v1,
    mfa as mfa_v1,
    passkeys as passkeys_v1,
    admin as admin_v1,
    webhooks as webhooks_v1,
    # sso as sso_v1,  # TODO: Re-enable once dependency injection is configured
    migration as migration_v1,
    white_label as white_label_v1,
    compliance as compliance_v1,
    iot as iot_v1,
    localization as localization_v1,
    scim as scim_v1
)
from app.core.tenant_context import TenantMiddleware
from app.core.webhook_dispatcher import webhook_dispatcher
from app.core.performance import PerformanceMonitoringMiddleware, cache_manager
from app.core.scalability import initialize_scalability_features, shutdown_scalability_features, get_scalability_status
from app.services.monitoring import MetricsCollector, HealthChecker, AlertManager, SystemMonitor

# Set up logging
logging.basicConfig(level=logging.INFO if settings.DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize monitoring components
metrics_collector = MetricsCollector()
health_checker = HealthChecker(metrics_collector)
alert_manager = AlertManager(metrics_collector)
system_monitor = SystemMonitor(metrics_collector)

app = FastAPI(
    title="Plinto API",
    version="1.0.0",
    description="Modern authentication and identity platform API",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Server"] = "Plinto-API"  # Hide server version info
        
        return response

# Add security middleware (order matters - add these first)
if not settings.DEBUG:
    # Only redirect to HTTPS in production
    app.add_middleware(HTTPSRedirectMiddleware)

# Add trusted host middleware 
allowed_hosts = ["plinto.dev", "*.plinto.dev", "plinto-api.railway.app", "localhost", "127.0.0.1"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add tenant context middleware for multi-tenancy
app.add_middleware(TenantMiddleware)

# Add comprehensive error handling middleware (add last so it catches everything)
app.add_middleware(ErrorHandlingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"status": "healthy"}

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
    from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
    from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily
    from starlette.responses import Response
    import time
    
    registry = CollectorRegistry()
    
    try:
        # System metrics
        system_cpu = GaugeMetricFamily(
            'plinto_system_cpu_percent',
            'System CPU usage percentage'
        )
        system_memory = GaugeMetricFamily(
            'plinto_system_memory_percent', 
            'System memory usage percentage'
        )
        system_disk = GaugeMetricFamily(
            'plinto_system_disk_free_bytes',
            'System disk free space in bytes'
        )
        
        # Collect system metrics if monitor is available
        import psutil
        system_cpu.add_metric([], psutil.cpu_percent())
        system_memory.add_metric([], psutil.virtual_memory().percent)
        system_disk.add_metric([], psutil.disk_usage('/').free)
        
        registry.register(lambda: [system_cpu])
        registry.register(lambda: [system_memory])
        registry.register(lambda: [system_disk])
        
        # Application health
        app_health = GaugeMetricFamily(
            'plinto_app_health_status',
            'Application health status (1=healthy, 0=unhealthy)'
        )
        app_health.add_metric([], 1)  # Always 1 if this endpoint responds
        registry.register(lambda: [app_health])
        
        # API metrics (would be populated from monitoring service in production)
        http_requests = CounterMetricFamily(
            'plinto_http_requests_total',
            'Total HTTP requests',
            labels=['method', 'endpoint', 'status_code']
        )
        # Add sample data - in production this would come from metrics_collector
        http_requests.add_metric(['GET', '/health', '200'], 100)
        http_requests.add_metric(['POST', '/api/v1/auth/login', '200'], 50)
        http_requests.add_metric(['GET', '/metrics', '200'], 25)
        registry.register(lambda: [http_requests])
        
        # Response time histogram
        response_duration = HistogramMetricFamily(
            'plinto_http_request_duration_seconds',
            'HTTP request duration in seconds',
            labels=['method', 'endpoint']
        )
        # Sample histogram data
        response_duration.add_metric(['GET', '/health'], buckets=[
            ('0.01', 80), ('0.05', 95), ('0.1', 98), ('0.5', 100), ('+Inf', 100)
        ], sum_value=2.5)
        registry.register(lambda: [response_duration])
        
        # Database connection pool
        db_connections = GaugeMetricFamily(
            'plinto_database_connections_active',
            'Active database connections'
        )
        db_connections.add_metric([], 5)  # Sample data
        registry.register(lambda: [db_connections])
        
        # Redis connection status
        redis_connected = GaugeMetricFamily(
            'plinto_redis_connected',
            'Redis connection status (1=connected, 0=disconnected)'
        )
        redis_connected.add_metric([], 1)  # Sample data
        registry.register(lambda: [redis_connected])
        
    except Exception as e:
        # Fallback metrics if system monitoring fails
        error_metric = GaugeMetricFamily(
            'plinto_metrics_collection_errors_total',
            'Total metrics collection errors'
        )
        error_metric.add_metric([], 1)
        registry.register(lambda: [error_metric])
    
    return Response(
        generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )

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
    checks["status"] = "ready" if (
        checks["database"].get("healthy", False) and checks["redis"]
    ) else "degraded"

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
            "created_at": datetime.utcnow().isoformat()
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
                "storage": "redis"
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
                "storage": "memory"
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
            "user": {
                "id": user_data["id"],
                "email": user_data["email"],
                "name": user_data["name"]
            },
            "storage": storage_type
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
                    redis_users.append({
                        "id": user_data["id"],
                        "email": user_data["email"],
                        "name": user_data["name"],
                        "created_at": user_data["created_at"],
                        "storage": "redis"
                    })
            
            await redis_client.close()
            
        except:
            pass
        
        # Add memory users
        for user in memory_users:
            memory_users_formatted = {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "created_at": user["created_at"],
                "storage": "memory"
            }
            users.append(memory_users_formatted)
        
        all_users = redis_users + users
        
        return {
            "users": all_users,
            "total": len(all_users),
            "redis_count": len(redis_users),
            "memory_count": len(memory_users),
            "infrastructure": "Railway"
        }
        
    except Exception as e:
        return {"error": f"Failed to list users: {str(e)}", "users": [], "total": 0}

# API status
@app.get("/api/status")
def api_status():
    return {
        "status": "Plinto API v1.0.0 operational",
        "version": "1.0.0",
        "authentication": "JWT with refresh tokens",
        "infrastructure": "Railway PostgreSQL + Redis",
        "endpoints": {
            "beta": ["/beta/signup", "/beta/signin", "/beta/users"],
            "v1": ["/api/v1/auth/*", "/api/v1/users/*", "/api/v1/organizations/*"]
        },
        "features": {
            "signups": settings.ENABLE_SIGNUPS,
            "magic_links": settings.ENABLE_MAGIC_LINKS,
            "oauth": settings.ENABLE_OAUTH,
            "mfa": settings.ENABLE_MFA,
            "organizations": settings.ENABLE_ORGANIZATIONS
        }
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
app.include_router(mfa_v1.router, prefix="/api/v1")
app.include_router(passkeys_v1.router, prefix="/api/v1")
app.include_router(admin_v1.router, prefix="/api/v1")
app.include_router(webhooks_v1.router, prefix="/api/v1")
# TODO: Re-enable SSO router once dependency injection is properly configured
# app.include_router(sso_v1.router, prefix="/api/v1")
app.include_router(migration_v1.router, prefix="/api/v1")
app.include_router(white_label_v1.router, prefix="/api/v1")
app.include_router(compliance_v1.router, prefix="/api/v1")
app.include_router(iot_v1.router, prefix="/api/v1")
app.include_router(localization_v1.router, prefix="/api/v1")
app.include_router(scim_v1.router, prefix="/api/v1")  # SCIM 2.0 endpoints

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Plinto API...")
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
    logger.info("Plinto API started successfully")

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
    logger.info("Shutting down Plinto API...")
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
    logger.info("Plinto API shutdown complete")