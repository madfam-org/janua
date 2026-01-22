"""
Organization repository implementation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import (
    Organization as ORMOrganization,
    OrganizationInvitation as ORMOrganizationInvitation,
    User,
    organization_members
)
from ...domain.models.organization import Organization
from ...domain.models.membership import Membership, OrganizationInvitation

if TYPE_CHECKING:
    pass  # No circular imports needed here


@dataclass
class MembershipWithUser:
    """Membership with user details - defined here to avoid circular import"""

    membership: Membership
    user: User


class OrganizationRepository:
    """Repository for organization data access"""

    def __init__(self, db: Session):
        self.db = db

    async def find_by_id(self, organization_id: UUID) -> Optional[Organization]:
        """Find organization by ID"""
        orm_org = self.db.query(ORMOrganization).filter(
            ORMOrganization.id == organization_id
        ).first()

        if not orm_org:
            return None

        return self._map_orm_to_domain(orm_org)

    async def find_by_slug(self, slug: str) -> Optional[Organization]:
        """Find organization by slug"""
        orm_org = self.db.query(ORMOrganization).filter(
            ORMOrganization.slug == slug
        ).first()

        if not orm_org:
            return None

        return self._map_orm_to_domain(orm_org)

    async def save(self, organization: Organization) -> Organization:
        """Save organization to database"""
        # Check if this is an update or create
        existing = self.db.query(ORMOrganization).filter(
            ORMOrganization.id == organization.id
        ).first()

        if existing:
            # Update existing
            existing.name = organization.name
            existing.slug = organization.slug
            existing.description = organization.description
            existing.logo_url = organization.logo_url
            existing.owner_id = organization.owner_id
            existing.settings = organization.settings
            existing.org_metadata = organization.org_metadata
            existing.billing_email = organization.billing_email
            existing.billing_plan = organization.billing_plan
            existing.updated_at = organization.updated_at

            self.db.flush()
            self.db.refresh(existing)
            return self._map_orm_to_domain(existing)
        else:
            # Create new
            orm_org = ORMOrganization(
                id=organization.id,
                name=organization.name,
                slug=organization.slug,
                description=organization.description,
                logo_url=organization.logo_url,
                owner_id=organization.owner_id,
                settings=organization.settings,
                org_metadata=organization.org_metadata,
                billing_email=organization.billing_email,
                billing_plan=organization.billing_plan,
                created_at=organization.created_at,
                updated_at=organization.updated_at
            )

            self.db.add(orm_org)
            self.db.flush()
            self.db.refresh(orm_org)

            return self._map_orm_to_domain(orm_org)

    async def delete(self, organization_id: UUID) -> bool:
        """Delete organization"""
        orm_org = self.db.query(ORMOrganization).filter(
            ORMOrganization.id == organization_id
        ).first()

        if not orm_org:
            return False

        self.db.delete(orm_org)
        return True

    async def find_membership(self, organization_id: UUID, user_id: UUID) -> Optional[Membership]:
        """Find user's membership in organization"""
        member_row = self.db.query(organization_members).filter(
            and_(
                organization_members.c.organization_id == organization_id,
                organization_members.c.user_id == user_id
            )
        ).first()

        if not member_row:
            return None

        return Membership(
            organization_id=member_row.organization_id,
            user_id=member_row.user_id,
            role=member_row.role,
            permissions=member_row.permissions or [],
            joined_at=member_row.joined_at,
            invited_by=member_row.invited_by
        )

    async def add_membership(self, membership: Membership) -> Membership:
        """Add a new membership"""
        self.db.execute(
            organization_members.insert().values(
                organization_id=membership.organization_id,
                user_id=membership.user_id,
                role=membership.role,
                permissions=membership.permissions,
                joined_at=membership.joined_at,
                invited_by=membership.invited_by
            )
        )
        self.db.flush()
        return membership

    async def update_membership(self, membership: Membership) -> Membership:
        """Update an existing membership"""
        self.db.execute(
            organization_members.update().where(
                and_(
                    organization_members.c.organization_id == membership.organization_id,
                    organization_members.c.user_id == membership.user_id
                )
            ).values(
                role=membership.role,
                permissions=membership.permissions
            )
        )
        self.db.flush()
        return membership

    async def remove_membership(self, organization_id: UUID, user_id: UUID) -> bool:
        """Remove a membership"""
        result = self.db.execute(
            organization_members.delete().where(
                and_(
                    organization_members.c.organization_id == organization_id,
                    organization_members.c.user_id == user_id
                )
            )
        )
        return result.rowcount > 0

    async def list_memberships_with_users(self, organization_id: UUID) -> List[MembershipWithUser]:
        """List all memberships with user details"""
        results = self.db.query(
            User,
            organization_members.c.role,
            organization_members.c.permissions,
            organization_members.c.joined_at,
            organization_members.c.invited_by
        ).join(
            organization_members,
            User.id == organization_members.c.user_id
        ).filter(
            organization_members.c.organization_id == organization_id
        ).all()

        memberships_with_users = []
        for user, role, permissions, joined_at, invited_by in results:
            membership = Membership(
                organization_id=organization_id,
                user_id=user.id,
                role=role,
                permissions=permissions or [],
                joined_at=joined_at,
                invited_by=invited_by
            )

            memberships_with_users.append(
                MembershipWithUser(membership=membership, user=user)
            )

        return memberships_with_users

    async def get_member_count(self, organization_id: UUID) -> int:
        """Get count of organization members"""
        count = self.db.query(func.count(organization_members.c.user_id)).filter(
            organization_members.c.organization_id == organization_id
        ).scalar()

        return count or 0

    async def find_user_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        return self.db.query(User).filter(User.email == email).first()

    async def find_pending_invitation(self, organization_id: UUID, email: str) -> Optional[OrganizationInvitation]:
        """Find pending invitation by organization and email"""
        orm_invitation = self.db.query(ORMOrganizationInvitation).filter(
            and_(
                ORMOrganizationInvitation.organization_id == organization_id,
                ORMOrganizationInvitation.email == email,
                ORMOrganizationInvitation.status == "pending",
                ORMOrganizationInvitation.expires_at > datetime.utcnow()
            )
        ).first()

        if not orm_invitation:
            return None

        return self._map_orm_invitation_to_domain(orm_invitation)

    async def save_invitation(self, invitation: OrganizationInvitation) -> OrganizationInvitation:
        """Save invitation to database"""
        orm_invitation = ORMOrganizationInvitation(
            id=invitation.id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=invitation.role,
            permissions=invitation.permissions,
            token=invitation.token,
            invited_by=invitation.invited_by,
            status=invitation.status,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            accepted_at=invitation.accepted_at
        )

        self.db.add(orm_invitation)
        self.db.flush()
        self.db.refresh(orm_invitation)

        return self._map_orm_invitation_to_domain(orm_invitation)

    async def list_user_organizations(self, user_id: UUID) -> List[tuple[Organization, str]]:
        """List organizations where user is a member"""
        results = self.db.query(
            ORMOrganization,
            organization_members.c.role
        ).join(
            organization_members,
            ORMOrganization.id == organization_members.c.organization_id
        ).filter(
            organization_members.c.user_id == user_id
        ).all()

        organizations = []
        for orm_org, role in results:
            organization = self._map_orm_to_domain(orm_org)
            organizations.append((organization, role.value))

        return organizations

    def _map_orm_to_domain(self, orm_org: ORMOrganization) -> Organization:
        """Map ORM organization to domain model"""
        return Organization(
            id=orm_org.id,
            name=orm_org.name,
            slug=orm_org.slug,
            description=orm_org.description,
            logo_url=orm_org.logo_url,
            owner_id=orm_org.owner_id,
            settings=orm_org.settings or {},
            org_metadata=orm_org.org_metadata or {},
            billing_email=orm_org.billing_email,
            billing_plan=orm_org.billing_plan,
            created_at=orm_org.created_at,
            updated_at=orm_org.updated_at
        )

    def _map_orm_invitation_to_domain(self, orm_invitation: ORMOrganizationInvitation) -> OrganizationInvitation:
        """Map ORM invitation to domain model"""
        return OrganizationInvitation(
            id=orm_invitation.id,
            organization_id=orm_invitation.organization_id,
            email=orm_invitation.email,
            role=orm_invitation.role,
            permissions=orm_invitation.permissions or [],
            token=orm_invitation.token,
            invited_by=orm_invitation.invited_by,
            status=orm_invitation.status,
            created_at=orm_invitation.created_at,
            expires_at=orm_invitation.expires_at,
            accepted_at=orm_invitation.accepted_at
        )