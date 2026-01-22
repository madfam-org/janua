"""
OAuth2 Client Management API

Endpoints for managing OAuth2 clients that use Janua as an OAuth Provider.
This enables external applications to authenticate users via Janua's OIDC endpoints.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas.oauth_client import (
    OAuthClientCreate,
    OAuthClientDetailResponse,
    OAuthClientListResponse,
    OAuthClientResponse,
    OAuthClientSecretInfo,
    OAuthClientSecretRotateRequest,
    OAuthClientSecretRotateResponse,
    OAuthClientSecretRevokeRequest,
    OAuthClientSecretStatusResponse,
    OAuthClientUpdate,
)
from app.services.credential_rotation_service import CredentialRotationService
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
    request: Optional[OAuthClientSecretRotateRequest] = None,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate the client secret for an OAuth2 client with graceful transition.

    This generates a new secret while keeping old secrets valid for a grace period.
    During the grace period, both old and new secrets will work, allowing for
    zero-downtime credential updates.

    **Features**:
    - New secret becomes primary immediately
    - Old secrets remain valid for the grace period (default: 24 hours)
    - Customizable grace period via request body

    **Required permissions**: Client owner, org admin, or system admin
    """
    try:
        client_uuid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client_id format")

    # Get the client
    client = await service.get_client(
        client_db_id=client_uuid,
        user=current_user,
        require_ownership=True,
    )

    if not client:
        raise HTTPException(status_code=404, detail="OAuth client not found")

    # Perform rotation with credential rotation service
    rotation_service = CredentialRotationService(db)
    grace_hours = request.grace_period_hours if request else None

    new_secret_record, plain_secret = await rotation_service.rotate_secret(
        client=client,
        user=current_user,
        grace_hours=grace_hours,
    )

    grace_hours_used = (
        grace_hours if grace_hours is not None else settings.CLIENT_SECRET_ROTATION_GRACE_HOURS
    )
    expires_at = datetime.utcnow() + timedelta(hours=grace_hours_used)

    return OAuthClientSecretRotateResponse(
        client_id=client.client_id,
        client_secret=plain_secret,
        rotated_at=datetime.utcnow(),
        grace_period_hours=grace_hours_used,
        old_secrets_expire_at=expires_at,
    )


@router.get("/{client_id}/secrets", response_model=OAuthClientSecretStatusResponse)
async def get_oauth_client_secret_status(
    client_id: str,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of all secrets for an OAuth2 client.

    Shows active secrets, their expiration times, and rotation recommendations.

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

    rotation_service = CredentialRotationService(db)
    status = await rotation_service.get_secret_status(client)

    return OAuthClientSecretStatusResponse(
        client_id=client.client_id,
        active_count=status["active_count"],
        total_count=status["total_count"],
        has_primary=status["has_primary"],
        primary_created_at=datetime.fromisoformat(status["primary_created_at"])
        if status["primary_created_at"]
        else None,
        primary_age_days=status["primary_age_days"],
        rotation_recommended=status["rotation_recommended"],
        max_age_days=status["max_age_days"],
        secrets=[
            OAuthClientSecretInfo(
                id=s["id"],
                prefix=s["prefix"],
                is_primary=s["is_primary"],
                created_at=datetime.fromisoformat(s["created_at"]),
                expires_at=datetime.fromisoformat(s["expires_at"]) if s["expires_at"] else None,
                revoked_at=datetime.fromisoformat(s["revoked_at"]) if s["revoked_at"] else None,
                last_used_at=datetime.fromisoformat(s["last_used_at"])
                if s["last_used_at"]
                else None,
                is_valid=s["is_valid"],
            )
            for s in status["secrets"]
        ],
    )


@router.post("/{client_id}/secrets/revoke")
async def revoke_oauth_client_secret(
    client_id: str,
    request: OAuthClientSecretRevokeRequest,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a specific secret for an OAuth2 client.

    The secret will be immediately invalidated. Use with caution during rotation
    as this may break client applications still using the old secret.

    **Required permissions**: Client owner, org admin, or system admin
    """
    try:
        client_uuid = uuid.UUID(client_id)
        secret_uuid = uuid.UUID(request.secret_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    client = await service.get_client(
        client_db_id=client_uuid,
        user=current_user,
        require_ownership=True,
    )

    if not client:
        raise HTTPException(status_code=404, detail="OAuth client not found")

    rotation_service = CredentialRotationService(db)
    revoked = await rotation_service.revoke_secret(secret_uuid, current_user)

    if not revoked:
        raise HTTPException(status_code=404, detail="Secret not found")

    return {"message": "Secret revoked successfully", "secret_id": request.secret_id}


@router.post("/{client_id}/secrets/revoke-all-old")
async def revoke_all_old_secrets(
    client_id: str,
    current_user: User = Depends(get_current_user),
    service: OAuthClientService = Depends(get_oauth_client_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke all non-primary secrets for an OAuth2 client.

    This immediately invalidates all secrets except the current primary.
    Useful for emergency situations where old secrets may be compromised.

    **Warning**: This may break client applications still using old secrets
    during a rotation grace period.

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

    rotation_service = CredentialRotationService(db)
    revoked_count = await rotation_service.revoke_all_except_primary(client, current_user)

    return {
        "message": f"Revoked {revoked_count} old secret(s)",
        "revoked_count": revoked_count,
    }


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
