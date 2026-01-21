"""
Create organization command and handler
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


from app.models import OrganizationRole
from ..base import Command, CommandHandler, ConflictError, ValidationError
from ...domain.models.organization import Organization
from ...domain.models.membership import Membership
from ...infrastructure.repositories.organization_repository import OrganizationRepository


@dataclass
class CreateOrganizationCommand(Command):
    """Command to create a new organization"""

    name: str
    slug: str
    description: Optional[str]
    billing_email: Optional[str]
    owner_id: UUID
    owner_email: str


@dataclass
class CreateOrganizationResult:
    """Result of creating an organization"""

    organization: Organization
    membership: Membership


class CreateOrganizationHandler(CommandHandler[CreateOrganizationCommand, CreateOrganizationResult]):
    """Handler for creating organizations"""

    def __init__(self, repository: OrganizationRepository):
        self.repository = repository

    async def handle(self, command: CreateOrganizationCommand) -> CreateOrganizationResult:
        """Handle organization creation"""

        # Validate command
        await self._validate_command(command)

        # Check if slug is already taken
        existing_org = await self.repository.find_by_slug(command.slug)
        if existing_org:
            raise ConflictError("Organization slug already exists")

        # Create organization domain object
        organization = Organization(
            name=command.name,
            slug=command.slug.lower(),
            description=command.description,
            owner_id=command.owner_id,
            billing_email=command.billing_email or command.owner_email,
            billing_plan="free",
            settings={},
            org_metadata={}
        )

        # Create owner membership
        membership = Membership(
            organization_id=organization.id,
            user_id=command.owner_id,
            role=OrganizationRole.ADMIN,  # Owner gets admin role in membership table
            permissions=[]
        )

        # Save to repository
        saved_org = await self.repository.save(organization)
        await self.repository.add_membership(membership)

        return CreateOrganizationResult(
            organization=saved_org,
            membership=membership
        )

    async def _validate_command(self, command: CreateOrganizationCommand) -> None:
        """Validate the create organization command"""

        if not command.name or not command.name.strip():
            raise ValidationError("Organization name is required")

        if len(command.name) > 200:
            raise ValidationError("Organization name cannot exceed 200 characters")

        if not command.slug or not command.slug.strip():
            raise ValidationError("Organization slug is required")

        if len(command.slug) > 100:
            raise ValidationError("Organization slug cannot exceed 100 characters")

        # Validate slug format
        import re
        if not re.match(r'^[a-z0-9-]+$', command.slug.lower()):
            raise ValidationError("Organization slug must contain only lowercase letters, numbers, and hyphens")

        if command.description and len(command.description) > 1000:
            raise ValidationError("Organization description cannot exceed 1000 characters")

        if not command.owner_id:
            raise ValidationError("Owner ID is required")

        if not command.owner_email:
            raise ValidationError("Owner email is required")