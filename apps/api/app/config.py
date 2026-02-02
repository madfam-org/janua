"""
Application configuration
"""

from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # Application
    VERSION: str = "0.1.0"
    APP_NAME: str = Field(default="Janua")
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(
        default="development", pattern="^(development|staging|production|test)$"
    )
    BASE_URL: str = Field(default="https://janua.dev")
    API_BASE_URL: str = Field(
        default="https://api.janua.dev",
        description="Base URL for the API (used for SSO callbacks, OIDC discovery, etc.)",
    )
    JANUA_CUSTOM_DOMAIN: Optional[str] = Field(
        default=None,
        description="Custom domain for white-label deployments (e.g., auth.madfam.io). Used as OIDC issuer when set.",
    )
    INTERNAL_BASE_URL: Optional[str] = Field(
        default=None, description="Internal service URL for Railway private networking"
    )
    DOMAIN: str = Field(default="localhost")
    UPLOAD_DIR: str = Field(default="/tmp/uploads")
    FRONTEND_URL: Optional[str] = Field(default="http://localhost:3000")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/janua",
        description="PostgreSQL connection URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)
    AUTO_MIGRATE: bool = Field(default=False)

    # Database SSL Configuration
    DATABASE_SSL_MODE: str = Field(
        default="disable",
        description="PostgreSQL SSL mode: disable, allow, prefer, require, verify-ca, verify-full",
    )
    DATABASE_SSL_CA_FILE: Optional[str] = Field(
        default=None,
        description="Path to CA certificate file for database SSL verification",
    )
    DATABASE_SSL_CERT_FILE: Optional[str] = Field(
        default=None,
        description="Path to client certificate file for database SSL mutual auth",
    )
    DATABASE_SSL_KEY_FILE: Optional[str] = Field(
        default=None,
        description="Path to client private key file for database SSL mutual auth",
    )

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    REDIS_POOL_SIZE: int = Field(default=10)
    REDIS_DECODE_RESPONSES: bool = Field(default=True)
    REDIS_MAX_CONNECTIONS: int = Field(
        default=100, description="Maximum number of Redis connections in pool"
    )
    REDIS_CONNECTION_TIMEOUT: int = Field(
        default=5000, description="Redis connection timeout in milliseconds"
    )

    # JWT
    JWT_SECRET_KEY: Optional[str] = Field(default=None)
    JWT_PRIVATE_KEY: Optional[str] = Field(
        default=None, description="RSA private key in PEM format for RS256"
    )
    JWT_PUBLIC_KEY: Optional[str] = Field(
        default=None, description="RSA public key in PEM format for RS256"
    )
    JWT_KID: str = Field(default="janua-primary-key", description="Key ID for JWKS")
    JWT_ALGORITHM: str = Field(default="RS256")
    JWT_ISSUER: str = Field(default="https://api.janua.dev")
    JWT_AUDIENCE: str = Field(default="janua.dev")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480)  # 8 hours for better UX
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    # Aliases for compatibility
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480)  # 8 hours for better UX
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    ALGORITHM: str = Field(default="RS256")

    # Field-level encryption (SOC 2 CF-01)
    FIELD_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Fernet encryption key for sensitive fields at rest. "
        "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'",
    )

    # Security
    SECRET_KEY: Optional[str] = Field(default="development-secret-key-change-in-production")
    BCRYPT_ROUNDS: int = Field(default=12)

    # Cookie Configuration (for cross-subdomain SSO)
    COOKIE_DOMAIN: Optional[str] = Field(
        default=None,
        description="Domain for session cookies (e.g., '.janua.dev' for cross-subdomain SSO). None = current domain only.",
    )
    SECURE_COOKIES: bool = Field(
        default=True, description="Use secure cookies (HTTPS only). Should be True in production."
    )
    PASSWORD_MIN_LENGTH: int = Field(default=12)
    PASSWORD_REQUIRE_UPPERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_LOWERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_NUMBERS: bool = Field(default=True)
    PASSWORD_REQUIRE_SPECIAL: bool = Field(default=True)

    # CORS
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,https://janua.dev",
        description="Comma-separated string or JSON array of allowed CORS origins",
    )

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_PER_HOUR: int = Field(default=1000)
    RATE_LIMIT_WHITELIST: str = Field(
        default="127.0.0.1,::1", description="Comma-separated list of IPs exempt from rate limiting"
    )
    # SECURITY: Only trust X-Forwarded-For/X-Real-IP from these proxy IPs
    # Set to Cloudflare IPs, your load balancer IPs, etc.
    TRUSTED_PROXIES: str = Field(
        default="127.0.0.1,::1",
        description="Comma-separated list of trusted proxy IPs that can set X-Forwarded-For",
    )

    # Account Lockout
    ACCOUNT_LOCKOUT_ENABLED: bool = Field(
        default=True, description="Enable account lockout after failed login attempts"
    )
    ACCOUNT_LOCKOUT_THRESHOLD: int = Field(
        default=5, description="Number of failed attempts before account is locked"
    )
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = Field(
        default=15, description="Duration in minutes to lock account after threshold is reached"
    )
    ACCOUNT_LOCKOUT_RESET_ON_SUCCESS: bool = Field(
        default=True, description="Reset failed attempt counter on successful login"
    )

    # Email Verification Enforcement
    REQUIRE_EMAIL_VERIFICATION: bool = Field(
        default=True, description="Require email verification for sensitive operations"
    )
    EMAIL_VERIFICATION_GRACE_PERIOD_HOURS: int = Field(
        default=24, description="Hours to allow unverified users to access system before blocking"
    )

    # OAuth Client Credential Rotation
    CLIENT_SECRET_ROTATION_ENABLED: bool = Field(
        default=True, description="Enable graceful client secret rotation with overlap period"
    )
    CLIENT_SECRET_ROTATION_GRACE_HOURS: int = Field(
        default=24, description="Hours that old secret remains valid after rotation"
    )
    CLIENT_SECRET_MAX_AGE_DAYS: int = Field(
        default=90, description="Maximum age in days for client secrets before requiring rotation"
    )

    # Email
    EMAIL_ENABLED: bool = Field(default=False)
    EMAIL_PROVIDER: str = Field(default="resend", pattern="^(resend|ses|smtp|sendgrid)$")
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@janua.dev")
    EMAIL_FROM_NAME: str = Field(default="Janua")
    RESEND_API_KEY: Optional[str] = Field(default=None)

    # SMTP Configuration (for development/self-hosted)
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_TLS: bool = Field(default=True)

    # SendGrid Configuration (alternative email provider)
    SENDGRID_API_KEY: Optional[str] = Field(
        default=None, description="SendGrid API key for email delivery"
    )

    # Payment Webhook Secrets
    CONEKTA_WEBHOOK_SECRET: Optional[str] = Field(
        default=None, description="Webhook signing secret for Conekta payment notifications"
    )
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(
        default=None, description="Webhook signing secret for Stripe payment notifications"
    )
    DHANAM_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Webhook signing secret for Dhanam subscription notifications",
    )
    DHANAM_URL: str = Field(
        default="https://dhan.am",
        description="Dhanam billing service URL for checkout redirects",
    )

    # Email aliases for easier access
    FROM_EMAIL: Optional[str] = Field(default=None)
    FROM_NAME: Optional[str] = Field(default=None)
    SUPPORT_EMAIL: Optional[str] = Field(default=None)

    # Internal API (for service-to-service communication)
    INTERNAL_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for internal service communication (email, billing, etc.)",
    )

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
    WEBAUTHN_RP_ID: str = Field(default="janua.dev")
    WEBAUTHN_RP_NAME: str = Field(default="Janua")
    WEBAUTHN_ORIGIN: str = Field(default="https://janua.dev")
    WEBAUTHN_TIMEOUT: int = Field(default=60000)  # milliseconds

    # Cloudflare
    CLOUDFLARE_TURNSTILE_SECRET: Optional[str] = Field(default=None)
    CLOUDFLARE_ACCOUNT_ID: Optional[str] = Field(default=None)
    CLOUDFLARE_R2_ACCESS_KEY: Optional[str] = Field(default=None)
    CLOUDFLARE_R2_SECRET_KEY: Optional[str] = Field(default=None)
    CLOUDFLARE_R2_BUCKET: str = Field(default="janua-audit")
    R2_ENDPOINT: Optional[str] = Field(default=None, description="Cloudflare R2 endpoint URL")
    R2_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="Cloudflare R2 access key ID")
    R2_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None, description="Cloudflare R2 secret access key"
    )

    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None)
    OPENTELEMETRY_ENABLED: bool = Field(default=False)
    OPENTELEMETRY_ENDPOINT: Optional[str] = Field(default=None)
    MONITORING_ENDPOINT: Optional[str] = Field(
        default=None, description="External monitoring service endpoint"
    )
    MONITORING_API_KEY: Optional[str] = Field(
        default=None, description="API key for monitoring service"
    )
    ALERT_WEBHOOK_URL: Optional[str] = Field(
        default=None, description="Webhook URL for sending alerts"
    )

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
    # Beta endpoints - SECURITY: Disabled by default in production
    # These bypass standard auth flows and should only be enabled for development/testing
    ENABLE_BETA_ENDPOINTS: bool = Field(
        default=False,
        description="Enable beta endpoints (/beta/signup, /beta/signin). SECURITY WARNING: These bypass standard auth.",
    )

    # OAuth Providers - Google
    OAUTH_GOOGLE_CLIENT_ID: Optional[str] = Field(
        default=None, description="Google OAuth Client ID"
    )
    OAUTH_GOOGLE_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Google OAuth Client Secret"
    )

    # OAuth Providers - GitHub
    OAUTH_GITHUB_CLIENT_ID: Optional[str] = Field(
        default=None, description="GitHub OAuth Client ID"
    )
    OAUTH_GITHUB_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="GitHub OAuth Client Secret"
    )

    # OAuth Providers - Microsoft
    OAUTH_MICROSOFT_CLIENT_ID: Optional[str] = Field(
        default=None, description="Microsoft OAuth Client ID"
    )
    OAUTH_MICROSOFT_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Microsoft OAuth Client Secret"
    )
    OAUTH_MICROSOFT_TENANT_ID: Optional[str] = Field(
        default="common",
        description="Microsoft Tenant ID (common, organizations, consumers, or specific tenant)",
    )

    # OAuth Providers - Apple
    OAUTH_APPLE_CLIENT_ID: Optional[str] = Field(
        default=None, description="Apple Services ID (e.g., com.madfam.janua)"
    )
    OAUTH_APPLE_TEAM_ID: Optional[str] = Field(default=None, description="Apple Developer Team ID")
    OAUTH_APPLE_KEY_ID: Optional[str] = Field(default=None, description="Apple Sign-In Key ID")
    OAUTH_APPLE_PRIVATE_KEY: Optional[str] = Field(
        default=None, description="Apple Sign-In Private Key (PEM format)"
    )

    # OAuth Providers - Discord
    OAUTH_DISCORD_CLIENT_ID: Optional[str] = Field(
        default=None, description="Discord OAuth Client ID"
    )
    OAUTH_DISCORD_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Discord OAuth Client Secret"
    )

    # OAuth Providers - Twitter/X
    OAUTH_TWITTER_CLIENT_ID: Optional[str] = Field(
        default=None, description="Twitter/X OAuth 2.0 Client ID"
    )
    OAUTH_TWITTER_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Twitter/X OAuth 2.0 Client Secret"
    )

    # OAuth Providers - LinkedIn
    OAUTH_LINKEDIN_CLIENT_ID: Optional[str] = Field(
        default=None, description="LinkedIn OAuth Client ID"
    )
    OAUTH_LINKEDIN_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="LinkedIn OAuth Client Secret"
    )

    # OAuth Providers - Slack
    OAUTH_SLACK_CLIENT_ID: Optional[str] = Field(default=None, description="Slack OAuth Client ID")
    OAUTH_SLACK_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Slack OAuth Client Secret"
    )

    # Limits
    MAX_ORGANIZATIONS_PER_IDENTITY: int = Field(default=10)
    MAX_SESSIONS_PER_IDENTITY: int = Field(default=5)
    MAX_PASSKEYS_PER_IDENTITY: int = Field(default=10)
    MAX_WEBHOOKS_PER_TENANT: int = Field(default=10)

    # Compliance framework settings
    COMPLIANCE_GDPR_ENABLED: bool = Field(
        default=True, description="Enable GDPR compliance features"
    )
    COMPLIANCE_SOC2_ENABLED: bool = Field(
        default=False, description="Enable SOC 2 compliance features"
    )
    COMPLIANCE_HIPAA_ENABLED: bool = Field(
        default=False, description="Enable HIPAA compliance features"
    )
    COMPLIANCE_CCPA_ENABLED: bool = Field(
        default=True, description="Enable CCPA compliance features"
    )
    COMPLIANCE_PCI_DSS_ENABLED: bool = Field(
        default=False, description="Enable PCI DSS compliance features"
    )

    # Data retention defaults
    DEFAULT_RETENTION_PERIOD_DAYS: int = Field(
        default=2555, description="Default retention period (7 years)"
    )
    GDPR_DSR_RESPONSE_DAYS: int = Field(
        default=30, description="GDPR data subject request response period"
    )
    GDPR_BREACH_NOTIFICATION_HOURS: int = Field(
        default=72, description="GDPR breach notification period"
    )

    # Consent management
    CONSENT_COOKIE_LIFETIME_DAYS: int = Field(default=365, description="Consent cookie lifetime")
    CONSENT_RENEWAL_PERIOD_DAYS: int = Field(
        default=365, description="Period for consent renewal reminders"
    )

    # Privacy settings
    PRIVACY_BY_DEFAULT: bool = Field(default=True, description="Privacy by default for new users")
    AUTOMATIC_DATA_ANONYMIZATION: bool = Field(
        default=True, description="Enable automatic data anonymization"
    )

    # Audit and logging
    COMPLIANCE_AUDIT_RETENTION_YEARS: int = Field(
        default=7, description="Compliance audit log retention period"
    )
    AUDIT_LOG_ENCRYPTION: bool = Field(default=True, description="Enable audit log encryption")

    # Data export settings
    DATA_EXPORT_MAX_RECORDS: int = Field(
        default=10000, description="Maximum records per data export"
    )
    DATA_EXPORT_FORMAT_DEFAULT: str = Field(
        default="json", description="Default data export format"
    )

    # Breach detection
    BREACH_DETECTION_ENABLED: bool = Field(
        default=True, description="Enable automated breach detection"
    )
    BREACH_NOTIFICATION_EMAIL: Optional[str] = Field(
        default=None, description="Email for breach notifications"
    )

    # Compliance reporting
    COMPLIANCE_REPORTS_ENABLED: bool = Field(
        default=True, description="Enable compliance reporting"
    )
    COMPLIANCE_DASHBOARD_ENABLED: bool = Field(
        default=True, description="Enable compliance dashboard"
    )

    # Enterprise compliance infrastructure
    EVIDENCE_STORAGE_PATH: str = Field(
        default="/var/compliance/evidence", description="Path for compliance evidence storage"
    )
    DATA_EXPORT_PATH: str = Field(
        default="/var/compliance/exports", description="Path for GDPR data exports"
    )

    # Policy management
    POLICY_ACKNOWLEDGMENT_REQUIRED: bool = Field(
        default=True, description="Require policy acknowledgments"
    )
    POLICY_TRAINING_ENABLED: bool = Field(
        default=True, description="Enable policy training tracking"
    )
    POLICY_VIOLATION_DETECTION: bool = Field(
        default=True, description="Enable automated policy violation detection"
    )

    # Support system
    SUPPORT_SLA_MONITORING: bool = Field(
        default=True, description="Enable SLA monitoring for support"
    )
    SUPPORT_ESCALATION_ENABLED: bool = Field(
        default=True, description="Enable automatic support escalation"
    )
    SUPPORT_METRICS_COLLECTION: bool = Field(
        default=True, description="Enable support metrics collection"
    )

    # Enterprise features
    ENTERPRISE_AUDIT_TRAIL: bool = Field(default=True, description="Enable enterprise audit trail")
    ENTERPRISE_POLICY_MANAGEMENT: bool = Field(
        default=True, description="Enable enterprise policy management"
    )
    ENTERPRISE_PRIVACY_AUTOMATION: bool = Field(
        default=True, description="Enable privacy automation features"
    )

    # Compliance monitoring
    COMPLIANCE_REAL_TIME_MONITORING: bool = Field(
        default=True, description="Enable real-time compliance monitoring"
    )
    COMPLIANCE_ALERT_THRESHOLD_MINUTES: int = Field(
        default=15, description="Minutes before SLA breach alert"
    )
    COMPLIANCE_DASHBOARD_CACHE_MINUTES: int = Field(
        default=5, description="Dashboard data cache duration"
    )

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v):
        import os

        environment = os.getenv("ENVIRONMENT", "development")

        # In production, JWT_SECRET_KEY must be strong if used (HS256 fallback)
        if environment == "production":
            weak_secrets = [
                "development-secret-key",
                "secret",
                "secret-key",
                None,
                "",
            ]
            if v in weak_secrets:
                # In production, we prefer RS256 - if HS256 fallback is used, require strong key
                # This will be checked later; for now, allow None (RS256 should be configured)
                pass
            elif v and len(v) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters in production. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

        # Only use default if no value provided at all (not even empty string)
        if v is None:
            if environment == "production":
                # Return None - jwt_manager will enforce RS256 or raise error
                return None
            return "development-secret-key"
        return v

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v):
        # Validate secret key security
        import os

        environment = os.getenv("ENVIRONMENT", "development")

        # Check for default/weak secrets
        weak_secrets = [
            "change-this-in-production",
            "development-secret-key-change-in-production",
            "development-secret-key",
            "secret",
            "secret-key",
        ]

        if environment == "production":
            # In production, require strong secret
            if not v or v in weak_secrets:
                raise ValueError(
                    "SECRET_KEY must be set to a strong, unique value in production. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if len(v) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")

        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from string to list, handling both JSON and comma-separated formats"""
        import json

        if not self.CORS_ORIGINS.strip():
            return ["http://localhost:3000", "https://janua.dev"]

        # Try to parse as JSON first (for backwards compatibility)
        if self.CORS_ORIGINS.strip().startswith("["):
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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Enforce that critical secrets are set in production."""
        if self.ENVIRONMENT == "production":
            if not self.FIELD_ENCRYPTION_KEY:
                raise ValueError(
                    "FIELD_ENCRYPTION_KEY must be set in production for SOC 2 compliance. "
                    "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            if not self.SECRET_KEY or self.SECRET_KEY == "development-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY must be set to a strong, unique value in production."
                )
        return self

    @model_validator(mode="after")
    def compute_jwt_issuer_from_custom_domain(self) -> "Settings":
        """
        If JANUA_CUSTOM_DOMAIN is set and JWT_ISSUER is still the default,
        use the custom domain as the JWT issuer for white-label deployments.
        """
        default_issuer = "https://api.janua.dev"
        if self.JANUA_CUSTOM_DOMAIN and self.JWT_ISSUER == default_issuer:
            # Use custom domain as issuer (e.g., auth.madfam.io -> https://auth.madfam.io)
            object.__setattr__(self, "JWT_ISSUER", f"https://{self.JANUA_CUSTOM_DOMAIN}")
        return self


# Create settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings instance.

    Returns:
        Settings: Application settings with environment variable support
    """
    return settings
