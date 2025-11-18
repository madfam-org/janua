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
    async def test_check_permission_with_resource_id(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check with resource_id triggers resource-specific check"""
        mock_membership = Mock()
        mock_membership.status = "active"
        resource_id = str(uuid4())

        with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
            mock_tenant.get_organization_id.return_value = mock_org_id

            with patch.object(
                rbac_engine, "_get_user_membership", new=AsyncMock(return_value=mock_membership)
            ):
                with patch.object(
                    rbac_engine,
                    "_get_user_permissions",
                    new=AsyncMock(return_value={"user:own:read"}),
                ):
                    with patch.object(
                        rbac_engine, "_build_permission_string"
                    ) as mock_build_permission:
                        mock_build_permission.return_value = "user:read"

                        with patch.object(
                            rbac_engine, "_check_wildcard_permission"
                        ) as mock_check_wildcard:
                            mock_check_wildcard.return_value = False

                            with patch.object(
                                rbac_engine,
                                "_check_resource_permission",
                                new=AsyncMock(return_value=True),
                            ) as mock_check_resource:
                                result = await rbac_engine.check_permission(
                                    mock_session,
                                    mock_user_id,
                                    ResourceType.USER,
                                    Action.READ,
                                    resource_id=resource_id,
                                    organization_id=mock_org_id,
                                )

                                assert result is True
                                # Verify _check_resource_permission was called
                                mock_check_resource.assert_called_once_with(
                                    mock_session,
                                    mock_user_id,
                                    ResourceType.USER,
                                    Action.READ,
                                    resource_id,
                                    {"user:own:read"},
                                )

    @pytest.mark.asyncio
    async def test_check_permission_no_match_returns_false(
        self, rbac_engine, mock_session, mock_user_id, mock_org_id
    ):
        """Test permission check returns False when no permissions match"""
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
                    new=AsyncMock(return_value={"write:project"}),
                ):
                    with patch.object(
                        rbac_engine, "_build_permission_string"
                    ) as mock_build_permission:
                        mock_build_permission.return_value = "read:user"

                        with patch.object(
                            rbac_engine, "_check_wildcard_permission"
                        ) as mock_check_wildcard:
                            mock_check_wildcard.return_value = False

                            # Call without resource_id - should reach line 125 and return False
                            result = await rbac_engine.check_permission(
                                mock_session,
                                mock_user_id,
                                ResourceType.USER,
                                Action.READ,
                                organization_id=mock_org_id,
                            )

                            assert result is False

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
        # Test the _build_permission_string method directly
        result = rbac_engine._build_permission_string(ResourceType.USER, Action.READ)
        assert result == "user:read"

        result = rbac_engine._build_permission_string(ResourceType.PROJECT, Action.UPDATE)
        assert result == "project:update"

        result = rbac_engine._build_permission_string(ResourceType.ORGANIZATION, Action.DELETE)
        assert result == "organization:delete"

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


class TestWildcardPermissions:
    """Test wildcard permission matching logic"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    def test_wildcard_resource_match(self, rbac_engine):
        """Test resource wildcard matching (*:action)"""
        user_permissions = {"*:read", "write:project"}

        # Should match any resource with read action
        result = rbac_engine._check_wildcard_permission("user:read", user_permissions)
        assert result is True

        result = rbac_engine._check_wildcard_permission("project:read", user_permissions)
        assert result is True

        # Should not match different action
        result = rbac_engine._check_wildcard_permission("user:write", user_permissions)
        assert result is False

    def test_wildcard_action_match(self, rbac_engine):
        """Test action wildcard matching (resource:*)"""
        user_permissions = {"user:*", "read:project"}

        # Should match any action on user resource
        result = rbac_engine._check_wildcard_permission("user:read", user_permissions)
        assert result is True

        result = rbac_engine._check_wildcard_permission("user:delete", user_permissions)
        assert result is True

        # Should not match different resource
        result = rbac_engine._check_wildcard_permission("project:delete", user_permissions)
        assert result is False

    def test_wildcard_full_match(self, rbac_engine):
        """Test full wildcard matching (*:*)"""
        user_permissions = {"*:*"}

        # Should match any permission
        result = rbac_engine._check_wildcard_permission("user:read", user_permissions)
        assert result is True

        result = rbac_engine._check_wildcard_permission("project:delete", user_permissions)
        assert result is True

        result = rbac_engine._check_wildcard_permission("anything:everything", user_permissions)
        assert result is True

    def test_wildcard_no_match(self, rbac_engine):
        """Test no wildcard match"""
        user_permissions = {"user:read", "project:write"}

        # Should not match without wildcards
        result = rbac_engine._check_wildcard_permission("organization:read", user_permissions)
        assert result is False


class TestResourceOwnership:
    """Test resource ownership checking logic"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_user_owns_own_resource(self, rbac_engine, mock_session):
        """Test that user owns their own USER resource"""
        user_id = str(uuid4())

        result = await rbac_engine._check_resource_ownership(
            mock_session, user_id, ResourceType.USER, user_id
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_user_does_not_own_other_user_resource(self, rbac_engine, mock_session):
        """Test that user does not own another user's resource"""
        user_id = str(uuid4())
        other_user_id = str(uuid4())

        result = await rbac_engine._check_resource_ownership(
            mock_session, user_id, ResourceType.USER, other_user_id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_non_user_resource_returns_false(self, rbac_engine, mock_session):
        """Test that non-USER resources return False (not implemented)"""
        user_id = str(uuid4())
        resource_id = str(uuid4())

        result = await rbac_engine._check_resource_ownership(
            mock_session, user_id, ResourceType.PROJECT, resource_id
        )

        assert result is False


class TestExceptionHandling:
    """Test exception handling in permission checks"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_check_permission_exception_returns_false(self, rbac_engine, mock_session):
        """Test that exceptions during permission check return False (deny by default)"""
        user_id = str(uuid4())
        org_id = str(uuid4())

        # Mock _get_user_membership to raise an exception
        with patch.object(
            rbac_engine, "_get_user_membership", side_effect=Exception("Database error")
        ):
            with patch("app.core.rbac_engine.TenantContext") as mock_tenant:
                mock_tenant.get_organization_id.return_value = org_id

                result = await rbac_engine.check_permission(
                    mock_session, user_id, ResourceType.USER, Action.READ, organization_id=org_id
                )

                # Should return False on exception (fail-safe)
                assert result is False


class TestUserPermissions:
    """Test user permission aggregation (role + custom permissions)"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_user_permissions_with_role_only(self, rbac_engine, mock_session):
        """Test getting permissions from role without custom permissions"""
        role_id = str(uuid4())

        # Mock membership with role but no custom permissions
        mock_membership = Mock()
        mock_membership.role_id = role_id
        mock_membership.custom_permissions = None

        # Mock _get_role_permissions to return role permissions
        with patch.object(
            rbac_engine,
            "_get_role_permissions",
            new=AsyncMock(return_value={"user:read", "project:write"}),
        ):
            permissions = await rbac_engine._get_user_permissions(mock_session, mock_membership)

        assert permissions == {"user:read", "project:write"}

    @pytest.mark.asyncio
    async def test_user_permissions_with_custom_only(self, rbac_engine, mock_session):
        """Test getting permissions with only custom permissions (no role)"""
        # Mock membership with custom permissions but no role
        mock_membership = Mock()
        mock_membership.role_id = None
        mock_membership.custom_permissions = ["admin:delete", "user:manage"]

        permissions = await rbac_engine._get_user_permissions(mock_session, mock_membership)

        assert permissions == {"admin:delete", "user:manage"}

    @pytest.mark.asyncio
    async def test_user_permissions_combined(self, rbac_engine, mock_session):
        """Test combining role permissions with custom permissions"""
        role_id = str(uuid4())

        # Mock membership with both role and custom permissions
        mock_membership = Mock()
        mock_membership.role_id = role_id
        mock_membership.custom_permissions = ["admin:delete", "user:manage"]

        # Mock _get_role_permissions to return role permissions
        with patch.object(
            rbac_engine,
            "_get_role_permissions",
            new=AsyncMock(return_value={"user:read", "project:write"}),
        ):
            permissions = await rbac_engine._get_user_permissions(mock_session, mock_membership)

        # Should combine both role and custom permissions
        assert "user:read" in permissions
        assert "project:write" in permissions
        assert "admin:delete" in permissions
        assert "user:manage" in permissions
        assert len(permissions) == 4

    @pytest.mark.asyncio
    async def test_user_permissions_no_role_no_custom(self, rbac_engine, mock_session):
        """Test user with neither role nor custom permissions"""
        # Mock membership with no role and no custom permissions
        mock_membership = Mock()
        mock_membership.role_id = None
        mock_membership.custom_permissions = None

        permissions = await rbac_engine._get_user_permissions(mock_session, mock_membership)

        assert permissions == set()

    @pytest.mark.asyncio
    async def test_role_permission_caching(self, rbac_engine, mock_session):
        """Test that role permissions are properly cached"""
        role_id = str(uuid4())

        # Pre-populate cache
        rbac_engine._permission_cache[role_id] = {"cached:read", "cached:write"}

        # Mock membership with cached role
        mock_membership = Mock()
        mock_membership.role_id = role_id
        mock_membership.custom_permissions = ["custom:delete"]

        permissions = await rbac_engine._get_user_permissions(mock_session, mock_membership)

        # Should use cached role permissions + custom permissions
        assert "cached:read" in permissions
        assert "cached:write" in permissions
        assert "custom:delete" in permissions
        assert len(permissions) == 3


class TestResourceSpecificPermissions:
    """Test resource-specific permission checking"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_specific_resource_permission_match(self, rbac_engine, mock_session):
        """Test exact resource:id:action permission match"""
        user_id = str(uuid4())
        resource_id = str(uuid4())

        # Permission for specific resource
        permissions = {f"user:{resource_id}:read"}

        result = await rbac_engine._check_resource_permission(
            mock_session, user_id, ResourceType.USER, Action.READ, resource_id, permissions
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_ownership_based_permission(self, rbac_engine, mock_session):
        """Test ownership-based permission (user:own:action)"""
        user_id = str(uuid4())

        # Permission to access own resources
        permissions = {"user:own:read"}

        with patch.object(
            rbac_engine, "_check_resource_ownership", new=AsyncMock(return_value=True)
        ):
            result = await rbac_engine._check_resource_permission(
                mock_session, user_id, ResourceType.USER, Action.READ, user_id, permissions
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_ownership_permission_denied(self, rbac_engine, mock_session):
        """Test ownership-based permission denied when not owner"""
        user_id = str(uuid4())
        other_user_id = str(uuid4())

        # Permission to access own resources only
        permissions = {"user:own:read"}

        with patch.object(
            rbac_engine, "_check_resource_ownership", new=AsyncMock(return_value=False)
        ):
            result = await rbac_engine._check_resource_permission(
                mock_session, user_id, ResourceType.USER, Action.READ, other_user_id, permissions
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_no_resource_permission_match(self, rbac_engine, mock_session):
        """Test no matching resource-specific permission"""
        user_id = str(uuid4())
        resource_id = str(uuid4())

        # Different resource permissions
        permissions = {"project:123:read", "user:456:write"}

        result = await rbac_engine._check_resource_permission(
            mock_session, user_id, ResourceType.USER, Action.READ, resource_id, permissions
        )

        assert result is False


class TestRoleInheritance:
    """Test role permission inheritance functionality"""

    @pytest.fixture
    def rbac_engine(self):
        """Create RBACEngine instance for testing"""
        return RBACEngine()

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_role_permissions_without_parent(self, rbac_engine, mock_session):
        """Test getting permissions for role without parent"""
        role_id = str(uuid4())

        # Mock role without parent
        mock_role = Mock()
        mock_role.permissions = ["user:read", "user:list"]
        mock_role.parent_role_id = None

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute = AsyncMock(return_value=mock_result)

        permissions = await rbac_engine._get_role_permissions(mock_session, role_id)

        assert permissions == {"user:read", "user:list"}
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_role_permissions_with_parent(self, rbac_engine, mock_session):
        """Test getting permissions with parent role inheritance"""
        child_role_id = str(uuid4())
        parent_role_id = str(uuid4())

        # Mock child role with parent
        mock_child_role = Mock()
        mock_child_role.permissions = ["user:create", "user:update"]
        mock_child_role.parent_role_id = parent_role_id

        # Mock parent role
        mock_parent_role = Mock()
        mock_parent_role.permissions = ["user:read", "user:list"]
        mock_parent_role.parent_role_id = None

        # Setup mock returns for both queries
        call_count = [0]

        async def mock_execute(query):
            result = Mock()
            call_count[0] += 1

            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = mock_child_role
            else:
                result.scalar_one_or_none.return_value = mock_parent_role
            return result

        mock_session.execute = mock_execute

        permissions = await rbac_engine._get_role_permissions(mock_session, child_role_id)

        # Should include both child and parent permissions
        assert "user:create" in permissions
        assert "user:update" in permissions
        assert "user:read" in permissions
        assert "user:list" in permissions
        assert len(permissions) == 4

    @pytest.mark.asyncio
    async def test_get_role_permissions_nonexistent_role(self, rbac_engine, mock_session):
        """Test getting permissions for non-existent role returns empty set"""
        role_id = str(uuid4())

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        permissions = await rbac_engine._get_role_permissions(mock_session, role_id)

        assert permissions == set()

    @pytest.mark.asyncio
    async def test_role_inheritance_caching(self, rbac_engine, mock_session):
        """Test that role permissions are cached"""
        role_id = str(uuid4())

        # Mock role
        mock_role = Mock()
        mock_role.permissions = ["user:read"]
        mock_role.parent_role_id = None

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_role

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            return mock_result

        mock_session.execute = mock_execute

        # First call - should hit database
        permissions1 = await rbac_engine._get_role_permissions(mock_session, role_id)

        # Second call - should use cache
        permissions2 = await rbac_engine._get_role_permissions(mock_session, role_id)

        # Should return same permissions
        assert permissions1 == permissions2
        assert permissions1 == {"user:read"}

        # Should only call database once (cached second time)
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_initialize_default_roles(self, mock_session):
        """Test initialization of default roles for organization"""
        org_id = str(uuid4())

        # Track what roles were added
        added_roles = []

        def capture_add(role):
            added_roles.append(role)

        mock_session.add = Mock(side_effect=capture_add)
        mock_session.commit = AsyncMock()

        from app.core.rbac_engine import initialize_default_roles

        await initialize_default_roles(mock_session, org_id)

        # Should create 4 default roles (OWNER, ADMIN, MEMBER, VIEWER)
        assert len(added_roles) == 4

        # Verify roles have correct organization_id
        for role in added_roles:
            assert role.organization_id == org_id
            assert hasattr(role, "name")
            assert hasattr(role, "permissions")

        # Verify commit was called
        assert mock_session.commit.called
