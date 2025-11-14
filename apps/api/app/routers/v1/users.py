"""
User management endpoints
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, select, func, update
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import uuid
import os
import hashlib

from app.database import get_db
from ...models import User, UserStatus, Organization, OrganizationMember, Session as UserSession
from app.routers.v1.auth import get_current_user
from app.services.auth import AuthService
from app.config import settings

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdateRequest(BaseModel):
    """User profile update request"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=1000)
    phone_number: Optional[str] = Field(None, max_length=20)
    timezone: Optional[str] = Field(None, max_length=50)
    locale: Optional[str] = Field(None, max_length=10)
    user_metadata: Optional[dict] = None


class UserResponse(BaseModel):
    """User response model"""
    id: str
    email: str
    email_verified: bool
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    profile_image_url: Optional[str]
    bio: Optional[str]
    phone_number: Optional[str]
    phone_verified: bool
    timezone: Optional[str]
    locale: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime]
    user_metadata: dict


class UsersListResponse(BaseModel):
    """Users list response"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        email_verified=current_user.email_verified,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        display_name=current_user.display_name,
        profile_image_url=current_user.profile_image_url,
        bio=current_user.bio,
        phone_number=current_user.phone_number,
        phone_verified=current_user.phone_verified,
        timezone=current_user.timezone,
        locale=current_user.locale,
        status=current_user.status.value,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_sign_in_at=current_user.last_sign_in_at,
        user_metadata=current_user.user_metadata or {}
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    # Update fields if provided
    if request.first_name is not None:
        current_user.first_name = request.first_name
    if request.last_name is not None:
        current_user.last_name = request.last_name
    if request.display_name is not None:
        current_user.display_name = request.display_name
    if request.bio is not None:
        current_user.bio = request.bio
    if request.phone_number is not None:
        current_user.phone_number = request.phone_number
    if request.timezone is not None:
        current_user.timezone = request.timezone
    if request.locale is not None:
        current_user.locale = request.locale
    if request.user_metadata is not None:
        current_user.user_metadata = request.user_metadata
    
    await db.commit()
    await db.refresh(current_user)
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        email_verified=current_user.email_verified,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        display_name=current_user.display_name,
        profile_image_url=current_user.profile_image_url,
        bio=current_user.bio,
        phone_number=current_user.phone_number,
        phone_verified=current_user.phone_verified,
        timezone=current_user.timezone,
        locale=current_user.locale,
        status=current_user.status.value,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_sign_in_at=current_user.last_sign_in_at,
        user_metadata=current_user.user_metadata or {}
    )


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload user avatar"""
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    # Generate unique filename
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{current_user.id}_{hashlib.md5(contents).hexdigest()}.{file_extension}"
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    file_path = os.path.join(upload_dir, unique_filename)
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Update user profile
    avatar_url = f"/uploads/avatars/{unique_filename}"
    current_user.profile_image_url = avatar_url
    await db.commit()
    
    return {"profile_image_url": avatar_url}


@router.delete("/me/avatar")
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user avatar"""
    if current_user.profile_image_url:
        # Delete file if it's a local upload
        if current_user.profile_image_url.startswith("/uploads/"):
            file_path = os.path.join(
                settings.UPLOAD_DIR,
                current_user.profile_image_url.replace("/uploads/", "")
            )
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Clear avatar URL
        current_user.profile_image_url = None
        await db.commit()
    
    return {"message": "Avatar deleted successfully"}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user by ID (admin only or same organization)"""
    # Parse UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # Get user
    result = await db.execute(select(User).where(
        User.id == user_uuid,
        User.status == UserStatus.ACTIVE
    ))

    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions (admin or same organization)
    if not current_user.is_admin:
        # Check if users share an organization
        user_orgs = select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == user.id
        ).subquery()

        shared_result = await db.execute(select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id.in_(user_orgs)
        ))
        shared_org = shared_result.scalar_one_or_none()
        
        if not shared_org:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        email_verified=user.email_verified,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        profile_image_url=user.profile_image_url,
        bio=user.bio,
        phone_number=user.phone_number,
        phone_verified=user.phone_verified,
        timezone=user.timezone,
        locale=user.locale,
        status=user.status.value,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_sign_in_at=user.last_sign_in_at,
        user_metadata=user.user_metadata or {}
    )


@router.get("/", response_model=UsersListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users (admin only or same organization)"""
    stmt = select(User)
    
    # Filter by organization if not admin
    if not current_user.is_admin:
        # Get current user's organizations
        user_orgs = select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == current_user.id
        ).subquery()

        # Get users in same organizations
        org_users = select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id.in_(user_orgs)
        ).subquery()

        stmt = stmt.where(User.id.in_(org_users))
    
    # Apply filters
    if search:
        stmt = stmt.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    
    if status:
        try:
            status_enum = UserStatus(status)
            stmt = stmt.where(User.status == status_enum)
        except ValueError:
            pass
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result_set = await db.execute(stmt)
    users = result_set.scalars().all()
    
    # Convert to response
    users_response = []
    for user in users:
        users_response.append(UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            profile_image_url=user.profile_image_url,
            bio=user.bio,
            phone_number=user.phone_number,
            phone_verified=user.phone_verified,
            timezone=user.timezone,
            locale=user.locale,
            status=user.status.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
            user_metadata=user.user_metadata or {}
        ))
    
    return UsersListResponse(
        users=users_response,
        total=total,
        page=page,
        per_page=per_page
    )


@router.delete("/me")
async def delete_current_user(
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete current user account"""
    # Verify password
    if not AuthService.verify_password(password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")
    
    # Check if user is the only owner of any organizations
    owned_result = await db.execute(select(Organization).where(
        Organization.owner_id == current_user.id
    ))
    owned_orgs = owned_result.scalars().all()

    for org in owned_orgs:
        # Check if there are other admins
        admins_result = await db.execute(
            select(func.count()).select_from(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.role == "admin",
                OrganizationMember.user_id != current_user.id
            )
        )
        other_admins = admins_result.scalar()
        
        if other_admins == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete account: you are the only admin of organization '{org.name}'"
            )
    
    # Soft delete user
    current_user.status = UserStatus.DELETED
    current_user.email = f"deleted_{current_user.id}_{current_user.email}"
    current_user.username = None if current_user.username else None
    
    # Revoke all sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id)
        .values(revoked=True)
    )
    
    await db.commit()
    
    return {"message": "Account deleted successfully"}


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Suspend a user (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Parse UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # Get user
    result = await db.execute(select(User).where(User.id == user_uuid))

    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Suspend user
    user.status = UserStatus.SUSPENDED
    
    # Revoke all sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id)
        .values(revoked=True)
    )
    
    # Log the action
    if reason:
        user.user_metadata = user.user_metadata or {}
        user.user_metadata["suspension_reason"] = reason
        user.user_metadata["suspended_at"] = datetime.utcnow().isoformat()
        user.user_metadata["suspended_by"] = str(current_user.id)
    
    await db.commit()
    
    return {"message": "User suspended successfully"}


@router.post("/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reactivate a suspended user (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Parse UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # Get user
    result = await db.execute(select(User).where(User.id == user_uuid))

    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.status != UserStatus.SUSPENDED:
        raise HTTPException(status_code=400, detail="User is not suspended")
    
    # Reactivate user
    user.status = UserStatus.ACTIVE
    
    # Clear suspension metadata
    if user.user_metadata:
        user.user_metadata.pop("suspension_reason", None)
        user.user_metadata.pop("suspended_at", None)
        user.user_metadata.pop("suspended_by", None)
        user.user_metadata["reactivated_at"] = datetime.utcnow().isoformat()
        user.user_metadata["reactivated_by"] = str(current_user.id)
    
    await db.commit()
    
    return {"message": "User reactivated successfully"}