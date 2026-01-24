"""
Tests for app/routers/v1/webhooks.py - Webhook Management Router

Tests webhook endpoint CRUD, delivery tracking, and security features.
Target: 4% → 55% coverage.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.asyncio


class TestWebhooksRouterInitialization:
    """Test webhooks router setup."""

    def test_webhooks_router_exists(self):
        """Test webhooks router is properly imported."""
        from app.routers.v1.webhooks import router

        assert router is not None
        assert router.prefix == "/webhooks"
        assert "webhooks" in router.tags


class TestWebhookEventType:
    """Test WebhookEventType enum."""

    def test_webhook_event_type_exists(self):
        """Test WebhookEventType enum is available."""
        from app.services.webhooks import WebhookEventType

        assert hasattr(WebhookEventType, "USER_CREATED")
        assert hasattr(WebhookEventType, "USER_UPDATED")
        assert hasattr(WebhookEventType, "USER_DELETED")

    def test_webhook_event_type_values(self):
        """Test WebhookEventType values are correct."""
        from app.services.webhooks import WebhookEventType

        assert WebhookEventType.USER_CREATED.value == "user.created"
        assert WebhookEventType.USER_UPDATED.value == "user.updated"
        assert WebhookEventType.SESSION_CREATED.value == "session.created"


class TestWebhookRequestModels:
    """Test webhook request/response models."""

    def test_webhook_endpoint_create_model(self):
        """Test WebhookEndpointCreate model."""
        from app.routers.v1.webhooks import WebhookEndpointCreate
        from app.services.webhooks import WebhookEventType

        request = WebhookEndpointCreate(
            url="https://example.com/webhook",
            events=[WebhookEventType.USER_CREATED],
            description="Test webhook",
        )
        assert str(request.url) == "https://example.com/webhook"
        assert WebhookEventType.USER_CREATED in request.events
        assert request.description == "Test webhook"

    def test_webhook_endpoint_create_with_headers(self):
        """Test WebhookEndpointCreate with custom headers."""
        from app.routers.v1.webhooks import WebhookEndpointCreate
        from app.services.webhooks import WebhookEventType

        request = WebhookEndpointCreate(
            url="https://example.com/webhook",
            events=[WebhookEventType.USER_CREATED],
            headers={"X-Custom-Header": "value"},
        )
        assert request.headers == {"X-Custom-Header": "value"}

    def test_webhook_endpoint_update_model(self):
        """Test WebhookEndpointUpdate model."""
        from app.routers.v1.webhooks import WebhookEndpointUpdate

        update = WebhookEndpointUpdate(
            is_active=False,
            description="Updated description",
        )
        assert update.is_active is False
        assert update.description == "Updated description"
        assert update.url is None

    def test_webhook_endpoint_response_model(self):
        """Test WebhookEndpointResponse model."""
        from app.routers.v1.webhooks import WebhookEndpointResponse

        response = WebhookEndpointResponse(
            id=uuid.uuid4(),
            url="https://example.com/webhook",
            secret="whsec_test123",
            events=["user.created"],
            is_active=True,
            description="Test",
            headers=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        assert response.is_active is True
        assert "user.created" in response.events

    def test_webhook_event_response_model(self):
        """Test WebhookEventResponse model."""
        from app.routers.v1.webhooks import WebhookEventResponse

        response = WebhookEventResponse(
            id=uuid.uuid4(),
            type="user.created",
            data={"user_id": "123"},
            created_at=datetime.utcnow(),
        )
        assert response.type == "user.created"
        assert response.data["user_id"] == "123"

    def test_webhook_delivery_response_model(self):
        """Test WebhookDeliveryResponse model."""
        from app.routers.v1.webhooks import WebhookDeliveryResponse

        response = WebhookDeliveryResponse(
            id=uuid.uuid4(),
            webhook_endpoint_id=uuid.uuid4(),
            webhook_event_id=uuid.uuid4(),
            status_code=200,
            response_body="OK",
            error=None,
            attempt=1,
            delivered_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        assert response.status_code == 200
        assert response.attempt == 1

    def test_webhook_stats_response_model(self):
        """Test WebhookStatsResponse model."""
        from app.routers.v1.webhooks import WebhookStatsResponse

        stats = WebhookStatsResponse(
            total_deliveries=100,
            successful=95,
            failed=5,
            success_rate=0.95,
            average_delivery_time=0.5,
            period_days=7,
        )
        assert stats.total_deliveries == 100
        assert stats.success_rate == 0.95

    def test_webhook_endpoint_list_response_model(self):
        """Test WebhookEndpointListResponse model."""
        from app.routers.v1.webhooks import WebhookEndpointListResponse

        response = WebhookEndpointListResponse(endpoints=[], total=0)
        assert response.total == 0
        assert isinstance(response.endpoints, list)

    def test_webhook_event_list_response_model(self):
        """Test WebhookEventListResponse model."""
        from app.routers.v1.webhooks import WebhookEventListResponse

        response = WebhookEventListResponse(events=[], total=0)
        assert response.total == 0
        assert isinstance(response.events, list)


class TestWebhooksEndpointsAuthentication:
    """Test webhooks endpoints require authentication."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_create_webhook_requires_auth(self):
        """Test create webhook requires authentication."""
        response = self.client.post(
            "/api/v1/webhooks/",
            json={
                "url": "https://example.com/webhook",
                "events": ["user.created"],
            },
        )
        assert response.status_code == 401

    def test_list_webhooks_requires_auth(self):
        """Test list webhooks requires authentication."""
        response = self.client.get("/api/v1/webhooks/")
        assert response.status_code == 401

    def test_get_webhook_requires_auth(self):
        """Test get webhook requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/webhooks/{endpoint_id}")
        assert response.status_code == 401

    def test_update_webhook_requires_auth(self):
        """Test update webhook requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.patch(
            f"/api/v1/webhooks/{endpoint_id}",
            json={"is_active": False},
        )
        assert response.status_code == 401

    def test_delete_webhook_requires_auth(self):
        """Test delete webhook requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.delete(f"/api/v1/webhooks/{endpoint_id}")
        assert response.status_code == 401

    def test_test_webhook_requires_auth(self):
        """Test test webhook requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.post(f"/api/v1/webhooks/{endpoint_id}/test")
        assert response.status_code == 401

    def test_get_webhook_stats_requires_auth(self):
        """Test get webhook stats requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/webhooks/{endpoint_id}/stats")
        assert response.status_code == 401

    def test_list_webhook_events_requires_auth(self):
        """Test list webhook events requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/webhooks/{endpoint_id}/events")
        assert response.status_code == 401

    def test_list_webhook_deliveries_requires_auth(self):
        """Test list webhook deliveries requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/webhooks/{endpoint_id}/deliveries")
        assert response.status_code == 401

    def test_regenerate_secret_requires_auth(self):
        """Test regenerate secret requires authentication."""
        endpoint_id = uuid.uuid4()
        response = self.client.post(f"/api/v1/webhooks/{endpoint_id}/regenerate-secret")
        assert response.status_code == 401

    def test_list_event_types_requires_auth(self):
        """Test list event types requires authentication."""
        response = self.client.get("/api/v1/webhooks/events/types")
        assert response.status_code == 401

    def test_verify_signature_requires_auth(self):
        """Test verify signature requires authentication."""
        response = self.client.post(
            "/api/v1/webhooks/verify-signature",
            params={
                "secret": "test",
                "payload": "test",
                "signature": "test",
            },
        )
        assert response.status_code == 401


class TestCheckWebhookPermission:
    """Test webhook permission checking helper."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.is_admin = False
        return user

    async def test_permission_denied_for_non_owner(self, mock_db, mock_user):
        """Test permission denied for non-owner."""
        from app.routers.v1.webhooks import check_webhook_permission

        endpoint_id = uuid.uuid4()
        mock_endpoint = MagicMock()
        mock_endpoint.user_id = uuid.uuid4()  # Different user
        mock_endpoint.organization_id = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_endpoint
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await check_webhook_permission(mock_db, mock_user, endpoint_id)

        assert exc_info.value.status_code == 403

    async def test_endpoint_not_found(self, mock_db, mock_user):
        """Test 404 when endpoint not found."""
        from app.routers.v1.webhooks import check_webhook_permission

        endpoint_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await check_webhook_permission(mock_db, mock_user, endpoint_id)

        assert exc_info.value.status_code == 404

    async def test_admin_can_access_any_endpoint(self, mock_db):
        """Test admin can access any endpoint."""
        from app.routers.v1.webhooks import check_webhook_permission

        admin_user = MagicMock()
        admin_user.id = uuid.uuid4()
        admin_user.is_admin = True

        endpoint_id = uuid.uuid4()
        mock_endpoint = MagicMock()
        mock_endpoint.user_id = uuid.uuid4()  # Different user
        mock_endpoint.organization_id = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_endpoint
        mock_db.execute.return_value = mock_result

        result = await check_webhook_permission(mock_db, admin_user, endpoint_id)
        assert result == mock_endpoint

    async def test_owner_can_access_own_endpoint(self, mock_db, mock_user):
        """Test owner can access their own endpoint."""
        from app.routers.v1.webhooks import check_webhook_permission

        endpoint_id = uuid.uuid4()
        mock_endpoint = MagicMock()
        mock_endpoint.user_id = mock_user.id  # Same user
        mock_endpoint.organization_id = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_endpoint
        mock_db.execute.return_value = mock_result

        result = await check_webhook_permission(mock_db, mock_user, endpoint_id)
        assert result == mock_endpoint


class TestWebhookServiceIntegration:
    """Test webhook service integration."""

    def test_webhook_service_exists(self):
        """Test webhook_service is available."""
        from app.services.webhooks import webhook_service

        assert webhook_service is not None

    def test_webhook_service_has_register_endpoint(self):
        """Test webhook_service has register_endpoint method."""
        from app.services.webhooks import webhook_service

        assert hasattr(webhook_service, "register_endpoint")

    def test_webhook_service_has_update_endpoint(self):
        """Test webhook_service has update_endpoint method."""
        from app.services.webhooks import webhook_service

        assert hasattr(webhook_service, "update_endpoint")

    def test_webhook_service_has_delete_endpoint(self):
        """Test webhook_service has delete_endpoint method."""
        from app.services.webhooks import webhook_service

        assert hasattr(webhook_service, "delete_endpoint")

    def test_webhook_service_has_test_endpoint(self):
        """Test webhook_service has test_endpoint method."""
        from app.services.webhooks import webhook_service

        assert hasattr(webhook_service, "test_endpoint")

    def test_webhook_service_has_get_endpoint_stats(self):
        """Test webhook_service has get_endpoint_stats method."""
        from app.services.webhooks import webhook_service

        assert hasattr(webhook_service, "get_endpoint_stats")

    def test_webhook_service_has_verify_signature(self):
        """Test webhook_service has verify_webhook_signature method."""
        from app.services.webhooks import webhook_service

        assert hasattr(webhook_service, "verify_webhook_signature")


class TestWebhookValidation:
    """Test webhook validation."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_create_webhook_invalid_url(self):
        """Test create webhook with invalid URL."""
        response = self.client.post(
            "/api/v1/webhooks/",
            json={
                "url": "not-a-valid-url",
                "events": ["user.created"],
            },
        )
        # Should fail validation (or auth first)
        assert response.status_code in [401, 422]

    def test_create_webhook_empty_events(self):
        """Test create webhook with empty events list."""
        response = self.client.post(
            "/api/v1/webhooks/",
            json={
                "url": "https://example.com/webhook",
                "events": [],
            },
        )
        # Should fail (auth or validation)
        assert response.status_code in [401, 422]


class TestWebhookEndpointCRUD:
    """Test webhook endpoint CRUD operations with mocks."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_get_endpoint_with_invalid_uuid(self):
        """Test get endpoint with invalid UUID format returns 401 or 422."""
        response = self.client.get("/api/v1/webhooks/not-a-uuid")
        # Auth happens before path validation, so 401 is expected
        assert response.status_code in [401, 422]

    def test_update_endpoint_with_invalid_uuid(self):
        """Test update endpoint with invalid UUID format returns 401 or 422."""
        response = self.client.patch(
            "/api/v1/webhooks/not-a-uuid",
            json={"is_active": False},
        )
        # Auth happens before path validation, so 401 is expected
        assert response.status_code in [401, 422]

    def test_delete_endpoint_with_invalid_uuid(self):
        """Test delete endpoint with invalid UUID format returns 401 or 422."""
        response = self.client.delete("/api/v1/webhooks/not-a-uuid")
        # Auth happens before path validation, so 401 is expected
        assert response.status_code in [401, 422]


class TestWebhookEventTypes:
    """Test webhook event type listing."""

    def test_all_event_types_are_strings(self):
        """Test all event types have string values."""
        from app.services.webhooks import WebhookEventType

        for event_type in WebhookEventType:
            assert isinstance(event_type.value, str)
            assert "." in event_type.value  # Format: category.action

    def test_user_events_exist(self):
        """Test user-related events exist."""
        from app.services.webhooks import WebhookEventType

        user_events = [e for e in WebhookEventType if e.value.startswith("user.")]
        assert len(user_events) > 0

    def test_session_events_exist(self):
        """Test session-related events exist."""
        from app.services.webhooks import WebhookEventType

        session_events = [e for e in WebhookEventType if e.value.startswith("session.")]
        assert len(session_events) > 0


class TestWebhookModelsConfig:
    """Test webhook model configurations."""

    def test_endpoint_response_from_attributes(self):
        """Test WebhookEndpointResponse has from_attributes config."""
        from app.routers.v1.webhooks import WebhookEndpointResponse

        assert WebhookEndpointResponse.model_config.get("from_attributes") is True

    def test_event_response_from_attributes(self):
        """Test WebhookEventResponse has from_attributes config."""
        from app.routers.v1.webhooks import WebhookEventResponse

        assert WebhookEventResponse.model_config.get("from_attributes") is True

    def test_delivery_response_from_attributes(self):
        """Test WebhookDeliveryResponse has from_attributes config."""
        from app.routers.v1.webhooks import WebhookDeliveryResponse

        assert WebhookDeliveryResponse.model_config.get("from_attributes") is True


class TestWebhookStatsCalculation:
    """Test webhook stats response calculations."""

    def test_stats_with_zero_deliveries(self):
        """Test stats response with zero deliveries."""
        from app.routers.v1.webhooks import WebhookStatsResponse

        stats = WebhookStatsResponse(
            total_deliveries=0,
            successful=0,
            failed=0,
            success_rate=0.0,
            average_delivery_time=0.0,
            period_days=7,
        )
        assert stats.success_rate == 0.0
        assert stats.total_deliveries == 0

    def test_stats_with_all_successful(self):
        """Test stats response with all successful deliveries."""
        from app.routers.v1.webhooks import WebhookStatsResponse

        stats = WebhookStatsResponse(
            total_deliveries=100,
            successful=100,
            failed=0,
            success_rate=1.0,
            average_delivery_time=0.25,
            period_days=30,
        )
        assert stats.success_rate == 1.0
        assert stats.failed == 0

    def test_stats_period_configurable(self):
        """Test stats period is configurable."""
        from app.routers.v1.webhooks import WebhookStatsResponse

        stats = WebhookStatsResponse(
            total_deliveries=10,
            successful=10,
            failed=0,
            success_rate=1.0,
            average_delivery_time=0.5,
            period_days=1,
        )
        assert stats.period_days == 1


class TestWebhookDeliveryAttempts:
    """Test webhook delivery attempt tracking."""

    def test_delivery_with_error(self):
        """Test delivery response with error."""
        from app.routers.v1.webhooks import WebhookDeliveryResponse

        delivery = WebhookDeliveryResponse(
            id=uuid.uuid4(),
            webhook_endpoint_id=uuid.uuid4(),
            webhook_event_id=uuid.uuid4(),
            status_code=None,
            response_body=None,
            error="Connection timeout",
            attempt=3,
            delivered_at=None,
            created_at=datetime.utcnow(),
        )
        assert delivery.error == "Connection timeout"
        assert delivery.status_code is None
        assert delivery.delivered_at is None

    def test_delivery_multiple_attempts(self):
        """Test delivery with multiple attempts."""
        from app.routers.v1.webhooks import WebhookDeliveryResponse

        for attempt_num in [1, 2, 3, 4, 5]:
            delivery = WebhookDeliveryResponse(
                id=uuid.uuid4(),
                webhook_endpoint_id=uuid.uuid4(),
                webhook_event_id=uuid.uuid4(),
                status_code=None,
                response_body=None,
                error="Failed",
                attempt=attempt_num,
                delivered_at=None,
                created_at=datetime.utcnow(),
            )
            assert delivery.attempt == attempt_num


class TestWebhookSecurityFeatures:
    """Test webhook security features."""

    def test_secret_in_endpoint_response(self):
        """Test secret is included in endpoint response."""
        from app.routers.v1.webhooks import WebhookEndpointResponse

        response = WebhookEndpointResponse(
            id=uuid.uuid4(),
            url="https://example.com/webhook",
            secret="whsec_supersecretkey123",
            events=["user.created"],
            is_active=True,
            description=None,
            headers=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        assert response.secret.startswith("whsec_")

    def test_custom_headers_supported(self):
        """Test custom headers are supported."""
        from app.routers.v1.webhooks import WebhookEndpointCreate
        from app.services.webhooks import WebhookEventType

        request = WebhookEndpointCreate(
            url="https://example.com/webhook",
            events=[WebhookEventType.USER_CREATED],
            headers={
                "Authorization": "Bearer token",
                "X-API-Key": "api-key",
            },
        )
        assert "Authorization" in request.headers
        assert "X-API-Key" in request.headers
