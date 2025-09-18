# Plinto Architecture Design

## Executive Summary

Plinto is designed as a **edge-native, event-driven identity platform** that outperforms Clerk through superior architecture, not just features. Our design enables sub-30ms global verification, 5-minute integration, and complete data sovereignty.

**Key Differentiators:**
- 🚀 **Edge-first**: Authorization decisions at the edge, not round-trips to origin
- 🔐 **Passkeys-primary**: WebAuthn as first-class, passwords as fallback
- 🌍 **Multi-region native**: Not just deployed globally, but designed for it
- 🎯 **Event-sourced**: Perfect audit trails and compliance by design
- 🔌 **Plugin architecture**: Extensible without forking

---

## Core Architecture

### Hexagonal Architecture (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                            │
│  REST API │ GraphQL │ gRPC │ WebSocket │ Admin UI          │
├─────────────────────────────────────────────────────────────┤
│                     Application Layer                        │
│  Commands │ Queries │ Event Handlers │ Policies            │
├─────────────────────────────────────────────────────────────┤
│                       Domain Core                            │
│  Identity │ Sessions │ Organizations │ Policies │ Audit    │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                      │
│  PostgreSQL │ Redis │ S3/R2 │ Kafka │ Elasticsearch       │
└─────────────────────────────────────────────────────────────┘
```

### Domain Model

```python
# Core domain entities (technology-agnostic)

class Identity:
    """Core identity aggregate root"""
    id: IdentityId
    tenant_id: TenantId
    credentials: List[Credential]
    profile: Profile
    
    def add_passkey(self, passkey: Passkey) -> DomainEvent
    def authenticate(self, credential: Credential) -> Session
    def change_email(self, email: Email) -> DomainEvent

class Session:
    """Session value object"""
    id: SessionId
    identity_id: IdentityId
    device_fingerprint: DeviceFingerprint
    expires_at: DateTime
    
    def refresh(self) -> Token
    def revoke(self) -> DomainEvent
    def is_valid(self) -> bool

class Organization:
    """Organization aggregate"""
    id: OrganizationId
    tenant_id: TenantId
    members: List[Member]
    roles: List[Role]
    
    def invite_member(self, email: Email, role: Role) -> Invitation
    def assign_role(self, member: Member, role: Role) -> DomainEvent
```

---

## Data Architecture (CQRS + Event Sourcing)

### Write Side (Command Model)

**PostgreSQL** - Source of truth for transactional data
```sql
-- Event store for audit and replay
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_aggregate (aggregate_id, created_at)
);

-- Current state projections
CREATE TABLE identities (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    email VARCHAR(255),
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);
```

### Read Side (Query Model)

**Multi-Store Strategy:**
- **Redis**: Hot data (sessions, rate limits, feature flags)
- **DynamoDB**: Global secondary indexes for edge reads
- **Elasticsearch**: Audit logs, analytics, full-text search
- **PostgreSQL Read Replicas**: Complex queries, reporting

### Event Flow

```
User Action → Command → Domain Logic → Event → Event Store
                                          ↓
                                    Event Handlers
                                    ↙     ↓     ↘
                            Read Model  Webhooks  Analytics
```

---

## API Architecture

### RESTful API Design

```yaml
# OpenAPI 3.1 Specification
openapi: 3.1.0
info:
  title: Plinto Identity API
  version: 1.0.0

paths:
  /v1/identities:
    post:
      operationId: createIdentity
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email:
                  type: string
                  format: email
                password:
                  type: string
                  minLength: 12
                profile:
                  $ref: '#/components/schemas/Profile'
      responses:
        201:
          description: Identity created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Identity'
        409:
          description: Identity already exists

  /v1/sessions:
    post:
      operationId: createSession
      requestBody:
        required: true
        content:
          application/json:
            schema:
              oneOf:
                - $ref: '#/components/schemas/PasswordAuth'
                - $ref: '#/components/schemas/PasskeyAuth'
                - $ref: '#/components/schemas/MagicLinkAuth'
      responses:
        201:
          description: Session created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Session'
```

### GraphQL Alternative

```graphql
type Mutation {
  createIdentity(input: CreateIdentityInput!): Identity!
  startPasskeyRegistration(identityId: ID!): PasskeyChallenge!
  completePasskeyRegistration(
    identityId: ID!
    response: PasskeyResponse!
  ): Passkey!
}

type Query {
  identity(id: ID!): Identity
  session(id: ID!): Session
  organization(id: ID!): Organization
}

type Subscription {
  identityEvents(identityId: ID!): IdentityEvent!
  organizationEvents(orgId: ID!): OrganizationEvent!
}
```

---

## Edge Architecture

### Global Edge Network

```
┌─────────────────────────────────────────────────────────┐
│                   Edge PoPs (150+ locations)            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   LAX Edge   │  │   LHR Edge   │  │   SIN Edge   │ │
│  │              │  │              │  │              │ │
│  │ • JWKS Cache │  │ • JWKS Cache │  │ • JWKS Cache │ │
│  │ • Verify JWT │  │ • Verify JWT │  │ • Verify JWT │ │
│  │ • Rate Limit │  │ • Rate Limit │  │ • Rate Limit │ │
│  │ • Geo Route  │  │ • Geo Route  │  │ • Geo Route  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│           ↓                ↓                ↓           │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   Regional Clusters                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   US-EAST    │  │   EU-WEST    │  │   AP-SOUTH   │ │
│  │              │  │              │  │              │ │
│  │ • Full Stack │  │ • Full Stack │  │ • Full Stack │ │
│  │ • PostgreSQL │  │ • PostgreSQL │  │ • PostgreSQL │ │
│  │ • Redis      │  │ • Redis      │  │ • Redis      │ │
│  │ • Kafka      │  │ • Kafka      │  │ • Kafka      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Edge Verification Flow

```typescript
// Cloudflare Worker for edge verification
export default {
  async fetch(request: Request): Promise<Response> {
    const token = extractToken(request);
    
    // Check local cache first (sub-1ms)
    const cached = await CACHE.get(`session:${token}`);
    if (cached) return new Response(cached);
    
    // Verify JWT with cached JWKS (sub-10ms)
    const jwks = await getJWKS(); // Cached at edge
    const claims = await verifyJWT(token, jwks);
    
    // Optional: Check revocation list (async)
    const revoked = await REVOCATION.get(claims.jti);
    if (revoked) return new Response('Unauthorized', { status: 401 });
    
    // Cache for 1 minute
    await CACHE.put(`session:${token}`, JSON.stringify(claims), {
      expirationTtl: 60
    });
    
    return new Response(JSON.stringify(claims));
  }
};
```

---

## SDK Architecture

### Progressive Enhancement Model

```typescript
// Level 1: Simple REST Client
import { PlintoClient } from '@plinto/core';

const plinto = new PlintoClient({ 
  apiKey: 'pk_live_...' 
});

await plinto.identities.create({ email, password });

// Level 2: Smart Client with Caching
import { PlintoClient } from '@plinto/core';

const plinto = new PlintoClient({ 
  apiKey: 'pk_live_...',
  cache: true,
  cacheStore: localStorage
});

// Level 3: Edge-Aware with Local Policy Evaluation
import { PlintoEdge } from '@plinto/edge';

const plinto = new PlintoEdge({
  jwksUrl: 'https://plinto.dev/.well-known/jwks.json',
  policies: './policies.wasm', // WebAssembly policies
  syncInterval: 60000
});

// Verify locally without network call
const session = await plinto.verifyLocal(token);
const allowed = await plinto.evaluatePolicy(session, 'read:documents');

// Level 4: Offline-Capable with Sync
import { PlintoOffline } from '@plinto/offline';

const plinto = new PlintoOffline({
  indexedDB: true,
  syncStrategy: 'eventual',
  conflictResolution: 'last-write-wins'
});
```

### Framework-Specific SDKs

```typescript
// Next.js App Router
import { withPlinto } from '@plinto/nextjs';

export default withPlinto({
  publicRoutes: ['/sign-in', '/sign-up'],
  afterAuth: (auth, req) => {
    if (!auth.orgId && req.url !== '/org-selection') {
      return Response.redirect('/org-selection');
    }
  }
});

// React Components
import { SignIn, UserButton, OrganizationSwitcher } from '@plinto/react-sdk';

export default function App() {
  return (
    <>
      <UserButton afterSignOutUrl="/" />
      <OrganizationSwitcher />
    </>
  );
}
```

---

## Database Schema

### Core Tables (PostgreSQL)

```sql
-- Tenants (isolation boundary)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(63) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(10) NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Identities (users)
CREATE TABLE identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    email VARCHAR(255),
    email_verified BOOLEAN DEFAULT FALSE,
    phone VARCHAR(20),
    phone_verified BOOLEAN DEFAULT FALSE,
    profile JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email),
    INDEX idx_tenant_email (tenant_id, email)
) PARTITION BY HASH (tenant_id);

-- Passkeys (WebAuthn credentials)
CREATE TABLE passkeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID REFERENCES identities(id) ON DELETE CASCADE,
    credential_id TEXT UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    counter INTEGER DEFAULT 0,
    aaguid UUID,
    device_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    INDEX idx_identity_passkeys (identity_id)
);

-- Sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID REFERENCES identities(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id),
    refresh_token_hash VARCHAR(64) UNIQUE,
    device_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_identity_sessions (identity_id, expires_at),
    INDEX idx_refresh_token (refresh_token_hash)
) PARTITION BY RANGE (created_at);

-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    slug VARCHAR(63) NOT NULL,
    name VARCHAR(255) NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, slug)
);

-- Organization Members
CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    identity_id UUID REFERENCES identities(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    permissions JSONB DEFAULT '[]',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, identity_id),
    INDEX idx_identity_orgs (identity_id)
);
```

---

## Infrastructure Architecture

### Container Architecture

```yaml
# docker-compose.yml for local development
version: '3.9'

services:
  api:
    build: ./apps/api
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/plinto
      - REDIS_URL=redis://redis:6379
      - KAFKA_BROKERS=kafka:9092
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
      - kafka

  worker:
    build: ./apps/worker
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/plinto
      - REDIS_URL=redis://redis:6379
      - KAFKA_BROKERS=kafka:9092
    depends_on:
      - db
      - redis
      - kafka

  admin:
    build: ./apps/admin
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    ports:
      - "3000:3000"

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=plinto
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  kafka:
    image: confluentinc/cp-kafka:latest
    environment:
      - KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      - ZOOKEEPER_CLIENT_PORT=2181
```

### Production Deployment (Railway + Vercel + Cloudflare)

```typescript
// infrastructure/terraform/main.tf
terraform {
  required_providers {
    railway = {
      source = "railway/railway"
    }
    vercel = {
      source = "vercel/vercel"
    }
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}

# Railway - Backend Services
resource "railway_project" "plinto" {
  name = "plinto-production"
}

resource "railway_service" "api" {
  project_id = railway_project.plinto.id
  name       = "plinto-api"
  
  environment_variables = {
    PORT = "8000"
    NODE_ENV = "production"
  }
}

resource "railway_postgres" "main" {
  project_id = railway_project.plinto.id
  name       = "plinto-postgres"
}

resource "railway_redis" "cache" {
  project_id = railway_project.plinto.id
  name       = "plinto-redis"
}

# Vercel - Frontend & Edge
resource "vercel_project" "admin" {
  name      = "plinto-admin"
  framework = "nextjs"
  
  environment = {
    NEXT_PUBLIC_API_URL = railway_service.api.url
  }
}

# Cloudflare - CDN & Edge Workers
resource "cloudflare_zone" "plinto" {
  zone = "plinto.dev"
}

resource "cloudflare_worker_script" "edge_verify" {
  name    = "plinto-edge-verify"
  content = file("../../workers/verify.js")
}

resource "cloudflare_worker_route" "api_verify" {
  zone_id     = cloudflare_zone.plinto.id
  pattern     = "plinto.dev/api/v1/verify*"
  script_name = cloudflare_worker_script.edge_verify.name
}
```

---

## Security Architecture

### Defense in Depth

```
Layer 1: Cloudflare WAF
  ↓
Layer 2: Rate Limiting (per IP, per tenant)
  ↓
Layer 3: Bot Protection (Turnstile)
  ↓
Layer 4: Input Validation (Zod schemas)
  ↓
Layer 5: Authentication (Passkeys > Password)
  ↓
Layer 6: Authorization (OPA policies)
  ↓
Layer 7: Audit Logging (immutable)
  ↓
Layer 8: Encryption (at-rest, in-transit)
```

### Zero Trust Security Model

```typescript
// Every request is verified
async function authorizeRequest(req: Request): Promise<boolean> {
  // 1. Verify JWT signature
  const token = await verifyJWT(req.headers.authorization);
  
  // 2. Check token hasn't been revoked
  const revoked = await checkRevocation(token.jti);
  if (revoked) return false;
  
  // 3. Verify tenant context
  const tenant = await verifyTenant(token.tid);
  if (!tenant.active) return false;
  
  // 4. Evaluate policies
  const allowed = await evaluatePolicy({
    subject: token.sub,
    action: req.method,
    resource: req.url,
    context: {
      ip: req.ip,
      device: req.headers['user-agent'],
      time: new Date()
    }
  });
  
  return allowed;
}
```

---

## Monitoring & Observability

### Metrics (Prometheus)

```yaml
# Key metrics to track
plinto_auth_requests_total
plinto_auth_failures_total
plinto_session_duration_seconds
plinto_jwt_verification_duration_milliseconds
plinto_database_query_duration_milliseconds
plinto_cache_hit_ratio
plinto_webhook_delivery_success_rate
plinto_tenant_mau
```

### Distributed Tracing (OpenTelemetry)

```typescript
import { trace } from '@opentelemetry/api';

const tracer = trace.getTracer('plinto-api');

export async function createSession(input: CreateSessionInput) {
  const span = tracer.startSpan('createSession');
  
  try {
    span.setAttributes({
      'tenant.id': input.tenantId,
      'auth.method': input.method
    });
    
    const identity = await authenticateIdentity(input);
    const session = await generateSession(identity);
    const tokens = await issueTokens(session);
    
    span.setStatus({ code: SpanStatusCode.OK });
    return tokens;
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: SpanStatusCode.ERROR });
    throw error;
  } finally {
    span.end();
  }
}
```

---

## Migration Strategy

### From Clerk to Plinto

```typescript
// Dual-write adapter during migration
class AuthAdapter {
  async createUser(data: CreateUserData) {
    // Write to both systems
    const [clerkUser, plintoIdentity] = await Promise.all([
      this.clerk.users.create(data),
      this.plinto.identities.create(data)
    ]);
    
    // Map IDs for consistency
    await this.mapping.save({
      clerkId: clerkUser.id,
      plintoId: plintoIdentity.id
    });
    
    return plintoIdentity;
  }
  
  async verifySession(token: string) {
    // Try Plinto first, fall back to Clerk
    try {
      return await this.plinto.sessions.verify(token);
    } catch {
      const clerkSession = await this.clerk.sessions.verify(token);
      // Create shadow session in Plinto
      return await this.plinto.sessions.createShadow(clerkSession);
    }
  }
}
```

---

## Performance Optimization

### Caching Strategy

```typescript
// Multi-layer caching
class CacheManager {
  layers = [
    new MemoryCache({ ttl: 60 }),      // L1: In-memory (1 min)
    new RedisCache({ ttl: 300 }),      // L2: Redis (5 min)
    new CDNCache({ ttl: 3600 })        // L3: Cloudflare (1 hour)
  ];
  
  async get(key: string): Promise<any> {
    for (const cache of this.layers) {
      const value = await cache.get(key);
      if (value) {
        // Populate higher layers
        this.populateAbove(cache, key, value);
        return value;
      }
    }
    return null;
  }
}
```

### Database Optimization

```sql
-- Partitioning for scale
CREATE TABLE sessions_2024_01 PARTITION OF sessions
  FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Optimized indexes
CREATE INDEX CONCURRENTLY idx_sessions_lookup 
  ON sessions(refresh_token_hash, tenant_id) 
  WHERE revoked_at IS NULL;

-- Materialized views for analytics
CREATE MATERIALIZED VIEW daily_active_users AS
  SELECT 
    tenant_id,
    DATE(created_at) as date,
    COUNT(DISTINCT identity_id) as dau
  FROM sessions
  WHERE created_at > NOW() - INTERVAL '30 days'
  GROUP BY tenant_id, DATE(created_at);
```

---

## Competitive Advantages vs Clerk

| Feature | Clerk | Plinto | Advantage |
|---------|-------|---------|-----------|
| Verification Speed | 50-100ms | <30ms | 2-3x faster |
| Integration Time | 30 minutes | 5 minutes | 6x faster |
| Global Edge PoPs | ~30 | 150+ | 5x coverage |
| Passkey Support | Add-on | Native | Better UX |
| Data Ownership | Vendor-locked | Full export | Compliance |
| Pricing Transparency | Complex | Simple MAU | Predictable |
| Open Source | No | Core components | Extensible |
| GDPR Compliance | Basic | Event sourcing | Full audit |
| Multi-region | Single region | Native multi-region | Sovereignty |
| Free Tier | 5K MAU | 10K MAU | 2x generous |

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- Core domain models
- Basic auth flows (email/password)
- JWT issuance and verification
- PostgreSQL + Redis setup

### Phase 2: Edge (Week 3-4)
- Cloudflare Workers deployment
- JWKS distribution
- Edge caching layer
- Performance optimization

### Phase 3: WebAuthn (Week 5-6)
- Passkey registration/authentication
- Device management
- Fallback mechanisms
- Browser compatibility

### Phase 4: Organizations (Week 7-8)
- Multi-tenancy
- RBAC implementation
- Invitation flows
- Organization switching

### Phase 5: Enterprise (Week 9-12)
- SAML/OIDC SSO
- SCIM provisioning
- Audit logs
- Compliance reports

This architecture positions Plinto to not just compete with Clerk, but to redefine the identity platform category through superior technical design and developer experience.