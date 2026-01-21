"""
Organization REST controller - thin layer handling HTTP concerns only
"""

from typing import List
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.v1.auth import get_current_user

from ...application.commands.create_organization import CreateOrganizationCommand, CreateOrganizationHandler
from ...application.commands.invite_member import InviteMemberCommand, InviteMemberHandler
from ...application.queries.get_organization import GetOrganizationQuery, GetOrganizationHandler
from ...application.queries.list_memberships import ListMembershipsQuery, ListMembershipsHandler
from ...application.base import ApplicationError, ValidationError, NotFoundError, PermissionError, ConflictError
from ...infrastructure.repositories.organization_repository import OrganizationRepository

from .dto.requests import CreateOrganizationRequest, InviteMemberRequest
from .dto.responses import (
    OrganizationResponse, MemberResponse, InviteResultResponse,
    SuccessResponse
)


class OrganizationController:
    """Slim controller handling only HTTP concerns"""

    def __init__(self, db: Session = Depends(get_db)):
        self.repository = OrganizationRepository(db)
        self.db = db

    async def create_organization(
        self,
        request: CreateOrganizationRequest,
        current_user: User = Depends(get_current_user)
    ) -> OrganizationResponse:
        """Create a new organization"""
        try:
            # Create command
            command = CreateOrganizationCommand(
                name=request.name,
                slug=request.slug,
                description=request.description,
                billing_email=request.billing_email,
                owner_id=current_user.id,
                owner_email=current_user.email
            )

            # Execute command
            handler = CreateOrganizationHandler(self.repository)
            result = await handler.handle(command)

            # Commit transaction
            self.db.commit()

            # Return response
            return OrganizationResponse(
                id=str(result.organization.id),
                name=result.organization.name,
                slug=result.organization.slug,
                description=result.organization.description,
                logo_url=result.organization.logo_url,
                owner_id=str(result.organization.owner_id),
                settings=result.organization.settings,
                org_metadata=result.organization.org_metadata,
                billing_email=result.organization.billing_email,
                billing_plan=result.organization.billing_plan,
                created_at=result.organization.created_at,
                updated_at=result.organization.updated_at,
                member_count=1,  # Just created, owner is the only member
                is_owner=True,
                user_role="admin"
            )

        except ValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
        except ConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
        except ApplicationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message)
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

    async def get_organization(
        self,
        org_id: str,
        current_user: User = Depends(get_current_user)
    ) -> OrganizationResponse:
        """Get organization details"""
        try:
            # Validate org_id format
            try:
                org_uuid = UUID(org_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

            # Create query
            query = GetOrganizationQuery(
                organization_id=org_uuid,
                user_id=current_user.id
            )

            # Execute query
            handler = GetOrganizationHandler(self.repository)
            result = await handler.handle(query)

            # Return response
            return OrganizationResponse(
                id=str(result.organization.id),
                name=result.organization.name,
                slug=result.organization.slug,
                description=result.organization.description,
                logo_url=result.organization.logo_url,
                owner_id=str(result.organization.owner_id),
                settings=result.organization.settings,
                org_metadata=result.organization.org_metadata,
                billing_email=result.organization.billing_email,
                billing_plan=result.organization.billing_plan,
                created_at=result.organization.created_at,
                updated_at=result.organization.updated_at,
                member_count=result.member_count,
                is_owner=result.is_owner,
                user_role=result.user_role
            )

        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
        except ApplicationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message)

    async def list_organizations(
        self,
        current_user: User = Depends(get_current_user)
    ) -> List[OrganizationResponse]:
        """List user's organizations"""
        try:
            # Get user's organizations from repository
            user_orgs = await self.repository.list_user_organizations(current_user.id)

            results = []
            for organization, role in user_orgs:
                # Get member count for each organization
                member_count = await self.repository.get_member_count(organization.id)

                results.append(OrganizationResponse(
                    id=str(organization.id),
                    name=organization.name,
                    slug=organization.slug,
                    description=organization.description,
                    logo_url=organization.logo_url,
                    owner_id=str(organization.owner_id),
                    settings=organization.settings,
                    org_metadata=organization.org_metadata,
                    billing_email=organization.billing_email,
                    billing_plan=organization.billing_plan,
                    created_at=organization.created_at,
                    updated_at=organization.updated_at,
                    member_count=member_count,
                    is_owner=organization.is_owner(current_user.id),
                    user_role=role
                ))

            return results

        except ApplicationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message)

    async def invite_member(
        self,
        org_id: str,
        request: InviteMemberRequest,
        current_user: User = Depends(get_current_user)
    ) -> InviteResultResponse:
        """Invite a member to the organization"""
        try:
            # Validate org_id format
            try:
                org_uuid = UUID(org_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

            # Create command
            command = InviteMemberCommand(
                organization_id=org_uuid,
                email=request.email,
                role=request.role,
                permissions=request.permissions,
                inviter_id=current_user.id,
                message=request.message
            )

            # Execute command
            handler = InviteMemberHandler(self.repository)
            result = await handler.handle(command)

            # Commit transaction
            self.db.commit()

            # Return response
            return InviteResultResponse(
                message="Invitation sent successfully",
                invitation_id=str(result.invitation.id),
                expires_at=result.invitation.expires_at
            )

        except ValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
        except ConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
        except ApplicationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message)
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

    async def list_members(
        self,
        org_id: str,
        current_user: User = Depends(get_current_user)
    ) -> List[MemberResponse]:
        """List organization members"""
        try:
            # Validate org_id format
            try:
                org_uuid = UUID(org_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

            # Create query
            query = ListMembershipsQuery(
                organization_id=org_uuid,
                requester_id=current_user.id
            )

            # Execute query
            handler = ListMembershipsHandler(self.repository)
            result = await handler.handle(query)

            # Convert to response DTOs
            members = []
            for membership_with_user in result.memberships:
                user = membership_with_user.user
                membership = membership_with_user.membership

                members.append(MemberResponse(
                    user_id=str(user.id),
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    display_name=user.display_name,
                    profile_image_url=user.profile_image_url,
                    role=membership.role.value,
                    permissions=membership.permissions,
                    joined_at=membership.joined_at,
                    invited_by=str(membership.invited_by) if membership.invited_by else None
                ))

            return members

        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
        except ApplicationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message)

    async def delete_organization(
        self,
        org_id: str,
        current_user: User = Depends(get_current_user)
    ) -> SuccessResponse:
        """Delete an organization (owner only)"""
        try:
            # Validate org_id format
            try:
                org_uuid = UUID(org_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

            # Get organization
            organization = await self.repository.find_by_id(org_uuid)
            if not organization:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

            # Check if user is owner
            if not organization.can_be_deleted_by(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete organization")

            # Delete organization
            await self.repository.delete(org_uuid)
            self.db.commit()

            return SuccessResponse(message="Organization deleted successfully")

        except ApplicationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message)
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

    def _handle_application_error(self, error: Exception):
        """Handle application layer errors and convert to HTTP responses"""
        if isinstance(error, ValidationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error.message)
        elif isinstance(error, NotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.message)
        elif isinstance(error, PermissionError):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error.message)
        elif isinstance(error, ConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.message)
        elif isinstance(error, ApplicationError):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.message)
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")