# ADR-002: Universal Keyring (Connected Accounts)

**Status:** ACCEPTED (implementation in progress — Coupler Program P1)  
**Date:** 2026-01-17  
**Implementation target:** 2026-07-25 (Coupler P1 gate)
**Authors:** Galaxy Engineering
**Deciders:** Platform Architecture Team

## Context

The Galaxy ecosystem (Janua, Enclii, Dhanam) requires a unified approach to storing and managing third-party credentials across services. Currently:

- **OAuthAccount** model is limited to OAuth providers (Google, GitHub, etc.)
- **PaymentMethod** model is payment-specific (Stripe, Conekta tokens)
- No mechanism exists to store arbitrary API credentials (SendGrid, Twilio, Web3 wallets)

This blocks the "one membership, all services" vision where a single Janua identity grants access to all ecosystem capabilities.

## Decision

Create a `ConnectedAccount` model supporting any provider type with encrypted secrets, enabling:

1. **Financial integrations** (Stripe API keys for Dhanam)
2. **Communication providers** (SendGrid, Twilio for notifications)
3. **Infrastructure credentials** (Cloud provider tokens for Enclii)
4. **Web3 wallets** (Ethereum addresses, signing capabilities)
5. **Custom integrations** (Any third-party API credentials)

## Schema

```sql
-- ============================================================================
-- Universal Keyring: Connected Accounts
-- ============================================================================
-- Stores arbitrary provider credentials securely for the Galaxy ecosystem.
-- Enables "one membership, all services" across Enclii, Dhanam, and partners.
-- ============================================================================

CREATE TABLE connected_accounts (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Ownership (either user-level or org-level, not both)
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Provider identification
    provider_type VARCHAR(50) NOT NULL,      -- 'stripe', 'sendgrid', 'web3_wallet', 'twilio', 'aws', etc.
    provider_name VARCHAR(100) NOT NULL,     -- Display name: "Stripe Production", "My ETH Wallet"
    provider_id VARCHAR(255),                -- External ID (acct_xxx, wallet address, etc.)

    -- Credentials (encrypted at rest using AES-256-GCM)
    -- Keys are derived per-account from a master key (KMS/Vault)
    access_token_encrypted TEXT,             -- Primary credential (API key, access token)
    refresh_token_encrypted TEXT,            -- For OAuth-based providers
    api_key_encrypted TEXT,                  -- For API key-based providers
    secret_key_encrypted TEXT,               -- Secondary secret (Stripe secret key, etc.)

    -- OAuth metadata (for OAuth-based providers)
    oauth_scopes JSONB DEFAULT '[]',         -- Granted scopes: ["read:users", "write:payments"]
    oauth_expires_at TIMESTAMP,              -- Token expiration (for auto-refresh)

    -- Provider-specific metadata
    metadata JSONB DEFAULT '{}',             -- Flexible storage: { "region": "us-east-1", "env": "production" }

    -- Lifecycle management
    status VARCHAR(20) DEFAULT 'active',     -- active, revoked, expired, pending_verification
    verification_status VARCHAR(20),         -- For providers requiring verification: verified, pending, failed
    last_used_at TIMESTAMP,                  -- Track credential usage
    last_verified_at TIMESTAMP,              -- Last successful API call / verification
    expires_at TIMESTAMP,                    -- Hard expiration (null = never)

    -- Audit trail
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by UUID REFERENCES users(id),    -- Who connected this account

    -- Constraints
    CONSTRAINT unique_user_provider UNIQUE (user_id, provider_type, provider_id),
    CONSTRAINT unique_org_provider UNIQUE (organization_id, provider_type, provider_id),
    CONSTRAINT check_owner CHECK (
        (user_id IS NOT NULL AND organization_id IS NULL) OR
        (user_id IS NULL AND organization_id IS NOT NULL)
    )
);

-- Performance indexes
CREATE INDEX idx_connected_accounts_user ON connected_accounts(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_connected_accounts_org ON connected_accounts(organization_id) WHERE organization_id IS NOT NULL;
CREATE INDEX idx_connected_accounts_provider ON connected_accounts(provider_type);
CREATE INDEX idx_connected_accounts_status ON connected_accounts(status);

-- ============================================================================
-- Provider Type Registry
-- ============================================================================
-- Defines supported provider types with validation rules and metadata schema.
-- ============================================================================

CREATE TABLE provider_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Provider identification
    type_code VARCHAR(50) UNIQUE NOT NULL,   -- 'stripe', 'sendgrid', etc.
    display_name VARCHAR(100) NOT NULL,      -- "Stripe"
    category VARCHAR(50) NOT NULL,           -- 'payment', 'communication', 'infrastructure', 'web3'

    -- Configuration
    icon_url VARCHAR(500),                   -- Provider logo
    documentation_url VARCHAR(500),          -- Setup docs

    -- Credential schema (JSON Schema for validation)
    credential_schema JSONB NOT NULL,        -- Defines required/optional credentials
    metadata_schema JSONB DEFAULT '{}',      -- Defines allowed metadata fields

    -- Feature flags
    supports_oauth BOOLEAN DEFAULT FALSE,
    supports_api_key BOOLEAN DEFAULT TRUE,
    supports_verification BOOLEAN DEFAULT TRUE,
    requires_organization BOOLEAN DEFAULT FALSE,  -- Some providers are org-only

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Seed common provider types
INSERT INTO provider_types (type_code, display_name, category, supports_oauth, supports_api_key, credential_schema) VALUES
    ('stripe', 'Stripe', 'payment', FALSE, TRUE, '{"required": ["api_key", "secret_key"], "optional": ["webhook_secret"]}'),
    ('sendgrid', 'SendGrid', 'communication', FALSE, TRUE, '{"required": ["api_key"]}'),
    ('twilio', 'Twilio', 'communication', FALSE, TRUE, '{"required": ["account_sid", "auth_token"]}'),
    ('aws', 'Amazon Web Services', 'infrastructure', FALSE, TRUE, '{"required": ["access_key_id", "secret_access_key"], "optional": ["region"]}'),
    ('web3_wallet', 'Web3 Wallet', 'web3', FALSE, FALSE, '{"required": ["address"], "optional": ["chain_id"]}'),
    ('github', 'GitHub', 'development', TRUE, TRUE, '{"required": ["access_token"], "optional": ["refresh_token"]}'),
    ('custom', 'Custom Provider', 'custom', FALSE, TRUE, '{"required": [], "optional": ["api_key", "secret_key", "access_token"]}');
```

## SQLAlchemy Model

```python
# app/models/connected_accounts.py

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


class ProviderCategory(str, Enum):
    """Categories of connected account providers."""
    PAYMENT = "payment"
    COMMUNICATION = "communication"
    INFRASTRUCTURE = "infrastructure"
    WEB3 = "web3"
    DEVELOPMENT = "development"
    CUSTOM = "custom"


class AccountStatus(str, Enum):
    """Connected account lifecycle states."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING_VERIFICATION = "pending_verification"


class ConnectedAccount(Base):
    """
    Universal Keyring: Stores arbitrary provider credentials securely.

    Enables Galaxy ecosystem integration with third-party services.
    Credentials are encrypted at rest using AES-256-GCM with per-account keys.
    """
    __tablename__ = "connected_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Ownership
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))

    # Provider identification
    provider_type = Column(String(50), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False)
    provider_id = Column(String(255))

    # Credentials (encrypted)
    access_token_encrypted = Column(Text)
    refresh_token_encrypted = Column(Text)
    api_key_encrypted = Column(Text)
    secret_key_encrypted = Column(Text)

    # OAuth metadata
    oauth_scopes = Column(JSONB, default=list)
    oauth_expires_at = Column(DateTime)

    # Provider metadata
    metadata = Column(JSONB, default=dict)

    # Lifecycle
    status = Column(String(20), default=AccountStatus.ACTIVE.value, index=True)
    verification_status = Column(String(20))
    last_used_at = Column(DateTime)
    last_verified_at = Column(DateTime)
    expires_at = Column(DateTime)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="connected_accounts")
    organization = relationship("Organization", foreign_keys=[organization_id])
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        owner = f"user={self.user_id}" if self.user_id else f"org={self.organization_id}"
        return f"<ConnectedAccount {self.provider_type}:{self.provider_name} ({owner})>"

    def is_active(self) -> bool:
        """Check if account is currently usable."""
        if self.status != AccountStatus.ACTIVE.value:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def needs_refresh(self) -> bool:
        """Check if OAuth token needs refresh."""
        if not self.oauth_expires_at:
            return False
        # Refresh 5 minutes before expiry
        return datetime.utcnow() >= self.oauth_expires_at - timedelta(minutes=5)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "id": str(self.id),
            "provider_type": self.provider_type,
            "provider_name": self.provider_name,
            "provider_id": self.provider_id,
            "status": self.status,
            "verification_status": self.verification_status,
            "oauth_scopes": self.oauth_scopes,
            "metadata": self.metadata,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        # Never expose encrypted credentials in API responses
        if include_sensitive:
            result["has_access_token"] = bool(self.access_token_encrypted)
            result["has_api_key"] = bool(self.api_key_encrypted)
            result["has_secret_key"] = bool(self.secret_key_encrypted)

        return result
```

## Encryption Strategy

### Key Management

```
┌─────────────────────────────────────────────────────────────────┐
│                     KEY HIERARCHY                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌─────────────────┐                                          │
│    │   Master Key    │  ← AWS KMS / HashiCorp Vault             │
│    │   (KEK)         │    Never leaves HSM/KMS                  │
│    └────────┬────────┘                                          │
│             │ derives                                            │
│             ▼                                                    │
│    ┌─────────────────┐                                          │
│    │  Tenant Key     │  ← Per organization/user                 │
│    │   (DEK)         │    Encrypted with Master Key             │
│    └────────┬────────┘                                          │
│             │ encrypts                                           │
│             ▼                                                    │
│    ┌─────────────────┐                                          │
│    │  Credentials    │  ← AES-256-GCM encrypted                 │
│    │  (secrets)      │    Unique nonce per operation            │
│    └─────────────────┘                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Notes

1. **Encryption at rest**: All `*_encrypted` columns use AES-256-GCM
2. **Key derivation**: Per-account keys derived from tenant key using HKDF
3. **Nonce management**: Random 12-byte nonce prepended to ciphertext
4. **No plaintext logging**: Secrets never appear in logs, errors, or debug output
5. **Audit trail**: All access logged with timestamp and requester

## Business Alignment

This ADR enables critical Galaxy ecosystem capabilities:

### Dhanam (Finance)
- Store Stripe/Conekta API keys for payment processing
- Store bank connection credentials (Plaid, Belvo)
- Enable subscription billing across all Galaxy services

### Enclii (Infrastructure)
- Store cloud provider credentials (AWS, GCP, Azure)
- Store container registry tokens
- Enable infrastructure provisioning on behalf of users

### Communications
- Store SendGrid/Mailgun API keys for transactional email
- Store Twilio credentials for SMS/voice
- Enable unified notification delivery

### Web3 Integration
- Store wallet addresses for identity verification
- Enable on-chain transaction signing
- Support decentralized identity claims

## API Endpoints

```yaml
# Connected Accounts API
POST   /api/v1/connected-accounts              # Create new connection
GET    /api/v1/connected-accounts              # List user's connections
GET    /api/v1/connected-accounts/{id}         # Get specific connection
PATCH  /api/v1/connected-accounts/{id}         # Update connection metadata
DELETE /api/v1/connected-accounts/{id}         # Revoke/delete connection
POST   /api/v1/connected-accounts/{id}/verify  # Verify credentials work
POST   /api/v1/connected-accounts/{id}/refresh # Refresh OAuth token

# Organization-level
GET    /api/v1/organizations/{org_id}/connected-accounts
POST   /api/v1/organizations/{org_id}/connected-accounts
```

## Security Considerations

1. **Least privilege**: Service accounts get read access to specific providers only
2. **Rotation policy**: Credentials flagged for rotation after configurable period
3. **Access logging**: All credential access logged for audit
4. **Blast radius**: Per-tenant encryption limits breach impact
5. **Verification**: Credentials verified before storage when possible

## Migration Path

1. **Phase 1**: Deploy schema, no data migration (new table)
2. **Phase 2**: Add API endpoints behind feature flag
3. **Phase 3**: Migrate Dhanam billing credentials
4. **Phase 4**: Enable for all Galaxy services
5. **Phase 5**: Deprecate service-specific credential storage

## Consequences

### Positive
- Single source of truth for all third-party credentials
- Consistent encryption and audit across Galaxy
- Enables "one membership, all services" vision
- Reduces credential sprawl across services

### Negative
- Additional complexity in key management
- Requires secure backup/restore procedures
- Single point of failure for credential access
- Cross-service coordination for migrations

### Neutral
- Services must adopt new credential access pattern
- Existing service-specific storage continues to work during migration

## References

- [Galaxy Ecosystem Architecture](./ARCHITECTURE.md)
- [JWT Enrichment (ADR-001)](./ADR-001_JWT_ENRICHMENT.md)
- [Janua Security Model](../security/SECURITY_MODEL.md)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
