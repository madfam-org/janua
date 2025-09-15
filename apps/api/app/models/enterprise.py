"""
Enterprise Database Models for Multi-Tenant Architecture
Comprehensive models for organizations, RBAC, SCIM, and audit
"""

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    ForeignKey, JSON, Enum as SQLEnum, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..models import Base


# Enums for Enterprise Features
class TenantStatus(enum.Enum):
    """Tenant/Organization status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"
    PENDING = "pending"


class RoleType(enum.Enum):
    """System and custom role types"""
    SYSTEM = "system"  # Built-in roles
    CUSTOM = "custom"  # Organization-created roles


class PermissionScope(enum.Enum):
    """Permission scope levels"""
    GLOBAL = "global"  # Platform-wide
    ORGANIZATION = "organization"  # Organization-wide
    PROJECT = "project"  # Project-specific
    RESOURCE = "resource"  # Resource-specific


class AuditEventType(enum.Enum):
    """Audit event categories"""
    AUTH = "authentication"
    ACCESS = "access"
    MODIFY = "modification"
    DELETE = "deletion"
    ADMIN = "administration"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class WebhookStatus(enum.Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


# Enhanced Organization Model with Multi-Tenancy
class Organization(Base):
    """Enhanced organization model with multi-tenant support"""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)

    # Basic Information
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(255), unique=True, nullable=True)

    # Billing & Subscription
    subscription_tier = Column(String(50), default="free")
    subscription_status = Column(SQLEnum(TenantStatus), default=TenantStatus.TRIAL)
    trial_ends_at = Column(DateTime(timezone=True))

    # Settings
    settings = Column(JSONB, default={})
    features = Column(JSONB, default={})  # Feature flags
    limits = Column(JSONB, default={})  # Usage limits

    # Security
    allowed_domains = Column(ARRAY(String), default=[])
    ip_allowlist = Column(ARRAY(String), default=[])
    mfa_required = Column(Boolean, default=False)
    sso_enabled = Column(Boolean, default=False)
    scim_enabled = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    # Relationships
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    roles = relationship("OrganizationRole", back_populates="organization", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="organization", cascade="all, delete-orphan")
    webhooks = relationship("WebhookEndpoint", back_populates="organization", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index("idx_org_tenant_id", "tenant_id"),
        Index("idx_org_slug", "slug"),
        Index("idx_org_domain", "domain"),
    )


# Organization Membership with RBAC
class OrganizationMember(Base):
    """Organization membership with role assignments"""
    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Role Assignment
    role_id = Column(UUID(as_uuid=True), ForeignKey("organization_roles.id"), nullable=False)
    custom_permissions = Column(ARRAY(String), default=[])  # Additional permissions

    # Member Status
    status = Column(String(50), default="active")
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    invited_at = Column(DateTime(timezone=True))
    joined_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("OrganizationRole")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        Index("idx_org_member_user", "user_id"),
        Index("idx_org_member_org", "organization_id"),
    )


# RBAC Role Model
class OrganizationRole(Base):
    """Organization roles with hierarchical permissions"""
    __tablename__ = "organization_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Role Information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    type = Column(SQLEnum(RoleType), default=RoleType.CUSTOM)

    # Hierarchical Structure
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey("organization_roles.id"), nullable=True)
    priority = Column(Integer, default=0)  # Higher priority = more permissions

    # Permissions
    permissions = Column(ARRAY(String), default=[])

    # Settings
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)  # Cannot be modified

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="roles")
    parent_role = relationship("OrganizationRole", remote_side=[id])

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_role_name"),
        Index("idx_org_role_org", "organization_id"),
    )


# Permission Definitions
class PermissionDefinition(Base):
    """System-wide permission definitions"""
    __tablename__ = "permission_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Permission Information
    code = Column(String(100), unique=True, nullable=False)  # e.g., "users:read"
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # Grouping for UI

    # Scope
    scope = Column(SQLEnum(PermissionScope), default=PermissionScope.ORGANIZATION)

    # Dependencies
    requires = Column(ARRAY(String), default=[])  # Other permissions required
    includes = Column(ARRAY(String), default=[])  # Permissions this includes

    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# SCIM Resources
class SCIMResource(Base):
    """SCIM 2.0 resource mapping"""
    __tablename__ = "scim_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # SCIM Information
    scim_id = Column(String(255), unique=True, nullable=False)  # External SCIM ID
    resource_type = Column(String(50), nullable=False)  # User, Group

    # Mapping
    internal_id = Column(UUID(as_uuid=True), nullable=False)  # User or Group ID

    # Sync Status
    last_synced_at = Column(DateTime(timezone=True))
    sync_status = Column(String(50), default="synced")

    # Raw Data
    raw_attributes = Column(JSONB)  # Original SCIM attributes

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Indexes
    __table_args__ = (
        UniqueConstraint("organization_id", "scim_id", name="uq_org_scim_id"),
        Index("idx_scim_resource_org", "organization_id"),
        Index("idx_scim_resource_type", "resource_type"),
    )


# Enhanced Audit Log with Hash Chain
class AuditLog(Base):
    """Tamper-proof audit log with hash chain"""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Actor Information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    service_account_id = Column(UUID(as_uuid=True), nullable=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)

    # Event Information
    event_type = Column(SQLEnum(AuditEventType), nullable=False)
    event_name = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(255))

    # Event Data
    event_data = Column(JSONB)
    changes = Column(JSONB)  # Before/after for modifications

    # Hash Chain for Tamper Detection
    previous_hash = Column(String(64))  # SHA-256 of previous entry
    current_hash = Column(String(64), nullable=False)  # SHA-256 of this entry

    # Compliance
    compliance_tags = Column(ARRAY(String), default=[])  # SOC2, HIPAA, etc.
    retention_until = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="audit_logs")
    user = relationship("User")

    # Indexes for querying
    __table_args__ = (
        Index("idx_audit_org_created", "organization_id", "created_at"),
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_compliance", "compliance_tags"),
    )


# Webhook Endpoints
class WebhookEndpoint(Base):
    """Webhook endpoint configuration"""
    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Endpoint Configuration
    url = Column(String(500), nullable=False)
    description = Column(Text)

    # Security
    secret = Column(String(255), nullable=False)  # For HMAC signature

    # Event Subscription
    events = Column(ARRAY(String), nullable=False)  # Event types to send

    # Configuration
    is_active = Column(Boolean, default=True)
    headers = Column(JSONB)  # Custom headers

    # Retry Configuration
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=60)  # Seconds

    # Statistics
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_success_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="webhooks")
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_webhook_org", "organization_id"),
        Index("idx_webhook_active", "is_active"),
    )


# Webhook Delivery Log
class WebhookDelivery(Base):
    """Webhook delivery tracking"""
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False)

    # Event Information
    event_type = Column(String(100), nullable=False)
    event_id = Column(UUID(as_uuid=True), nullable=False)

    # Delivery Information
    status = Column(SQLEnum(WebhookStatus), default=WebhookStatus.PENDING)
    attempts = Column(Integer, default=0)

    # Request/Response
    request_headers = Column(JSONB)
    request_body = Column(JSONB)
    response_status = Column(Integer)
    response_headers = Column(JSONB)
    response_body = Column(Text)

    # Timing
    scheduled_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    next_retry_at = Column(DateTime(timezone=True))

    # Error Information
    error_message = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")

    # Indexes
    __table_args__ = (
        Index("idx_delivery_endpoint", "endpoint_id"),
        Index("idx_delivery_status", "status"),
        Index("idx_delivery_scheduled", "scheduled_at"),
    )