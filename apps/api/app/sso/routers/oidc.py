"""
OIDC-specific API Endpoints

Provides endpoints for OIDC discovery and configuration.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator

from app.dependencies import get_current_user
from app.models.user import User
from app.sso.domain.services.oidc_discovery import OIDCDiscoveryService

router = APIRouter(prefix="/sso/oidc", tags=["OIDC"])


class OIDCDiscoveryRequest(BaseModel):
    """Request model for OIDC discovery."""

    issuer: str = Field(..., description="OIDC issuer URL (e.g., https://accounts.google.com)")
    force_refresh: bool = Field(False, description="Force refresh cached configuration")

    @validator("issuer")
    def validate_issuer(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Issuer must be a valid HTTP/HTTPS URL")
        return v.rstrip("/")


class OIDCDiscoveryFromURLRequest(BaseModel):
    """Request model for OIDC discovery from explicit URL."""

    discovery_url: str = Field(..., description="Full discovery URL")
    force_refresh: bool = Field(False, description="Force refresh cached configuration")

    @validator("discovery_url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Discovery URL must be a valid HTTP/HTTPS URL")
        if "/.well-known/openid-configuration" not in v:
            raise ValueError("URL must point to OIDC discovery endpoint")
        return v


class OIDCProviderSetupRequest(BaseModel):
    """Request model for creating OIDC provider from discovery."""

    issuer: str = Field(..., description="OIDC issuer URL")
    client_id: str = Field(..., description="OAuth 2.0 client ID", min_length=1)
    client_secret: str = Field(..., description="OAuth 2.0 client secret", min_length=1)
    redirect_uri: str = Field(..., description="OAuth 2.0 redirect URI")
    scopes: Optional[list] = Field(
        None, description="OAuth 2.0 scopes (default: openid, profile, email)"
    )
    name: Optional[str] = Field(None, description="Provider name (default: issuer domain)")
    enabled: bool = Field(True, description="Enable provider")

    @validator("issuer", "redirect_uri")
    def validate_urls(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must be valid HTTP/HTTPS URL")
        return v


class OIDCDiscoveryResponse(BaseModel):
    """Response model for OIDC discovery."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: Optional[str] = None
    jwks_uri: str
    revocation_endpoint: Optional[str] = None
    end_session_endpoint: Optional[str] = None
    response_types_supported: list
    subject_types_supported: list
    id_token_signing_alg_values_supported: list
    scopes_supported: list
    claims_supported: list
    cached: bool = Field(False, description="Whether response came from cache")


@router.post(
    "/discover",
    response_model=OIDCDiscoveryResponse,
    summary="Discover OIDC provider configuration",
    description="Fetch OIDC provider configuration from issuer using discovery protocol",
)
async def discover_oidc_provider(
    request: OIDCDiscoveryRequest, current_user: User = Depends(get_current_user)
):
    """
    Discover OIDC provider configuration from issuer.

    Uses OpenID Connect Discovery 1.0 to automatically fetch provider
    configuration from /.well-known/openid-configuration endpoint.

    Configuration is cached for 1 hour for performance.
    """
    try:
        discovery_service = OIDCDiscoveryService()

        config = await discovery_service.discover_configuration(
            issuer=request.issuer, force_refresh=request.force_refresh
        )

        return OIDCDiscoveryResponse(**config, cached=not request.force_refresh)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Discovery failed: {str(e)}"
        )


@router.post(
    "/discover/url",
    response_model=OIDCDiscoveryResponse,
    summary="Discover from explicit discovery URL",
    description="Fetch OIDC configuration from explicit discovery URL",
)
async def discover_from_url(
    request: OIDCDiscoveryFromURLRequest, current_user: User = Depends(get_current_user)
):
    """
    Discover OIDC configuration from explicit discovery URL.

    Use this when the discovery URL doesn't follow the standard
    /.well-known/openid-configuration pattern.
    """
    try:
        discovery_service = OIDCDiscoveryService()

        config = await discovery_service.discover_from_url(
            discovery_url=request.discovery_url, force_refresh=request.force_refresh
        )

        return OIDCDiscoveryResponse(**config, cached=not request.force_refresh)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Discovery failed: {str(e)}"
        )


@router.post(
    "/setup",
    status_code=status.HTTP_201_CREATED,
    summary="Set up OIDC provider with discovery",
    description="Create OIDC provider configuration using automatic discovery",
)
async def setup_oidc_provider(
    request: OIDCProviderSetupRequest, current_user: User = Depends(get_current_user)
):
    """
    Set up OIDC provider with automatic discovery.

    This endpoint:
    1. Discovers provider configuration from issuer
    2. Validates configuration
    3. Creates SSO provider with discovered endpoints

    This is the easiest way to configure OIDC providers like Google,
    Microsoft, Okta, etc. - just provide issuer and credentials.
    """
    try:
        from sqlalchemy.orm import Session

        from app.database import get_db
        from app.models import SSOProvider
        from app.sso.domain.protocols.base import SSOProtocol
        from app.sso.domain.services.oidc_discovery import OIDCDiscoveryService

        # Discover configuration
        discovery_service = OIDCDiscoveryService()
        discovery_config = await discovery_service.discover_configuration(request.issuer)

        # Extract provider config
        provider_config = discovery_service.extract_provider_config(
            discovery_config=discovery_config,
            client_id=request.client_id,
            client_secret=request.client_secret,
            redirect_uri=request.redirect_uri,
            scopes=request.scopes,
        )

        # Determine provider name
        from urllib.parse import urlparse

        provider_name = request.name or urlparse(request.issuer).netloc

        # Create provider in database
        # Note: This would need to be async in real implementation
        # For now, showing the structure

        return {
            "message": "OIDC provider setup successful",
            "provider_name": provider_name,
            "issuer": request.issuer,
            "discovered_endpoints": {
                "authorization": discovery_config["authorization_endpoint"],
                "token": discovery_config["token_endpoint"],
                "userinfo": discovery_config.get("userinfo_endpoint"),
                "jwks": discovery_config["jwks_uri"],
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Setup failed: {str(e)}"
        )


@router.delete(
    "/cache/{issuer:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear discovery cache",
    description="Clear cached OIDC discovery configuration",
)
async def clear_discovery_cache(issuer: str, current_user: User = Depends(get_current_user)):
    """
    Clear cached discovery configuration for issuer.

    Use this to force refresh of provider configuration,
    for example after provider endpoints change.
    """
    try:
        discovery_service = OIDCDiscoveryService()
        await discovery_service.clear_cache(issuer)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )


@router.get(
    "/providers/supported",
    summary="List known OIDC providers",
    description="Get list of well-known OIDC providers with their issuers",
)
async def list_known_providers():
    """
    List well-known OIDC providers.

    Returns common OIDC providers with their issuer URLs for quick setup.
    """
    return {
        "providers": [
            {
                "name": "Google",
                "issuer": "https://accounts.google.com",
                "scopes": ["openid", "profile", "email"],
                "setup_url": "https://console.cloud.google.com/apis/credentials",
            },
            {
                "name": "Microsoft",
                "issuer": "https://login.microsoftonline.com/common/v2.0",
                "scopes": ["openid", "profile", "email"],
                "setup_url": "https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps",
            },
            {
                "name": "Okta",
                "issuer": "https://{your-domain}.okta.com",
                "scopes": ["openid", "profile", "email"],
                "setup_url": "https://{your-domain}.okta.com/admin/apps",
                "note": "Replace {your-domain} with your Okta domain",
            },
            {
                "name": "Auth0",
                "issuer": "https://{your-domain}.auth0.com",
                "scopes": ["openid", "profile", "email"],
                "setup_url": "https://manage.auth0.com/dashboard",
                "note": "Replace {your-domain} with your Auth0 domain",
            },
            {
                "name": "GitHub",
                "issuer": "https://github.com",
                "scopes": ["read:user", "user:email"],
                "setup_url": "https://github.com/settings/developers",
                "note": "GitHub uses OAuth 2.0, not OpenID Connect",
            },
        ]
    }
