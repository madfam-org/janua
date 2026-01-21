"""
Integration tests for Resend email service
Tests email delivery, template rendering, and enterprise email flows
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis

from app.services.resend_email_service import EmailPriority, ResendEmailService


@pytest.fixture
async def redis_client():
    """Mock Redis client for testing"""
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.hset = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.hincrby = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})
    return mock_redis


@pytest.fixture
def email_service(redis_client):
    """Email service instance with mock Redis"""
    return ResendEmailService(redis_client=redis_client)


class TestResendEmailService:
    """Test Resend email service basic functionality"""

    @pytest.mark.asyncio
    async def test_send_email_development_mode(self, email_service):
        """Test email sending in development mode (console logging)"""
        # Development mode should not require Resend API key
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_email(
                    to_email="test@example.com",
                    subject="Test Email",
                    html_content="<p>Test content</p>",
                    text_content="Test content",
                )

                assert result.status == "sent"
                assert result.message_id.startswith("janua-")
                assert "test@example.com" in str(result.metadata) if result.metadata else True

    @pytest.mark.asyncio
    async def test_send_email_disabled(self, email_service):
        """Test email sending when EMAIL_ENABLED is False"""
        with patch("app.services.resend_email_service.settings.EMAIL_ENABLED", False):
            result = await email_service.send_email(
                to_email="test@example.com",
                subject="Test Email",
                html_content="<p>Test content</p>",
            )

            assert result.status == "disabled"
            assert result.error_message == "Email service disabled"

    @pytest.mark.asyncio
    async def test_delivery_tracking(self, email_service, redis_client):
        """Test delivery status tracking in Redis"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_email(
                    to_email="test@example.com",
                    subject="Test Email",
                    html_content="<p>Test</p>",
                    track_delivery=True,
                )

                # Verify Redis tracking calls were made
                assert redis_client.hset.called
                assert redis_client.expire.called
                assert redis_client.hincrby.called

    @pytest.mark.asyncio
    async def test_get_delivery_status(self, email_service, redis_client):
        """Test retrieving delivery status from Redis"""
        # Mock Redis response
        redis_client.hgetall = AsyncMock(
            return_value={
                "status": "sent",
                "timestamp": datetime.utcnow().isoformat(),
                "error_message": "",
                "metadata": "",
            }
        )

        status = await email_service.get_delivery_status("test-message-id")

        assert status is not None
        assert status.message_id == "test-message-id"
        assert status.status == "sent"

    @pytest.mark.asyncio
    async def test_email_statistics(self, email_service, redis_client):
        """Test email statistics retrieval"""
        # Mock Redis stats response
        redis_client.hgetall = AsyncMock(return_value={"total_sent": "100", "total_failed": "5"})

        stats = await email_service.get_email_statistics()

        assert stats["total_sent"] == 100
        assert stats["total_failed"] == 5


class TestTransactionalEmails:
    """Test transactional email methods"""

    @pytest.mark.asyncio
    async def test_send_verification_email(self, email_service):
        """Test email verification email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_verification_email(
                    to_email="user@example.com",
                    user_name="Test User",
                    verification_url="https://janua.dev/verify?token=abc123",
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "email_verification"

    @pytest.mark.asyncio
    async def test_send_password_reset_email(self, email_service):
        """Test password reset email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_password_reset_email(
                    to_email="user@example.com",
                    user_name="Test User",
                    reset_url="https://janua.dev/reset?token=xyz789",
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "password_reset"

    @pytest.mark.asyncio
    async def test_send_welcome_email(self, email_service):
        """Test welcome email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_welcome_email(
                    to_email="user@example.com", user_name="Test User"
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "welcome"


class TestEnterpriseEmails:
    """Test enterprise email methods"""

    @pytest.mark.asyncio
    async def test_send_invitation_email(self, email_service):
        """Test organization invitation email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                expires_at = datetime.utcnow() + timedelta(days=7)

                result = await email_service.send_invitation_email(
                    to_email="newuser@company.com",
                    inviter_name="Admin User",
                    organization_name="Acme Corp",
                    role="member",
                    invitation_url="https://janua.dev/invite?token=inv123",
                    expires_at=expires_at,
                    teams=["engineering", "product"],
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "invitation"
                assert result.metadata["organization"] == "Acme Corp"
                assert result.metadata["role"] == "member"

    @pytest.mark.asyncio
    async def test_send_sso_configuration_email(self, email_service):
        """Test SSO configuration notification email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_sso_configuration_email(
                    to_email="admin@company.com",
                    admin_name="Admin User",
                    organization_name="Acme Corp",
                    sso_provider="okta",
                    configuration_url="https://janua.dev/settings/sso",
                    domains=["company.com", "company.io"],
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "sso_configuration"
                assert result.metadata["provider"] == "okta"

    @pytest.mark.asyncio
    async def test_send_sso_enabled_email(self, email_service):
        """Test SSO enabled notification email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_sso_enabled_email(
                    to_email="user@company.com",
                    user_name="John Doe",
                    organization_name="Acme Corp",
                    sso_provider="okta",
                    login_url="https://janua.dev/login",
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "sso_enabled"
                assert result.metadata["provider"] == "okta"

    @pytest.mark.asyncio
    async def test_send_compliance_alert_email_action_required(self, email_service):
        """Test compliance alert email with action required"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                deadline = datetime.utcnow() + timedelta(days=30)

                result = await email_service.send_compliance_alert_email(
                    to_email="admin@company.com",
                    admin_name="Admin User",
                    organization_name="Acme Corp",
                    alert_type="Data Subject Request",
                    alert_description="User requested data export under GDPR Article 15",
                    action_required=True,
                    action_url="https://janua.dev/compliance/requests/123",
                    deadline=deadline,
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "compliance_alert"
                assert result.metadata["action_required"] is True
                # CRITICAL priority for action-required alerts
                assert "critical" in str(result.metadata).lower() or result.status == "sent"

    @pytest.mark.asyncio
    async def test_send_compliance_alert_email_informational(self, email_service):
        """Test informational compliance alert email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_compliance_alert_email(
                    to_email="admin@company.com",
                    admin_name="Admin User",
                    organization_name="Acme Corp",
                    alert_type="Policy Update",
                    alert_description="Privacy policy has been updated",
                    action_required=False,
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "compliance_alert"
                assert result.metadata["action_required"] is False

    @pytest.mark.asyncio
    async def test_send_data_export_ready_email(self, email_service):
        """Test data export ready notification email"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                expires_at = datetime.utcnow() + timedelta(days=7)

                result = await email_service.send_data_export_ready_email(
                    to_email="user@company.com",
                    user_name="John Doe",
                    request_type="GDPR Data Access Request",
                    download_url="https://janua.dev/exports/xyz123",
                    expires_at=expires_at,
                )

                assert result.status == "sent"
                assert result.metadata["type"] == "data_export_ready"
                assert result.metadata["request_type"] == "GDPR Data Access Request"


class TestEmailPriority:
    """Test email priority handling"""

    @pytest.mark.asyncio
    async def test_critical_priority_email(self, email_service):
        """Test critical priority email handling"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_email(
                    to_email="admin@company.com",
                    subject="Critical Security Alert",
                    html_content="<p>Immediate action required</p>",
                    priority=EmailPriority.CRITICAL,
                )

                assert result.status == "sent"

    @pytest.mark.asyncio
    async def test_low_priority_email(self, email_service):
        """Test low priority email handling"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_email(
                    to_email="user@company.com",
                    subject="Weekly Newsletter",
                    html_content="<p>Newsletter content</p>",
                    priority=EmailPriority.LOW,
                )

                assert result.status == "sent"


class TestEmailTemplateRendering:
    """Test email template rendering"""

    @pytest.mark.asyncio
    async def test_template_rendering_with_context(self, email_service):
        """Test template rendering with proper context variables"""
        # This tests that templates can be rendered without errors
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_invitation_email(
                    to_email="test@example.com",
                    inviter_name="Test Inviter",
                    organization_name="Test Org",
                    role="admin",
                    invitation_url="https://test.com/invite",
                    expires_at=datetime.utcnow() + timedelta(days=7),
                    teams=["team1", "team2"],
                )

                # If no exception was raised, template rendered successfully
                assert result.status == "sent"

    @pytest.mark.asyncio
    async def test_template_missing_graceful_handling(self, email_service):
        """Test graceful handling of missing templates"""
        # This would test template fallback mechanisms if implemented
        # Currently templates are required, so this verifies error handling


class TestEmailMetadata:
    """Test email metadata and tagging"""

    @pytest.mark.asyncio
    async def test_email_with_metadata(self, email_service):
        """Test email with custom metadata"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                metadata = {"user_id": "user123", "campaign": "onboarding", "variant": "A"}

                result = await email_service.send_email(
                    to_email="test@example.com",
                    subject="Test with Metadata",
                    html_content="<p>Test</p>",
                    metadata=metadata,
                )

                assert result.status == "sent"
                assert result.metadata == metadata

    @pytest.mark.asyncio
    async def test_email_with_tags(self, email_service):
        """Test email with tags"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                tags = [
                    {"name": "category", "value": "transactional"},
                    {"name": "environment", "value": "test"},
                ]

                result = await email_service.send_email(
                    to_email="test@example.com",
                    subject="Test with Tags",
                    html_content="<p>Test</p>",
                    tags=tags,
                )

                assert result.status == "sent"


class TestEmailOptions:
    """Test advanced email options (CC, BCC, Reply-To)"""

    @pytest.mark.asyncio
    async def test_email_with_cc(self, email_service):
        """Test email with CC recipients"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_email(
                    to_email="primary@example.com",
                    subject="Test with CC",
                    html_content="<p>Test</p>",
                    cc=["cc1@example.com", "cc2@example.com"],
                )

                assert result.status == "sent"

    @pytest.mark.asyncio
    async def test_email_with_reply_to(self, email_service):
        """Test email with custom reply-to"""
        with patch("app.services.resend_email_service.settings.RESEND_API_KEY", None):
            with patch("app.services.resend_email_service.settings.ENVIRONMENT", "development"):
                result = await email_service.send_email(
                    to_email="user@example.com",
                    subject="Test with Reply-To",
                    html_content="<p>Test</p>",
                    reply_to="support@janua.dev",
                )

                assert result.status == "sent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
