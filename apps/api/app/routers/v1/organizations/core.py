"""
Core organization CRUD operations
Basic organization management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from datetime import datetime

from app.database import get_db
from app.models import User, Organization, organization_members
from app.routers.v1.auth import get_current_user
from .schemas import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationResponse,
    OrganizationDetailResponse,
    OrganizationListResponse,
    UserSummary
)
from .dependencies import (
    check_organization_admin_permission,
    check_organization_member_permission,
    validate_unique_slug
)

router = APIRouter()


@router.post("/", response_model=OrganizationResponse)
async def create_organization(
    request: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new organization"""
    # Validate unique slug
    await validate_unique_slug(db, request.slug)

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
            role="admin",
            permissions=[],
            joined_at=datetime.utcnow()
        )
    )

    await db.commit()
    await db.refresh(org)

    # Get member count
    count_result = await db.execute(
        select(func.count(organization_members.c.user_id)).where(
            organization_members.c.organization_id == org.id
        )
    )
    member_count = count_result.scalar()

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        billing_email=org.billing_email,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count,
        settings=org.settings or {}
    )


@router.get("/", response_model=OrganizationListResponse)
async def list_organizations(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's organizations"""
    # Calculate offset
    offset = (page - 1) * per_page

    # Get organizations where user is a member
    stmt = select(
        Organization,
        organization_members.c.role
    ).join(
        organization_members,
        Organization.id == organization_members.c.organization_id
    ).where(
        organization_members.c.user_id == current_user.id
    )

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    # Get paginated results
    result = await db.execute(stmt.offset(offset).limit(per_page))
    user_orgs = result.all()

    orgs_result = []
    for org, role in user_orgs:
        # Get member count
        count_result = await db.execute(
            select(func.count(organization_members.c.user_id)).where(
                organization_members.c.organization_id == org.id
            )
        )
        member_count = count_result.scalar()

        # Get owner email for display
        owner_email = None
        if org.owner_id:
            owner_result = await db.execute(select(User).where(User.id == org.owner_id))
            owner = owner_result.scalar_one_or_none()
            if owner:
                owner_email = owner.email

        orgs_result.append(OrganizationResponse(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            description=org.description,
            logo_url=org.logo_url,
            billing_email=org.billing_email,
            created_at=org.created_at,
            updated_at=org.updated_at,
            member_count=member_count,
            settings=org.settings or {},
            # Include plan (subscription_tier) and owner_email for UI
            plan=getattr(org, 'subscription_tier', None) or getattr(org, 'billing_plan', 'community'),
            owner_email=owner_email
        ))

    return OrganizationListResponse(
        organizations=orgs_result,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/{org_id}", response_model=OrganizationDetailResponse)
async def get_organization(
    org_id: str,
    organization: Organization = Depends(check_organization_member_permission),
    db: Session = Depends(get_db)
):
    """Get organization details"""
    # Get owner details
    owner_result = await db.execute(select(User).where(User.id == organization.owner_id))
    owner = owner_result.scalar_one_or_none()

    # Get member count
    count_result = await db.execute(
        select(func.count(organization_members.c.user_id)).where(
            organization_members.c.organization_id == organization.id
        )
    )
    member_count = count_result.scalar()

    return OrganizationDetailResponse(
        id=str(organization.id),
        name=organization.name,
        slug=organization.slug,
        description=organization.description,
        logo_url=organization.logo_url,
        billing_email=organization.billing_email,
        created_at=organization.created_at,
        updated_at=organization.updated_at,
        member_count=member_count,
        settings=organization.settings or {},
        owner=UserSummary(
            id=str(owner.id),
            email=owner.email,
            first_name=owner.first_name,
            last_name=owner.last_name,
            avatar_url=getattr(owner, 'avatar_url', None)
        ),
        subscription_status=getattr(organization, 'subscription_status', None),
        subscription_plan=getattr(organization, 'billing_plan', 'free')
    )


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    request: OrganizationUpdateRequest,
    organization: Organization = Depends(check_organization_admin_permission),
    db: Session = Depends(get_db)
):
    """Update organization details"""
    # Update fields
    if request.name is not None:
        organization.name = request.name

    if request.description is not None:
        organization.description = request.description

    if request.logo_url is not None:
        organization.logo_url = request.logo_url

    if request.billing_email is not None:
        organization.billing_email = request.billing_email

    if request.settings is not None:
        organization.settings = request.settings

    organization.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(organization)

    # Get member count
    count_result = await db.execute(
        select(func.count(organization_members.c.user_id)).where(
            organization_members.c.organization_id == organization.id
        )
    )
    member_count = count_result.scalar()

    return OrganizationResponse(
        id=str(organization.id),
        name=organization.name,
        slug=organization.slug,
        description=organization.description,
        logo_url=organization.logo_url,
        billing_email=organization.billing_email,
        created_at=organization.created_at,
        updated_at=organization.updated_at,
        member_count=member_count,
        settings=organization.settings or {}
    )


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    organization: Organization = Depends(check_organization_admin_permission),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete organization (owner only)"""
    # Only owner can delete
    if organization.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organization owner can delete the organization")

    # Check if organization has active subscriptions or billing
    # In a real implementation, you'd check for active subscriptions here

    # Delete organization (this will cascade to members via foreign key)
    db.delete(organization)
    await db.commit()

    return {"success": True, "message": "Organization deleted successfully"}


@router.get("/slug/{slug}", response_model=OrganizationResponse)
async def get_organization_by_slug(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization by slug (public information only)"""
    org_result = await db.execute(select(Organization).where(Organization.slug == slug))
    org = org_result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if user is a member to determine what information to return
    user_role = None
    member_result = await db.execute(select(organization_members).where(
        organization_members.c.organization_id == org.id,
        organization_members.c.user_id == current_user.id
    ))
    member = member_result.first()

    if member:
        user_role = member.role

    # Get member count
    count_result = await db.execute(
        select(func.count(organization_members.c.user_id)).where(
            organization_members.c.organization_id == org.id
        )
    )
    member_count = count_result.scalar()

    # Return basic information (more details if user is a member)
    settings = org.settings if user_role else {}

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        billing_email=org.billing_email if user_role else None,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count if user_role else None,
        settings=settings
    )