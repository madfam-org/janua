"""
Health check endpoints for monitoring integration
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import asyncio
from datetime import datetime

from app.core.database_manager import get_database_health

router = APIRouter(
    prefix="/health",
    tags=["health"]
)

# This will be injected from main.py
health_checker = None

def get_health_checker():
    """Dependency to get health checker instance"""
    if health_checker is None:
        raise HTTPException(
            status_code=503, 
            detail="Health checker not initialized"
        )
    return health_checker

@router.get("")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "plinto-api",
        "version": "1.0.0"
    }

@router.get("/detailed")
async def detailed_health_check(
    checker = Depends(get_health_checker)
) -> Dict[str, Any]:
    """Detailed health check with all registered checks"""
    return await checker.check_health()

@router.get("/ready")
async def readiness_check(
    checker = Depends(get_health_checker)
) -> Dict[str, Any]:
    """Kubernetes readiness probe endpoint"""
    result = await checker.check_health()
    
    if result["status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )
    
    return {
        "status": "ready",
        "timestamp": result["timestamp"]
    }

@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe endpoint"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }