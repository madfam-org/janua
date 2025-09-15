"""
White-label and branding models for customization
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from app.models import Base


class ThemeMode(enum.Enum):
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class BrandingLevel(enum.Enum):
    BASIC = "basic"  # Logo and colors only
    STANDARD = "standard"  # Logo, colors, fonts, basic customization
    ADVANCED = "advanced"  # Full theming control
    ENTERPRISE = "enterprise"  # Custom domain, email templates, full control


class BrandingConfiguration(Base):
    """White-label branding configuration for organizations"""
    __tablename__ = 'branding_configurations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False, unique=True)
    
    # Branding level
    branding_level = Column(SQLEnum(BrandingLevel), default=BrandingLevel.BASIC)
    is_enabled = Column(Boolean, default=True)
    
    # Company identity
    company_name = Column(String(200), nullable=True)
    company_logo_url = Column(String(500), nullable=True)
    company_logo_dark_url = Column(String(500), nullable=True)  # Dark mode logo
    company_favicon_url = Column(String(500), nullable=True)
    company_website = Column(String(500), nullable=True)
    
    # Theme configuration
    theme_mode = Column(SQLEnum(ThemeMode), default=ThemeMode.LIGHT)
    primary_color = Column(String(7), default="#1a73e8")  # Hex color
    secondary_color = Column(String(7), default="#ea4335")
    accent_color = Column(String(7), default="#34a853")
    background_color = Column(String(7), default="#ffffff")
    surface_color = Column(String(7), default="#f8f9fa")
    text_color = Column(String(7), default="#202124")
    error_color = Column(String(7), default="#d93025")
    warning_color = Column(String(7), default="#fbbc04")
    success_color = Column(String(7), default="#34a853")
    info_color = Column(String(7), default="#1a73e8")
    
    # Typography
    font_family = Column(String(200), default="Inter, system-ui, sans-serif")
    heading_font_family = Column(String(200), nullable=True)
    font_size_base = Column(String(10), default="16px")
    font_weight_normal = Column(String(10), default="400")
    font_weight_bold = Column(String(10), default="600")
    
    # Layout customization
    border_radius = Column(String(10), default="8px")
    button_radius = Column(String(10), default="6px")
    card_radius = Column(String(10), default="12px")
    spacing_unit = Column(String(10), default="8px")
    
    # Advanced theming (JSON for flexibility)
    custom_css = Column(Text, nullable=True)  # Custom CSS overrides
    theme_variables = Column(JSON, default=dict)  # CSS variables
    component_styles = Column(JSON, default=dict)  # Component-specific styles
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    custom_domain = relationship("CustomDomain", back_populates="branding_configuration", uselist=False)
    email_templates = relationship("EmailTemplate", back_populates="branding_configuration")
    page_customizations = relationship("PageCustomization", back_populates="branding_configuration")


class CustomDomain(Base):
    """Custom domain configuration for white-label"""
    __tablename__ = 'custom_domains'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branding_configuration_id = Column(UUID(as_uuid=True), ForeignKey('branding_configurations.id'), nullable=False)
    
    # Domain configuration
    domain = Column(String(255), unique=True, nullable=False, index=True)
    subdomain = Column(String(100), nullable=True)  # For subdomain setup
    
    # SSL/TLS
    ssl_enabled = Column(Boolean, default=True)
    ssl_certificate = Column(Text, nullable=True)  # SSL certificate
    ssl_private_key = Column(Text, nullable=True)  # Encrypted private key
    ssl_ca_bundle = Column(Text, nullable=True)  # CA bundle
    ssl_auto_renew = Column(Boolean, default=True)  # Auto-renew with Let's Encrypt
    
    # DNS verification
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    verification_method = Column(String(50), default="dns")  # dns, http
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=False)
    dns_configured = Column(Boolean, default=False)
    ssl_configured = Column(Boolean, default=False)
    
    # Configuration
    cname_target = Column(String(255), nullable=True)  # CNAME target for DNS
    a_record_ips = Column(JSON, default=list)  # A record IPs
    txt_records = Column(JSON, default=list)  # TXT records for verification
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    branding_configuration = relationship("BrandingConfiguration", back_populates="custom_domain")


class EmailTemplate(Base):
    """Customizable email templates"""
    __tablename__ = 'email_templates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branding_configuration_id = Column(UUID(as_uuid=True), ForeignKey('branding_configurations.id'), nullable=False)
    
    # Template identification
    template_type = Column(String(50), nullable=False)  # welcome, reset_password, verify_email, etc.
    locale = Column(String(10), default="en")  # Language locale
    
    # Template content
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)  # Plain text version
    
    # Template variables (for documentation)
    available_variables = Column(JSON, default=dict)
    """
    Example variables:
    {
        "user_name": "User's display name",
        "company_name": "Organization name",
        "action_url": "Call-to-action URL",
        "support_email": "Support email address"
    }
    """
    
    # Settings
    is_active = Column(Boolean, default=True)
    from_name = Column(String(100), nullable=True)
    from_email = Column(String(255), nullable=True)
    reply_to = Column(String(255), nullable=True)
    
    # Design settings
    header_image_url = Column(String(500), nullable=True)
    footer_text = Column(Text, nullable=True)
    button_color = Column(String(7), nullable=True)
    button_text_color = Column(String(7), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    branding_configuration = relationship("BrandingConfiguration", back_populates="email_templates")


class PageCustomization(Base):
    """Custom page content and layouts"""
    __tablename__ = 'page_customizations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branding_configuration_id = Column(UUID(as_uuid=True), ForeignKey('branding_configurations.id'), nullable=False)
    
    # Page identification
    page_type = Column(String(50), nullable=False)  # login, signup, dashboard, etc.
    page_path = Column(String(255), nullable=True)  # Custom path if applicable
    
    # Content customization
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    meta_tags = Column(JSON, default=dict)  # SEO meta tags
    
    # Layout customization
    layout_template = Column(String(50), default="default")  # Template to use
    show_header = Column(Boolean, default=True)
    show_footer = Column(Boolean, default=True)
    show_sidebar = Column(Boolean, default=False)
    
    # Content blocks (JSON for flexibility)
    hero_section = Column(JSON, nullable=True)
    """
    Example hero section:
    {
        "title": "Welcome Back",
        "subtitle": "Sign in to continue",
        "background_image": "url",
        "background_color": "#1a73e8"
    }
    """
    
    content_blocks = Column(JSON, default=list)
    """
    Example content blocks:
    [
        {
            "type": "text",
            "content": "Lorem ipsum...",
            "alignment": "center"
        },
        {
            "type": "image",
            "src": "url",
            "alt": "Description"
        }
    ]
    """
    
    # Custom HTML/CSS/JS
    custom_html = Column(Text, nullable=True)
    custom_css = Column(Text, nullable=True)
    custom_js = Column(Text, nullable=True)
    
    # Settings
    is_active = Column(Boolean, default=True)
    requires_auth = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    branding_configuration = relationship("BrandingConfiguration", back_populates="page_customizations")


class ThemePreset(Base):
    """Pre-built theme presets"""
    __tablename__ = 'theme_presets'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Preset details
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # professional, playful, minimal, etc.
    
    # Theme configuration (same as BrandingConfiguration)
    primary_color = Column(String(7), nullable=False)
    secondary_color = Column(String(7), nullable=False)
    accent_color = Column(String(7), nullable=False)
    background_color = Column(String(7), nullable=False)
    surface_color = Column(String(7), nullable=False)
    text_color = Column(String(7), nullable=False)
    error_color = Column(String(7), nullable=False)
    warning_color = Column(String(7), nullable=False)
    success_color = Column(String(7), nullable=False)
    info_color = Column(String(7), nullable=False)
    
    # Typography
    font_family = Column(String(200), nullable=False)
    heading_font_family = Column(String(200), nullable=True)
    
    # Layout
    border_radius = Column(String(10), nullable=False)
    button_radius = Column(String(10), nullable=False)
    card_radius = Column(String(10), nullable=False)
    
    # Preview
    preview_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Usage
    is_public = Column(Boolean, default=True)
    times_used = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())