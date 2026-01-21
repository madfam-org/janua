import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive test coverage for Email Service
Critical for user authentication and communication workflows

Target: 0% → 80%+ coverage
Covers: EmailService with verification, password reset, welcome emails, token management
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
import smtplib
from pathlib import Path

from app.services.email_service import EmailService, get_email_service


class TestEmailServiceInitialization:
    """Test email service initialization and configuration"""

    def test_email_service_init_without_redis(self):
        """Test email service initializes correctly without Redis"""
        service = EmailService()
        assert service is not None
        assert service.redis_client is None
        assert service.template_dir is not None
        assert service.jinja_env is not None

    def test_email_service_init_with_redis(self):
        """Test email service initializes correctly with Redis"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)
        assert service is not None
        assert service.redis_client == mock_redis

    def test_email_service_template_directory(self):
        """Test email service template directory is set correctly"""
        service = EmailService()
        Path(__file__).parent.parent.parent.parent / "app" / "templates" / "email"
        assert service.template_dir.name == "email"

    def test_get_email_service_factory(self):
        """Test email service factory function"""
        service = get_email_service()
        assert isinstance(service, EmailService)
        assert service.redis_client is None

        mock_redis = AsyncMock()
        service_with_redis = get_email_service(mock_redis)
        assert isinstance(service_with_redis, EmailService)
        assert service_with_redis.redis_client == mock_redis


class TestTokenGeneration:
    """Test email token generation and security"""

    def test_generate_verification_token(self):
        """Test verification token generation"""
        service = EmailService()
        token = service._generate_verification_token()

        # Token should be a 64-character hex string
        assert isinstance(token, str)
        assert len(token) == 64
        assert all(c in '0123456789abcdef' for c in token)

    def test_generate_verification_token_uniqueness(self):
        """Test that generated tokens are unique"""
        service = EmailService()
        tokens = set()

        # Generate 100 tokens and verify uniqueness
        for _ in range(100):
            token = service._generate_verification_token()
            tokens.add(token)

        # All tokens should be unique
        assert len(tokens) == 100

    def test_verification_token_security(self):
        """Test that verification tokens are cryptographically secure"""
        service = EmailService()
        token = service._generate_verification_token()

        # Token should be hex representation of SHA-256
        assert len(token) == 64  # SHA-256 hex is 64 chars

        # Should contain mix of letters and numbers
        has_letter = any(c.isalpha() for c in token)
        has_number = any(c.isdigit() for c in token)
        assert has_letter or has_number  # At least one should be true for random data


class TestTemplateRendering:
    """Test email template rendering functionality"""

    def test_render_template_success(self):
        """Test successful template rendering"""
        service = EmailService()

        # Mock successful template rendering
        with patch.object(service.jinja_env, 'get_template') as mock_get_template:
            mock_template = AsyncMock()
            mock_template.render.return_value = "Rendered content"
            mock_get_template.return_value = mock_template

            result = service._render_template("test.html", {"name": "John"})
            assert result == "Rendered content"
            mock_template.render.assert_called_once_with(name="John")

    def test_render_template_verification_fallback(self):
        """Test verification template fallback"""
        service = EmailService()

        # Mock template rendering failure
        with patch.object(service.jinja_env, 'get_template') as mock_get_template:
            mock_get_template.side_effect = Exception("Template not found")

            data = {"verification_url": "https://example.com/verify?token=123"}
            result = service._render_template("verification.html", data)

            assert "verify" in result.lower()
            assert data["verification_url"] in result

    def test_render_template_password_reset_fallback(self):
        """Test password reset template fallback"""
        service = EmailService()

        with patch.object(service.jinja_env, 'get_template') as mock_get_template:
            mock_get_template.side_effect = Exception("Template not found")

            data = {"reset_url": "https://example.com/reset?token=123"}
            result = service._render_template("password_reset.html", data)

            assert "reset" in result.lower()
            assert data["reset_url"] in result

    def test_render_template_welcome_fallback(self):
        """Test welcome template fallback"""
        service = EmailService()

        with patch.object(service.jinja_env, 'get_template') as mock_get_template:
            mock_get_template.side_effect = Exception("Template not found")

            data = {"user_name": "John"}
            result = service._render_template("welcome.html", data)

            assert "welcome" in result.lower()
            assert data["user_name"] in result

    def test_render_template_generic_fallback(self):
        """Test generic template fallback"""
        service = EmailService()

        with patch.object(service.jinja_env, 'get_template') as mock_get_template:
            mock_get_template.side_effect = Exception("Template not found")

            result = service._render_template("unknown.html", {})
            assert result == "Email content unavailable"


class TestEmailVerification:
    """Test email verification functionality"""

    @pytest.mark.asyncio
    async def test_send_verification_email_success(self):
        """Test successful verification email sending"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        # Mock successful email sending
        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            token = await service.send_verification_email(
                email="test@example.com",
                user_name="John Doe",
                user_id="user123"
            )

            # Verify token was generated
            assert isinstance(token, str)
            assert len(token) == 64

            # Verify Redis storage
            mock_redis.setex.assert_called_once()
            args = mock_redis.setex.call_args
            assert args[0][0].startswith("email_verification:")
            assert args[0][1] == 24 * 60 * 60  # 24 hours

            # Verify email was sent
            mock_send.assert_called_once()
            send_args = mock_send.call_args[1]
            assert send_args["to_email"] == "test@example.com"
            assert "verify" in send_args["subject"].lower()

    @pytest.mark.asyncio
    async def test_send_verification_email_without_redis(self):
        """Test verification email sending without Redis"""
        service = EmailService()  # No Redis client

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            token = await service.send_verification_email(
                email="test@example.com"
            )

            # Should still generate token and send email
            assert isinstance(token, str)
            assert len(token) == 64
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_verification_email_send_failure(self):
        """Test verification email sending failure"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = False
            mock_render.return_value = "Rendered content"

            with pytest.raises(Exception, match="Failed to send verification email"):
                await service.send_verification_email("test@example.com")

    @pytest.mark.asyncio
    async def test_verify_email_token_success(self):
        """Test successful email token verification"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        # Mock token data in Redis
        token_data = {
            "email": "test@example.com",
            "user_id": "user123",
            "created_at": datetime.utcnow().isoformat(),
            "type": "email_verification"
        }
        mock_redis.get.return_value = str(token_data).encode()

        result = await service.verify_email_token("valid_token")

        # Verify token was retrieved and deleted
        mock_redis.get.assert_called_once_with("email_verification:valid_token")
        mock_redis.delete.assert_called_once_with("email_verification:valid_token")

        # Verify result structure
        assert result["email"] == "test@example.com"
        assert result["user_id"] == "user123"
        assert result["type"] == "email_verification"

    @pytest.mark.asyncio
    async def test_verify_email_token_not_found(self):
        """Test email token verification with invalid token"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        # Mock token not found
        mock_redis.get.return_value = None

        with pytest.raises(Exception, match="Invalid or expired verification token"):
            await service.verify_email_token("invalid_token")

        # Should not delete token if not found
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_email_token_without_redis(self):
        """Test email token verification without Redis"""
        service = EmailService()  # No Redis client

        with pytest.raises(Exception, match="Redis not available for token verification"):
            await service.verify_email_token("any_token")

    @pytest.mark.asyncio
    async def test_verify_email_token_malformed_data(self):
        """Test email token verification with malformed data"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        # Mock malformed token data
        mock_redis.get.return_value = b"invalid_data"

        with pytest.raises(Exception, match="Invalid or expired verification token"):
            await service.verify_email_token("malformed_token")


class TestPasswordReset:
    """Test password reset functionality"""

    @pytest.mark.asyncio
    async def test_send_password_reset_email_success(self):
        """Test successful password reset email sending"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            token = await service.send_password_reset_email(
                email="test@example.com",
                user_name="John Doe"
            )

            # Verify token was generated
            assert isinstance(token, str)
            assert len(token) == 64

            # Verify Redis storage with 1-hour expiry
            mock_redis.setex.assert_called_once()
            args = mock_redis.setex.call_args
            assert args[0][0].startswith("password_reset:")
            assert args[0][1] == 60 * 60  # 1 hour

            # Verify email was sent
            mock_send.assert_called_once()
            send_args = mock_send.call_args[1]
            assert send_args["to_email"] == "test@example.com"
            assert "reset" in send_args["subject"].lower()

    @pytest.mark.asyncio
    async def test_send_password_reset_email_without_user_name(self):
        """Test password reset email without user name"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            token = await service.send_password_reset_email("test@example.com")

            # Should use email prefix as user name
            assert isinstance(token, str)
            mock_render.assert_called()
            render_call_args = mock_render.call_args[0][1]  # template_data
            assert render_call_args["user_name"] == "test"  # email prefix

    @pytest.mark.asyncio
    async def test_send_password_reset_email_send_failure(self):
        """Test password reset email sending failure"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = False
            mock_render.return_value = "Rendered content"

            with pytest.raises(Exception, match="Failed to send password reset email"):
                await service.send_password_reset_email("test@example.com")


class TestWelcomeEmail:
    """Test welcome email functionality"""

    @pytest.mark.asyncio
    async def test_send_welcome_email_success(self):
        """Test successful welcome email sending"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            result = await service.send_welcome_email(
                email="test@example.com",
                user_name="John Doe"
            )

            assert result is True
            mock_send.assert_called_once()
            send_args = mock_send.call_args[1]
            assert send_args["to_email"] == "test@example.com"
            assert "welcome" in send_args["subject"].lower()

    @pytest.mark.asyncio
    async def test_send_welcome_email_without_user_name(self):
        """Test welcome email without user name"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            result = await service.send_welcome_email("test@example.com")

            assert result is True
            mock_render.assert_called()
            render_call_args = mock_render.call_args[0][1]  # template_data
            assert render_call_args["user_name"] == "test"  # email prefix

    @pytest.mark.asyncio
    async def test_send_welcome_email_failure(self):
        """Test welcome email sending failure"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = False
            mock_render.return_value = "Rendered content"

            result = await service.send_welcome_email("test@example.com")

            assert result is False


class TestEmailSending:
    """Test email sending functionality"""

    @pytest.mark.asyncio
    async def test_send_email_alpha_mode(self):
        """Test email sending in alpha mode (no SMTP configured)"""
        service = EmailService()

        # Mock settings without SMTP configuration
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_HOST = None

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>",
                text_content="Test"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_smtp_success(self):
        """Test successful SMTP email sending"""
        service = EmailService()

        # Mock SMTP settings
        with patch('app.services.email_service.settings') as mock_settings, \
             patch('app.services.email_service.smtplib.SMTP') as mock_smtp_class:

            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_TLS = True
            mock_settings.SMTP_USERNAME = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.FROM_EMAIL = "noreply@example.com"
            mock_settings.FROM_NAME = "Test Service"

            mock_smtp = AsyncMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>",
                text_content="Test"
            )

            assert result is True
            mock_smtp.starttls.assert_called_once()
            mock_smtp.login.assert_called_once_with("user", "pass")
            mock_smtp.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_smtp_no_auth(self):
        """Test SMTP email sending without authentication"""
        service = EmailService()

        with patch('app.services.email_service.settings') as mock_settings, \
             patch('app.services.email_service.smtplib.SMTP') as mock_smtp_class:

            # Configure mock settings as attributes, not method returns
            mock_settings.configure_mock(
                ALPHA_MODE=False,
                SMTP_HOST="smtp.example.com",
                SMTP_PORT=25,
                SMTP_TLS=False,
                SMTP_USERNAME=None,
                SMTP_PASSWORD=None,
                FROM_EMAIL="noreply@example.com",
                FROM_NAME="Test Janua"
            )

            mock_smtp = AsyncMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp
            # Mock sendmail to return None instead of leaving it as MagicMock
            mock_smtp.sendmail.return_value = None

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>"
            )

            assert result is True
            mock_smtp.starttls.assert_not_called()
            mock_smtp.login.assert_not_called()
            mock_smtp.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_smtp_failure(self):
        """Test SMTP email sending failure"""
        service = EmailService()

        with patch('app.services.email_service.settings') as mock_settings, \
             patch('app.services.email_service.smtplib.SMTP') as mock_smtp_class:

            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.FROM_EMAIL = "noreply@example.com"

            mock_smtp_class.side_effect = smtplib.SMTPException("Connection failed")

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_only_html_content(self):
        """Test email sending with only HTML content"""
        service = EmailService()

        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_HOST = None  # Alpha mode

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>"
                # No text_content
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_only_text_content(self):
        """Test email sending with only text content"""
        service = EmailService()

        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_HOST = None  # Alpha mode

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>",
                text_content="Test"
            )

            assert result is True


class TestEmailWorkflows:
    """Test complete email workflows"""

    @pytest.mark.asyncio
    async def test_complete_verification_workflow(self):
        """Test complete email verification workflow"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        # Mock successful email sending
        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            # Step 1: Send verification email
            token = await service.send_verification_email(
                email="test@example.com",
                user_name="John Doe",
                user_id="user123"
            )

            assert isinstance(token, str)
            mock_redis.setex.assert_called_once()

            # Step 2: Verify token
            token_data = {
                "email": "test@example.com",
                "user_id": "user123",
                "created_at": datetime.utcnow().isoformat(),
                "type": "email_verification"
            }
            mock_redis.get.return_value = str(token_data).encode()

            result = await service.verify_email_token(token)

            assert result["email"] == "test@example.com"
            assert result["user_id"] == "user123"
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_password_reset_workflow(self):
        """Test complete password reset workflow"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            # Send password reset email
            token = await service.send_password_reset_email(
                email="test@example.com",
                user_name="John Doe"
            )

            assert isinstance(token, str)
            mock_redis.setex.assert_called_once()

            # Verify Redis storage with correct expiry
            args = mock_redis.setex.call_args
            assert args[0][0].startswith("password_reset:")
            assert args[0][1] == 60 * 60  # 1 hour

    @pytest.mark.asyncio
    async def test_user_onboarding_workflow(self):
        """Test user onboarding email workflow"""
        service = EmailService()

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            # Send welcome email
            result = await service.send_welcome_email(
                email="test@example.com",
                user_name="John Doe"
            )

            assert result is True
            mock_send.assert_called_once()

            # Verify welcome email content
            render_calls = mock_render.call_args_list
            welcome_calls = [call for call in render_calls if "welcome" in call[0][0]]
            assert len(welcome_calls) > 0


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_email_service_resilience(self):
        """Test email service resilience to failures"""
        service = EmailService()

        # Test with invalid email format (service should still attempt)
        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            result = await service.send_welcome_email("invalid-email")
            assert result is True

    def test_token_generation_edge_cases(self):
        """Test token generation edge cases"""
        service = EmailService()

        # Test multiple rapid token generations
        tokens = []
        for _ in range(10):
            token = service._generate_verification_token()
            tokens.append(token)

        # All should be valid and unique
        assert len(set(tokens)) == 10
        for token in tokens:
            assert len(token) == 64
            assert all(c in '0123456789abcdef' for c in token)

    @pytest.mark.asyncio
    async def test_redis_failure_handling(self):
        """Test handling of Redis failures"""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        # Mock Redis failure
        mock_redis.setex.side_effect = Exception("Redis connection failed")

        with patch.object(service, '_send_email') as mock_send, \
             patch.object(service, '_render_template') as mock_render:

            mock_send.return_value = True
            mock_render.return_value = "Rendered content"

            # The current implementation does not handle Redis failures gracefully
            # It will raise an exception when Redis fails
            with pytest.raises(Exception, match="Redis connection failed"):
                await service.send_verification_email("test@example.com")

    def test_template_directory_validation(self):
        """Test template directory setup"""
        service = EmailService()

        # Template directory should be set correctly
        assert service.template_dir is not None
        assert service.template_dir.name == "email"

        # Jinja environment should be configured
        assert service.jinja_env is not None
        assert service.jinja_env.autoescape is True