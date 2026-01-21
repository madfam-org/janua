"""
OAuth Consent Service

Manages user consent for OAuth client access, including checking existing
consents and storing new consent grants.
"""

from datetime import datetime
from typing import List, Set
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserConsent

logger = structlog.get_logger(__name__)


class ConsentService:
    """Service for managing OAuth user consents."""

    @staticmethod
    def parse_scopes(scope_string: str) -> Set[str]:
        """
        Parse a space-separated scope string into a set of scopes.

        Args:
            scope_string: Space-separated scopes (e.g., "openid profile email")

        Returns:
            Set of scope strings
        """
        if not scope_string:
            return set()
        return set(scope_string.strip().split())

    @staticmethod
    async def has_consent(
        db: AsyncSession,
        user_id: UUID,
        client_id: str,
        requested_scopes: Set[str],
    ) -> bool:
        """
        Check if user has already consented to the requested scopes for a client.

        Args:
            db: Database session
            user_id: User ID
            client_id: OAuth client ID
            requested_scopes: Set of requested scope strings

        Returns:
            True if user has consented to all requested scopes
        """
        result = await db.execute(
            select(UserConsent).where(
                and_(
                    UserConsent.user_id == user_id,
                    UserConsent.client_id == client_id,
                    UserConsent.revoked_at.is_(None),
                )
            )
        )
        consent = result.scalar_one_or_none()

        if not consent:
            return False

        # Check if consent has expired
        if consent.expires_at and consent.expires_at < datetime.utcnow():
            return False

        # Check if all requested scopes are covered
        granted_scopes = set(consent.scopes) if consent.scopes else set()
        return requested_scopes.issubset(granted_scopes)

    @staticmethod
    async def get_missing_scopes(
        db: AsyncSession,
        user_id: UUID,
        client_id: str,
        requested_scopes: Set[str],
    ) -> Set[str]:
        """
        Get scopes that the user hasn't yet consented to.

        Args:
            db: Database session
            user_id: User ID
            client_id: OAuth client ID
            requested_scopes: Set of requested scope strings

        Returns:
            Set of scopes requiring new consent
        """
        result = await db.execute(
            select(UserConsent).where(
                and_(
                    UserConsent.user_id == user_id,
                    UserConsent.client_id == client_id,
                    UserConsent.revoked_at.is_(None),
                )
            )
        )
        consent = result.scalar_one_or_none()

        if not consent:
            return requested_scopes

        # Check if consent has expired
        if consent.expires_at and consent.expires_at < datetime.utcnow():
            return requested_scopes

        granted_scopes = set(consent.scopes) if consent.scopes else set()
        return requested_scopes - granted_scopes

    @staticmethod
    async def grant_consent(
        db: AsyncSession,
        user_id: UUID,
        client_id: str,
        scopes: Set[str],
    ) -> UserConsent:
        """
        Store user consent for an OAuth client.

        If consent already exists, updates it with new scopes.

        Args:
            db: Database session
            user_id: User ID
            client_id: OAuth client ID
            scopes: Set of scope strings to grant

        Returns:
            The UserConsent record
        """
        result = await db.execute(
            select(UserConsent).where(
                and_(
                    UserConsent.user_id == user_id,
                    UserConsent.client_id == client_id,
                )
            )
        )
        consent = result.scalar_one_or_none()

        if consent:
            # Update existing consent with new scopes
            existing_scopes = set(consent.scopes) if consent.scopes else set()
            consent.scopes = list(existing_scopes.union(scopes))
            consent.granted_at = datetime.utcnow()
            consent.revoked_at = None  # Un-revoke if previously revoked
            consent.expires_at = None  # Clear expiration on new grant

            logger.info(
                "Updated OAuth consent",
                user_id=str(user_id),
                client_id=client_id,
                scopes=list(scopes),
            )
        else:
            # Create new consent
            consent = UserConsent(
                user_id=user_id,
                client_id=client_id,
                scopes=list(scopes),
                granted_at=datetime.utcnow(),
            )
            db.add(consent)

            logger.info(
                "Granted new OAuth consent",
                user_id=str(user_id),
                client_id=client_id,
                scopes=list(scopes),
            )

        await db.commit()
        await db.refresh(consent)
        return consent

    @staticmethod
    async def revoke_consent(
        db: AsyncSession,
        user_id: UUID,
        client_id: str,
    ) -> bool:
        """
        Revoke user consent for an OAuth client.

        Args:
            db: Database session
            user_id: User ID
            client_id: OAuth client ID

        Returns:
            True if consent was revoked, False if not found
        """
        result = await db.execute(
            select(UserConsent).where(
                and_(
                    UserConsent.user_id == user_id,
                    UserConsent.client_id == client_id,
                    UserConsent.revoked_at.is_(None),
                )
            )
        )
        consent = result.scalar_one_or_none()

        if not consent:
            return False

        consent.revoked_at = datetime.utcnow()
        await db.commit()

        logger.info(
            "Revoked OAuth consent",
            user_id=str(user_id),
            client_id=client_id,
        )

        return True

    @staticmethod
    async def list_consents(
        db: AsyncSession,
        user_id: UUID,
    ) -> List[UserConsent]:
        """
        List all active consents for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of UserConsent records
        """
        result = await db.execute(
            select(UserConsent)
            .where(
                and_(
                    UserConsent.user_id == user_id,
                    UserConsent.revoked_at.is_(None),
                )
            )
            .order_by(UserConsent.granted_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def get_scope_descriptions() -> dict:
        """
        Get human-readable descriptions for standard OAuth/OIDC scopes.

        Returns:
            Dictionary mapping scope names to descriptions
        """
        return {
            "openid": ("OpenID Connect", "Verify your identity"),
            "profile": ("Profile", "Access your name and profile information"),
            "email": ("Email", "Access your email address"),
            "address": ("Address", "Access your address information"),
            "phone": ("Phone", "Access your phone number"),
            "offline_access": ("Offline Access", "Access your data when you're not logged in"),
            "read:user": ("Read User", "Read your user information"),
            "write:user": ("Write User", "Update your user information"),
            "read:org": ("Read Organization", "Access organization information"),
            "write:org": ("Write Organization", "Modify organization information"),
        }
