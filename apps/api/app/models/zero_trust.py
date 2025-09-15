"""
Zero-Trust authentication models for adaptive security
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..models import Base


class RiskLevel(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthenticationMethod(enum.Enum):
    PASSWORD = "password"
    MFA = "mfa"
    PASSKEY = "passkey"
    SSO = "sso"
    MAGIC_LINK = "magic_link"
    BIOMETRIC = "biometric"


class DeviceTrustLevel(enum.Enum):
    UNTRUSTED = "untrusted"
    KNOWN = "known"
    MANAGED = "managed"
    TRUSTED = "trusted"


class AccessDecision(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"
    STEP_UP = "step_up"


class RiskAssessment(Base):
    """Risk assessment for authentication attempts"""
    __tablename__ = 'risk_assessments'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=True)
    
    # Risk scores (0.0 to 1.0)
    overall_risk_score = Column(Float, nullable=False)
    location_risk_score = Column(Float, default=0.0)
    device_risk_score = Column(Float, default=0.0)
    behavior_risk_score = Column(Float, default=0.0)
    network_risk_score = Column(Float, default=0.0)
    
    # Risk level
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    
    # Context data
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    location_country = Column(String(2), nullable=True)
    location_city = Column(String(100), nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Risk factors
    risk_factors = Column(JSON, default=dict)  # Detailed risk factors
    anomalies_detected = Column(JSON, default=list)  # List of anomalies
    
    # Decision
    access_decision = Column(SQLEnum(AccessDecision), nullable=False)
    required_auth_methods = Column(JSON, default=list)  # Required auth methods
    
    # Timestamps
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User")
    session = relationship("Session")
    adaptive_challenges = relationship("AdaptiveChallenge", back_populates="risk_assessment")


class DeviceProfile(Base):
    """Device profiles for trust evaluation"""
    __tablename__ = 'device_profiles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Device identification
    device_fingerprint = Column(String(255), unique=True, nullable=False)
    device_name = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    
    # Trust level
    trust_level = Column(SQLEnum(DeviceTrustLevel), default=DeviceTrustLevel.UNTRUSTED)
    
    # Device details
    platform = Column(String(50), nullable=True)  # iOS, Android, Windows, etc.
    browser = Column(String(50), nullable=True)
    browser_version = Column(String(20), nullable=True)
    
    # Security posture
    is_rooted = Column(Boolean, default=False)
    has_screen_lock = Column(Boolean, default=False)
    has_biometric = Column(Boolean, default=False)
    last_security_check = Column(DateTime(timezone=True), nullable=True)
    
    # Compliance
    is_compliant = Column(Boolean, default=False)
    compliance_issues = Column(JSON, default=list)
    
    # Management
    is_managed = Column(Boolean, default=False)
    mdm_enrollment_id = Column(String(255), nullable=True)
    
    # Usage statistics
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    successful_auth_count = Column(Integer, default=0)
    failed_auth_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    access_policies = relationship("DeviceAccessPolicy", back_populates="device_profile")


class AdaptiveChallenge(Base):
    """Adaptive authentication challenges"""
    __tablename__ = 'adaptive_challenges'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    risk_assessment_id = Column(UUID(as_uuid=True), ForeignKey('risk_assessments.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Challenge details
    challenge_type = Column(String(50), nullable=False)  # captcha, mfa, biometric, etc.
    challenge_data = Column(JSON, default=dict)
    
    # Status
    is_completed = Column(Boolean, default=False)
    is_successful = Column(Boolean, nullable=True)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    risk_assessment = relationship("RiskAssessment", back_populates="adaptive_challenges")
    user = relationship("User")


class AccessPolicy(Base):
    """Zero-trust access policies"""
    __tablename__ = 'access_policies'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Policy details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority evaluated first
    
    # Conditions (JSON logic)
    conditions = Column(JSON, nullable=False)
    """
    Example conditions:
    {
        "and": [
            {"risk_level": {"in": ["high", "critical"]}},
            {"location_country": {"not_in": ["US", "CA"]}}
        ]
    }
    """
    
    # Actions
    access_decision = Column(SQLEnum(AccessDecision), nullable=False)
    required_auth_methods = Column(JSON, default=list)
    additional_checks = Column(JSON, default=list)  # captcha, device_trust, etc.
    
    # Scope
    applies_to_users = Column(JSON, default=list)  # User IDs or groups
    applies_to_resources = Column(JSON, default=list)  # Resource patterns
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    policy_evaluations = relationship("PolicyEvaluation", back_populates="access_policy")


class PolicyEvaluation(Base):
    """Access policy evaluation logs"""
    __tablename__ = 'policy_evaluations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    access_policy_id = Column(UUID(as_uuid=True), ForeignKey('access_policies.id'), nullable=False)
    risk_assessment_id = Column(UUID(as_uuid=True), ForeignKey('risk_assessments.id'), nullable=False)
    
    # Evaluation result
    matched = Column(Boolean, nullable=False)
    decision = Column(SQLEnum(AccessDecision), nullable=False)
    
    # Context
    evaluation_context = Column(JSON, default=dict)
    
    # Timestamp
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    access_policy = relationship("AccessPolicy", back_populates="policy_evaluations")
    risk_assessment = relationship("RiskAssessment")


class DeviceAccessPolicy(Base):
    """Device-specific access policies"""
    __tablename__ = 'device_access_policies'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_profile_id = Column(UUID(as_uuid=True), ForeignKey('device_profiles.id'), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Policy rules
    require_managed = Column(Boolean, default=False)
    require_compliant = Column(Boolean, default=False)
    require_encrypted = Column(Boolean, default=False)
    require_latest_os = Column(Boolean, default=False)
    
    # Trust requirements
    minimum_trust_level = Column(SQLEnum(DeviceTrustLevel), default=DeviceTrustLevel.KNOWN)
    
    # Restrictions
    blocked_platforms = Column(JSON, default=list)
    allowed_platforms = Column(JSON, default=list)
    blocked_browsers = Column(JSON, default=list)
    allowed_browsers = Column(JSON, default=list)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    device_profile = relationship("DeviceProfile", back_populates="access_policies")
    organization = relationship("Organization")


class BehaviorBaseline(Base):
    """User behavior baselines for anomaly detection"""
    __tablename__ = 'behavior_baselines'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, unique=True)
    
    # Login patterns
    typical_login_times = Column(JSON, default=dict)  # Hour distribution
    typical_login_days = Column(JSON, default=dict)  # Day of week distribution
    typical_locations = Column(JSON, default=list)  # Common locations
    typical_devices = Column(JSON, default=list)  # Common devices
    typical_ip_ranges = Column(JSON, default=list)  # Common IP ranges
    
    # Activity patterns
    average_session_duration = Column(Float, nullable=True)  # In minutes
    average_daily_logins = Column(Float, nullable=True)
    typical_user_agents = Column(JSON, default=list)
    
    # Resource access patterns
    commonly_accessed_resources = Column(JSON, default=list)
    access_frequency_patterns = Column(JSON, default=dict)
    
    # Statistical measures
    login_velocity_baseline = Column(Float, nullable=True)  # Logins per hour
    failed_login_baseline = Column(Float, nullable=True)  # Failed login ratio
    
    # Learning period
    learning_started_at = Column(DateTime(timezone=True), server_default=func.now())
    learning_completed_at = Column(DateTime(timezone=True), nullable=True)
    data_points_collected = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")


class ThreatIntelligence(Base):
    """Threat intelligence data for risk assessment"""
    __tablename__ = 'threat_intelligence'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Threat indicator
    indicator_type = Column(String(50), nullable=False)  # ip, email, domain, etc.
    indicator_value = Column(String(255), nullable=False, index=True)
    
    # Threat details
    threat_type = Column(String(100), nullable=True)  # malware, phishing, botnet, etc.
    threat_level = Column(SQLEnum(RiskLevel), nullable=False)
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    
    # Source
    source = Column(String(100), nullable=True)  # Threat feed source
    source_reference = Column(String(500), nullable=True)
    
    # Context
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    
    # Validity
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())