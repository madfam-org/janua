# Plinto Database Design

## Overview

Plinto uses a **multi-database strategy** optimized for different access patterns:
- **PostgreSQL**: Source of truth for transactional data
- **Redis**: Session cache, rate limiting, hot data
- **DynamoDB**: Global secondary indexes for edge reads
- **Elasticsearch**: Audit logs, full-text search, analytics
- **S3/R2**: Long-term storage for exports and backups

---

## PostgreSQL Schema (Primary Database)

### Core Design Principles

1. **Multi-tenancy**: Logical isolation with `tenant_id` everywhere
2. **Partitioning**: Time-based for sessions/events, hash-based for identities
3. **Event Sourcing**: Immutable event log for perfect audit trails
4. **Soft Deletes**: Maintain referential integrity and compliance
5. **JSONB Flexibility**: Metadata fields for extensibility

### Schema Definition

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Custom types
CREATE TYPE auth_method AS ENUM ('password', 'passkey', 'magic_link', 'oauth', 'saml');
CREATE TYPE member_role AS ENUM ('owner', 'admin', 'member', 'guest');
CREATE TYPE event_status AS ENUM ('pending', 'processing', 'completed', 'failed');

-- ============================================
-- TENANTS (Top-level isolation boundary)
-- ============================================
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(63) UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9-]+$'),
    name VARCHAR(255) NOT NULL,
    
    -- Configuration
    region VARCHAR(10) NOT NULL DEFAULT 'us-east-1',
    plan VARCHAR(20) NOT NULL DEFAULT 'community',
    settings JSONB NOT NULL DEFAULT '{}',
    features JSONB NOT NULL DEFAULT '[]',
    
    -- Billing
    stripe_customer_id VARCHAR(255),
    billing_email VARCHAR(255),
    subscription_status VARCHAR(20) DEFAULT 'trialing',
    
    -- Limits
    max_mau INTEGER DEFAULT 2000,
    max_organizations INTEGER DEFAULT 5,
    max_sso_connections INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    -- Indexes
    INDEX idx_tenants_slug (slug) WHERE deleted_at IS NULL,
    INDEX idx_tenants_region (region),
    INDEX idx_tenants_plan (plan)
);

-- ============================================
-- IDENTITIES (Users)
-- ============================================
CREATE TABLE identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Core fields
    email VARCHAR(255),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    phone VARCHAR(20),
    phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
    username VARCHAR(63),
    
    -- Profile
    profile JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Security
    password_hash VARCHAR(255),
    totp_secret VARCHAR(255),
    backup_codes TEXT[],
    security_keys INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    suspension_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    last_sign_in_at TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(tenant_id, email) WHERE deleted_at IS NULL,
    UNIQUE(tenant_id, username) WHERE deleted_at IS NULL AND username IS NOT NULL,
    
    -- Indexes
    INDEX idx_identities_tenant (tenant_id) WHERE deleted_at IS NULL,
    INDEX idx_identities_email (email) WHERE deleted_at IS NULL,
    INDEX idx_identities_status (status),
    INDEX idx_identities_created (created_at DESC)
) PARTITION BY HASH (tenant_id);

-- Create partitions for identities (8 partitions for distribution)
CREATE TABLE identities_0 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 0);
CREATE TABLE identities_1 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 1);
CREATE TABLE identities_2 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 2);
CREATE TABLE identities_3 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 3);
CREATE TABLE identities_4 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 4);
CREATE TABLE identities_5 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 5);
CREATE TABLE identities_6 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 6);
CREATE TABLE identities_7 PARTITION OF identities FOR VALUES WITH (modulus 8, remainder 7);

-- ============================================
-- PASSKEYS (WebAuthn Credentials)
-- ============================================
CREATE TABLE passkeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
    
    -- WebAuthn fields
    credential_id TEXT UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    
    -- Device info
    aaguid UUID,
    attestation_format VARCHAR(20),
    transport_methods TEXT[],
    device_name VARCHAR(255),
    device_type VARCHAR(20),
    
    -- Metadata
    user_agent TEXT,
    ip_address INET,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    -- Indexes
    INDEX idx_passkeys_identity (identity_id),
    INDEX idx_passkeys_credential (credential_id),
    INDEX idx_passkeys_last_used (last_used_at DESC)
);

-- ============================================
-- SESSIONS
-- ============================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Token management
    access_token_jti UUID NOT NULL UNIQUE,
    refresh_token_hash VARCHAR(64) UNIQUE,
    
    -- Session info
    auth_method auth_method NOT NULL,
    ip_address INET,
    user_agent TEXT,
    device_id VARCHAR(255),
    device_fingerprint JSONB,
    
    -- Expiration
    expires_at TIMESTAMPTZ NOT NULL,
    idle_expires_at TIMESTAMPTZ,
    
    -- Activity
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activity_count INTEGER NOT NULL DEFAULT 1,
    
    -- Revocation
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES identities(id),
    revocation_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_sessions_identity (identity_id) WHERE revoked_at IS NULL,
    INDEX idx_sessions_tenant (tenant_id) WHERE revoked_at IS NULL,
    INDEX idx_sessions_refresh (refresh_token_hash) WHERE revoked_at IS NULL,
    INDEX idx_sessions_jti (access_token_jti),
    INDEX idx_sessions_expires (expires_at) WHERE revoked_at IS NULL,
    INDEX idx_sessions_created (created_at DESC)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for sessions
CREATE TABLE sessions_2024_01 PARTITION OF sessions 
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE sessions_2024_02 PARTITION OF sessions 
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- Continue for all months...

-- ============================================
-- ORGANIZATIONS
-- ============================================
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Core fields
    slug VARCHAR(63) NOT NULL CHECK (slug ~ '^[a-z0-9-]+$'),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Configuration
    settings JSONB NOT NULL DEFAULT '{}',
    features JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Branding
    logo_url VARCHAR(500),
    primary_color VARCHAR(7),
    
    -- Limits
    max_members INTEGER DEFAULT 100,
    max_roles INTEGER DEFAULT 10,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(tenant_id, slug) WHERE deleted_at IS NULL,
    
    -- Indexes
    INDEX idx_organizations_tenant (tenant_id) WHERE deleted_at IS NULL,
    INDEX idx_organizations_slug (slug) WHERE deleted_at IS NULL,
    INDEX idx_organizations_created (created_at DESC)
);

-- ============================================
-- ORGANIZATION MEMBERS
-- ============================================
CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    identity_id UUID NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
    
    -- Role and permissions
    role member_role NOT NULL DEFAULT 'member',
    custom_role_id UUID REFERENCES custom_roles(id),
    permissions JSONB NOT NULL DEFAULT '[]',
    
    -- Metadata
    invited_by UUID REFERENCES identities(id),
    invitation_id UUID,
    
    -- Timestamps
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(organization_id, identity_id) WHERE removed_at IS NULL,
    CHECK (role = 'owner' OR custom_role_id IS NULL),
    
    -- Indexes
    INDEX idx_org_members_org (organization_id) WHERE removed_at IS NULL,
    INDEX idx_org_members_identity (identity_id) WHERE removed_at IS NULL,
    INDEX idx_org_members_role (role)
);

-- ============================================
-- CUSTOM ROLES
-- ============================================
CREATE TABLE custom_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Role definition
    name VARCHAR(63) NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '[]',
    
    -- Metadata
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(tenant_id, name) WHERE organization_id IS NULL,
    UNIQUE(organization_id, name) WHERE organization_id IS NOT NULL,
    
    -- Indexes
    INDEX idx_custom_roles_tenant (tenant_id),
    INDEX idx_custom_roles_org (organization_id)
);

-- ============================================
-- INVITATIONS
-- ============================================
CREATE TABLE invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Invitation details
    email VARCHAR(255) NOT NULL,
    role member_role NOT NULL DEFAULT 'member',
    custom_role_id UUID REFERENCES custom_roles(id),
    
    -- Token
    token VARCHAR(255) UNIQUE NOT NULL,
    
    -- Metadata
    invited_by UUID NOT NULL REFERENCES identities(id),
    message TEXT,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),
    accepted_by UUID REFERENCES identities(id),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    
    -- Indexes
    INDEX idx_invitations_org (organization_id),
    INDEX idx_invitations_email (email),
    INDEX idx_invitations_token (token),
    INDEX idx_invitations_status (status)
);

-- ============================================
-- POLICIES (Authorization Rules)
-- ============================================
CREATE TABLE policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Policy definition
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Rules (OPA/Rego format)
    rules TEXT NOT NULL,
    compiled_wasm BYTEA,
    
    -- Configuration
    effect VARCHAR(10) NOT NULL CHECK (effect IN ('allow', 'deny')),
    priority INTEGER NOT NULL DEFAULT 0,
    conditions JSONB,
    
    -- Status
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    compiled_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(tenant_id, name, version),
    
    -- Indexes
    INDEX idx_policies_tenant (tenant_id) WHERE enabled = TRUE,
    INDEX idx_policies_org (organization_id) WHERE enabled = TRUE,
    INDEX idx_policies_priority (priority DESC)
);

-- ============================================
-- AUDIT EVENTS (Immutable Log)
-- ============================================
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    -- Event details
    event_type VARCHAR(100) NOT NULL,
    event_action VARCHAR(50) NOT NULL,
    event_result VARCHAR(20) NOT NULL CHECK (event_result IN ('success', 'failure', 'error')),
    
    -- Actor
    actor_id UUID REFERENCES identities(id),
    actor_type VARCHAR(20) NOT NULL DEFAULT 'identity',
    impersonator_id UUID REFERENCES identities(id),
    
    -- Target
    target_id UUID,
    target_type VARCHAR(50),
    target_display VARCHAR(255),
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    session_id UUID,
    request_id UUID,
    
    -- Data
    metadata JSONB NOT NULL DEFAULT '{}',
    changes JSONB,
    
    -- Timestamp (immutable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_audit_tenant_created (tenant_id, created_at DESC),
    INDEX idx_audit_actor (actor_id, created_at DESC),
    INDEX idx_audit_target (target_id, created_at DESC),
    INDEX idx_audit_type (event_type, created_at DESC),
    INDEX idx_audit_request (request_id)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for audit events
CREATE TABLE audit_events_2024_01 PARTITION OF audit_events 
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- Continue for all months...

-- ============================================
-- WEBHOOKS
-- ============================================
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Configuration
    url VARCHAR(500) NOT NULL,
    events TEXT[] NOT NULL,
    headers JSONB,
    
    -- Security
    signing_secret VARCHAR(255) NOT NULL,
    
    -- Status
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Statistics
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_webhooks_tenant (tenant_id) WHERE enabled = TRUE,
    INDEX idx_webhooks_events (events) USING GIN
);

-- ============================================
-- WEBHOOK DELIVERIES
-- ============================================
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES audit_events(id),
    
    -- Delivery details
    attempt_count INTEGER NOT NULL DEFAULT 1,
    status_code INTEGER,
    response_body TEXT,
    error_message TEXT,
    
    -- Timing
    delivered_at TIMESTAMPTZ,
    duration_ms INTEGER,
    next_retry_at TIMESTAMPTZ,
    
    -- Status
    status event_status NOT NULL DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_webhook_deliveries_webhook (webhook_id, created_at DESC),
    INDEX idx_webhook_deliveries_status (status) WHERE status = 'pending',
    INDEX idx_webhook_deliveries_retry (next_retry_at) WHERE status = 'pending'
);

-- ============================================
-- JWK KEYS (Key Management)
-- ============================================
CREATE TABLE jwk_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Key details
    kid VARCHAR(255) UNIQUE NOT NULL,
    kty VARCHAR(10) NOT NULL,
    use VARCHAR(10) NOT NULL,
    alg VARCHAR(10) NOT NULL,
    
    -- Key material (public only in DB)
    public_key JSONB NOT NULL,
    thumbprint VARCHAR(64) NOT NULL,
    
    -- Status
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'next', 'retired', 'revoked')),
    
    -- Rotation
    activated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_jwk_keys_kid (kid),
    INDEX idx_jwk_keys_tenant (tenant_id) WHERE status = 'active',
    INDEX idx_jwk_keys_status (status)
);

-- ============================================
-- RATE LIMITS (Tracking)
-- ============================================
CREATE TABLE rate_limit_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Bucket identification
    bucket_key VARCHAR(255) NOT NULL,
    bucket_type VARCHAR(20) NOT NULL,
    
    -- Limits
    limit_value INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,
    
    -- Current state
    current_value INTEGER NOT NULL DEFAULT 0,
    reset_at TIMESTAMPTZ NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(tenant_id, bucket_key),
    
    -- Indexes
    INDEX idx_rate_limits_tenant (tenant_id),
    INDEX idx_rate_limits_reset (reset_at)
);

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to relevant tables
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_identities_updated_at BEFORE UPDATE ON identities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Ensure single owner per organization
CREATE OR REPLACE FUNCTION check_single_owner()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.role = 'owner' THEN
        IF EXISTS (
            SELECT 1 FROM organization_members 
            WHERE organization_id = NEW.organization_id 
            AND role = 'owner' 
            AND id != NEW.id
            AND removed_at IS NULL
        ) THEN
            RAISE EXCEPTION 'Organization can only have one owner';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_single_owner BEFORE INSERT OR UPDATE ON organization_members
    FOR EACH ROW EXECUTE FUNCTION check_single_owner();

-- Auto-expire old sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    UPDATE sessions 
    SET revoked_at = NOW(), 
        revocation_reason = 'expired'
    WHERE expires_at < NOW() 
    AND revoked_at IS NULL;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- MATERIALIZED VIEWS (Analytics)
-- ============================================

-- Daily Active Users
CREATE MATERIALIZED VIEW daily_active_users AS
SELECT 
    tenant_id,
    DATE(created_at) as date,
    COUNT(DISTINCT identity_id) as dau,
    COUNT(*) as total_sessions
FROM sessions
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY tenant_id, DATE(created_at);

CREATE INDEX idx_dau_tenant_date ON daily_active_users(tenant_id, date DESC);

-- Organization Statistics
CREATE MATERIALIZED VIEW organization_stats AS
SELECT 
    o.id as organization_id,
    o.tenant_id,
    COUNT(DISTINCT om.identity_id) as member_count,
    COUNT(DISTINCT CASE WHEN om.role = 'admin' THEN om.identity_id END) as admin_count,
    MAX(om.joined_at) as last_member_joined
FROM organizations o
LEFT JOIN organization_members om ON o.id = om.organization_id AND om.removed_at IS NULL
WHERE o.deleted_at IS NULL
GROUP BY o.id, o.tenant_id;

CREATE INDEX idx_org_stats_tenant ON organization_stats(tenant_id);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on sensitive tables
ALTER TABLE identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- Create policies for tenant isolation
CREATE POLICY tenant_isolation_identities ON identities
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_sessions ON sessions
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_organizations ON organizations
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_audit ON audit_events
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## Redis Schema (Cache Layer)

### Key Patterns

```redis
# Sessions
session:{session_id} -> JSON (TTL: 15 minutes)
session:refresh:{refresh_token_hash} -> session_id (TTL: 7 days)
session:identity:{identity_id} -> SET of session_ids

# Rate Limiting
ratelimit:ip:{ip_address}:{endpoint} -> counter (TTL: 1 minute)
ratelimit:tenant:{tenant_id}:{endpoint} -> counter (TTL: 1 minute)
ratelimit:identity:{identity_id}:{action} -> counter (TTL: 1 hour)

# Feature Flags
features:tenant:{tenant_id} -> JSON
features:global -> JSON

# JWKS Cache
jwks:tenant:{tenant_id} -> JSON (TTL: 5 minutes)
jwks:global -> JSON (TTL: 5 minutes)

# Revocation List
revoked:jti:{jti} -> 1 (TTL: until token expiry)
revoked:session:{session_id} -> 1 (TTL: 24 hours)

# Temporary Data
verify:email:{token} -> identity_id (TTL: 15 minutes)
verify:phone:{code} -> identity_id (TTL: 5 minutes)
reset:password:{token} -> identity_id (TTL: 1 hour)

# Analytics
analytics:tenant:{tenant_id}:mau -> HyperLogLog
analytics:tenant:{tenant_id}:events -> Stream
```

### Lua Scripts

```lua
-- Atomic rate limit check and increment
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('GET', key)

if current and tonumber(current) >= limit then
    return {0, limit - tonumber(current)}
else
    local new_value = redis.call('INCR', key)
    if new_value == 1 then
        redis.call('EXPIRE', key, window)
    end
    return {1, limit - new_value}
end
```

---

## DynamoDB Schema (Global Edge Data)

### Tables

```yaml
# Session Table (Global)
SessionTable:
  PartitionKey: tenant_id
  SortKey: session_id
  Attributes:
    - identity_id
    - expires_at
    - revoked
  GlobalSecondaryIndexes:
    - IdentityIndex:
        PartitionKey: identity_id
        SortKey: created_at
    - ExpiryIndex:
        PartitionKey: tenant_id
        SortKey: expires_at
  TTL: expires_at

# Policy Cache Table
PolicyTable:
  PartitionKey: tenant_id
  SortKey: policy_id#version
  Attributes:
    - compiled_wasm
    - rules
    - effect
    - priority
  GlobalSecondaryIndexes:
    - PriorityIndex:
        PartitionKey: tenant_id
        SortKey: priority

# Identity Cache Table
IdentityTable:
  PartitionKey: tenant_id
  SortKey: identity_id
  Attributes:
    - email
    - organizations
    - roles
    - last_updated
  GlobalSecondaryIndexes:
    - EmailIndex:
        PartitionKey: tenant_id#email
        SortKey: identity_id
```

---

## Elasticsearch Schema (Analytics & Search)

### Index Mappings

```json
{
  "audit-events": {
    "mappings": {
      "properties": {
        "tenant_id": { "type": "keyword" },
        "event_type": { "type": "keyword" },
        "event_action": { "type": "keyword" },
        "event_result": { "type": "keyword" },
        "actor_id": { "type": "keyword" },
        "target_id": { "type": "keyword" },
        "target_type": { "type": "keyword" },
        "ip_address": { "type": "ip" },
        "user_agent": { "type": "text" },
        "metadata": { "type": "object", "enabled": false },
        "created_at": { "type": "date" },
        "message": { "type": "text", "analyzer": "standard" }
      }
    },
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "index.lifecycle.name": "audit-policy",
      "index.lifecycle.rollover_alias": "audit-events"
    }
  }
}
```

### Index Lifecycle Policy

```json
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "7d"
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "freeze": {}
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

---

## Migration Strategy

### Initial Setup

```sql
-- Migration 001: Initial schema
BEGIN;
-- Create all tables as defined above
COMMIT;

-- Migration 002: Seed data
BEGIN;
INSERT INTO tenants (slug, name, region, plan) 
VALUES ('demo', 'Demo Tenant', 'us-east-1', 'community');

INSERT INTO custom_roles (tenant_id, name, permissions, is_system)
SELECT id, 'viewer', '["read"]', true FROM tenants WHERE slug = 'demo';
COMMIT;
```

### Data Migration from Clerk

```sql
-- Migration: Import from Clerk
BEGIN;

-- Import users as identities
INSERT INTO identities (
    id, 
    tenant_id, 
    email, 
    email_verified, 
    profile,
    created_at
)
SELECT 
    gen_random_uuid(),
    (SELECT id FROM tenants WHERE slug = 'imported'),
    clerk_email,
    clerk_email_verified,
    jsonb_build_object(
        'firstName', clerk_first_name,
        'lastName', clerk_last_name,
        'clerkId', clerk_id
    ),
    clerk_created_at
FROM clerk_users_export;

COMMIT;
```

---

## Performance Optimizations

### Indexes

```sql
-- Compound indexes for common queries
CREATE INDEX idx_sessions_lookup 
    ON sessions(tenant_id, identity_id, expires_at DESC) 
    WHERE revoked_at IS NULL;

CREATE INDEX idx_audit_search 
    ON audit_events(tenant_id, event_type, created_at DESC);

-- Partial indexes for active records
CREATE INDEX idx_active_identities 
    ON identities(tenant_id, email) 
    WHERE deleted_at IS NULL AND status = 'active';

-- GIN indexes for JSONB searches
CREATE INDEX idx_identities_metadata 
    ON identities USING GIN (metadata);
```

### Query Optimizations

```sql
-- Use CTEs for complex queries
WITH active_sessions AS (
    SELECT * FROM sessions 
    WHERE expires_at > NOW() 
    AND revoked_at IS NULL
)
SELECT 
    i.email,
    COUNT(s.id) as session_count
FROM identities i
JOIN active_sessions s ON i.id = s.identity_id
GROUP BY i.email;

-- Use window functions for analytics
SELECT 
    tenant_id,
    DATE(created_at) as date,
    COUNT(*) as daily_sessions,
    SUM(COUNT(*)) OVER (
        PARTITION BY tenant_id 
        ORDER BY DATE(created_at) 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as weekly_sessions
FROM sessions
GROUP BY tenant_id, DATE(created_at);
```

This database design provides a solid foundation for Plinto's identity platform with excellent performance, scalability, and maintainability characteristics.