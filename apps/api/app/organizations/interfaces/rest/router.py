"""
Organization router using the new layered architecture
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.v1.auth import get_current_user

from .organization_controller import OrganizationController
from .dto.requests import CreateOrganizationRequest, InviteMemberRequest
from .dto.responses import (
    OrganizationResponse,
    MemberResponse,
    InviteResultResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new organization"""
    controller = OrganizationController(db)
    return await controller.create_organization(request, current_user)


@router.get("/", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List user's organizations"""
    controller = OrganizationController(db)
    return await controller.list_organizations(current_user)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get organization details"""
    controller = OrganizationController(db)
    return await controller.get_organization(org_id, current_user)


@router.delete("/{org_id}", response_model=SuccessResponse)
async def delete_organization(
    org_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete an organization (owner only)"""
    controller = OrganizationController(db)
    return await controller.delete_organization(org_id, current_user)


@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def list_organization_members(
    org_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List organization members"""
    controller = OrganizationController(db)
    return await controller.list_members(org_id, current_user)


@router.post("/{org_id}/invite", response_model=InviteResultResponse, status_code=201)
async def invite_member(
    org_id: str,
    request: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invite a new member to organization"""
    controller = OrganizationController(db)
    return await controller.invite_member(org_id, request, current_user)
