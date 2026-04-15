"""
API Key Management Service

Business logic for creating, validating, and managing API keys.
Follows the same patterns as OAuthClientService for consistency.

Supports two key formats:
- Legacy: jnk_<random> (bcrypt hashed) -- existing keys
- Modern: sk_live_<hex> (SHA-256 hashed) -- new keys for external consumers / AI agents
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, AuditLog, OrganizationMember, User
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate

logger = logging.getLogger(__name__)

# Prefix for modern API keys (external consumers, AI agents)
SK_LIVE_PREFIX = "sk_live_"


class ApiKeyService:
    """Service for API key management operations"""

    # Configuration
    KEY_LENGTH = 48  # Length of random part (base64 encoded)
    KEY_PREFIX = "jnk_"  # Janua Key prefix (legacy)
    DISPLAY_PREFIX_LENGTH = 12  # Characters to show in display prefix

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Key generation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_api_key() -> Tuple[str, str, str]:
        """
        Generate a new API key with hash and display prefix (legacy format).

        Returns:
            Tuple of (plain_key, hashed_key, display_prefix)
        """
        random_part = secrets.token_urlsafe(ApiKeyService.KEY_LENGTH)
        plain_key = f"{ApiKeyService.KEY_PREFIX}{random_part}"

        # Hash the key using bcrypt
        hashed = bcrypt.hashpw(plain_key.encode(), bcrypt.gensalt()).decode()

        # Create display prefix (first 12 chars + ...)
        display_prefix = plain_key[: ApiKeyService.DISPLAY_PREFIX_LENGTH] + "..."

        return plain_key, hashed, display_prefix

    @staticmethod
    def generate_sk_live_key() -> Tuple[str, str, str]:
        """
        Generate a modern sk_live_ key with SHA-256 hash.

        Returns:
            Tuple of (full_key, sha256_hex_hash, key_prefix)
            key_prefix format: "sk_live_" + first 4 hex chars of the random part
        """
        random_hex = secrets.token_hex(32)  # 64 hex chars
        full_key = f"{SK_LIVE_PREFIX}{random_hex}"
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        key_prefix = f"{SK_LIVE_PREFIX}{random_hex[:4]}"
        return full_key, key_hash, key_prefix

    @staticmethod
    def hash_key_sha256(plain_key: str) -> str:
        """Hash a key with SHA-256 for constant-time lookup."""
        return hashlib.sha256(plain_key.encode()).hexdigest()

    @staticmethod
    def verify_api_key(plain_key: str, hashed_key: str) -> bool:
        """
        Verify an API key against its hash.
        Supports both bcrypt (legacy jnk_) and SHA-256 (modern sk_live_) formats.

        Args:
            plain_key: The plain text API key
            hashed_key: The bcrypt or SHA-256 hash to verify against

        Returns:
            True if the key is valid, False otherwise
        """
        try:
            # SHA-256 hashes are exactly 64 hex chars
            if len(hashed_key) == 64 and all(c in '0123456789abcdef' for c in hashed_key):
                return hashlib.sha256(plain_key.encode()).hexdigest() == hashed_key
            # Fall back to bcrypt verification for legacy keys
            return bcrypt.checkpw(plain_key.encode(), hashed_key.encode())
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return False

    async def create_api_key(
        self,
        data: ApiKeyCreate,
        user: User,
        organization_id: uuid.UUID,
        use_sk_live: bool = True,
    ) -> Tuple[ApiKey, str]:
        """
        Create a new API key.

        Args:
            data: API key creation data
            user: User creating the key
            organization_id: Organization the key belongs to
            use_sk_live: If True, generate modern sk_live_ key with SHA-256.
                         If False, generate legacy jnk_ key with bcrypt.

        Returns:
            Tuple of (created ApiKey model, plain text key)
        """
        # Generate the key
        if use_sk_live:
            plain_key, hashed_key, visible_prefix = self.generate_sk_live_key()
        else:
            plain_key, hashed_key, visible_prefix = self.generate_api_key()

        # Display prefix for backward compat (first 12 chars + ...)
        display_prefix = plain_key[: self.DISPLAY_PREFIX_LENGTH] + "..."

        # Create the API key record
        api_key = ApiKey(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization_id,
            name=data.name,
            key_hash=hashed_key,
            prefix=display_prefix,
            key_prefix=visible_prefix,
            scopes=data.scopes,
            rate_limit_per_min=getattr(data, "rate_limit_per_min", 60),
            is_active=True,
            expires_at=data.expires_at,
        )

        self.db.add(api_key)

        # Create audit log entry
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            action="api_key_created",
            resource_type="api_key",
            resource_id=str(api_key.id),
            details={
                "api_key_name": data.name,
                "scopes": data.scopes,
                "rate_limit_per_min": api_key.rate_limit_per_min,
                "expires_at": data.expires_at.isoformat() if data.expires_at else None,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info(
            f"API key created: {api_key.id} for user {user.id} in org {organization_id}"
        )

        return api_key, plain_key

    async def list_api_keys(
        self,
        user: User,
        organization_id: Optional[uuid.UUID] = None,
        page: int = 1,
        per_page: int = 20,
        include_inactive: bool = False,
    ) -> Tuple[List[ApiKey], int]:
        """
        List API keys for a user or organization.

        Args:
            user: The user requesting the list
            organization_id: Optional organization filter
            page: Page number (1-indexed)
            per_page: Items per page (max 100)
            include_inactive: Whether to include inactive/revoked keys

        Returns:
            Tuple of (list of ApiKey models, total count)
        """
        # Validate pagination
        page = max(1, page)
        per_page = min(max(1, per_page), 100)
        offset = (page - 1) * per_page

        # Build base query
        query = select(ApiKey).where(ApiKey.user_id == user.id)

        if organization_id:
            query = query.where(ApiKey.organization_id == organization_id)

        if not include_inactive:
            query = query.where(ApiKey.is_active == True)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(ApiKey.created_at.desc()).offset(offset).limit(per_page)
        result = await self.db.execute(query)
        api_keys = list(result.scalars().all())

        return api_keys, total

    async def get_api_key(
        self,
        api_key_id: uuid.UUID,
        user: User,
    ) -> Optional[ApiKey]:
        """
        Get a single API key by ID.

        Args:
            api_key_id: The API key ID
            user: The user requesting the key (for authorization)

        Returns:
            The ApiKey model if found and authorized, None otherwise
        """
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.user_id == user.id,
            )
        )
        return result.scalar_one_or_none()

    async def get_api_key_by_prefix(self, prefix: str) -> Optional[ApiKey]:
        """
        Get an API key by its display prefix.

        Useful for API key authentication flows.

        Args:
            prefix: The display prefix (e.g., "jnk_abc123...")

        Returns:
            The ApiKey model if found, None otherwise
        """
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.prefix == prefix,
                ApiKey.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def update_api_key(
        self,
        api_key_id: uuid.UUID,
        data: ApiKeyUpdate,
        user: User,
    ) -> Optional[ApiKey]:
        """
        Update an API key.

        Args:
            api_key_id: The API key ID
            data: Update data
            user: The user making the update

        Returns:
            The updated ApiKey model, or None if not found/unauthorized
        """
        api_key = await self.get_api_key(api_key_id, user)
        if not api_key:
            return None

        # Track changes for audit log
        changes = {}

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            old_value = getattr(api_key, field)
            if old_value != value:
                changes[field] = {"old": old_value, "new": value}
                setattr(api_key, field, value)

        if changes:
            api_key.updated_at = datetime.utcnow()

            # Create audit log entry
            audit_log = AuditLog(
                id=uuid.uuid4(),
                user_id=user.id,
                action="api_key_updated",
                resource_type="api_key",
                resource_id=str(api_key.id),
                details={
                    "api_key_name": api_key.name,
                    "organization_id": str(api_key.organization_id),
                    "changes": changes,
                },
            )
            self.db.add(audit_log)

            await self.db.commit()
            await self.db.refresh(api_key)

            logger.info(f"API key updated: {api_key.id} by user {user.id}")

        return api_key

    async def delete_api_key(
        self,
        api_key_id: uuid.UUID,
        user: User,
    ) -> bool:
        """
        Delete (revoke) an API key.

        This performs a soft delete by setting is_active=False and revoked_at.

        Args:
            api_key_id: The API key ID
            user: The user performing the deletion

        Returns:
            True if deleted, False if not found/unauthorized
        """
        api_key = await self.get_api_key(api_key_id, user)
        if not api_key:
            return False

        # Soft delete
        now = datetime.utcnow()
        api_key.is_active = False
        api_key.revoked_at = now
        api_key.updated_at = now

        # Create audit log entry
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            action="api_key_revoked",
            resource_type="api_key",
            resource_id=str(api_key.id),
            details={
                "api_key_name": api_key.name,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()

        logger.info(f"API key revoked: {api_key.id} by user {user.id}")

        return True

    async def rotate_api_key(
        self,
        api_key_id: uuid.UUID,
        user: User,
    ) -> Optional[Tuple[ApiKey, str, str]]:
        """
        Rotate an API key by generating a new secret.

        The old key is immediately invalidated.

        Args:
            api_key_id: The API key ID
            user: The user performing the rotation

        Returns:
            Tuple of (updated ApiKey, new plain key, old prefix) or None if not found
        """
        api_key = await self.get_api_key(api_key_id, user)
        if not api_key:
            return None

        # Store old prefix for response
        old_prefix = api_key.prefix

        # Generate new key
        plain_key, hashed_key, display_prefix = self.generate_api_key()

        # Update the key
        api_key.key_hash = hashed_key
        api_key.prefix = display_prefix
        api_key.updated_at = datetime.utcnow()

        # Create audit log entry
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            action="api_key_rotated",
            resource_type="api_key",
            resource_id=str(api_key.id),
            details={
                "api_key_name": api_key.name,
                "organization_id": str(api_key.organization_id),
                "old_prefix": old_prefix,
                "new_prefix": display_prefix,
            },
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info(f"API key rotated: {api_key.id} by user {user.id}")

        return api_key, plain_key, old_prefix

    async def update_last_used(self, api_key: ApiKey) -> None:
        """
        Update the last_used timestamp for an API key.

        Called when the key is used for authentication.

        Args:
            api_key: The API key that was used
        """
        api_key.last_used = datetime.utcnow()
        await self.db.commit()

    async def validate_and_get_user(
        self,
        plain_key: str,
    ) -> Optional[Tuple[User, ApiKey]]:
        """
        Validate an API key and return the associated user.

        This is the main authentication flow for API keys.
        Supports both legacy jnk_ and modern sk_live_ key formats.

        Args:
            plain_key: The plain text API key

        Returns:
            Tuple of (User, ApiKey) if valid, None if invalid
        """
        api_key = await self._resolve_api_key(plain_key)
        if not api_key:
            return None

        # Get the user
        result = await self.db.execute(select(User).where(User.id == api_key.user_id))
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Update last used timestamp
        await self.update_last_used(api_key)

        return user, api_key

    async def verify_key_for_service(
        self,
        plain_key: str,
    ) -> Optional[ApiKey]:
        """
        Verify an API key and return the key record (for service-to-service calls).

        Unlike validate_and_get_user, this does NOT load the User object --
        it returns only the ApiKey so the caller can extract org_id and scopes.

        Args:
            plain_key: The plain text API key

        Returns:
            The ApiKey record if valid, None if invalid/revoked/expired
        """
        api_key = await self._resolve_api_key(plain_key)
        if not api_key:
            return None

        # Update last used timestamp
        await self.update_last_used(api_key)
        return api_key

    async def _resolve_api_key(self, plain_key: str) -> Optional[ApiKey]:
        """
        Internal helper: look up and verify an API key by its plain text value.

        Supports two lookup strategies:
        - sk_live_ keys: SHA-256 hash lookup (constant-time, no scan)
        - jnk_ keys: prefix lookup + bcrypt verify (legacy)

        Returns:
            The verified ApiKey record, or None
        """
        if plain_key.startswith(SK_LIVE_PREFIX):
            # Modern format: direct hash lookup
            key_hash = self.hash_key_sha256(plain_key)
            result = await self.db.execute(
                select(ApiKey).where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active == True,
                    ApiKey.revoked_at == None,
                )
            )
            api_key = result.scalar_one_or_none()
        elif plain_key.startswith(self.KEY_PREFIX):
            # Legacy format: prefix lookup + bcrypt verify
            display_prefix = plain_key[: self.DISPLAY_PREFIX_LENGTH] + "..."
            result = await self.db.execute(
                select(ApiKey).where(
                    ApiKey.prefix == display_prefix,
                    ApiKey.is_active == True,
                    ApiKey.revoked_at == None,
                )
            )
            api_key = result.scalar_one_or_none()
            if api_key and not self.verify_api_key(plain_key, api_key.key_hash):
                return None
        else:
            return None

        if not api_key:
            return None

        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            logger.info(f"API key expired: {api_key.id}")
            return None

        return api_key

    async def check_user_can_manage_key(
        self,
        api_key_id: uuid.UUID,
        user: User,
    ) -> bool:
        """
        Check if a user can manage an API key.

        A user can manage a key if:
        - They own the key, OR
        - They are an admin/owner of the key's organization

        Args:
            api_key_id: The API key ID
            user: The user to check

        Returns:
            True if authorized, False otherwise
        """
        # Check if user owns the key
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.user_id == user.id,
            )
        )
        if result.scalar_one_or_none():
            return True

        # Check if user is org admin
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.id == api_key_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return False

        # Check org membership
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == api_key.organization_id,
                OrganizationMember.role.in_(["admin", "owner"]),
            )
        )
        return result.scalar_one_or_none() is not None
