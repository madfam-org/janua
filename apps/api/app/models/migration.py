"""
Migration models for data portability and user migration
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from app.models import Base


class MigrationProvider(enum.Enum):
    AUTH0 = "auth0"
    OKTA = "okta"
    COGNITO = "cognito"
    FIREBASE = "firebase"
    CUSTOM = "custom"
    CSV = "csv"
    JSON = "json"


class MigrationStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class HashAlgorithm(enum.Enum):
    BCRYPT = "bcrypt"
    SCRYPT = "scrypt"
    PBKDF2 = "pbkdf2"
    ARGON2 = "argon2"
    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"  # Legacy support only
    CUSTOM = "custom"


class MigrationJob(Base):
    """Migration job tracking"""
    __tablename__ = 'migration_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Migration details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(SQLEnum(MigrationProvider), nullable=False)
    status = Column(SQLEnum(MigrationStatus), default=MigrationStatus.PENDING)
    
    # Configuration
    source_config = Column(JSON, default=dict)  # Provider-specific config
    mapping_config = Column(JSON, default=dict)  # Field mapping configuration
    options = Column(JSON, default=dict)  # Migration options
    
    # Statistics
    total_users = Column(Integer, default=0)
    migrated_users = Column(Integer, default=0)
    failed_users = Column(Integer, default=0)
    skipped_users = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    estimated_completion = Column(DateTime(timezone=True), nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    migration_logs = relationship("MigrationLog", back_populates="migration_job", cascade="all, delete-orphan")
    migrated_users = relationship("MigratedUser", back_populates="migration_job", cascade="all, delete-orphan")


class MigratedUser(Base):
    """Track migrated users"""
    __tablename__ = 'migrated_users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey('migration_jobs.id'), nullable=False)
    
    # Source user info
    source_user_id = Column(String(255), nullable=False)  # ID in source system
    source_email = Column(String(255), nullable=False)
    source_username = Column(String(100), nullable=True)
    
    # Target user info
    target_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Migration status
    is_migrated = Column(Boolean, default=False)
    migration_errors = Column(JSON, default=list)
    
    # Password migration
    requires_password_reset = Column(Boolean, default=False)
    password_migrated = Column(Boolean, default=False)
    hash_algorithm = Column(SQLEnum(HashAlgorithm), nullable=True)
    
    # Data mapping
    source_data = Column(JSON, default=dict)  # Original user data
    mapped_data = Column(JSON, default=dict)  # Transformed data
    
    # Timestamps
    migrated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    migration_job = relationship("MigrationJob", back_populates="migrated_users")
    target_user = relationship("User")


class MigrationLog(Base):
    """Detailed migration logs"""
    __tablename__ = 'migration_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey('migration_jobs.id'), nullable=False)
    
    # Log details
    level = Column(String(20), nullable=False)  # info, warning, error
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    
    # Context
    user_id = Column(String(255), nullable=True)  # Source user ID if applicable
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    migration_job = relationship("MigrationJob", back_populates="migration_logs")


class PasswordHashAdapter(Base):
    """Password hash algorithm adapters"""
    __tablename__ = 'password_hash_adapters'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Adapter details
    name = Column(String(100), unique=True, nullable=False)
    algorithm = Column(SQLEnum(HashAlgorithm), nullable=False)
    is_enabled = Column(Boolean, default=True)
    
    # Configuration
    config = Column(JSON, default=dict)
    """
    Example configs:
    BCRYPT: {"rounds": 12}
    PBKDF2: {"iterations": 100000, "key_length": 32, "digest": "sha256"}
    SCRYPT: {"n": 16384, "r": 8, "p": 1}
    ARGON2: {"time_cost": 2, "memory_cost": 65536, "parallelism": 1}
    """
    
    # Validation
    test_hash = Column(Text, nullable=True)  # Known hash for validation
    test_password = Column(Text, nullable=True)  # Known password for validation
    
    # Usage statistics
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DataExport(Base):
    """Data export jobs for portability"""
    __tablename__ = 'data_exports'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Export details
    export_type = Column(String(50), nullable=False)  # user_data, organization_data, audit_logs
    format = Column(String(20), nullable=False)  # json, csv, xml
    status = Column(SQLEnum(MigrationStatus), default=MigrationStatus.PENDING)
    
    # Configuration
    include_options = Column(JSON, default=dict)  # What to include in export
    exclude_options = Column(JSON, default=dict)  # What to exclude
    
    # File details
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # In bytes
    download_url = Column(String(500), nullable=True)
    
    # Security
    is_encrypted = Column(Boolean, default=True)
    encryption_key_id = Column(String(255), nullable=True)
    
    # Timing
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User")
    organization = relationship("Organization")


class MigrationTemplate(Base):
    """Reusable migration templates"""
    __tablename__ = 'migration_templates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Template details
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(SQLEnum(MigrationProvider), nullable=False)
    
    # Field mappings
    field_mappings = Column(JSON, nullable=False)
    """
    Example mapping:
    {
        "user_id": {"source": "user_id", "transform": "string"},
        "email": {"source": "email", "transform": "lowercase"},
        "name": {"source": ["given_name", "family_name"], "transform": "concat"},
        "metadata": {"source": "user_metadata", "transform": "json"}
    }
    """
    
    # Transformation rules
    transformations = Column(JSON, default=dict)
    """
    Example transformations:
    {
        "lowercase": "value.toLowerCase()",
        "concat": "values.join(' ')",
        "date": "new Date(value).toISOString()"
    }
    """
    
    # Validation rules
    validations = Column(JSON, default=dict)
    
    # Usage
    is_default = Column(Boolean, default=False)
    times_used = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())