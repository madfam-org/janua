"""
Database models for Plinto API
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Table, JSON, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum


Base = declarative_base()


class UserStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class SessionStatus(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class OrganizationRole(enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class OAuthProvider(enum.Enum):
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    APPLE = "apple"
    DISCORD = "discord"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"


class WebhookStatus(enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


# Association tables for many-to-many relationships
# organization_members table replaced by OrganizationMember model class


class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    email_verified = Column(Boolean, default=False)
    username = Column(String(50), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth-only users
    
    # Profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    display_name = Column(String(200), nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=True)
    phone_verified = Column(Boolean, default=False)
    timezone = Column(String(50), nullable=True)
    locale = Column(String(10), nullable=True)
    
    # Status and metadata
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE)
    user_metadata = Column(JSON, default=dict)
    
    # Security
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_backup_codes = Column(JSON, default=list)
    is_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_sign_in_at = Column(DateTime(timezone=True), nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    passkeys = relationship("Passkey", back_populates="user", cascade="all, delete-orphan")
    magic_links = relationship("MagicLink", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")
    webhook_endpoints = relationship("WebhookEndpoint", back_populates="user", cascade="all, delete-orphan")
    # organizations = relationship("Organization", secondary=organization_members, back_populates="members")
    organization_memberships = relationship("OrganizationMember", back_populates="user")
    owned_organizations = relationship("Organization", back_populates="owner")
    invitations_sent = relationship("OrganizationInvitation", foreign_keys="OrganizationInvitation.invited_by", back_populates="inviter")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Token data
    access_token_jti = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token_jti = Column(String(255), unique=True, nullable=False, index=True)
    
    # Session info
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_name = Column(String(100), nullable=True)
    
    # Status
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE)
    revoked = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class OAuthAccount(Base):
    __tablename__ = 'oauth_accounts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    provider = Column(SQLEnum(OAuthProvider), nullable=False)
    provider_user_id = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=True)
    
    # OAuth tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Provider data
    provider_data = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="oauth_accounts")
    
    # Unique constraint for provider + provider_user_id
    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='unique_provider_account'),
    )


class Passkey(Base):
    __tablename__ = 'passkeys'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # WebAuthn data
    credential_id = Column(String(500), unique=True, nullable=False)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0)
    
    # Device info
    name = Column(String(100), nullable=True)
    authenticator_attachment = Column(String(50), nullable=True)  # platform or cross-platform
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="passkeys")


class MagicLink(Base):
    __tablename__ = 'magic_links'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    token = Column(String(255), unique=True, nullable=False, index=True)
    redirect_url = Column(String(500), nullable=True)
    
    # Status
    used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="magic_links")


class PasswordReset(Base):
    __tablename__ = 'password_resets'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    token = Column(String(255), unique=True, nullable=False, index=True)
    
    # Status
    used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="password_resets")


class EmailVerification(Base):
    __tablename__ = 'email_verifications'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    token = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)  # Store the email being verified
    
    # Status
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="email_verifications")


class Organization(Base):
    __tablename__ = 'organizations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    
    # Owner
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Settings
    settings = Column(JSON, default=dict)
    org_metadata = Column(JSON, default=dict)
    
    # Billing
    billing_email = Column(String(255), nullable=True)
    billing_plan = Column(String(50), default="free")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="owned_organizations")
    members = relationship("OrganizationMember", back_populates="organization")
    invitations = relationship("OrganizationInvitation", back_populates="organization", cascade="all, delete-orphan")
    roles = relationship("OrganizationCustomRole", back_populates="organization", cascade="all, delete-orphan")
    webhook_endpoints = relationship("WebhookEndpoint", back_populates="organization", cascade="all, delete-orphan")


class OrganizationMember(Base):
    """Organization membership model for tracking user-organization relationships"""
    __tablename__ = 'organization_members'
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True)
    role = Column(SQLEnum(OrganizationRole), default=OrganizationRole.MEMBER)
    permissions = Column(JSON, default=list)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User")
    inviter = relationship("User", foreign_keys=[invited_by])


class OrganizationInvitation(Base):
    __tablename__ = 'organization_invitations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    
    email = Column(String(255), nullable=False)
    role = Column(SQLEnum(OrganizationRole), default=OrganizationRole.MEMBER)
    permissions = Column(JSON, default=list)
    
    token = Column(String(255), unique=True, nullable=False, index=True)
    
    # Who invited
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, accepted, expired
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="invitations")
    inviter = relationship("User", back_populates="invitations_sent")


class OrganizationCustomRole(Base):
    __tablename__ = 'organization_custom_roles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, default=list)
    
    # System roles cannot be deleted
    is_system = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="roles")


class ActivityLog(Base):
    __tablename__ = 'activity_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    action = Column(String(100), nullable=False)  # signin, signup, password_change, etc.
    details = Column(JSON, default=dict)
    
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="activity_logs")
    

class WebhookEndpoint(Base):
    """Webhook endpoint configuration"""
    __tablename__ = "webhook_endpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=False)
    events = Column(ARRAY(String), nullable=False)  # List of subscribed event types
    is_active = Column(Boolean, default=True)
    description = Column(String(500), nullable=True)
    headers = Column(JSON, nullable=True)  # Custom headers to include
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="webhook_endpoints")
    organization = relationship("Organization", back_populates="webhook_endpoints")
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")


class WebhookEvent(Base):
    """Webhook event record"""
    __tablename__ = "webhook_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(100), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="event", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    """Webhook delivery attempt record"""
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False)
    webhook_event_id = Column(UUID(as_uuid=True), ForeignKey("webhook_events.id", ondelete="CASCADE"), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    attempt = Column(Integer, default=1)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
    event = relationship("WebhookEvent", back_populates="deliveries")


# Backward compatibility alias for migration period
organization_members = OrganizationMember.__table__


# ==========================================
# SSO/SAML MODELS (moved from models/sso.py)
# ==========================================

class SSOProvider(enum.Enum):
    SAML = "saml"
    OIDC = "oidc"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"


class SSOStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"


class SSOConfiguration(Base):
    """Enterprise SSO configuration for organizations"""
    __tablename__ = 'sso_configurations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)

    # Provider configuration
    provider = Column(SQLEnum(SSOProvider), nullable=False)
    status = Column(SQLEnum(SSOStatus), default=SSOStatus.PENDING)
    enabled = Column(Boolean, default=False)

    # SAML configuration
    saml_metadata_url = Column(String(500), nullable=True)
    saml_metadata_xml = Column(Text, nullable=True)
    saml_sso_url = Column(String(500), nullable=True)
    saml_slo_url = Column(String(500), nullable=True)
    saml_certificate = Column(Text, nullable=True)
    saml_entity_id = Column(String(255), nullable=True)
    saml_acs_url = Column(String(500), nullable=True)

    # OIDC configuration
    oidc_issuer = Column(String(500), nullable=True)
    oidc_client_id = Column(String(255), nullable=True)
    oidc_client_secret = Column(Text, nullable=True)  # Encrypted
    oidc_discovery_url = Column(String(500), nullable=True)
    oidc_authorization_url = Column(String(500), nullable=True)
    oidc_token_url = Column(String(500), nullable=True)
    oidc_userinfo_url = Column(String(500), nullable=True)
    oidc_jwks_url = Column(String(500), nullable=True)
    oidc_scopes = Column(JSON, default=list)

    # Common settings
    jit_provisioning = Column(Boolean, default=True)
    default_role = Column(String(50), default='member')
    attribute_mapping = Column(JSON, default=dict)
    allowed_domains = Column(JSON, default=list)

    # Security settings
    sign_request = Column(Boolean, default=True)
    encrypt_assertion = Column(Boolean, default=False)
    force_authn = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="sso_configurations")
    sso_sessions = relationship("SSOSession", back_populates="sso_configuration", cascade="all, delete-orphan")


class SSOSession(Base):
    """SSO session tracking"""
    __tablename__ = 'sso_sessions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    sso_configuration_id = Column(UUID(as_uuid=True), ForeignKey('sso_configurations.id'), nullable=False)

    # Session data
    session_index = Column(String(255), nullable=True)  # SAML SessionIndex
    name_id = Column(String(255), nullable=True)  # SAML NameID
    idp_session_id = Column(String(255), nullable=True)

    # Metadata
    attributes = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sso_sessions")
    sso_configuration = relationship("SSOConfiguration", back_populates="sso_sessions")


class IDPMetadata(Base):
    """Identity Provider metadata cache"""
    __tablename__ = 'idp_metadata'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sso_configuration_id = Column(UUID(as_uuid=True), ForeignKey('sso_configurations.id'), nullable=False)

    # Metadata
    metadata_url = Column(String(500), nullable=True)
    metadata_xml = Column(Text, nullable=False)

    # Parsed values (cached)
    entity_id = Column(String(255), nullable=False)
    sso_url = Column(String(500), nullable=True)
    slo_url = Column(String(500), nullable=True)
    certificates = Column(JSON, default=list)

    # Validity
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    last_fetched = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    sso_configuration = relationship("SSOConfiguration")


# Token models for JWT authentication
class TokenClaims(Base):
    """JWT token claims model"""
    __tablename__ = "token_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    jti = Column(String(255), unique=True, nullable=False)  # JWT ID
    token_type = Column(String(50), nullable=False)  # access or refresh
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")


class TokenPair(Base):
    """Token pair for access and refresh tokens"""
    __tablename__ = "token_pairs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    access_token_jti = Column(String(255), nullable=False)
    refresh_token_jti = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")