"""
Repository for SSO session management
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session as SSOSessionModel  # Using regular Session model for SSO sessions

from ...domain.protocols.base import SSOSession


class SSOSessionRepository:
    """Repository for managing SSO sessions"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session: SSOSession) -> SSOSession:
        """Create new SSO session"""

        # Convert domain object to database model
        db_session = SSOSessionModel(
            user_id=session.user_id,
            session_id=session.session_id,
            protocol=session.protocol,
            provider_name=session.provider_name,
            attributes=session.attributes,
            expires_at=session.expires_at,
            session_index=session.session_index,
            name_id=session.name_id,
            is_active=True,
            created_at=session.created_at,
        )

        self.db.add(db_session)
        await self.db.commit()
        await self.db.refresh(db_session)

        return self._to_domain_object(db_session)

    async def get_by_session_id(self, session_id: str) -> Optional[SSOSession]:
        """Get SSO session by session ID"""

        stmt = select(SSOSessionModel).where(
            SSOSessionModel.session_id == session_id, SSOSessionModel.is_active == True
        )
        result = await self.db.execute(stmt)
        db_session = result.scalar_one_or_none()

        if not db_session:
            return None

        return self._to_domain_object(db_session)

    async def get_by_user_id(self, user_id: str, active_only: bool = True) -> List[SSOSession]:
        """Get SSO sessions by user ID"""

        stmt = select(SSOSessionModel).where(SSOSessionModel.user_id == user_id)

        if active_only:
            stmt = stmt.where(
                SSOSessionModel.is_active == True, SSOSessionModel.expires_at > datetime.utcnow()
            )

        result = await self.db.execute(stmt)
        db_sessions = result.scalars().all()

        return [self._to_domain_object(session) for session in db_sessions]

    async def invalidate(self, session_id: str) -> bool:
        """Invalidate SSO session"""

        stmt = (
            update(SSOSessionModel)
            .where(SSOSessionModel.session_id == session_id)
            .values(is_active=False, invalidated_at=datetime.utcnow())
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.rowcount > 0

    async def invalidate_all_for_user(self, user_id: str) -> int:
        """Invalidate all SSO sessions for a user"""

        stmt = (
            update(SSOSessionModel)
            .where(SSOSessionModel.user_id == user_id, SSOSessionModel.is_active == True)
            .values(is_active=False, invalidated_at=datetime.utcnow())
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.rowcount

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired SSO sessions"""

        stmt = (
            update(SSOSessionModel)
            .where(
                SSOSessionModel.expires_at < datetime.utcnow(), SSOSessionModel.is_active == True
            )
            .values(is_active=False, invalidated_at=datetime.utcnow())
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.rowcount

    async def update_session_attributes(
        self, session_id: str, attributes: dict
    ) -> Optional[SSOSession]:
        """Update session attributes"""

        stmt = (
            update(SSOSessionModel)
            .where(SSOSessionModel.session_id == session_id, SSOSessionModel.is_active == True)
            .values(attributes=attributes, updated_at=datetime.utcnow())
        )

        await self.db.execute(stmt)
        await self.db.commit()

        return await self.get_by_session_id(session_id)

    async def extend_session(self, session_id: str, new_expiry: datetime) -> Optional[SSOSession]:
        """Extend session expiry time"""

        stmt = (
            update(SSOSessionModel)
            .where(SSOSessionModel.session_id == session_id, SSOSessionModel.is_active == True)
            .values(expires_at=new_expiry, updated_at=datetime.utcnow())
        )

        await self.db.execute(stmt)
        await self.db.commit()

        return await self.get_by_session_id(session_id)

    async def get_active_session_count(self, user_id: str) -> int:
        """Get count of active sessions for a user"""

        stmt = select(SSOSessionModel).where(
            SSOSessionModel.user_id == user_id,
            SSOSessionModel.is_active == True,
            SSOSessionModel.expires_at > datetime.utcnow(),
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        return len(sessions)

    def _to_domain_object(self, db_session: SSOSessionModel) -> SSOSession:
        """Convert database model to domain object"""

        return SSOSession(
            user_id=db_session.user_id,
            session_id=db_session.session_id,
            protocol=db_session.protocol,
            provider_name=db_session.provider_name,
            attributes=db_session.attributes,
            expires_at=db_session.expires_at,
            session_index=db_session.session_index,
            name_id=db_session.name_id,
        )
