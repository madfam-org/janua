"""
Application configuration
"""

from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application settings with environment variable support
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Application
    VERSION: str = "0.1.0"
    APP_NAME: str = Field(default="Plinto")
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production|test)$")
    BASE_URL: str = Field(default="https://plinto.dev")
    INTERNAL_BASE_URL: Optional[str] = Field(default=None, description="Internal service URL for Railway private networking")
    DOMAIN: str = Field(default="localhost")
    UPLOAD_DIR: str = Field(default="/tmp/uploads")
    FRONTEND_URL: Optional[str] = Field(default="http://localhost:3000")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/plinto",
        description="PostgreSQL connection URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)
    AUTO_MIGRATE: bool = Field(default=False)
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    REDIS_POOL_SIZE: int = Field(default=10)
    REDIS_DECODE_RESPONSES: bool = Field(default=True)
    
    # JWT
    JWT_SECRET_KEY: Optional[str] = Field(default=None)
    JWT_ALGORITHM: str = Field(default="RS256")
    JWT_ISSUER: str = Field(default="https://plinto.dev")
    JWT_AUDIENCE: str = Field(default="plinto.dev")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    # Aliases for compatibility
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    ALGORITHM: str = Field(default="HS256")
    
    # Security
    SECRET_KEY: str = Field(default="change-this-in-production")
    BCRYPT_ROUNDS: int = Field(default=12)
    PASSWORD_MIN_LENGTH: int = Field(default=12)
    PASSWORD_REQUIRE_UPPERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_LOWERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_NUMBERS: bool = Field(default=True)
    PASSWORD_REQUIRE_SPECIAL: bool = Field(default=True)
    
    # CORS
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,https://plinto.dev",
        description="Comma-separated string or JSON array of allowed CORS origins"
    )
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_PER_HOUR: int = Field(default=1000)
    RATE_LIMIT_WHITELIST: str = Field(default="127.0.0.1,::1", description="Comma-separated list of IPs exempt from rate limiting")
    
    # Email
    EMAIL_ENABLED: bool = Field(default=False)
    EMAIL_PROVIDER: str = Field(default="sendgrid", pattern="^(sendgrid|ses|smtp)$")
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@plinto.dev")
    EMAIL_FROM_NAME: str = Field(default="Plinto")
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    
    # SMTP Configuration (for development/self-hosted)
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_TLS: bool = Field(default=True)
    
    # Email aliases for easier access
    FROM_EMAIL: Optional[str] = Field(default=None)
    FROM_NAME: Optional[str] = Field(default=None)
    SUPPORT_EMAIL: Optional[str] = Field(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set email aliases if not explicitly provided
        if not self.FROM_EMAIL:
            self.FROM_EMAIL = self.EMAIL_FROM_ADDRESS
        if not self.FROM_NAME:
            self.FROM_NAME = self.EMAIL_FROM_NAME
        if not self.SUPPORT_EMAIL:
            self.SUPPORT_EMAIL = self.EMAIL_FROM_ADDRESS
    
    # WebAuthn
    WEBAUTHN_RP_ID: str = Field(default="plinto.dev")
    WEBAUTHN_RP_NAME: str = Field(default="Plinto")
    WEBAUTHN_ORIGIN: str = Field(default="https://plinto.dev")
    WEBAUTHN_TIMEOUT: int = Field(default=60000)  # milliseconds
    
    # Cloudflare
    CLOUDFLARE_TURNSTILE_SECRET: Optional[str] = Field(default=None)
    CLOUDFLARE_ACCOUNT_ID: Optional[str] = Field(default=None)
    CLOUDFLARE_R2_ACCESS_KEY: Optional[str] = Field(default=None)
    CLOUDFLARE_R2_SECRET_KEY: Optional[str] = Field(default=None)
    CLOUDFLARE_R2_BUCKET: str = Field(default="plinto-audit")
    R2_ENDPOINT: Optional[str] = Field(default=None, description="Cloudflare R2 endpoint URL")
    R2_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="Cloudflare R2 access key ID")
    R2_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, description="Cloudflare R2 secret access key")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None)
    OPENTELEMETRY_ENABLED: bool = Field(default=False)
    OPENTELEMETRY_ENDPOINT: Optional[str] = Field(default=None)
    MONITORING_ENDPOINT: Optional[str] = Field(default=None, description="External monitoring service endpoint")
    MONITORING_API_KEY: Optional[str] = Field(default=None, description="API key for monitoring service")
    ALERT_WEBHOOK_URL: Optional[str] = Field(default=None, description="Webhook URL for sending alerts")
    
    # Features
    ENABLE_DOCS: bool = Field(default=True)
    ENABLE_METRICS: bool = Field(default=True)
    ENABLE_WEBHOOKS: bool = Field(default=True)
    ENABLE_AUDIT: bool = Field(default=True)
    ENABLE_SSO: bool = Field(default=False)
    ENABLE_SCIM: bool = Field(default=False)
    ENABLE_SIGNUPS: bool = Field(default=True)
    ENABLE_MAGIC_LINKS: bool = Field(default=True)
    ENABLE_OAUTH: bool = Field(default=True)
    ENABLE_MFA: bool = Field(default=True)
    ENABLE_ORGANIZATIONS: bool = Field(default=True)
    
    # Limits
    MAX_ORGANIZATIONS_PER_IDENTITY: int = Field(default=10)
    MAX_SESSIONS_PER_IDENTITY: int = Field(default=5)
    MAX_PASSKEYS_PER_IDENTITY: int = Field(default=10)
    MAX_WEBHOOKS_PER_TENANT: int = Field(default=10)

    # Compliance framework settings
    COMPLIANCE_GDPR_ENABLED: bool = Field(default=True, description="Enable GDPR compliance features")
    COMPLIANCE_SOC2_ENABLED: bool = Field(default=False, description="Enable SOC 2 compliance features")
    COMPLIANCE_HIPAA_ENABLED: bool = Field(default=False, description="Enable HIPAA compliance features")
    COMPLIANCE_CCPA_ENABLED: bool = Field(default=True, description="Enable CCPA compliance features")
    COMPLIANCE_PCI_DSS_ENABLED: bool = Field(default=False, description="Enable PCI DSS compliance features")

    # Data retention defaults
    DEFAULT_RETENTION_PERIOD_DAYS: int = Field(default=2555, description="Default retention period (7 years)")
    GDPR_DSR_RESPONSE_DAYS: int = Field(default=30, description="GDPR data subject request response period")
    GDPR_BREACH_NOTIFICATION_HOURS: int = Field(default=72, description="GDPR breach notification period")

    # Consent management
    CONSENT_COOKIE_LIFETIME_DAYS: int = Field(default=365, description="Consent cookie lifetime")
    CONSENT_RENEWAL_PERIOD_DAYS: int = Field(default=365, description="Period for consent renewal reminders")

    # Privacy settings
    PRIVACY_BY_DEFAULT: bool = Field(default=True, description="Privacy by default for new users")
    AUTOMATIC_DATA_ANONYMIZATION: bool = Field(default=True, description="Enable automatic data anonymization")

    # Audit and logging
    COMPLIANCE_AUDIT_RETENTION_YEARS: int = Field(default=7, description="Compliance audit log retention period")
    AUDIT_LOG_ENCRYPTION: bool = Field(default=True, description="Enable audit log encryption")

    # Data export settings
    DATA_EXPORT_MAX_RECORDS: int = Field(default=10000, description="Maximum records per data export")
    DATA_EXPORT_FORMAT_DEFAULT: str = Field(default="json", description="Default data export format")

    # Breach detection
    BREACH_DETECTION_ENABLED: bool = Field(default=True, description="Enable automated breach detection")
    BREACH_NOTIFICATION_EMAIL: Optional[str] = Field(default=None, description="Email for breach notifications")

    # Compliance reporting
    COMPLIANCE_REPORTS_ENABLED: bool = Field(default=True, description="Enable compliance reporting")
    COMPLIANCE_DASHBOARD_ENABLED: bool = Field(default=True, description="Enable compliance dashboard")
    
    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v):
        # Only use default if no value provided at all (not even empty string)
        if v is None:
            return "development-secret-key"
        return v
    
    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v):
        # Only validate in production environment
        import os
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production" and v == "change-this-in-production":
            raise ValueError("SECRET_KEY must be changed in production")
        return v
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from string to list, handling both JSON and comma-separated formats"""
        import json
        
        if not self.CORS_ORIGINS.strip():
            return ["http://localhost:3000", "https://plinto.dev"]
        
        # Try to parse as JSON first (for backwards compatibility)
        if self.CORS_ORIGINS.strip().startswith('['):
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                pass
        
        # Parse as comma-separated string
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    @property
    def service_url(self) -> str:
        """
        Returns internal URL for service-to-service communication if available,
        otherwise falls back to public BASE_URL
        """
        return self.INTERNAL_BASE_URL or self.BASE_URL


# Create settings instance
settings = Settings()