"""
White-label and branding API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
import uuid

from ...database import get_db
from ...auth import get_current_user, require_admin
from ...models import User, Organization
from ...models.white_label import (
    BrandingConfiguration, BrandingLevel, ThemeMode,
    CustomDomain, EmailTemplate, PageCustomization, ThemePreset
)

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
    domain: str = Field(..., pattern=r'^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9](?:\.[a-zA-Z]{2,})+$')
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
    db: AsyncSession = Depends(get_db)
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
                detail="Branding configuration already exists for this organization"
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
            custom_css=config.custom_css
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
            updated_at=branding_config.updated_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to create branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/branding/{organization_id}", response_model=BrandingConfigurationResponse)
async def get_branding_configuration(
    organization_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
            updated_at=config.updated_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/branding/{organization_id}", response_model=BrandingConfigurationResponse)
async def update_branding_configuration(
    organization_id: str,
    update: BrandingConfigurationUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
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
            updated_at=config.updated_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to update branding configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/domains", response_model=CustomDomainResponse)
async def create_custom_domain(
    branding_config_id: str,
    domain_request: CustomDomainCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
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
            cname_target=f"custom-{branding_config_id}.plinto.dev",  # Example CNAME target
            a_record_ips=["203.0.113.1", "203.0.113.2"],  # Example IPs
            txt_records=[f"plinto-verification={verification_token}"]
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
            updated_at=custom_domain.updated_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to create custom domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/domains/{domain_id}/verify")
async def verify_custom_domain(
    domain_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
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
            button_color=template.button_color
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
            updated_at=email_template.updated_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to create email template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/theme-presets", response_model=List[Dict[str, Any]])
async def list_theme_presets(
    category: Optional[str] = None,
    is_public: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
                "times_used": preset.times_used
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
    db: AsyncSession = Depends(get_db)
):
    """
    Get compiled CSS for organization's branding
    """
    try:
        result = await db.execute(
            select(BrandingConfiguration).where(
                BrandingConfiguration.organization_id == organization_id,
                BrandingConfiguration.is_enabled == True
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
            headers={"Cache-Control": "public, max-age=3600"}
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