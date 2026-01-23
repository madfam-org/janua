"""
Comprehensive Account Lockout Service Test Suite
Tests account lockout functionality including brute-force protection,
failed attempt tracking, and manual unlock operations.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


class TestIsAccountLocked:
    """Test account lock status checking"""

    def test_lockout_disabled_returns_not_locked(self):
        """Account should never be locked when feature is disabled"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        mock_user.locked_until = datetime.utcnow() + timedelta(hours=1)

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = False

            is_locked, seconds = AccountLockoutService.is_account_locked(mock_user)

            assert is_locked is False
            assert seconds is None

    def test_no_locked_until_returns_not_locked(self):
        """Account without locked_until should not be locked"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        mock_user.locked_until = None

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True

            is_locked, seconds = AccountLockoutService.is_account_locked(mock_user)

            assert is_locked is False
            assert seconds is None

    def test_locked_until_in_future_returns_locked(self):
        """Account with future locked_until should be locked"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        # Lock for 30 more minutes
        mock_user.locked_until = datetime.utcnow() + timedelta(minutes=30)

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True

            is_locked, seconds = AccountLockoutService.is_account_locked(mock_user)

            assert is_locked is True
            assert seconds is not None
            # Should be approximately 30 minutes (1800 seconds), allow some tolerance
            assert 1790 <= seconds <= 1810

    def test_locked_until_in_past_returns_not_locked(self):
        """Account with past locked_until should not be locked"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        # Lock expired 5 minutes ago
        mock_user.locked_until = datetime.utcnow() - timedelta(minutes=5)

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True

            is_locked, seconds = AccountLockoutService.is_account_locked(mock_user)

            assert is_locked is False
            assert seconds is None

    def test_locked_until_edge_case_now(self):
        """Account with locked_until at current time should not be locked"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        mock_user.locked_until = datetime.utcnow()

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True

            is_locked, seconds = AccountLockoutService.is_account_locked(mock_user)

            assert is_locked is False


class TestRecordFailedAttempt:
    """Test failed login attempt recording"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.locked_until = None
        return user

    async def test_lockout_disabled_returns_not_locked(self, mock_db, mock_user):
        """Should not lock when feature is disabled"""
        from app.services.account_lockout_service import AccountLockoutService

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = False

            is_locked, seconds = await AccountLockoutService.record_failed_attempt(
                mock_db, mock_user, "192.168.1.1"
            )

            assert is_locked is False
            assert seconds is None
            mock_db.commit.assert_not_called()

    async def test_increments_failed_attempts(self, mock_db, mock_user):
        """Should increment failed attempt counter"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user.failed_login_attempts = 2

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5
            mock_settings.ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

            await AccountLockoutService.record_failed_attempt(
                mock_db, mock_user, "192.168.1.1"
            )

            assert mock_user.failed_login_attempts == 3
            assert mock_user.last_failed_login is not None

    async def test_locks_account_at_threshold(self, mock_db, mock_user):
        """Should lock account when threshold is reached"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user.failed_login_attempts = 4  # One away from threshold

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5
            mock_settings.ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

            is_locked, seconds = await AccountLockoutService.record_failed_attempt(
                mock_db, mock_user, "192.168.1.1"
            )

            assert is_locked is True
            assert seconds == 30 * 60  # 30 minutes in seconds
            assert mock_user.locked_until is not None
            mock_db.commit.assert_called()

    async def test_does_not_lock_before_threshold(self, mock_db, mock_user):
        """Should not lock account before threshold is reached"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user.failed_login_attempts = 1

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5
            mock_settings.ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

            is_locked, seconds = await AccountLockoutService.record_failed_attempt(
                mock_db, mock_user, "192.168.1.1"
            )

            assert is_locked is False
            assert seconds is None
            assert mock_user.locked_until is None

    async def test_handles_none_failed_attempts(self, mock_db, mock_user):
        """Should handle case where failed_login_attempts is None"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user.failed_login_attempts = None

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5
            mock_settings.ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

            await AccountLockoutService.record_failed_attempt(mock_db, mock_user)

            assert mock_user.failed_login_attempts == 1

    async def test_configurable_lock_duration(self, mock_db, mock_user):
        """Should use configured lock duration"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user.failed_login_attempts = 4

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5
            mock_settings.ACCOUNT_LOCKOUT_DURATION_MINUTES = 60  # 1 hour

            is_locked, seconds = await AccountLockoutService.record_failed_attempt(
                mock_db, mock_user
            )

            assert is_locked is True
            assert seconds == 60 * 60  # 1 hour in seconds


class TestResetFailedAttempts:
    """Test resetting failed attempts after successful login"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.failed_login_attempts = 3
        user.locked_until = datetime.utcnow() + timedelta(hours=1)
        return user

    async def test_resets_when_enabled(self, mock_db, mock_user):
        """Should reset attempts when feature is enabled"""
        from app.services.account_lockout_service import AccountLockoutService

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_RESET_ON_SUCCESS = True

            await AccountLockoutService.reset_failed_attempts(mock_db, mock_user)

            assert mock_user.failed_login_attempts == 0
            assert mock_user.locked_until is None
            mock_db.commit.assert_called()

    async def test_no_reset_when_disabled(self, mock_db, mock_user):
        """Should not reset when feature is disabled"""
        from app.services.account_lockout_service import AccountLockoutService

        original_attempts = mock_user.failed_login_attempts

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = False

            await AccountLockoutService.reset_failed_attempts(mock_db, mock_user)

            assert mock_user.failed_login_attempts == original_attempts
            mock_db.commit.assert_not_called()

    async def test_no_reset_when_reset_on_success_disabled(self, mock_db, mock_user):
        """Should not reset when reset on success is disabled"""
        from app.services.account_lockout_service import AccountLockoutService

        original_attempts = mock_user.failed_login_attempts

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_RESET_ON_SUCCESS = False

            await AccountLockoutService.reset_failed_attempts(mock_db, mock_user)

            assert mock_user.failed_login_attempts == original_attempts

    async def test_no_commit_when_no_failed_attempts(self, mock_db, mock_user):
        """Should not commit when there are no failed attempts to reset"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user.failed_login_attempts = 0

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_RESET_ON_SUCCESS = True

            await AccountLockoutService.reset_failed_attempts(mock_db, mock_user)

            mock_db.commit.assert_not_called()


class TestUnlockAccount:
    """Test manual account unlock functionality"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_unlock_existing_user(self, mock_db):
        """Should unlock existing user account"""
        from app.services.account_lockout_service import AccountLockoutService

        user_id = uuid4()
        admin_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "locked@example.com"
        mock_user.failed_login_attempts = 5
        mock_user.locked_until = datetime.utcnow() + timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AccountLockoutService.unlock_account(mock_db, user_id, admin_id)

        assert result is True
        assert mock_user.failed_login_attempts == 0
        assert mock_user.locked_until is None
        mock_db.commit.assert_called()

    async def test_unlock_nonexistent_user(self, mock_db):
        """Should return False for nonexistent user"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AccountLockoutService.unlock_account(mock_db, uuid4())

        assert result is False

    async def test_unlock_without_admin_id(self, mock_db):
        """Should work without admin ID"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "user@example.com"
        mock_user.failed_login_attempts = 3
        mock_user.locked_until = datetime.utcnow() + timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AccountLockoutService.unlock_account(mock_db, mock_user.id)

        assert result is True


class TestGetLockoutStatus:
    """Test lockout status retrieval"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    async def test_get_status_for_existing_user(self, mock_db):
        """Should return full status for existing user"""
        from app.services.account_lockout_service import AccountLockoutService

        user_id = uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "user@example.com"
        mock_user.failed_login_attempts = 3
        mock_user.last_failed_login = datetime.utcnow()
        mock_user.locked_until = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5

            status = await AccountLockoutService.get_lockout_status(mock_db, user_id)

            assert status["user_id"] == str(user_id)
            assert status["email"] == "user@example.com"
            assert status["failed_login_attempts"] == 3
            assert status["lockout_threshold"] == 5
            assert status["is_locked"] is False

    async def test_get_status_for_locked_user(self, mock_db):
        """Should return locked status for locked user"""
        from app.services.account_lockout_service import AccountLockoutService

        user_id = uuid4()
        locked_until = datetime.utcnow() + timedelta(minutes=30)

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "locked@example.com"
        mock_user.failed_login_attempts = 5
        mock_user.last_failed_login = datetime.utcnow() - timedelta(minutes=1)
        mock_user.locked_until = locked_until

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5

            status = await AccountLockoutService.get_lockout_status(mock_db, user_id)

            assert status["is_locked"] is True
            assert status["seconds_until_unlock"] is not None
            assert status["locked_until"] is not None

    async def test_get_status_for_nonexistent_user(self, mock_db):
        """Should return error for nonexistent user"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        status = await AccountLockoutService.get_lockout_status(mock_db, uuid4())

        assert "error" in status
        assert status["error"] == "User not found"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_exactly_at_threshold(self):
        """Test behavior exactly at lockout threshold"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        mock_user.failed_login_attempts = 5  # At threshold
        mock_user.locked_until = datetime.utcnow() + timedelta(minutes=1)

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 5

            is_locked, _ = AccountLockoutService.is_account_locked(mock_user)
            assert is_locked is True

    def test_zero_lock_duration(self):
        """Test with zero lock duration configured"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_user = MagicMock()
        mock_user.locked_until = datetime.utcnow()  # Effectively not locked

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True

            is_locked, seconds = AccountLockoutService.is_account_locked(mock_user)

            assert is_locked is False

    async def test_concurrent_failed_attempts(self):
        """Test handling of concurrent failed attempts"""
        from app.services.account_lockout_service import AccountLockoutService

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "user@example.com"
        mock_user.failed_login_attempts = 3

        with patch("app.services.account_lockout_service.settings") as mock_settings:
            mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
            mock_settings.ACCOUNT_LOCKOUT_THRESHOLD = 10
            mock_settings.ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

            # Simulate multiple concurrent calls
            await AccountLockoutService.record_failed_attempt(mock_db, mock_user)
            mock_user.failed_login_attempts = 4  # Simulate concurrent increment
            await AccountLockoutService.record_failed_attempt(mock_db, mock_user)

            assert mock_user.failed_login_attempts == 5
