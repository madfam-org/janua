"""
Comprehensive Webhook Service Test Suite
Tests for webhook event notifications and delivery
"""

import hashlib
import hmac
from datetime import datetime

import pytest

from app.services.webhooks import (
    WebhookService,
    WebhookEventType,
    WebhookPayload,
    trigger_user_webhook,
    trigger_organization_webhook,
    trigger_security_webhook,
)

pytestmark = pytest.mark.asyncio


class TestWebhookEventType:
    """Test WebhookEventType enum."""

    def test_user_created_value(self):
        """Test USER_CREATED event type."""
        assert WebhookEventType.USER_CREATED.value == "user.created"

    def test_user_updated_value(self):
        """Test USER_UPDATED event type."""
        assert WebhookEventType.USER_UPDATED.value == "user.updated"

    def test_user_deleted_value(self):
        """Test USER_DELETED event type."""
        assert WebhookEventType.USER_DELETED.value == "user.deleted"

    def test_session_created_value(self):
        """Test SESSION_CREATED event type."""
        assert WebhookEventType.SESSION_CREATED.value == "session.created"

    def test_organization_created_value(self):
        """Test ORGANIZATION_CREATED event type."""
        assert WebhookEventType.ORGANIZATION_CREATED.value == "organization.created"

    def test_member_added_value(self):
        """Test MEMBER_ADDED event type."""
        assert WebhookEventType.MEMBER_ADDED.value == "organization.member.added"

    def test_mfa_enabled_value(self):
        """Test MFA_ENABLED event type."""
        assert WebhookEventType.MFA_ENABLED.value == "security.mfa.enabled"

    def test_password_changed_value(self):
        """Test PASSWORD_CHANGED event type."""
        assert WebhookEventType.PASSWORD_CHANGED.value == "security.password.changed"

    def test_oauth_linked_value(self):
        """Test OAUTH_LINKED event type."""
        assert WebhookEventType.OAUTH_LINKED.value == "oauth.account.linked"

    def test_admin_action_value(self):
        """Test ADMIN_ACTION event type."""
        assert WebhookEventType.ADMIN_ACTION.value == "admin.action"

    def test_system_alert_value(self):
        """Test SYSTEM_ALERT event type."""
        assert WebhookEventType.SYSTEM_ALERT.value == "system.alert"


class TestWebhookPayload:
    """Test WebhookPayload model."""

    def test_create_payload(self):
        """Test creating a webhook payload."""
        payload = WebhookPayload(
            id="event-123",
            type=WebhookEventType.USER_CREATED,
            created_at=datetime.utcnow().isoformat(),
            data={"user_id": "user-456"},
            object="user",
        )

        assert payload.id == "event-123"
        assert payload.type == WebhookEventType.USER_CREATED
        assert payload.object == "user"
        assert payload.api_version == "v1"

    def test_payload_has_default_api_version(self):
        """Test payload has default API version."""
        payload = WebhookPayload(
            id="event-123",
            type=WebhookEventType.USER_CREATED,
            created_at=datetime.utcnow().isoformat(),
            data={},
            object="user",
        )

        assert payload.api_version == "v1"


class TestWebhookServiceInitialization:
    """Test WebhookService initialization."""

    def test_service_initialization(self):
        """Test service initializes with defaults."""
        service = WebhookService()

        assert service.max_retries == 3
        assert service.retry_delays == [1, 5, 30]

    def test_service_has_client(self):
        """Test service has HTTP client."""
        service = WebhookService()

        assert service.client is not None


class TestGenerateSignature:
    """Test webhook signature generation."""

    @pytest.fixture
    def service(self):
        """Create WebhookService instance."""
        return WebhookService()

    def test_signature_generation(self, service):
        """Test signature is generated correctly."""
        secret = "test-secret"
        payload = '{"event": "test"}'

        signature = service._generate_signature(secret, payload)

        # Verify it's a valid HMAC-SHA256 hex digest
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest length

    def test_signature_deterministic(self, service):
        """Test same inputs produce same signature."""
        secret = "test-secret"
        payload = '{"event": "test"}'

        sig1 = service._generate_signature(secret, payload)
        sig2 = service._generate_signature(secret, payload)

        assert sig1 == sig2

    def test_different_secrets_different_signatures(self, service):
        """Test different secrets produce different signatures."""
        payload = '{"event": "test"}'

        sig1 = service._generate_signature("secret1", payload)
        sig2 = service._generate_signature("secret2", payload)

        assert sig1 != sig2

    def test_different_payloads_different_signatures(self, service):
        """Test different payloads produce different signatures."""
        secret = "test-secret"

        sig1 = service._generate_signature(secret, '{"event": "test1"}')
        sig2 = service._generate_signature(secret, '{"event": "test2"}')

        assert sig1 != sig2


class TestVerifyWebhookSignature:
    """Test webhook signature verification."""

    @pytest.fixture
    def service(self):
        """Create WebhookService instance."""
        return WebhookService()

    async def test_verify_valid_signature(self, service):
        """Test verifying a valid signature."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        signature = service._generate_signature(secret, payload)

        result = await service.verify_webhook_signature(secret, payload, signature)

        assert result is True

    async def test_verify_invalid_signature(self, service):
        """Test verifying an invalid signature."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        invalid_signature = "invalid-signature-value"

        result = await service.verify_webhook_signature(secret, payload, invalid_signature)

        assert result is False

    async def test_verify_wrong_secret(self, service):
        """Test verifying with wrong secret."""
        payload = '{"event": "test"}'
        signature = service._generate_signature("secret1", payload)

        result = await service.verify_webhook_signature("wrong-secret", payload, signature)

        assert result is False


class TestGetObjectType:
    """Test getting object type from event type."""

    @pytest.fixture
    def service(self):
        """Create WebhookService instance."""
        return WebhookService()

    def test_user_event_returns_user(self, service):
        """Test user events return 'user' object type."""
        result = service._get_object_type(WebhookEventType.USER_CREATED)
        assert result == "user"

    def test_session_event_returns_session(self, service):
        """Test session events return 'session' object type."""
        result = service._get_object_type(WebhookEventType.SESSION_CREATED)
        assert result == "session"

    def test_organization_event_returns_organization(self, service):
        """Test organization events return 'organization' object type."""
        result = service._get_object_type(WebhookEventType.ORGANIZATION_CREATED)
        assert result == "organization"

    def test_security_event_returns_security(self, service):
        """Test security events return 'security' object type."""
        result = service._get_object_type(WebhookEventType.MFA_ENABLED)
        assert result == "security"

    def test_oauth_event_returns_oauth(self, service):
        """Test OAuth events return 'oauth' object type."""
        result = service._get_object_type(WebhookEventType.OAUTH_LINKED)
        assert result == "oauth"


class TestProcessWebhooks:
    """Test webhook processing helper functions."""

    def test_process_stripe_webhook(self):
        """Test processing Stripe webhook data."""
        webhook_data = {"type": "charge.succeeded", "data": {"amount": 1000}}

        result = WebhookService.process_stripe_webhook(webhook_data)

        assert result is not None
        assert isinstance(result, dict)

    def test_process_github_webhook(self):
        """Test processing GitHub webhook data."""
        webhook_data = {"action": "opened", "repository": {"name": "test-repo"}}

        result = WebhookService.process_github_webhook(webhook_data)

        assert result is not None
        assert isinstance(result, dict)

    def test_process_generic_webhook(self):
        """Test processing generic webhook data."""
        webhook_data = {"event": "custom", "data": {"key": "value"}}

        result = WebhookService.process_generic_webhook(webhook_data)

        assert result is not None
        assert isinstance(result, dict)


class TestServiceMethods:
    """Test service method existence and signatures."""

    @pytest.fixture
    def service(self):
        """Create WebhookService instance."""
        return WebhookService()

    def test_has_trigger_event(self, service):
        """Test service has trigger_event method."""
        assert hasattr(service, "trigger_event")
        import asyncio
        assert asyncio.iscoroutinefunction(service.trigger_event)

    def test_has_deliver_webhook(self, service):
        """Test service has _deliver_webhook method."""
        assert hasattr(service, "_deliver_webhook")
        import asyncio
        assert asyncio.iscoroutinefunction(service._deliver_webhook)

    def test_has_register_endpoint(self, service):
        """Test service has register_endpoint method."""
        assert hasattr(service, "register_endpoint")
        import asyncio
        assert asyncio.iscoroutinefunction(service.register_endpoint)

    def test_has_update_endpoint(self, service):
        """Test service has update_endpoint method."""
        assert hasattr(service, "update_endpoint")
        import asyncio
        assert asyncio.iscoroutinefunction(service.update_endpoint)

    def test_has_delete_endpoint(self, service):
        """Test service has delete_endpoint method."""
        assert hasattr(service, "delete_endpoint")
        import asyncio
        assert asyncio.iscoroutinefunction(service.delete_endpoint)

    def test_has_test_endpoint(self, service):
        """Test service has test_endpoint method."""
        assert hasattr(service, "test_endpoint")
        import asyncio
        assert asyncio.iscoroutinefunction(service.test_endpoint)

    def test_has_get_endpoint_stats(self, service):
        """Test service has get_endpoint_stats method."""
        assert hasattr(service, "get_endpoint_stats")
        import asyncio
        assert asyncio.iscoroutinefunction(service.get_endpoint_stats)

    def test_has_cleanup_old_events(self, service):
        """Test service has cleanup_old_events method."""
        assert hasattr(service, "cleanup_old_events")
        import asyncio
        assert asyncio.iscoroutinefunction(service.cleanup_old_events)

    def test_has_verify_webhook_signature(self, service):
        """Test service has verify_webhook_signature method."""
        assert hasattr(service, "verify_webhook_signature")
        import asyncio
        assert asyncio.iscoroutinefunction(service.verify_webhook_signature)


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_trigger_user_webhook_exists(self):
        """Test trigger_user_webhook function exists."""
        assert callable(trigger_user_webhook)
        import asyncio
        assert asyncio.iscoroutinefunction(trigger_user_webhook)

    def test_trigger_organization_webhook_exists(self):
        """Test trigger_organization_webhook function exists."""
        assert callable(trigger_organization_webhook)
        import asyncio
        assert asyncio.iscoroutinefunction(trigger_organization_webhook)

    def test_trigger_security_webhook_exists(self):
        """Test trigger_security_webhook function exists."""
        assert callable(trigger_security_webhook)
        import asyncio
        assert asyncio.iscoroutinefunction(trigger_security_webhook)


class TestWebhookEventTypeCategories:
    """Test webhook event type categorization."""

    def test_user_events_category(self):
        """Test user events are properly categorized."""
        user_events = [
            WebhookEventType.USER_CREATED,
            WebhookEventType.USER_UPDATED,
            WebhookEventType.USER_DELETED,
            WebhookEventType.USER_VERIFIED,
            WebhookEventType.USER_SUSPENDED,
            WebhookEventType.USER_REACTIVATED,
        ]

        for event in user_events:
            assert event.value.startswith("user.")

    def test_session_events_category(self):
        """Test session events are properly categorized."""
        session_events = [
            WebhookEventType.SESSION_CREATED,
            WebhookEventType.SESSION_REVOKED,
            WebhookEventType.SESSION_EXPIRED,
        ]

        for event in session_events:
            assert event.value.startswith("session.")

    def test_organization_events_category(self):
        """Test organization events are properly categorized."""
        org_events = [
            WebhookEventType.ORGANIZATION_CREATED,
            WebhookEventType.ORGANIZATION_UPDATED,
            WebhookEventType.ORGANIZATION_DELETED,
            WebhookEventType.MEMBER_ADDED,
            WebhookEventType.MEMBER_REMOVED,
            WebhookEventType.MEMBER_ROLE_CHANGED,
        ]

        for event in org_events:
            assert event.value.startswith("organization.")

    def test_security_events_category(self):
        """Test security events are properly categorized."""
        security_events = [
            WebhookEventType.MFA_ENABLED,
            WebhookEventType.MFA_DISABLED,
            WebhookEventType.PASSKEY_REGISTERED,
            WebhookEventType.PASSKEY_REMOVED,
            WebhookEventType.PASSWORD_CHANGED,
            WebhookEventType.PASSWORD_RESET,
            WebhookEventType.SUSPICIOUS_ACTIVITY,
        ]

        for event in security_events:
            assert event.value.startswith("security.")


class TestRetryConfiguration:
    """Test retry configuration for webhook delivery."""

    @pytest.fixture
    def service(self):
        """Create WebhookService instance."""
        return WebhookService()

    def test_max_retries_default(self, service):
        """Test default max retries value."""
        assert service.max_retries == 3

    def test_retry_delays_configuration(self, service):
        """Test retry delays are configured."""
        assert len(service.retry_delays) == 3
        assert service.retry_delays[0] == 1  # First retry after 1 second
        assert service.retry_delays[1] == 5  # Second retry after 5 seconds
        assert service.retry_delays[2] == 30  # Third retry after 30 seconds

    def test_retry_delays_increase(self, service):
        """Test retry delays increase exponentially."""
        delays = service.retry_delays
        for i in range(len(delays) - 1):
            assert delays[i + 1] > delays[i]


class TestSignatureFormat:
    """Test webhook signature format and structure."""

    @pytest.fixture
    def service(self):
        """Create WebhookService instance."""
        return WebhookService()

    def test_signature_is_hex(self, service):
        """Test signature is hexadecimal string."""
        signature = service._generate_signature("secret", "payload")

        # All characters should be valid hex digits
        assert all(c in "0123456789abcdef" for c in signature.lower())

    def test_signature_length_sha256(self, service):
        """Test signature has correct length for SHA256."""
        signature = service._generate_signature("secret", "payload")

        # SHA256 produces 32 bytes = 64 hex characters
        assert len(signature) == 64

    def test_signature_matches_manual_hmac(self, service):
        """Test signature matches manual HMAC calculation."""
        secret = "test-secret"
        payload = "test-payload"

        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        result = service._generate_signature(secret, payload)

        assert result == expected
