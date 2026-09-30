"""
White-label and branding API endpoints
"""

import enum
import hashlib
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.white_label import (
    BrandingConfiguration,
    BrandingLevel,
    CustomDomain,
    EmailTemplate,
    ThemeMode,
    ThemePreset,
)

from ...models import Organization, User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/white-label",
    tags=["White Label"],
    responses={404: {"description": "Not found"}},
)


# Branding contract.
#
# The request and response field names below are the wire contract nauta reads
# and writes (nauta#331, packages/integrations/src/janua-branding.ts). They are
# NOT the column names of white_label_configurations: BRANDING_FIELD_COLUMNS is
# the one mapping between the two, and every branding handler goes through it.
# Before it existed the handlers used the API names as ORM attributes, so GET,
# PUT and POST /branding raised on every call and answered 500.

HEX_COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"

# What POST fills in for a field the caller leaves out, and what the compiled
# CSS falls back to for a column that is NULL. nauta reads a value equal to one
# of these as "not chosen" (JANUA_BRANDING_DEFAULTS), so change them together.
DEFAULT_THEME: Dict[str, str] = {
    "primary_color": "#1a73e8",
    "secondary_color": "#ea4335",
    "accent_color": "#34a853",
    "background_color": "#ffffff",
    "surface_color": "#f8f9fa",
    "text_color": "#202124",
    "font_family": "Inter, system-ui, sans-serif",
    "border_radius": "8px",
}

# API field -> white_label_configurations column.
BRANDING_FIELD_COLUMNS: Dict[str, str] = {
    "is_enabled": "is_active",
    "branding_level": "branding_level",
    "company_name": "brand_name",
    "company_logo_url": "logo_url",
    "company_logo_dark_url": "logo_dark_url",
    "company_favicon_url": "favicon_url",
    "company_website": "website_url",
    "theme_mode": "theme_mode",
    "primary_color": "primary_color",
    "secondary_color": "secondary_color",
    "accent_color": "accent_color",
    "background_color": "background_color",
    "surface_color": "surface_color",
    "text_color": "text_color",
    "font_family": "font_family",
    "border_radius": "border_radius",
    "custom_css": "custom_css",
}


# Field limits mirror the column widths, so an over-long value is a 422 here
# instead of a database error (a 500) at commit.
def _name() -> Any:
    return Field(None, max_length=255)


def _url() -> Any:
    return Field(None, max_length=500)


def _font(default: Optional[str]) -> Any:
    return Field(default, min_length=1, max_length=255)


def _radius(default: Optional[str]) -> Any:
    return Field(default, min_length=1, max_length=20)


def _color(default: Optional[str]) -> Any:
    return Field(default, pattern=HEX_COLOR_PATTERN)


class BrandingConfigurationCreate(BaseModel):
    """Create branding configuration request"""

    branding_level: BrandingLevel = BrandingLevel.BASIC
    company_name: Optional[str] = _name()
    company_logo_url: Optional[str] = _url()
    company_logo_dark_url: Optional[str] = _url()
    company_favicon_url: Optional[str] = _url()
    company_website: Optional[str] = _url()
    theme_mode: ThemeMode = ThemeMode.LIGHT
    primary_color: str = _color(DEFAULT_THEME["primary_color"])
    secondary_color: str = _color(DEFAULT_THEME["secondary_color"])
    accent_color: str = _color(DEFAULT_THEME["accent_color"])
    background_color: str = _color(DEFAULT_THEME["background_color"])
    surface_color: str = _color(DEFAULT_THEME["surface_color"])
    text_color: str = _color(DEFAULT_THEME["text_color"])
    font_family: str = _font(DEFAULT_THEME["font_family"])
    border_radius: str = _radius(DEFAULT_THEME["border_radius"])
    custom_css: Optional[str] = None


class BrandingConfigurationUpdate(BaseModel):
    """Update branding configuration request (partial: only the fields sent change).

    An explicit null clears a field; `is_enabled` cannot be null.
    """

    is_enabled: Optional[bool] = None
    company_name: Optional[str] = _name()
    company_logo_url: Optional[str] = _url()
    company_logo_dark_url: Optional[str] = _url()
    company_favicon_url: Optional[str] = _url()
    company_website: Optional[str] = _url()
    theme_mode: Optional[ThemeMode] = None
    primary_color: Optional[str] = _color(None)
    secondary_color: Optional[str] = _color(None)
    accent_color: Optional[str] = _color(None)
    background_color: Optional[str] = _color(None)
    surface_color: Optional[str] = _color(None)
    text_color: Optional[str] = _color(None)
    font_family: Optional[str] = _font(None)
    border_radius: Optional[str] = _radius(None)
    custom_css: Optional[str] = None

    @field_validator("is_enabled")
    @classmethod
    def _is_enabled_not_null(cls, value: Optional[bool]) -> bool:
        if value is None:
            raise ValueError("is_enabled must be true or false")
        return value


class BrandingConfigurationResponse(BaseModel):
    """Branding configuration response. A field with no stored value is null."""

    id: str
    organization_id: str
    branding_level: Optional[BrandingLevel]
    is_enabled: bool
    company_name: Optional[str]
    company_logo_url: Optional[str]
    company_logo_dark_url: Optional[str]
    company_favicon_url: Optional[str]
    company_website: Optional[str]
    theme_mode: Optional[ThemeMode]
    primary_color: Optional[str]
    secondary_color: Optional[str]
    accent_color: Optional[str]
    background_color: Optional[str]
    surface_color: Optional[str]
    text_color: Optional[str]
    font_family: Optional[str]
    border_radius: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


# Pydantic models (domains, email templates, pages)
class CustomDomainCreate(BaseModel):
    """Create custom domain request"""

    domain: str = Field(
        ..., pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9](?:\.[a-zA-Z]{2,})+$"
    )
    subdomain: Optional[str] = None


class CustomDomainResponse(BaseModel):
    """Custom domain response"""

    id: str
    domain: str
    subdomain: Optional[str]
    is_verified: bool
    is_active: bool
    dns_configured: bool
    ssl_configured: bool
    verification_token: Optional[str]
    cname_target: Optional[str]
    a_record_ips: List[str]
    txt_records: List[str]
    created_at: str
    updated_at: str


class EmailTemplateCreate(BaseModel):
    """Create email template request"""

    template_type: str = Field(..., max_length=50)
    locale: str = "en"
    subject: str = Field(..., max_length=500)
    html_body: str
    text_body: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    header_image_url: Optional[str] = None
    footer_text: Optional[str] = None
    button_color: Optional[str] = None


class EmailTemplateResponse(BaseModel):
    """Email template response"""

    id: str
    template_type: str
    locale: str
    subject: str
    html_body: str
    text_body: Optional[str]
    is_active: bool
    from_name: Optional[str]
    from_email: Optional[str]
    created_at: str
    updated_at: str


class PageCustomizationCreate(BaseModel):
    """Create page customization request"""

    page_type: str = Field(..., max_length=50)
    title: Optional[str] = None
    description: Optional[str] = None
    show_header: bool = True
    show_footer: bool = True
    hero_section: Optional[Dict[str, Any]] = None
    content_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    custom_html: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None


BRANDING_NOT_FOUND = "Branding configuration not found"


def _org_uuid(organization_id: str, not_found: str) -> uuid.UUID:
    """The organization id as a UUID. A malformed id matches nothing: 404."""
    try:
        return uuid.UUID(str(organization_id))
    except ValueError:
        raise HTTPException(status_code=404, detail=not_found)


def _column_value(value: Any) -> Any:
    """Enums are stored as their string value."""
    return value.value if isinstance(value, enum.Enum) else value


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _branding_response(config: BrandingConfiguration) -> BrandingConfigurationResponse:
    """The API view of a white_label_configurations row, via BRANDING_FIELD_COLUMNS."""
    values = {
        field: getattr(config, column)
        for field, column in BRANDING_FIELD_COLUMNS.items()
        if field in BrandingConfigurationResponse.model_fields
    }
    # A row inserted outside this API may hold NULL; the CSS endpoint treats
    # that as disabled, and so does the answer here.
    values["is_enabled"] = bool(values["is_enabled"])
    return BrandingConfigurationResponse(
        id=str(config.id),
        organization_id=str(config.organization_id),
        created_at=_isoformat(config.created_at),
        updated_at=_isoformat(config.updated_at),
        **values,
    )


async def _get_branding(db: AsyncSession, organization_id: str) -> BrandingConfiguration:
    """The organization's branding row, or 404."""
    org_id = _org_uuid(organization_id, BRANDING_NOT_FOUND)
    result = await db.execute(
        select(BrandingConfiguration).where(BrandingConfiguration.organization_id == org_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=BRANDING_NOT_FOUND)
    return config


BRANDING_EXISTS = "Branding configuration already exists for this organization"


@router.post("/branding", response_model=BrandingConfigurationResponse)
async def create_branding_configuration(
    organization_id: str,
    config: BrandingConfigurationCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create branding configuration for organization

    Requires admin privileges. 404 when the organization does not exist, 400
    when it already has a branding configuration (use PUT to change it).
    """
    try:
        org_id = _org_uuid(organization_id, "Organization not found")
        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        existing = await db.execute(
            select(BrandingConfiguration).where(BrandingConfiguration.organization_id == org_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=BRANDING_EXISTS)

        branding_config = BrandingConfiguration(
            organization_id=org_id,
            is_active=True,
            **{
                BRANDING_FIELD_COLUMNS[field]: _column_value(value)
                for field, value in config.model_dump().items()
            },
        )
        db.add(branding_config)
        try:
            await db.commit()
        except IntegrityError:
            # A concurrent create won the unique(organization_id) race.
            await db.rollback()
            raise HTTPException(status_code=400, detail=BRANDING_EXISTS)
        await db.refresh(branding_config)

        return _branding_response(branding_config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/branding/{organization_id}", response_model=BrandingConfigurationResponse)
async def get_branding_configuration(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get branding configuration for organization. 404 when it has none.
    """
    try:
        return _branding_response(await _get_branding(db, organization_id))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/branding/{organization_id}", response_model=BrandingConfigurationResponse)
async def update_branding_configuration(
    organization_id: str,
    update: BrandingConfigurationUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Update branding configuration. Partial: only the fields sent change.

    Requires admin privileges. 404 when the organization has no branding
    configuration (create it with POST first).
    """
    try:
        config = await _get_branding(db, organization_id)

        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(config, BRANDING_FIELD_COLUMNS[field], _column_value(value))
        config.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(config)

        return _branding_response(config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Logo Upload Endpoints
# =============================================================================

ALLOWED_IMAGE_TYPES = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
]
MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5MB
MAX_FAVICON_SIZE = 1 * 1024 * 1024  # 1MB


def _safe_delete_uploaded_file(url_path: Optional[str]) -> bool:
    """
    Safely delete an uploaded file with path traversal protection.

    Security: Prevents path traversal (CWE-22) by validating the resolved
    path is within the upload directory before deletion.

    Args:
        url_path: The URL path of the uploaded file (e.g., "/uploads/branding/...")

    Returns:
        True if file was deleted, False otherwise
    """
    if not url_path or not url_path.startswith("/uploads/"):
        return False

    try:
        # Remove the /uploads/ prefix to get relative path
        relative_path = url_path.replace("/uploads/", "", 1)

        # Resolve both base and target paths
        base_dir = Path(settings.UPLOAD_DIR).resolve()
        target_path = (base_dir / relative_path).resolve()

        # CRITICAL: Verify path is within base directory (prevents path traversal)
        target_path.relative_to(base_dir)

        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            return True
        return False
    except (ValueError, OSError) as e:
        logger.warning(f"Failed to delete uploaded file: {e}")
        return False


def _sanitize_path_component(component: str) -> str:
    """
    Sanitize a string for safe use in file paths.

    Security: Prevents path traversal (CWE-22) by using regex substitution
    to remove all characters except alphanumeric, hyphens, and underscores.

    Args:
        component: Path component to sanitize (e.g., organization_id)

    Returns:
        A new sanitized string containing only safe characters

    Raises:
        HTTPException: If the sanitized result is empty
    """
    if not component:
        raise HTTPException(status_code=400, detail="Invalid path component: empty value")

    # Use regex to remove all non-safe characters
    # Pattern: replace anything that is NOT alphanumeric, hyphen, or underscore with empty string
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", component)

    if not sanitized:
        raise HTTPException(
            status_code=400,
            detail="Invalid path component: must contain at least one alphanumeric character",
        )

    return sanitized


async def _upload_branding_image(
    file: UploadFile,
    organization_id: str,
    image_type: str,
    max_size: int,
) -> str:
    """
    Helper to upload branding images (logos, favicons).

    Args:
        file: The uploaded file
        organization_id: Organization ID for the image
        image_type: Type of image (logo, logo-dark, favicon)
        max_size: Maximum file size in bytes

    Returns:
        URL path to the uploaded image
    """
    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    # Read and validate file size
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_size // (1024 * 1024)}MB",
        )

    # Validate organization_id to prevent path traversal
    safe_org_id = _sanitize_path_component(organization_id)

    # Generate unique filename
    file_extension = file.filename.split(".")[-1] if file.filename else "png"
    content_hash = hashlib.sha256(contents).hexdigest()[:12]
    unique_filename = f"{safe_org_id}_{image_type}_{content_hash}.{file_extension}"

    # Create upload directory using pathlib for safety
    base_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir = (base_dir / "branding" / safe_org_id).resolve()

    # Verify path is within base directory (defense in depth)
    try:
        upload_dir.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization path")

    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = upload_dir / unique_filename
    with open(file_path, "wb") as f:
        f.write(contents)

    # Return URL path
    return f"/uploads/branding/{safe_org_id}/{unique_filename}"


@router.post("/branding/{organization_id}/logo")
async def upload_logo(
    organization_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload primary logo for organization branding.

    Accepts: JPEG, PNG, GIF, WebP, SVG
    Max size: 5MB

    Recommended dimensions: 200x50px or similar aspect ratio
    """
    try:
        config = await _get_branding(db, organization_id)

        # Delete old logo if exists (using safe deletion to prevent path traversal)
        _safe_delete_uploaded_file(config.logo_url)

        # Upload new logo
        logo_url = await _upload_branding_image(file, organization_id, "logo", MAX_LOGO_SIZE)

        # Update branding configuration
        config.logo_url = logo_url
        config.updated_at = datetime.utcnow()
        await db.commit()

        return {
            "message": "Logo uploaded successfully",
            "company_logo_url": logo_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload logo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/branding/{organization_id}/logo-dark")
async def upload_logo_dark(
    organization_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload dark mode logo for organization branding.

    Accepts: JPEG, PNG, GIF, WebP, SVG
    Max size: 5MB

    Use this for logos that display well on dark backgrounds.
    """
    try:
        config = await _get_branding(db, organization_id)

        # Delete old logo if exists (using safe deletion to prevent path traversal)
        _safe_delete_uploaded_file(config.logo_dark_url)

        # Upload new logo
        logo_url = await _upload_branding_image(file, organization_id, "logo-dark", MAX_LOGO_SIZE)

        # Update branding configuration
        config.logo_dark_url = logo_url
        config.updated_at = datetime.utcnow()
        await db.commit()

        return {
            "message": "Dark mode logo uploaded successfully",
            "company_logo_dark_url": logo_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload dark mode logo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/branding/{organization_id}/favicon")
async def upload_favicon(
    organization_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload favicon for organization branding.

    Accepts: JPEG, PNG, GIF, WebP, SVG, ICO
    Max size: 1MB

    Recommended: 32x32px or 16x16px PNG/ICO
    """
    try:
        config = await _get_branding(db, organization_id)

        # Delete old favicon if exists (using safe deletion to prevent path traversal)
        _safe_delete_uploaded_file(config.favicon_url)

        # Upload new favicon (allow ICO files too)
        allowed_types = ALLOWED_IMAGE_TYPES + ["image/x-icon", "image/vnd.microsoft.icon"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
            )

        # Read and validate file size
        contents = await file.read()
        if len(contents) > MAX_FAVICON_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FAVICON_SIZE // (1024 * 1024)}MB",
            )

        # Validate organization_id to prevent path traversal
        safe_org_id = _sanitize_path_component(organization_id)

        # Generate unique filename
        file_extension = file.filename.split(".")[-1] if file.filename else "png"
        content_hash = hashlib.sha256(contents).hexdigest()[:12]
        unique_filename = f"{safe_org_id}_favicon_{content_hash}.{file_extension}"

        # Create upload directory using pathlib for safety
        base_dir = Path(settings.UPLOAD_DIR).resolve()
        upload_dir = (base_dir / "branding" / safe_org_id).resolve()

        # Verify path is within base directory (defense in depth)
        try:
            upload_dir.relative_to(base_dir)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization path")

        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = upload_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(contents)

        favicon_url = f"/uploads/branding/{safe_org_id}/{unique_filename}"

        # Update branding configuration
        config.favicon_url = favicon_url
        config.updated_at = datetime.utcnow()
        await db.commit()

        return {
            "message": "Favicon uploaded successfully",
            "company_favicon_url": favicon_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload favicon: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/branding/{organization_id}/logo")
async def delete_logo(
    organization_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete the primary logo for organization branding.
    """
    try:
        config = await _get_branding(db, organization_id)

        # Delete logo file if exists (using safe deletion to prevent path traversal)
        if config.logo_url:
            _safe_delete_uploaded_file(config.logo_url)
            config.logo_url = None
            config.updated_at = datetime.utcnow()
            await db.commit()

        return {"message": "Logo deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete logo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/branding/{organization_id}/logo-dark")
async def delete_logo_dark(
    organization_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete the dark mode logo for organization branding.
    """
    try:
        config = await _get_branding(db, organization_id)

        # Delete logo file if exists (using safe deletion to prevent path traversal)
        if config.logo_dark_url:
            _safe_delete_uploaded_file(config.logo_dark_url)
            config.logo_dark_url = None
            config.updated_at = datetime.utcnow()
            await db.commit()

        return {"message": "Dark mode logo deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dark mode logo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/branding/{organization_id}/favicon")
async def delete_favicon(
    organization_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete the favicon for organization branding.
    """
    try:
        config = await _get_branding(db, organization_id)

        # Delete favicon file if exists (using safe deletion to prevent path traversal)
        if config.favicon_url:
            _safe_delete_uploaded_file(config.favicon_url)
            config.favicon_url = None
            config.updated_at = datetime.utcnow()
            await db.commit()

        return {"message": "Favicon deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete favicon: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/domains", response_model=CustomDomainResponse)
async def create_custom_domain(
    branding_config_id: str,
    domain_request: CustomDomainCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create custom domain configuration

    Requires admin privileges.
    """
    try:
        # Check if branding config exists
        branding_config = await db.get(BrandingConfiguration, branding_config_id)
        if not branding_config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Check if domain already exists
        existing = await db.execute(
            select(CustomDomain).where(CustomDomain.domain == domain_request.domain)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Domain already exists")

        # Generate verification token
        verification_token = str(uuid.uuid4())

        # Create custom domain
        custom_domain = CustomDomain(
            branding_configuration_id=branding_config_id,
            domain=domain_request.domain,
            subdomain=domain_request.subdomain,
            verification_token=verification_token,
            cname_target=f"custom-{branding_config_id}.janua.dev",  # Example CNAME target
            a_record_ips=["203.0.113.1", "203.0.113.2"],  # Example IPs
            txt_records=[f"janua-verification={verification_token}"],
        )

        db.add(custom_domain)
        await db.commit()

        return CustomDomainResponse(
            id=str(custom_domain.id),
            domain=custom_domain.domain,
            subdomain=custom_domain.subdomain,
            is_verified=custom_domain.is_verified,
            is_active=custom_domain.is_active,
            dns_configured=custom_domain.dns_configured,
            ssl_configured=custom_domain.ssl_configured,
            verification_token=custom_domain.verification_token,
            cname_target=custom_domain.cname_target,
            a_record_ips=custom_domain.a_record_ips,
            txt_records=custom_domain.txt_records,
            created_at=custom_domain.created_at.isoformat(),
            updated_at=custom_domain.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create custom domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/domains/{domain_id}/verify")
async def verify_custom_domain(
    domain_id: str, current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    """
    Verify custom domain DNS configuration

    Requires admin privileges.
    """
    try:
        custom_domain = await db.get(CustomDomain, domain_id)
        if not custom_domain:
            raise HTTPException(status_code=404, detail="Custom domain not found")

        # In production, implement actual DNS verification
        # For now, simulate verification
        custom_domain.is_verified = True
        custom_domain.dns_configured = True
        custom_domain.verified_at = datetime.utcnow()

        await db.commit()

        return {"message": "Domain verified successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify custom domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email-templates", response_model=EmailTemplateResponse)
async def create_email_template(
    branding_config_id: str,
    template: EmailTemplateCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create custom email template

    Requires admin privileges.
    """
    try:
        # Check if branding config exists
        branding_config = await db.get(BrandingConfiguration, branding_config_id)
        if not branding_config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Create email template
        email_template = EmailTemplate(
            branding_configuration_id=branding_config_id,
            template_type=template.template_type,
            locale=template.locale,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            from_name=template.from_name,
            from_email=template.from_email,
            header_image_url=template.header_image_url,
            footer_text=template.footer_text,
            button_color=template.button_color,
        )

        db.add(email_template)
        await db.commit()

        return EmailTemplateResponse(
            id=str(email_template.id),
            template_type=email_template.template_type,
            locale=email_template.locale,
            subject=email_template.subject,
            html_body=email_template.html_body,
            text_body=email_template.text_body,
            is_active=email_template.is_active,
            from_name=email_template.from_name,
            from_email=email_template.from_email,
            created_at=email_template.created_at.isoformat(),
            updated_at=email_template.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create email template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/theme-presets", response_model=List[Dict[str, Any]])
async def list_theme_presets(
    category: Optional[str] = None,
    is_public: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List available theme presets
    """
    try:
        query = select(ThemePreset).where(ThemePreset.is_public == is_public)

        if category:
            query = query.where(ThemePreset.category == category)

        result = await db.execute(query)
        presets = result.scalars().all()

        return [
            {
                "id": str(preset.id),
                "name": preset.name,
                "description": preset.description,
                "category": preset.category,
                "primary_color": preset.primary_color,
                "secondary_color": preset.secondary_color,
                "accent_color": preset.accent_color,
                "background_color": preset.background_color,
                "font_family": preset.font_family,
                "border_radius": preset.border_radius,
                "preview_url": preset.preview_url,
                "thumbnail_url": preset.thumbnail_url,
                "times_used": preset.times_used,
            }
            for preset in presets
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list theme presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/css/{organization_id}")
async def get_organization_css(
    organization_id: str,
    theme_mode: Optional[ThemeMode] = ThemeMode.LIGHT,
    db: AsyncSession = Depends(get_db),
):
    """
    Get compiled CSS for organization's branding
    """
    try:
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id,
                BrandingConfiguration.is_active.is_(True),
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            # Return default CSS
            css_content = _generate_default_css()
        else:
            # Generate CSS from branding configuration
            css_content = _generate_organization_css(config, theme_mode)

        return Response(
            content=css_content,
            media_type="text/css",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get organization CSS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_default_css() -> str:
    """Generate default CSS"""
    return """
    :root {
        --primary-color: #1a73e8;
        --secondary-color: #ea4335;
        --accent-color: #34a853;
        --background-color: #ffffff;
        --surface-color: #f8f9fa;
        --text-color: #202124;
        --border-radius: 8px;
        --font-family: Inter, system-ui, sans-serif;
    }
    
    body {
        font-family: var(--font-family);
        color: var(--text-color);
        background-color: var(--background-color);
    }
    
    .btn-primary {
        background-color: var(--primary-color);
        border-radius: var(--border-radius);
    }
    """


def _generate_organization_css(config: BrandingConfiguration, theme_mode: ThemeMode) -> str:
    """Generate CSS from branding configuration"""
    # A column never set (NULL) falls back to the default theme value.
    theme = {key: getattr(config, key) or default for key, default in DEFAULT_THEME.items()}
    css_vars = f"""
    :root {{
        --primary-color: {theme["primary_color"]};
        --secondary-color: {theme["secondary_color"]};
        --accent-color: {theme["accent_color"]};
        --background-color: {theme["background_color"]};
        --surface-color: {theme["surface_color"]};
        --text-color: {theme["text_color"]};
        --border-radius: {theme["border_radius"]};
        --font-family: {theme["font_family"]};
    }}
    
    body {{
        font-family: var(--font-family);
        color: var(--text-color);
        background-color: var(--background-color);
    }}
    
    .btn-primary {{
        background-color: var(--primary-color);
        border-radius: var(--border-radius);
    }}
    
    .btn-secondary {{
        background-color: var(--secondary-color);
        border-radius: var(--border-radius);
    }}
    """

    # Add custom CSS if provided
    if config.custom_css:
        css_vars += f"\n\n{config.custom_css}"

    return css_vars
