"""
Localization and internationalization API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel
import logging

from ...database import get_db
from app.dependencies import require_admin
from ...models import User
from ...models.localization import Locale, TranslationKey, Translation

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/localization",
    tags=["Localization"],
    responses={404: {"description": "Not found"}},
)


class TranslationCreate(BaseModel):
    key: str
    locale_code: str
    value: str


@router.get("/locales")
async def list_locales(is_active: Optional[bool] = None, db: AsyncSession = Depends(get_db)):
    """List available locales"""
    try:
        query = select(Locale)
        if is_active is not None:
            query = query.where(Locale.is_active == is_active)

        result = await db.execute(query)
        locales = result.scalars().all()

        return [
            {
                "code": locale.code,
                "name": locale.name,
                "native_name": locale.native_name,
                "is_active": locale.is_active,
                "is_rtl": locale.is_rtl,
                "translation_progress": locale.translation_progress,
            }
            for locale in locales
        ]

    except Exception as e:
        logger.error(f"Failed to list locales: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translations")
async def create_translation(
    translation: TranslationCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create or update translation"""
    try:
        # Get or create translation key
        key_result = await db.execute(
            select(TranslationKey).where(TranslationKey.key == translation.key)
        )
        translation_key = key_result.scalar_one_or_none()

        if not translation_key:
            translation_key = TranslationKey(key=translation.key, default_value=translation.value)
            db.add(translation_key)
            await db.flush()

        # Get locale
        locale_result = await db.execute(
            select(Locale).where(Locale.code == translation.locale_code)
        )
        locale = locale_result.scalar_one_or_none()

        if not locale:
            raise HTTPException(status_code=404, detail="Locale not found")

        # Create or update translation
        trans_result = await db.execute(
            select(Translation).where(
                Translation.translation_key_id == translation_key.id,
                Translation.locale_id == locale.id,
            )
        )
        existing_translation = trans_result.scalar_one_or_none()

        if existing_translation:
            existing_translation.value = translation.value
        else:
            new_translation = Translation(
                translation_key_id=translation_key.id, locale_id=locale.id, value=translation.value
            )
            db.add(new_translation)

        await db.commit()

        return {"message": "Translation saved successfully"}

    except Exception as e:
        logger.error(f"Failed to create translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/translations/{locale_code}")
async def get_translations(locale_code: str, db: AsyncSession = Depends(get_db)):
    """Get all translations for a locale"""
    try:
        query = (
            select(Translation, TranslationKey)
            .join(TranslationKey, Translation.translation_key_id == TranslationKey.id)
            .join(Locale, Translation.locale_id == Locale.id)
            .where(Locale.code == locale_code)
        )

        result = await db.execute(query)
        translations = result.all()

        return {
            translation_key.key: translation.value for translation, translation_key in translations
        }

    except Exception as e:
        logger.error(f"Failed to get translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
