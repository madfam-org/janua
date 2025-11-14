"""
SSO/SAML API endpoints for enterprise authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from ...models import User, Organization, SSOConfiguration, SSOProvider, SSOStatus
from app.services.sso_service import SSOService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sso",
    tags=["SSO/SAML"],
    responses={404: {"description": "Not found"}},
)


# Pydantic models for request/response
class SSOConfigurationCreate(BaseModel):
    """Create SSO configuration request"""
    provider: SSOProvider
    # SAML fields
    saml_metadata_url: Optional[str] = None
    saml_metadata_xml: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    saml_certificate: Optional[str] = None
    saml_entity_id: Optional[str] = None
    
    # OIDC fields
    oidc_issuer: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    
    # Common settings
    jit_provisioning: bool = True
    default_role: str = "member"
    attribute_mapping: Dict[str, str] = Field(default_factory=dict)
    allowed_domains: List[str] = Field(default_factory=list)


class SSOConfigurationUpdate(BaseModel):
    """Update SSO configuration request"""
    enabled: Optional[bool] = None
    # SAML fields
    saml_metadata_url: Optional[str] = None
    saml_metadata_xml: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    saml_certificate: Optional[str] = None
    
    # OIDC fields
    oidc_issuer: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    
    # Settings
    jit_provisioning: Optional[bool] = None
    default_role: Optional[str] = None
    attribute_mapping: Optional[Dict[str, str]] = None
    allowed_domains: Optional[List[str]] = None


class SSOConfigurationResponse(BaseModel):
    """SSO configuration response"""
    id: str
    organization_id: str
    provider: SSOProvider
    status: SSOStatus
    enabled: bool
    
    # SAML info (sanitized)
    saml_entity_id: Optional[str] = None
    saml_acs_url: Optional[str] = None
    saml_sso_url: Optional[str] = None
    
    # OIDC info (sanitized)
    oidc_issuer: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_authorization_url: Optional[str] = None
    
    # Settings
    jit_provisioning: bool
    default_role: str
    allowed_domains: List[str]
    
    created_at: str
    updated_at: str


class SSOInitiateRequest(BaseModel):
    """SSO login initiation request"""
    organization_slug: str
    return_url: Optional[str] = None


class SSOTestRequest(BaseModel):
    """SSO configuration test request"""
    configuration_id: str


# SSO service dependency
def get_sso_service() -> SSOService:
    """
    Create SSO service instance with dependencies.
    This is a placeholder - in production, inject actual db, cache, and jwt_service
    """
    # TODO: Replace with actual dependency injection
    return None  # Will be properly initialized when dependencies are available


@router.post("/configurations", response_model=SSOConfigurationResponse)
async def create_sso_configuration(
    organization_id: str,
    config: SSOConfigurationCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create SSO configuration for an organization
    
    Requires admin privileges for the organization.
    """
    try:
        # Verify organization exists and user is admin
        org = await db.get(Organization, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Check if SSO config already exists
        result = await db.execute(select(SSOConfiguration).where(
            SSOConfiguration.organization_id == organization_id
        ))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=400, 
                detail="SSO configuration already exists for this organization"
            )
        
        # Create configuration based on provider
        if config.provider == SSOProvider.SAML:
            result = await sso_service.create_saml_configuration(
                organization_id=organization_id,
                metadata_url=config.saml_metadata_url,
                metadata_xml=config.saml_metadata_xml,
                sso_url=config.saml_sso_url,
                slo_url=config.saml_slo_url,
                certificate=config.saml_certificate,
                entity_id=config.saml_entity_id,
                jit_provisioning=config.jit_provisioning,
                default_role=config.default_role,
                attribute_mapping=config.attribute_mapping,
                allowed_domains=config.allowed_domains
            )
        elif config.provider == SSOProvider.OIDC:
            result = await sso_service.create_oidc_configuration(
                organization_id=organization_id,
                issuer=config.oidc_issuer,
                client_id=config.oidc_client_id,
                client_secret=config.oidc_client_secret,
                discovery_url=config.oidc_discovery_url,
                jit_provisioning=config.jit_provisioning,
                default_role=config.default_role,
                attribute_mapping=config.attribute_mapping,
                allowed_domains=config.allowed_domains
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Provider {config.provider} not yet supported"
            )
        
        return SSOConfigurationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to create SSO configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configurations/{organization_id}", response_model=SSOConfigurationResponse)
async def get_sso_configuration(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get SSO configuration for an organization
    
    Returns the SSO configuration if the user belongs to the organization.
    """
    try:
        config = await sso_service.get_configuration(organization_id)
        if not config:
            raise HTTPException(status_code=404, detail="SSO configuration not found")
        
        # Verify user belongs to organization
        # TODO: Add proper organization membership check
        
        return SSOConfigurationResponse(**config)
        
    except Exception as e:
        logger.error(f"Failed to get SSO configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configurations/{organization_id}", response_model=SSOConfigurationResponse)
async def update_sso_configuration(
    organization_id: str,
    update: SSOConfigurationUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update SSO configuration for an organization
    
    Requires admin privileges for the organization.
    """
    try:
        result = await sso_service.update_configuration(
            organization_id, 
            update.dict(exclude_unset=True)
        )
        if not result:
            raise HTTPException(status_code=404, detail="SSO configuration not found")
        
        return SSOConfigurationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to update SSO configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configurations/{organization_id}")
async def delete_sso_configuration(
    organization_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete SSO configuration for an organization
    
    Requires admin privileges for the organization.
    """
    try:
        result = await sso_service.delete_configuration(organization_id)
        if not result:
            raise HTTPException(status_code=404, detail="SSO configuration not found")
        
        return {"message": "SSO configuration deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete SSO configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initiate")
async def initiate_sso(
    request: SSOInitiateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate SSO login flow
    
    Returns redirect URL to identity provider.
    """
    try:
        # Get organization by slug
        org_result = await db.execute(select(Organization).where(
            Organization.slug == request.organization_slug
        ))
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get SSO configuration
        config = await sso_service.get_configuration(str(org.id))
        if not config or not config.get("enabled"):
            raise HTTPException(
                status_code=400, 
                detail="SSO is not enabled for this organization"
            )
        
        # Initiate based on provider
        if config["provider"] == SSOProvider.SAML.value:
            result = await sso_service.initiate_saml_sso(
                str(org.id), 
                request.return_url
            )
        elif config["provider"] == SSOProvider.OIDC.value:
            result = await sso_service.initiate_oidc_sso(
                str(org.id), 
                request.return_url
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Provider {config['provider']} not supported"
            )
        
        return RedirectResponse(url=result["redirect_url"], status_code=302)
        
    except Exception as e:
        logger.error(f"Failed to initiate SSO: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/saml/acs")
async def saml_acs(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    SAML Assertion Consumer Service (ACS) endpoint
    
    Handles SAML response from identity provider.
    """
    try:
        form_data = await request.form()
        saml_response = form_data.get("SAMLResponse")
        relay_state = form_data.get("RelayState", "")
        
        if not saml_response:
            raise HTTPException(status_code=400, detail="Missing SAML response")
        
        # Handle SAML response
        result = await sso_service.handle_saml_response(saml_response, relay_state)
        
        # Create session and redirect
        # TODO: Create JWT tokens and session
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        return_url = result.get("return_url", "/")
        
        # Set cookies and redirect
        response = RedirectResponse(url=return_url, status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"SAML ACS error: {str(e)}")
        raise HTTPException(status_code=500, detail="SSO authentication failed")


@router.post("/saml/slo")
async def saml_slo(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    SAML Single Logout (SLO) endpoint
    
    Handles logout request from identity provider.
    """
    try:
        form_data = await request.form()
        saml_request = form_data.get("SAMLRequest")
        saml_response = form_data.get("SAMLResponse")
        relay_state = form_data.get("RelayState", "")
        
        if saml_request:
            # Handle logout request from IdP
            result = await sso_service.handle_saml_logout_request(
                saml_request, 
                relay_state
            )
        elif saml_response:
            # Handle logout response from IdP
            result = await sso_service.handle_saml_logout_response(
                saml_response, 
                relay_state
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail="Missing SAML request or response"
            )
        
        # Clear session and redirect
        response = RedirectResponse(url=result.get("redirect_url", "/"), status_code=302)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        
        return response
        
    except Exception as e:
        logger.error(f"SAML SLO error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/oidc/callback")
async def oidc_callback(
    code: str,
    state: str,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    OIDC callback endpoint
    
    Handles OAuth2/OIDC response from identity provider.
    """
    try:
        if error:
            logger.error(f"OIDC error: {error} - {error_description}")
            raise HTTPException(
                status_code=400, 
                detail=error_description or "Authentication failed"
            )
        
        # Handle OIDC callback
        result = await sso_service.handle_oidc_callback(code, state)
        
        # Create session and redirect
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        return_url = result.get("return_url", "/")
        
        # Set cookies and redirect
        response = RedirectResponse(url=return_url, status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"OIDC callback error: {str(e)}")
        raise HTTPException(status_code=500, detail="SSO authentication failed")


@router.post("/test")
async def test_sso_configuration(
    test_request: SSOTestRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Test SSO configuration
    
    Validates the SSO configuration without initiating a full login flow.
    """
    try:
        result = await sso_service.test_configuration(test_request.configuration_id)
        return result
        
    except Exception as e:
        logger.error(f"SSO test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata/{organization_id}")
async def get_sp_metadata(
    organization_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get Service Provider (SP) metadata for SAML configuration
    
    Returns the SP metadata XML for configuring the identity provider.
    """
    try:
        metadata = await sso_service.generate_sp_metadata(organization_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        return Response(
            content=metadata,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=sp-metadata-{organization_id}.xml"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to generate SP metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))