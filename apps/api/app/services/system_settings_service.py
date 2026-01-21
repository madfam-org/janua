"""
System Settings Service
Manages global platform configuration that can be modified via API.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert

from app.models.system_settings import (
    SystemSetting,
    AllowedCorsOrigin,
    SystemSettingCategory,
    SettingKeys,
)
from app.config import settings as app_settings

logger = logging.getLogger(__name__)


class SystemSettingsService:
    """Service for managing system-wide settings"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: Dict[str, Any] = {}
        self._cors_cache: Optional[List[str]] = None

    # =========================================================================
    # Generic Settings Management
    # =========================================================================

    async def get_setting(
        self,
        key: str,
        default: Any = None,
        use_cache: bool = True
    ) -> Any:
        """
        Get a system setting value.
        Falls back to environment variable / config.py if not set in database.
        """
        if use_cache and key in self._cache:
            return self._cache[key]

        result = await self.db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            value = setting.get_value()
            self._cache[key] = value
            return value

        # Fall back to default
        return default

    async def set_setting(
        self,
        key: str,
        value: Any,
        category: str = SystemSettingCategory.FEATURES,
        description: Optional[str] = None,
        is_sensitive: bool = False,
        updated_by: Optional[UUID] = None
    ) -> SystemSetting:
        """Create or update a system setting"""
        # Determine if value should be stored as JSON or string
        if isinstance(value, (dict, list)):
            json_value = value
            str_value = None
        else:
            json_value = None
            str_value = str(value) if value is not None else None

        # Upsert the setting
        stmt = insert(SystemSetting).values(
            key=key,
            value=str_value,
            json_value=json_value,
            category=category,
            description=description,
            is_sensitive=is_sensitive,
            updated_by=updated_by,
        ).on_conflict_do_update(
            index_elements=['key'],
            set_={
                'value': str_value,
                'json_value': json_value,
                'category': category,
                'description': description,
                'is_sensitive': is_sensitive,
                'updated_by': updated_by,
            }
        ).returning(SystemSetting)

        result = await self.db.execute(stmt)
        setting = result.scalar_one()
        await self.db.commit()

        # Invalidate cache
        self._cache.pop(key, None)

        # Sanitize key for logging to prevent log injection
        safe_key = key.replace("\n", "").replace("\r", "")[:100]
        logger.info("System setting updated: %s", safe_key)
        return setting

    async def delete_setting(self, key: str) -> bool:
        """Delete a system setting"""
        result = await self.db.execute(
            delete(SystemSetting).where(SystemSetting.key == key)
        )
        await self.db.commit()
        self._cache.pop(key, None)
        return result.rowcount > 0

    async def get_all_settings(
        self,
        category: Optional[str] = None,
        include_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all system settings, optionally filtered by category"""
        query = select(SystemSetting)
        if category:
            query = query.where(SystemSetting.category == category)

        result = await self.db.execute(query.order_by(SystemSetting.key))
        settings = result.scalars().all()

        return [
            {
                "id": str(setting.id),
                "key": setting.key,
                "value": setting.get_value() if (include_sensitive or not setting.is_sensitive) else "***REDACTED***",
                "category": setting.category,
                "description": setting.description,
                "is_sensitive": setting.is_sensitive,
                "is_readonly": setting.is_readonly,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
            }
            for setting in settings
        ]

    # =========================================================================
    # CORS Origins Management
    # =========================================================================

    async def get_cors_origins(
        self,
        organization_id: Optional[UUID] = None,
        include_inactive: bool = False,
        include_system: bool = True
    ) -> List[str]:
        """
        Get allowed CORS origins.

        Args:
            organization_id: If provided, include org-specific origins
            include_inactive: Include deactivated origins
            include_system: Include system-level origins (organization_id=None)

        Returns list combining:
        - Config file defaults (always included)
        - System-level database origins (if include_system=True)
        - Organization-specific origins (if organization_id provided)
        """
        cache_key = f"{organization_id}_{include_inactive}_{include_system}"
        if self._cors_cache is not None and cache_key in self._cors_cache:
            return self._cors_cache[cache_key]

        # Build query for database origins
        conditions = []

        if include_system:
            conditions.append(AllowedCorsOrigin.organization_id.is_(None))

        if organization_id:
            conditions.append(AllowedCorsOrigin.organization_id == organization_id)

        if conditions:
            from sqlalchemy import or_
            query = select(AllowedCorsOrigin).where(or_(*conditions))
        else:
            query = select(AllowedCorsOrigin).where(False)  # No results if no conditions

        if not include_inactive:
            query = query.where(AllowedCorsOrigin.is_active == True)

        result = await self.db.execute(query)
        db_origins = [origin.origin for origin in result.scalars().all()]

        # Combine with config defaults
        config_origins = app_settings.cors_origins_list

        # Merge and deduplicate
        all_origins = list(set(config_origins + db_origins))

        # Cache results
        if self._cors_cache is None:
            self._cors_cache = {}
        self._cors_cache[cache_key] = all_origins

        return all_origins

    async def add_cors_origin(
        self,
        origin: str,
        organization_id: Optional[UUID] = None,
        description: Optional[str] = None,
        created_by: Optional[UUID] = None
    ) -> AllowedCorsOrigin:
        """
        Add a new CORS origin.

        Args:
            origin: The origin URL (e.g., https://app.example.com)
            organization_id: Optional org ID for tenant-specific origin (None = system-level)
            description: Human-readable description
            created_by: User ID who created this entry
        """
        # Normalize origin (remove trailing slash)
        origin = origin.rstrip("/")

        # Validate origin format
        if not origin.startswith(("http://", "https://")):
            raise ValueError("CORS origin must start with http:// or https://")

        # Check if origin already exists for this org/system level
        existing = await self.db.execute(
            select(AllowedCorsOrigin).where(
                AllowedCorsOrigin.origin == origin,
                AllowedCorsOrigin.organization_id == organization_id
            )
        )
        existing_origin = existing.scalar_one_or_none()

        if existing_origin:
            # Update existing
            existing_origin.description = description or existing_origin.description
            existing_origin.is_active = True
            existing_origin.created_by = created_by or existing_origin.created_by
            await self.db.commit()
            await self.db.refresh(existing_origin)
            cors_origin = existing_origin
        else:
            # Create new
            cors_origin = AllowedCorsOrigin(
                origin=origin,
                organization_id=organization_id,
                description=description,
                is_active=True,
                created_by=created_by,
            )
            self.db.add(cors_origin)
            await self.db.commit()
            await self.db.refresh(cors_origin)

        # Invalidate cache
        self._cors_cache = None

        scope = f"org:{organization_id}" if organization_id else "system"
        # Sanitize origin for logging to prevent log injection
        safe_origin = origin.replace("\n", "").replace("\r", "")[:200]
        logger.info("CORS origin added [%s]: %s", scope, safe_origin)
        return cors_origin

    async def remove_cors_origin(
        self,
        origin: str,
        organization_id: Optional[UUID] = None
    ) -> bool:
        """Remove a CORS origin (soft delete by deactivating)"""
        result = await self.db.execute(
            select(AllowedCorsOrigin).where(
                AllowedCorsOrigin.origin == origin,
                AllowedCorsOrigin.organization_id == organization_id
            )
        )
        cors_origin = result.scalar_one_or_none()

        if cors_origin:
            cors_origin.is_active = False
            await self.db.commit()
            self._cors_cache = None
            scope = f"org:{organization_id}" if organization_id else "system"
            # Sanitize origin for logging to prevent log injection
            safe_origin = origin.replace("\n", "").replace("\r", "")[:200]
            logger.info("CORS origin removed [%s]: %s", scope, safe_origin)
            return True

        return False

    async def delete_cors_origin(
        self,
        origin: str,
        organization_id: Optional[UUID] = None
    ) -> bool:
        """Permanently delete a CORS origin"""
        result = await self.db.execute(
            delete(AllowedCorsOrigin).where(
                AllowedCorsOrigin.origin == origin,
                AllowedCorsOrigin.organization_id == organization_id
            )
        )
        await self.db.commit()
        self._cors_cache = None
        return result.rowcount > 0

    async def list_cors_origins(
        self,
        organization_id: Optional[UUID] = None,
        include_inactive: bool = False,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """
        List CORS origins with metadata.

        Args:
            organization_id: Filter by organization (None = system-level only)
            include_inactive: Include deactivated origins
            include_system: Include system-level origins (org_id=None)
        """
        conditions = []

        if include_system:
            conditions.append(AllowedCorsOrigin.organization_id.is_(None))

        if organization_id:
            conditions.append(AllowedCorsOrigin.organization_id == organization_id)

        if conditions:
            from sqlalchemy import or_
            query = select(AllowedCorsOrigin).where(or_(*conditions))
        else:
            query = select(AllowedCorsOrigin).where(AllowedCorsOrigin.organization_id.is_(None))

        if not include_inactive:
            query = query.where(AllowedCorsOrigin.is_active == True)

        result = await self.db.execute(query.order_by(AllowedCorsOrigin.origin))
        origins = result.scalars().all()

        return [
            {
                "id": str(o.id),
                "origin": o.origin,
                "organization_id": str(o.organization_id) if o.organization_id else None,
                "scope": "organization" if o.organization_id else "system",
                "description": o.description,
                "is_active": o.is_active,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in origins
        ]

    async def sync_cors_origins(self, origins: List[str], created_by: Optional[UUID] = None):
        """
        Sync CORS origins - add new ones, deactivate removed ones.
        Preserves origins from config file.
        """
        config_origins = set(app_settings.cors_origins_list)
        new_origins = set(origins)

        # Get current database origins
        result = await self.db.execute(select(AllowedCorsOrigin))
        current_db_origins = {o.origin: o for o in result.scalars().all()}

        # Add new origins
        for origin in new_origins:
            if origin not in current_db_origins:
                await self.add_cors_origin(origin, created_by=created_by)
            elif not current_db_origins[origin].is_active:
                current_db_origins[origin].is_active = True

        # Deactivate removed origins (except config origins)
        for origin, db_origin in current_db_origins.items():
            if origin not in new_origins and origin not in config_origins:
                db_origin.is_active = False

        await self.db.commit()
        self._cors_cache = None

    # =========================================================================
    # OIDC Settings
    # =========================================================================

    async def get_custom_domain(self) -> Optional[str]:
        """Get custom OIDC issuer domain"""
        db_value = await self.get_setting(SettingKeys.OIDC_CUSTOM_DOMAIN)
        return db_value or app_settings.JANUA_CUSTOM_DOMAIN

    async def set_custom_domain(
        self,
        domain: str,
        updated_by: Optional[UUID] = None
    ) -> SystemSetting:
        """Set custom OIDC issuer domain"""
        # Validate domain format
        domain = domain.strip().lower()
        if domain.startswith(("http://", "https://")):
            # Extract domain from URL
            from urllib.parse import urlparse
            domain = urlparse(domain).netloc

        return await self.set_setting(
            key=SettingKeys.OIDC_CUSTOM_DOMAIN,
            value=domain,
            category=SystemSettingCategory.OIDC,
            description="Custom domain for OIDC issuer (e.g., auth.madfam.io)",
            updated_by=updated_by,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def invalidate_cache(self):
        """Invalidate all cached settings"""
        self._cache.clear()
        self._cors_cache = None


# Singleton-ish pattern for getting cached CORS origins
_cors_origins_cache: Optional[List[str]] = None


async def get_cached_cors_origins(db: AsyncSession) -> List[str]:
    """
    Get CORS origins with caching at module level.
    This is used by the CORS middleware.
    """
    global _cors_origins_cache

    if _cors_origins_cache is not None:
        return _cors_origins_cache

    service = SystemSettingsService(db)
    _cors_origins_cache = await service.get_cors_origins()
    return _cors_origins_cache


def invalidate_cors_cache():
    """
    Invalidate all CORS caches (service-level and middleware-level).
    This should be called whenever CORS origins are added, removed, or modified.
    """
    global _cors_origins_cache
    _cors_origins_cache = None

    # Also invalidate the middleware cache
    try:
        from app.middleware.dynamic_cors import invalidate_cors_cache as invalidate_middleware_cache
        invalidate_middleware_cache()
    except ImportError:
        pass  # Middleware not yet loaded
