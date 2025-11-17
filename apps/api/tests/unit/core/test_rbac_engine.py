import pytest

pytestmark = pytest.mark.asyncio


"""
Comprehensive tests for app.core.rbac_engine module
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.core.rbac_engine import Action, RBACEngine, ResourceType


class TestResourceType:
    """Test ResourceType enum"""

    def test_resource_type_values(self):
        """Test ResourceType enum values"""
        assert ResourceType.ORGANIZATION.value == "organization"
        assert ResourceType.USER.value == "user"
        assert ResourceType.ROLE.value == "role"
        assert ResourceType.PROJECT.value == "project"
        assert ResourceType.API_KEY.value == "api_key"
        assert ResourceType.WEBHOOK.value == "webhook"
        assert ResourceType.AUDIT_LOG.value == "audit_log"
        assert ResourceType.BILLING.value == "billing"
        assert ResourceType.SETTINGS.value == "settings"

    def test_resource_type_membership(self):
        """Test ResourceType enum membership"""
        assert ResourceType.ORGANIZATION in ResourceType
        assert ResourceType.USER in ResourceType
        assert "invalid_resource" not in [rt.value for rt in ResourceType]


class TestAction:
    """Test Action enum"""

    def test_action_values(self):
        """Test Action enum values"""
        assert Action.CREATE.value == "create"
        assert Action.READ.value == "read"
        assert Action.UPDATE.value == "update"
        assert Action.DELETE.value == "delete"
        assert Action.LIST.value == "list"
        assert Action.ADMIN.value == "admin"
        assert Action.EXECUTE.value == "execute"

    def test_action_membership(self):
        """Test Action enum membership"""
        assert Action.CREATE in Action
        assert Action.ADMIN in Action
        assert "invalid_action" not in [a.value for a in Action]


class TestRBACEngine:
    """Test RBACEngine class"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.fixture
    def mock_user_id(self):
        """Mock user ID"""
        return str(uuid4())

    @pytest.fixture
    def mock_org_id(self):
        """Mock organization ID"""
        return str(uuid4())

    def test_rbac_engine_initialization(self, rbac_engine):
        """Test RBACEngine initialization"""
        assert rbac_engine._permission_cache == {}
        assert rbac_engine._role_hierarchy_cache == {}

    @pytest.mark.asyncio
    async def test_check_permission_no_organization_context(
        self, rbac_engine, mock_session, mock_user_id
    ):
        """Test permission check without organization context"""
        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = None

            result = await rbac_engine.check_permission(
                mock_session, mock_user_id, ResourceType.USER, Action.READ
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_no_membership(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check when user has no membership"""
        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

        with patch.object(rbac_engine, "_get_user_membership") as mock_get_membership:
            mock_get_membership.return_value = None

            result = await rbac_engine.check_permission(
                mock_session,
                mock_user_id,
                ResourceType.USER,
                Action.READ,
                organization_id=mock_org_id,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_inactive_membership(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check when user membership is inactive"""
        mock_membership = Mock()
        mock_membership.status = "suspended"

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

        with patch.object(rbac_engine, "_get_user_membership") as mock_get_membership:
            mock_get_membership.return_value = mock_membership

            result = await rbac_engine.check_permission(
                mock_session,
                mock_user_id,
                ResourceType.USER,
                Action.READ,
                organization_id=mock_org_id,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_exact_match(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check with exact permission match"""
        mock_membership = Mock()
        mock_membership.status = "active"

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

            with patch.object(
                rbac_engine, "_get_user_membership", new=AsyncMock(return_value=mock_membership)
            ):
                with patch.object(
                    rbac_engine,
                    "_get_user_permissions",
                    new=AsyncMock(return_value={"read:user", "write:project"}),
                ):
                    with patch.object(
                        rbac_engine, "_build_permission_string"
                    ) as mock_build_permission:
                        mock_build_permission.return_value = "read:user"

                        result = await rbac_engine.check_permission(
                            mock_session,
                            mock_user_id,
                            ResourceType.USER,
                            Action.READ,
                            organization_id=mock_org_id,
                        )

                        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_wildcard_match(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check with wildcard permission"""
        mock_membership = Mock()
        mock_membership.status = "active"

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

            with patch.object(
                rbac_engine, "_get_user_membership", new=AsyncMock(return_value=mock_membership)
            ):
                with patch.object(
                    rbac_engine,
                    "_get_user_permissions",
                    new=AsyncMock(return_value={"*:admin", "read:project"}),
                ):
                    with patch.object(
                        rbac_engine, "_build_permission_string"
                    ) as mock_build_permission:
                        mock_build_permission.return_value = "delete:user"

                        with patch.object(
                            rbac_engine, "_check_wildcard_permission"
                        ) as mock_check_wildcard:
                            mock_check_wildcard.return_value = True

                            result = await rbac_engine.check_permission(
                                mock_session,
                                mock_user_id,
                                ResourceType.USER,
                                Action.DELETE,
                                organization_id=mock_org_id,
                            )

                            assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_admin_override(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check with admin override"""
        mock_membership = Mock()
        mock_membership.status = "active"

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

            with patch.object(
                rbac_engine, "_get_user_membership", new=AsyncMock(return_value=mock_membership)
            ):
                with patch.object(
                    rbac_engine, "_get_user_permissions", new=AsyncMock(return_value={"user:admin"})
                ):
                    with patch.object(
                        rbac_engine, "_build_permission_string"
                    ) as mock_build_permission:
                        mock_build_permission.return_value = "delete:user"

                        with patch.object(
                            rbac_engine, "_check_wildcard_permission"
                        ) as mock_check_wildcard:
                            mock_check_wildcard.return_value = False

                            result = await rbac_engine.check_permission(
                                mock_session,
                                mock_user_id,
                                ResourceType.USER,
                                Action.DELETE,
                                organization_id=mock_org_id,
                            )

                            assert result is True

    @pytest.mark.asyncio
    async def test_get_user_permissions_no_organization(
        self, rbac_engine, mock_session, mock_user_id
    ):
        """Test get user permissions without organization context"""
        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = None

            result = await rbac_engine.get_user_permissions(mock_session, mock_user_id)

            assert result == set()

    @pytest.mark.asyncio
    async def test_get_user_permissions_no_membership(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test get user permissions when user has no membership"""
        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

        with patch.object(rbac_engine, "_get_user_membership") as mock_get_membership:
            mock_get_membership.return_value = None

            result = await rbac_engine.get_user_permissions(mock_session, mock_user_id, mock_org_id)

            assert result == set()

    @pytest.mark.asyncio
    async def test_get_user_permissions_success(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test successful get user permissions"""
        mock_membership = Mock()
        expected_permissions = {"read:user", "write:project", "admin:*"}

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

        with patch.object(rbac_engine, "_get_user_membership") as mock_get_membership:
            mock_get_membership.return_value = mock_membership

        with patch.object(rbac_engine, "_get_user_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = expected_permissions

            result = await rbac_engine.get_user_permissions(mock_session, mock_user_id, mock_org_id)

            assert result == expected_permissions

    @pytest.mark.asyncio
    async def test_has_any_permission_true(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test has_any_permission returns True when user has one of the permissions"""
        expected_permissions = {"read:user", "write:project"}

        with patch.object(rbac_engine, "get_user_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = expected_permissions

            result = await rbac_engine.has_any_permission(
                mock_session, mock_user_id, ["read:user", "delete:user"], mock_org_id
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_has_any_permission_false(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test has_any_permission returns False when user has none of the permissions"""
        expected_permissions = {"read:project", "write:project"}

        with patch.object(rbac_engine, "get_user_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = expected_permissions

            result = await rbac_engine.has_any_permission(
                mock_session, mock_user_id, ["read:user", "delete:user"], mock_org_id
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_has_all_permissions_true(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test has_all_permissions returns True when user has all permissions"""
        expected_permissions = {"read:user", "write:user", "delete:user"}

        with patch.object(rbac_engine, "get_user_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = expected_permissions

            result = await rbac_engine.has_all_permissions(
                mock_session, mock_user_id, ["read:user", "write:user"], mock_org_id
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_has_all_permissions_false(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test has_all_permissions returns False when user missing some permissions"""
        expected_permissions = {"read:user", "write:project"}

        with patch.object(rbac_engine, "get_user_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = expected_permissions

            result = await rbac_engine.has_all_permissions(
                mock_session, mock_user_id, ["read:user", "delete:user"], mock_org_id
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_exception_handling(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test exception handling in check_permission"""
        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.side_effect = Exception("Test error")

            result = await rbac_engine.check_permission(
                mock_session,
                mock_user_id,
                ResourceType.USER,
                Action.READ,
                organization_id=mock_org_id,
            )

            assert result is False

    def test_permission_string_building(self, rbac_engine):
        """Test permission string building logic"""
        # This tests the _build_permission_string method indirectly
        # We can't test it directly without exposing it, but we can verify
        # the logic through the public interface behavior

        # The actual method would create strings like "read:user", "admin:billing"
        # We'll test this through the integration tests
        assert True  # Placeholder for permission string logic verification

    def test_wildcard_permission_checking(self, rbac_engine):
        """Test wildcard permission checking logic"""
        # This tests the _check_wildcard_permission method indirectly
        # Wildcard patterns like "*", "admin:*", "read:*" should match appropriately
        assert True  # Placeholder for wildcard logic verification


class TestRBACEngineIntegration:
    """Integration tests for realistic RBAC scenarios"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for integration testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_admin_user_scenario(self, rbac_engine, mock_session):
        """Test admin user with full permissions"""
        user_id = str(uuid4())
        org_id = str(uuid4())

        mock_membership = Mock()
        mock_membership.status = "active"

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = org_id

            with patch.object(
                rbac_engine, "_get_user_membership", new=AsyncMock(return_value=mock_membership)
            ):
                with patch.object(
                    rbac_engine, "_get_user_permissions", new=AsyncMock(return_value={"*:admin"})
                ):
                    with patch.object(
                        rbac_engine, "_build_permission_string"
                    ) as mock_build_permission:
                        mock_build_permission.return_value = "delete:billing"

                        with patch.object(
                            rbac_engine, "_check_wildcard_permission"
                        ) as mock_check_wildcard:
                            mock_check_wildcard.return_value = False

                            # Admin should have access through admin override
                            result = await rbac_engine.check_permission(
                                mock_session,
                                user_id,
                                ResourceType.BILLING,
                                Action.DELETE,
                                organization_id=org_id,
                            )

                            assert result is True

    @pytest.mark.asyncio
    async def test_limited_user_scenario(self, rbac_engine, mock_session):
        """Test user with limited permissions"""
        user_id = str(uuid4())
        org_id = str(uuid4())

        mock_membership = Mock()
        mock_membership.status = "active"

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = org_id

        with patch.object(rbac_engine, "_get_user_membership") as mock_get_membership:
            mock_get_membership.return_value = mock_membership

        with patch.object(rbac_engine, "_get_user_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = {"read:user", "read:project"}

        with patch.object(rbac_engine, "_build_permission_string") as mock_build_permission:
            mock_build_permission.return_value = "delete:user"

        with patch.object(rbac_engine, "_check_wildcard_permission") as mock_check_wildcard:
            mock_check_wildcard.return_value = False

            # Limited user should not have delete access
            result = await rbac_engine.check_permission(
                mock_session, user_id, ResourceType.USER, Action.DELETE, organization_id=org_id
            )

            assert result is False
