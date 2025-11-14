"""
Organization management endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, select
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
import uuid
import secrets
import string

from app.database import get_db
from ...models import (
    User, Organization, OrganizationMember, OrganizationInvitation,
    OrganizationCustomRole, OrganizationRole, organization_members
)
from app.routers.v1.auth import get_current_user
from app.services.email import EmailService
from app.config import settings

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreateRequest(BaseModel):
    """Organization creation request"""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: Optional[str] = Field(None, max_length=1000)
    billing_email: Optional[str] = None
    
    @validator('slug')
    def validate_slug(cls, v):
        """Ensure slug is lowercase and valid"""
        return v.lower()


class OrganizationUpdateRequest(BaseModel):
    """Organization update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    logo_url: Optional[str] = Field(None, max_length=500)
    billing_email: Optional[str] = None
    settings: Optional[dict] = None


class OrganizationResponse(BaseModel):
    """Organization response model"""
    id: str
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    owner_id: str
    settings: dict
    org_metadata: dict
    billing_email: Optional[str]
    billing_plan: str
    created_at: datetime
    updated_at: datetime
    member_count: int
    is_owner: bool
    user_role: Optional[str]


class OrganizationMemberResponse(BaseModel):
    """Organization member response"""
    user_id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    profile_image_url: Optional[str]
    role: str
    permissions: List[str]
    joined_at: datetime
    invited_by: Optional[str]


class OrganizationInviteRequest(BaseModel):
    """Organization invitation request"""
    email: str
    role: OrganizationRole = OrganizationRole.MEMBER
    permissions: Optional[List[str]] = Field(default_factory=list)
    message: Optional[str] = None


class OrganizationInvitationResponse(BaseModel):
    """Organization invitation response"""
    id: str
    organization_id: str
    organization_name: str
    email: str
    role: str
    permissions: List[str]
    invited_by: str
    inviter_name: Optional[str]
    status: str
    created_at: datetime
    expires_at: datetime


class RoleCreateRequest(BaseModel):
    """Custom role creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    """Role response model"""
    id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime


async def get_user_organization_role(db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> Optional[OrganizationRole]:
    """Get user's role in an organization"""
    result = await db.execute(select(organization_members).where(
        and_(
            organization_members.c.user_id == user_id,
            organization_members.c.organization_id == org_id
        )
    ))
    member = result.first()
    
    return member.role if member else None


async def check_organization_permission(
    db: Session,
    user: User,
    org_id: uuid.UUID,
    required_role: OrganizationRole = OrganizationRole.MEMBER
) -> Organization:
    """Check if user has required permission in organization"""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Owner always has access
    if org.owner_id == user.id:
        return org
    
    # Check membership and role
    user_role = await get_user_organization_role(db, user.id, org_id)
    if not user_role:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    
    # Role hierarchy: OWNER > ADMIN > MEMBER > VIEWER
    role_hierarchy = {
        OrganizationRole.VIEWER: 0,
        OrganizationRole.MEMBER: 1,
        OrganizationRole.ADMIN: 2,
        OrganizationRole.OWNER: 3
    }
    
    if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return org


@router.post("/", response_model=OrganizationResponse)
async def create_organization(
    request: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new organization"""
    # Check if slug is already taken
    result = await db.execute(select(Organization).where(
        Organization.slug == request.slug
    ))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already exists")
    
    # Create organization
    org = Organization(
        name=request.name,
        slug=request.slug,
        description=request.description,
        owner_id=current_user.id,
        billing_email=request.billing_email or current_user.email,
        billing_plan="free",
        settings={},
        org_metadata={}
    )
    
    db.add(org)
    db.flush()
    
    # Add owner as admin member
    db.execute(
        organization_members.insert().values(
            organization_id=org.id,
            user_id=current_user.id,
            role=OrganizationRole.ADMIN,
            permissions=[],
            joined_at=datetime.utcnow()
        )
    )
    
    await db.commit()
    await db.refresh(org)
    
    # Get member count
    result = await db.execute(select(func.count(organization_members.c.user_id)).where(
        organization_members.c.organization_id == org.id
    ))
    member_count = result.scalar()
    
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        owner_id=str(org.owner_id),
        settings=org.settings or {},
        org_metadata=org.org_metadata or {},
        billing_email=org.billing_email,
        billing_plan=org.billing_plan,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count,
        is_owner=True,
        user_role="admin"
    )


@router.get("/", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's organizations"""
    # Get organizations where user is a member
    result_set = await db.execute(
        select(
            Organization,
            organization_members.c.role
        ).join(
            organization_members,
            Organization.id == organization_members.c.organization_id
        ).where(
            organization_members.c.user_id == current_user.id
        )
    )
    user_orgs = result_set.all()
    
    result = []
    for org, role in user_orgs:
        count_result = await db.execute(select(func.count(organization_members.c.user_id)).where(
            organization_members.c.organization_id == org.id
        ))
        member_count = count_result.scalar()
        
        result.append(OrganizationResponse(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            description=org.description,
            logo_url=org.logo_url,
            owner_id=str(org.owner_id),
            settings=org.settings or {},
            org_metadata=org.org_metadata or {},
            billing_email=org.billing_email,
            billing_plan=org.billing_plan,
            created_at=org.created_at,
            updated_at=org.updated_at,
            member_count=member_count,
            is_owner=org.owner_id == current_user.id,
            user_role=role.value if role else None
        ))
    
    return result


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization details"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid)
    
    count_result = await db.execute(select(func.count(organization_members.c.user_id)).where(
        organization_members.c.organization_id == org.id
    ))
    member_count = count_result.scalar()
    
    user_role = await get_user_organization_role(db, current_user.id, org_uuid)
    
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        owner_id=str(org.owner_id),
        settings=org.settings or {},
        org_metadata=org.org_metadata or {},
        billing_email=org.billing_email,
        billing_plan=org.billing_plan,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count,
        is_owner=org.owner_id == current_user.id,
        user_role=user_role.value if user_role else None
    )


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    request: OrganizationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update organization details"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)
    
    # Update fields
    if request.name is not None:
        org.name = request.name
    if request.description is not None:
        org.description = request.description
    if request.logo_url is not None:
        org.logo_url = request.logo_url
    if request.billing_email is not None:
        org.billing_email = request.billing_email
    if request.settings is not None:
        org.settings = request.settings
    
    await db.commit()
    await db.refresh(org)
    
    count_result = await db.execute(select(func.count(organization_members.c.user_id)).where(
        organization_members.c.organization_id == org.id
    ))
    member_count = count_result.scalar()
    
    user_role = await get_user_organization_role(db, current_user.id, org_uuid)
    
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        owner_id=str(org.owner_id),
        settings=org.settings or {},
        org_metadata=org.org_metadata or {},
        billing_email=org.billing_email,
        billing_plan=org.billing_plan,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count,
        is_owner=org.owner_id == current_user.id,
        user_role=user_role.value if user_role else None
    )


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an organization (owner only)"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Only owner can delete
    if org.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete organization")
    
    # Delete organization (cascade will handle related records)
    db.delete(org)
    await db.commit()
    
    return {"message": "Organization deleted successfully"}


@router.get("/{org_id}/members", response_model=List[OrganizationMemberResponse])
async def list_organization_members(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organization members"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid)
    
    # Get members with their roles
    result_set = await db.execute(
        select(
            User,
            organization_members.c.role,
            organization_members.c.permissions,
            organization_members.c.joined_at,
            organization_members.c.invited_by
        ).join(
            organization_members,
            User.id == organization_members.c.user_id
        ).where(
            organization_members.c.organization_id == org_uuid
        )
    )
    members = result_set.all()
    
    result = []
    for user, role, permissions, joined_at, invited_by in members:
        result.append(OrganizationMemberResponse(
            user_id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            profile_image_url=user.profile_image_url,
            role=role.value,
            permissions=permissions or [],
            joined_at=joined_at,
            invited_by=str(invited_by) if invited_by else None
        ))
    
    return result


@router.put("/{org_id}/members/{user_id}/role")
async def update_member_role(
    org_id: str,
    user_id: str,
    role: OrganizationRole,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update member role"""
    try:
        org_uuid = uuid.UUID(org_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)
    
    # Can't change owner's role
    if org.owner_id == user_uuid:
        raise HTTPException(status_code=400, detail="Cannot change owner's role")
    
    # Update role
    db.execute(
        organization_members.update().where(
            and_(
                organization_members.c.organization_id == org_uuid,
                organization_members.c.user_id == user_uuid
            )
        ).values(role=role)
    )
    
    await db.commit()
    
    return {"message": "Role updated successfully"}


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove member from organization"""
    try:
        org_uuid = uuid.UUID(org_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)
    
    # Can't remove owner
    if org.owner_id == user_uuid:
        raise HTTPException(status_code=400, detail="Cannot remove organization owner")
    
    # Remove member
    db.execute(
        organization_members.delete().where(
            and_(
                organization_members.c.organization_id == org_uuid,
                organization_members.c.user_id == user_uuid
            )
        )
    )
    
    await db.commit()
    
    return {"message": "Member removed successfully"}


@router.post("/{org_id}/invite")
async def invite_member(
    org_id: str,
    request: OrganizationInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invite a new member to organization"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)
    
    # Check if user already member
    user_result = await db.execute(select(User).where(User.email == request.email))
    existing_user = user_result.scalar_one_or_none()
    if existing_user:
        member_result = await db.execute(select(organization_members).where(
            and_(
                organization_members.c.organization_id == org_uuid,
                organization_members.c.user_id == existing_user.id
            )
        ))
        existing_member = member_result.first()
        
        if existing_member:
            raise HTTPException(status_code=400, detail="User is already a member")
    
    # Check for pending invitation
    pending_result = await db.execute(select(OrganizationInvitation).where(
        and_(
            OrganizationInvitation.organization_id == org_uuid,
            OrganizationInvitation.email == request.email,
            OrganizationInvitation.status == "pending",
            OrganizationInvitation.expires_at > datetime.utcnow()
        )
    ))
    pending = pending_result.scalar_one_or_none()
    
    if pending:
        raise HTTPException(status_code=400, detail="Invitation already sent")
    
    # Generate invitation token
    token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # Create invitation
    invitation = OrganizationInvitation(
        organization_id=org_uuid,
        email=request.email,
        role=request.role,
        permissions=request.permissions or [],
        token=token,
        invited_by=current_user.id,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    
    db.add(invitation)
    await db.commit()
    
    # Send invitation email
    # TODO: Implement email sending
    # EmailService.send_invitation(request.email, org.name, token)
    
    return {
        "message": "Invitation sent successfully",
        "invitation_id": str(invitation.id),
        "expires_at": invitation.expires_at
    }


@router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept an organization invitation"""
    # Find invitation
    invitation_result = await db.execute(select(OrganizationInvitation).where(
        and_(
            OrganizationInvitation.token == token,
            OrganizationInvitation.status == "pending"
        )
    ))
    invitation = invitation_result.scalar_one_or_none()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid or expired invitation")
    
    # Check expiration
    if invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Invitation has expired")
    
    # Check email match
    if invitation.email != current_user.email:
        raise HTTPException(status_code=403, detail="Invitation is for a different email")
    
    # Check if already member
    member_check_result = await db.execute(select(organization_members).where(
        and_(
            organization_members.c.organization_id == invitation.organization_id,
            organization_members.c.user_id == current_user.id
        )
    ))
    existing = member_check_result.first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already a member of this organization")
    
    # Add user to organization
    db.execute(
        organization_members.insert().values(
            organization_id=invitation.organization_id,
            user_id=current_user.id,
            role=invitation.role,
            permissions=invitation.permissions,
            joined_at=datetime.utcnow(),
            invited_by=invitation.invited_by
        )
    )
    
    # Update invitation status
    invitation.status = "accepted"
    invitation.accepted_at = datetime.utcnow()
    
    await db.commit()
    
    # Get organization details
    org_result = await db.execute(select(Organization).where(
        Organization.id == invitation.organization_id
    ))
    org = org_result.scalar_one_or_none()
    
    return {
        "message": "Successfully joined organization",
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug
        }
    }


@router.get("/{org_id}/invitations", response_model=List[OrganizationInvitationResponse])
async def list_invitations(
    org_id: str,
    status: Optional[str] = Query(None, pattern="^(pending|accepted|expired)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organization invitations"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)
    
    # Build query
    stmt = select(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == org_uuid
    )
    
    if status:
        stmt = stmt.where(OrganizationInvitation.status == status)
    
    stmt = stmt.order_by(OrganizationInvitation.created_at.desc())
    
    invitations_result = await db.execute(stmt)
    invitations = invitations_result.scalars().all()
    
    result = []
    for inv in invitations:
        # Get inviter details
        inviter_result = await db.execute(select(User).where(User.id == inv.invited_by))
        inviter = inviter_result.scalar_one_or_none()
        
        result.append(OrganizationInvitationResponse(
            id=str(inv.id),
            organization_id=str(inv.organization_id),
            organization_name=org.name,
            email=inv.email,
            role=inv.role.value,
            permissions=inv.permissions or [],
            invited_by=str(inv.invited_by),
            inviter_name=inviter.display_name or f"{inviter.first_name} {inviter.last_name}" if inviter else None,
            status=inv.status,
            created_at=inv.created_at,
            expires_at=inv.expires_at
        ))
    
    return result


@router.delete("/{org_id}/invitations/{invitation_id}")
async def revoke_invitation(
    org_id: str,
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an invitation"""
    try:
        org_uuid = uuid.UUID(org_id)
        inv_uuid = uuid.UUID(invitation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)

    invitation_result = await db.execute(select(OrganizationInvitation).where(
        and_(
            OrganizationInvitation.id == inv_uuid,
            OrganizationInvitation.organization_id == org_uuid
        )
    ))
    invitation = invitation_result.scalar_one_or_none()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Can only revoke pending invitations")
    
    db.delete(invitation)
    await db.commit()
    
    return {"message": "Invitation revoked successfully"}


@router.post("/{org_id}/roles", response_model=RoleResponse)
async def create_custom_role(
    org_id: str,
    request: RoleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a custom role for organization"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)

    # Check if role name already exists
    existing_result = await db.execute(select(OrganizationCustomRole).where(
        and_(
            OrganizationCustomRole.organization_id == org_uuid,
            OrganizationCustomRole.name == request.name
        )
    ))
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")
    
    # Create role
    role = OrganizationCustomRole(
        organization_id=org_uuid,
        name=request.name,
        description=request.description,
        permissions=request.permissions,
        is_system=False
    )
    
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=role.permissions or [],
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at
    )


@router.get("/{org_id}/roles", response_model=List[RoleResponse])
async def list_custom_roles(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organization's custom roles"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")
    
    org = await check_organization_permission(db, current_user, org_uuid)

    roles_result = await db.execute(select(OrganizationCustomRole).where(
        OrganizationCustomRole.organization_id == org_uuid
    ))
    roles = roles_result.scalars().all()
    
    # Add built-in roles
    result = [
        RoleResponse(
            id="built-in-owner",
            name="Owner",
            description="Full control over organization",
            permissions=["*"],
            is_system=True,
            created_at=org.created_at,
            updated_at=org.updated_at
        ),
        RoleResponse(
            id="built-in-admin",
            name="Admin",
            description="Administrative access",
            permissions=["manage_members", "manage_settings", "manage_billing"],
            is_system=True,
            created_at=org.created_at,
            updated_at=org.updated_at
        ),
        RoleResponse(
            id="built-in-member",
            name="Member",
            description="Regular member access",
            permissions=["read", "write"],
            is_system=True,
            created_at=org.created_at,
            updated_at=org.updated_at
        ),
        RoleResponse(
            id="built-in-viewer",
            name="Viewer",
            description="Read-only access",
            permissions=["read"],
            is_system=True,
            created_at=org.created_at,
            updated_at=org.updated_at
        )
    ]
    
    # Add custom roles
    for role in roles:
        result.append(RoleResponse(
            id=str(role.id),
            name=role.name,
            description=role.description,
            permissions=role.permissions or [],
            is_system=role.is_system,
            created_at=role.created_at,
            updated_at=role.updated_at
        ))
    
    return result


@router.delete("/{org_id}/roles/{role_id}")
async def delete_custom_role(
    org_id: str,
    role_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a custom role"""
    try:
        org_uuid = uuid.UUID(org_id)
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    org = await check_organization_permission(db, current_user, org_uuid, OrganizationRole.ADMIN)

    role_result = await db.execute(select(OrganizationCustomRole).where(
        and_(
            OrganizationCustomRole.id == role_uuid,
            OrganizationCustomRole.organization_id == org_uuid
        )
    ))
    role = role_result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")
    
    # TODO: Check if role is in use by any members
    
    db.delete(role)
    await db.commit()
    
    return {"message": "Role deleted successfully"}


@router.post("/{org_id}/transfer-ownership")
async def transfer_ownership(
    org_id: str,
    new_owner_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Transfer organization ownership"""
    try:
        org_uuid = uuid.UUID(org_id)
        new_owner_uuid = uuid.UUID(new_owner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")

    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Only current owner can transfer
    if org.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can transfer ownership")
    
    # Check new owner is a member
    member_result = await db.execute(select(organization_members).where(
        and_(
            organization_members.c.organization_id == org_uuid,
            organization_members.c.user_id == new_owner_uuid
        )
    ))
    new_owner_member = member_result.first()
    
    if not new_owner_member:
        raise HTTPException(status_code=400, detail="New owner must be a member of the organization")
    
    # Update ownership
    org.owner_id = new_owner_uuid
    
    # Update roles
    db.execute(
        organization_members.update().where(
            and_(
                organization_members.c.organization_id == org_uuid,
                organization_members.c.user_id == new_owner_uuid
            )
        ).values(role=OrganizationRole.ADMIN)
    )
    
    await db.commit()
    
    return {"message": "Ownership transferred successfully"}