"""
Third-party integrations token access endpoints.

This module provides endpoints for authorized services (like Enclii) to retrieve
a user's OAuth access tokens for third-party providers (like GitHub).

Security considerations:
- Requires valid Janua JWT authentication
- Only returns tokens for the authenticated user's own linked accounts
- Tokens are encrypted at rest in the database
- Access is logged for audit purposes
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ActivityLog, OAuthAccount, OAuthProvider, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class IntegrationTokenResponse(BaseModel):
    """Response containing a third-party integration token"""

    provider: str
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    provider_user_id: Optional[str] = None
    provider_email: Optional[str] = None
    linked_at: datetime


class IntegrationStatusResponse(BaseModel):
    """Response containing integration status for a provider"""

    provider: str
    linked: bool
    provider_email: Optional[str] = None
    linked_at: Optional[datetime] = None
    can_access_repos: bool = False  # True if scope includes repo access


class IntegrationsListResponse(BaseModel):
    """Response listing all available integrations"""

    integrations: list[IntegrationStatusResponse]


@router.get("/{provider}/token", response_model=IntegrationTokenResponse)
async def get_integration_token(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the access token for a linked third-party provider.

    This endpoint is designed for service-to-service communication, allowing
    authorized services (like Enclii) to retrieve a user's GitHub token to
    perform repository operations on their behalf.

    The user must have previously linked their GitHub account via OAuth.

    Args:
        provider: The OAuth provider (e.g., 'github', 'google')

    Returns:
        IntegrationTokenResponse with the access token and metadata

    Raises:
        400: Invalid provider
        404: Provider account not linked
    """
    try:
        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider: {provider}. Valid providers: {[p.value for p in OAuthProvider]}",
            )

        # Find OAuth account for this user and provider
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id, OAuthAccount.provider == oauth_provider
            )
        )
        oauth_account = result.scalar_one_or_none()

        if not oauth_account:
            raise HTTPException(
                status_code=404,
                detail=f"{provider.capitalize()} account is not linked. Please connect your {provider.capitalize()} account first.",
            )

        if not oauth_account.access_token:
            raise HTTPException(
                status_code=404,
                detail=f"No access token available for {provider.capitalize()}. Please re-link your account.",
            )

        # Log the token access for audit purposes
        activity = ActivityLog(
            user_id=current_user.id,
            action="integration_token_accessed",
            resource_type="oauth_integration",
            resource_id=provider,
            activity_metadata={
                "provider": provider,
                "provider_user_id": oauth_account.provider_user_id,
            },
        )
        db.add(activity)
        await db.commit()

        # SECURITY: Use parameterized logging to prevent log injection
        logger.info(
            "Integration token accessed",
            user_id=str(current_user.id),
            provider=provider,
        )

        return IntegrationTokenResponse(
            provider=provider,
            access_token=oauth_account.access_token,
            refresh_token=oauth_account.refresh_token,
            token_expires_at=oauth_account.token_expires_at,
            provider_user_id=oauth_account.provider_user_id,
            provider_email=oauth_account.provider_email,
            linked_at=oauth_account.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        # SECURITY: Use parameterized logging to prevent log injection
        logger.error("Error retrieving integration token", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve integration token")


@router.get("/{provider}/status", response_model=IntegrationStatusResponse)
async def get_integration_status(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if a third-party provider is linked for the current user.

    This is a lightweight endpoint to check integration status without
    retrieving the actual token.

    Args:
        provider: The OAuth provider (e.g., 'github', 'google')

    Returns:
        IntegrationStatusResponse with link status
    """
    try:
        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        # Find OAuth account
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id, OAuthAccount.provider == oauth_provider
            )
        )
        oauth_account = result.scalar_one_or_none()

        if not oauth_account:
            return IntegrationStatusResponse(
                provider=provider,
                linked=False,
                can_access_repos=False,
            )

        # Check if GitHub account has repo scope (stored in provider_data)
        can_access_repos = False
        if oauth_provider == OAuthProvider.GITHUB and oauth_account.provider_data:
            scopes = oauth_account.provider_data.get("scopes", [])
            can_access_repos = "repo" in scopes or "public_repo" in scopes

        return IntegrationStatusResponse(
            provider=provider,
            linked=True,
            provider_email=oauth_account.provider_email,
            linked_at=oauth_account.created_at,
            can_access_repos=can_access_repos,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking integration status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check integration status")


@router.get("/", response_model=IntegrationsListResponse)
async def list_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all available integrations and their status for the current user.

    Returns:
        IntegrationsListResponse with all integration statuses
    """
    try:
        # Get all linked OAuth accounts for user
        result = await db.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == current_user.id)
        )
        oauth_accounts = result.scalars().all()

        # Build lookup map
        linked_providers = {acc.provider: acc for acc in oauth_accounts}

        integrations = []
        for provider in list(OAuthProvider):
            oauth_account = linked_providers.get(provider)

            can_access_repos = False
            if provider == OAuthProvider.GITHUB and oauth_account and oauth_account.provider_data:
                scopes = oauth_account.provider_data.get("scopes", [])
                can_access_repos = "repo" in scopes or "public_repo" in scopes

            integrations.append(
                IntegrationStatusResponse(
                    provider=provider.value,
                    linked=oauth_account is not None,
                    provider_email=oauth_account.provider_email if oauth_account else None,
                    linked_at=oauth_account.created_at if oauth_account else None,
                    can_access_repos=can_access_repos,
                )
            )

        return IntegrationsListResponse(integrations=integrations)

    except Exception as e:
        logger.error(f"Error listing integrations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list integrations")
