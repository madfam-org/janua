"""
White-label and branding API endpoints
"""

import hashlib
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
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


# Pydantic models
class BrandingConfigurationCreate(BaseModel):
    """Create branding configuration request"""

    branding_level: BrandingLevel = BrandingLevel.BASIC
    company_name: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_logo_dark_url: Optional[str] = None
    company_favicon_url: Optional[str] = None
    company_website: Optional[str] = None
    theme_mode: ThemeMode = ThemeMode.LIGHT
    primary_color: str = "#1a73e8"
    secondary_color: str = "#ea4335"
    accent_color: str = "#34a853"
    background_color: str = "#ffffff"
    surface_color: str = "#f8f9fa"
    text_color: str = "#202124"
    font_family: str = "Inter, system-ui, sans-serif"
    border_radius: str = "8px"
    custom_css: Optional[str] = None


class BrandingConfigurationUpdate(BaseModel):
    """Update branding configuration request"""

    is_enabled: Optional[bool] = None
    company_name: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_logo_dark_url: Optional[str] = None
    company_favicon_url: Optional[str] = None
    company_website: Optional[str] = None
    theme_mode: Optional[ThemeMode] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    surface_color: Optional[str] = None
    text_color: Optional[str] = None
    font_family: Optional[str] = None
    border_radius: Optional[str] = None
    custom_css: Optional[str] = None


class BrandingConfigurationResponse(BaseModel):
    """Branding configuration response"""

    id: str
    organization_id: str
    branding_level: BrandingLevel
    is_enabled: bool
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
    created_at: str
    updated_at: str


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


@router.post("/branding", response_model=BrandingConfigurationResponse)
async def create_branding_configuration(
    organization_id: str,
    config: BrandingConfigurationCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create branding configuration for organization

    Requires admin privileges.
    """
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

        return BrandingConfigurationResponse(
            id=str(branding_config.id),
            organization_id=str(branding_config.organization_id),
            branding_level=branding_config.branding_level,
            is_enabled=branding_config.is_enabled,
            company_name=branding_config.company_name,
            company_logo_url=branding_config.company_logo_url,
            company_logo_dark_url=branding_config.company_logo_dark_url,
            company_favicon_url=branding_config.company_favicon_url,
            company_website=branding_config.company_website,
            theme_mode=branding_config.theme_mode,
            primary_color=branding_config.primary_color,
            secondary_color=branding_config.secondary_color,
            accent_color=branding_config.accent_color,
            background_color=branding_config.background_color,
            surface_color=branding_config.surface_color,
            text_color=branding_config.text_color,
            font_family=branding_config.font_family,
            border_radius=branding_config.border_radius,
            created_at=branding_config.created_at.isoformat(),
            updated_at=branding_config.updated_at.isoformat(),
        )

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
    Get branding configuration for organization
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
            primary_color=config.primary_color,
            secondary_color=config.secondary_color,
            accent_color=config.accent_color,
            background_color=config.background_color,
            surface_color=config.surface_color,
            text_color=config.text_color,
            font_family=config.font_family,
            border_radius=config.border_radius,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )

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
    Update branding configuration

    Requires admin privileges.
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

        # Update fields
        update_data = update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await db.commit()

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
            primary_color=config.primary_color,
            secondary_color=config.secondary_color,
            accent_color=config.accent_color,
            background_color=config.background_color,
            surface_color=config.surface_color,
            text_color=config.text_color,
            font_family=config.font_family,
            border_radius=config.border_radius,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to update branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Logo Upload Endpoints
# =============================================================================

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/svg+xml"]
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
            detail="Invalid path component: must contain at least one alphanumeric character"
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
    content_hash = hashlib.md5(contents).hexdigest()[:12]
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
        logo_url = await _upload_branding_image(
            file, organization_id, "logo", MAX_LOGO_SIZE
        )

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
        logo_url = await _upload_branding_image(
            file, organization_id, "logo-dark", MAX_LOGO_SIZE
        )

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
        content_hash = hashlib.md5(contents).hexdigest()[:12]
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
        --primary-color: {config.primary_color};
        --secondary-color: {config.secondary_color};
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
