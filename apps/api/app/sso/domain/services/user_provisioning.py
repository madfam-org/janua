"""
User provisioning service for SSO
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User

from ...exceptions import ValidationError
from ..protocols.base import SSOConfiguration, UserProvisioningData


class UserProvisioningService:
    """Service for provisioning users from SSO authentication"""

    def __init__(self, db: AsyncSession, audit_logger=None):
        self.db = db
        self.audit_logger = audit_logger

    async def provision_user(
        self,
        user_data: UserProvisioningData,
        organization_id: str,
        sso_config: SSOConfiguration,
        session_data: Optional[Dict[str, Any]] = None,
    ) -> User:
        """
        Provision user from SSO authentication

        Args:
            user_data: Mapped user data from SSO response
            organization_id: Organization ID for the user
            sso_config: SSO configuration settings
            session_data: Additional session information

        Returns:
            User object (existing or newly created)
        """

        # Check if user already exists
        existing_user = await self._find_existing_user(user_data.email, organization_id)

        if existing_user:
            # Update existing user if JIT provisioning allows updates
            if sso_config.jit_provisioning:
                updated_user = await self._update_existing_user(
                    existing_user, user_data, sso_config
                )
                await self._log_user_update(updated_user, user_data, session_data)
                return updated_user
            else:
                await self._log_user_login(existing_user, session_data)
                return existing_user

        # Create new user if JIT provisioning is enabled
        if not sso_config.jit_provisioning:
            raise ValidationError(
                f"User {user_data.email} not found and JIT provisioning is disabled"
            )

        new_user = await self._create_new_user(user_data, organization_id, sso_config)

        await self._log_user_creation(new_user, user_data, session_data)

        return new_user

    async def _find_existing_user(self, email: str, organization_id: str) -> Optional[User]:
        """Find existing user by email and organization"""

        stmt = select(User).where(User.email == email, User.organization_id == organization_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_new_user(
        self, user_data: UserProvisioningData, organization_id: str, sso_config: SSOConfiguration
    ) -> User:
        """Create new user from SSO data"""

        # Validate organization exists
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org_result = await self.db.execute(org_stmt)
        organization = org_result.scalar_one_or_none()

        if not organization:
            raise ValidationError(f"Organization {organization_id} not found")

        # Create user
        user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            display_name=user_data.display_name or user_data.get_full_name(),
            organization_id=organization_id,
            role=sso_config.default_role,
            is_active=True,
            email_verified=True,  # SSO implies verified email
            sso_provider=sso_config.protocol,
            sso_subject_id=user_data.attributes.get("sub") or user_data.email,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def _update_existing_user(
        self, user: User, user_data: UserProvisioningData, sso_config: SSOConfiguration
    ) -> User:
        """Update existing user with SSO data"""

        # Update user attributes if they've changed
        updated = False

        if user_data.first_name and user.first_name != user_data.first_name:
            user.first_name = user_data.first_name
            updated = True

        if user_data.last_name and user.last_name != user_data.last_name:
            user.last_name = user_data.last_name
            updated = True

        if user_data.display_name and user.display_name != user_data.display_name:
            user.display_name = user_data.display_name
            updated = True

        # Update SSO-specific fields
        if user.sso_provider != sso_config.protocol:
            user.sso_provider = sso_config.protocol
            updated = True

        sso_subject_id = user_data.attributes.get("sub") or user_data.email
        if user.sso_subject_id != sso_subject_id:
            user.sso_subject_id = sso_subject_id
            updated = True

        if updated:
            user.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)

        return user

    async def _log_user_creation(
        self, user: User, user_data: UserProvisioningData, session_data: Optional[Dict[str, Any]]
    ):
        """Log user creation event"""

        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type="user_created",
                user_id=user.id,
                organization_id=user.organization_id,
                details={
                    "method": "sso_jit_provisioning",
                    "protocol": session_data.get("protocol") if session_data else None,
                    "email": user_data.email,
                    "provisioned": True,
                },
            )

    async def _log_user_update(
        self, user: User, user_data: UserProvisioningData, session_data: Optional[Dict[str, Any]]
    ):
        """Log user update event"""

        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type="user_updated",
                user_id=user.id,
                organization_id=user.organization_id,
                details={
                    "method": "sso_attribute_sync",
                    "protocol": session_data.get("protocol") if session_data else None,
                    "email": user_data.email,
                    "updated": True,
                },
            )

    async def _log_user_login(self, user: User, session_data: Optional[Dict[str, Any]]):
        """Log user login event"""

        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type="user_login",
                user_id=user.id,
                organization_id=user.organization_id,
                details={
                    "method": "sso_authentication",
                    "protocol": session_data.get("protocol") if session_data else None,
                    "login_time": datetime.utcnow().isoformat(),
                },
            )

    async def validate_user_access(self, user: User, sso_config: SSOConfiguration) -> bool:
        """Validate user access based on SSO configuration"""

        # Check if user is active
        if not user.is_active:
            return False

        # Check domain restrictions
        if sso_config.config.get("allowed_domains"):
            user_domain = user.email.split("@")[1].lower()
            allowed_domains = [d.lower() for d in sso_config.config["allowed_domains"]]
            if user_domain not in allowed_domains:
                return False

        # Check role restrictions
        if sso_config.config.get("allowed_roles"):
            if user.role not in sso_config.config["allowed_roles"]:
                return False

        return True
