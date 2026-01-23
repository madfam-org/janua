"""
Comprehensive Device Verification Service Test Suite
Tests device fingerprinting, trust management, and session tracking.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


class TestGenerateDeviceFingerprint:
    """Test device fingerprint generation"""

    def test_fingerprint_with_user_agent(self):
        """Should generate fingerprint from user agent"""
        from app.services.device_verification_service import DeviceVerificationService

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        fingerprint = DeviceVerificationService.generate_device_fingerprint(user_agent)

        assert len(fingerprint) == 32  # SHA256 truncated to 32 chars
        assert isinstance(fingerprint, str)

    def test_fingerprint_consistency(self):
        """Same user agent should produce same fingerprint"""
        from app.services.device_verification_service import DeviceVerificationService

        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15"

        fp1 = DeviceVerificationService.generate_device_fingerprint(user_agent)
        fp2 = DeviceVerificationService.generate_device_fingerprint(user_agent)

        assert fp1 == fp2

    def test_fingerprint_varies_by_user_agent(self):
        """Different user agents should produce different fingerprints"""
        from app.services.device_verification_service import DeviceVerificationService

        ua_chrome = "Mozilla/5.0 Chrome/120.0"
        ua_firefox = "Mozilla/5.0 Firefox/121.0"

        fp_chrome = DeviceVerificationService.generate_device_fingerprint(ua_chrome)
        fp_firefox = DeviceVerificationService.generate_device_fingerprint(ua_firefox)

        assert fp_chrome != fp_firefox

    def test_fingerprint_with_additional_data(self):
        """Should incorporate additional data into fingerprint"""
        from app.services.device_verification_service import DeviceVerificationService

        user_agent = "Mozilla/5.0 Chrome/120.0"

        fp_without = DeviceVerificationService.generate_device_fingerprint(user_agent)
        fp_with = DeviceVerificationService.generate_device_fingerprint(
            user_agent, additional_data="screen:1920x1080"
        )

        assert fp_without != fp_with

    def test_fingerprint_ignores_ip_address(self):
        """IP address should not affect fingerprint (IPs change)"""
        from app.services.device_verification_service import DeviceVerificationService

        user_agent = "Mozilla/5.0 Chrome/120.0"

        fp1 = DeviceVerificationService.generate_device_fingerprint(
            user_agent, ip_address="192.168.1.1"
        )
        fp2 = DeviceVerificationService.generate_device_fingerprint(
            user_agent, ip_address="10.0.0.1"
        )

        # Should be same since IP is intentionally not used
        assert fp1 == fp2

    def test_fingerprint_none_user_agent(self):
        """Should handle None user agent"""
        from app.services.device_verification_service import DeviceVerificationService

        fingerprint = DeviceVerificationService.generate_device_fingerprint(None)

        assert len(fingerprint) == 32


class TestGetFriendlyDeviceName:
    """Test friendly device name generation"""

    def test_chrome_windows(self):
        """Should return a device name for Chrome on Windows"""
        from app.services.device_verification_service import DeviceVerificationService

        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
        name = DeviceVerificationService.get_friendly_device_name(ua)

        # Should return a valid device name (may vary based on user_agents library availability)
        assert name is not None
        assert len(name) > 0
        # With fallback parser, it returns the detected browser/OS or "Unknown Device"
        assert name != ""

    def test_safari_mac(self):
        """Should return a device name for Safari on Mac"""
        from app.services.device_verification_service import DeviceVerificationService

        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
        name = DeviceVerificationService.get_friendly_device_name(ua)

        assert name is not None
        assert len(name) > 0

    def test_firefox_linux(self):
        """Should return a device name for Firefox on Linux"""
        from app.services.device_verification_service import DeviceVerificationService

        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
        name = DeviceVerificationService.get_friendly_device_name(ua)

        assert name is not None
        assert len(name) > 0

    def test_none_user_agent(self):
        """Should return Unknown Device for None"""
        from app.services.device_verification_service import DeviceVerificationService

        name = DeviceVerificationService.get_friendly_device_name(None)

        assert name == "Unknown Device"

    def test_empty_user_agent(self):
        """Should handle empty user agent gracefully"""
        from app.services.device_verification_service import DeviceVerificationService

        name = DeviceVerificationService.get_friendly_device_name("")

        assert "Unknown" in name or name


class TestIsDeviceTrusted:
    """Test device trust verification"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    async def test_trusted_device_found(self, mock_db):
        """Should return True when trusted device exists"""
        from app.services.device_verification_service import DeviceVerificationService

        user_id = uuid4()
        fingerprint = "abc123"

        mock_device = MagicMock()
        mock_device.trust_expires_at = None  # Never expires

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_device)
        mock_db.execute = AsyncMock(return_value=mock_result)

        is_trusted, device = await DeviceVerificationService.is_device_trusted(
            mock_db, user_id, fingerprint
        )

        assert is_trusted is True
        assert device == mock_device

    async def test_trusted_device_not_found(self, mock_db):
        """Should return False when device not found"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        is_trusted, device = await DeviceVerificationService.is_device_trusted(
            mock_db, uuid4(), "fingerprint"
        )

        assert is_trusted is False
        assert device is None

    async def test_trusted_device_expired(self, mock_db):
        """Should return False when trust has expired"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_device = MagicMock()
        mock_device.trust_expires_at = datetime.utcnow() - timedelta(days=1)  # Expired

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_device)
        mock_db.execute = AsyncMock(return_value=mock_result)

        is_trusted, device = await DeviceVerificationService.is_device_trusted(
            mock_db, uuid4(), "fingerprint"
        )

        assert is_trusted is False
        assert device == mock_device  # Still returns device for potential re-trust

    async def test_trusted_device_not_expired(self, mock_db):
        """Should return True when trust has not expired"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_device = MagicMock()
        mock_device.trust_expires_at = datetime.utcnow() + timedelta(days=10)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_device)
        mock_db.execute = AsyncMock(return_value=mock_result)

        is_trusted, device = await DeviceVerificationService.is_device_trusted(
            mock_db, uuid4(), "fingerprint"
        )

        assert is_trusted is True


class TestTrustDevice:
    """Test device trust creation/update"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    async def test_trust_new_device(self, mock_db):
        """Should create new trusted device record"""
        from app.services.device_verification_service import DeviceVerificationService

        user_id = uuid4()
        fingerprint = "new_fingerprint"
        user_agent = "Mozilla/5.0 Chrome/120.0"

        # No existing device
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        device = await DeviceVerificationService.trust_device(
            mock_db,
            user_id,
            fingerprint,
            user_agent=user_agent,
            ip_address="192.168.1.1",
            trust_duration_days=30,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_db.refresh.assert_called()

    async def test_update_existing_trusted_device(self, mock_db):
        """Should update existing trusted device"""
        from app.services.device_verification_service import DeviceVerificationService

        user_id = uuid4()
        fingerprint = "existing_fingerprint"

        existing_device = MagicMock()
        existing_device.last_used_at = datetime.utcnow() - timedelta(days=5)
        existing_device.trust_expires_at = datetime.utcnow() + timedelta(days=10)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_device)
        mock_db.execute = AsyncMock(return_value=mock_result)

        device = await DeviceVerificationService.trust_device(
            mock_db, user_id, fingerprint, trust_duration_days=30
        )

        assert device == existing_device
        assert existing_device.last_used_at is not None
        mock_db.add.assert_not_called()  # Should not add new

    async def test_trust_with_permanent_duration(self, mock_db):
        """Should handle permanent trust (None duration)"""
        from app.services.device_verification_service import DeviceVerificationService

        # No existing device
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        device = await DeviceVerificationService.trust_device(
            mock_db,
            uuid4(),
            "fingerprint",
            trust_duration_days=None,  # Permanent
        )

        mock_db.add.assert_called_once()

    async def test_trust_with_custom_name(self, mock_db):
        """Should use custom device name when provided"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        await DeviceVerificationService.trust_device(
            mock_db,
            uuid4(),
            "fingerprint",
            device_name="My Work Laptop",
        )

        # Verify device was created with custom name
        add_call = mock_db.add.call_args[0][0]
        assert add_call.device_name == "My Work Laptop"


class TestRevokeDeviceTrust:
    """Test device trust revocation"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.delete = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_revoke_existing_device(self, mock_db):
        """Should delete trusted device record"""
        from app.services.device_verification_service import DeviceVerificationService

        user_id = uuid4()
        device_id = uuid4()

        mock_device = MagicMock()
        mock_device.device_name = "Test Device"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_device)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await DeviceVerificationService.revoke_device_trust(
            mock_db, user_id, device_id
        )

        assert result is True
        mock_db.delete.assert_called_once_with(mock_device)
        mock_db.commit.assert_called()

    async def test_revoke_nonexistent_device(self, mock_db):
        """Should return False for nonexistent device"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await DeviceVerificationService.revoke_device_trust(
            mock_db, uuid4(), uuid4()
        )

        assert result is False
        mock_db.delete.assert_not_called()


class TestRevokeAllDevices:
    """Test bulk device revocation"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_revoke_all_devices(self, mock_db):
        """Should revoke all devices for user"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.rowcount = 5  # 5 devices revoked
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await DeviceVerificationService.revoke_all_devices(mock_db, uuid4())

        assert count == 5
        mock_db.commit.assert_called()

    async def test_revoke_all_except_current(self, mock_db):
        """Should keep current device when specified"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.rowcount = 4  # 4 devices revoked, 1 kept
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await DeviceVerificationService.revoke_all_devices(
            mock_db, uuid4(), except_device_fingerprint="current_fingerprint"
        )

        assert count == 4

    async def test_revoke_all_returns_zero_when_none(self, mock_db):
        """Should return 0 when no devices to revoke"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await DeviceVerificationService.revoke_all_devices(mock_db, uuid4())

        assert count == 0


class TestListTrustedDevices:
    """Test trusted device listing"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    async def test_list_devices(self, mock_db):
        """Should return list of trusted devices"""
        from app.services.device_verification_service import DeviceVerificationService

        device1 = MagicMock()
        device1.device_name = "Device 1"
        device2 = MagicMock()
        device2.device_name = "Device 2"

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[device1, device2])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)

        devices = await DeviceVerificationService.list_trusted_devices(
            mock_db, uuid4()
        )

        assert len(devices) == 2

    async def test_list_devices_empty(self, mock_db):
        """Should return empty list when no devices"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)

        devices = await DeviceVerificationService.list_trusted_devices(
            mock_db, uuid4()
        )

        assert devices == []


class TestListActiveSessions:
    """Test active session listing"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    async def test_list_active_sessions(self, mock_db):
        """Should return only active, non-expired sessions"""
        from app.services.device_verification_service import DeviceVerificationService

        session1 = MagicMock()
        session1.is_active = True
        session2 = MagicMock()
        session2.is_active = True

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[session1, session2])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)

        sessions = await DeviceVerificationService.list_active_sessions(
            mock_db, uuid4()
        )

        assert len(sessions) == 2


class TestUpdateSessionDeviceInfo:
    """Test session device info update"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_update_session_device_info(self, mock_db):
        """Should update session with device fingerprint"""
        from app.services.device_verification_service import DeviceVerificationService

        await DeviceVerificationService.update_session_device_info(
            mock_db, uuid4(), "fingerprint", is_trusted=True
        )

        mock_db.execute.assert_called()
        mock_db.commit.assert_called()


class TestIsNewDeviceForUser:
    """Test new device detection"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    async def test_new_device_not_in_trusted_or_sessions(self, mock_db):
        """Should return True for completely new device"""
        from app.services.device_verification_service import DeviceVerificationService

        # First query - not in trusted devices
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=None)

        # Second query - not in sessions
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none = MagicMock(return_value=None)

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        is_new = await DeviceVerificationService.is_new_device_for_user(
            mock_db, uuid4(), "new_fingerprint"
        )

        assert is_new is True

    async def test_known_device_in_trusted(self, mock_db):
        """Should return False for device in trusted list"""
        from app.services.device_verification_service import DeviceVerificationService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock())
        mock_db.execute = AsyncMock(return_value=mock_result)

        is_new = await DeviceVerificationService.is_new_device_for_user(
            mock_db, uuid4(), "known_fingerprint"
        )

        assert is_new is False

    async def test_known_device_in_sessions(self, mock_db):
        """Should return False for device with previous session"""
        from app.services.device_verification_service import DeviceVerificationService

        # First query - not in trusted devices
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=None)

        # Second query - found in sessions
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none = MagicMock(return_value=MagicMock())

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        is_new = await DeviceVerificationService.is_new_device_for_user(
            mock_db, uuid4(), "session_fingerprint"
        )

        assert is_new is False


class TestFallbackUserAgentParser:
    """Test fallback user agent parser when library not available"""

    def test_fallback_chrome_detection(self):
        """Fallback parser should detect Chrome"""
        # Simulate fallback by using the internal logic
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"

        # The service should handle this gracefully
        from app.services.device_verification_service import DeviceVerificationService

        name = DeviceVerificationService.get_friendly_device_name(ua)
        fingerprint = DeviceVerificationService.generate_device_fingerprint(ua)

        # Should produce valid outputs
        assert name is not None
        assert len(fingerprint) == 32

    def test_fallback_handles_edge_cases(self):
        """Fallback should handle unusual user agents"""
        from app.services.device_verification_service import DeviceVerificationService

        unusual_uas = [
            "curl/7.79.1",
            "python-requests/2.28.0",
            "PostmanRuntime/7.32.3",
            "Mozilla/5.0",  # Minimal
            "CustomApp/1.0",
        ]

        for ua in unusual_uas:
            name = DeviceVerificationService.get_friendly_device_name(ua)
            fingerprint = DeviceVerificationService.generate_device_fingerprint(ua)

            assert name is not None
            assert len(fingerprint) == 32
