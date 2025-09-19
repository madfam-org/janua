"""
Enterprise models for advanced features
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from . import Base
# Import models from main models module for convenience
from . import Organization, OrganizationMember, OrganizationRole, WebhookEndpoint, WebhookDelivery, WebhookStatus, AuditLog


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
    __tablename__ = "scim_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    enabled = Column(Boolean, default=False)
    base_url = Column(String(500))
    bearer_token = Column(String(500))
    configuration = Column(JSONB, default={})
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
    attributes = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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