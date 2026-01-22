# Core models
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, relationship

from app.models.types import GUID as UUID
from app.models.types import JSON as JSONB
from app.models.types import InetAddress


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base class for all models."""

    pass


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    email_verified = Column(Boolean, default=False)
    password_hash = Column(String(255))
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE)
    first_name = Column(String(255))
    last_name = Column(String(255))
    username = Column(String(50), unique=True)
    phone = Column(String(50))
    phone_number = Column(String(20))  # Additional phone field
    avatar_url = Column(String(500))
    profile_image_url = Column(String(500))
    user_metadata = Column(JSONB, default={})
    tenant_id = Column(UUID(as_uuid=True), index=True)  # For multi-tenancy support
    last_login = Column(DateTime)
    last_sign_in_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # Admin flag for system-wide admin access

    # MFA fields
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    mfa_backup_codes = Column(JSONB, default=[])

    # Account lockout fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_failed_login = Column(DateTime, nullable=True)

    # Additional profile fields
    display_name = Column(String(200))
    bio = Column(Text)
    phone_verified = Column(Boolean, default=False)
    timezone = Column(String(50))
    locale = Column(String(10))
    email_verified_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    oauth_accounts = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )
    passkeys = relationship("Passkey", back_populates="user", cascade="all, delete-orphan")

    @property
    def name(self) -> str | None:
        """Return full name from first_name and last_name, or display_name, or None."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        elif self.display_name:
            return self.display_name
        return None


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    subscription_tier = Column(String(100), default="community")  # For tenant/organization billing
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # Organization owner
    billing_plan = Column(String(100), default="free")  # Billing plan
    billing_email = Column(String(255))  # Billing contact
    billing_customer_id = Column(String(255), index=True)  # External billing provider customer ID
    logo_url = Column(String(500))  # Organization logo
    description = Column(Text)  # Organization description
    settings = Column(JSONB, default={})  # Organization settings
    org_metadata = Column(JSONB, default={})  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(50), default="member")
    status = Column(
        String(50), default="active"
    )  # Member status: active, inactive, pending, removed
    joined_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class MagicLink(Base):
    __tablename__ = "magic_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    redirect_url = Column(String(500))
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(255), nullable=False)
    resource_type = Column(String(255))
    resource_id = Column(String(255))
    ip_address = Column(String(50))
    user_agent = Column(Text)
    activity_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(Text, unique=True, nullable=False)
    refresh_token = Column(Text, unique=True)
    access_token_jti = Column(String(255), unique=True)  # JWT token identifier
    refresh_token_jti = Column(String(255), unique=True)  # Refresh token identifier
    refresh_token_family = Column(String(255), index=True)  # Token family for rotation
    ip_address = Column(String(50))
    user_agent = Column(Text)
    device_name = Column(String(255))  # Device identification
    device_fingerprint = Column(String(255), index=True)  # Unique device fingerprint
    is_active = Column(Boolean, default=True)  # Session active status
    revoked = Column(Boolean, default=False)  # Whether session is revoked
    revoked_at = Column(DateTime)  # When session was revoked
    revoked_reason = Column(String(255))  # Reason for revocation
    is_trusted_device = Column(Boolean, default=False)  # If this session is from a trusted device
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrustedDevice(Base):
    """
    Represents a device that a user has explicitly trusted.

    Trusted devices:
    - Don't require MFA re-verification for a configured period
    - Can be managed by the user from their security settings
    - Trigger notifications when removed or when login from new device occurs
    """

    __tablename__ = "trusted_devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    device_fingerprint = Column(String(255), nullable=False, index=True)
    device_name = Column(String(255))  # User-friendly device name
    user_agent = Column(Text)  # Browser/app user agent
    ip_address = Column(String(50))  # Last known IP
    last_ip_address = Column(String(50))  # Most recent IP (may differ from initial)
    last_location = Column(String(255))  # Approximate location (city, country)
    trust_expires_at = Column(DateTime)  # When trust expires (None = permanent)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Composite unique constraint
    __table_args__ = (
        # Each device fingerprint should be unique per user
        {"sqlite_autoincrement": True},
    )


class UserConsent(Base):
    """
    Stores user consent for OAuth client access.

    When a user approves an OAuth authorization request, their consent
    is stored here to avoid asking for the same scopes again.
    """

    __tablename__ = "user_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(String(255), nullable=False, index=True)  # OAuth client ID
    scopes = Column(JSONB, nullable=False, default=[])  # List of approved scopes
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    revoked_at = Column(DateTime, nullable=True)  # When consent was revoked
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # Each user-client combination should have one consent record
        {"sqlite_autoincrement": True},
    )


class OAuthProvider(str, enum.Enum):
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    APPLE = "apple"
    DISCORD = "discord"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    SLACK = "slack"


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider = Column(SQLEnum(OAuthProvider), nullable=False)
    provider_user_id = Column(String(255), nullable=False)
    provider_email = Column(String(255))
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    provider_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="oauth_accounts")


class OAuthClient(Base):
    """
    OAuth2 Client registration for applications using Janua as an OAuth Provider.

    This enables external applications (like Enclii) to authenticate users via Janua's
    OAuth2/OIDC endpoints. Each client gets a client_id and client_secret for the
    OAuth2 authorization code flow.
    """

    __tablename__ = "oauth_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Client credentials
    client_id = Column(String(255), unique=True, nullable=False, index=True)
    client_secret_hash = Column(String(255), nullable=False)  # bcrypt hashed
    client_secret_prefix = Column(String(20), nullable=False)  # For display: jns_abc...

    # Configuration
    name = Column(String(255), nullable=False)
    description = Column(Text)
    redirect_uris = Column(JSONB, default=[])  # Array of allowed redirect URIs
    allowed_scopes = Column(JSONB, default=["openid", "profile", "email"])
    grant_types = Column(JSONB, default=["authorization_code", "refresh_token"])

    # Metadata
    logo_url = Column(String(500))
    website_url = Column(String(500))

    # Status & Activity
    is_active = Column(Boolean, default=True)
    is_confidential = Column(Boolean, default=True)  # True = requires secret
    last_used_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def verify_secret(self, plain_secret: str) -> bool:
        """
        Verify a plain-text client secret against the stored hash.

        Args:
            plain_secret: The plain-text secret to verify

        Returns:
            True if the secret matches, False otherwise
        """
        import bcrypt

        try:
            return bcrypt.checkpw(
                plain_secret.encode("utf-8"), self.client_secret_hash.encode("utf-8")
            )
        except Exception:
            return False


class OAuthClientSecret(Base):
    """
    Stores client secrets for OAuth clients, supporting graceful rotation.

    During rotation, multiple secrets can be active simultaneously for a grace period,
    allowing applications to update their configuration without downtime.
    """

    __tablename__ = "oauth_client_secrets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("oauth_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Secret data (hashed)
    secret_hash = Column(String(255), nullable=False)
    secret_prefix = Column(String(20), nullable=False)  # For display: jns_abc...

    # Lifecycle management
    is_primary = Column(Boolean, default=True)  # The main/current secret
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # When this secret becomes invalid
    revoked_at = Column(DateTime, nullable=True)  # Manual revocation timestamp
    last_used_at = Column(DateTime, nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    def is_valid(self) -> bool:
        """Check if this secret is still valid (not expired or revoked)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < datetime.utcnow():
            return False
        return True

    def verify(self, plain_secret: str) -> bool:
        """Verify a plain-text secret against this hash."""
        import bcrypt

        try:
            return bcrypt.checkpw(plain_secret.encode("utf-8"), self.secret_hash.encode("utf-8"))
        except Exception:
            return False


class Passkey(Base):
    __tablename__ = "passkeys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    credential_id = Column(String(500), unique=True, nullable=False)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0)
    name = Column(String(100))
    authenticator_attachment = Column(String(50))  # platform or cross-platform
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)

    # Relationship
    user = relationship("User", back_populates="passkeys")


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrganizationRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class OrganizationCustomRole(Base):
    __tablename__ = "organization_custom_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    permissions = Column(JSONB, default=[])
    parent_role_id = Column(
        UUID(as_uuid=True), ForeignKey("organization_custom_roles.id"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Association table reference - uses OrganizationMember model's table
# Access via OrganizationMember.__table__ if needed as a Table object
organization_members = OrganizationMember.__table__


class Policy(Base):
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    rules = Column(JSONB, default={})
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    url = Column(String(500), nullable=False)
    events = Column(JSONB, default=[])
    secret = Column(String(255))
    active = Column(Boolean, default=True)

    @property
    def is_active(self):
        return self.active

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create alias for backward compatibility
WebhookModel = Webhook


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    status = Column(String(50), default="pending")
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit log model matching the existing production database schema."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)  # Matches DB column
    resource_type = Column(String(100))
    resource_id = Column(UUID(as_uuid=True))
    details = Column(JSONB, default={})
    ip_address = Column(InetAddress)  # Cross-database IP address type
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# Webhook models
class WebhookEventType(str, enum.Enum):
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_SIGNED_IN = "user.signed_in"
    USER_SIGNED_OUT = "user.signed_out"
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    INVITATION_CREATED = "invitation.created"
    INVITATION_ACCEPTED = "invitation.accepted"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SYSTEM_ALERT = "system.alert"


class WebhookStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    url = Column(String(500), nullable=False)
    secret = Column(String(255))
    events = Column(JSONB, default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(255), nullable=False)
    data = Column(JSONB, default={})
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_endpoint_id = Column(
        UUID(as_uuid=True), ForeignKey("webhook_endpoints.id"), nullable=False
    )
    webhook_event_id = Column(UUID(as_uuid=True), ForeignKey("webhook_events.id"), nullable=False)
    status = Column(SQLEnum(WebhookStatus), default=WebhookStatus.PENDING)
    attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime)
    next_retry_at = Column(DateTime)
    response_status = Column(Integer)
    response_body = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# JWT Token models
class TokenClaims(Base):
    __tablename__ = "token_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    claims = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class TokenPair(Base):
    __tablename__ = "token_pairs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), unique=True, nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    price_id = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)  # "conekta" or "fungies"
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    session_metadata = Column(Text)  # JSON string for additional data


# Additional enterprise models
class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    permissions = Column(JSONB, default=[])
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    resource = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    conditions = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False)
    prefix = Column(String(20), nullable=False)
    scopes = Column(JSONB, default=[])
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"))
    invoice_number = Column(String(255), unique=True, nullable=False)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(3), default="USD")
    status = Column(String(50), default="pending")
    due_date = Column(DateTime, nullable=False)
    paid_at = Column(DateTime)
    stripe_invoice_id = Column(String(255), unique=True)
    invoice_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(3), default="USD")
    status = Column(String(50), default="pending")
    payment_method = Column(String(100))
    stripe_payment_id = Column(String(255), unique=True)
    processed_at = Column(DateTime)
    payment_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(100), default="info")
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Additional missing models
class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    settings_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SessionType(str, enum.Enum):
    WEB = "web"
    MOBILE = "mobile"
    API = "api"
    SSO = "sso"


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price_monthly = Column(Integer, default=0)  # Price in cents
    price_yearly = Column(Integer, default=0)  # Price in cents
    features = Column(JSONB, default=[])
    max_users = Column(Integer)
    max_organizations = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Localization models
class Locale(Base):
    __tablename__ = "locales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(10), unique=True, nullable=False, index=True)  # e.g., "en-US", "es-ES"
    name = Column(String(100), nullable=False)  # e.g., "English (US)"
    native_name = Column(String(100), nullable=False)  # e.g., "English (United States)"
    is_active = Column(Boolean, default=True)
    is_rtl = Column(Boolean, default=False)  # Right-to-left language
    translation_progress = Column(Integer, default=0)  # Percentage of translated keys
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TranslationKey(Base):
    __tablename__ = "translation_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), unique=True, nullable=False, index=True)  # e.g., "auth.login.submit"
    default_value = Column(Text, nullable=False)  # Fallback English text
    description = Column(Text)  # Context for translators
    category = Column(String(100))  # e.g., "auth", "dashboard", "settings"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Translation(Base):
    __tablename__ = "translations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    translation_key_id = Column(
        UUID(as_uuid=True), ForeignKey("translation_keys.id"), nullable=False
    )
    locale_id = Column(UUID(as_uuid=True), ForeignKey("locales.id"), nullable=False)
    value = Column(Text, nullable=False)  # Translated text
    is_approved = Column(Boolean, default=False)  # For translation workflow
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Import enterprise models
# Import compliance models

# Add relationships to User model
User.consent_records = relationship(
    "ConsentRecord", back_populates="user", foreign_keys="ConsentRecord.user_id"
)
User.data_subject_requests = relationship(
    "DataSubjectRequest", back_populates="user", foreign_keys="DataSubjectRequest.user_id"
)
User.privacy_settings = relationship(
    "PrivacySettings", back_populates="user", uselist=False, foreign_keys="PrivacySettings.user_id"
)

# Import system settings models
