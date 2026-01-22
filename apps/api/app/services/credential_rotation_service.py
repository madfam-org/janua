"""
OAuth Client Credential Rotation Service

Manages graceful client secret rotation with overlap periods,
allowing zero-downtime credential updates.
"""

import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

import bcrypt
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, OAuthClient, OAuthClientSecret, User

logger = structlog.get_logger(__name__)


class CredentialRotationService:
    """Service for managing OAuth client credential rotation."""

    CLIENT_SECRET_LENGTH = 48
    CLIENT_SECRET_PREFIX = "jns_"

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_secret() -> Tuple[str, str, str]:
        """
        Generate a new client secret.

        Returns:
            Tuple of (plain_secret, hashed_secret, display_prefix)
        """
        random_part = secrets.token_urlsafe(CredentialRotationService.CLIENT_SECRET_LENGTH)
        plain_secret = f"{CredentialRotationService.CLIENT_SECRET_PREFIX}{random_part}"

        # Hash using bcrypt
        hashed = bcrypt.hashpw(plain_secret.encode(), bcrypt.gensalt()).decode()

        # Create display prefix (first 12 chars + ...)
        display_prefix = plain_secret[:12] + "..."

        return plain_secret, hashed, display_prefix

    async def get_active_secrets(
        self,
        client_id: UUID,
    ) -> List[OAuthClientSecret]:
        """
        Get all active (non-expired, non-revoked) secrets for a client.

        Args:
            client_id: The OAuth client's database ID

        Returns:
            List of active OAuthClientSecret records
        """
        result = await self.db.execute(
            select(OAuthClientSecret)
            .where(
                and_(
                    OAuthClientSecret.client_id == client_id,
                    OAuthClientSecret.revoked_at.is_(None),
                    (OAuthClientSecret.expires_at.is_(None))
                    | (OAuthClientSecret.expires_at > datetime.utcnow()),
                )
            )
            .order_by(OAuthClientSecret.created_at.desc())
        )
        return list(result.scalars().all())

    async def validate_secret(
        self,
        client: OAuthClient,
        plain_secret: str,
    ) -> Optional[OAuthClientSecret]:
        """
        Validate a secret against all active secrets for a client.

        Args:
            client: The OAuth client
            plain_secret: The plain text secret to validate

        Returns:
            The matching OAuthClientSecret if valid, None otherwise
        """
        if not settings.CLIENT_SECRET_ROTATION_ENABLED:
            # Fall back to legacy single-secret validation
            if client.verify_secret(plain_secret):
                return None  # Indicates valid but no rotation tracking
            return None

        # Get all active secrets
        active_secrets = await self.get_active_secrets(client.id)

        # Also check legacy secret for backward compatibility
        if not active_secrets:
            if client.verify_secret(plain_secret):
                # Migrate to new system by creating a secret record
                await self._migrate_legacy_secret(client)
                return None
            return None

        # Check against all active secrets
        for secret in active_secrets:
            if secret.verify(plain_secret):
                # Update last used timestamp
                secret.last_used_at = datetime.utcnow()
                await self.db.commit()
                return secret

        # Also check legacy secret as fallback
        if client.verify_secret(plain_secret):
            return None

        return None

    async def _migrate_legacy_secret(self, client: OAuthClient) -> None:
        """
        Migrate a client's legacy secret to the new rotation system.
        This creates a record for the existing secret without knowing its value.
        """
        # Check if already migrated
        existing = await self.db.execute(
            select(OAuthClientSecret).where(OAuthClientSecret.client_id == client.id)
        )
        if existing.scalar_one_or_none():
            return

        # Create a placeholder record for the legacy secret
        # Note: We don't have the hash, so this is just for tracking
        logger.info(
            "Legacy secret migration noted",
            client_id=str(client.id),
            message="Client using legacy secret system",
        )

    async def rotate_secret(
        self,
        client: OAuthClient,
        user: User,
        grace_hours: Optional[int] = None,
    ) -> Tuple[OAuthClientSecret, str]:
        """
        Rotate the client secret with a grace period.

        Creates a new primary secret and sets the old one to expire
        after the grace period.

        Args:
            client: The OAuth client to rotate
            user: User performing the rotation
            grace_hours: Hours before old secrets expire (default from config)

        Returns:
            Tuple of (new secret record, plain text secret)
        """
        if grace_hours is None:
            grace_hours = settings.CLIENT_SECRET_ROTATION_GRACE_HOURS

        grace_period = timedelta(hours=grace_hours)
        expiry_time = datetime.utcnow() + grace_period

        # Generate new secret
        plain_secret, hashed_secret, display_prefix = self.generate_secret()

        # Mark all existing secrets as non-primary and set expiry
        existing_secrets = await self.get_active_secrets(client.id)
        for secret in existing_secrets:
            secret.is_primary = False
            if secret.expires_at is None or secret.expires_at > expiry_time:
                secret.expires_at = expiry_time

        # Create new primary secret
        new_secret = OAuthClientSecret(
            client_id=client.id,
            secret_hash=hashed_secret,
            secret_prefix=display_prefix,
            is_primary=True,
            created_by=user.id,
        )
        self.db.add(new_secret)

        # Update client's primary secret hash for legacy compatibility
        client.client_secret_hash = hashed_secret
        client.client_secret_prefix = display_prefix
        client.updated_at = datetime.utcnow()

        # Audit log
        audit_log = AuditLog(
            user_id=user.id,
            action="oauth_client_secret_rotated",
            resource_type="oauth_client",
            resource_id=client.id,
            details={
                "client_id": client.client_id,
                "grace_hours": grace_hours,
                "old_secrets_expire_at": expiry_time.isoformat(),
            },
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(new_secret)

        logger.info(
            "Client secret rotated",
            client_id=client.client_id,
            grace_hours=grace_hours,
            new_secret_id=str(new_secret.id),
        )

        return new_secret, plain_secret

    async def revoke_secret(
        self,
        secret_id: UUID,
        user: User,
    ) -> bool:
        """
        Immediately revoke a specific secret.

        Args:
            secret_id: The secret to revoke
            user: User performing the revocation

        Returns:
            True if revoked, False if not found
        """
        result = await self.db.execute(
            select(OAuthClientSecret).where(OAuthClientSecret.id == secret_id)
        )
        secret = result.scalar_one_or_none()

        if not secret:
            return False

        if secret.revoked_at is not None:
            return True  # Already revoked

        secret.revoked_at = datetime.utcnow()
        secret.revoked_by = user.id

        # Audit log
        audit_log = AuditLog(
            user_id=user.id,
            action="oauth_client_secret_revoked",
            resource_type="oauth_client_secret",
            resource_id=secret.id,
            details={
                "client_id": str(secret.client_id),
                "secret_prefix": secret.secret_prefix,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()

        logger.info(
            "Client secret revoked",
            secret_id=str(secret_id),
            revoked_by=str(user.id),
        )

        return True

    async def revoke_all_except_primary(
        self,
        client: OAuthClient,
        user: User,
    ) -> int:
        """
        Revoke all non-primary secrets for a client (emergency cleanup).

        Args:
            client: The OAuth client
            user: User performing the revocation

        Returns:
            Number of secrets revoked
        """
        result = await self.db.execute(
            select(OAuthClientSecret).where(
                and_(
                    OAuthClientSecret.client_id == client.id,
                    OAuthClientSecret.is_primary == False,
                    OAuthClientSecret.revoked_at.is_(None),
                )
            )
        )
        secrets = result.scalars().all()

        revoked_count = 0
        for secret in secrets:
            secret.revoked_at = datetime.utcnow()
            secret.revoked_by = user.id
            revoked_count += 1

        if revoked_count > 0:
            audit_log = AuditLog(
                user_id=user.id,
                action="oauth_client_secrets_bulk_revoked",
                resource_type="oauth_client",
                resource_id=client.id,
                details={
                    "client_id": client.client_id,
                    "revoked_count": revoked_count,
                },
            )
            self.db.add(audit_log)
            await self.db.commit()

            logger.info(
                "Bulk secret revocation",
                client_id=client.client_id,
                revoked_count=revoked_count,
            )

        return revoked_count

    async def get_secret_status(
        self,
        client: OAuthClient,
    ) -> dict:
        """
        Get the rotation status for a client's secrets.

        Args:
            client: The OAuth client

        Returns:
            Dictionary with rotation status information
        """
        active_secrets = await self.get_active_secrets(client.id)

        # Get all secrets including expired/revoked for history
        result = await self.db.execute(
            select(OAuthClientSecret)
            .where(OAuthClientSecret.client_id == client.id)
            .order_by(OAuthClientSecret.created_at.desc())
            .limit(10)
        )
        all_secrets = list(result.scalars().all())

        primary = next((s for s in active_secrets if s.is_primary), None)

        # Check if rotation is recommended
        rotation_recommended = False
        if primary:
            age_days = (datetime.utcnow() - primary.created_at).days
            if age_days >= settings.CLIENT_SECRET_MAX_AGE_DAYS:
                rotation_recommended = True

        return {
            "active_count": len(active_secrets),
            "total_count": len(all_secrets),
            "has_primary": primary is not None,
            "primary_created_at": primary.created_at.isoformat() if primary else None,
            "primary_age_days": (datetime.utcnow() - primary.created_at).days if primary else None,
            "rotation_recommended": rotation_recommended,
            "max_age_days": settings.CLIENT_SECRET_MAX_AGE_DAYS,
            "secrets": [
                {
                    "id": str(s.id),
                    "prefix": s.secret_prefix,
                    "is_primary": s.is_primary,
                    "created_at": s.created_at.isoformat(),
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None,
                    "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
                    "is_valid": s.is_valid(),
                }
                for s in all_secrets
            ],
        }

    async def cleanup_expired_secrets(self) -> int:
        """
        Clean up expired and revoked secrets older than 30 days.

        Returns:
            Number of secrets deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=30)

        result = await self.db.execute(
            select(OAuthClientSecret).where(
                and_(
                    OAuthClientSecret.created_at < cutoff,
                    (OAuthClientSecret.expires_at < datetime.utcnow())
                    | (OAuthClientSecret.revoked_at.isnot(None)),
                )
            )
        )
        expired_secrets = result.scalars().all()

        deleted_count = 0
        for secret in expired_secrets:
            await self.db.delete(secret)
            deleted_count += 1

        if deleted_count > 0:
            await self.db.commit()
            logger.info("Cleaned up expired secrets", count=deleted_count)

        return deleted_count
