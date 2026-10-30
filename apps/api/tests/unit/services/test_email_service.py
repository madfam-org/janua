"""
Comprehensive Email Service Test Suite
Tests for sending verification, password reset, and notification emails
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import (
    EmailService,
    _redact_email,
    get_email_service,
)

pytestmark = pytest.mark.asyncio


class TestRedactEmail:
    """Test email redaction helper function."""

    def test_redact_normal_email(self):
        """Test redacting a normal email address."""
        result = _redact_email("testuser@example.com")
        assert result == "te***@example.com"

    def test_redact_short_local_part(self):
        """Test redacting email with short local part."""
        result = _redact_email("ab@example.com")
        assert result == "a***@example.com"

    def test_redact_single_char_local(self):
        """Test redacting email with single character local part."""
        result = _redact_email("a@example.com")
        assert result == "a***@example.com"

    def test_redact_empty_email(self):
        """Test redacting empty email."""
        result = _redact_email("")
        assert result == "[redacted]"

    def test_redact_none_email(self):
        """Test redacting None email."""
        result = _redact_email(None)
        assert result == "[redacted]"

    def test_redact_invalid_email(self):
        """Test redacting email without @."""
        result = _redact_email("invalid_email")
        assert result == "[redacted]"

    def test_redact_preserves_domain(self):
        """Test redaction preserves the full domain."""
        result = _redact_email("user@subdomain.example.com")
        assert result.endswith("@subdomain.example.com")


class TestEmailServiceInitialization:
    """Test EmailService initialization."""

    def test_initialization_without_redis(self):
        """Test service initialization without Redis."""
        service = EmailService()

        assert service.redis_client is None
        assert service.jinja_env is not None

    def test_initialization_with_redis(self):
        """Test service initialization with Redis client."""
        mock_redis = AsyncMock()
        service = EmailService(redis_client=mock_redis)

        assert service.redis_client is mock_redis

    def test_initialization_sets_template_dir(self):
        """Test service sets template directory."""
        service = EmailService()

        assert service.template_dir is not None
        assert "templates" in str(service.template_dir)


class TestGenerateVerificationToken:
    """Test verification token generation."""

    def test_token_is_string(self):
        """Test generated token is a string."""
        service = EmailService()
        token = service._generate_verification_token()

        assert isinstance(token, str)

    def test_token_has_correct_length(self):
        """Test generated token has correct length (64 chars)."""
        service = EmailService()
        token = service._generate_verification_token()

        assert len(token) == 64

    def test_token_is_hexadecimal(self):
        """Test generated token is hexadecimal."""
        service = EmailService()
        token = service._generate_verification_token()

        # Should only contain hex characters
        assert all(c in "0123456789abcdef" for c in token)

    def test_tokens_are_unique(self):
        """Test consecutive tokens are unique."""
        service = EmailService()

        token1 = service._generate_verification_token()
        token2 = service._generate_verification_token()

        assert token1 != token2


class TestRenderTemplate:
    """Test template rendering."""

    @pytest.fixture
    def service(self):
        """Create EmailService instance."""
        return EmailService()

    def test_render_verification_fallback(self, service):
        """Test verification template fallback."""
        data = {"verification_url": "https://example.com/verify?token=abc123"}

        # Force fallback by using non-existent template
        with patch.object(service.jinja_env, "get_template", side_effect=Exception("Template not found")):
            result = service._render_template("verification.html", data)

        assert "https://example.com/verify?token=abc123" in result

    def test_render_password_reset_fallback(self, service):
        """Test password reset template fallback."""
        data = {"reset_url": "https://example.com/reset?token=xyz789"}

        with patch.object(service.jinja_env, "get_template", side_effect=Exception("Template not found")):
            result = service._render_template("password_reset.html", data)

        assert "https://example.com/reset?token=xyz789" in result

    def test_render_welcome_fallback(self, service):
        """Test welcome template fallback."""
        data = {"user_name": "TestUser"}

        with patch.object(service.jinja_env, "get_template", side_effect=Exception("Template not found")):
            result = service._render_template("welcome.html", data)

        assert "TestUser" in result

    def test_render_unknown_template_fallback(self, service):
        """Test unknown template fallback.

        The degraded path is localized too: a recipient who hits it is no more
        likely to read English than one who does not.
        """
        data = {}

        with patch.object(service.jinja_env, "get_template", side_effect=Exception("Template not found")):
            assert service._render_template("unknown.html", data, "en") == "Email content unavailable"
            assert service._render_template("unknown.html", data, "es") == "Contenido no disponible"


class TestSendEmail:
    """Test internal send email method."""

    @pytest.fixture
    def service(self):
        """Create EmailService instance."""
        return EmailService()

    async def test_send_email_without_transport_reports_failure(self, service):
        """With no transport configured, the send must report failure.

        This asserted `is True` ("alpha mode") until 2026-08-13, which made an
        email that physically could not be delivered indistinguishable from a
        delivered one — every caller logged success and every UI said "check
        your inbox". Reporting False is what lets callers tell the truth.
        """
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.EMAIL_PROVIDER = "smtp"
            mock_settings.RESEND_API_KEY = None

            result = await service._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<p>Test HTML</p>",
                text_content="Test Text",
            )

        assert result is False

    async def test_send_email_with_smtp_success(self, service):
        """Test sending email with SMTP configuration."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_TLS = True
            mock_settings.SMTP_USERNAME = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.FROM_NAME = "Janua"
            mock_settings.FROM_EMAIL = "noreply@janua.dev"

            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__.return_value = mock_server

                result = await service._send_email(
                    to_email="test@example.com",
                    subject="Test Subject",
                    html_content="<p>Test HTML</p>",
                    text_content="Test Text",
                )

        assert result is True

    async def test_send_email_failure(self, service):
        """Test handling email send failure."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_TLS = False
            mock_settings.SMTP_USERNAME = None
            mock_settings.SMTP_PASSWORD = None
            mock_settings.FROM_NAME = "Janua"
            mock_settings.FROM_EMAIL = "noreply@janua.dev"

            with patch("smtplib.SMTP", side_effect=Exception("SMTP connection failed")):
                result = await service._send_email(
                    to_email="test@example.com",
                    subject="Test Subject",
                    html_content="<p>Test HTML</p>",
                )

        assert result is False


class TestSendVerificationEmail:
    """Test send verification email functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        """Create EmailService instance with mock Redis."""
        return EmailService(redis_client=mock_redis)

    async def test_send_verification_returns_token(self, service):
        """Test verification email returns token."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template", return_value="content"):
                token = await service.send_verification_email(
                    email="test@example.com",
                    user_name="Test User",
                    user_id="user-123",
                )

        assert isinstance(token, str)
        assert len(token) == 64

    async def test_send_verification_stores_token_in_redis(self, service, mock_redis):
        """Test verification email stores token in Redis."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template", return_value="content"):
                await service.send_verification_email(
                    email="test@example.com",
                    user_name="Test User",
                    user_id="user-123",
                )

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 24 * 60 * 60  # 24 hours

    async def test_send_verification_raises_on_failure(self, service):
        """Test verification email raises on send failure."""
        with patch.object(service, "_send_email", return_value=False):
            with patch.object(service, "_render_template", return_value="content"):
                with pytest.raises(Exception) as exc_info:
                    await service.send_verification_email(email="test@example.com")

        assert "Failed to send verification email" in str(exc_info.value)

    async def test_send_verification_url_points_to_dashboard_app(self, service):
        """Verification link must target FRONTEND_URL (app.janua.dev, which
        serves /auth/verify-email) — not BASE_URL (janua.dev, the marketing
        site with no such route, which 404s)."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "https://app.janua.dev"
            mock_settings.BASE_URL = "https://janua.dev"
            mock_settings.SUPPORT_EMAIL = None

            with patch.object(service, "_send_email", return_value=True):
                with patch.object(
                    service, "_render_template", return_value="content"
                ) as mock_render:
                    token = await service.send_verification_email(email="test@example.com")

        rendered_data = mock_render.call_args_list[0].args[1]
        assert rendered_data["verification_url"] == (
            f"https://app.janua.dev/auth/verify-email?token={token}"
        )


class TestVerifyEmailToken:
    """Test email token verification."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock()
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        """Create EmailService instance with mock Redis."""
        return EmailService(redis_client=mock_redis)

    async def test_verify_token_success(self, service, mock_redis):
        """Test successful token verification."""
        token_data = str({
            "email": "test@example.com",
            "user_id": "user-123",
            "created_at": datetime.utcnow().isoformat(),
            "type": "email_verification",
        })
        mock_redis.get.return_value = token_data.encode()

        result = await service.verify_email_token("valid-token")

        assert result["email"] == "test@example.com"
        mock_redis.delete.assert_called_once()

    async def test_verify_token_not_found(self, service, mock_redis):
        """Test token verification with invalid token."""
        mock_redis.get.return_value = None

        with pytest.raises(Exception) as exc_info:
            await service.verify_email_token("invalid-token")

        assert "Invalid or expired verification token" in str(exc_info.value)

    async def test_verify_token_no_redis(self):
        """Test token verification without Redis."""
        service = EmailService()  # No Redis client

        with pytest.raises(Exception) as exc_info:
            await service.verify_email_token("any-token")

        assert "Redis not available" in str(exc_info.value)


class TestSendPasswordResetEmail:
    """Test send password reset email functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        """Create EmailService instance with mock Redis."""
        return EmailService(redis_client=mock_redis)

    async def test_send_reset_returns_token(self, service):
        """The service emails and returns the CALLER's stored token — it must
        never mint its own (the emailed link has to match password_resets)."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template", return_value="content"):
                token = await service.send_password_reset_email(
                    email="test@example.com",
                    reset_token="caller-token-abc",
                    user_name="Test User",
                )

        assert token == "caller-token-abc"

    async def test_send_reset_stores_token_in_redis(self, service, mock_redis):
        """Test password reset mirrors the caller's token with 1-hour expiry."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template", return_value="content"):
                await service.send_password_reset_email(
                    email="test@example.com", reset_token="caller-token-abc"
                )

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "password_reset:caller-token-abc"
        assert call_args[0][1] == 60 * 60  # 1 hour

    async def test_send_reset_raises_on_failure(self, service):
        """Test password reset raises on send failure."""
        with patch.object(service, "_send_email", return_value=False):
            with patch.object(service, "_render_template", return_value="content"):
                with pytest.raises(Exception) as exc_info:
                    await service.send_password_reset_email(
                        email="test@example.com", reset_token="caller-token-abc"
                    )

        assert "Failed to send password reset email" in str(exc_info.value)


class TestPasswordResetLinkLanguage:
    """The default reset link opens the hosted page in the email's language
    (2026-10-27): a Spanish email must not land on an English page."""

    @pytest.fixture
    def service(self):
        return EmailService(redis_client=AsyncMock())

    async def _reset_url(self, service, **kwargs):
        from app.config import settings

        with (
            patch.object(service, "_send_email", return_value=True),
            patch.object(service, "_render_template", return_value="content") as render,
            patch.object(settings, "BASE_URL", "https://auth.example.test"),
        ):
            await service.send_password_reset_email(
                email="test@example.com", reset_token="tok-abc", **kwargs
            )
        data = render.call_args_list[0][0][1]
        assert data["reset_link"] == data["reset_url"]
        return data["reset_url"]

    async def test_spanish_email_links_to_the_spanish_page(self, service):
        url = await self._reset_url(service, locale="es-MX")
        assert url == (
            "https://auth.example.test/api/v1/auth/reset-password?token=tok-abc&ui_locales=es"
        )

    async def test_english_email_links_to_the_unchanged_english_url(self, service):
        url = await self._reset_url(service, locale="en")
        assert url == "https://auth.example.test/api/v1/auth/reset-password?token=tok-abc"

    async def test_stored_user_locale_decides_when_the_caller_names_none(self, service):
        from types import SimpleNamespace

        english_user = SimpleNamespace(locale="en-US")
        url = await self._reset_url(service, user=english_user)
        assert "ui_locales" not in url

    async def test_the_deployment_default_language_decides_last(self, service):
        from app.config import settings

        with patch.object(settings, "DEFAULT_EMAIL_LOCALE", "es"):
            assert (await self._reset_url(service)).endswith("&ui_locales=es")
        with patch.object(settings, "DEFAULT_EMAIL_LOCALE", "en"):
            assert "ui_locales" not in await self._reset_url(service)

    async def test_a_product_redirect_base_is_left_untouched(self, service):
        for locale in ("es", "en"):
            url = await self._reset_url(
                service, locale=locale, redirect_base="https://app.example.test/reset"
            )
            assert url == "https://app.example.test/reset?token=tok-abc"


class TestSendWelcomeEmail:
    """Test send welcome email functionality."""

    @pytest.fixture
    def service(self):
        """Create EmailService instance."""
        return EmailService()

    async def test_send_welcome_success(self, service):
        """Test successful welcome email send."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template", return_value="content"):
                result = await service.send_welcome_email(
                    email="test@example.com",
                    user_name="Test User",
                )

        assert result is True

    async def test_send_welcome_failure(self, service):
        """Test welcome email send failure."""
        with patch.object(service, "_send_email", return_value=False):
            with patch.object(service, "_render_template", return_value="content"):
                result = await service.send_welcome_email(email="test@example.com")

        assert result is False

    async def test_send_welcome_uses_email_local_part_as_name(self, service):
        """Test welcome email uses email local part when no name provided."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template", return_value="content") as mock_render:
                await service.send_welcome_email(email="john@example.com")

        # Check that user_name was derived from email
        render_calls = mock_render.call_args_list
        assert any("john" in str(call) for call in render_calls)


class TestGetEmailService:
    """Test get_email_service factory function."""

    def test_get_service_without_redis(self):
        """Test getting service without Redis."""
        service = get_email_service()

        assert isinstance(service, EmailService)
        assert service.redis_client is None

    def test_get_service_with_redis(self):
        """Test getting service with Redis client."""
        mock_redis = AsyncMock()
        service = get_email_service(redis_client=mock_redis)

        assert isinstance(service, EmailService)
        assert service.redis_client is mock_redis


class TestServiceMethodExistence:
    """Test that required service methods exist."""

    @pytest.fixture
    def service(self):
        """Create EmailService instance."""
        return EmailService()

    def test_has_send_verification_email(self, service):
        """Test service has send_verification_email method."""
        assert hasattr(service, "send_verification_email")
        import asyncio
        assert asyncio.iscoroutinefunction(service.send_verification_email)

    def test_has_verify_email_token(self, service):
        """Test service has verify_email_token method."""
        assert hasattr(service, "verify_email_token")
        import asyncio
        assert asyncio.iscoroutinefunction(service.verify_email_token)

    def test_has_send_password_reset_email(self, service):
        """Test service has send_password_reset_email method."""
        assert hasattr(service, "send_password_reset_email")
        import asyncio
        assert asyncio.iscoroutinefunction(service.send_password_reset_email)

    def test_has_send_welcome_email(self, service):
        """Test service has send_welcome_email method."""
        assert hasattr(service, "send_welcome_email")
        import asyncio
        assert asyncio.iscoroutinefunction(service.send_welcome_email)

    def test_has_generate_verification_token(self, service):
        """Test service has _generate_verification_token method."""
        assert hasattr(service, "_generate_verification_token")

    def test_has_render_template(self, service):
        """Test service has _render_template method."""
        assert hasattr(service, "_render_template")

    def test_has_send_email(self, service):
        """Test service has _send_email method."""
        assert hasattr(service, "_send_email")
        import asyncio
        assert asyncio.iscoroutinefunction(service._send_email)


class TestEmailTemplateData:
    """Test email template data preparation."""

    @pytest.fixture
    def service(self):
        """Create EmailService instance with mock Redis."""
        return EmailService(redis_client=AsyncMock())

    async def test_verification_email_includes_required_data(self, service):
        """Test verification email template data includes required fields."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template") as mock_render:
                mock_render.return_value = "content"
                await service.send_verification_email(
                    email="test@example.com",
                    user_name="Test User",
                )

        # Check _render_template was called with appropriate data
        assert mock_render.called

    async def test_password_reset_email_includes_required_data(self, service):
        """Test password reset email template data includes required fields."""
        with patch.object(service, "_send_email", return_value=True):
            with patch.object(service, "_render_template") as mock_render:
                mock_render.return_value = "content"
                await service.send_password_reset_email(
                    email="test@example.com", reset_token="caller-token-abc"
                )

        assert mock_render.called
        template_data = mock_render.call_args[0][1]
        assert "caller-token-abc" in template_data["reset_url"]
