"""
System Settings Models
Global platform configuration that can be managed via API and GUI.

These settings override environment variables and provide dynamic configuration
without requiring deployment changes.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Index, ForeignKey
from app.models.types import GUID as UUID, JSON as JSONB
from datetime import datetime
import uuid

from . import Base


class SystemSettingCategory:
    """Categories for system settings"""

    SECURITY = "security"
    CORS = "cors"
    AUTH = "auth"
    EMAIL = "email"
    FEATURES = "features"
    OIDC = "oidc"
    BRANDING = "branding"


class SystemSetting(Base):
    """
    System-wide configuration settings.

    These settings are loaded at runtime and can be changed via the admin API.
    They take precedence over environment variables when set.

    Examples:
        - CORS allowed origins
        - Custom OIDC issuer domain
        - Feature flags
        - Rate limiting configuration
    """

    __tablename__ = "system_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=True)  # String value for simple settings
    json_value = Column(JSONB, nullable=True)  # JSON value for complex settings
    category = Column(String(50), nullable=False, default=SystemSettingCategory.FEATURES)
    description = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False)  # Hide value in API responses
    is_readonly = Column(Boolean, default=False)  # Cannot be changed via API
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), nullable=True)  # User who last updated

    __table_args__ = (Index("ix_system_settings_category", "category"),)

    def get_value(self):
        """Get the setting value (prefer json_value if set)"""
        if self.json_value is not None:
            return self.json_value
        return self.value


class AllowedCorsOrigin(Base):
    """
    Allowed CORS origins for the API.

    Supports both system-level (organization_id=None) and tenant-level origins.
    System-level origins are managed by platform admins.
    Tenant-level origins are managed by organization admins for their white-label apps.

    This provides a normalized table for CORS origins, making it easier to
    manage and audit which domains can make cross-origin requests.
    """

    __tablename__ = "allowed_cors_origins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    origin = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)  # e.g., "Enclii Admin Dashboard"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_allowed_cors_origins_active", "is_active"),
        Index("ix_allowed_cors_origins_org", "organization_id"),
        # Unique constraint: origin must be unique per organization (or globally for system)
        Index("ix_allowed_cors_origins_unique", "origin", "organization_id", unique=True),
    )


# Pre-defined setting keys for type safety
class SettingKeys:
    """Known setting keys for type safety and documentation"""

    # CORS
    CORS_ADDITIONAL_ORIGINS = "cors.additional_origins"  # JSON array of additional origins
    CORS_ALLOW_CREDENTIALS = "cors.allow_credentials"
    CORS_MAX_AGE = "cors.max_age"

    # OIDC
    OIDC_CUSTOM_DOMAIN = "oidc.custom_domain"  # Custom issuer domain (e.g., auth.madfam.io)
    OIDC_JWT_ISSUER = "oidc.jwt_issuer"  # Override JWT issuer

    # Auth
    AUTH_SESSION_LIFETIME = "auth.session_lifetime_minutes"
    AUTH_REQUIRE_MFA = "auth.require_mfa"
    AUTH_ALLOW_SIGNUPS = "auth.allow_signups"

    # Features
    FEATURE_OAUTH_ENABLED = "features.oauth_enabled"
    FEATURE_MAGIC_LINKS_ENABLED = "features.magic_links_enabled"
    FEATURE_ORGANIZATIONS_ENABLED = "features.organizations_enabled"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = "rate_limit.per_minute"
    RATE_LIMIT_PER_HOUR = "rate_limit.per_hour"
