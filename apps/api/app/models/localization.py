"""
Localization models with Pydantic schemas.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

# Re-export SQLAlchemy models from __init__.py for router usage
from . import Locale, TranslationKey, Translation

# Make SQLAlchemy models available at module level
__all__ = ["Locale", "TranslationKey", "Translation"]


# Pydantic Schemas


class LocaleCreate(BaseModel):
    """Schema for creating a locale."""

    code: str = Field(..., min_length=2, max_length=10, pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    name: str = Field(..., min_length=1, max_length=100)
    native_name: str = Field(..., min_length=1, max_length=100)
    is_rtl: bool = False


class LocaleUpdate(BaseModel):
    """Schema for updating a locale."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    native_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    is_rtl: Optional[bool] = None
    translation_progress: Optional[int] = Field(None, ge=0, le=100)


class LocaleResponse(BaseModel):
    """Schema for locale response."""

    id: str
    code: str
    name: str
    native_name: str
    is_active: bool
    is_rtl: bool
    translation_progress: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranslationKeyCreate(BaseModel):
    """Schema for creating a translation key."""

    key: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9_.]+$")
    default_value: str = Field(..., min_length=1)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)


class TranslationKeyUpdate(BaseModel):
    """Schema for updating a translation key."""

    default_value: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)


class TranslationKeyResponse(BaseModel):
    """Schema for translation key response."""

    id: str
    key: str
    default_value: str
    description: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranslationCreate(BaseModel):
    """Schema for creating a translation."""

    translation_key_id: str
    locale_id: str
    value: str = Field(..., min_length=1)


class TranslationUpdate(BaseModel):
    """Schema for updating a translation."""

    value: Optional[str] = Field(None, min_length=1)
    is_approved: Optional[bool] = None


class TranslationResponse(BaseModel):
    """Schema for translation response."""

    id: str
    translation_key_id: str
    locale_id: str
    value: str
    is_approved: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranslationBulkCreate(BaseModel):
    """Schema for bulk creating translations."""

    locale_code: str
    translations: dict[str, str] = Field(..., description="Dictionary of key: value pairs")


class TranslationExportResponse(BaseModel):
    """Schema for exporting translations."""

    locale_code: str
    translations: dict[str, str]
    total_keys: int
    translated_keys: int
    progress_percentage: int
