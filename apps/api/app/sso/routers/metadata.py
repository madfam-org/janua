"""
SAML Metadata API Endpoints

Provides endpoints for:
- SP metadata generation and retrieval
- IdP metadata upload and parsing
- Metadata validation
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator

from app.dependencies import get_current_user
from app.models.user import User
from app.sso.domain.services.certificate_manager import CertificateManager
from app.sso.domain.services.metadata_manager import MetadataManager

router = APIRouter(prefix="/sso/metadata", tags=["SSO Metadata"])


class SPMetadataRequest(BaseModel):
    """Request model for SP metadata generation."""

    organization_name: Optional[str] = Field(None, description="Organization name")
    contact_email: Optional[str] = Field(None, description="Technical contact email")
    certificate_id: Optional[str] = Field(None, description="Certificate ID to use")
    want_assertions_signed: bool = Field(True, description="Require signed assertions")
    authn_requests_signed: bool = Field(True, description="Sign authentication requests")

    @validator("contact_email")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Invalid email address")
        return v


class IdPMetadataUpload(BaseModel):
    """Request model for IdP metadata upload."""

    metadata_xml: str = Field(..., description="SAML metadata XML")
    validate_certificates: bool = Field(True, description="Validate IdP certificates")

    @validator("metadata_xml")
    def validate_xml(cls, v):
        if not v.strip().startswith("<?xml") and not v.strip().startswith("<"):
            raise ValueError("Invalid XML format")
        return v


class MetadataResponse(BaseModel):
    """Response model for metadata operations."""

    entity_id: str
    metadata_xml: Optional[str] = None
    parsed_data: Optional[dict] = None
    validation: Optional[dict] = None


@router.post(
    "/sp/generate",
    response_model=MetadataResponse,
    summary="Generate SP metadata",
    description="Generate SAML Service Provider metadata XML",
)
async def generate_sp_metadata(
    request: SPMetadataRequest, current_user: User = Depends(get_current_user)
):
    """
    Generate SP metadata for SAML SSO configuration.

    This endpoint creates SAML metadata XML that should be provided to
    the Identity Provider (IdP) during SSO setup.
    """
    try:
        # Initialize managers
        cert_manager = CertificateManager()
        metadata_manager = MetadataManager(cert_manager)

        # Get certificate if ID provided
        certificate_pem = None
        if request.certificate_id:
            certificate_pem = cert_manager.load_certificate(
                current_user.organization_id, request.certificate_id
            )

        # Construct entity ID and URLs
        # In production, these would come from configuration
        base_url = "https://api.plinto.dev"  # TODO: Get from settings
        entity_id = f"{base_url}/sso/sp"
        acs_url = f"{base_url}/api/v1/sso/saml/acs"
        sls_url = f"{base_url}/api/v1/sso/saml/sls"

        # Generate metadata
        metadata_xml = metadata_manager.generate_sp_metadata(
            entity_id=entity_id,
            acs_url=acs_url,
            sls_url=sls_url,
            organization_name=request.organization_name,
            contact_email=request.contact_email,
            certificate_pem=certificate_pem,
            want_assertions_signed=request.want_assertions_signed,
            authn_requests_signed=request.authn_requests_signed,
        )

        return MetadataResponse(entity_id=entity_id, metadata_xml=metadata_xml)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate metadata: {str(e)}",
        )


@router.get(
    "/sp",
    response_model=str,
    summary="Get SP metadata",
    description="Retrieve SAML Service Provider metadata XML",
    responses={200: {"content": {"application/xml": {}}, "description": "SAML metadata XML"}},
)
async def get_sp_metadata(current_user: User = Depends(get_current_user)):
    """
    Get SP metadata XML.

    This endpoint returns the SAML metadata for this Service Provider.
    IdPs can use this URL to automatically fetch and configure SSO.
    """
    try:
        # Initialize managers
        metadata_manager = MetadataManager()

        # Construct entity ID and URLs
        base_url = "https://api.plinto.dev"  # TODO: Get from settings
        entity_id = f"{base_url}/sso/sp"
        acs_url = f"{base_url}/api/v1/sso/saml/acs"
        sls_url = f"{base_url}/api/v1/sso/saml/sls"

        # Generate metadata
        metadata_xml = metadata_manager.generate_sp_metadata(
            entity_id=entity_id, acs_url=acs_url, sls_url=sls_url
        )

        return metadata_xml

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metadata: {str(e)}",
        )


@router.post(
    "/idp/upload",
    response_model=MetadataResponse,
    summary="Upload IdP metadata",
    description="Parse and validate Identity Provider metadata",
)
async def upload_idp_metadata(
    upload: IdPMetadataUpload, current_user: User = Depends(get_current_user)
):
    """
    Upload and parse IdP metadata.

    This endpoint accepts SAML metadata XML from an Identity Provider,
    parses it, validates certificates, and extracts configuration.
    """
    try:
        # Initialize managers
        cert_manager = CertificateManager()
        metadata_manager = MetadataManager(cert_manager)

        # Validate metadata
        validation = metadata_manager.validate_metadata(upload.metadata_xml, metadata_type="idp")

        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid metadata", "errors": validation["errors"]},
            )

        # Parse metadata
        parsed_data = metadata_manager.parse_idp_metadata(upload.metadata_xml)

        # Store certificates if validation requested
        if upload.validate_certificates:
            for i, cert in enumerate(parsed_data.get("certificates", [])):
                if cert["validation"]["valid"]:
                    # Store certificate for future use
                    cert_id = f"idp_cert_{i}"
                    cert_manager.store_certificate(
                        current_user.organization_id, cert["pem"], cert_id
                    )

        return MetadataResponse(
            entity_id=parsed_data["entity_id"], parsed_data=parsed_data, validation=validation
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process metadata: {str(e)}",
        )


@router.post(
    "/validate",
    response_model=dict,
    summary="Validate metadata",
    description="Validate SAML metadata XML",
)
async def validate_metadata(
    metadata_xml: str, metadata_type: str = "idp", current_user: User = Depends(get_current_user)
):
    """
    Validate SAML metadata.

    Checks metadata structure, certificate validity, and compliance
    with SAML standards.
    """
    try:
        # Initialize managers
        cert_manager = CertificateManager()
        metadata_manager = MetadataManager(cert_manager)

        # Validate metadata
        validation = metadata_manager.validate_metadata(metadata_xml, metadata_type=metadata_type)

        return validation

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Validation failed: {str(e)}"
        )
