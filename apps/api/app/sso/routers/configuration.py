"""
SSO Configuration API Endpoints

Provides endpoints for managing SSO provider configurations.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import SSOProvider
from app.models.user import User
from app.sso.domain.protocols.base import SSOProtocol
from app.sso.domain.services.certificate_manager import CertificateManager
from app.sso.domain.services.metadata_manager import MetadataManager

router = APIRouter(prefix="/sso/config", tags=["SSO Configuration"])


class SSOProviderCreate(BaseModel):
    """Request model for creating SSO provider configuration."""

    name: str = Field(..., description="Provider name", min_length=1, max_length=100)
    protocol: str = Field(..., description="SSO protocol (saml or oidc)")

    # SAML-specific fields
    saml_entity_id: Optional[str] = Field(None, description="SAML IdP entity ID")
    saml_sso_url: Optional[str] = Field(None, description="SAML SSO URL")
    saml_slo_url: Optional[str] = Field(None, description="SAML SLO URL")
    saml_certificate: Optional[str] = Field(None, description="SAML signing certificate")
    saml_want_assertions_signed: bool = Field(True, description="Require signed assertions")
    saml_metadata_xml: Optional[str] = Field(
        None, description="SAML metadata XML (alternative to individual fields)"
    )

    # OIDC-specific fields
    oidc_issuer: Optional[str] = Field(None, description="OIDC issuer URL")
    oidc_client_id: Optional[str] = Field(None, description="OIDC client ID")
    oidc_client_secret: Optional[str] = Field(None, description="OIDC client secret")
    oidc_authorization_endpoint: Optional[str] = Field(
        None, description="OIDC authorization endpoint"
    )
    oidc_token_endpoint: Optional[str] = Field(None, description="OIDC token endpoint")
    oidc_userinfo_endpoint: Optional[str] = Field(None, description="OIDC userinfo endpoint")
    oidc_jwks_uri: Optional[str] = Field(None, description="OIDC JWKS URI")
    oidc_discovery_url: Optional[str] = Field(
        None, description="OIDC discovery URL (alternative to individual endpoints)"
    )

    enabled: bool = Field(True, description="Enable this provider")

    @validator("protocol")
    def validate_protocol(cls, v):
        if v.lower() not in ["saml", "oidc"]:
            raise ValueError('Protocol must be either "saml" or "oidc"')
        return v.lower()

    @validator("saml_metadata_xml")
    def validate_saml_metadata(cls, v, values):
        """Validate SAML metadata if provided."""
        if v and values.get("protocol") == "saml":
            # Basic XML validation
            if not v.strip().startswith("<?xml") and not v.strip().startswith("<"):
                raise ValueError("Invalid XML format for SAML metadata")
        return v


class SSOProviderUpdate(BaseModel):
    """Request model for updating SSO provider configuration."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    enabled: Optional[bool] = None

    # SAML updates
    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    saml_certificate: Optional[str] = None
    saml_want_assertions_signed: Optional[bool] = None

    # OIDC updates
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_authorization_endpoint: Optional[str] = None
    oidc_token_endpoint: Optional[str] = None
    oidc_userinfo_endpoint: Optional[str] = None
    oidc_jwks_uri: Optional[str] = None


class SSOProviderResponse(BaseModel):
    """Response model for SSO provider."""

    id: str
    organization_id: str
    name: str
    protocol: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    # SAML fields (if protocol is SAML)
    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    saml_certificate_fingerprint: Optional[str] = None

    # OIDC fields (if protocol is OIDC)
    oidc_issuer: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_authorization_endpoint: Optional[str] = None
    oidc_token_endpoint: Optional[str] = None

    class Config:
        from_attributes = True


@router.post(
    "/providers",
    response_model=SSOProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SSO provider",
    description="Create a new SSO provider configuration",
)
async def create_sso_provider(
    provider: SSOProviderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create SSO provider configuration.

    For SAML providers, you can either:
    - Provide individual fields (entity_id, sso_url, certificate)
    - Upload metadata XML (will automatically parse and extract fields)

    For OIDC providers, you can either:
    - Provide individual endpoints
    - Provide discovery URL (will fetch endpoint configuration)
    """
    try:
        # Initialize managers
        cert_manager = CertificateManager()
        metadata_manager = MetadataManager(cert_manager)

        # Process based on protocol
        if provider.protocol == "saml":
            # If metadata XML provided, parse it
            if provider.saml_metadata_xml:
                parsed = metadata_manager.parse_idp_metadata(provider.saml_metadata_xml)

                # Use parsed values, overriding individual fields
                provider.saml_entity_id = parsed["entity_id"]
                provider.saml_sso_url = parsed["sso_url"]
                provider.saml_slo_url = parsed.get("slo_url")

                # Store first certificate if available
                if parsed.get("certificates"):
                    cert_data = parsed["certificates"][0]
                    cert_id = cert_manager.store_certificate(
                        current_user.organization_id, cert_data["pem"]
                    )
                    provider.saml_certificate = cert_id

            # Validate required SAML fields
            if not provider.saml_entity_id or not provider.saml_sso_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SAML provider requires entity_id and sso_url",
                )

        elif provider.protocol == "oidc":
            # If discovery URL provided, fetch configuration
            if provider.oidc_discovery_url:
                # TODO: Implement OIDC discovery
                # For now, require manual configuration
                pass

            # Validate required OIDC fields
            if not provider.oidc_client_id or not provider.oidc_authorization_endpoint:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OIDC provider requires client_id and authorization_endpoint",
                )

        # Create provider in database
        db_provider = SSOProvider(
            organization_id=current_user.organization_id,
            name=provider.name,
            protocol=SSOProtocol(provider.protocol),
            enabled=provider.enabled,
            config={
                # SAML config
                "saml_entity_id": provider.saml_entity_id,
                "saml_sso_url": provider.saml_sso_url,
                "saml_slo_url": provider.saml_slo_url,
                "saml_certificate_id": provider.saml_certificate,
                "saml_want_assertions_signed": provider.saml_want_assertions_signed,
                # OIDC config
                "oidc_issuer": provider.oidc_issuer,
                "oidc_client_id": provider.oidc_client_id,
                "oidc_client_secret": provider.oidc_client_secret,
                "oidc_authorization_endpoint": provider.oidc_authorization_endpoint,
                "oidc_token_endpoint": provider.oidc_token_endpoint,
                "oidc_userinfo_endpoint": provider.oidc_userinfo_endpoint,
                "oidc_jwks_uri": provider.oidc_jwks_uri,
            },
        )

        db.add(db_provider)
        db.commit()
        db.refresh(db_provider)

        return SSOProviderResponse.from_orm(db_provider)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create provider: {str(e)}",
        )


@router.get(
    "/providers",
    response_model=List[SSOProviderResponse],
    summary="List SSO providers",
    description="Get all SSO providers for organization",
)
async def list_sso_providers(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List all SSO providers for the current organization."""
    try:
        providers = (
            db.query(SSOProvider)
            .filter(SSOProvider.organization_id == current_user.organization_id)
            .all()
        )

        return [SSOProviderResponse.from_orm(p) for p in providers]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list providers: {str(e)}",
        )


@router.get(
    "/providers/{provider_id}",
    response_model=SSOProviderResponse,
    summary="Get SSO provider",
    description="Get specific SSO provider details",
)
async def get_sso_provider(
    provider_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get SSO provider by ID."""
    try:
        provider = (
            db.query(SSOProvider)
            .filter(
                SSOProvider.id == provider_id,
                SSOProvider.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        return SSOProviderResponse.from_orm(provider)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get provider: {str(e)}",
        )


@router.patch(
    "/providers/{provider_id}",
    response_model=SSOProviderResponse,
    summary="Update SSO provider",
    description="Update SSO provider configuration",
)
async def update_sso_provider(
    provider_id: str,
    update: SSOProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update SSO provider configuration."""
    try:
        provider = (
            db.query(SSOProvider)
            .filter(
                SSOProvider.id == provider_id,
                SSOProvider.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        # Update fields
        if update.name is not None:
            provider.name = update.name
        if update.enabled is not None:
            provider.enabled = update.enabled

        # Update config
        config = provider.config or {}

        if update.saml_entity_id is not None:
            config["saml_entity_id"] = update.saml_entity_id
        if update.saml_sso_url is not None:
            config["saml_sso_url"] = update.saml_sso_url
        if update.saml_slo_url is not None:
            config["saml_slo_url"] = update.saml_slo_url
        if update.saml_certificate is not None:
            config["saml_certificate_id"] = update.saml_certificate
        if update.saml_want_assertions_signed is not None:
            config["saml_want_assertions_signed"] = update.saml_want_assertions_signed

        if update.oidc_client_id is not None:
            config["oidc_client_id"] = update.oidc_client_id
        if update.oidc_client_secret is not None:
            config["oidc_client_secret"] = update.oidc_client_secret
        if update.oidc_authorization_endpoint is not None:
            config["oidc_authorization_endpoint"] = update.oidc_authorization_endpoint
        if update.oidc_token_endpoint is not None:
            config["oidc_token_endpoint"] = update.oidc_token_endpoint
        if update.oidc_userinfo_endpoint is not None:
            config["oidc_userinfo_endpoint"] = update.oidc_userinfo_endpoint
        if update.oidc_jwks_uri is not None:
            config["oidc_jwks_uri"] = update.oidc_jwks_uri

        provider.config = config

        db.commit()
        db.refresh(provider)

        return SSOProviderResponse.from_orm(provider)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider: {str(e)}",
        )


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete SSO provider",
    description="Delete SSO provider configuration",
)
async def delete_sso_provider(
    provider_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete SSO provider."""
    try:
        provider = (
            db.query(SSOProvider)
            .filter(
                SSOProvider.id == provider_id,
                SSOProvider.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        db.delete(provider)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete provider: {str(e)}",
        )
