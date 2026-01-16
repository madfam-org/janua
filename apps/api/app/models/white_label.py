"""
White Label Configuration Models
Supports multi-tenant customization and branding
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from app.models.types import GUID as UUID, JSON as JSONB
from datetime import datetime
import uuid

from . import Base
import enum


class BrandingLevel(str, enum.Enum):
    """White label branding levels"""
    BASIC = "basic"
    ADVANCED = "advanced"
    ENTERPRISE = "enterprise"


class ThemeMode(str, enum.Enum):
    """Theme mode options"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class CustomDomain(Base):
    """Custom domain configuration"""
    __tablename__ = "custom_domains"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    domain = Column(String(255), nullable=False, unique=True)
    verified = Column(Boolean, default=False)
    ssl_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailTemplate(Base):
    """Email template configuration"""
    __tablename__ = "email_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    template_type = Column(String(255), nullable=False)  # "welcome", "password_reset", etc.
    subject = Column(String(255), nullable=False)
    html_content = Column(Text)
    text_content = Column(Text)
    variables = Column(JSONB, default=[])  # Available template variables
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WhiteLabelConfiguration(Base):
    """White label configuration for organizations"""

    __tablename__ = "white_label_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True)

    # Branding
    brand_name = Column(String(255))
    logo_url = Column(String(500))
    favicon_url = Column(String(500))
    primary_color = Column(String(7))  # Hex color
    secondary_color = Column(String(7))

    # Custom domains
    custom_domain = Column(String(255), unique=True)
    custom_domain_verified = Column(Boolean, default=False)

    # Email customization
    email_from_name = Column(String(255))
    email_from_address = Column(String(255))
    email_footer_text = Column(Text)

    # UI customization
    custom_css = Column(Text)
    custom_javascript = Column(Text)
    hide_powered_by = Column(Boolean, default=False)

    # Feature toggles
    features = Column(JSONB, default={})

    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PageCustomization(Base):
    """Page customization for white-label branding"""
    __tablename__ = "page_customizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    page_type = Column(String(50), nullable=False)  # "login", "signup", "error", etc.
    title = Column(String(255))
    description = Column(Text)
    show_header = Column(Boolean, default=True)
    show_footer = Column(Boolean, default=True)
    hero_section = Column(JSONB, default={})
    content_blocks = Column(JSONB, default=[])
    custom_html = Column(Text)
    custom_css = Column(Text)
    custom_js = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ThemePreset(Base):
    """Theme preset templates for white-label customization"""
    __tablename__ = "theme_presets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # "modern", "classic", "minimal", etc.
    primary_color = Column(String(7))  # Hex color
    secondary_color = Column(String(7))
    accent_color = Column(String(7))
    background_color = Column(String(7))
    surface_color = Column(String(7))
    text_color = Column(String(7))
    font_family = Column(String(255))
    border_radius = Column(String(20))
    preview_url = Column(String(500))
    thumbnail_url = Column(String(500))
    times_used = Column(String(20), default="0")  # Counter as string for display
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Aliases for backward compatibility
WhiteLabel = WhiteLabelConfiguration
BrandingConfiguration = WhiteLabelConfiguration