"""
Localization and internationalization models
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..models import Base


class LocaleStatus(enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"


class TranslationStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class Locale(Base):
    """Supported locales/languages"""
    __tablename__ = 'locales'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Locale identification
    code = Column(String(10), unique=True, nullable=False, index=True)  # e.g., en-US, fr-FR
    language_code = Column(String(2), nullable=False)  # ISO 639-1
    country_code = Column(String(2), nullable=True)  # ISO 3166-1
    
    # Display information
    name = Column(String(100), nullable=False)  # English name
    native_name = Column(String(100), nullable=False)  # Native language name
    flag_emoji = Column(String(10), nullable=True)  # Flag emoji
    
    # Configuration
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    is_rtl = Column(Boolean, default=False)  # Right-to-left
    
    # Formatting
    date_format = Column(String(50), default="MM/DD/YYYY")
    time_format = Column(String(50), default="HH:mm:ss")
    number_format = Column(JSON, default=dict)
    """
    Example number format:
    {
        "decimal_separator": ".",
        "thousands_separator": ",",
        "currency_symbol": "$",
        "currency_position": "before"
    }
    """
    
    # Translation status
    translation_progress = Column(Integer, default=0)  # Percentage
    total_strings = Column(Integer, default=0)
    translated_strings = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    translations = relationship("Translation", back_populates="locale", cascade="all, delete-orphan")
    locale_settings = relationship("LocaleSettings", back_populates="locale", cascade="all, delete-orphan")


class TranslationKey(Base):
    """Translation keys/strings to be translated"""
    __tablename__ = 'translation_keys'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Key identification
    key = Column(String(500), unique=True, nullable=False, index=True)  # e.g., auth.login.title
    category = Column(String(100), nullable=True)  # Grouping category
    
    # Default content
    default_value = Column(Text, nullable=False)  # Default English text
    description = Column(Text, nullable=True)  # Context for translators
    
    # Metadata
    max_length = Column(Integer, nullable=True)  # Character limit
    is_html = Column(Boolean, default=False)  # Contains HTML
    is_plural = Column(Boolean, default=False)  # Requires plural forms
    
    # Variables
    variables = Column(JSON, default=list)  # List of variables in string
    """
    Example variables:
    ["{{username}}", "{{count}}", "{{date}}"]
    """
    
    # Context
    screenshot_url = Column(String(500), nullable=True)  # UI context
    notes = Column(Text, nullable=True)  # Translation notes
    
    # Status
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)  # Prevent changes
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    translations = relationship("Translation", back_populates="translation_key", cascade="all, delete-orphan")


class Translation(Base):
    """Translated content for each locale"""
    __tablename__ = 'translations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    translation_key_id = Column(UUID(as_uuid=True), ForeignKey('translation_keys.id'), nullable=False)
    locale_id = Column(UUID(as_uuid=True), ForeignKey('locales.id'), nullable=False)
    
    # Translation content
    value = Column(Text, nullable=False)  # Translated text
    plural_forms = Column(JSON, nullable=True)  # For plural translations
    """
    Example plural forms:
    {
        "zero": "No items",
        "one": "One item",
        "other": "{{count}} items"
    }
    """
    
    # Status
    status = Column(SQLEnum(TranslationStatus), default=TranslationStatus.PENDING)
    is_machine_translated = Column(Boolean, default=False)
    confidence_score = Column(Float, nullable=True)  # Translation confidence
    
    # Review
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Version control
    version = Column(Integer, default=1)
    previous_value = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    translation_key = relationship("TranslationKey", back_populates="translations")
    locale = relationship("Locale", back_populates="translations")
    reviewer = relationship("User")


class LocaleSettings(Base):
    """Organization-specific locale settings"""
    __tablename__ = 'locale_settings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    locale_id = Column(UUID(as_uuid=True), ForeignKey('locales.id'), nullable=False)
    
    # Settings
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Customization
    custom_translations = Column(JSON, default=dict)  # Override default translations
    custom_date_format = Column(String(50), nullable=True)
    custom_time_format = Column(String(50), nullable=True)
    custom_number_format = Column(JSON, nullable=True)
    
    # Regional settings
    timezone = Column(String(50), nullable=True)
    currency = Column(String(3), nullable=True)  # ISO 4217
    
    # Content preferences
    content_filter = Column(JSON, nullable=True)  # Filter inappropriate content
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")
    locale = relationship("Locale", back_populates="locale_settings")


class TranslationProject(Base):
    """Translation project management"""
    __tablename__ = 'translation_projects'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Project details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Scope
    target_locales = Column(JSON, default=list)  # List of locale codes
    translation_keys = Column(JSON, default=list)  # List of key IDs
    
    # Status
    status = Column(SQLEnum(LocaleStatus), default=LocaleStatus.DRAFT)
    progress = Column(Integer, default=0)  # Overall progress percentage
    
    # Team
    project_manager_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    translator_ids = Column(JSON, default=list)  # List of translator user IDs
    reviewer_ids = Column(JSON, default=list)  # List of reviewer user IDs
    
    # Timeline
    start_date = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_date = Column(DateTime(timezone=True), nullable=True)
    
    # Budget
    budget = Column(JSON, nullable=True)  # Budget information
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    project_manager = relationship("User")


class TranslationMemory(Base):
    """Translation memory for reuse"""
    __tablename__ = 'translation_memory'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source and target
    source_locale = Column(String(10), nullable=False)
    target_locale = Column(String(10), nullable=False)
    source_text = Column(Text, nullable=False, index=True)
    target_text = Column(Text, nullable=False)
    
    # Context
    context = Column(String(500), nullable=True)  # Usage context
    domain = Column(String(100), nullable=True)  # Subject domain
    
    # Quality
    quality_score = Column(Float, default=1.0)  # 0.0 to 1.0
    usage_count = Column(Integer, default=0)
    
    # Source
    source_type = Column(String(50), nullable=True)  # manual, machine, import
    source_reference = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class LocalizationGlossary(Base):
    """Terminology glossary for consistent translations"""
    __tablename__ = 'localization_glossary'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    
    # Term
    term = Column(String(200), nullable=False, index=True)
    definition = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    
    # Translations
    translations = Column(JSON, default=dict)  # Locale code -> translation
    """
    Example translations:
    {
        "fr-FR": "terme",
        "es-ES": "término",
        "de-DE": "Begriff"
    }
    """
    
    # Rules
    do_not_translate = Column(Boolean, default=False)  # Brand names, etc.
    case_sensitive = Column(Boolean, default=False)
    
    # Categories
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization")


class RegionalContent(Base):
    """Region-specific content variations"""
    __tablename__ = 'regional_content'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Content identification
    content_key = Column(String(500), nullable=False, index=True)
    content_type = Column(String(50), nullable=False)  # text, image, video, etc.
    
    # Regional variations
    regions = Column(JSON, default=dict)  # Region code -> content
    """
    Example regions:
    {
        "US": {"value": "Color", "image": "us-flag.png"},
        "GB": {"value": "Colour", "image": "uk-flag.png"},
        "AU": {"value": "Colour", "image": "au-flag.png"}
    }
    """
    
    # Default
    default_content = Column(JSON, nullable=False)
    
    # Rules
    selection_rules = Column(JSON, nullable=True)  # Rules for content selection
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())