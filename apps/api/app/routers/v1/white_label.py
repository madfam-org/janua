"""
White-label and branding API endpoints
"""

import hashlib
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
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
from app.services.branding_service_auth import (
    BrandingActor,
    branding_reader,
    branding_writer,
    refuse_service_custom_css,
)

from ...models import Organization, User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/white-label",
    tags=["White Label"],
    responses={404: {"description": "Not found"}},
)


# Style tokens reach a public stylesheet (`/white-label/css/{org}`) verbatim,
# and the color columns are VARCHAR(7): anything but a hex color would either
# inject CSS or fail the write with a 500. So they are validated here.
_HEX = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"
_FONT = r"^[A-Za-z0-9 ,'\"_-]{1,160}$"
_RADIUS = r"^[0-9]{1,3}(?:\.[0-9]{1,2})?(?:px|rem|em|%)$"


# Pydantic models
class BrandingConfigurationCreate(BaseModel):
    """Create branding configuration request"""

    branding_level: BrandingLevel = BrandingLevel.BASIC
    company_name: Optional[str] = Field(None, max_length=255)
    company_logo_url: Optional[str] = Field(None, max_length=500)
    company_logo_dark_url: Optional[str] = Field(None, max_length=500)
    company_favicon_url: Optional[str] = Field(None, max_length=500)
    company_website: Optional[str] = Field(None, max_length=500)
    theme_mode: ThemeMode = ThemeMode.LIGHT
    primary_color: str = Field("#1a73e8", pattern=_HEX)
    secondary_color: str = Field("#ea4335", pattern=_HEX)
    accent_color: str = Field("#34a853", pattern=_HEX)
    background_color: str = Field("#ffffff", pattern=_HEX)
    surface_color: str = Field("#f8f9fa", pattern=_HEX)
    text_color: str = Field("#202124", pattern=_HEX)
    font_family: str = Field("Inter, system-ui, sans-serif", pattern=_FONT)
    border_radius: str = Field("8px", pattern=_RADIUS)
    custom_css: Optional[str] = None


class BrandingConfigurationUpdate(BaseModel):
    """Update branding configuration request"""

    is_enabled: Optional[bool] = None
    company_name: Optional[str] = Field(None, max_length=255)
    company_logo_url: Optional[str] = Field(None, max_length=500)
    company_logo_dark_url: Optional[str] = Field(None, max_length=500)
    company_favicon_url: Optional[str] = Field(None, max_length=500)
    company_website: Optional[str] = Field(None, max_length=500)
    theme_mode: Optional[ThemeMode] = None
    primary_color: Optional[str] = Field(None, pattern=_HEX)
    secondary_color: Optional[str] = Field(None, pattern=_HEX)
    accent_color: Optional[str] = Field(None, pattern=_HEX)
    background_color: Optional[str] = Field(None, pattern=_HEX)
    surface_color: Optional[str] = Field(None, pattern=_HEX)
    text_color: Optional[str] = Field(None, pattern=_HEX)
    font_family: Optional[str] = Field(None, pattern=_FONT)
    border_radius: Optional[str] = Field(None, pattern=_RADIUS)
    custom_css: Optional[str] = None


class BrandingConfigurationResponse(BaseModel):
    """Branding configuration response"""

    id: str
    organization_id: str
    branding_level: BrandingLevel
    # NULL on rows written outside this API; reported as stored, not guessed.
    is_enabled: Optional[bool]
    company_name: Optional[str]
    company_logo_url: Optional[str]
    company_logo_dark_url: Optional[str]
    company_favicon_url: Optional[str]
    company_website: Optional[str]
    theme_mode: ThemeMode
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str
    surface_color: str
    text_color: str
    font_family: str
    border_radius: str
    created_at: Optional[str]
    updated_at: Optional[str]


# Janua's defaults for the two colour COLUMNS. The style tokens under
# `features["branding"]` fall back to the same values in the model; these two
# are columns, nullable since 000_init (as are `is_active` and the timestamps),
# so a row written outside this API may hold NULL. Reading such a row must
# answer 200, not a validation 500.
DEFAULT_PRIMARY_COLOR = "#1a73e8"
DEFAULT_SECONDARY_COLOR = "#ea4335"


def _branding_response(config: BrandingConfiguration) -> BrandingConfigurationResponse:
    return BrandingConfigurationResponse(
        id=str(config.id),
        organization_id=str(config.organization_id),
        branding_level=config.branding_level,
        is_enabled=config.is_enabled,
        company_name=config.company_name,
        company_logo_url=config.company_logo_url,
        company_logo_dark_url=config.company_logo_dark_url,
        company_favicon_url=config.company_favicon_url,
        company_website=config.company_website,
        theme_mode=config.theme_mode,
        primary_color=config.primary_color or DEFAULT_PRIMARY_COLOR,
        secondary_color=config.secondary_color or DEFAULT_SECONDARY_COLOR,
        accent_color=config.accent_color,
        background_color=config.background_color,
        surface_color=config.surface_color,
        text_color=config.text_color,
        font_family=config.font_family,
        border_radius=config.border_radius,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


# A DNS host name: dot-separated labels of letters, digits and inner hyphens,
# ending in an alphabetic top-level label. 253 is the DNS limit.
_HOSTNAME = r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"


class CustomDomainCreate(BaseModel):
    """Create custom domain request.

    Only what `custom_domains` stores is accepted; any other field is a 422
    naming it, never silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(..., max_length=253, pattern=_HOSTNAME)


class CustomDomainResponse(BaseModel):
    """Custom domain response, as stored."""

    id: str
    organization_id: str
    domain: str
    is_verified: bool
    status: Literal["pending", "verified"]
    ssl_configured: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class EmailTemplateCreate(BaseModel):
    """Create email template request.

    Only what `email_templates` stores is accepted; any other field is a 422
    naming it, never silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    template_type: str = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=1, max_length=255)
    html_body: str = Field(..., min_length=1)
    text_body: Optional[str] = None


class EmailTemplateResponse(BaseModel):
    """Email template response, as stored."""

    id: str
    organization_id: str
    template_type: str
    subject: str
    html_body: Optional[str]
    text_body: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


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


@router.post("/branding", response_model=BrandingConfigurationResponse)
async def create_branding_configuration(
    organization_id: str,
    config: BrandingConfigurationCreate,
    actor: BrandingActor = Depends(branding_writer),
    db: AsyncSession = Depends(get_db),
):
    """
    Create branding configuration for organization

    Requires admin privileges, or the organization's own branding service
    client (see app/services/branding_service_auth.py).
    """
    refuse_service_custom_css(actor, config)
    try:
        # Check if organization exists
        org = await db.get(Organization, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Check if branding config already exists
        existing = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Branding configuration already exists for this organization",
            )

        # Create branding configuration
        branding_config = BrandingConfiguration(
            organization_id=organization_id,
            branding_level=config.branding_level,
            company_name=config.company_name,
            company_logo_url=config.company_logo_url,
            company_logo_dark_url=config.company_logo_dark_url,
            company_favicon_url=config.company_favicon_url,
            company_website=config.company_website,
            theme_mode=config.theme_mode,
            primary_color=config.primary_color,
            secondary_color=config.secondary_color,
            accent_color=config.accent_color,
            background_color=config.background_color,
            surface_color=config.surface_color,
            text_color=config.text_color,
            font_family=config.font_family,
            border_radius=config.border_radius,
            custom_css=config.custom_css,
        )

        db.add(branding_config)
        await db.commit()

        return _branding_response(branding_config)

    except HTTPException:
        # 404/400 are answers, not failures: without this they became 500s.
        raise
    except Exception as e:
        logger.error(f"Failed to create branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/branding/{organization_id}", response_model=BrandingConfigurationResponse)
async def get_branding_configuration(
    organization_id: str,
    actor: BrandingActor = Depends(branding_reader),
    db: AsyncSession = Depends(get_db),
):
    """
    Get branding configuration for organization

    Any signed-in user, or the organization's own branding service client.
    """
    try:
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        return _branding_response(config)

    except HTTPException:
        # 404/400 are answers, not failures: without this they became 500s.
        raise
    except Exception as e:
        logger.error(f"Failed to get branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/branding/{organization_id}", response_model=BrandingConfigurationResponse)
async def update_branding_configuration(
    organization_id: str,
    update: BrandingConfigurationUpdate,
    actor: BrandingActor = Depends(branding_writer),
    db: AsyncSession = Depends(get_db),
):
    """
    Update branding configuration

    Requires admin privileges, or the organization's own branding service
    client (see app/services/branding_service_auth.py).
    """
    refuse_service_custom_css(actor, update)
    try:
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Update fields
        update_data = update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await db.commit()

        return _branding_response(config)

    except HTTPException:
        # 404/400 are answers, not failures: without this they became 500s.
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
        # Get branding configuration
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Delete old logo if exists (using safe deletion to prevent path traversal)
        _safe_delete_uploaded_file(config.company_logo_url)

        # Upload new logo
        logo_url = await _upload_branding_image(file, organization_id, "logo", MAX_LOGO_SIZE)

        # Update branding configuration
        config.company_logo_url = logo_url
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
        # Get branding configuration
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Delete old logo if exists (using safe deletion to prevent path traversal)
        _safe_delete_uploaded_file(config.company_logo_dark_url)

        # Upload new logo
        logo_url = await _upload_branding_image(file, organization_id, "logo-dark", MAX_LOGO_SIZE)

        # Update branding configuration
        config.company_logo_dark_url = logo_url
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
        # Get branding configuration
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Delete old favicon if exists (using safe deletion to prevent path traversal)
        _safe_delete_uploaded_file(config.company_favicon_url)

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
        config.company_favicon_url = favicon_url
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
        # Get branding configuration
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Delete logo file if exists (using safe deletion to prevent path traversal)
        if config.company_logo_url:
            _safe_delete_uploaded_file(config.company_logo_url)
            config.company_logo_url = None
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
        # Get branding configuration
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Delete logo file if exists (using safe deletion to prevent path traversal)
        if config.company_logo_dark_url:
            _safe_delete_uploaded_file(config.company_logo_dark_url)
            config.company_logo_dark_url = None
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
        # Get branding configuration
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Branding configuration not found")

        # Delete favicon file if exists (using safe deletion to prevent path traversal)
        if config.company_favicon_url:
            _safe_delete_uploaded_file(config.company_favicon_url)
            config.company_favicon_url = None
            config.updated_at = datetime.utcnow()
            await db.commit()

        return {"message": "Favicon deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete favicon: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Custom domains and email templates
#
# Both tables belong to an organization (`organization_id`); the routes are
# addressed by the organization's branding configuration and store its
# organization. Platform admins only, as before.
# =============================================================================


def _refusal(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _parse_id(value: str, code: str, message: str) -> uuid.UUID:
    # A malformed id cannot name a row: it is the same answer as a missing one,
    # not a database error.
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise _refusal(404, code, message) from None


async def _branding_config_or_404(
    db: AsyncSession, branding_config_id: str
) -> BrandingConfiguration:
    code, message = "branding_configuration_not_found", "Branding configuration not found"
    config = await db.get(BrandingConfiguration, _parse_id(branding_config_id, code, message))
    if not config:
        raise _refusal(404, code, message)
    return config


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _domain_response(domain: CustomDomain) -> CustomDomainResponse:
    verified = bool(domain.verified)
    return CustomDomainResponse(
        id=str(domain.id),
        organization_id=str(domain.organization_id),
        domain=domain.domain,
        is_verified=verified,
        status="verified" if verified else "pending",
        ssl_configured=bool(domain.ssl_enabled),
        created_at=_iso(domain.created_at),
        updated_at=_iso(domain.updated_at),
    )


def _template_response(template: EmailTemplate) -> EmailTemplateResponse:
    return EmailTemplateResponse(
        id=str(template.id),
        organization_id=str(template.organization_id),
        template_type=template.template_type,
        subject=template.subject,
        html_body=template.html_content,
        text_body=template.text_content,
        is_active=template.is_active is not False,
        created_at=_iso(template.created_at),
        updated_at=_iso(template.updated_at),
    )


_DOMAIN_EXISTS = ("custom_domain_exists", "This domain is already registered")


@router.post("/domains", response_model=CustomDomainResponse)
async def create_custom_domain(
    branding_config_id: str,
    domain_request: CustomDomainCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CustomDomainResponse:
    """
    Register a custom domain for the branding configuration's organization.

    The domain starts unverified. Host names are stored lower-case, and each
    one is registered once across all organizations.

    Requires admin privileges.
    """
    try:
        branding_config = await _branding_config_or_404(db, branding_config_id)
        hostname = domain_request.domain.lower()

        existing = await db.execute(
            select(CustomDomain.id).where(func.lower(CustomDomain.domain) == hostname)
        )
        if existing.first() is not None:
            raise _refusal(409, *_DOMAIN_EXISTS)

        custom_domain = CustomDomain(
            organization_id=branding_config.organization_id,
            domain=hostname,
            verified=False,
            ssl_enabled=False,
        )
        db.add(custom_domain)
        try:
            await db.commit()
        except IntegrityError:
            # Registered concurrently: the unique column decided it.
            await db.rollback()
            raise _refusal(409, *_DOMAIN_EXISTS) from None

        return _domain_response(custom_domain)

    except HTTPException:
        # 404/409 are answers, not failures.
        raise
    except Exception:
        logger.exception("Failed to create custom domain")
        await db.rollback()
        raise _refusal(500, "custom_domain_create_failed", "The domain could not be stored")


@router.post("/domains/{domain_id}/verify", response_model=CustomDomainResponse)
async def verify_custom_domain(
    domain_id: str, current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> CustomDomainResponse:
    """
    Mark a custom domain as verified, and return it as stored.

    This records a platform admin's confirmation that the domain's DNS points
    at Janua; Janua does not look the records up itself. Verifying a verified
    domain returns it unchanged.

    Requires admin privileges.
    """
    try:
        code, message = "custom_domain_not_found", "Custom domain not found"
        custom_domain = await db.get(CustomDomain, _parse_id(domain_id, code, message))
        if not custom_domain:
            raise _refusal(404, code, message)

        if not custom_domain.verified:
            custom_domain.verified = True
            await db.commit()

        return _domain_response(custom_domain)

    except HTTPException:
        # 404 is an answer, not a failure.
        raise
    except Exception:
        logger.exception("Failed to verify custom domain")
        await db.rollback()
        raise _refusal(500, "custom_domain_verify_failed", "The domain could not be updated")


@router.post("/email-templates", response_model=EmailTemplateResponse)
async def create_email_template(
    branding_config_id: str,
    template: EmailTemplateCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """
    Create an email template for the branding configuration's organization.

    One template per type and organization.

    Requires admin privileges.
    """
    try:
        branding_config = await _branding_config_or_404(db, branding_config_id)

        existing = await db.execute(
            select(EmailTemplate.id).where(
                EmailTemplate.organization_id == branding_config.organization_id,
                EmailTemplate.template_type == template.template_type,
            )
        )
        if existing.first() is not None:
            raise _refusal(
                409,
                "email_template_exists",
                "An email template of this type already exists for this organization",
            )

        email_template = EmailTemplate(
            organization_id=branding_config.organization_id,
            template_type=template.template_type,
            subject=template.subject,
            html_content=template.html_body,
            text_content=template.text_body,
            is_active=True,
        )
        db.add(email_template)
        await db.commit()

        return _template_response(email_template)

    except HTTPException:
        # 404/409 are answers, not failures.
        raise
    except Exception:
        logger.exception("Failed to create email template")
        await db.rollback()
        raise _refusal(500, "email_template_create_failed", "The template could not be stored")


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
        # 404/400 are answers, not failures: without this they became 500s.
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
                BrandingConfiguration.is_enabled == True,
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
        # 404/400 are answers, not failures: without this they became 500s.
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
    css_vars = f"""
    :root {{
        --primary-color: {config.primary_color or DEFAULT_PRIMARY_COLOR};
        --secondary-color: {config.secondary_color or DEFAULT_SECONDARY_COLOR};
        --accent-color: {config.accent_color};
        --background-color: {config.background_color};
        --surface-color: {config.surface_color};
        --text-color: {config.text_color};
        --border-radius: {config.border_radius};
        --font-family: {config.font_family};
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
