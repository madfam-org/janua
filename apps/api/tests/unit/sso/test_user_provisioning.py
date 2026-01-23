"""
Comprehensive User Provisioning Service Test Suite
Tests JIT provisioning, user updates, and access validation for SSO.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the module for patching
from app.sso.domain.services import user_provisioning as user_provisioning_module

pytestmark = pytest.mark.asyncio


class TestUserProvisioning:
    """Test user provisioning from SSO authentication"""

    @pytest.fixture
    def mock_db(self):
        """Mock async database session"""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_audit_logger(self):
        """Mock audit logger"""
        logger = AsyncMock()
        logger.log_event = AsyncMock()
        return logger

    @pytest.fixture
    def provisioning_service(self, mock_db, mock_audit_logger):
        """Create user provisioning service"""
        from app.sso.domain.services.user_provisioning import UserProvisioningService

        return UserProvisioningService(db=mock_db, audit_logger=mock_audit_logger)

    @pytest.fixture
    def user_data(self):
        """Sample user provisioning data"""
        from app.sso.domain.protocols.base import UserProvisioningData

        return UserProvisioningData(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            display_name="Test User",
            attributes={"sub": "user_123"},
        )

    @pytest.fixture
    def sso_config(self):
        """Sample SSO configuration"""
        from app.sso.domain.protocols.base import SSOConfiguration

        return SSOConfiguration(
            organization_id="org_123",
            protocol="saml2",
            provider_name="Test IdP",
            config={},
            jit_provisioning=True,
            default_role="member",
        )

    async def test_provision_new_user_with_jit_enabled(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should create new user when JIT provisioning is enabled"""
        # Mock _find_existing_user to return None (no existing user)
        with patch.object(
            provisioning_service, "_find_existing_user", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = None

            with patch.object(
                provisioning_service, "_create_new_user", new_callable=AsyncMock
            ) as mock_create:
                mock_user = MagicMock()
                mock_user.id = "user_456"
                mock_create.return_value = mock_user

                result = await provisioning_service.provision_user(
                    user_data=user_data,
                    organization_id="org_123",
                    sso_config=sso_config,
                )

                mock_find.assert_called_once_with("test@example.com", "org_123")
                mock_create.assert_called_once()
                assert result.id == "user_456"

    async def test_provision_existing_user_with_jit_update(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should update existing user when JIT provisioning allows updates"""
        # Mock existing user found
        mock_user = MagicMock()
        mock_user.id = "existing_user"
        mock_user.first_name = "Old"
        mock_user.last_name = "Name"

        with patch.object(
            provisioning_service, "_find_existing_user", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_user

            with patch.object(
                provisioning_service, "_update_existing_user", new_callable=AsyncMock
            ) as mock_update:
                mock_update.return_value = mock_user

                result = await provisioning_service.provision_user(
                    user_data=user_data,
                    organization_id="org_123",
                    sso_config=sso_config,
                )

                mock_update.assert_called_once()
                assert result.id == "existing_user"

    async def test_provision_existing_user_without_jit(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should return existing user without update when JIT is disabled"""
        sso_config.jit_provisioning = False

        # Mock existing user found
        mock_user = MagicMock()
        mock_user.id = "existing_user"

        with patch.object(
            provisioning_service, "_find_existing_user", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_user

            result = await provisioning_service.provision_user(
                user_data=user_data,
                organization_id="org_123",
                sso_config=sso_config,
            )

            assert result.id == "existing_user"

    async def test_provision_new_user_jit_disabled_raises_error(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should raise error when new user and JIT provisioning is disabled"""
        from app.sso.exceptions import ValidationError

        sso_config.jit_provisioning = False

        # Mock no existing user found
        with patch.object(
            provisioning_service, "_find_existing_user", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = None

            with pytest.raises(ValidationError) as exc_info:
                await provisioning_service.provision_user(
                    user_data=user_data,
                    organization_id="org_123",
                    sso_config=sso_config,
                )

            assert "not found" in str(exc_info.value)
            assert "JIT provisioning is disabled" in str(exc_info.value)


class TestCreateNewUser:
    """Test new user creation"""

    @pytest.fixture
    def mock_db(self):
        """Mock async database session"""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def provisioning_service(self, mock_db):
        """Create user provisioning service"""
        from app.sso.domain.services.user_provisioning import UserProvisioningService

        return UserProvisioningService(db=mock_db, audit_logger=None)

    @pytest.fixture
    def user_data(self):
        """Sample user provisioning data"""
        from app.sso.domain.protocols.base import UserProvisioningData

        return UserProvisioningData(
            email="new@example.com",
            first_name="New",
            last_name="User",
            display_name=None,
            attributes={"sub": "user_new"},
        )

    @pytest.fixture
    def sso_config(self):
        """Sample SSO configuration"""
        from app.sso.domain.protocols.base import SSOConfiguration

        return SSOConfiguration(
            organization_id="org_123",
            protocol="saml2",
            provider_name="Test IdP",
            config={},
            jit_provisioning=True,
            default_role="member",
        )

    async def test_create_user_with_all_fields(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should create user with all SSO fields populated"""
        # Mock organization exists
        mock_org = MagicMock()
        mock_org.id = "org_123"
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_org)
        )

        # Mock User class to avoid model schema issues
        with patch.object(user_provisioning_module, "User") as mock_user_class:
            mock_user = MagicMock()
            mock_user.id = "new_user_123"
            mock_user_class.return_value = mock_user

            result = await provisioning_service._create_new_user(
                user_data=user_data,
                organization_id="org_123",
                sso_config=sso_config,
            )

            # Verify User was instantiated with correct data
            mock_user_class.assert_called_once()
            call_kwargs = mock_user_class.call_args.kwargs
            assert call_kwargs["email"] == "new@example.com"
            assert call_kwargs["first_name"] == "New"
            assert call_kwargs["last_name"] == "User"
            assert call_kwargs["organization_id"] == "org_123"
            assert call_kwargs["is_active"] is True
            assert call_kwargs["email_verified"] is True

            # Verify db operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    async def test_create_user_organization_not_found(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should raise error when organization not found"""
        from app.sso.exceptions import ValidationError

        # Mock organization not found
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        )

        with pytest.raises(ValidationError) as exc_info:
            await provisioning_service._create_new_user(
                user_data=user_data,
                organization_id="nonexistent_org",
                sso_config=sso_config,
            )

        assert "Organization" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


class TestUpdateExistingUser:
    """Test existing user updates"""

    @pytest.fixture
    def mock_db(self):
        """Mock async database session"""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def provisioning_service(self, mock_db):
        """Create user provisioning service"""
        from app.sso.domain.services.user_provisioning import UserProvisioningService

        return UserProvisioningService(db=mock_db, audit_logger=None)

    @pytest.fixture
    def user_data(self):
        """Sample user provisioning data with updates"""
        from app.sso.domain.protocols.base import UserProvisioningData

        return UserProvisioningData(
            email="user@example.com",
            first_name="Updated",
            last_name="Name",
            display_name="Updated Name",
            attributes={"sub": "user_123"},
        )

    @pytest.fixture
    def sso_config(self):
        """Sample SSO configuration"""
        from app.sso.domain.protocols.base import SSOConfiguration

        return SSOConfiguration(
            organization_id="org_123",
            protocol="oidc",
            provider_name="Test OIDC IdP",
            config={},
            jit_provisioning=True,
            default_role="member",
        )

    async def test_update_user_first_name(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should update user first name when changed"""
        mock_user = MagicMock()
        mock_user.first_name = "Old"
        mock_user.last_name = "Name"
        mock_user.display_name = "Old Name"
        mock_user.sso_provider = "oidc"
        mock_user.sso_subject_id = "user_123"

        result = await provisioning_service._update_existing_user(
            user=mock_user,
            user_data=user_data,
            sso_config=sso_config,
        )

        assert mock_user.first_name == "Updated"
        mock_db.commit.assert_called_once()

    async def test_update_user_no_changes(
        self, provisioning_service, sso_config, mock_db
    ):
        """Should not commit when no changes needed"""
        from app.sso.domain.protocols.base import UserProvisioningData

        user_data = UserProvisioningData(
            email="user@example.com",
            first_name="Same",
            last_name="Name",
            display_name="Same Name",
            attributes={"sub": "user_123"},
        )

        mock_user = MagicMock()
        mock_user.first_name = "Same"
        mock_user.last_name = "Name"
        mock_user.display_name = "Same Name"
        mock_user.sso_provider = "oidc"
        mock_user.sso_subject_id = "user_123"

        result = await provisioning_service._update_existing_user(
            user=mock_user,
            user_data=user_data,
            sso_config=sso_config,
        )

        mock_db.commit.assert_not_called()

    async def test_update_user_sso_provider_change(
        self, provisioning_service, user_data, sso_config, mock_db
    ):
        """Should update SSO provider when changed"""
        mock_user = MagicMock()
        mock_user.first_name = "Updated"
        mock_user.last_name = "Name"
        mock_user.display_name = "Updated Name"
        mock_user.sso_provider = "saml2"  # Different from config
        mock_user.sso_subject_id = "user_123"

        result = await provisioning_service._update_existing_user(
            user=mock_user,
            user_data=user_data,
            sso_config=sso_config,
        )

        assert mock_user.sso_provider == "oidc"
        mock_db.commit.assert_called_once()


class TestValidateUserAccess:
    """Test user access validation"""

    @pytest.fixture
    def provisioning_service(self):
        """Create user provisioning service"""
        from app.sso.domain.services.user_provisioning import UserProvisioningService

        return UserProvisioningService(db=AsyncMock(), audit_logger=None)

    @pytest.fixture
    def sso_config(self):
        """Sample SSO configuration"""
        from app.sso.domain.protocols.base import SSOConfiguration

        return SSOConfiguration(
            organization_id="org_123",
            protocol="saml2",
            provider_name="Test IdP",
            config={},
            jit_provisioning=True,
            default_role="member",
        )

    async def test_validate_active_user(self, provisioning_service, sso_config):
        """Should allow active user"""
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.email = "user@example.com"
        mock_user.role = "member"

        result = await provisioning_service.validate_user_access(mock_user, sso_config)
        assert result is True

    async def test_validate_inactive_user(self, provisioning_service, sso_config):
        """Should deny inactive user"""
        mock_user = MagicMock()
        mock_user.is_active = False

        result = await provisioning_service.validate_user_access(mock_user, sso_config)
        assert result is False

    async def test_validate_user_domain_restriction_allowed(
        self, provisioning_service, sso_config
    ):
        """Should allow user with allowed domain"""
        sso_config.config["allowed_domains"] = ["example.com", "company.com"]

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.email = "user@example.com"
        mock_user.role = "member"

        result = await provisioning_service.validate_user_access(mock_user, sso_config)
        assert result is True

    async def test_validate_user_domain_restriction_denied(
        self, provisioning_service, sso_config
    ):
        """Should deny user with non-allowed domain"""
        sso_config.config["allowed_domains"] = ["company.com"]

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.email = "user@other.com"
        mock_user.role = "member"

        result = await provisioning_service.validate_user_access(mock_user, sso_config)
        assert result is False

    async def test_validate_user_role_restriction_allowed(
        self, provisioning_service, sso_config
    ):
        """Should allow user with allowed role"""
        sso_config.config["allowed_roles"] = ["admin", "member"]

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.email = "user@example.com"
        mock_user.role = "admin"

        result = await provisioning_service.validate_user_access(mock_user, sso_config)
        assert result is True

    async def test_validate_user_role_restriction_denied(
        self, provisioning_service, sso_config
    ):
        """Should deny user with non-allowed role"""
        sso_config.config["allowed_roles"] = ["admin"]

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.email = "user@example.com"
        mock_user.role = "viewer"

        result = await provisioning_service.validate_user_access(mock_user, sso_config)
        assert result is False


class TestAuditLogging:
    """Test audit logging for user provisioning"""

    @pytest.fixture
    def mock_db(self):
        """Mock async database session"""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_audit_logger(self):
        """Mock audit logger"""
        logger = AsyncMock()
        logger.log_event = AsyncMock()
        return logger

    @pytest.fixture
    def provisioning_service(self, mock_db, mock_audit_logger):
        """Create user provisioning service"""
        from app.sso.domain.services.user_provisioning import UserProvisioningService

        return UserProvisioningService(db=mock_db, audit_logger=mock_audit_logger)

    async def test_log_user_creation(self, provisioning_service, mock_audit_logger):
        """Should log user creation event"""
        from app.sso.domain.protocols.base import UserProvisioningData

        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.organization_id = "org_123"

        user_data = UserProvisioningData(
            email="new@example.com",
            first_name="New",
            last_name="User",
            attributes={},
        )

        session_data = {"protocol": "saml2"}

        await provisioning_service._log_user_creation(mock_user, user_data, session_data)

        mock_audit_logger.log_event.assert_called_once()
        call_args = mock_audit_logger.log_event.call_args
        assert call_args.kwargs["event_type"] == "user_created"
        assert call_args.kwargs["user_id"] == "user_123"

    async def test_log_user_update(self, provisioning_service, mock_audit_logger):
        """Should log user update event"""
        from app.sso.domain.protocols.base import UserProvisioningData

        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.organization_id = "org_123"

        user_data = UserProvisioningData(
            email="user@example.com",
            first_name="Updated",
            last_name="User",
            attributes={},
        )

        session_data = {"protocol": "oidc"}

        await provisioning_service._log_user_update(mock_user, user_data, session_data)

        mock_audit_logger.log_event.assert_called_once()
        call_args = mock_audit_logger.log_event.call_args
        assert call_args.kwargs["event_type"] == "user_updated"

    async def test_log_user_login(self, provisioning_service, mock_audit_logger):
        """Should log user login event"""
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.organization_id = "org_123"

        session_data = {"protocol": "saml2"}

        await provisioning_service._log_user_login(mock_user, session_data)

        mock_audit_logger.log_event.assert_called_once()
        call_args = mock_audit_logger.log_event.call_args
        assert call_args.kwargs["event_type"] == "user_login"

    async def test_no_logging_without_logger(self, mock_db):
        """Should not fail when audit logger is None"""
        from app.sso.domain.services.user_provisioning import UserProvisioningService
        from app.sso.domain.protocols.base import UserProvisioningData

        service = UserProvisioningService(db=mock_db, audit_logger=None)

        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.organization_id = "org_123"

        user_data = UserProvisioningData(
            email="user@example.com",
            first_name="Test",
            last_name="User",
            attributes={},
        )

        # Should not raise any exception
        await service._log_user_creation(mock_user, user_data, None)
        await service._log_user_update(mock_user, user_data, None)
        await service._log_user_login(mock_user, None)
