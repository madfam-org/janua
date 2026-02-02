"""
Tests for secrets provider abstraction (SOC 2 CF-06).
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.core.secrets_provider import (
    EnvSecretsProvider,
    VaultSecretsProvider,
    create_secrets_provider,
    reset_secrets_provider,
)

pytestmark = pytest.mark.asyncio


class TestEnvSecretsProvider:
    """Test environment variable secrets provider."""

    async def test_get_secret_exists(self):
        provider = EnvSecretsProvider()
        with patch.dict(os.environ, {"TEST_SECRET": "my-value"}):
            result = await provider.get_secret("TEST_SECRET")
            assert result == "my-value"

    async def test_get_secret_missing(self):
        provider = EnvSecretsProvider()
        result = await provider.get_secret("NONEXISTENT_KEY_12345")
        assert result is None

    async def test_health_check(self):
        provider = EnvSecretsProvider()
        assert await provider.health_check() is True

    async def test_provider_name(self):
        provider = EnvSecretsProvider()
        assert provider.provider_name == "env"


class TestVaultSecretsProvider:
    """Test Vault secrets provider with mocked hvac client."""

    @patch.dict("sys.modules", {"hvac": MagicMock()})
    async def test_get_secret_from_vault(self):
        import hvac  # mocked

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"DB_PASSWORD": "vault-secret"}}
        }

        with patch("app.core.secrets_provider.hvac") as mock_hvac:
            mock_hvac.Client.return_value = mock_client
            provider = VaultSecretsProvider(
                vault_addr="http://vault:8200",
                vault_token="test-token",
            )
            provider._client = mock_client

            result = await provider.get_secret("DB_PASSWORD")
            assert result == "vault-secret"

    @patch.dict("sys.modules", {"hvac": MagicMock()})
    async def test_health_check_authenticated(self):
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True

        with patch("app.core.secrets_provider.hvac") as mock_hvac:
            mock_hvac.Client.return_value = mock_client
            provider = VaultSecretsProvider(
                vault_addr="http://vault:8200",
                vault_token="test-token",
            )
            provider._client = mock_client

            assert await provider.health_check() is True

    @patch.dict("sys.modules", {"hvac": MagicMock()})
    async def test_health_check_unauthenticated(self):
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False

        with patch("app.core.secrets_provider.hvac") as mock_hvac:
            mock_hvac.Client.return_value = mock_client
            provider = VaultSecretsProvider(
                vault_addr="http://vault:8200",
                vault_token="test-token",
            )
            provider._client = mock_client

            assert await provider.health_check() is False

    async def test_provider_name(self):
        with patch.dict("sys.modules", {"hvac": MagicMock()}):
            with patch("app.core.secrets_provider.hvac") as mock_hvac:
                mock_hvac.Client.return_value = MagicMock()
                provider = VaultSecretsProvider(
                    vault_addr="http://vault:8200",
                    vault_token="test-token",
                )
                assert provider.provider_name == "vault"

    @patch.dict("sys.modules", {"hvac": MagicMock()})
    async def test_cache_ttl(self):
        """Test that cache is reused within TTL."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"KEY": "value"}}
        }

        with patch("app.core.secrets_provider.hvac") as mock_hvac:
            mock_hvac.Client.return_value = mock_client
            provider = VaultSecretsProvider(
                vault_addr="http://vault:8200",
                vault_token="test-token",
                cache_ttl=300,
            )
            provider._client = mock_client

            await provider.get_secret("KEY")
            await provider.get_secret("KEY")

            # Should only call Vault once due to caching
            assert mock_client.secrets.kv.v2.read_secret_version.call_count == 1


class TestCreateSecretsProvider:
    """Test factory function."""

    def setup_method(self):
        reset_secrets_provider()

    def teardown_method(self):
        reset_secrets_provider()

    def test_creates_env_provider_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            # Ensure no VAULT_ADDR
            os.environ.pop("VAULT_ADDR", None)
            os.environ.pop("VAULT_TOKEN", None)
            provider = create_secrets_provider()
            assert isinstance(provider, EnvSecretsProvider)

    @patch.dict("sys.modules", {"hvac": MagicMock()})
    def test_creates_vault_provider_when_configured(self):
        with patch("app.core.secrets_provider.hvac") as mock_hvac:
            mock_hvac.Client.return_value = MagicMock()
            with patch.dict(os.environ, {"VAULT_ADDR": "http://vault:8200", "VAULT_TOKEN": "tok"}):
                provider = create_secrets_provider()
                assert isinstance(provider, VaultSecretsProvider)
