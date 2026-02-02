"""
Custom SQLAlchemy Types for Cross-Database Compatibility
Created: January 13, 2025

Provides database-agnostic column types, particularly for UUID and JSON support
across PostgreSQL and SQLite.
"""

import json
import uuid

from sqlalchemy import CHAR, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(36) storing as stringified hex values.
    This allows the same model to work with both PostgreSQL and SQLite.
    """

    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid=True):
        """Initialize with optional as_uuid parameter for PostgreSQL compatibility"""
        self.as_uuid = as_uuid
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class JSON(TypeDecorator):
    """
    Platform-independent JSON type.

    Uses PostgreSQL's JSONB type when available, otherwise uses TEXT with JSON serialization.
    This allows the same model to work with both PostgreSQL and SQLite.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            # PostgreSQL JSONB returns dict directly, only parse if string (SQLite)
            if isinstance(value, str):
                value = json.loads(value)
            # else: value is already a dict/list from JSONB, return as-is
        return value


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type that transparently encrypts/decrypts field values at rest.

    Uses Fernet encryption (AES-128-CBC + HMAC-SHA256).
    Gracefully handles unencrypted legacy data on read.
    If FIELD_ENCRYPTION_KEY is not configured (non-production), stores plaintext.
    """

    impl = Text
    cache_ok = True

    def __init__(self, length=None):
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        try:
            from app.core.encryption import FieldEncryptor

            encryptor = FieldEncryptor.get_instance()
            return encryptor.encrypt_field(str(value))
        except Exception:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        try:
            from app.core.encryption import FieldEncryptor

            encryptor = FieldEncryptor.get_instance()
            return encryptor.decrypt_field(value)
        except Exception:
            return value


class InetAddress(TypeDecorator):
    """
    Platform-independent INET/IP address type.

    Uses PostgreSQL INET type when available, otherwise VARCHAR(45) for SQLite.
    This allows the same model to work with both PostgreSQL and SQLite.
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import INET

            return dialect.type_descriptor(INET())
        else:
            return dialect.type_descriptor(String(45))

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return value
