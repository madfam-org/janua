"""
Tests for email module exports and email/__init__.py

This tests the email module's public API and initialization.
Tests what's actually accessible via the email package.
"""

import logging
from unittest.mock import patch

import pytest

from app.services.email import EmailService, get_resend_service
from app.services.email_service import _redact_email

pytestmark = pytest.mark.asyncio


class TestEmailModuleExports:
    """Test email module exports and initialization."""

    def test_email_service_exported(self):
        """Test EmailService is exported from email module."""
        assert EmailService is not None

    def test_get_resend_service_function_exists(self):
        """Test get_resend_service function is exported."""
        assert callable(get_resend_service)

    def test_get_resend_service_returns_class(self):
        """Test get_resend_service returns ResendService class."""
        resend_cls = get_resend_service()
        assert resend_cls is not None
        assert hasattr(resend_cls, "__name__")
        assert resend_cls.__name__ == "ResendService"



class TestRedactEmail:
    """Test email redaction helper function."""

    def test_redact_normal_email(self):
        """Test redacting a normal email address."""
        result = _redact_email("testuser@example.com")
        assert result == "te***@example.com"

    def test_redact_short_local_part_two_chars(self):
        """Test redacting email with 2 character local part."""
        result = _redact_email("ab@example.com")
        assert result == "a***@example.com"

    def test_redact_short_local_part_one_char(self):
        """Test redacting email with 1 character local part."""
        result = _redact_email("a@example.com")
        assert result == "a***@example.com"

    def test_redact_empty_email(self):
        """Test redacting empty email returns [redacted]."""
        result = _redact_email("")
        assert result == "[redacted]"

    def test_redact_none_email(self):
        """Test redacting None email returns [redacted]."""
        result = _redact_email(None)
        assert result == "[redacted]"

    def test_redact_email_without_at(self):
        """Test redacting invalid email without @ symbol."""
        result = _redact_email("invalid_email")
        assert result == "[redacted]"

    def test_redact_preserves_full_domain(self):
        """Test redaction preserves complete domain."""
        result = _redact_email("user@subdomain.example.com")
        assert result == "us***@subdomain.example.com"

    def test_redact_long_local_part(self):
        """Test redacting email with long local part."""
        result = _redact_email("verylongemail@domain.com")
        assert result == "ve***@domain.com"

    def test_redact_special_chars_in_local(self):
        """Test redacting email with special chars in local part."""
        result = _redact_email("test.user+tag@example.com")
        assert result == "te***@example.com"


class TestEmailServiceInstanceMethods:
    """Test EmailService instance methods."""

    @pytest.fixture
    def service(self):
        """Create EmailService instance."""
        return EmailService()

    def test_email_service_instantiation(self):
        """Test EmailService can be instantiated."""
        service = EmailService()
        assert service is not None

    def test_email_service_has_redis_client_attribute(self):
        """Test EmailService has redis_client attribute."""
        service = EmailService()
        assert hasattr(service, "redis_client")

    def test_email_service_has_template_dir(self):
        """Test EmailService has template_dir attribute."""
        service = EmailService()
        assert hasattr(service, "template_dir")

    def test_email_service_has_jinja_env(self):
        """Test EmailService has jinja_env attribute."""
        service = EmailService()
        assert hasattr(service, "jinja_env")
