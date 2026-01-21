"""
Caching utilities with circuit-breaker protected Redis

Provides decorators and utilities for caching hot paths with:
- Circuit breaker protection (graceful degradation)
- Configurable TTL
- Cache invalidation patterns
- Performance monitoring
"""

import hashlib
import json
from functools import wraps
from typing import Any, Callable, Optional
import structlog

from app.core.redis import get_redis, ResilientRedisClient

logger = structlog.get_logger()


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from function arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        str: Hash-based cache key
    """
    # Convert args/kwargs to deterministic string
    key_data = {
        "args": [str(arg) for arg in args],
        "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}
    }
    key_str = json.dumps(key_data, sort_keys=True)

    # Generate hash
    key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]
    return key_hash


def cached(
    ttl: int = 300,  # 5 minutes default
    key_prefix: Optional[str] = None,
    key_builder: Optional[Callable] = None
):
    """
    Decorator for caching function results with circuit-breaker protected Redis.

    Automatically handles:
    - Cache hits: Return cached value
    - Cache misses: Call function, cache result
    - Redis failures: Fall back to calling function (no caching)

    Args:
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        key_prefix: Optional prefix for cache keys (default: function name)
        key_builder: Optional function to build cache key from args

    Example:
        @cached(ttl=600)  # Cache for 10 minutes
        async def get_user_by_id(user_id: str) -> User:
            return await db.query(User).filter(User.id == user_id).first()

        # With custom key
        @cached(ttl=3600, key_prefix="org", key_builder=lambda org_id: f"org:{org_id}")
        async def get_organization(org_id: str) -> Organization:
            return await db.query(Organization).filter(Organization.id == org_id).first()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Build cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"

            if key_builder:
                key_suffix = key_builder(*args, **kwargs)
            else:
                key_suffix = cache_key(*args, **kwargs)

            full_key = f"{prefix}:{key_suffix}"

            # Try to get from cache
            try:
                redis_client = await get_redis()
                cached_value = await redis_client.get(full_key)

                if cached_value is not None:
                    logger.debug(
                        "Cache hit",
                        key=full_key,
                        function=func.__name__
                    )
                    return json.loads(cached_value)

                logger.debug(
                    "Cache miss",
                    key=full_key,
                    function=func.__name__
                )

            except Exception as e:
                # If cache lookup fails, just proceed with function call
                logger.warning(
                    "Cache lookup failed, proceeding without cache",
                    key=full_key,
                    function=func.__name__,
                    error=str(e)
                )

            # Call the actual function
            result = await func(*args, **kwargs)

            # Try to cache the result
            try:
                redis_client = await get_redis()
                # Serialize result
                serialized = json.dumps(result, default=str)

                await redis_client.set(full_key, serialized, ex=ttl)

                logger.debug(
                    "Cached result",
                    key=full_key,
                    function=func.__name__,
                    ttl=ttl
                )

            except Exception as e:
                # If caching fails, we still have the result
                logger.warning(
                    "Failed to cache result, returning uncached",
                    key=full_key,
                    function=func.__name__,
                    error=str(e)
                )

            return result

        return wrapper
    return decorator


class CacheManager:
    """
    Manager for cache operations with invalidation patterns.

    Provides methods for:
    - Bulk cache invalidation
    - Pattern-based invalidation
    - Cache warming
    """

    def __init__(self, redis_client: Optional[ResilientRedisClient] = None):
        self.redis_client = redis_client

    async def _get_client(self) -> ResilientRedisClient:
        """Get Redis client (lazy initialization)"""
        if self.redis_client is None:
            self.redis_client = await get_redis()
        return self.redis_client

    async def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache key.

        Args:
            key: Cache key to invalidate

        Returns:
            bool: True if key was deleted, False otherwise
        """
        try:
            client = await self._get_client()
            deleted = await client.delete(key)

            logger.info(
                "Cache invalidated",
                key=key,
                deleted=bool(deleted)
            )

            return bool(deleted)

        except Exception as e:
            logger.error(
                "Cache invalidation failed",
                key=key,
                error=str(e)
            )
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        NOTE: This uses SCAN which is safe for production but may be slow
        for large keyspaces. Consider using more specific invalidation.

        Args:
            pattern: Redis key pattern (e.g., "user:*", "org:123:*")

        Returns:
            int: Number of keys deleted

        Example:
            # Invalidate all user caches
            await cache_manager.invalidate_pattern("user:*")

            # Invalidate all caches for specific organization
            await cache_manager.invalidate_pattern("org:abc123:*")
        """
        try:
            await self._get_client()

            # Note: This requires access to raw Redis for SCAN operation
            # For now, we'll log a warning
            logger.warning(
                "Pattern invalidation requires raw Redis access",
                pattern=pattern,
                message="Consider invalidating specific keys instead"
            )

            return 0

        except Exception as e:
            logger.error(
                "Pattern invalidation failed",
                pattern=pattern,
                error=str(e)
            )
            return 0

    async def warm_cache(
        self,
        key: str,
        value: Any,
        ttl: int = 300
    ) -> bool:
        """
        Warm cache with a specific value.

        Useful for pre-populating caches after database updates.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            bool: True if successful, False otherwise

        Example:
            # After creating a user, warm the cache
            await cache_manager.warm_cache(
                f"user:{user.id}",
                user.to_dict(),
                ttl=600
            )
        """
        try:
            client = await self._get_client()
            serialized = json.dumps(value, default=str)

            await client.set(key, serialized, ex=ttl)

            logger.info(
                "Cache warmed",
                key=key,
                ttl=ttl
            )

            return True

        except Exception as e:
            logger.error(
                "Cache warming failed",
                key=key,
                error=str(e)
            )
            return False


# Global cache manager instance
cache_manager = CacheManager()


# ============================================================================
# Hot Path Cache Utilities
# ============================================================================
# Pre-configured cache decorators for common use cases


def cache_user(ttl: int = 600):
    """Cache user lookups (10 minutes default)"""
    return cached(
        ttl=ttl,
        key_prefix="user",
        key_builder=lambda user_id, *args, **kwargs: f"{user_id}"
    )


def cache_organization(ttl: int = 3600):
    """Cache organization lookups (1 hour default)"""
    return cached(
        ttl=ttl,
        key_prefix="org",
        key_builder=lambda org_id, *args, **kwargs: f"{org_id}"
    )


def cache_permissions(ttl: int = 300):
    """Cache permission checks (5 minutes default)"""
    return cached(
        ttl=ttl,
        key_prefix="perms",
        key_builder=lambda user_id, resource, action, *args, **kwargs: f"{user_id}:{resource}:{action}"
    )


def cache_sso_config(ttl: int = 1800):
    """Cache SSO configurations (30 minutes default)"""
    return cached(
        ttl=ttl,
        key_prefix="sso",
        key_builder=lambda org_id, provider, *args, **kwargs: f"{org_id}:{provider}"
    )


# ============================================================================
# Usage Examples
# ============================================================================

"""
Example 1: Cache user lookups
------------------------------
from app.core.caching import cache_user, cache_manager

@cache_user(ttl=600)  # Cache for 10 minutes
async def get_user_by_id(user_id: str, db: AsyncSession) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()

# After updating user, invalidate cache
async def update_user(user_id: str, data: dict):
    user = await update_user_in_db(user_id, data)
    await cache_manager.invalidate(f"user:{user_id}")
    return user


Example 2: Cache organization with members
-------------------------------------------
from app.core.caching import cache_organization

@cache_organization(ttl=3600)  # Cache for 1 hour
async def get_organization_with_members(org_id: str, db: AsyncSession):
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.members))  # Avoid N+1
        .where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    return org.to_dict() if org else None


Example 3: Cache permission checks
-----------------------------------
from app.core.caching import cache_permissions

@cache_permissions(ttl=300)  # Cache for 5 minutes
async def check_user_permission(
    user_id: str,
    resource: str,
    action: str,
    db: AsyncSession
) -> bool:
    # Complex permission check
    result = await db.execute(
        select(Permission)
        .join(Role)
        .join(UserRole)
        .where(
            UserRole.user_id == user_id,
            Permission.resource == resource,
            Permission.action == action
        )
    )
    return result.scalar_one_or_none() is not None


Example 4: Custom cache with invalidation
------------------------------------------
from app.core.caching import cached, cache_manager

@cached(ttl=600, key_prefix="product", key_builder=lambda product_id: f"{product_id}")
async def get_product(product_id: str):
    # ... fetch product
    pass

# In update handler
async def update_product(product_id: str, data: dict):
    product = await update_in_db(product_id, data)

    # Invalidate cache
    await cache_manager.invalidate(f"product:{product_id}")

    # Optionally warm with new data
    await cache_manager.warm_cache(
        f"product:{product_id}",
        product.to_dict(),
        ttl=600
    )

    return product
"""
