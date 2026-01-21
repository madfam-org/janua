"""
Policy and RBAC models with Pydantic schemas.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import enum

# Re-export SQLAlchemy models from __init__.py
from . import Policy as PolicyModel, Role as RoleModel

# Additional SQLAlchemy models for Policy system
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from app.models.types import GUID as UUID, JSON as JSONB
from . import Base
import uuid


class PolicyEffect(str, enum.Enum):
    """Policy effect enumeration."""
    ALLOW = "allow"
    DENY = "deny"


class PolicyTargetType(str, enum.Enum):
    """Policy target type enumeration."""
    USER = "user"
    ROLE = "role"
    ORGANIZATION = "organization"
    GLOBAL = "global"


class UserRole(Base):
    """User-Role assignment table."""
    __tablename__ = "user_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    scope = Column(String(50), default="organization")  # tenant, organization, global
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RolePolicy(Base):
    """Role-Policy association table."""
    __tablename__ = "role_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PolicyEvaluation(Base):
    """Policy evaluation results cache."""
    __tablename__ = "policy_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False, index=True)
    subject_id = Column(UUID(as_uuid=True), index=True)  # user_id or role_id
    resource_type = Column(String(255))
    resource_id = Column(String(255))
    action = Column(String(255))
    result = Column(Boolean, nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    context = Column(JSONB, default={})


# Pydantic Schemas

class PolicyCreate(BaseModel):
    """Schema for creating a policy."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    rules: Dict[str, Any] = Field(default_factory=dict)
    effect: PolicyEffect = PolicyEffect.ALLOW
    priority: int = Field(default=0, ge=0, le=1000)
    target_type: Optional[PolicyTargetType] = None
    target_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_pattern: Optional[str] = None
    actions: List[str] = Field(default_factory=list)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None


class PolicyUpdate(BaseModel):
    """Schema for updating a policy."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None
    effect: Optional[PolicyEffect] = None
    priority: Optional[int] = Field(None, ge=0, le=1000)
    enabled: Optional[bool] = None
    target_type: Optional[PolicyTargetType] = None
    target_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_pattern: Optional[str] = None
    actions: Optional[List[str]] = None
    conditions: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class PolicyResponse(BaseModel):
    """Schema for policy response."""
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    rules: Dict[str, Any]
    effect: str
    priority: int
    enabled: bool
    version: int
    target_type: Optional[str]
    target_id: Optional[str]
    resource_type: Optional[str]
    resource_pattern: Optional[str]
    actions: List[str]
    conditions: Dict[str, Any]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, obj):
        """Convert SQLAlchemy model to Pydantic schema."""
        return cls(
            id=str(obj.id),
            tenant_id=str(obj.tenant_id) if obj.tenant_id else "",
            name=obj.name,
            description=obj.description,
            rules=obj.rules or {},
            effect=obj.effect,
            priority=obj.priority or 0,
            enabled=obj.enabled if hasattr(obj, 'enabled') else True,
            version=obj.version if hasattr(obj, 'version') else 1,
            target_type=obj.target_type,
            target_id=obj.target_id,
            resource_type=obj.resource_type,
            resource_pattern=obj.resource_pattern,
            actions=obj.actions or [],
            conditions=obj.conditions or {},
            expires_at=obj.expires_at,
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )


class PolicyEvaluateRequest(BaseModel):
    """Schema for policy evaluation request."""
    subject_id: Optional[str] = None  # user_id or role_id
    subject_type: str = Field(default="user", pattern="^(user|role)$")
    resource_type: str = Field(..., min_length=1)
    resource_id: Optional[str] = None
    action: str = Field(..., min_length=1)
    context: Dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluateResponse(BaseModel):
    """Schema for policy evaluation response."""
    allowed: bool
    matched_policies: List[str] = Field(default_factory=list)
    denied_by: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoleCreate(BaseModel):
    """Schema for creating a role."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    organization_id: Optional[str] = None


class RoleResponse(BaseModel):
    """Schema for role response."""
    id: str
    tenant_id: str
    organization_id: Optional[str]
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, obj):
        """Convert SQLAlchemy model to Pydantic schema."""
        return cls(
            id=str(obj.id),
            tenant_id=str(obj.organization_id) if obj.organization_id else "",
            organization_id=str(obj.organization_id) if obj.organization_id else None,
            name=obj.name,
            description=obj.description,
            permissions=obj.permissions or [],
            is_system=obj.is_system if hasattr(obj, 'is_system') else False,
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )


# Re-export SQLAlchemy models for convenience
Policy = PolicyModel
Role = RoleModel
