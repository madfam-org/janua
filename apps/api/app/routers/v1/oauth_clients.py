"""
OAuth2 Client Management API

Endpoints for managing OAuth2 clients that use Janua as an OAuth Provider.
This enables external applications to authenticate users via Janua's OIDC endpoints.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas.oauth_client import (
    OAuthClientCreate,
    OAuthClientDetailResponse,
    OAuthClientListResponse,
    OAuthClientResponse,
    OAuthClientSecretRotateResponse,
    OAuthClientUpdate,
)
from app.services.oauth_client_service import OAuthClientService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth/clients", tags=["oauth-clients"])


async def get_oauth_client_service(
    db: AsyncSession = Depends(get_db),
) -> OAuthClientService:
    """Dependency to get OAuth client service"""
    return OAuthClientService(db)


@router.post("", response_model=OAuthClientDetailResponse, status_code=201)
async def create_oauth_client(
    data: OAuthClientCreate,
    organization_id: Optional[str] = Query(None, description="Organization to scope client to"),
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    Create a new OAuth2 client.

    This registers an application to use Janua as an OAuth2/OIDC provider.
    The client_secret is only returned once on creation - save it immediately.

    **Required permissions**: Authenticated user (org admin for org-scoped clients)
    """
    try:
        org_uuid = uuid.UUID(organization_id) if organization_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization_id format")

    client, plain_secret = await service.create_client(
        data=data,
        created_by=current_user,
        organization_id=org_uuid,
    )

    return OAuthClientDetailResponse(
        id=str(client.id),
        client_id=client.client_id,
        client_secret=plain_secret,  # Only returned on creation
        name=client.name,
        description=client.description,
        redirect_uris=client.redirect_uris or [],
        allowed_scopes=client.allowed_scopes or [],
        grant_types=client.grant_types or [],
        logo_url=client.logo_url,
        website_url=client.website_url,
        is_active=client.is_active,
        is_confidential=client.is_confidential,
        last_used_at=client.last_used_at,
        organization_id=str(client.organization_id) if client.organization_id else None,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.get("", response_model=OAuthClientListResponse)
async def list_oauth_clients(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    List OAuth2 clients accessible to the current user.

    Returns clients created by the user or within organizations they admin.
    System admins can see all clients.

    **Required permissions**: Authenticated user
    """
    try:
        org_uuid = uuid.UUID(organization_id) if organization_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization_id format")

    clients, total = await service.list_clients(
        user=current_user,
        organization_id=org_uuid,
        page=page,
        per_page=per_page,
    )

    return OAuthClientListResponse(
        clients=[
            OAuthClientResponse(
                id=str(c.id),
                client_id=c.client_id,
                name=c.name,
                description=c.description,
                is_active=c.is_active,
                is_confidential=c.is_confidential,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in clients
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{client_id}", response_model=OAuthClientDetailResponse)
async def get_oauth_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    Get details of an OAuth2 client.

    Note: The client_secret is never returned after creation.

    **Required permissions**: Client owner, org admin, or system admin
    """
    try:
        client_uuid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client_id format")

    client = await service.get_client(
        client_db_id=client_uuid,
        user=current_user,
        require_ownership=True,
    )

    if not client:
        raise HTTPException(status_code=404, detail="OAuth client not found")

    return OAuthClientDetailResponse(
        id=str(client.id),
        client_id=client.client_id,
        client_secret=None,  # Never return secret after creation
        name=client.name,
        description=client.description,
        redirect_uris=client.redirect_uris or [],
        allowed_scopes=client.allowed_scopes or [],
        grant_types=client.grant_types or [],
        logo_url=client.logo_url,
        website_url=client.website_url,
        is_active=client.is_active,
        is_confidential=client.is_confidential,
        last_used_at=client.last_used_at,
        organization_id=str(client.organization_id) if client.organization_id else None,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.patch("/{client_id}", response_model=OAuthClientDetailResponse)
async def update_oauth_client(
    client_id: str,
    data: OAuthClientUpdate,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    Update an OAuth2 client.

    **Required permissions**: Client owner, org admin, or system admin
    """
    try:
        client_uuid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client_id format")

    client = await service.update_client(
        client_db_id=client_uuid,
        data=data,
        user=current_user,
    )

    if not client:
        raise HTTPException(status_code=404, detail="OAuth client not found")

    return OAuthClientDetailResponse(
        id=str(client.id),
        client_id=client.client_id,
        client_secret=None,
        name=client.name,
        description=client.description,
        redirect_uris=client.redirect_uris or [],
        allowed_scopes=client.allowed_scopes or [],
        grant_types=client.grant_types or [],
        logo_url=client.logo_url,
        website_url=client.website_url,
        is_active=client.is_active,
        is_confidential=client.is_confidential,
        last_used_at=client.last_used_at,
        organization_id=str(client.organization_id) if client.organization_id else None,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.delete("/{client_id}", status_code=204)
async def delete_oauth_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    Delete an OAuth2 client.

    This will immediately invalidate all tokens issued to this client.

    **Required permissions**: Client owner, org admin, or system admin
    """
    try:
        client_uuid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client_id format")

    deleted = await service.delete_client(
        client_db_id=client_uuid,
        user=current_user,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="OAuth client not found")

    return None


@router.post("/{client_id}/rotate", response_model=OAuthClientSecretRotateResponse)
async def rotate_oauth_client_secret(
    client_id: str,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    Rotate the client secret for an OAuth2 client.

    This generates a new secret and invalidates the old one immediately.
    Save the new secret - it will only be returned once.

    **Required permissions**: Client owner, org admin, or system admin
    """
    try:
        client_uuid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client_id format")

    result = await service.rotate_secret(
        client_db_id=client_uuid,
        user=current_user,
    )

    if not result:
        raise HTTPException(status_code=404, detail="OAuth client not found")

    client, new_secret = result

    return OAuthClientSecretRotateResponse(
        client_id=client.client_id,
        client_secret=new_secret,
        rotated_at=datetime.utcnow(),
    )


# Admin-only endpoints
@router.get("/admin/all", response_model=OAuthClientListResponse)
async def admin_list_all_oauth_clients(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    service: OAuthClientService = Depends(get_oauth_client_service),
):
    """
    List all OAuth2 clients in the system (admin only).

    **Required permissions**: System admin
    """
    clients, total = await service.list_clients(
        user=current_user,
        page=page,
        per_page=per_page,
    )

    return OAuthClientListResponse(
        clients=[
            OAuthClientResponse(
                id=str(c.id),
                client_id=c.client_id,
                name=c.name,
                description=c.description,
                is_active=c.is_active,
                is_confidential=c.is_confidential,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in clients
        ],
        total=total,
        page=page,
        per_page=per_page,
    )
