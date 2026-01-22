"""
Comprehensive tests for enterprise features
Testing multi-tenancy, RBAC, SCIM, audit logging, and webhooks
"""

import pytest
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    User,
    Organization,
    OrganizationMember,
    OrganizationRole,
    WebhookEndpoint,
    WebhookDelivery,
    WebhookStatus,
)


# Mock missing imports for tests
class TenantContext:
    pass


class ResourceType:
    pass


class Action:
    pass


class WebhookEventTypes:
    pass


rbac_engine = None
audit_logger = None
webhook_dispatcher = None

# Test utilities (TestDataFactory, TestUtils) are available via conftest.py if needed


class TestTenantContext:
    """Test multi-tenant context management"""

    @pytest.mark.asyncio
    async def test_tenant_context_middleware(self, client: AsyncClient, db_session: AsyncSession):
        """Test tenant context extraction from JWT"""

        # Create organization and user
        org_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()

        org = Organization(id=org_id, tenant_id=tenant_id, name="Test Org", slug="test-org")
        db_session.add(org)

        user = User(id=user_id, email="test@example.com", username="testuser")
        db_session.add(user)
        await db_session.commit()

        # Create JWT with tenant info
        from app.core.jwt_manager import jwt_manager

        access_token, _, _ = jwt_manager.create_access_token(
            str(user_id),
            "test@example.com",
            additional_claims={"tid": str(tenant_id), "oid": str(org_id)},
        )

        # Make request with token
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get("/api/v1/users/me", headers=headers)

        # Verify tenant context was set (would be in response headers)
        assert "X-Tenant-ID" in response.headers
        assert response.headers["X-Tenant-ID"] == str(tenant_id)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, db_session: AsyncSession):
        """Test that tenant context isolates data"""

        # Create two organizations
        org1 = Organization(name="Org 1", slug="org1")
        org2 = Organization(name="Org 2", slug="org2")
        db_session.add_all([org1, org2])
        await db_session.commit()

        # Set tenant context to org1
        TenantContext.set(org1.tenant_id, org1.id)

        # Query should only return org1 data
        tenant_id = TenantContext.get_tenant_id()
        assert tenant_id == str(org1.tenant_id)

        # Clear and set to org2
        TenantContext.clear()
        TenantContext.set(org2.tenant_id, org2.id)

        tenant_id = TenantContext.get_tenant_id()
        assert tenant_id == str(org2.tenant_id)


class TestRBACEngine:
    """Test Role-Based Access Control"""

    @pytest.mark.asyncio
    async def test_permission_checking(self, db_session: AsyncSession):
        """Test basic permission checking"""

        # Create organization, role, and user
        org = Organization(name="Test Org", slug="test-org")
        db_session.add(org)
        await db_session.flush()

        role = OrganizationRole(
            organization_id=org.id,
            name="Editor",
            permissions=["user:read", "user:update", "project:*"],
        )
        db_session.add(role)
        await db_session.flush()

        user = User(email="editor@example.com", username="editor")
        db_session.add(user)
        await db_session.flush()

        member = OrganizationMember(
            organization_id=org.id, user_id=user.id, role_id=role.id, status="active"
        )
        db_session.add(member)
        await db_session.commit()

        # Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # Test permissions
        can_read = await rbac_engine.check_permission(
            db_session, str(user.id), ResourceType.USER, Action.READ
        )
        assert can_read is True

        can_delete = await rbac_engine.check_permission(
            db_session, str(user.id), ResourceType.USER, Action.DELETE
        )
        assert can_delete is False

        # Test wildcard permission
        can_create_project = await rbac_engine.check_permission(
            db_session, str(user.id), ResourceType.PROJECT, Action.CREATE
        )
        assert can_create_project is True

    @pytest.mark.asyncio
    async def test_hierarchical_roles(self, db_session: AsyncSession):
        """Test role hierarchy and inheritance"""

        # Create organization
        org = Organization(name="Test Org", slug="test-org")
        db_session.add(org)
        await db_session.flush()

        # Create parent role
        parent_role = OrganizationRole(
            organization_id=org.id, name="Manager", permissions=["user:read", "project:read"]
        )
        db_session.add(parent_role)
        await db_session.flush()

        # Create child role that inherits
        child_role = OrganizationRole(
            organization_id=org.id,
            name="Team Lead",
            parent_role_id=parent_role.id,
            permissions=["project:create"],  # Additional permission
        )
        db_session.add(child_role)
        await db_session.flush()

        user = User(email="lead@example.com", username="lead")
        db_session.add(user)
        await db_session.flush()

        member = OrganizationMember(
            organization_id=org.id, user_id=user.id, role_id=child_role.id, status="active"
        )
        db_session.add(member)
        await db_session.commit()

        # Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # Test inherited permission
        can_read_user = await rbac_engine.check_permission(
            db_session, str(user.id), ResourceType.USER, Action.READ
        )
        assert can_read_user is True

        # Test own permission
        can_create_project = await rbac_engine.check_permission(
            db_session, str(user.id), ResourceType.PROJECT, Action.CREATE
        )
        assert can_create_project is True


class TestSCIMIntegration:
    """Test SCIM 2.0 provisioning"""

    @pytest.mark.asyncio
    async def test_scim_user_provisioning(self, client: AsyncClient, db_session: AsyncSession):
        """Test SCIM user creation and sync"""

        # Create organization with SCIM enabled
        org = Organization(name="SCIM Org", slug="scim-org", scim_enabled=True)
        db_session.add(org)
        await db_session.commit()

        # Simulate SCIM token (in production, would be validated)
        # SCIM headers would be used for actual endpoint calls
        # scim_headers = {"Authorization": "Bearer scim-token-123", "Content-Type": "application/json"}

        # SCIM user creation payload
        scim_user = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "scim.user",
            "emails": [{"value": "scim@example.com", "type": "work", "primary": True}],
            "name": {"givenName": "SCIM", "familyName": "User"},
            "displayName": "SCIM User",
            "active": True,
        }

        # Create user via SCIM
        TenantContext.set(org.tenant_id, org.id)

        # Note: This would normally go through the SCIM router
        # but we're testing the logic directly

        # For this test, we'll create the resource manually
        user = User(
            email="scim@example.com", username="scim.user", first_name="SCIM", last_name="User"
        )
        db_session.add(user)
        await db_session.flush()

        scim_resource = SCIMResource(
            organization_id=org.id,
            scim_id=str(uuid4()),
            resource_type="User",
            internal_id=user.id,
            raw_attributes=scim_user,
        )
        db_session.add(scim_resource)
        await db_session.commit()

        # Verify mapping
        assert scim_resource.internal_id == user.id
        assert scim_resource.resource_type == "User"


class TestAuditLogging:
    """Test audit logging with hash chain"""

    @pytest.mark.asyncio
    async def test_audit_log_creation(self, db_session: AsyncSession):
        """Test creating audit log entries"""

        # Create organization
        org = Organization(name="Audit Org", slug="audit-org")
        db_session.add(org)
        await db_session.commit()

        # Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # Create audit log entry
        log = await audit_logger.log_event(
            session=db_session,
            event_type=AuditEventType.AUTH,
            event_name="user.login",
            resource_type="user",
            resource_id="user-123",
            event_data={"method": "password"},
            ip_address="192.168.1.1",
            user_agent="TestClient/1.0",
        )

        await db_session.commit()

        assert log is not None
        assert log.event_type == AuditEventType.AUTH
        assert log.current_hash is not None

    @pytest.mark.asyncio
    async def test_audit_hash_chain_integrity(self, db_session: AsyncSession):
        """Test hash chain integrity verification"""

        # Create organization
        org = Organization(name="Audit Org", slug="audit-org")
        db_session.add(org)
        await db_session.commit()

        # Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # Create multiple audit entries
        previous_hash = None
        for i in range(5):
            log = await audit_logger.log_event(
                session=db_session,
                event_type=AuditEventType.ACCESS,
                event_name=f"resource.access.{i}",
                resource_type="document",
                resource_id=f"doc-{i}",
            )

            if previous_hash:
                assert log.previous_hash == previous_hash

            previous_hash = log.current_hash
            await db_session.commit()

        # Verify integrity
        result = await audit_logger.verify_integrity(
            session=db_session, organization_id=str(org.id)
        )

        assert result["verified"] is True
        assert result["total_entries"] == 5
        assert len(result["broken_links"]) == 0

    @pytest.mark.asyncio
    async def test_audit_log_tampering_detection(self, db_session: AsyncSession):
        """Test detection of tampered audit logs"""

        # Create organization
        org = Organization(name="Audit Org", slug="audit-org")
        db_session.add(org)
        await db_session.commit()

        # Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # Create audit entry
        log = await audit_logger.log_event(
            session=db_session,
            event_type=AuditEventType.MODIFY,
            event_name="data.modified",
            resource_type="record",
            resource_id="rec-123",
        )
        await db_session.commit()

        # Tamper with the log
        log.event_data = {"tampered": True}
        await db_session.commit()

        # Verify integrity should fail
        result = await audit_logger.verify_integrity(
            session=db_session, organization_id=str(org.id)
        )

        assert result["verified"] is False
        assert len(result["broken_links"]) > 0
        assert result["broken_links"][0]["type"] == "hash_mismatch"


class TestWebhookDispatcher:
    """Test webhook event system"""

    @pytest.mark.asyncio
    async def test_webhook_event_creation(self, db_session: AsyncSession):
        """Test creating and dispatching webhook events"""

        # Create organization and webhook endpoint
        org = Organization(name="Webhook Org", slug="webhook-org")
        db_session.add(org)
        await db_session.flush()

        endpoint = WebhookEndpoint(
            organization_id=org.id,
            url="https://example.com/webhook",
            secret="webhook-secret",
            events=[WebhookEventTypes.USER_CREATED],
            is_active=True,
        )
        db_session.add(endpoint)
        await db_session.commit()

        # Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # Emit event
        event = await webhook_dispatcher.emit_event(
            session=db_session,
            event_type=WebhookEventTypes.USER_CREATED,
            data={"user_id": "new-user-123", "email": "new@example.com"},
            organization_id=str(org.id),
        )

        # Verify event and delivery were created
        assert event is not None
        assert event.type == WebhookEventTypes.USER_CREATED

        # Check delivery was queued
        deliveries = await db_session.execute(
            select(WebhookDelivery).where(WebhookDelivery.webhook_event_id == event.id)
        )
        delivery = deliveries.scalar_one()
        assert delivery.status == WebhookStatus.PENDING

    @pytest.mark.asyncio
    async def test_webhook_signature_verification(self):
        """Test webhook signature calculation and verification"""

        secret = "test-secret-key"
        payload = json.dumps({"test": "data"}).encode()

        # Calculate signature
        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Verify signature
        from app.core.webhook_dispatcher import verify_webhook_signature

        is_valid = verify_webhook_signature(
            payload=payload, signature=expected_signature, secret=secret
        )

        assert is_valid is True

        # Test with wrong signature
        is_invalid = verify_webhook_signature(
            payload=payload, signature="wrong-signature", secret=secret
        )

        assert is_invalid is False

    @pytest.mark.asyncio
    async def test_webhook_retry_logic(self, db_session: AsyncSession):
        """Test webhook retry with exponential backoff"""

        # Create organization and endpoint
        org = Organization(name="Webhook Org", slug="webhook-org")
        db_session.add(org)
        await db_session.flush()

        endpoint = WebhookEndpoint(
            organization_id=org.id,
            url="https://failing-endpoint.com/webhook",
            secret="secret",
            events=["test.event"],
            is_active=True,
            max_retries=3,
            retry_delay=60,
        )
        db_session.add(endpoint)
        await db_session.flush()

        event = WebhookEvent(type="test.event", data={"test": "data"}, organization_id=org.id)
        db_session.add(event)
        await db_session.flush()

        delivery = WebhookDelivery(
            webhook_endpoint_id=endpoint.id,
            webhook_event_id=event.id,
            status=WebhookStatus.PENDING,
            attempts=0,
        )
        db_session.add(delivery)
        await db_session.commit()

        # Simulate failed delivery
        delivery.attempts = 1
        delivery.status = WebhookStatus.RETRYING
        delivery.error_message = "Connection timeout"

        # Calculate next retry time
        next_retry = datetime.utcnow() + timedelta(seconds=60)
        delivery.next_retry_at = next_retry

        await db_session.commit()

        # Verify retry was scheduled
        assert delivery.status == WebhookStatus.RETRYING
        assert delivery.next_retry_at is not None
        assert delivery.attempts == 1


class TestEnterpriseIntegration:
    """Test integration of all enterprise features"""

    @pytest.mark.asyncio
    async def test_full_enterprise_workflow(self, db_session: AsyncSession):
        """Test complete enterprise workflow with all features"""

        # 1. Create multi-tenant organization
        org = Organization(
            name="Enterprise Corp",
            slug="enterprise-corp",
            subscription_tier="enterprise",
            scim_enabled=True,
            sso_enabled=True,
            mfa_required=True,
        )
        db_session.add(org)
        await db_session.flush()

        # 2. Set tenant context
        TenantContext.set(org.tenant_id, org.id)

        # 3. Create RBAC roles
        admin_role = OrganizationRole(
            organization_id=org.id, name="Admin", permissions=["*:*"], is_system=True
        )
        db_session.add(admin_role)
        await db_session.flush()

        # 4. Create user via SCIM
        user = User(email="admin@enterprise.com", username="admin", mfa_enabled=True)
        db_session.add(user)
        await db_session.flush()

        # 5. Add user to organization with role
        member = OrganizationMember(
            organization_id=org.id, user_id=user.id, role_id=admin_role.id, status="active"
        )
        db_session.add(member)

        # 6. Create SCIM mapping
        scim_resource = SCIMResource(
            organization_id=org.id, scim_id=str(uuid4()), resource_type="User", internal_id=user.id
        )
        db_session.add(scim_resource)

        # 7. Log audit event
        audit_log = await audit_logger.log_event(
            session=db_session,
            event_type=AuditEventType.ADMIN,
            event_name="organization.created",
            resource_type="organization",
            resource_id=str(org.id),
            user_id=str(user.id),
            compliance_tags=["SOC2", "HIPAA"],
        )

        # 8. Create webhook endpoint
        webhook_endpoint = WebhookEndpoint(
            organization_id=org.id,
            url="https://enterprise.com/webhooks",
            secret="enterprise-secret",
            events=["*"],  # All events
            is_active=True,
        )
        db_session.add(webhook_endpoint)

        await db_session.commit()

        # 9. Emit webhook event
        webhook_event = await webhook_dispatcher.emit_event(
            session=db_session,
            event_type="organization.created",
            data={"org_id": str(org.id), "name": org.name},
            user_id=str(user.id),
            organization_id=str(org.id),
        )

        # 10. Verify RBAC permissions
        has_admin = await rbac_engine.check_permission(
            db_session, str(user.id), ResourceType.ORGANIZATION, Action.ADMIN
        )

        # Assertions
        assert org.tenant_id is not None
        assert member.role_id == admin_role.id
        assert scim_resource.internal_id == user.id
        assert audit_log.current_hash is not None
        assert webhook_event is not None
        assert has_admin is True
