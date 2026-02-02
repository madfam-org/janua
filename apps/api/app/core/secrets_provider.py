"""
Secrets provider abstraction for KMS integration (SOC 2 CF-06).

Supports:
- Environment variables (default, zero behavior change)
- HashiCorp Vault (when VAULT_ADDR is configured)
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

try:
    import hvac
except ImportError:
    hvac = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class SecretsProvider(ABC):
    """Abstract base class for secrets providers."""

    @abstractmethod
    async def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret by key."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the secrets provider is healthy."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for health check reporting."""
        pass


class EnvSecretsProvider(SecretsProvider):
    """Reads secrets from environment variables. Zero behavior change from current."""

    async def get_secret(self, key: str) -> Optional[str]:
        return os.environ.get(key)

    async def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "env"


class VaultSecretsProvider(SecretsProvider):
    """
    Reads secrets from HashiCorp Vault using hvac.
    Caches secrets with configurable TTL.
    """

    def __init__(
        self,
        vault_addr: str,
        vault_token: str,
        secret_path: str = "secret/data/janua",
        cache_ttl: int = 300,
    ):
        if hvac is None:
            raise ImportError(
                "hvac package required for Vault integration. Install with: pip install hvac>=2.1.0"
            )

        self._client = hvac.Client(url=vault_addr, token=vault_token)
        self._secret_path = secret_path
        self._cache_ttl = cache_ttl
        self._cache: Dict[str, str] = {}
        self._cache_timestamp: float = 0.0

    async def _refresh_cache(self) -> None:
        """Fetch all secrets from Vault and cache them."""
        now = time.time()
        if self._cache and (now - self._cache_timestamp) < self._cache_ttl:
            return

        try:
            # KV v2 read
            response = self._client.secrets.kv.v2.read_secret_version(
                path=self._secret_path.replace("secret/data/", ""),
                mount_point="secret",
            )
            self._cache = response.get("data", {}).get("data", {}) or {}
            self._cache_timestamp = now
            logger.info("Vault secrets cache refreshed", extra={"path": self._secret_path})
        except Exception as e:
            logger.warning("Failed to read from Vault, using cached values", extra={"error": str(e)})
            if not self._cache:
                raise

    async def get_secret(self, key: str) -> Optional[str]:
        await self._refresh_cache()
        return self._cache.get(key)

    async def health_check(self) -> bool:
        try:
            return self._client.is_authenticated()
        except Exception:
            return False

    @property
    def provider_name(self) -> str:
        return "vault"


# Singleton instance
_provider: Optional[SecretsProvider] = None


def create_secrets_provider() -> SecretsProvider:
    """Factory: select provider based on environment configuration."""
    global _provider
    if _provider is not None:
        return _provider

    vault_addr = os.environ.get("VAULT_ADDR")
    vault_token = os.environ.get("VAULT_TOKEN")

    if vault_addr and vault_token:
        secret_path = os.environ.get("VAULT_SECRET_PATH", "secret/data/janua")
        cache_ttl = int(os.environ.get("VAULT_CACHE_TTL", "300"))
        _provider = VaultSecretsProvider(
            vault_addr=vault_addr,
            vault_token=vault_token,
            secret_path=secret_path,
            cache_ttl=cache_ttl,
        )
        logger.info("Using Vault secrets provider", extra={"addr": vault_addr, "path": secret_path})
    else:
        _provider = EnvSecretsProvider()
        logger.info("Using environment variable secrets provider")

    return _provider


def get_secrets_provider() -> SecretsProvider:
    """Get the current secrets provider instance."""
    global _provider
    if _provider is None:
        return create_secrets_provider()
    return _provider


def reset_secrets_provider() -> None:
    """Reset the singleton (for testing)."""
    global _provider
    _provider = None
