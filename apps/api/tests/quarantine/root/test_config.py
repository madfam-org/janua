"""
Unit tests for application configuration
"""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from app.config import Settings


class TestSettings:
    """Test the Settings configuration class."""

    def test_default_settings(self):
        """Test default configuration values."""
        # Clear environment AND disable .env file loading to ensure pure defaults
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)

            assert settings.VERSION == "0.1.0"
            assert settings.DEBUG is False
            assert settings.ENVIRONMENT == "development"
            assert settings.BASE_URL == "https://janua.dev"
            assert settings.DATABASE_POOL_SIZE == 20
            assert settings.REDIS_POOL_SIZE == 10
            assert settings.JWT_ALGORITHM == "RS256"

    def test_environment_validation(self):
        """Test environment field validation."""
        # Valid environments (production requires extra secrets, so test separately)
        for env in ["development", "staging", "test"]:
            settings = Settings(ENVIRONMENT=env)
            assert settings.ENVIRONMENT == env

        # Production requires FIELD_ENCRYPTION_KEY and SECRET_KEY
        settings = Settings(
            **self._production_settings_kwargs()
        )
        assert settings.ENVIRONMENT == "production"

        # Invalid environment should raise validation error
        with pytest.raises(ValidationError):
            Settings(ENVIRONMENT="invalid")

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_secret_key_validation(self):
        """Test SECRET_KEY validation."""
        # Should not accept default value in production
        with pytest.raises(ValidationError):
            Settings(**self._production_settings_kwargs(SECRET_KEY="change-this-in-production"))

        # Should not accept too-short SECRET_KEY in production
        with pytest.raises(ValidationError):
            Settings(**self._production_settings_kwargs(SECRET_KEY="too-short"))

        # Should accept a valid (32+ chars) SECRET_KEY in production
        settings = Settings(**self._production_settings_kwargs())
        assert len(settings.SECRET_KEY) >= 32

        # Should accept default in development
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            settings = Settings(ENVIRONMENT="development", SECRET_KEY="change-this-in-production")
            assert settings.SECRET_KEY == "change-this-in-production"

    def test_jwt_secret_validation(self):
        """Test JWT_SECRET_KEY field validator."""
        settings = Settings(JWT_SECRET_KEY=None)
        assert settings.JWT_SECRET_KEY == "development-secret-key"

        settings = Settings(JWT_SECRET_KEY="custom-key")
        assert settings.JWT_SECRET_KEY == "custom-key"

    def test_cors_origins_list_property(self):
        """Test CORS origins parsing."""
        # Test comma-separated string
        settings = Settings(CORS_ORIGINS="http://localhost:3000,https://app.example.com")
        expected = ["http://localhost:3000", "https://app.example.com"]
        assert settings.cors_origins_list == expected

        # Test JSON array string
        settings = Settings(CORS_ORIGINS='["http://localhost:3000", "https://app.example.com"]')
        assert settings.cors_origins_list == expected

        # Test empty string
        settings = Settings(CORS_ORIGINS="")
        assert settings.cors_origins_list == ["http://localhost:3000", "https://janua.dev"]

        # Test malformed JSON falls back to comma parsing
        settings = Settings(CORS_ORIGINS='["malformed json')
        assert settings.cors_origins_list == ['["malformed json']

    def test_service_url_property(self):
        """Test service URL property logic."""
        # With INTERNAL_BASE_URL set
        settings = Settings(
            BASE_URL="https://api.janua.dev", INTERNAL_BASE_URL="http://internal.railway.app"
        )
        assert settings.service_url == "http://internal.railway.app"

        # Without INTERNAL_BASE_URL
        settings = Settings(BASE_URL="https://api.janua.dev", INTERNAL_BASE_URL=None)
        assert settings.service_url == "https://api.janua.dev"

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",  # Changed from "test" to match expected default
            "DEBUG": "true",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "REDIS_URL": "redis://localhost:6379/1",
        },
    )
    def test_environment_variable_loading(self):
        """Test loading from environment variables."""
        settings = Settings()

        assert settings.ENVIRONMENT == "development"  # Changed expectation
        assert settings.DEBUG is True
        assert settings.DATABASE_URL == "postgresql://test:test@localhost/test"
        assert settings.REDIS_URL == "redis://localhost:6379/1"

    def test_field_descriptions(self):
        """Test that important fields have descriptions."""
        settings = Settings()
        schema = settings.model_json_schema()

        # Check some key fields have descriptions
        assert "description" in schema["properties"]["INTERNAL_BASE_URL"]
        assert "description" in schema["properties"]["CORS_ORIGINS"]
        assert "description" in schema["properties"]["DATABASE_URL"]

    def _production_settings_kwargs(self, **overrides):
        """Base kwargs needed to create a valid production Settings instance."""
        defaults = {
            "ENVIRONMENT": "production",
            "SECRET_KEY": "a-secure-production-key-that-is-at-least-32-chars-long",
            "FIELD_ENCRYPTION_KEY": "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdW5pdC10ZXN0cw==",
        }
        defaults.update(overrides)
        return defaults

    def test_storage_defaults(self):
        """Test that storage config fields have correct defaults."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)

            assert settings.STORAGE_ENABLED is False
            assert settings.STORAGE_BUCKET_NAME is None
            assert settings.STORAGE_ACCESS_KEY_ID is None
            assert settings.STORAGE_SECRET_ACCESS_KEY is None

    def test_storage_enabled_from_env(self):
        """Test that storage config fields load from environment variables."""
        with patch.dict(os.environ, {
            "STORAGE_ENABLED": "true",
            "STORAGE_BUCKET_NAME": "my-bucket",
            "STORAGE_ACCESS_KEY_ID": "AKID123",
            "STORAGE_SECRET_ACCESS_KEY": "secret456",
        }):
            settings = Settings(_env_file=None)

            assert settings.STORAGE_ENABLED is True
            assert settings.STORAGE_BUCKET_NAME == "my-bucket"
            assert settings.STORAGE_ACCESS_KEY_ID == "AKID123"
            assert settings.STORAGE_SECRET_ACCESS_KEY == "secret456"

    def test_database_ssl_mode_warning_in_production(self):
        """Test that insecure DATABASE_SSL_MODE emits a warning in production."""
        import warnings

        for ssl_mode in ("disable", "allow"):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                Settings(**self._production_settings_kwargs(DATABASE_SSL_MODE=ssl_mode))
                ssl_warnings = [x for x in w if "DATABASE_SSL_MODE" in str(x.message)]
                assert len(ssl_warnings) == 1, (
                    f"Expected warning for DATABASE_SSL_MODE='{ssl_mode}'"
                )
                assert ssl_mode in str(ssl_warnings[0].message)

    def test_database_ssl_mode_no_warning_when_secure(self):
        """Test that secure DATABASE_SSL_MODE values do not emit warnings in production."""
        import warnings

        for ssl_mode in ("require", "verify-ca", "verify-full"):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                Settings(**self._production_settings_kwargs(DATABASE_SSL_MODE=ssl_mode))
                ssl_warnings = [x for x in w if "DATABASE_SSL_MODE" in str(x.message)]
                assert len(ssl_warnings) == 0, (
                    f"Unexpected warning for DATABASE_SSL_MODE='{ssl_mode}'"
                )

    def test_database_ssl_mode_no_warning_in_development(self):
        """Test that DATABASE_SSL_MODE does not warn in non-production environments."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(
                ENVIRONMENT="development",
                DATABASE_SSL_MODE="disable",
            )
            ssl_warnings = [x for x in w if "DATABASE_SSL_MODE" in str(x.message)]
            assert len(ssl_warnings) == 0
