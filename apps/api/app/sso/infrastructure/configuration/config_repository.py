"""
Repository for SSO configuration management
"""

from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SSOConfiguration as SSOConfigModel

from ...domain.protocols.base import SSOConfiguration


class SSOConfigurationRepository:
    """Repository for managing SSO configurations"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
        """Get SSO configuration by organization and optional protocol"""

        stmt = select(SSOConfigModel).where(
            SSOConfigModel.organization_id == organization_id, SSOConfigModel.is_active == True
        )

        if protocol:
            stmt = stmt.where(SSOConfigModel.protocol == protocol)

        result = await self.db.execute(stmt)
        db_config = result.scalar_one_or_none()

        if not db_config:
            return None

        return self._to_domain_object(db_config)

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

        stmt = (
            update(SSOConfigModel)
            .where(SSOConfigModel.id == config_id, SSOConfigModel.is_active == True)
            .values(**updates)
        )

        await self.db.execute(stmt)
        await self.db.commit()

        # Return updated config
        return await self.get_by_id(config_id)

    async def delete(self, config_id: str) -> bool:
        """Soft delete SSO configuration"""

        stmt = update(SSOConfigModel).where(SSOConfigModel.id == config_id).values(is_active=False)

        result = await self.db.execute(stmt)
        await self.db.commit()

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
