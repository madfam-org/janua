# Migration models - placeholder for enterprise features
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from app.models.types import GUID as UUID, JSON as JSONB
from datetime import datetime
import uuid
import enum

from . import Base

class MigrationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MigrationProvider(str, enum.Enum):
    AUTH0 = "auth0"
    OKTA = "okta"
    FIREBASE = "firebase"
    COGNITO = "cognito"
    CUSTOM = "custom"

class MigrationJob(Base):
    __tablename__ = "migration_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    provider = Column(SQLEnum(MigrationProvider), nullable=False)
    status = Column(SQLEnum(MigrationStatus), default=MigrationStatus.PENDING)
    config = Column(JSONB, default={})
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MigratedUser(Base):
    __tablename__ = "migrated_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey("migration_jobs.id"))
    external_id = Column(String(255))
    janua_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(SQLEnum(MigrationStatus))
    migration_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

class MigrationLog(Base):
    __tablename__ = "migration_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_job_id = Column(UUID(as_uuid=True), ForeignKey("migration_jobs.id"))
    level = Column(String(20))
    message = Column(Text)
    details = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

class MigrationTemplate(Base):
    __tablename__ = "migration_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    provider = Column(SQLEnum(MigrationProvider))
    config_schema = Column(JSONB)
    mapping_rules = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)