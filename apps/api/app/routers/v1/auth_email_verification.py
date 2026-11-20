"""Email verification: POST /auth/verify-email, POST /auth/email/verify, POST /auth/email/resend-verification.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import secrets
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_schemas import VerifyEmailRequest
from app.routers.v1.auth_shared import limiter, router
from app.services.email_service import send_verification_email_task

from ...models import EmailVerification, User


# Alias for /email/verify (tests expect /verify-email)
@router.post("/verify-email")
async def verify_email_alias(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with token (alias for /email/verify)"""
    return await verify_email(request, db)


@router.post("/email/verify")
async def verify_email(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with token"""
    # Find valid verification token
    result = await db.execute(
        select(EmailVerification).where(
            EmailVerification.token == request.token,
            # The model records use as a timestamp; it has no boolean
            # `verified` column, and referencing one raised AttributeError,
            # so every verification link answered 500.
            EmailVerification.verified_at.is_(None),
            EmailVerification.expires_at > datetime.utcnow(),
        )
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    # Mark email as verified
    user = await db.get(User, verification.user_id)
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()

    # Mark verification as used
    verification.verified_at = datetime.utcnow()

    await db.commit()

    # Log activity
    await _auth_shared.log_activity(db, str(user.id), "email_verified", {})
    await _auth_shared.log_audit_event(db, str(user.id), "email_verified", {})

    return {"message": "Email successfully verified"}


@router.post("/email/resend-verification")
@limiter.limit("5/hour")  # Rate limiting for email verification requests
async def resend_verification_email(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resend verification email"""
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")

    # Create new verification token
    verification_token = secrets.token_urlsafe(32)
    verification = EmailVerification(
        user_id=current_user.id,
        token=verification_token,
        email=current_user.email,
        expires_at=datetime.utcnow() + timedelta(hours=48),
    )
    db.add(verification)
    await db.commit()

    # Send email in background
    background_tasks.add_task(
        send_verification_email_task,
        current_user.email,
        verification_token,
        locale=getattr(current_user, "locale", None),
        org_id=getattr(current_user, "tenant_id", None),
        formality=getattr(current_user, "spanish_formality", None),
    )

    return {"message": "Verification email sent"}
