"""
Organization settings management endpoints
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrganizationSettings, User
from app.routers.v1.auth import get_current_user

from .dependencies import check_organization_admin_permission, check_organization_member_permission

router = APIRouter()


class OrganizationSettingsResponse(BaseModel):
    """Organization settings response model"""

    id: str
    organization_id: str
    settings_data: dict
    created_at: datetime
    updated_at: datetime


class OrganizationSettingsUpdateRequest(BaseModel):
    """Update organization settings request"""

    settings_data: dict = Field(default_factory=dict)


@router.get("/{org_id}/settings", response_model=OrganizationSettingsResponse)
async def get_organization_settings(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get organization settings"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    await check_organization_member_permission(db, current_user, org_uuid)

    # Get or create settings
    result = await db.execute(
        select(OrganizationSettings).where(OrganizationSettings.organization_id == org_uuid)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings
        settings = OrganizationSettings(
            organization_id=org_uuid,
            settings_data={},
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return OrganizationSettingsResponse(
        id=str(settings.id),
        organization_id=str(settings.organization_id),
        settings_data=settings.settings_data or {},
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.put("/{org_id}/settings", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    org_id: str,
    request: OrganizationSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update organization settings"""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    await check_organization_admin_permission(db, current_user, org_uuid)

    # Get or create settings
    result = await db.execute(
        select(OrganizationSettings).where(OrganizationSettings.organization_id == org_uuid)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create new settings
        settings = OrganizationSettings(
            organization_id=org_uuid,
            settings_data=request.settings_data,
        )
        db.add(settings)
    else:
        # Update existing settings (merge with existing)
        current_settings = settings.settings_data or {}
        current_settings.update(request.settings_data)
        settings.settings_data = current_settings

    await db.commit()
    await db.refresh(settings)

    return OrganizationSettingsResponse(
        id=str(settings.id),
        organization_id=str(settings.organization_id),
        settings_data=settings.settings_data or {},
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )
