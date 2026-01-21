"""
Compliance and data protection models for GDPR, SOC 2, HIPAA, and other frameworks
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.types import GUID as UUID
from app.models.types import JSON as JSONB

from . import Base


class ComplianceFramework(str, enum.Enum):
    """Supported compliance frameworks"""

    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    CCPA = "ccpa"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"


class ConsentType(str, enum.Enum):
    """Types of consent under GDPR"""

    MARKETING = "marketing"
    ANALYTICS = "analytics"
    FUNCTIONAL = "functional"
    NECESSARY = "necessary"
    PERSONALIZATION = "personalization"
    THIRD_PARTY = "third_party"
    COOKIES = "cookies"
    PROFILING = "profiling"


class ConsentStatus(str, enum.Enum):
    """Consent status"""

    GIVEN = "given"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"


class LegalBasis(str, enum.Enum):
    """GDPR lawful basis for processing"""

    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"


class DataCategory(str, enum.Enum):
    """Categories of personal data"""

    IDENTITY = "identity"  # Name, username, email
    CONTACT = "contact"  # Email, phone, address
    DEMOGRAPHIC = "demographic"  # Age, gender, location
    FINANCIAL = "financial"  # Payment data, billing info
    TECHNICAL = "technical"  # IP address, device info, cookies
    BEHAVIORAL = "behavioral"  # Usage patterns, preferences
    HEALTH = "health"  # PHI under HIPAA
    BIOMETRIC = "biometric"  # Fingerprints, facial recognition
    LOCATION = "location"  # GPS, geolocation data
    SOCIAL = "social"  # Social media data
    PROFESSIONAL = "professional"  # Employment, job title
    EDUCATIONAL = "educational"  # Academic records


class DataSubjectRequestType(str, enum.Enum):
    """GDPR Article 15-22 data subject rights"""

    ACCESS = "access"  # Article 15 - Right of access
    RECTIFICATION = "rectification"  # Article 16 - Right to rectification
    ERASURE = "erasure"  # Article 17 - Right to erasure (right to be forgotten)
    PORTABILITY = "portability"  # Article 20 - Right to data portability
    RESTRICTION = "restriction"  # Article 18 - Right to restriction of processing
    OBJECTION = "objection"  # Article 21 - Right to object


class RequestStatus(str, enum.Enum):
    """Status of data subject requests"""

    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class ControlStatus(str, enum.Enum):
    """SOC2 control effectiveness status"""

    COMPLIANT = "compliant"  # Control meets requirements
    NON_COMPLIANT = "non_compliant"  # Control fails requirements
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    NEEDS_IMPROVEMENT = "needs_improvement"
    NOT_TESTED = "not_tested"
    EXCEPTION = "exception"


class ConsentRecord(Base):
    """GDPR consent management"""

    __tablename__ = "consent_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    # Consent details
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    purpose = Column(String(500), nullable=False)  # Purpose of processing
    legal_basis = Column(SQLEnum(LegalBasis), default=LegalBasis.CONSENT)
    status = Column(SQLEnum(ConsentStatus), default=ConsentStatus.GIVEN)

    # Consent lifecycle
    given_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    withdrawn_at = Column(DateTime)
    expires_at = Column(DateTime)  # Consent expiration
    last_confirmed_at = Column(DateTime)  # Last reconfirmation

    # Technical details
    ip_address = Column(String(50))
    user_agent = Column(Text)
    consent_method = Column(String(100))  # e.g., "cookie_banner", "form", "api"
    consent_version = Column(String(50))  # Privacy policy version

    # Additional metadata
    data_categories = Column(JSONB, default=[])  # Categories of data covered
    processing_purposes = Column(JSONB, default=[])  # Specific processing purposes
    third_parties = Column(JSONB, default=[])  # Third parties data is shared with
    retention_period = Column(Integer)  # Retention period in days

    # Audit trail
    consent_evidence = Column(JSONB, default={})  # Evidence of consent (form data, etc.)
    withdrawal_reason = Column(String(500))  # Reason for withdrawal
    notes = Column(Text)  # Additional notes

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataRetentionPolicy(Base):
    """Data retention and deletion policies"""

    __tablename__ = "data_retention_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    tenant_id = Column(UUID(as_uuid=True), index=True)

    # Policy details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    compliance_framework = Column(SQLEnum(ComplianceFramework))

    # Data classification
    data_category = Column(SQLEnum(DataCategory), nullable=False)
    data_source = Column(String(255))  # Source system/table
    legal_basis = Column(SQLEnum(LegalBasis))

    # Retention rules
    retention_period_days = Column(Integer, nullable=False)
    deletion_method = Column(
        String(100), default="soft_delete"
    )  # soft_delete, hard_delete, anonymize
    archival_required = Column(Boolean, default=False)
    archival_period_days = Column(Integer)

    # Automation settings
    auto_deletion_enabled = Column(Boolean, default=True)
    notification_before_deletion_days = Column(Integer, default=30)
    require_approval = Column(Boolean, default=False)

    # Policy metadata
    policy_version = Column(String(50), default="1.0")
    effective_date = Column(DateTime, default=datetime.utcnow)
    review_date = Column(DateTime)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataSubjectRequest(Base):
    """GDPR data subject rights requests"""

    __tablename__ = "data_subject_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(100), unique=True, nullable=False)  # Human-readable ID
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    # Request details
    request_type = Column(SQLEnum(DataSubjectRequestType), nullable=False)
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.RECEIVED)
    description = Column(Text)

    # Data scope
    data_categories = Column(JSONB, default=[])  # Categories of data requested
    date_range_start = Column(DateTime)  # Date range for data
    date_range_end = Column(DateTime)
    specific_fields = Column(JSONB, default=[])  # Specific fields requested

    # Processing details
    received_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    completed_at = Column(DateTime)
    response_due_date = Column(DateTime)  # Legal deadline (30 days for GDPR)

    # Identity verification
    identity_verified = Column(Boolean, default=False)
    identity_verification_method = Column(String(100))
    identity_verification_notes = Column(Text)

    # Response details
    response_method = Column(String(100))  # email, postal, secure_portal
    response_data_url = Column(String(500))  # URL to data export
    response_notes = Column(Text)
    rejection_reason = Column(String(500))  # If rejected

    # Compliance tracking
    legal_review_required = Column(Boolean, default=False)
    legal_review_completed = Column(Boolean, default=False)
    legal_reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Technical details
    ip_address = Column(String(50))
    user_agent = Column(Text)
    request_source = Column(String(100))  # web, api, email, phone

    # Audit trail
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    processing_notes = Column(Text)
    escalation_reason = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivacySettings(Base):
    """User privacy preferences and settings"""

    __tablename__ = "privacy_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    tenant_id = Column(UUID(as_uuid=True), index=True)

    # Communication preferences
    email_marketing = Column(Boolean, default=False)
    email_product_updates = Column(Boolean, default=True)
    email_security_alerts = Column(Boolean, default=True)
    sms_marketing = Column(Boolean, default=False)
    phone_marketing = Column(Boolean, default=False)

    # Data processing preferences
    analytics_tracking = Column(Boolean, default=True)
    personalization = Column(Boolean, default=True)
    third_party_sharing = Column(Boolean, default=False)
    profiling = Column(Boolean, default=False)
    automated_decision_making = Column(Boolean, default=False)

    # Cookie preferences
    essential_cookies = Column(Boolean, default=True)  # Always true
    functional_cookies = Column(Boolean, default=True)
    analytics_cookies = Column(Boolean, default=False)
    marketing_cookies = Column(Boolean, default=False)

    # Privacy controls
    profile_visibility = Column(String(50), default="private")  # public, private, contacts
    data_export_format = Column(String(50), default="json")  # json, csv, xml
    deletion_preference = Column(String(100), default="anonymize")  # delete, anonymize, retain

    # Geographic controls
    data_residency_preference = Column(String(100))  # Preferred data location
    cross_border_transfer_consent = Column(Boolean, default=False)

    # Compliance-specific settings
    gdpr_explicit_consent = Column(Boolean, default=False)
    ccpa_opt_out = Column(Boolean, default=False)

    # Metadata
    last_updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    privacy_policy_version = Column(String(50))
    consent_renewal_due = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataBreachIncident(Base):
    """Data breach incident tracking"""

    __tablename__ = "data_breach_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    breach_id = Column(String(100), unique=True, nullable=False)  # Human-readable ID
    tenant_id = Column(UUID(as_uuid=True), index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    # Incident details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(50), nullable=False)  # low, medium, high, critical
    breach_type = Column(String(100), nullable=False)  # unauthorized_access, data_loss, etc.

    # Impact assessment
    affected_records_count = Column(Integer, default=0)
    data_categories_affected = Column(JSONB, default=[])
    affected_users = Column(JSONB, default=[])  # User IDs or criteria
    geographic_scope = Column(JSONB, default=[])  # Countries/regions affected

    # Timeline
    discovered_at = Column(DateTime, nullable=False)
    occurred_at = Column(DateTime)  # When breach actually happened
    contained_at = Column(DateTime)
    resolved_at = Column(DateTime)

    # Notification tracking
    authority_notification_required = Column(Boolean, default=False)
    authority_notified_at = Column(DateTime)
    authority_notification_reference = Column(String(255))

    user_notification_required = Column(Boolean, default=False)
    users_notified_at = Column(DateTime)
    notification_method = Column(String(100))  # email, postal, website, media

    # 72-hour rule tracking (GDPR Article 33)
    notification_deadline = Column(DateTime)  # 72 hours from discovery
    deadline_met = Column(Boolean)
    deadline_miss_reason = Column(Text)

    # Investigation and response
    root_cause = Column(Text)
    technical_measures_taken = Column(Text)
    organizational_measures_taken = Column(Text)
    lessons_learned = Column(Text)

    # Risk assessment
    likelihood_of_risk = Column(String(50))  # low, medium, high
    risk_mitigation_measures = Column(Text)
    ongoing_monitoring_required = Column(Boolean, default=False)

    # Compliance framework specific fields
    gdpr_applicable = Column(Boolean, default=False)
    hipaa_applicable = Column(Boolean, default=False)
    ccpa_applicable = Column(Boolean, default=False)

    # Incident team
    incident_commander_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    legal_team_involved = Column(Boolean, default=False)
    external_counsel_involved = Column(Boolean, default=False)
    law_enforcement_involved = Column(Boolean, default=False)

    # Documentation
    forensic_report_url = Column(String(500))
    legal_analysis_url = Column(String(500))
    communication_template_used = Column(String(255))

    # Status tracking
    status = Column(String(50), default="open")  # open, investigating, contained, resolved, closed
    resolution_summary = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceReport(Base):
    """Compliance reporting and audit trails"""

    __tablename__ = "compliance_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(String(100), unique=True, nullable=False)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    # Report details
    title = Column(String(255), nullable=False)
    report_type = Column(String(100), nullable=False)  # audit, assessment, breach_notification
    compliance_framework = Column(SQLEnum(ComplianceFramework), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Report content
    executive_summary = Column(Text)
    findings = Column(JSONB, default=[])
    recommendations = Column(JSONB, default=[])
    risk_assessment = Column(JSONB, default={})
    compliance_score = Column(Integer)  # 0-100

    # Metrics
    metrics = Column(JSONB, default={})  # Key compliance metrics
    kpis = Column(JSONB, default={})  # Key performance indicators
    trends = Column(JSONB, default={})  # Trend analysis

    # Review and approval
    status = Column(String(50), default="draft")  # draft, review, approved, published
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    approved_at = Column(DateTime)

    # Distribution
    recipients = Column(JSONB, default=[])  # Who receives this report
    published_at = Column(DateTime)
    publication_url = Column(String(500))
    confidentiality_level = Column(String(50), default="internal")  # public, internal, confidential

    # Audit trail
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    generation_method = Column(String(100), default="automated")  # automated, manual, hybrid
    data_sources = Column(JSONB, default=[])  # Sources of data for the report

    # Follow-up
    action_items = Column(JSONB, default=[])
    follow_up_required = Column(Boolean, default=False)
    next_review_date = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceControl(Base):
    """SOC 2 and other compliance controls tracking"""

    __tablename__ = "compliance_controls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    # Control identification
    control_id = Column(String(100), nullable=False)  # e.g., CC6.1, A.9.1.1
    control_name = Column(String(255), nullable=False)
    compliance_framework = Column(SQLEnum(ComplianceFramework), nullable=False)
    control_family = Column(String(100))  # e.g., Access Control, Incident Response

    # Control details
    description = Column(Text, nullable=False)
    control_objective = Column(Text)
    control_activity = Column(Text)
    control_type = Column(String(50))  # preventive, detective, corrective
    control_frequency = Column(String(50))  # continuous, daily, weekly, monthly, quarterly, annual

    # Implementation
    implementation_status = Column(
        String(50), default="not_implemented"
    )  # not_implemented, in_progress, implemented, effective
    implementation_date = Column(DateTime)
    implementation_evidence = Column(JSONB, default={})
    responsible_party = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Testing and validation
    last_tested_date = Column(DateTime)
    test_frequency = Column(String(50))  # monthly, quarterly, annually
    test_results = Column(JSONB, default={})
    effectiveness_rating = Column(String(50))  # effective, partially_effective, ineffective

    # Control effectiveness status (used by compliance service)
    status = Column(SQLEnum(ControlStatus), default=ControlStatus.NOT_TESTED, nullable=False)
    last_assessed = Column(DateTime, nullable=True)
    assessed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Deficiencies and remediation
    deficiencies_identified = Column(JSONB, default=[])
    remediation_plan = Column(Text)
    remediation_due_date = Column(DateTime)
    remediation_status = Column(
        String(50), default="not_required"
    )  # not_required, planned, in_progress, completed

    # Evidence and documentation
    evidence_location = Column(String(500))  # Where evidence is stored
    evidence_retention_period = Column(Integer)  # Days to retain evidence
    documentation_url = Column(String(500))

    # Risk assessment
    inherent_risk_rating = Column(String(50))  # low, medium, high, critical
    residual_risk_rating = Column(String(50))  # After control implementation
    risk_tolerance = Column(String(50))
    compensating_controls = Column(JSONB, default=[])

    # Monitoring
    monitoring_method = Column(String(100))  # automated, manual, hybrid
    monitoring_frequency = Column(String(50))
    key_metrics = Column(JSONB, default={})
    alerting_enabled = Column(Boolean, default=False)

    # Audit and review
    last_reviewed_date = Column(DateTime)
    review_frequency = Column(String(50))  # quarterly, annually
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    audit_findings = Column(JSONB, default=[])

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Add relationships
ConsentRecord.user = relationship(
    "User", back_populates="consent_records", foreign_keys=[ConsentRecord.user_id]
)
DataSubjectRequest.user = relationship(
    "User", back_populates="data_subject_requests", foreign_keys=[DataSubjectRequest.user_id]
)
DataSubjectRequest.assigned_user = relationship(
    "User", foreign_keys=[DataSubjectRequest.assigned_to]
)
DataSubjectRequest.legal_reviewer = relationship(
    "User", foreign_keys=[DataSubjectRequest.legal_reviewer_id]
)
PrivacySettings.user = relationship(
    "User", back_populates="privacy_settings", foreign_keys=[PrivacySettings.user_id]
)
DataBreachIncident.incident_commander = relationship(
    "User", foreign_keys=[DataBreachIncident.incident_commander_id]
)
ComplianceReport.generated_by_user = relationship(
    "User", foreign_keys=[ComplianceReport.generated_by]
)
ComplianceReport.reviewed_by_user = relationship(
    "User", foreign_keys=[ComplianceReport.reviewed_by]
)
ComplianceReport.approved_by_user = relationship(
    "User", foreign_keys=[ComplianceReport.approved_by]
)
ComplianceControl.responsible_user = relationship(
    "User", foreign_keys=[ComplianceControl.responsible_party]
)
ComplianceControl.reviewer = relationship("User", foreign_keys=[ComplianceControl.reviewer_id])
