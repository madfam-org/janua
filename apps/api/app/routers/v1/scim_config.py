"""
SCIM Configuration Management API

Administrative endpoints for managing SCIM provisioning configuration per organization.
Separate from the SCIM 2.0 protocol endpoints in scim.py which handle IdP requests.
"""

import secrets
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_org_admin
from app.models import User, Organization
from app.models.enterprise import (
    SCIMConfiguration,
    SCIMResource,
    SCIMSyncLog,
    SCIMProvider,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organizations/{org_id}/scim",
    tags=["SCIM Configuration"],
    responses={404: {"description": "Not found"}},
)


# ========================================
# Pydantic Models
# ========================================


class SCIMConfigCreate(BaseModel):
    """Create SCIM configuration request"""

    provider: SCIMProvider = SCIMProvider.CUSTOM
    enabled: bool = False
    base_url: Optional[str] = Field(
        None, description="Base URL for SCIM endpoint (auto-generated if not provided)"
    )
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration (e.g., attribute mappings)",
    )


class SCIMConfigUpdate(BaseModel):
    """Update SCIM configuration request"""

    provider: Optional[SCIMProvider] = None
    enabled: Optional[bool] = None
    configuration: Optional[Dict[str, Any]] = None


class SCIMConfigResponse(BaseModel):
    """SCIM configuration response"""

    id: str
    organization_id: str
    provider: SCIMProvider
    enabled: bool
    base_url: str
    bearer_token_prefix: Optional[str] = Field(
        None, description="First 8 chars of bearer token for identification"
    )
    configuration: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SCIMTokenResponse(BaseModel):
    """SCIM bearer token response (only shown once on creation/rotation)"""

    bearer_token: str
    message: str = "Store this token securely. It will not be shown again."


class SCIMSyncStatusResponse(BaseModel):
    """SCIM sync status overview"""

    enabled: bool
    provider: Optional[SCIMProvider] = None
    total_users: int = 0
    total_groups: int = 0
    synced_users: int = 0
    synced_groups: int = 0
    pending_users: int = 0
    pending_groups: int = 0
    error_users: int = 0
    error_groups: int = 0
    last_sync_at: Optional[datetime] = None
    recent_operations: List[Dict[str, Any]] = Field(default_factory=list)


class SCIMSyncLogEntry(BaseModel):
    """SCIM sync log entry"""

    id: str
    operation: str
    resource_type: str
    scim_id: Optional[str] = None
    internal_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    synced_at: datetime


# ========================================
# Helper Functions
# ========================================


def generate_scim_token() -> str:
    """Generate a secure SCIM bearer token"""
    return f"scim_{secrets.token_urlsafe(48)}"


async def get_org_scim_config(
    org_id: UUID, db: AsyncSession
) -> Optional[SCIMConfiguration]:
    """Get SCIM configuration for an organization"""
    result = await db.execute(
        select(SCIMConfiguration).where(SCIMConfiguration.organization_id == org_id)
    )
    return result.scalar_one_or_none()


async def verify_org_access(
    org_id: UUID, user: User, db: AsyncSession
) -> Organization:
    """Verify user has admin access to organization for SCIM configuration"""
    from app.models import organization_members

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    # Super admin always has access
    if user.is_admin:
        return org

    # Organization owner always has access
    if org.owner_id == user.id:
        return org

    # Check if user is an admin member of the organization
    member_result = await db.execute(
        select(organization_members).where(
            and_(
                organization_members.c.user_id == user.id,
                organization_members.c.organization_id == org_id
            )
        )
    )
    member = member_result.first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )

    # SCIM configuration requires admin role
    if member.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to manage SCIM configuration"
        )

    return org


# ========================================
# Configuration Endpoints
# ========================================


@router.post("/config", response_model=SCIMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_scim_config(
    org_id: UUID,
    config: SCIMConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create SCIM configuration for an organization.

    Generates a bearer token for IdP authentication.
    The token is only returned once - store it securely.
    """
    await verify_org_access(org_id, current_user, db)

    # Check if config already exists
    existing = await get_org_scim_config(org_id, db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SCIM configuration already exists for this organization. Use PUT to update.",
        )

    # Generate bearer token
    bearer_token = generate_scim_token()

    # Auto-generate base_url if not provided
    from app.config import settings
    base_url = config.base_url or f"{settings.BASE_URL}/scim/v2"

    scim_config = SCIMConfiguration(
        organization_id=org_id,
        provider=config.provider.value if config.provider else SCIMProvider.CUSTOM.value,
        enabled=config.enabled,
        base_url=base_url,
        bearer_token=bearer_token,
        configuration=config.configuration,
    )

    db.add(scim_config)
    await db.commit()
    await db.refresh(scim_config)

    logger.info(f"Created SCIM config for org {org_id}")

    return SCIMConfigResponse(
        id=str(scim_config.id),
        organization_id=str(scim_config.organization_id),
        provider=SCIMProvider(scim_config.provider) if scim_config.provider else SCIMProvider.CUSTOM,
        enabled=scim_config.enabled,
        base_url=scim_config.base_url,
        bearer_token_prefix=bearer_token[:12] + "...",
        configuration=scim_config.configuration or {},
        created_at=scim_config.created_at,
        updated_at=scim_config.updated_at,
    )


@router.get("/config", response_model=SCIMConfigResponse)
async def get_scim_config(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get SCIM configuration for an organization.

    Note: The bearer token is not returned. Use POST /config/token to rotate.
    """
    await verify_org_access(org_id, current_user, db)

    scim_config = await get_org_scim_config(org_id, db)
    if not scim_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SCIM configuration not found for this organization",
        )

    token_prefix = None
    if scim_config.bearer_token:
        token_prefix = scim_config.bearer_token[:12] + "..."

    return SCIMConfigResponse(
        id=str(scim_config.id),
        organization_id=str(scim_config.organization_id),
        provider=SCIMProvider(scim_config.provider) if scim_config.provider else SCIMProvider.CUSTOM,
        enabled=scim_config.enabled,
        base_url=scim_config.base_url or "",
        bearer_token_prefix=token_prefix,
        configuration=scim_config.configuration or {},
        created_at=scim_config.created_at,
        updated_at=scim_config.updated_at,
    )


@router.put("/config", response_model=SCIMConfigResponse)
async def update_scim_config(
    org_id: UUID,
    config: SCIMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update SCIM configuration for an organization.

    Note: This does not rotate the bearer token. Use POST /config/token for that.
    """
    await verify_org_access(org_id, current_user, db)

    scim_config = await get_org_scim_config(org_id, db)
    if not scim_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SCIM configuration not found for this organization",
        )

    # Update fields
    if config.provider is not None:
        scim_config.provider = config.provider.value
    if config.enabled is not None:
        scim_config.enabled = config.enabled
    if config.configuration is not None:
        scim_config.configuration = config.configuration

    scim_config.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(scim_config)

    logger.info(f"Updated SCIM config for org {org_id}")

    token_prefix = None
    if scim_config.bearer_token:
        token_prefix = scim_config.bearer_token[:12] + "..."

    return SCIMConfigResponse(
        id=str(scim_config.id),
        organization_id=str(scim_config.organization_id),
        provider=SCIMProvider(scim_config.provider) if scim_config.provider else SCIMProvider.CUSTOM,
        enabled=scim_config.enabled,
        base_url=scim_config.base_url or "",
        bearer_token_prefix=token_prefix,
        configuration=scim_config.configuration or {},
        created_at=scim_config.created_at,
        updated_at=scim_config.updated_at,
    )


@router.delete("/config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scim_config(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete SCIM configuration for an organization.

    Warning: This will invalidate any configured IdP integrations.
    SCIM resources and sync logs are preserved for audit purposes.
    """
    await verify_org_access(org_id, current_user, db)

    scim_config = await get_org_scim_config(org_id, db)
    if not scim_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SCIM configuration not found for this organization",
        )

    await db.delete(scim_config)
    await db.commit()

    logger.info(f"Deleted SCIM config for org {org_id}")


@router.post("/config/token", response_model=SCIMTokenResponse)
async def rotate_scim_token(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rotate the SCIM bearer token.

    Warning: This invalidates the previous token immediately.
    Update your IdP configuration with the new token.
    """
    await verify_org_access(org_id, current_user, db)

    scim_config = await get_org_scim_config(org_id, db)
    if not scim_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SCIM configuration not found for this organization",
        )

    # Generate new token
    new_token = generate_scim_token()
    scim_config.bearer_token = new_token
    scim_config.updated_at = datetime.utcnow()

    await db.commit()

    logger.info(f"Rotated SCIM token for org {org_id}")

    return SCIMTokenResponse(
        bearer_token=new_token,
        message="Store this token securely. It will not be shown again. Update your IdP configuration.",
    )


# ========================================
# Status & Monitoring Endpoints
# ========================================


@router.get("/status", response_model=SCIMSyncStatusResponse)
async def get_scim_sync_status(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get SCIM sync status and statistics for an organization.

    Shows overview of synced resources and recent operations.
    """
    await verify_org_access(org_id, current_user, db)

    scim_config = await get_org_scim_config(org_id, db)
    if not scim_config:
        return SCIMSyncStatusResponse(enabled=False)

    # Get resource counts by type and status
    resource_stats = await db.execute(
        select(
            SCIMResource.resource_type,
            SCIMResource.sync_status,
            func.count(SCIMResource.id).label("count"),
        )
        .where(SCIMResource.organization_id == org_id)
        .group_by(SCIMResource.resource_type, SCIMResource.sync_status)
    )

    stats = {
        "total_users": 0,
        "total_groups": 0,
        "synced_users": 0,
        "synced_groups": 0,
        "pending_users": 0,
        "pending_groups": 0,
        "error_users": 0,
        "error_groups": 0,
    }

    for row in resource_stats.fetchall():
        resource_type, sync_status, count = row
        type_key = "users" if resource_type == "User" else "groups"
        stats[f"total_{type_key}"] += count

        if sync_status == "synced":
            stats[f"synced_{type_key}"] += count
        elif sync_status == "pending":
            stats[f"pending_{type_key}"] += count
        elif sync_status == "error":
            stats[f"error_{type_key}"] += count

    # Get last sync time
    last_sync = await db.execute(
        select(SCIMResource.last_synced_at)
        .where(
            and_(
                SCIMResource.organization_id == org_id,
                SCIMResource.last_synced_at.isnot(None),
            )
        )
        .order_by(SCIMResource.last_synced_at.desc())
        .limit(1)
    )
    last_sync_at = last_sync.scalar_one_or_none()

    # Get recent operations (last 10)
    recent_ops = await db.execute(
        select(SCIMSyncLog)
        .where(SCIMSyncLog.organization_id == org_id)
        .order_by(SCIMSyncLog.synced_at.desc())
        .limit(10)
    )

    recent_operations = []
    for log in recent_ops.scalars():
        recent_operations.append(
            {
                "id": str(log.id),
                "operation": log.operation,
                "resource_type": log.resource_type,
                "status": log.status,
                "synced_at": log.synced_at.isoformat() if log.synced_at else None,
                "error_message": log.error_message,
            }
        )

    return SCIMSyncStatusResponse(
        enabled=scim_config.enabled,
        provider=SCIMProvider(scim_config.provider) if scim_config.provider else None,
        last_sync_at=last_sync_at,
        recent_operations=recent_operations,
        **stats,
    )


@router.get("/logs", response_model=List[SCIMSyncLogEntry])
async def get_scim_sync_logs(
    org_id: UUID,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get SCIM sync operation logs for an organization.

    Useful for debugging sync issues and auditing provisioning activity.
    """
    await verify_org_access(org_id, current_user, db)

    query = select(SCIMSyncLog).where(SCIMSyncLog.organization_id == org_id)

    if status:
        query = query.where(SCIMSyncLog.status == status)
    if resource_type:
        query = query.where(SCIMSyncLog.resource_type == resource_type)

    query = query.order_by(SCIMSyncLog.synced_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        SCIMSyncLogEntry(
            id=str(log.id),
            operation=log.operation,
            resource_type=log.resource_type,
            scim_id=log.scim_id,
            internal_id=str(log.internal_id) if log.internal_id else None,
            status=log.status,
            error_message=log.error_message,
            error_code=log.error_code,
            synced_at=log.synced_at,
        )
        for log in logs
    ]
