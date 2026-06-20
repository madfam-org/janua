"""ConnectedAccount service — vault CRUD and OAuthAccount bridge."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthAccount, OAuthProvider, User
from app.models.connected_account import ConnectedAccount, ConnectedAccountStatus

logger = logging.getLogger(__name__)

_PROVIDER_MAP = {
    "github": OAuthProvider.GITHUB,
    "slack": OAuthProvider.SLACK,
}


class ConnectedAccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(self, user: User, *, sync_oauth: bool = True) -> list[ConnectedAccount]:
        if sync_oauth:
            await self._sync_from_oauth_accounts(user)
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.status == ConnectedAccountStatus.ACTIVE.value,
            )
        )
        return list(result.scalars().all())

    async def get_for_user(self, user: User, connection_id: uuid.UUID) -> Optional[ConnectedAccount]:
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == connection_id,
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.status == ConnectedAccountStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, connection_id: uuid.UUID) -> Optional[ConnectedAccount]:
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == connection_id,
                ConnectedAccount.status == ConnectedAccountStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, user: User, connection_id: uuid.UUID) -> bool:
        account = await self.get_for_user(user, connection_id)
        if not account:
            return False
        account.status = ConnectedAccountStatus.REVOKED.value
        account.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def delegate_token(
        self,
        connection: ConnectedAccount,
        *,
        acting_user_id: uuid.UUID,
        purpose: str = "tool_execute",
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        if connection.user_id != acting_user_id:
            raise PermissionError("acting_user_mismatch")
        if not connection.access_token_encrypted:
            raise ValueError("no_access_token")

        connection.last_used_at = datetime.utcnow()
        await self.db.commit()

        expires_at = datetime.utcnow() + timedelta(seconds=min(ttl_seconds, 900))
        return {
            "access_token": connection.access_token_encrypted,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat() + "Z",
            "purpose": purpose,
            "provider_type": connection.provider_type,
            "scopes": connection.oauth_scopes or [],
        }

    async def _sync_from_oauth_accounts(self, user: User) -> None:
        """Bootstrap ConnectedAccount rows from legacy OAuthAccount linkages."""
        result = await self.db.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == user.id)
        )
        oauth_accounts = result.scalars().all()
        if not oauth_accounts:
            return

        existing = await self.db.execute(
            select(ConnectedAccount.provider_type).where(ConnectedAccount.user_id == user.id)
        )
        existing_types = {row[0] for row in existing.all()}

        for oauth in oauth_accounts:
            provider_type = oauth.provider.value
            if provider_type not in _PROVIDER_MAP or provider_type in existing_types:
                continue
            if not oauth.access_token:
                continue

            account = ConnectedAccount(
                id=uuid.uuid4(),
                user_id=user.id,
                provider_type=provider_type,
                provider_name=f"{provider_type.capitalize()} connection",
                provider_id=oauth.provider_user_id,
                access_token_encrypted=oauth.access_token,
                refresh_token_encrypted=oauth.refresh_token,
                oauth_scopes=[],
                oauth_expires_at=oauth.token_expires_at,
                status=ConnectedAccountStatus.ACTIVE.value,
                account_metadata={"source": "oauth_account_sync"},
                created_by=user.id,
            )
            self.db.add(account)
            existing_types.add(provider_type)

        await self.db.commit()
