"""
Compliance and regulatory models for GDPR, HIPAA, and other standards
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..models import Base


class ComplianceStandard(enum.Enum):
    GDPR = "gdpr"  # General Data Protection Regulation
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    CCPA = "ccpa"  # California Consumer Privacy Act
    SOC2 = "soc2"  # Service Organization Control 2
    ISO27001 = "iso27001"  # Information Security Management
    PCI_DSS = "pci_dss"  # Payment Card Industry Data Security Standard
    NIST = "nist"  # National Institute of Standards and Technology


class ConsentType(enum.Enum):
    TERMS_OF_SERVICE = "terms_of_service"
    PRIVACY_POLICY = "privacy_policy"
    MARKETING = "marketing"
    DATA_PROCESSING = "data_processing"
    COOKIES = "cookies"
    ANALYTICS = "analytics"
    THIRD_PARTY = "third_party"


class DataRequestType(enum.Enum):
    ACCESS = "access"  # Right to access data
    PORTABILITY = "portability"  # Right to data portability
    RECTIFICATION = "rectification"  # Right to correct data
    ERASURE = "erasure"  # Right to be forgotten
    RESTRICTION = "restriction"  # Right to restrict processing
    OBJECTION = "objection"  # Right to object to processing


class DataRequestStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ComplianceConfiguration(Base):
    """Organization compliance configuration"""
    __tablename__ = 'compliance_configurations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False, unique=True)
    
    # Enabled standards
    enabled_standards = Column(JSON, default=list)  # List of ComplianceStandard values
    
    # GDPR settings
    gdpr_enabled = Column(Boolean, default=False)
    gdpr_data_controller = Column(String(500), nullable=True)  # Controller entity name
    gdpr_data_processor = Column(String(500), nullable=True)  # Processor entity name
    gdpr_dpo_email = Column(String(255), nullable=True)  # Data Protection Officer email
    gdpr_lawful_basis = Column(JSON, default=dict)  # Lawful basis for processing
    
    # HIPAA settings
    hipaa_enabled = Column(Boolean, default=False)
    hipaa_covered_entity = Column(Boolean, default=False)
    hipaa_business_associate = Column(Boolean, default=False)
    hipaa_security_officer = Column(String(255), nullable=True)
    
    # Data residency
    data_residency_enabled = Column(Boolean, default=False)
    allowed_regions = Column(JSON, default=list)  # List of allowed regions
    default_region = Column(String(50), nullable=True)
    
    # Consent management
    consent_required = Column(Boolean, default=True)
    consent_age_verification = Column(Boolean, default=False)
    consent_minimum_age = Column(Integer, default=16)  # GDPR default
    consent_renewal_days = Column(Integer, nullable=True)  # Days before renewal required
    
    # Data retention
    retention_enabled = Column(Boolean, default=False)
    default_retention_days = Column(Integer, default=365)
    retention_policies = Column(JSON, default=dict)  # Type-specific retention
    
    # Audit requirements
    audit_logging_enabled = Column(Boolean, default=True)
    audit_retention_days = Column(Integer, default=2555)  # 7 years default
    
    # Encryption requirements
    encryption_at_rest = Column(Boolean, default=True)
    encryption_in_transit = Column(Boolean, default=True)
    encryption_algorithm = Column(String(50), default="AES-256")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    consent_records = relationship("ConsentRecord", back_populates="compliance_configuration")
    data_requests = relationship("DataRequest", back_populates="compliance_configuration")


class ConsentRecord(Base):
    """User consent tracking"""
    __tablename__ = 'consent_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    compliance_configuration_id = Column(UUID(as_uuid=True), ForeignKey('compliance_configurations.id'), nullable=True)
    
    # Consent details
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    version = Column(String(50), nullable=False)  # Version of terms/policy
    
    # Status
    is_granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    consent_method = Column(String(50), nullable=True)  # explicit, implicit, opt-out
    
    # Legal basis (GDPR)
    lawful_basis = Column(String(50), nullable=True)  # consent, contract, legal, vital, public, legitimate
    purpose = Column(Text, nullable=True)  # Purpose of processing
    
    # Document references
    document_url = Column(String(500), nullable=True)
    document_hash = Column(String(255), nullable=True)  # SHA256 of document
    
    # Parental consent (for minors)
    requires_parental_consent = Column(Boolean, default=False)
    parental_consent_provided = Column(Boolean, default=False)
    parent_email = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    compliance_configuration = relationship("ComplianceConfiguration", back_populates="consent_records")


class DataRequest(Base):
    """User data requests (GDPR, CCPA)"""
    __tablename__ = 'data_requests'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    compliance_configuration_id = Column(UUID(as_uuid=True), ForeignKey('compliance_configurations.id'), nullable=True)
    
    # Request details
    request_type = Column(SQLEnum(DataRequestType), nullable=False)
    status = Column(SQLEnum(DataRequestStatus), default=DataRequestStatus.PENDING)
    
    # Request data
    request_details = Column(JSON, default=dict)  # Specific details of request
    verification_token = Column(String(255), nullable=True)
    verification_completed = Column(Boolean, default=False)
    
    # Response
    response_data = Column(JSON, nullable=True)  # Response data or file references
    response_file_url = Column(String(500), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Processing
    processor_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    processing_notes = Column(Text, nullable=True)
    
    # Timing
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=False)  # Legal deadline
    processed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    processor = relationship("User", foreign_keys=[processor_id])
    compliance_configuration = relationship("ComplianceConfiguration", back_populates="data_requests")


class AuditLog(Base):
    """Comprehensive audit logging for compliance"""
    __tablename__ = 'audit_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Actor information
    actor_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    actor_type = Column(String(50), nullable=False)  # user, system, api
    actor_ip = Column(String(50), nullable=True)
    actor_user_agent = Column(String(500), nullable=True)
    
    # Action details
    action = Column(String(100), nullable=False)  # Action performed
    resource_type = Column(String(50), nullable=False)  # Type of resource
    resource_id = Column(String(255), nullable=True)  # ID of affected resource
    
    # Change details
    old_values = Column(JSON, nullable=True)  # Previous state
    new_values = Column(JSON, nullable=True)  # New state
    metadata = Column(JSON, default=dict)  # Additional context
    
    # Compliance
    compliance_relevant = Column(Boolean, default=False)
    compliance_standards = Column(JSON, default=list)  # Relevant standards
    
    # Security
    risk_level = Column(String(20), nullable=True)  # low, medium, high, critical
    is_suspicious = Column(Boolean, default=False)
    
    # Result
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization")
    actor = relationship("User")


class DataRetentionPolicy(Base):
    """Data retention policies by type"""
    __tablename__ = 'data_retention_policies'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    
    # Policy details
    data_type = Column(String(100), nullable=False)  # user_data, logs, sessions, etc.
    retention_days = Column(Integer, nullable=False)
    
    # Actions
    action_on_expiry = Column(String(50), default="delete")  # delete, anonymize, archive
    
    # Exceptions
    legal_hold = Column(Boolean, default=False)  # Prevent deletion for legal reasons
    exception_criteria = Column(JSON, nullable=True)  # Criteria for exceptions
    
    # Settings
    is_active = Column(Boolean, default=True)
    auto_delete = Column(Boolean, default=True)
    
    # Statistics
    last_cleanup_at = Column(DateTime(timezone=True), nullable=True)
    records_deleted = Column(Integer, default=0)
    records_anonymized = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")


class PrivacyPolicy(Base):
    """Privacy policy versions and acceptance"""
    __tablename__ = 'privacy_policies'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Policy details
    version = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)  # Full policy text
    summary = Column(Text, nullable=True)  # Key points summary
    
    # Legal
    effective_date = Column(DateTime(timezone=True), nullable=False)
    jurisdiction = Column(String(100), nullable=True)
    languages = Column(JSON, default=list)  # Available languages
    
    # Changes
    change_summary = Column(Text, nullable=True)  # What changed from previous
    requires_reacceptance = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    
    # URLs
    public_url = Column(String(500), nullable=True)
    pdf_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    organization = relationship("Organization")


class DataResidency(Base):
    """Data residency configuration"""
    __tablename__ = 'data_residency'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Region configuration
    region = Column(String(50), nullable=False)  # us-east, eu-west, ap-south, etc.
    country = Column(String(2), nullable=True)  # ISO country code
    
    # Data types
    data_types = Column(JSON, default=list)  # Types of data stored in region
    
    # Compliance
    compliance_requirements = Column(JSON, default=list)  # Applicable regulations
    
    # Status
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)
    
    # Migration
    migrated_from = Column(String(50), nullable=True)  # Previous region
    migrated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User")