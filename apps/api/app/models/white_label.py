"""
White Label Configuration Models
Supports multi-tenant customization and branding
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import synonym

from app.models.types import GUID as UUID
from app.models.types import JSON as JSONB

from . import Base


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
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True
    )

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

    # ── The branding API's names (routers/v1/white_label.py) ────────────────
    #
    # The white-label router was written against attributes this table never
    # had (`company_name`, `accent_color`, `is_enabled`, …), so every create
    # answered 500 ("'branding_level' is an invalid keyword argument") and no
    # organization's branding could be written or read through the API.
    #
    # Where a column already holds the value, the API name is a SYNONYM for it
    # (usable in queries too: `BrandingConfiguration.is_enabled == True`).
    # The style tokens with no column live under `features["branding"]`, one
    # key per API name, so no DDL is needed and a later migration can move
    # them into real columns one to one.
    company_name = synonym("brand_name")
    company_logo_url = synonym("logo_url")
    company_favicon_url = synonym("favicon_url")
    is_enabled = synonym("is_active")

    def _branding_token(self, key, default=None):
        return ((self.features or {}).get("branding") or {}).get(key, default)

    def _set_branding_token(self, key, value) -> None:
        # Reassign rather than mutate: a plain JSON column only notices a
        # new object, and an in-place edit would be silently dropped.
        features = dict(self.features or {})
        branding = dict(features.get("branding") or {})
        if value is None:
            branding.pop(key, None)
        else:
            branding[key] = value.value if isinstance(value, enum.Enum) else value
        features["branding"] = branding
        self.features = features

    def _token(key, default=None, kind=None):  # noqa: N805 — class-body helper
        def getter(self):
            value = self._branding_token(key, default)
            return kind(value) if kind is not None and value is not None else value

        def setter(self, value):
            self._set_branding_token(key, value)

        return property(getter, setter)

    branding_level = _token("branding_level", BrandingLevel.BASIC.value, BrandingLevel)
    theme_mode = _token("theme_mode", ThemeMode.LIGHT.value, ThemeMode)
    company_logo_dark_url = _token("company_logo_dark_url")
    company_website = _token("company_website")
    accent_color = _token("accent_color", "#34a853")
    background_color = _token("background_color", "#ffffff")
    surface_color = _token("surface_color", "#f8f9fa")
    text_color = _token("text_color", "#202124")
    font_family = _token("font_family", "Inter, system-ui, sans-serif")
    border_radius = _token("border_radius", "8px")
    del _token


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
