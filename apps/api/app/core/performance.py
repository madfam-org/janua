"""
Performance optimization utilities for Plinto API
Phase 2: Sub-100ms response time optimization
"""

import asyncio
import time
import logging
from functools import wraps
from typing import Dict, Any, Optional, Callable, Awaitable
from contextlib import asynccontextmanager
import weakref
import json
import hashlib
from datetime import datetime, timedelta

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

# Global performance cache
_performance_cache = {}
_cache_stats = {
    'hits': 0,
    'misses': 0,
    'sets': 0
}

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor API performance and identify slow endpoints"""
    
    def __init__(self, app, slow_threshold_ms: float = 100.0):
        super().__init__(app)
        self.slow_threshold = slow_threshold_ms / 1000.0  # Convert to seconds
        self.request_times = weakref.WeakValueDictionary()
    
    async def dispatch(self, request: Request, call_next):
        # Skip monitoring for health checks and metrics
        if request.url.path in ['/health', '/metrics', '/ready']:
            return await call_next(request)
        
        start_time = time.perf_counter()
        request_id = id(request)
        
        # Add performance context to request
        request.state.start_time = start_time
        request.state.performance_metrics = {}
        
        try:
            response = await call_next(request)
            
            # Calculate total request time
            end_time = time.perf_counter()
            request_time = end_time - start_time
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{request_time * 1000:.2f}ms"
            
            # Log slow requests
            if request_time > self.slow_threshold:
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path} "
                    f"took {request_time * 1000:.2f}ms"
                )
            
            # Store performance metrics
            self._record_performance_metric(
                method=request.method,
                path=request.url.path,
                duration_ms=request_time * 1000,
                status_code=response.status_code
            )
            
            return response
            
        except Exception as e:
            end_time = time.perf_counter()
            request_time = end_time - start_time
            
            logger.error(
                f"Request error: {request.method} {request.url.path} "
                f"failed after {request_time * 1000:.2f}ms: {str(e)}"
            )
            raise
    
    def _record_performance_metric(self, method: str, path: str, duration_ms: float, status_code: int):
        """Record performance metrics for monitoring"""
        # Simplified in-memory storage - in production, would use proper metrics system
        key = f"{method}:{path}"
        if key not in _performance_cache:
            _performance_cache[key] = {
                'count': 0,
                'total_time': 0,
                'min_time': float('inf'),
                'max_time': 0,
                'error_count': 0
            }
        
        metrics = _performance_cache[key]
        metrics['count'] += 1
        metrics['total_time'] += duration_ms
        metrics['min_time'] = min(metrics['min_time'], duration_ms)
        metrics['max_time'] = max(metrics['max_time'], duration_ms)
        
        if status_code >= 400:
            metrics['error_count'] += 1

class QueryOptimizer:
    """Database query optimization utilities"""
    
    @staticmethod
    async def get_connection_pool_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get database connection pool statistics"""
        try:
            result = await db.execute(text("""
                SELECT 
                    state,
                    COUNT(*) as count
                FROM pg_stat_activity 
                WHERE datname = current_database()
                GROUP BY state
            """))
            
            stats = {}
            for row in result:
                stats[row.state or 'idle'] = row.count
                
            return stats
        except Exception as e:
            logger.error(f"Failed to get connection pool stats: {e}")
            return {}
    
    @staticmethod
    async def analyze_slow_queries(db: AsyncSession) -> list:
        """Analyze current slow queries"""
        try:
            result = await db.execute(text("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                FROM pg_stat_statements 
                WHERE mean_time > 50
                AND query NOT LIKE '%pg_stat_statements%'
                ORDER BY mean_time DESC 
                LIMIT 10
            """))
            
            return [dict(row) for row in result]
        except Exception:
            # pg_stat_statements not available
            return []
    
    @staticmethod
    def optimize_select_query(query_builder, use_join_load: bool = True):
        """Apply common query optimizations"""
        if use_join_load:
            # Add eager loading for relationships to avoid N+1 queries
            pass  # Implementation depends on specific query patterns
        
        return query_builder

class CachingManager:
    """High-performance caching manager with Redis backend"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache = {}  # L1 cache for ultra-fast access
        self.cache_ttl = {
            'user_profile': 300,      # 5 minutes
            'session_validation': 60, # 1 minute  
            'organization': 600,      # 10 minutes
            'settings': 1800,         # 30 minutes
        }
    
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            if settings.redis_url:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("✅ Redis cache initialized")
            else:
                logger.warning("⚠️ Redis URL not configured, using memory cache only")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis: {e}")
            self.redis_client = None
    
    async def close_redis(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    def _generate_cache_key(self, namespace: str, key: str) -> str:
        """Generate standardized cache key"""
        return f"plinto:{namespace}:{key}"
    
    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get cached value with L1 and L2 cache support"""
        cache_key = self._generate_cache_key(namespace, key)
        
        # Try L1 cache (memory) first
        if cache_key in self.local_cache:
            value, expiry = self.local_cache[cache_key]
            if datetime.now() < expiry:
                _cache_stats['hits'] += 1
                return value
            else:
                del self.local_cache[cache_key]
        
        # Try L2 cache (Redis)
        if self.redis_client:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    value = json.loads(cached)
                    # Store in L1 cache for next access
                    ttl = self.cache_ttl.get(namespace, 300)
                    self.local_cache[cache_key] = (
                        value, 
                        datetime.now() + timedelta(seconds=ttl)
                    )
                    _cache_stats['hits'] += 1
                    return value
            except Exception as e:
                logger.warning(f"Redis cache get error: {e}")
        
        _cache_stats['misses'] += 1
        return None
    
    async def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached value in both L1 and L2 cache"""
        cache_key = self._generate_cache_key(namespace, key)
        ttl = ttl or self.cache_ttl.get(namespace, 300)
        
        # Set in L1 cache
        self.local_cache[cache_key] = (
            value,
            datetime.now() + timedelta(seconds=ttl)
        )
        
        # Set in L2 cache (Redis)
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key, 
                    ttl, 
                    json.dumps(value, default=str)
                )
                _cache_stats['sets'] += 1
                return True
            except Exception as e:
                logger.warning(f"Redis cache set error: {e}")
        
        _cache_stats['sets'] += 1
        return True
    
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete cached value from both caches"""
        cache_key = self._generate_cache_key(namespace, key)
        
        # Delete from L1 cache
        if cache_key in self.local_cache:
            del self.local_cache[cache_key]
        
        # Delete from L2 cache
        if self.redis_client:
            try:
                await self.redis_client.delete(cache_key)
                return True
            except Exception as e:
                logger.warning(f"Redis cache delete error: {e}")
        
        return True
    
    async def clear_namespace(self, namespace: str) -> bool:
        """Clear all cached values in a namespace"""
        pattern = self._generate_cache_key(namespace, "*")
        
        # Clear L1 cache
        keys_to_delete = [k for k in self.local_cache.keys() if k.startswith(f"plinto:{namespace}:")]
        for key in keys_to_delete:
            del self.local_cache[key]
        
        # Clear L2 cache
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                return True
            except Exception as e:
                logger.warning(f"Redis cache clear error: {e}")
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = _cache_stats['hits'] + _cache_stats['misses']
        hit_rate = (_cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': _cache_stats['hits'],
            'misses': _cache_stats['misses'],
            'sets': _cache_stats['sets'],
            'hit_rate_percent': round(hit_rate, 2),
            'l1_cache_size': len(self.local_cache),
            'redis_connected': self.redis_client is not None
        }

# Global cache manager instance
cache_manager = CachingManager()

def performance_cache(namespace: str, ttl: Optional[int] = None, 
                     cache_key_fn: Optional[Callable] = None):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_fn:
                key = cache_key_fn(*args, **kwargs)
            else:
                # Generate key from function name and arguments
                key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = await cache_manager.get(namespace, key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(namespace, key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

class ConnectionPoolOptimizer:
    """Database connection pool optimization"""
    
    @staticmethod
    async def optimize_connection_pool(engine):
        """Apply connection pool optimizations"""
        # These would be applied at the SQLAlchemy engine level
        optimizations = {
            'pool_size': 20,          # Base connection pool size
            'max_overflow': 30,       # Maximum overflow connections
            'pool_timeout': 30,       # Connection timeout
            'pool_recycle': 1800,     # Recycle connections after 30 minutes
            'pool_pre_ping': True,    # Validate connections before use
        }
        
        logger.info("🔧 Connection pool optimizations configured")
        return optimizations

async def get_performance_metrics() -> Dict[str, Any]:
    """Get comprehensive performance metrics"""
    return {
        'cache_stats': cache_manager.get_stats(),
        'endpoint_performance': dict(_performance_cache),
        'timestamp': datetime.now().isoformat()
    }

# Performance optimization context manager
@asynccontextmanager
async def performance_context():
    """Context manager for performance-optimized operations"""
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        if duration > 0.1:  # Log operations taking more than 100ms
            logger.info(f"Operation completed in {duration * 1000:.2f}ms")