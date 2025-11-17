"""
SSO Module Exceptions

Custom exceptions for SSO/SAML/OIDC authentication flows.
"""


class SSOException(Exception):
    """Base exception for SSO-related errors."""

    pass


class AuthenticationError(SSOException):
    """Raised when SSO authentication fails."""

    def __init__(self, message: str, provider: str = None, details: dict = None):
        self.message = message
        self.provider = provider
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(SSOException):
    """Raised when SSO configuration or data validation fails."""

    def __init__(self, message: str, field: str = None, details: dict = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(SSOException):
    """Raised when SSO provider configuration is invalid or incomplete."""

    def __init__(self, message: str, provider: str = None, missing_fields: list = None):
        self.message = message
        self.provider = provider
        self.missing_fields = missing_fields or []
        super().__init__(self.message)


class MetadataError(SSOException):
    """Raised when SAML metadata parsing or validation fails."""

    def __init__(self, message: str, metadata_source: str = None):
        self.message = message
        self.metadata_source = metadata_source
        super().__init__(self.message)


class CertificateError(SSOException):
    """Raised when certificate validation or operations fail."""

    def __init__(self, message: str, certificate_id: str = None):
        self.message = message
        self.certificate_id = certificate_id
        super().__init__(self.message)


class ProvisioningError(SSOException):
    """Raised when user provisioning (JIT) fails."""

    def __init__(self, message: str, user_data: dict = None):
        self.message = message
        self.user_data = user_data or {}
        super().__init__(self.message)


__all__ = [
    "SSOException",
    "AuthenticationError",
    "ValidationError",
    "ConfigurationError",
    "MetadataError",
    "CertificateError",
    "ProvisioningError",
]
