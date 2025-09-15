"""
SSO/SAML models for enterprise authentication
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..models import Base


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