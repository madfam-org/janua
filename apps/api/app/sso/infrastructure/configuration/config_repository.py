"""
Repository for SSO configuration management
"""

from typing import List, Optional
import json

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SSOConfiguration as SSOConfigModel
from app.core.redis import get_redis

from ...domain.protocols.base import SSOConfiguration


class SSOConfigurationRepository:
    """Repository for managing SSO configurations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._redis = None

    async def _get_redis(self):
        """Lazy load Redis client"""
        if self._redis is None:
            try:
                self._redis = await get_redis()
            except Exception:
                pass  # Intentionally ignoring - Redis is optional, continue without caching
        return self._redis

    async def _cache_get(self, key: str) -> Optional[dict]:
        """Get from cache"""
        try:
            redis = await self._get_redis()
            if redis:
                cached = await redis.get(key)
                if cached:
                    return json.loads(cached)
        except Exception:
            pass  # Intentionally ignoring - cache read failure falls through to database
        return None

    async def _cache_set(self, key: str, value: dict, ttl: int = 900):
        """Set to cache (15 min default)"""
        try:
            redis = await self._get_redis()
            if redis:
                await redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:
            pass  # Intentionally ignoring - cache write failure is non-critical

    async def _cache_delete(self, pattern: str):
        """Delete from cache by pattern"""
        try:
            redis = await self._get_redis()
            if redis:
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
        except Exception:
            pass  # Intentionally ignoring - cache delete failure is non-critical

    async def create(self, config: SSOConfiguration) -> SSOConfiguration:
        """Create new SSO configuration"""

        # Convert domain object to database model
        db_config = SSOConfigModel(
            organization_id=config.organization_id,
            protocol=config.protocol,
            provider_name=config.provider_name,
            config=config.config,
            attribute_mapping=config.attribute_mapping,
            jit_provisioning=config.jit_provisioning,
            default_role=config.default_role,
            is_active=True,
            created_at=config.created_at,
        )

        self.db.add(db_config)
        await self.db.commit()
        await self.db.refresh(db_config)

        return self._to_domain_object(db_config)

    async def get_by_id(self, config_id: str) -> Optional[SSOConfiguration]:
        """Get SSO configuration by ID"""

        stmt = select(SSOConfigModel).where(
            SSOConfigModel.id == config_id, SSOConfigModel.is_active == True
        )
        result = await self.db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            return None

        return self._to_domain_object(db_config)

    async def get_by_organization(
        self, organization_id: str, protocol: Optional[str] = None
    ) -> Optional[SSOConfiguration]:
        """Get SSO configuration by organization and optional protocol (cached 15 min)"""

        # Try cache first
        cache_key = f"sso:config:{organization_id}:{protocol or 'any'}"
        cached = await self._cache_get(cache_key)
        if cached:
            return SSOConfiguration(**cached)

        stmt = select(SSOConfigModel).where(
            SSOConfigModel.organization_id == organization_id, SSOConfigModel.is_active == True
        )

        if protocol:
            stmt = stmt.where(SSOConfigModel.protocol == protocol)

        result = await self.db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            return None

        domain_obj = self._to_domain_object(db_config)

        # Cache the result (SSO configs change infrequently)
        await self._cache_set(
            cache_key,
            {
                "organization_id": domain_obj.organization_id,
                "protocol": domain_obj.protocol,
                "provider_name": domain_obj.provider_name,
                "config": domain_obj.config,
                "attribute_mapping": domain_obj.attribute_mapping,
                "jit_provisioning": domain_obj.jit_provisioning,
                "default_role": domain_obj.default_role,
            },
            ttl=900,
        )  # 15 minutes

        return domain_obj

    async def list_by_organization(self, organization_id: str) -> List[SSOConfiguration]:
        """List all SSO configurations for an organization"""

        stmt = select(SSOConfigModel).where(
            SSOConfigModel.organization_id == organization_id, SSOConfigModel.is_active == True
        )
        result = await self.db.execute(stmt)
        db_configs = result.scalars().all()

        return [self._to_domain_object(config) for config in db_configs]

    async def update(self, config_id: str, updates: dict) -> Optional[SSOConfiguration]:
        """Update SSO configuration"""

        # Get org ID before update for cache invalidation
        stmt_get = select(SSOConfigModel.organization_id).where(SSOConfigModel.id == config_id)
        result = await self.db.execute(stmt_get)
        org_id = result.scalar_one_or_none()

        stmt = (
            update(SSOConfigModel)
            .where(SSOConfigModel.id == config_id, SSOConfigModel.is_active == True)
            .values(**updates)
        )

        await self.db.execute(stmt)
        await self.db.commit()

        # Invalidate cache for this organization
        if org_id:
            await self._cache_delete(f"sso:config:{org_id}:*")

        # Return updated config
        return await self.get_by_id(config_id)

    async def delete(self, config_id: str) -> bool:
        """Soft delete SSO configuration"""

        # Get org ID before delete for cache invalidation
        stmt_get = select(SSOConfigModel.organization_id).where(SSOConfigModel.id == config_id)
        result = await self.db.execute(stmt_get)
        org_id = result.scalar_one_or_none()

        stmt = update(SSOConfigModel).where(SSOConfigModel.id == config_id).values(is_active=False)

        result = await self.db.execute(stmt)
        await self.db.commit()

        # Invalidate cache for this organization
        if org_id:
            await self._cache_delete(f"sso:config:{org_id}:*")

        return result.rowcount > 0

    async def exists_for_organization(self, organization_id: str, protocol: str) -> bool:
        """Check if SSO configuration exists for organization and protocol"""

        stmt = select(SSOConfigModel.id).where(
            SSOConfigModel.organization_id == organization_id,
            SSOConfigModel.protocol == protocol,
            SSOConfigModel.is_active == True,
        )
        result = await self.db.execute(stmt)

        return result.scalar_one_or_none() is not None

    def _to_domain_object(self, db_config: SSOConfigModel) -> SSOConfiguration:
        """Convert database model to domain object"""

        return SSOConfiguration(
            organization_id=db_config.organization_id,
            protocol=db_config.protocol,
            provider_name=db_config.provider_name,
            config=db_config.config,
            attribute_mapping=db_config.attribute_mapping,
            jit_provisioning=db_config.jit_provisioning,
            default_role=db_config.default_role,
        )
