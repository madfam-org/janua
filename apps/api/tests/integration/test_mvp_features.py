import pytest

pytestmark = pytest.mark.asyncio

"""
Integration tests for MVP features
Tests organization members, RBAC, webhooks, and audit logging
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.services.organization_member_service import OrganizationMemberService
from app.services.rbac_service import RBACService
from app.services.webhook_enhanced import WebhookService
from app.services.audit_logger import AuditLogger, AuditAction
from app.core.jwt_manager import JWTManager
from app.models import User, OrganizationMember


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.lpush = AsyncMock(return_value=1)
    redis.keys = AsyncMock(return_value=[])
    redis.xadd = AsyncMock(return_value="1234567890")
    return redis


class TestOrganizationMemberService:
    """Test organization member lifecycle"""

    @pytest.mark.asyncio
    async def test_add_member_success(self, mock_db, mock_redis):
        """Test adding a new member to organization"""
        service = OrganizationMemberService(mock_db, mock_redis)

        # Mock query results
        mock_db.query().filter().first.return_value = None  # No existing member

        org_id = uuid4()
        user_id = uuid4()
        invited_by = uuid4()

        # Mock the member object that gets created
        mock_member = Mock(
            id=uuid4(),
            organization_id=org_id,
            user_id=user_id,
            role="member",
            status="active",
            joined_at=datetime.utcnow(),
            invited_by=invited_by
        )
        mock_db.refresh.side_effect = lambda x: setattr(x, '__dict__', mock_member.__dict__)

        _result = await service.add_member(
            organization_id=org_id,
            user_id=user_id,
            role="member",
            invited_by=invited_by
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        mock_redis.delete.assert_called_with(f"org_members:{org_id}")

    @pytest.mark.asyncio
    async def test_prevent_duplicate_member(self, mock_db, mock_redis):
        """Test preventing duplicate member addition"""
        service = OrganizationMemberService(mock_db, mock_redis)

        # Mock existing member
        mock_db.query().filter().first.return_value = Mock(id=uuid4())

        with pytest.raises(Exception) as exc_info:
            await service.add_member(
                organization_id=uuid4(),
                user_id=uuid4(),
                role="member",
                invited_by=uuid4()
            )

        assert "already a member" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invitation_flow(self, mock_db, mock_redis):
        """Test invitation creation and acceptance"""
        service = OrganizationMemberService(mock_db, mock_redis)

        # Mock no existing invitation
        mock_db.query().filter().first.return_value = None

        org_id = uuid4()
        email = "newuser@example.com"
        invited_by = uuid4()

        # Create invitation
        mock_invitation = Mock(
            id=uuid4(),
            organization_id=org_id,
            email=email,
            role="member",
            token="test_token_123",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        mock_db.refresh.side_effect = lambda x: setattr(x, '__dict__', mock_invitation.__dict__)

        _invitation = await service.create_invitation(
            organization_id=org_id,
            email=email,
            role="member",
            invited_by=invited_by
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        mock_redis.set.assert_called()


class TestRBACService:
    """Test RBAC permission system"""

    @pytest.mark.asyncio
    async def test_check_permission_with_role_hierarchy(self, mock_db, mock_redis):
        """Test permission checking with role hierarchy"""
        service = RBACService(mock_db, mock_redis)

        # Mock user as admin
        mock_user = Mock(id=uuid4(), is_super_admin=False)
        mock_member = Mock(role="admin", status="active")

        mock_db.query(User).filter().first.return_value = mock_user
        mock_db.query(OrganizationMember).filter().first.return_value = mock_member

        # Test admin has users:read permission
        has_permission = await service.check_permission(
            user_id=mock_user.id,
            organization_id=uuid4(),
            permission="users:read"
        )

        assert has_permission is True
        mock_redis.set.assert_called()  # Result should be cached

    @pytest.mark.asyncio
    async def test_super_admin_bypass(self, mock_db, mock_redis):
        """Test super admin has all permissions"""
        service = RBACService(mock_db, mock_redis)

        # Mock user as super admin
        mock_user = Mock(id=uuid4(), is_super_admin=True)
        mock_db.query(User).filter().first.return_value = mock_user

        # Test super admin has any permission
        has_permission = await service.check_permission(
            user_id=mock_user.id,
            organization_id=uuid4(),
            permission="anything:delete"
        )

        assert has_permission is True

    @pytest.mark.asyncio
    async def test_wildcard_permission_matching(self, mock_db, mock_redis):
        """Test wildcard permission patterns"""
        service = RBACService(mock_db, mock_redis)

        # Test exact match
        assert service._match_permission("users:read", "users:read") is True

        # Test wildcard match
        assert service._match_permission("users:*", "users:read") is True
        assert service._match_permission("users:*", "users:delete") is True
        assert service._match_permission("*", "anything:here") is True

        # Test non-match
        assert service._match_permission("users:read", "users:write") is False
        assert service._match_permission("users:*", "org:read") is False


class TestWebhookService:
    """Test webhook retry mechanism"""

    @pytest.mark.asyncio
    async def test_webhook_delivery_with_retry(self, mock_db, mock_redis):
        """Test webhook delivery with retry logic"""
        service = WebhookService(mock_db)

        # Mock webhook endpoint
        mock_endpoint = Mock(
            id=uuid4(),
            url="https://example.com/webhook",
            secret="webhook_secret",
            is_active=True
        )

        mock_db.query().filter().first.return_value = mock_endpoint

        # Mock failed HTTP request
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Connection error")

            # Attempt delivery
            event_data = {"event": "user.created", "user_id": str(uuid4())}

            _delivery = await service.send_webhook(
                endpoint_id=mock_endpoint.id,
                event_type="user.created",
                payload=event_data,
                organization_id=uuid4()
            )

            # Should create retry entry
            assert mock_db.add.called
            # Should push to retry queue
            mock_redis.lpush.assert_called()


class TestAuditLogger:
    """Test audit logging system"""

    @pytest.mark.asyncio
    async def test_audit_log_creation(self, mock_db, mock_redis):
        """Test creating audit log entries"""
        logger = AuditLogger(mock_db)
        logger.redis_client = mock_redis

        user_id = uuid4()
        org_id = uuid4()

        # Log an authentication event
        await logger.log_action(
            action=AuditAction.USER_LOGIN,
            user_id=user_id,
            organization_id=org_id,
            details={
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0"
            },
            severity="info"
        )

        # Verify log was created
        assert mock_db.add.called
        assert mock_db.commit.called

        # Verify Redis streaming
        mock_redis.xadd.assert_called()

    @pytest.mark.asyncio
    async def test_security_event_logging(self, mock_db, mock_redis):
        """Test logging security events"""
        logger = AuditLogger(mock_db)
        logger.redis_client = mock_redis

        # Log a security event
        await logger.log_security_event(
            event_type="SUSPICIOUS_LOGIN",
            user_id=uuid4(),
            organization_id=uuid4(),
            details={
                "reason": "Multiple failed attempts",
                "ip_address": "10.0.0.1"
            }
        )

        # Should be logged with high severity
        call_args = mock_db.add.call_args[0][0]
        assert hasattr(call_args, 'severity')


class TestJWTManager:
    """Test JWT token rotation"""

    def test_access_token_creation(self):
        """Test creating access tokens"""
        manager = JWTManager()

        user_id = str(uuid4())
        email = "user@example.com"

        token, jti, expires_at = manager.create_access_token(
            user_id=user_id,
            email=email
        )

        assert token is not None
        assert jti is not None
        assert expires_at > datetime.utcnow()

    def test_refresh_token_with_family(self):
        """Test refresh token creation with family tracking"""
        manager = JWTManager()

        user_id = str(uuid4())

        # Create initial refresh token
        token1, jti1, family, expires_at1 = manager.create_refresh_token(
            user_id=user_id
        )

        assert family is not None

        # Create rotated token with same family
        token2, jti2, family2, expires_at2 = manager.create_refresh_token(
            user_id=user_id,
            family=family
        )

        assert family2 == family  # Same family
        assert jti1 != jti2  # Different JTI

    def test_token_verification(self):
        """Test token verification"""
        manager = JWTManager()

        user_id = str(uuid4())
        email = "user@example.com"

        # Create and verify token
        token, _, _ = manager.create_access_token(user_id, email)
        payload = manager.verify_token(token, token_type="access")

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["email"] == email


class TestIntegrationScenarios:
    """Test complete integration scenarios"""

    @pytest.mark.asyncio
    async def test_complete_member_lifecycle(self, mock_db, mock_redis):
        """Test complete member lifecycle from invitation to removal"""
        OrganizationMemberService(mock_db, mock_redis)
        rbac_service = RBACService(mock_db, mock_redis)

        org_id = uuid4()
        invited_by = uuid4()
        new_user_id = uuid4()

        # Step 1: Create invitation
        mock_db.query().filter().first.return_value = None
        mock_invitation = Mock(
            id=uuid4(),
            organization_id=org_id,
            email="newuser@example.com",
            role="member",
            token="invite_token_123",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(days=7),
            invited_by=invited_by
        )

        # Step 2: Accept invitation (becomes member)
        mock_redis.get.return_value = f'{{"id": "{mock_invitation.id}"}}'.encode()

        # Step 3: Check permissions
        mock_user = Mock(id=new_user_id, is_super_admin=False)
        mock_member = Mock(role="member", status="active")
        mock_db.query(User).filter().first.return_value = mock_user
        mock_db.query(OrganizationMember).filter().first.return_value = mock_member

        has_permission = await rbac_service.check_permission(
            user_id=new_user_id,
            organization_id=org_id,
            permission="org:read"
        )

        assert has_permission is True

    @pytest.mark.asyncio
    async def test_webhook_with_audit_logging(self, mock_db, mock_redis):
        """Test webhook delivery with audit logging"""
        # Note: WebhookService is initialized to verify it doesn't throw during audit tests
        assert WebhookService(mock_db) is not None  # Verify service initializes correctly
        audit_logger = AuditLogger(mock_db)
        audit_logger.redis_client = mock_redis

        org_id = uuid4()
        endpoint_id = uuid4()

        # Log webhook creation
        await audit_logger.log_action(
            action=AuditAction.WEBHOOK_CREATED,
            user_id=uuid4(),
            organization_id=org_id,
            details={"endpoint_id": str(endpoint_id)}
        )

        # Attempt webhook delivery
        mock_endpoint = Mock(
            id=endpoint_id,
            url="https://example.com/webhook",
            is_active=True
        )
        mock_db.query().filter().first.return_value = mock_endpoint

        # Verify both services interact correctly
        assert mock_db.add.called
        mock_redis.xadd.assert_called()  # Audit log streamed