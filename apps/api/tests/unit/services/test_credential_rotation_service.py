"""
Comprehensive Credential Rotation Service Test Suite
Tests OAuth client secret rotation, validation, and lifecycle management.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


class TestGenerateSecret:
    """Test secret generation functionality"""

    def test_generate_secret_format(self):
        """Secret should have correct format with prefix"""
        from app.services.credential_rotation_service import CredentialRotationService

        plain, hashed, prefix = CredentialRotationService.generate_secret()

        assert plain.startswith("jns_")
        assert len(plain) > 48  # prefix + random part
        assert prefix.endswith("...")
        assert prefix.startswith("jns_")
        assert len(prefix) == 15  # 12 chars + "..."

    def test_generate_secret_uniqueness(self):
        """Each call should generate unique secrets"""
        from app.services.credential_rotation_service import CredentialRotationService

        secrets = set()
        for _ in range(100):
            plain, _, _ = CredentialRotationService.generate_secret()
            secrets.add(plain)

        assert len(secrets) == 100  # All should be unique

    def test_generate_secret_hash_format(self):
        """Hashed secret should be valid bcrypt hash"""
        from app.services.credential_rotation_service import CredentialRotationService

        _, hashed, _ = CredentialRotationService.generate_secret()

        # bcrypt hashes start with $2a$, $2b$, or $2y$
        assert hashed.startswith("$2")
        assert len(hashed) == 60  # bcrypt hash length

    def test_generated_secret_verifiable(self):
        """Generated secret should be verifiable against its hash"""
        import bcrypt

        from app.services.credential_rotation_service import CredentialRotationService

        plain, hashed, _ = CredentialRotationService.generate_secret()

        # Verify using bcrypt directly
        assert bcrypt.checkpw(plain.encode(), hashed.encode())


class TestGetActiveSecrets:
    """Test active secrets retrieval"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    async def test_returns_active_secrets(self, service):
        """Should return only active (non-expired, non-revoked) secrets"""
        client_id = uuid4()

        mock_secret1 = MagicMock()
        mock_secret1.is_valid = MagicMock(return_value=True)
        mock_secret2 = MagicMock()
        mock_secret2.is_valid = MagicMock(return_value=True)

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_secret1, mock_secret2])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        service.db.execute = AsyncMock(return_value=mock_result)

        secrets = await service.get_active_secrets(client_id)

        assert len(secrets) == 2
        service.db.execute.assert_called_once()

    async def test_returns_empty_list_when_no_secrets(self, service):
        """Should return empty list when no active secrets exist"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        service.db.execute = AsyncMock(return_value=mock_result)

        secrets = await service.get_active_secrets(uuid4())

        assert secrets == []


class TestValidateSecret:
    """Test secret validation"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    async def test_validate_with_rotation_disabled_legacy(self, service):
        """Should fall back to legacy validation when rotation disabled"""
        mock_client = MagicMock()
        mock_client.verify_secret = MagicMock(return_value=True)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_ENABLED = False

            result = await service.validate_secret(mock_client, "test_secret")

            assert result is None  # None indicates valid legacy secret
            mock_client.verify_secret.assert_called_once_with("test_secret")

    async def test_validate_with_rotation_disabled_invalid(self, service):
        """Should return None for invalid legacy secret when rotation disabled"""
        mock_client = MagicMock()
        mock_client.verify_secret = MagicMock(return_value=False)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_ENABLED = False

            result = await service.validate_secret(mock_client, "invalid_secret")

            assert result is None

    async def test_validate_against_active_secrets(self, service):
        """Should validate against all active secrets"""
        mock_client = MagicMock()
        mock_client.id = uuid4()
        mock_client.verify_secret = MagicMock(return_value=False)

        mock_secret = MagicMock()
        mock_secret.verify = MagicMock(return_value=True)
        mock_secret.last_used_at = None

        # Mock get_active_secrets
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_secret])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)
        service.db.commit = AsyncMock()

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_ENABLED = True

            result = await service.validate_secret(mock_client, "valid_secret")

            assert result == mock_secret
            mock_secret.verify.assert_called_once_with("valid_secret")
            assert mock_secret.last_used_at is not None

    async def test_validate_updates_last_used(self, service):
        """Should update last_used_at on successful validation"""
        mock_client = MagicMock()
        mock_client.id = uuid4()

        mock_secret = MagicMock()
        mock_secret.verify = MagicMock(return_value=True)
        mock_secret.last_used_at = None

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_secret])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)
        service.db.commit = AsyncMock()

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_ENABLED = True

            await service.validate_secret(mock_client, "secret")

            assert mock_secret.last_used_at is not None
            service.db.commit.assert_called()

    async def test_validate_fallback_to_legacy(self, service):
        """Should fall back to legacy secret if no rotation secrets match"""
        mock_client = MagicMock()
        mock_client.id = uuid4()
        mock_client.verify_secret = MagicMock(return_value=True)

        # No active secrets
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_ENABLED = True

            result = await service.validate_secret(mock_client, "legacy_secret")

            assert result is None
            mock_client.verify_secret.assert_called()


class TestRotateSecret:
    """Test secret rotation functionality"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.id = uuid4()
        client.client_id = "test_client_id"
        client.client_secret_hash = "old_hash"
        client.client_secret_prefix = "old_prefix"
        return client

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid4()
        return user

    async def test_rotate_creates_new_primary_secret(
        self, service, mock_client, mock_user
    ):
        """Should create new primary secret"""
        # Mock no existing secrets
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_GRACE_HOURS = 24

            new_secret, plain = await service.rotate_secret(mock_client, mock_user)

            assert plain.startswith("jns_")
            assert service.db.add.called
            assert service.db.commit.called

    async def test_rotate_sets_expiry_on_old_secrets(
        self, service, mock_client, mock_user
    ):
        """Should set expiry on existing secrets"""
        old_secret = MagicMock()
        old_secret.is_primary = True
        old_secret.expires_at = None

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[old_secret])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_GRACE_HOURS = 24

            await service.rotate_secret(mock_client, mock_user, grace_hours=12)

            assert old_secret.is_primary is False
            assert old_secret.expires_at is not None

    async def test_rotate_uses_custom_grace_period(
        self, service, mock_client, mock_user
    ):
        """Should use custom grace period when provided"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_GRACE_HOURS = 24

            # Use 48 hours grace period
            await service.rotate_secret(mock_client, mock_user, grace_hours=48)

            # Verify audit log was created with correct grace hours
            add_calls = service.db.add.call_args_list
            # Find the AuditLog call (should have details with grace_hours)
            for call in add_calls:
                obj = call[0][0]
                if hasattr(obj, "details") and obj.details:
                    if "grace_hours" in obj.details:
                        assert obj.details["grace_hours"] == 48

    async def test_rotate_updates_client_legacy_secret(
        self, service, mock_client, mock_user
    ):
        """Should update client's legacy secret hash for compatibility"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_ROTATION_GRACE_HOURS = 24

            await service.rotate_secret(mock_client, mock_user)

            assert mock_client.client_secret_hash != "old_hash"
            assert mock_client.client_secret_prefix != "old_prefix"
            assert mock_client.updated_at is not None


class TestRevokeSecret:
    """Test secret revocation"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid4()
        return user

    async def test_revoke_existing_secret(self, service, mock_user):
        """Should revoke existing secret"""
        secret_id = uuid4()
        mock_secret = MagicMock()
        mock_secret.id = secret_id
        mock_secret.client_id = uuid4()
        mock_secret.secret_prefix = "jns_test..."
        mock_secret.revoked_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_secret)
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.revoke_secret(secret_id, mock_user)

        assert result is True
        assert mock_secret.revoked_at is not None
        assert mock_secret.revoked_by == mock_user.id
        service.db.commit.assert_called()

    async def test_revoke_nonexistent_secret(self, service, mock_user):
        """Should return False for nonexistent secret"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.revoke_secret(uuid4(), mock_user)

        assert result is False

    async def test_revoke_already_revoked_secret(self, service, mock_user):
        """Should return True for already revoked secret"""
        mock_secret = MagicMock()
        mock_secret.revoked_at = datetime.utcnow()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_secret)
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.revoke_secret(uuid4(), mock_user)

        assert result is True


class TestRevokeAllExceptPrimary:
    """Test bulk revocation functionality"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.id = uuid4()
        client.client_id = "test_client"
        return client

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid4()
        return user

    async def test_revoke_all_non_primary(self, service, mock_client, mock_user):
        """Should revoke all non-primary secrets"""
        secret1 = MagicMock()
        secret1.revoked_at = None
        secret2 = MagicMock()
        secret2.revoked_at = None

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[secret1, secret2])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        count = await service.revoke_all_except_primary(mock_client, mock_user)

        assert count == 2
        assert secret1.revoked_at is not None
        assert secret2.revoked_at is not None
        service.db.commit.assert_called()

    async def test_revoke_none_when_empty(self, service, mock_client, mock_user):
        """Should return 0 when no non-primary secrets exist"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        count = await service.revoke_all_except_primary(mock_client, mock_user)

        assert count == 0


class TestGetSecretStatus:
    """Test secret status retrieval"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.id = uuid4()
        return client

    async def test_get_status_with_secrets(self, service, mock_client):
        """Should return comprehensive status"""
        primary_secret = MagicMock()
        primary_secret.id = uuid4()
        primary_secret.is_primary = True
        primary_secret.created_at = datetime.utcnow() - timedelta(days=10)
        primary_secret.expires_at = None
        primary_secret.revoked_at = None
        primary_secret.last_used_at = datetime.utcnow()
        primary_secret.secret_prefix = "jns_abc..."
        primary_secret.is_valid = MagicMock(return_value=True)

        # First call returns active secrets
        mock_scalars1 = MagicMock()
        mock_scalars1.all = MagicMock(return_value=[primary_secret])
        mock_result1 = MagicMock()
        mock_result1.scalars = MagicMock(return_value=mock_scalars1)

        # Second call returns all secrets
        mock_scalars2 = MagicMock()
        mock_scalars2.all = MagicMock(return_value=[primary_secret])
        mock_result2 = MagicMock()
        mock_result2.scalars = MagicMock(return_value=mock_scalars2)

        service.db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_MAX_AGE_DAYS = 90

            status = await service.get_secret_status(mock_client)

            assert status["active_count"] == 1
            assert status["has_primary"] is True
            assert status["rotation_recommended"] is False
            assert len(status["secrets"]) == 1

    async def test_get_status_recommends_rotation_for_old_secrets(
        self, service, mock_client
    ):
        """Should recommend rotation when primary secret is old"""
        old_secret = MagicMock()
        old_secret.id = uuid4()
        old_secret.is_primary = True
        old_secret.created_at = datetime.utcnow() - timedelta(days=100)  # Old
        old_secret.expires_at = None
        old_secret.revoked_at = None
        old_secret.last_used_at = None
        old_secret.secret_prefix = "jns_old..."
        old_secret.is_valid = MagicMock(return_value=True)

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[old_secret])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.credential_rotation_service.settings"
        ) as mock_settings:
            mock_settings.CLIENT_SECRET_MAX_AGE_DAYS = 90

            status = await service.get_secret_status(mock_client)

            assert status["rotation_recommended"] is True


class TestCleanupExpiredSecrets:
    """Test expired secret cleanup"""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()
        from app.services.credential_rotation_service import CredentialRotationService

        return CredentialRotationService(mock_db)

    async def test_cleanup_deletes_old_expired_secrets(self, service):
        """Should delete expired secrets older than 30 days"""
        expired_secret = MagicMock()
        expired_secret.created_at = datetime.utcnow() - timedelta(days=40)
        expired_secret.expires_at = datetime.utcnow() - timedelta(days=35)

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[expired_secret])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        count = await service.cleanup_expired_secrets()

        assert count == 1
        service.db.delete.assert_called_once_with(expired_secret)
        service.db.commit.assert_called()

    async def test_cleanup_returns_zero_when_none_expired(self, service):
        """Should return 0 when no secrets to clean up"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        service.db.execute = AsyncMock(return_value=mock_result)

        count = await service.cleanup_expired_secrets()

        assert count == 0
        service.db.commit.assert_not_called()
