"""
Enterprise models for advanced features
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer, Enum as SQLEnum
from app.models.types import GUID as UUID, JSON as JSONB
from datetime import datetime
import uuid
import enum

from . import Base
# Import models from main models module for convenience


class SSOProvider(str, enum.Enum):
    """SSO provider types"""
    SAML = "saml"
    OIDC = "oidc"
    OAUTH2 = "oauth2"
    LDAP = "ldap"
    ACTIVE_DIRECTORY = "active_directory"


class SSOStatus(str, enum.Enum):
    """SSO configuration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"


class AuditEventType(str, enum.Enum):
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    POLICY_CREATED = "policy.created"
    POLICY_UPDATED = "policy.updated"
    POLICY_DELETED = "policy.deleted"
    SECURITY_ALERT = "security.alert"
    DATA_EXPORT = "data.export"
    SYSTEM_CONFIG_CHANGED = "system.config_changed"


class BillingPlan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class BillingInterval(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    TRIALING = "trialing"


class EnterpriseAuditLog(Base):
    __tablename__ = "enterprise_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_type = Column(SQLEnum(AuditEventType), nullable=False)
    resource_type = Column(String(255))
    resource_id = Column(String(255))
    event_data = Column(JSONB, default={})
    ip_address = Column(String(50))
    user_agent = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    plan = Column(SQLEnum(BillingPlan), nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), nullable=False)
    billing_interval = Column(SQLEnum(BillingInterval), nullable=False)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    trial_end = Column(DateTime)
    canceled_at = Column(DateTime)
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    subscription_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BillingUsage(Base):
    __tablename__ = "billing_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    metric_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=0)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EnterpriseFeature(Base):
    __tablename__ = "enterprise_features"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    feature_name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=False)
    configuration = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SSOConfiguration(Base):
    __tablename__ = "sso_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    provider = Column(String(255), nullable=False)  # "saml", "oidc", etc.
    enabled = Column(Boolean, default=False)
    configuration = Column(JSONB, default={})
    metadata_url = Column(String(500))
    certificate = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SCIMConfiguration(Base):
    """SCIM provisioning configuration for an organization"""
    __tablename__ = "scim_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True)
    provider = Column(String(50), default="custom")  # okta, azure_ad, onelogin, google_workspace, jumpcloud, ping_identity, custom
    enabled = Column(Boolean, default=False)
    base_url = Column(String(500))
    bearer_token = Column(String(500))
    configuration = Column(JSONB, default={})  # Provider-specific settings (attribute mappings, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceLog(Base):
    __tablename__ = "compliance_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    compliance_type = Column(String(255), nullable=False)  # "gdpr", "hipaa", "sox", etc.
    event_type = Column(String(255), nullable=False)
    resource_type = Column(String(255))
    resource_id = Column(String(255))
    details = Column(JSONB, default={})
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


# REMOVED: DataRetentionPolicy class (use the comprehensive version from app.models.compliance)
# Note: Import DataRetentionPolicy from app.models.compliance for data retention functionality


class SCIMResource(Base):
    __tablename__ = "scim_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    resource_type = Column(String(255), nullable=False)  # "User", "Group", etc.
    scim_id = Column(String(255), nullable=False)
    internal_id = Column(UUID(as_uuid=True))
    external_id = Column(String(255))  # ID from the IdP
    attributes = Column(JSONB, default={})
    raw_attributes = Column(JSONB, default={})  # Original SCIM payload
    sync_status = Column(String(50), default="pending")  # pending, synced, error
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SCIMSyncLog(Base):
    """Track SCIM sync operations for audit and debugging"""
    __tablename__ = "scim_sync_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    operation = Column(String(50), nullable=False)  # create, update, delete, patch
    resource_type = Column(String(50), nullable=False)  # User, Group
    scim_id = Column(String(255))
    internal_id = Column(UUID(as_uuid=True))
    status = Column(String(50), nullable=False)  # success, failed, partial
    request_payload = Column(JSONB, default={})
    response_payload = Column(JSONB, default={})
    error_message = Column(Text)
    error_code = Column(String(50))
    idp_request_id = Column(String(255))  # Request ID from IdP for correlation
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class SCIMProvider(str, enum.Enum):
    """Supported SCIM identity providers"""
    OKTA = "okta"
    AZURE_AD = "azure_ad"
    ONELOGIN = "onelogin"
    GOOGLE_WORKSPACE = "google_workspace"
    JUMPCLOUD = "jumpcloud"
    PING_IDENTITY = "ping_identity"
    CUSTOM = "custom"


class PermissionDefinition(Base):
    __tablename__ = "permission_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    resource_type = Column(String(255), nullable=False)
    actions = Column(JSONB, default=[])  # List of allowed actions
    conditions = Column(JSONB, default={})  # Conditional logic
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PermissionScope(str, enum.Enum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    USER = "user"
    RESOURCE = "resource"


class RoleType(str, enum.Enum):
    SYSTEM = "system"
    CUSTOM = "custom"


# For backward compatibility with existing code
# Note: Use the main AuditLog from __init__.py for general audit logging
# EnterpriseAuditLog is for enterprise-specific audit requirements