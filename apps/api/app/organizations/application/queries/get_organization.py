"""
Get organization query and handler
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from ..base import Query, QueryHandler, NotFoundError, PermissionError
from ...domain.models.organization import Organization
from ...domain.models.membership import Membership
from ...domain.services.membership_service import MembershipService
from ...infrastructure.repositories.organization_repository import OrganizationRepository


@dataclass
class GetOrganizationQuery(Query):
    """Query to get organization details"""

    organization_id: UUID
    user_id: UUID


@dataclass
class GetOrganizationResult:
    """Result of getting an organization"""

    organization: Organization
    membership: Optional[Membership]
    member_count: int
    is_owner: bool
    user_role: Optional[str]


class GetOrganizationHandler(QueryHandler[GetOrganizationQuery, GetOrganizationResult]):
    """Handler for getting organization details"""

    def __init__(self, repository: OrganizationRepository):
        self.repository = repository
        self.membership_service = MembershipService()

    async def handle(self, query: GetOrganizationQuery) -> GetOrganizationResult:
        """Handle getting organization details"""

        # Get organization
        organization = await self.repository.find_by_id(query.organization_id)
        if not organization:
            raise NotFoundError("Organization not found")

        # Get user's membership
        membership = await self.repository.find_membership(query.organization_id, query.user_id)

        # Check access permissions
        is_owner = organization.is_owner(query.user_id)
        if not is_owner and not membership:
            raise PermissionError("Not a member of this organization")

        # Get member count
        member_count = await self.repository.get_member_count(query.organization_id)

        # Determine user role
        user_role = None
        if is_owner:
            user_role = "owner"
        elif membership:
            user_role = membership.role.value

        return GetOrganizationResult(
            organization=organization,
            membership=membership,
            member_count=member_count,
            is_owner=is_owner,
            user_role=user_role,
        )
