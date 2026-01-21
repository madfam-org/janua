"""
Comprehensive tests for RBAC Service
Target: Bring coverage from 27% to 80%+

Tests:
- Permission checking with cache
- Role hierarchy and permissions
- Policy evaluation (conditional, time-based, custom)
- Policy CRUD operations
- Permission enforcement
- Bulk permission checks
- Cache management
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from freezegun import freeze_time

from app.models import OrganizationMember, User
from app.services.rbac_service import RBACPolicy, RBACService


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis service"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def rbac_service(mock_db, mock_redis):
    """Create RBAC service instance"""
    return RBACService(db=mock_db, redis=mock_redis)


@pytest.fixture
def mock_user():
    """Mock user"""
    user = Mock(spec=User)
    user.id = uuid4()
    user.is_super_admin = False
    return user


@pytest.fixture
def mock_super_admin():
    """Mock super admin user"""
    user = Mock(spec=User)
    user.id = uuid4()
    user.is_super_admin = True
    return user


@pytest.fixture
def mock_org_member():
    """Mock organization member"""
    member = Mock(spec=OrganizationMember)
    member.user_id = uuid4()
    member.organization_id = uuid4()
    member.role = "admin"
    member.status = "active"
    return member


@pytest.mark.asyncio
class TestRoleHierarchy:
    """Test role hierarchy and level checking"""

    def test_get_role_level_valid_roles(self, rbac_service):
        """Test getting numeric levels for valid roles"""
        assert rbac_service.get_role_level("super_admin") == 4
        assert rbac_service.get_role_level("owner") == 3
        assert rbac_service.get_role_level("admin") == 2
        assert rbac_service.get_role_level("member") == 1
        assert rbac_service.get_role_level("viewer") == 0

    def test_get_role_level_invalid_role(self, rbac_service):
        """Test getting level for invalid role returns -1"""
        assert rbac_service.get_role_level("invalid_role") == -1
        assert rbac_service.get_role_level("") == -1

    def test_has_higher_role_equal(self, rbac_service):
        """Test role comparison with equal roles"""
        assert rbac_service.has_higher_role("admin", "admin") is True
        assert rbac_service.has_higher_role("member", "member") is True

    def test_has_higher_role_higher(self, rbac_service):
        """Test role comparison with higher role"""
        assert rbac_service.has_higher_role("owner", "admin") is True
        assert rbac_service.has_higher_role("admin", "member") is True
        assert rbac_service.has_higher_role("super_admin", "owner") is True

    def test_has_higher_role_lower(self, rbac_service):
        """Test role comparison with lower role"""
        assert rbac_service.has_higher_role("member", "admin") is False
        assert rbac_service.has_higher_role("viewer", "member") is False
        assert rbac_service.has_higher_role("admin", "owner") is False


@pytest.mark.asyncio
class TestPermissionChecking:
    """Test permission checking with caching"""

    async def test_check_permission_cached_true(self, rbac_service, mock_redis):
        """Test permission check with cached true result"""
        user_id = uuid4()
        org_id = uuid4()
        mock_redis.get = AsyncMock(return_value="true")

        result = await rbac_service.check_permission(user_id, org_id, "org:read")

        assert result is True
        mock_redis.get.assert_awaited_once()
        # Should not query database if cached
        rbac_service.db.query.assert_not_called()

    async def test_check_permission_cached_false(self, rbac_service, mock_redis):
        """Test permission check with cached false result"""
        user_id = uuid4()
        org_id = uuid4()
        mock_redis.get = AsyncMock(return_value="false")

        result = await rbac_service.check_permission(user_id, org_id, "org:delete")

        assert result is False
        mock_redis.get.assert_awaited_once()

    async def test_check_permission_no_role(self, rbac_service, mock_redis, mock_db):
        """Test permission check when user has no role"""
        user_id = uuid4()
        org_id = uuid4()

        # Mock no user found
        mock_result = Mock()
        mock_result.first = Mock(return_value=None)
        mock_db.query.return_value.filter.return_value = mock_result

        result = await rbac_service.check_permission(user_id, org_id, "org:read")

        assert result is False
        # Should cache false result
        mock_redis.set.assert_awaited_once()
        assert mock_redis.set.call_args[0][1] == "false"

    async def test_check_permission_with_role_allowed(
        self, rbac_service, mock_redis, mock_db, mock_user, mock_org_member
    ):
        """Test permission check with role that allows permission"""
        user_id = mock_user.id
        org_id = mock_org_member.organization_id
        mock_org_member.role = "admin"

        # Mock user query
        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        # Mock org member query
        member_result = Mock()
        member_result.first = Mock(return_value=mock_org_member)

        # Setup query chain
        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        result = await rbac_service.check_permission(
            user_id,
            org_id,
            "org:read",  # admin has org:read
        )

        assert result is True
        mock_redis.set.assert_awaited_once()
        assert mock_redis.set.call_args[0][1] == "true"

    async def test_check_permission_with_wildcard(
        self, rbac_service, mock_redis, mock_db, mock_user, mock_org_member
    ):
        """Test permission check with wildcard permissions"""
        user_id = mock_user.id
        org_id = mock_org_member.organization_id
        mock_org_member.role = "owner"  # owner has 'org:*'

        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=mock_org_member)

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        result = await rbac_service.check_permission(
            user_id,
            org_id,
            "org:anything",  # owner has org:*
        )

        assert result is True


@pytest.mark.asyncio
class TestUserRole:
    """Test user role retrieval"""

    async def test_get_user_role_super_admin(self, rbac_service, mock_db, mock_super_admin):
        """Test getting role for super admin returns super_admin"""
        user_result = Mock()
        user_result.first = Mock(return_value=mock_super_admin)
        mock_db.query.return_value.filter.return_value = user_result

        role = await rbac_service.get_user_role(mock_super_admin.id, uuid4())

        assert role == "super_admin"

    async def test_get_user_role_no_org(self, rbac_service, mock_db, mock_user):
        """Test getting role with no organization returns None"""
        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)
        mock_db.query.return_value.filter.return_value = user_result

        role = await rbac_service.get_user_role(mock_user.id, None)

        assert role is None

    async def test_get_user_role_org_member(
        self, rbac_service, mock_db, mock_user, mock_org_member
    ):
        """Test getting role for organization member"""
        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=mock_org_member)

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        role = await rbac_service.get_user_role(
            mock_org_member.user_id, mock_org_member.organization_id
        )

        assert role == "admin"

    async def test_get_user_role_not_member(self, rbac_service, mock_db, mock_user):
        """Test getting role for non-member returns None"""
        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=None)

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        role = await rbac_service.get_user_role(uuid4(), uuid4())

        assert role is None


@pytest.mark.asyncio
class TestPermissionMatching:
    """Test permission pattern matching with wildcards"""

    def test_match_permission_direct_match(self, rbac_service):
        """Test direct permission match"""
        assert rbac_service._match_permission("org:read", "org:read") is True
        assert rbac_service._match_permission("users:create", "users:create") is True

    def test_match_permission_no_match(self, rbac_service):
        """Test permission no match"""
        assert rbac_service._match_permission("org:read", "org:write") is False
        assert rbac_service._match_permission("users:create", "users:delete") is False

    def test_match_permission_wildcard_all(self, rbac_service):
        """Test full wildcard match"""
        assert rbac_service._match_permission("*", "org:read") is True
        assert rbac_service._match_permission("*", "anything:here") is True

    def test_match_permission_wildcard_resource(self, rbac_service):
        """Test resource wildcard match"""
        assert rbac_service._match_permission("org:*", "org:read") is True
        assert rbac_service._match_permission("org:*", "org:write") is True
        assert rbac_service._match_permission("org:*", "org:delete") is True
        assert rbac_service._match_permission("org:*", "users:read") is False

    def test_check_role_permission_with_wildcard(self, rbac_service):
        """Test role permission check with wildcards"""
        # super_admin has '*'
        assert rbac_service._check_role_permission("super_admin", "anything") is True
        # owner has 'org:*'
        assert rbac_service._check_role_permission("owner", "org:delete") is True
        # admin has 'users:*'
        assert rbac_service._check_role_permission("admin", "users:delete") is True


@pytest.mark.asyncio
class TestPolicyEvaluation:
    """Test conditional policy evaluation"""

    def test_evaluate_policy_user_condition_match(self, rbac_service):
        """Test policy evaluation with matching user condition"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {"user_id": str(uuid4())}
        user_id = UUID(policy.conditions["user_id"])

        result = rbac_service._evaluate_policy(policy, user_id, None, {})

        assert result is True

    def test_evaluate_policy_user_condition_no_match(self, rbac_service):
        """Test policy evaluation with non-matching user condition"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {"user_id": str(uuid4())}
        user_id = uuid4()  # Different user

        result = rbac_service._evaluate_policy(policy, user_id, None, {})

        assert result is False

    def test_evaluate_policy_resource_condition_match(self, rbac_service):
        """Test policy evaluation with matching resource condition"""
        resource_id = uuid4()
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {"resource_id": str(resource_id)}

        result = rbac_service._evaluate_policy(policy, uuid4(), resource_id, {})

        assert result is True

    def test_evaluate_policy_resource_condition_no_match(self, rbac_service):
        """Test policy evaluation with non-matching resource condition"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {"resource_id": str(uuid4())}
        resource_id = uuid4()  # Different resource

        result = rbac_service._evaluate_policy(policy, uuid4(), resource_id, {})

        assert result is False

    @freeze_time("2025-11-18 12:00:00")
    def test_evaluate_policy_time_range_within(self, rbac_service):
        """Test policy evaluation within time range"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {
            "time_range": {"start": "2025-11-18T10:00:00", "end": "2025-11-18T14:00:00"}
        }

        result = rbac_service._evaluate_policy(policy, uuid4(), None, {})

        assert result is True

    @freeze_time("2025-11-18 09:00:00")
    def test_evaluate_policy_time_range_before(self, rbac_service):
        """Test policy evaluation before time range"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {
            "time_range": {"start": "2025-11-18T10:00:00", "end": "2025-11-18T14:00:00"}
        }

        result = rbac_service._evaluate_policy(policy, uuid4(), None, {})

        assert result is False

    @freeze_time("2025-11-18 15:00:00")
    def test_evaluate_policy_time_range_after(self, rbac_service):
        """Test policy evaluation after time range"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {
            "time_range": {"start": "2025-11-18T10:00:00", "end": "2025-11-18T14:00:00"}
        }

        result = rbac_service._evaluate_policy(policy, uuid4(), None, {})

        assert result is False

    def test_evaluate_policy_custom_conditions_match(self, rbac_service):
        """Test policy evaluation with matching custom conditions"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {"custom": {"department": "engineering", "level": "senior"}}
        context = {"department": "engineering", "level": "senior"}

        result = rbac_service._evaluate_policy(policy, uuid4(), None, context)

        assert result is True

    def test_evaluate_policy_custom_conditions_no_match(self, rbac_service):
        """Test policy evaluation with non-matching custom conditions"""
        policy = Mock(spec=RBACPolicy)
        policy.conditions = {"custom": {"department": "engineering", "level": "senior"}}
        context = {
            "department": "sales",  # Different department
            "level": "junior",
        }

        result = rbac_service._evaluate_policy(policy, uuid4(), None, context)

        assert result is False

    @freeze_time("2025-11-18 12:00:00")
    def test_check_time_range_valid(self, rbac_service):
        """Test time range check within valid range"""
        time_range = {"start": "2025-11-18T10:00:00", "end": "2025-11-18T14:00:00"}

        result = rbac_service._check_time_range(time_range)

        assert result is True

    @freeze_time("2025-11-18 12:00:00")
    def test_check_time_range_only_start(self, rbac_service):
        """Test time range check with only start time"""
        time_range = {"start": "2025-11-18T10:00:00"}

        result = rbac_service._check_time_range(time_range)

        assert result is True

    @freeze_time("2025-11-18 12:00:00")
    def test_check_time_range_only_end(self, rbac_service):
        """Test time range check with only end time"""
        time_range = {"end": "2025-11-18T14:00:00"}

        result = rbac_service._check_time_range(time_range)

        assert result is True


@pytest.mark.asyncio
class TestUserPermissions:
    """Test getting all user permissions"""

    async def test_get_user_permissions_no_role(self, rbac_service, mock_db, mock_user):
        """Test getting permissions for user with no role"""
        user_result = Mock()
        user_result.first = Mock(return_value=None)
        mock_db.query.return_value.filter.return_value = user_result

        permissions = await rbac_service.get_user_permissions(uuid4(), uuid4())

        assert permissions == set()

    async def test_get_user_permissions_member_role(
        self, rbac_service, mock_db, mock_user, mock_org_member
    ):
        """Test getting permissions for member role"""
        user_id = mock_user.id
        org_id = mock_org_member.organization_id
        mock_org_member.role = "member"

        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=mock_org_member)

        # Mock policy query
        policy_result = Mock()
        policy_result.all = Mock(return_value=[])

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            else:  # RBACPolicy
                return Mock(filter=Mock(return_value=policy_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        permissions = await rbac_service.get_user_permissions(user_id, org_id)

        expected = set(["org:read", "users:read", "users:update:self", "settings:read"])
        assert permissions == expected


@pytest.mark.asyncio
class TestPolicyCRUD:
    """Test policy create, update, delete operations"""

    async def test_create_policy(self, rbac_service, mock_redis):
        """Test creating a new policy"""
        org_id = uuid4()
        creator_id = uuid4()
        conditions = {"user_id": str(uuid4())}

        with patch("app.services.rbac_service.RBACPolicy") as mock_policy_class:
            mock_policy = Mock()
            mock_policy_class.return_value = mock_policy

            _policy = await rbac_service.create_policy(
                organization_id=org_id,
                name="Test Policy",
                permission="custom:action",
                conditions=conditions,
                created_by=creator_id,
            )

            rbac_service.db.add.assert_called_once_with(mock_policy)
            rbac_service.db.commit.assert_called_once()
            rbac_service.db.refresh.assert_called_once_with(mock_policy)
            # Should clear cache
            mock_redis.keys.assert_awaited_once()

    async def test_update_policy_success(self, rbac_service, mock_db, mock_redis):
        """Test updating existing policy"""
        policy_id = uuid4()
        org_id = uuid4()
        mock_policy = Mock(spec=RBACPolicy)
        mock_policy.id = policy_id
        mock_policy.organization_id = org_id
        mock_policy.name = "Old Name"

        policy_result = Mock()
        policy_result.first = Mock(return_value=mock_policy)
        mock_db.query.return_value.filter.return_value = policy_result

        updates = {"name": "New Name"}
        await rbac_service.update_policy(policy_id, updates, uuid4())

        assert mock_policy.name == "New Name"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_policy)
        mock_redis.keys.assert_awaited_once()

    async def test_update_policy_not_found(self, rbac_service, mock_db):
        """Test updating non-existent policy raises exception"""
        policy_result = Mock()
        policy_result.first = Mock(return_value=None)
        mock_db.query.return_value.filter.return_value = policy_result

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await rbac_service.update_policy(uuid4(), {}, uuid4())

        assert exc_info.value.status_code == 404

    async def test_delete_policy_success(self, rbac_service, mock_db, mock_redis):
        """Test deleting existing policy (soft delete)"""
        policy_id = uuid4()
        org_id = uuid4()
        mock_policy = Mock(spec=RBACPolicy)
        mock_policy.id = policy_id
        mock_policy.organization_id = org_id
        mock_policy.is_active = True

        policy_result = Mock()
        policy_result.first = Mock(return_value=mock_policy)
        mock_db.query.return_value.filter.return_value = policy_result

        await rbac_service.delete_policy(policy_id)

        assert mock_policy.is_active is False
        assert mock_policy.deleted_at is not None
        mock_db.commit.assert_called_once()
        mock_redis.keys.assert_awaited_once()

    async def test_delete_policy_not_found(self, rbac_service, mock_db):
        """Test deleting non-existent policy raises exception"""
        policy_result = Mock()
        policy_result.first = Mock(return_value=None)
        mock_db.query.return_value.filter.return_value = policy_result

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await rbac_service.delete_policy(uuid4())

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestCacheManagement:
    """Test RBAC cache management"""

    async def test_clear_rbac_cache_with_keys(self, rbac_service, mock_redis):
        """Test clearing cache when keys exist"""
        org_id = uuid4()
        mock_keys = [f"rbac:user1:{org_id}:perm1", f"rbac:user2:{org_id}:perm2"]
        mock_redis.keys = AsyncMock(return_value=mock_keys)

        await rbac_service._clear_rbac_cache(org_id)

        mock_redis.keys.assert_awaited_once()
        mock_redis.delete.assert_awaited_once_with(*mock_keys)

    async def test_clear_rbac_cache_no_keys(self, rbac_service, mock_redis):
        """Test clearing cache when no keys exist"""
        org_id = uuid4()
        mock_redis.keys = AsyncMock(return_value=[])

        await rbac_service._clear_rbac_cache(org_id)

        mock_redis.keys.assert_awaited_once()
        mock_redis.delete.assert_not_awaited()


@pytest.mark.asyncio
class TestPermissionEnforcement:
    """Test permission enforcement with exceptions"""

    async def test_enforce_permission_allowed(
        self, rbac_service, mock_redis, mock_db, mock_user, mock_org_member
    ):
        """Test enforcing permission that is allowed"""
        user_id = mock_user.id
        org_id = mock_org_member.organization_id
        mock_org_member.role = "admin"

        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=mock_org_member)

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        # Should not raise exception
        await rbac_service.enforce_permission(user_id, org_id, "org:read")

    async def test_enforce_permission_denied(self, rbac_service, mock_redis, mock_db, mock_user):
        """Test enforcing permission that is denied raises exception"""
        user_id = mock_user.id
        org_id = uuid4()

        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=None)

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await rbac_service.enforce_permission(user_id, org_id, "org:delete")

        assert exc_info.value.status_code == 403
        assert "Permission denied" in str(exc_info.value.detail)


@pytest.mark.asyncio
class TestBulkPermissionCheck:
    """Test bulk permission checking"""

    async def test_bulk_check_permissions(
        self, rbac_service, mock_redis, mock_db, mock_user, mock_org_member
    ):
        """Test checking multiple permissions at once"""
        user_id = mock_user.id
        org_id = mock_org_member.organization_id
        mock_org_member.role = "admin"

        user_result = Mock()
        user_result.first = Mock(return_value=mock_user)

        member_result = Mock()
        member_result.first = Mock(return_value=mock_org_member)

        def query_side_effect(model):
            if model == User:
                return Mock(filter=Mock(return_value=user_result))
            elif model == OrganizationMember:
                return Mock(filter=Mock(return_value=member_result))
            return Mock()

        mock_db.query.side_effect = query_side_effect

        permissions = ["org:read", "org:update", "users:create", "billing:delete"]
        results = await rbac_service.bulk_check_permissions(user_id, org_id, permissions)

        assert len(results) == 4
        assert results["org:read"] is True  # admin has this
        assert results["org:update"] is True  # admin has this
        assert results["users:create"] is True  # admin has users:*
        assert results["billing:delete"] is False  # admin doesn't have billing
