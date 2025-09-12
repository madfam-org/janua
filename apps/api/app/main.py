from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
import secrets
import os
import redis.asyncio as redis
import asyncpg
from datetime import datetime
import logging

from app.config import settings
from app.database import init_database
from app.routers.v1 import (
    auth as auth_v1,
    oauth as oauth_v1,
    health as health_v1,
    users as users_v1,
    sessions as sessions_v1,
    organizations as organizations_v1,
    mfa as mfa_v1,
    passkeys as passkeys_v1,
    admin as admin_v1,
    webhooks as webhooks_v1,
    sso as sso_v1
)

# Set up logging
logging.basicConfig(level=logging.INFO if settings.DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)

# Create FastAPI app 
app = FastAPI(
    title="Plinto API",
    version="1.0.0",
    description="Modern authentication and identity platform API",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None
)

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

# Utility functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == hashed

# Root endpoint
@app.get("/")
def root():
    return {"status": "ok", "message": "Ultra-minimal beta API", "version": "0.1.0"}

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Infrastructure connectivity test using direct connections
@app.get("/ready")
async def ready_check():
    checks = {"status": "ready", "database": False, "redis": False}
    
    # Test Redis with direct connection
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        checks["redis"] = True
        await redis_client.close()
    except:
        pass
    
    # Test PostgreSQL with direct connection
    try:
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgresql://"):
            # Fix URL for asyncpg
            db_url = db_url.replace("postgresql://", "postgresql://", 1)
            conn = await asyncpg.connect(db_url)
            await conn.execute("SELECT 1")
            checks["database"] = True
            await conn.close()
    except:
        pass
    
    return checks

# Beta authentication with direct Redis operations
@app.post("/beta/signup")
async def beta_signup(request: SignUpRequest):
    try:
        # Validate
        if len(request.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Try Redis first, fallback to memory
        user_id = secrets.token_hex(16)
        user_data = {
            "id": user_id,
            "email": request.email,
            "name": request.name,
            "password_hash": hash_password(request.password),
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            redis_client = await get_redis_client()
            user_key = f"beta_user:{request.email}"
            
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
                "email": request.email,
                "name": request.name,
                "message": "User created in Railway Redis",
                "storage": "redis"
            }
            
        except Exception as redis_error:
            # Fallback to memory storage
            if request.email in BETA_USERS:
                raise HTTPException(status_code=400, detail="User already exists")
            
            BETA_USERS[request.email] = user_data
            
            return {
                "id": user_id,
                "email": request.email,
                "name": request.name,
                "message": "User created in memory (Redis fallback)",
                "storage": "memory"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@app.post("/beta/signin")
async def beta_signin(request: SignInRequest):
    try:
        user_data = None
        storage_type = "unknown"
        
        # Try Redis first
        try:
            redis_client = await get_redis_client()
            user_key = f"beta_user:{request.email}"
            user_data = await redis_client.hgetall(user_key)
            await redis_client.close()
            
            if user_data:
                storage_type = "redis"
            
        except:
            # Fallback to memory
            user_data = BETA_USERS.get(request.email)
            if user_data:
                storage_type = "memory"
        
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not verify_password(request.password, user_data["password_hash"]):
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
app.include_router(sso_v1.router, prefix="/api/v1")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Plinto API...")
    if settings.AUTO_MIGRATE:
        logger.info("Initializing database tables...")
        init_database()
    logger.info("Plinto API started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Plinto API...")