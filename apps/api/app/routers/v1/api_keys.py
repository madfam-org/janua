"""
API Key Management Router

REST endpoints for creating, managing, and revoking API keys.
API keys allow programmatic access to Janua APIs with scoped permissions.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import OrganizationMember, User
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyRotateResponse,
    ApiKeyUpdate,
    ApiKeyVerifyRequest,
    ApiKeyVerifyResponse,
)
from app.services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "Not found"},
    },
)


async def get_user_organization_id(
    user: User,
    db: AsyncSession,
    organization_id: Optional[str] = None,
) -> uuid.UUID:
    """
    Get the organization ID for API key operations.

    If organization_id is provided, validates user membership.
    Otherwise, returns the user's first organization.
    """
    if organization_id:
        org_uuid = uuid.UUID(organization_id)
        # Validate user is member of this organization
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == org_uuid,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="Not a member of the specified organization",
            )
        return org_uuid
    else:
        # Get user's first organization
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id
            ).order_by(OrganizationMember.created_at)
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=400,
                detail="User must belong to an organization to create API keys",
            )
        return membership.organization_id


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    organization_id: Optional[str] = Query(
        None, description="Filter by organization ID"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include revoked keys"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all API keys for the current user.

    Returns a paginated list of API keys. By default, only active keys
    are returned. Use `include_inactive=true` to also see revoked keys.
    """
    service = ApiKeyService(db)

    org_uuid = None
    if organization_id:
        org_uuid = uuid.UUID(organization_id)

    api_keys, total = await service.list_api_keys(
        user=current_user,
        organization_id=org_uuid,
        page=page,
        per_page=per_page,
        include_inactive=include_inactive,
    )

    return ApiKeyListResponse(
        items=[
            ApiKeyResponse(
                id=str(key.id),
                user_id=str(key.user_id),
                organization_id=str(key.organization_id),
                name=key.name,
                prefix=key.prefix,
                key_prefix=key.key_prefix,
                scopes=key.scopes or [],
                rate_limit_per_min=key.rate_limit_per_min or 60,
                is_active=key.is_active,
                last_used=key.last_used,
                expires_at=key.expires_at,
                revoked_at=key.revoked_at,
                created_at=key.created_at,
                updated_at=key.updated_at,
            )
            for key in api_keys
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    organization_id: Optional[str] = Query(
        None, description="Organization ID (uses default org if not specified)"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.

    **IMPORTANT**: The plain API key is returned **only once** in this response.
    Store it securely as it cannot be retrieved again. Only the key prefix
    will be visible in subsequent API calls.

    The key format is: `jnk_<random-string>`
    """
    service = ApiKeyService(db)

    org_uuid = await get_user_organization_id(current_user, db, organization_id)

    api_key, plain_key = await service.create_api_key(
        data=data,
        user=current_user,
        organization_id=org_uuid,
    )

    return ApiKeyCreateResponse(
        id=str(api_key.id),
        user_id=str(api_key.user_id),
        organization_id=str(api_key.organization_id),
        name=api_key.name,
        prefix=api_key.prefix,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes or [],
        rate_limit_per_min=api_key.rate_limit_per_min or 60,
        is_active=api_key.is_active,
        last_used=api_key.last_used,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
        key=plain_key,
    )


@router.get("/{api_key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific API key.

    Returns the key's metadata including name, scopes, and last used timestamp.
    The actual key value is never returned after creation.
    """
    service = ApiKeyService(db)

    try:
        key_uuid = uuid.UUID(api_key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid API key ID format")

    api_key = await service.get_api_key(key_uuid, current_user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return ApiKeyResponse(
        id=str(api_key.id),
        user_id=str(api_key.user_id),
        organization_id=str(api_key.organization_id),
        name=api_key.name,
        prefix=api_key.prefix,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes or [],
        rate_limit_per_min=api_key.rate_limit_per_min or 60,
        is_active=api_key.is_active,
        last_used=api_key.last_used,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
    )


@router.patch("/{api_key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    api_key_id: str,
    data: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an API key.

    You can update the key's name, scopes, expiration date, or active status.
    Note: Deactivating a key is equivalent to revoking it.
    """
    service = ApiKeyService(db)

    try:
        key_uuid = uuid.UUID(api_key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid API key ID format")

    api_key = await service.update_api_key(key_uuid, data, current_user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return ApiKeyResponse(
        id=str(api_key.id),
        user_id=str(api_key.user_id),
        organization_id=str(api_key.organization_id),
        name=api_key.name,
        prefix=api_key.prefix,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes or [],
        rate_limit_per_min=api_key.rate_limit_per_min or 60,
        is_active=api_key.is_active,
        last_used=api_key.last_used,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
    )


@router.delete("/{api_key_id}", status_code=204)
async def delete_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete (revoke) an API key.

    The key is immediately invalidated and can no longer be used for
    authentication. This operation cannot be undone.
    """
    service = ApiKeyService(db)

    try:
        key_uuid = uuid.UUID(api_key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid API key ID format")

    success = await service.delete_api_key(key_uuid, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")

    return None


@router.post("/{api_key_id}/rotate", response_model=ApiKeyRotateResponse)
async def rotate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate an API key to generate a new secret.

    The old key is immediately invalidated. A new key is generated with
    the same metadata (name, scopes, etc.).

    **IMPORTANT**: The new plain API key is returned **only once** in this response.
    Store it securely as it cannot be retrieved again.
    """
    service = ApiKeyService(db)

    try:
        key_uuid = uuid.UUID(api_key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid API key ID format")

    result = await service.rotate_api_key(key_uuid, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key, plain_key, old_prefix = result

    return ApiKeyRotateResponse(
        id=str(api_key.id),
        user_id=str(api_key.user_id),
        organization_id=str(api_key.organization_id),
        name=api_key.name,
        prefix=api_key.prefix,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes or [],
        rate_limit_per_min=api_key.rate_limit_per_min or 60,
        is_active=api_key.is_active,
        last_used=api_key.last_used,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
        key=plain_key,
        previous_prefix=old_prefix,
    )


@router.post("/verify", response_model=ApiKeyVerifyResponse)
async def verify_api_key(
    data: ApiKeyVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an API key and return its org_id and scopes.

    This is an **internal** endpoint intended for service-to-service calls.
    It does NOT require JWT authentication so that other MADFAM services
    can validate API keys presented by external consumers.

    Returns valid=false (not an HTTP error) when the key is invalid,
    so callers can distinguish "key checked but rejected" from transport errors.
    """
    service = ApiKeyService(db)

    api_key = await service.verify_key_for_service(data.key)

    if not api_key:
        return ApiKeyVerifyResponse(
            valid=False,
            org_id=None,
            scopes=[],
            key_id=None,
        )

    return ApiKeyVerifyResponse(
        valid=True,
        org_id=str(api_key.organization_id),
        scopes=api_key.scopes or [],
        key_id=str(api_key.id),
    )
