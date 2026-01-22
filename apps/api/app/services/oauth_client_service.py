"""
OAuth2 Client Management Service

Business logic for managing OAuth2 clients that use Janua as an OAuth Provider.
"""

import logging
import secrets
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, OAuthClient, OrganizationMember, User
from app.schemas.oauth_client import OAuthClientCreate, OAuthClientUpdate

logger = logging.getLogger(__name__)


class OAuthClientService:
    """Service for OAuth2 client management operations"""

    # Configuration
    CLIENT_ID_LENGTH = 24
    CLIENT_SECRET_LENGTH = 48
    CLIENT_ID_PREFIX = "jnc_"  # Janua Client
    CLIENT_SECRET_PREFIX = "jns_"  # Janua Secret

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_client_id() -> str:
        """Generate a unique client ID"""
        random_part = secrets.token_urlsafe(OAuthClientService.CLIENT_ID_LENGTH)
        return f"{OAuthClientService.CLIENT_ID_PREFIX}{random_part}"

    @staticmethod
    def generate_client_secret() -> Tuple[str, str, str]:
        """
        Generate a client secret with hash and prefix.

        Returns:
            Tuple of (plain_secret, hashed_secret, prefix_for_display)
        """
        random_part = secrets.token_urlsafe(OAuthClientService.CLIENT_SECRET_LENGTH)
        plain_secret = f"{OAuthClientService.CLIENT_SECRET_PREFIX}{random_part}"

        # Hash the secret using bcrypt
        hashed = bcrypt.hashpw(plain_secret.encode(), bcrypt.gensalt()).decode()

        # Create prefix for display (first 8 chars + ...)
        display_prefix = plain_secret[:12] + "..."

        return plain_secret, hashed, display_prefix

    @staticmethod
    def verify_client_secret(plain_secret: str, hashed_secret: str) -> bool:
        """Verify a client secret against its hash"""
        try:
            return bcrypt.checkpw(plain_secret.encode(), hashed_secret.encode())
        except Exception as e:
            logger.error(f"Error verifying client secret: {e}")
            return False

    async def create_client(
        self,
        data: OAuthClientCreate,
        created_by: User,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Tuple[OAuthClient, str]:
        """
        Create a new OAuth2 client.

        Args:
            data: Client creation data
            created_by: User creating the client
            organization_id: Optional organization to scope the client to

        Returns:
            Tuple of (created client, plain text secret)
        """
        # Generate credentials
        client_id = self.generate_client_id()
        plain_secret, hashed_secret, secret_prefix = self.generate_client_secret()

        # Create client record
        client = OAuthClient(
            id=uuid.uuid4(),
            organization_id=organization_id,
            created_by=created_by.id,
            client_id=client_id,
            client_secret_hash=hashed_secret,
            client_secret_prefix=secret_prefix,
            name=data.name,
            description=data.description,
            redirect_uris=data.redirect_uris,
            allowed_scopes=data.allowed_scopes or ["openid", "profile", "email"],
            grant_types=data.grant_types or ["authorization_code", "refresh_token"],
            logo_url=data.logo_url,
            website_url=data.website_url,
            is_confidential=data.is_confidential if data.is_confidential is not None else True,
            is_active=True,
        )

        self.db.add(client)

        # Log the action
        audit_log = AuditLog(
            user_id=created_by.id,
            action="oauth_client_created",
            resource_type="oauth_client",
            resource_id=client.id,
            details={
                "client_id": client_id,
                "name": data.name,
                "organization_id": str(organization_id) if organization_id else None,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(client)

        logger.info(f"OAuth client created: {client_id} by user {created_by.id}")

        return client, plain_secret

    async def get_client(
        self,
        client_db_id: uuid.UUID,
        user: User,
        require_ownership: bool = True,
    ) -> Optional[OAuthClient]:
        """
        Get an OAuth2 client by database ID.

        Args:
            client_db_id: Database UUID of the client
            user: User requesting the client
            require_ownership: If True, verify user has access to this client

        Returns:
            OAuthClient if found and accessible, None otherwise
        """
        result = await self.db.execute(select(OAuthClient).where(OAuthClient.id == client_db_id))
        client = result.scalar_one_or_none()

        if not client:
            return None

        if require_ownership and not await self._can_access_client(user, client):
            return None

        return client

    async def get_client_by_client_id(self, client_id: str) -> Optional[OAuthClient]:
        """
        Get an OAuth2 client by its client_id (public identifier).

        Args:
            client_id: The public client identifier (e.g., jnc_xxx)

        Returns:
            OAuthClient if found, None otherwise
        """
        result = await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id, OAuthClient.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def list_clients(
        self,
        user: User,
        organization_id: Optional[uuid.UUID] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[OAuthClient], int]:
        """
        List OAuth2 clients accessible to the user.

        Args:
            user: User requesting the list
            organization_id: Filter by organization (optional)
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Tuple of (list of clients, total count)
        """
        # Build base query
        query = select(OAuthClient)

        # If user is admin, show all clients
        if user.is_admin:
            if organization_id:
                query = query.where(OAuthClient.organization_id == organization_id)
        else:
            # Get organizations the user is admin of
            org_result = await self.db.execute(
                select(OrganizationMember.organization_id).where(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.role.in_(["admin", "owner"]),
                )
            )
            org_ids = [row[0] for row in org_result.fetchall()]

            # Include clients created by the user or in their organizations
            query = query.where(
                (OAuthClient.created_by == user.id)
                | (OAuthClient.organization_id.in_(org_ids) if org_ids else False)
            )

            if organization_id and organization_id in org_ids:
                query = query.where(OAuthClient.organization_id == organization_id)

        # Get total count
        count_result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.order_by(OAuthClient.created_at.desc()).offset(offset).limit(per_page)

        result = await self.db.execute(query)
        clients = result.scalars().all()

        return list(clients), total

    async def update_client(
        self,
        client_db_id: uuid.UUID,
        data: OAuthClientUpdate,
        user: User,
    ) -> Optional[OAuthClient]:
        """
        Update an OAuth2 client.

        Args:
            client_db_id: Database UUID of the client
            data: Update data
            user: User performing the update

        Returns:
            Updated client if successful, None if not found/unauthorized
        """
        client = await self.get_client(client_db_id, user, require_ownership=True)
        if not client:
            return None

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(client, field):
                setattr(client, field, value)

        client.updated_at = datetime.utcnow()

        # Log the action
        audit_log = AuditLog(
            user_id=user.id,
            action="oauth_client_updated",
            resource_type="oauth_client",
            resource_id=client.id,
            details={"updated_fields": list(update_data.keys())},
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(client)

        logger.info(f"OAuth client updated: {client.client_id} by user {user.id}")

        return client

    async def delete_client(
        self,
        client_db_id: uuid.UUID,
        user: User,
    ) -> bool:
        """
        Delete an OAuth2 client.

        Args:
            client_db_id: Database UUID of the client
            user: User performing the deletion

        Returns:
            True if deleted, False if not found/unauthorized
        """
        client = await self.get_client(client_db_id, user, require_ownership=True)
        if not client:
            return False

        client_id = client.client_id

        # Log before deletion
        audit_log = AuditLog(
            user_id=user.id,
            action="oauth_client_deleted",
            resource_type="oauth_client",
            resource_id=client.id,
            details={"client_id": client_id, "name": client.name},
        )
        self.db.add(audit_log)

        await self.db.delete(client)
        await self.db.commit()

        logger.info(f"OAuth client deleted: {client_id} by user {user.id}")

        return True

    async def rotate_secret(
        self,
        client_db_id: uuid.UUID,
        user: User,
    ) -> Optional[Tuple[OAuthClient, str]]:
        """
        Rotate the client secret for an OAuth2 client.

        Args:
            client_db_id: Database UUID of the client
            user: User performing the rotation

        Returns:
            Tuple of (client, new plain text secret) if successful, None otherwise
        """
        client = await self.get_client(client_db_id, user, require_ownership=True)
        if not client:
            return None

        # Generate new secret
        plain_secret, hashed_secret, secret_prefix = self.generate_client_secret()

        # Update client
        client.client_secret_hash = hashed_secret
        client.client_secret_prefix = secret_prefix
        client.updated_at = datetime.utcnow()

        # Log the action
        audit_log = AuditLog(
            user_id=user.id,
            action="oauth_client_secret_rotated",
            resource_type="oauth_client",
            resource_id=client.id,
            details={"client_id": client.client_id},
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(client)

        logger.info(f"OAuth client secret rotated: {client.client_id} by user {user.id}")

        return client, plain_secret

    async def validate_client_credentials(
        self,
        client_id: str,
        client_secret: str,
    ) -> Optional[OAuthClient]:
        """
        Validate client credentials for OAuth flow.

        Supports credential rotation by checking all active secrets during
        the grace period, as well as the primary secret stored on the client.

        Args:
            client_id: The client's public identifier
            client_secret: The client's secret

        Returns:
            OAuthClient if valid, None otherwise
        """
        from app.config import settings

        client = await self.get_client_by_client_id(client_id)
        if not client:
            return None

        # If rotation is enabled, use the rotation service
        if settings.CLIENT_SECRET_ROTATION_ENABLED:
            from app.services.credential_rotation_service import CredentialRotationService

            rotation_service = CredentialRotationService(self.db)
            matched_secret = await rotation_service.validate_secret(client, client_secret)

            # If we got a matched secret or None (legacy valid), the secret is valid
            if matched_secret is not None or client.verify_secret(client_secret):
                # Update last used timestamp
                client.last_used_at = datetime.utcnow()
                await self.db.commit()
                return client
            return None

        # Legacy validation (single secret)
        if not self.verify_client_secret(client_secret, client.client_secret_hash):
            return None

        # Update last used timestamp
        client.last_used_at = datetime.utcnow()
        await self.db.commit()

        return client

    async def _can_access_client(self, user: User, client: OAuthClient) -> bool:
        """Check if user can access a client"""
        # Admin can access all
        if user.is_admin:
            return True

        # Creator can access
        if client.created_by == user.id:
            return True

        # Organization admin can access org clients
        if client.organization_id:
            result = await self.db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == client.organization_id,
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.role.in_(["admin", "owner"]),
                )
            )
            if result.scalar_one_or_none():
                return True

        return False
