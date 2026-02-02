"""
Field-level encryption for sensitive data at rest (SOC 2 CF-01, CF-11)
"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


class FieldEncryptor:
    """Encrypt/decrypt sensitive fields using Fernet (AES-128-CBC with HMAC)."""

    _instance = None

    def __init__(self):
        key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
        if key:
            # Key must be 32 url-safe base64-encoded bytes
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            self._fernet = None
            if settings.ENVIRONMENT == "production":
                raise ValueError(
                    "FIELD_ENCRYPTION_KEY must be set in production. "
                    "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )

    @classmethod
    def get_instance(cls) -> "FieldEncryptor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt a string field. Returns base64-encoded ciphertext."""
        if not self._fernet:
            return plaintext
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("ascii")

    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt a field. Gracefully handles unencrypted legacy data."""
        if not self._fernet:
            return ciphertext
        try:
            token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            return self._fernet.decrypt(token).decode("utf-8")
        except (InvalidToken, Exception):
            # Likely plaintext legacy data — return as-is
            return ciphertext
