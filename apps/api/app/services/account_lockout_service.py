"""
Account Lockout Service

Provides protection against brute-force attacks by locking accounts
after a configurable number of failed login attempts.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User

logger = structlog.get_logger(__name__)


class AccountLockoutService:
    """Service for managing account lockout functionality."""

    @staticmethod
    def is_account_locked(user: User) -> Tuple[bool, Optional[int]]:
        """
        Check if a user account is currently locked.

        Args:
            user: The user to check

        Returns:
            Tuple of (is_locked, seconds_remaining)
            - is_locked: True if account is locked
            - seconds_remaining: Seconds until unlock, or None if not locked
        """
        if not settings.ACCOUNT_LOCKOUT_ENABLED:
            return False, None

        if not user.locked_until:
            return False, None

        now = datetime.utcnow()
        if user.locked_until > now:
            seconds_remaining = int((user.locked_until - now).total_seconds())
            return True, seconds_remaining

        return False, None

    @staticmethod
    async def record_failed_attempt(
        db: AsyncSession,
        user: User,
        ip_address: Optional[str] = None,
    ) -> Tuple[bool, Optional[int]]:
        """
        Record a failed login attempt for a user.

        Args:
            db: Database session
            user: The user who failed to authenticate
            ip_address: Optional IP address of the attempt

        Returns:
            Tuple of (is_now_locked, seconds_until_unlock)
        """
        if not settings.ACCOUNT_LOCKOUT_ENABLED:
            return False, None

        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        user.last_failed_login = datetime.utcnow()

        logger.warning(
            "Failed login attempt recorded",
            user_id=str(user.id),
            email=user.email,
            failed_attempts=user.failed_login_attempts,
            threshold=settings.ACCOUNT_LOCKOUT_THRESHOLD,
            ip_address=ip_address,
        )

        # Check if we should lock the account
        if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
            lock_duration = timedelta(minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES)
            user.locked_until = datetime.utcnow() + lock_duration
            seconds_until_unlock = int(lock_duration.total_seconds())

            logger.warning(
                "Account locked due to too many failed attempts",
                user_id=str(user.id),
                email=user.email,
                failed_attempts=user.failed_login_attempts,
                locked_until=user.locked_until.isoformat(),
                lock_duration_minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES,
                ip_address=ip_address,
            )

            await db.commit()
            return True, seconds_until_unlock

        await db.commit()
        return False, None

    @staticmethod
    async def reset_failed_attempts(
        db: AsyncSession,
        user: User,
    ) -> None:
        """
        Reset failed login attempts after successful authentication.

        Args:
            db: Database session
            user: The user who successfully authenticated
        """
        if not settings.ACCOUNT_LOCKOUT_ENABLED:
            return

        if not settings.ACCOUNT_LOCKOUT_RESET_ON_SUCCESS:
            return

        if user.failed_login_attempts and user.failed_login_attempts > 0:
            previous_attempts = user.failed_login_attempts
            user.failed_login_attempts = 0
            user.locked_until = None
            await db.commit()

            logger.info(
                "Failed login attempts reset after successful login",
                user_id=str(user.id),
                email=user.email,
                previous_failed_attempts=previous_attempts,
            )

    @staticmethod
    async def unlock_account(
        db: AsyncSession,
        user_id: UUID,
        admin_user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Manually unlock a user account (admin function).

        Args:
            db: Database session
            user_id: ID of the user to unlock
            admin_user_id: Optional ID of admin performing the unlock

        Returns:
            True if account was unlocked, False if user not found
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

        logger.info(
            "Account manually unlocked",
            user_id=str(user_id),
            email=user.email,
            admin_user_id=str(admin_user_id) if admin_user_id else None,
        )

        return True

    @staticmethod
    async def get_lockout_status(
        db: AsyncSession,
        user_id: UUID,
    ) -> dict:
        """
        Get the lockout status for a user (admin function).

        Args:
            db: Database session
            user_id: ID of the user to check

        Returns:
            Dict with lockout status information
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return {"error": "User not found"}

        is_locked, seconds_remaining = AccountLockoutService.is_account_locked(user)

        return {
            "user_id": str(user_id),
            "email": user.email,
            "is_locked": is_locked,
            "seconds_until_unlock": seconds_remaining,
            "failed_login_attempts": user.failed_login_attempts or 0,
            "lockout_threshold": settings.ACCOUNT_LOCKOUT_THRESHOLD,
            "last_failed_login": user.last_failed_login.isoformat()
            if user.last_failed_login
            else None,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        }
