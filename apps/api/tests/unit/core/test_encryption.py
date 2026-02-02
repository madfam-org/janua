"""
Tests for field-level encryption module (SOC 2 CF-01, CF-11)
"""

from unittest.mock import patch, MagicMock

import pytest


class TestFieldEncryptor:
    """Test FieldEncryptor class."""

    def _make_encryptor(self, key=None, environment="test"):
        """Create a FieldEncryptor with mocked settings."""
        from cryptography.fernet import Fernet

        if key is None:
            key = Fernet.generate_key().decode()

        mock_settings = MagicMock()
        mock_settings.FIELD_ENCRYPTION_KEY = key
        mock_settings.ENVIRONMENT = environment

        with patch("app.core.encryption.settings", mock_settings):
            from app.core.encryption import FieldEncryptor

            # Reset singleton for test isolation
            FieldEncryptor._instance = None
            enc = FieldEncryptor()
            FieldEncryptor._instance = None
            return enc

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt then decrypt returns original plaintext."""
        enc = self._make_encryptor()
        plaintext = "my-secret-totp-key-12345"
        ciphertext = enc.encrypt_field(plaintext)
        assert ciphertext != plaintext
        assert enc.decrypt_field(ciphertext) == plaintext

    def test_encrypt_returns_different_output(self):
        """Test that ciphertext differs from plaintext."""
        enc = self._make_encryptor()
        plaintext = "secret"
        ciphertext = enc.encrypt_field(plaintext)
        assert ciphertext != plaintext

    def test_decrypt_handles_legacy_plaintext(self):
        """Test that decrypt gracefully returns unencrypted legacy data."""
        enc = self._make_encryptor()
        legacy = "plain-text-mfa-secret"
        assert enc.decrypt_field(legacy) == legacy

    def test_no_key_returns_plaintext(self):
        """Test that without encryption key, encrypt returns plaintext."""
        mock_settings = MagicMock()
        mock_settings.FIELD_ENCRYPTION_KEY = None
        mock_settings.ENVIRONMENT = "test"

        with patch("app.core.encryption.settings", mock_settings):
            from app.core.encryption import FieldEncryptor

            FieldEncryptor._instance = None
            enc = FieldEncryptor()
            FieldEncryptor._instance = None

        assert enc.encrypt_field("hello") == "hello"
        assert enc.decrypt_field("hello") == "hello"

    def test_production_requires_key(self):
        """Test that production environment raises without encryption key."""
        mock_settings = MagicMock()
        mock_settings.FIELD_ENCRYPTION_KEY = None
        mock_settings.ENVIRONMENT = "production"

        with patch("app.core.encryption.settings", mock_settings):
            from app.core.encryption import FieldEncryptor

            FieldEncryptor._instance = None
            with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEY must be set"):
                FieldEncryptor()
            FieldEncryptor._instance = None

    def test_singleton_pattern(self):
        """Test get_instance returns singleton."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        mock_settings = MagicMock()
        mock_settings.FIELD_ENCRYPTION_KEY = key
        mock_settings.ENVIRONMENT = "test"

        with patch("app.core.encryption.settings", mock_settings):
            from app.core.encryption import FieldEncryptor

            FieldEncryptor._instance = None
            a = FieldEncryptor.get_instance()
            b = FieldEncryptor.get_instance()
            assert a is b
            FieldEncryptor._instance = None

    def test_encrypt_unicode(self):
        """Test encryption handles unicode strings."""
        enc = self._make_encryptor()
        plaintext = "contraseña-秘密-пароль"
        assert enc.decrypt_field(enc.encrypt_field(plaintext)) == plaintext

    def test_encrypt_empty_string(self):
        """Test encryption handles empty string."""
        enc = self._make_encryptor()
        assert enc.decrypt_field(enc.encrypt_field("")) == ""


class TestEncryptedStringType:
    """Test EncryptedString SQLAlchemy TypeDecorator."""

    def test_process_bind_param_none(self):
        """Test None values pass through."""
        from app.models.types import EncryptedString

        t = EncryptedString()
        assert t.process_bind_param(None, MagicMock()) is None

    def test_process_result_value_none(self):
        """Test None values pass through on read."""
        from app.models.types import EncryptedString

        t = EncryptedString()
        assert t.process_result_value(None, MagicMock()) is None

    def test_process_bind_param_fallback(self):
        """Test that bind param falls back to str on encryption failure."""
        from app.models.types import EncryptedString

        t = EncryptedString()
        with patch("app.core.encryption.FieldEncryptor.get_instance", side_effect=Exception("no key")):
            result = t.process_bind_param("test-value", MagicMock())
            assert result == "test-value"

    def test_process_result_value_fallback(self):
        """Test that result value falls back on decryption failure."""
        from app.models.types import EncryptedString

        t = EncryptedString()
        with patch("app.core.encryption.FieldEncryptor.get_instance", side_effect=Exception("no key")):
            result = t.process_result_value("some-cipher", MagicMock())
            assert result == "some-cipher"

    def test_impl_is_text(self):
        """Test that impl type is Text."""
        from sqlalchemy import Text

        from app.models.types import EncryptedString

        assert EncryptedString.impl is Text

    def test_cache_ok(self):
        """Test cache_ok is True."""
        from app.models.types import EncryptedString

        assert EncryptedString.cache_ok is True
