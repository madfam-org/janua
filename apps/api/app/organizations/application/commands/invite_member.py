"""
Invite member command and handler
"""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID, uuid4

from app.models import OrganizationRole

from ...domain.models.membership import OrganizationInvitation
from ...domain.services.membership_service import MembershipService
from ...infrastructure.repositories.organization_repository import OrganizationRepository
from ..base import (
    Command,
    CommandHandler,
    ConflictError,
    NotFoundError,
    PermissionError,
    ValidationError,
)


@dataclass
class InviteMemberCommand(Command):
    """Command to invite a member to an organization"""

    organization_id: UUID
    email: str
    role: OrganizationRole
    permissions: List[str]
    inviter_id: UUID
    message: Optional[str] = None


@dataclass
class InviteMemberResult:
    """Result of inviting a member"""

    invitation: OrganizationInvitation


class InviteMemberHandler(CommandHandler[InviteMemberCommand, InviteMemberResult]):
    """Handler for inviting members to organizations"""

    def __init__(self, repository: OrganizationRepository):
        self.repository = repository
        self.membership_service = MembershipService()

    async def handle(self, command: InviteMemberCommand) -> InviteMemberResult:
        """Handle member invitation"""

        # Validate command
        await self._validate_command(command)

        # Get organization and verify it exists
        organization = await self.repository.find_by_id(command.organization_id)
        if not organization:
            raise NotFoundError("Organization not found")

        # Get inviter's membership and verify permissions
        inviter_membership = await self.repository.find_membership(
            command.organization_id, command.inviter_id
        )

        if not inviter_membership:
            raise PermissionError("Not a member of this organization")

        # Validate invitation role against inviter's role
        self.membership_service.validate_invitation_role(command.role, inviter_membership.role)

        # Check if user is already a member
        existing_member = await self.repository.find_user_by_email(command.email)
        if existing_member:
            existing_membership = await self.repository.find_membership(
                command.organization_id, existing_member.id
            )
            if existing_membership:
                raise ConflictError("User is already a member of this organization")

        # Check for existing pending invitation
        existing_invitation = await self.repository.find_pending_invitation(
            command.organization_id, command.email
        )
        if existing_invitation:
            raise ConflictError("An invitation has already been sent to this email")

        # Validate permissions
        self.membership_service.validate_permissions(command.permissions, command.role)

        # Create invitation
        invitation = OrganizationInvitation(
            id=uuid4(),
            organization_id=command.organization_id,
            email=command.email,
            role=command.role,
            permissions=command.permissions,
            token=self.membership_service.create_invitation_token(),
            invited_by=command.inviter_id,
            status="pending",
            expires_at=self.membership_service.calculate_invitation_expiry(),
        )

        # Save invitation
        saved_invitation = await self.repository.save_invitation(invitation)

        # Send invitation email
        import structlog

        from app.config import settings
        from app.core.redis import get_redis
        from app.services.resend_email_service import get_resend_email_service

        logger = structlog.get_logger()

        try:
            redis_client = await get_redis()
            email_service = get_resend_email_service(redis_client)

            # Get inviter details
            inviter = await self.repository.find_user_by_id(command.inviter_id)
            inviter_name = inviter.full_name if inviter and inviter.full_name else command.email

            invitation_url = f"{settings.FRONTEND_URL}/invitations/accept/{saved_invitation.token}"

            await email_service.send_invitation_email(
                to_email=command.email,
                inviter_name=inviter_name,
                organization_name=organization.name,
                role=command.role.value if hasattr(command.role, "value") else str(command.role),
                invitation_url=invitation_url,
                expires_at=saved_invitation.expires_at,
                teams=None,
            )
        except Exception as e:
            # Log email error but don't fail the invitation
            logger.error(
                f"Failed to send invitation email: {e}",
                email=command.email,
                organization_id=str(command.organization_id),
            )

        return InviteMemberResult(invitation=saved_invitation)

    async def _validate_command(self, command: InviteMemberCommand) -> None:
        """Validate the invite member command"""

        if not command.organization_id:
            raise ValidationError("Organization ID is required")

        if not command.email or not command.email.strip():
            raise ValidationError("Email is required")

        # Basic email validation
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, command.email):
            raise ValidationError("Invalid email format")

        if not isinstance(command.role, OrganizationRole):
            raise ValidationError("Valid role is required")

        if not isinstance(command.permissions, list):
            raise ValidationError("Permissions must be a list")

        if not command.inviter_id:
            raise ValidationError("Inviter ID is required")

        if command.message and len(command.message) > 1000:
            raise ValidationError("Message cannot exceed 1000 characters")
