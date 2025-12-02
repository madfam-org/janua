# Janua API Specification

## Overview

The Janua API is a **RESTful, resource-oriented API** with optional GraphQL endpoint for complex queries. Designed for sub-50ms response times globally with intelligent caching and edge optimization.

**Base URL**: `https://janua.dev/api/v1`  
**GraphQL**: `https://janua.dev/graphql`  
**WebSocket**: `wss://janua.dev/ws`

---

## Authentication

### API Keys (Server-to-Server)

```bash
curl https://janua.dev/api/v1/identities \
  -H "Authorization: Bearer pk_live_..." \
  -H "X-Janua-Tenant: tenant_123"
```

### JWT Tokens (Client-to-Server)

```bash
curl https://janua.dev/api/v1/me \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Janua-Organization: org_456"
```

### Session Cookies (Browser)

```javascript
// Automatically included in browser requests
fetch('https://janua.dev/api/v1/me', {
  credentials: 'include'
});
```

---

## Core Resources

### Identities

```yaml
# POST /v1/identities
Request:
  email: string
  password?: string  # Optional if using passkeys
  profile?:
    firstName?: string
    lastName?: string
    avatarUrl?: string
  metadata?: object

Response:
  id: string
  email: string
  emailVerified: boolean
  profile: object
  createdAt: datetime
  
# GET /v1/identities/:id
# PATCH /v1/identities/:id
# DELETE /v1/identities/:id
```

### Sessions

```yaml
# POST /v1/sessions
Request:
  OneOf:
    - email: string
      password: string
    - email: string
      passkey: PasskeyAssertion
    - refreshToken: string

Response:
  accessToken: string
  refreshToken: string
  expiresIn: number
  identity:
    id: string
    email: string
    
# DELETE /v1/sessions/:id (Revoke)
# GET /v1/sessions/verify
```

### Passkeys

```yaml
# POST /v1/passkeys/registration/begin
Request:
  identityId: string

Response:
  challenge: string
  rp:
    id: string
    name: string
  user:
    id: string
    name: string
    displayName: string
  pubKeyCredParams: array
  timeout: number
  excludeCredentials: array
  authenticatorSelection: object

# POST /v1/passkeys/registration/complete
Request:
  identityId: string
  credential: PublicKeyCredential

Response:
  id: string
  credentialId: string
  deviceName: string
  createdAt: datetime

# POST /v1/passkeys/authentication/begin
# POST /v1/passkeys/authentication/complete
```

### Organizations

```yaml
# POST /v1/organizations
Request:
  name: string
  slug: string
  settings?: object

Response:
  id: string
  name: string
  slug: string
  createdAt: datetime

# GET /v1/organizations
# GET /v1/organizations/:id
# PATCH /v1/organizations/:id
# DELETE /v1/organizations/:id

# Organization Members
POST /v1/organizations/:id/members
GET /v1/organizations/:id/members
DELETE /v1/organizations/:id/members/:memberId
PATCH /v1/organizations/:id/members/:memberId/role
```

### Invitations

```yaml
# POST /v1/invitations
Request:
  organizationId: string
  email: string
  role: string
  expiresIn?: number

Response:
  id: string
  token: string
  expiresAt: datetime
  inviteUrl: string

# POST /v1/invitations/:token/accept
# DELETE /v1/invitations/:id
```

### Policies

```yaml
# POST /v1/policies
Request:
  name: string
  description?: string
  rules: PolicyRules
  effect: "allow" | "deny"

Response:
  id: string
  name: string
  version: number
  compiledWasm?: string  # For edge evaluation

# POST /v1/policies/evaluate
Request:
  subject: string
  action: string
  resource: string
  context?: object

Response:
  allowed: boolean
  reasons: string[]
  appliedPolicies: string[]
```

### Webhooks

```yaml
# POST /v1/webhooks
Request:
  url: string
  events: string[]
  secret?: string
  headers?: object

Response:
  id: string
  url: string
  events: string[]
  signingSecret: string
  
# Webhook Events
identity.created
identity.updated
identity.deleted
session.created
session.revoked
passkey.registered
passkey.used
organization.created
organization.member.added
organization.member.removed
policy.evaluated
```

### Audit Logs

```yaml
# GET /v1/audit-logs
Query Parameters:
  actor?: string
  action?: string
  resource?: string
  startDate?: datetime
  endDate?: datetime
  limit?: number
  cursor?: string

Response:
  events: AuditEvent[]
  nextCursor?: string
  
# GET /v1/audit-logs/export
Query Parameters:
  format: "json" | "csv"
  startDate: datetime
  endDate: datetime

Response:
  exportUrl: string  # S3/R2 presigned URL
  expiresAt: datetime
```

---

## GraphQL API

### Schema

```graphql
type Query {
  # Identity queries
  identity(id: ID!): Identity
  identities(
    filter: IdentityFilter
    sort: IdentitySort
    pagination: Pagination
  ): IdentityConnection!
  
  # Session queries
  session(id: ID!): Session
  currentSession: Session
  
  # Organization queries
  organization(id: ID!): Organization
  organizations(
    filter: OrganizationFilter
    pagination: Pagination
  ): OrganizationConnection!
  
  # Policy evaluation
  evaluatePolicy(input: PolicyEvaluationInput!): PolicyEvaluation!
  
  # Audit logs
  auditLogs(
    filter: AuditLogFilter
    pagination: Pagination
  ): AuditLogConnection!
}

type Mutation {
  # Identity mutations
  createIdentity(input: CreateIdentityInput!): Identity!
  updateIdentity(id: ID!, input: UpdateIdentityInput!): Identity!
  deleteIdentity(id: ID!): Boolean!
  
  # Session mutations
  createSession(input: CreateSessionInput!): Session!
  refreshSession(refreshToken: String!): Session!
  revokeSession(id: ID!): Boolean!
  
  # Passkey mutations
  beginPasskeyRegistration(identityId: ID!): PasskeyChallenge!
  completePasskeyRegistration(
    identityId: ID!
    credential: String!
  ): Passkey!
  
  # Organization mutations
  createOrganization(input: CreateOrganizationInput!): Organization!
  updateOrganization(id: ID!, input: UpdateOrganizationInput!): Organization!
  deleteOrganization(id: ID!): Boolean!
  
  # Member mutations
  inviteMember(input: InviteMemberInput!): Invitation!
  acceptInvitation(token: String!): OrganizationMember!
  updateMemberRole(
    organizationId: ID!
    memberId: ID!
    role: String!
  ): OrganizationMember!
  removeMember(organizationId: ID!, memberId: ID!): Boolean!
  
  # Policy mutations
  createPolicy(input: CreatePolicyInput!): Policy!
  updatePolicy(id: ID!, input: UpdatePolicyInput!): Policy!
  deletePolicy(id: ID!): Boolean!
}

type Subscription {
  # Real-time events
  identityEvents(identityId: ID!): IdentityEvent!
  sessionEvents(identityId: ID!): SessionEvent!
  organizationEvents(organizationId: ID!): OrganizationEvent!
  auditEvents(filter: AuditEventFilter): AuditEvent!
}

# Core Types
type Identity {
  id: ID!
  email: String!
  emailVerified: Boolean!
  profile: Profile!
  passkeys: [Passkey!]!
  sessions: [Session!]!
  organizations: [OrganizationMember!]!
  createdAt: DateTime!
  updatedAt: DateTime!
}

type Session {
  id: ID!
  identity: Identity!
  device: Device!
  expiresAt: DateTime!
  createdAt: DateTime!
  lastActivityAt: DateTime!
}

type Organization {
  id: ID!
  name: String!
  slug: String!
  members: OrganizationMemberConnection!
  invitations: [Invitation!]!
  policies: [Policy!]!
  settings: JSON!
  createdAt: DateTime!
}
```

---

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('wss://janua.dev/ws');

ws.onopen = () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'eyJhbGc...'
  }));
  
  // Subscribe to events
  ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['identity:123', 'org:456']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};
```

### Event Types

```typescript
interface WebSocketEvent {
  type: 'identity.updated' | 'session.created' | 'org.member.added';
  timestamp: string;
  data: any;
  metadata: {
    actor?: string;
    ip?: string;
    userAgent?: string;
  };
}
```

---

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "invalid_request",
    "message": "The request body is invalid",
    "details": {
      "email": "Invalid email format",
      "password": "Password must be at least 12 characters"
    },
    "requestId": "req_2KtYZKyYvhKRU",
    "documentation": "https://janua.dev/docs/errors/invalid_request"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|------------|-------------|
| `invalid_request` | 400 | Request validation failed |
| `unauthorized` | 401 | Missing or invalid authentication |
| `forbidden` | 403 | Insufficient permissions |
| `not_found` | 404 | Resource not found |
| `conflict` | 409 | Resource already exists |
| `rate_limited` | 429 | Too many requests |
| `internal_error` | 500 | Server error |
| `service_unavailable` | 503 | Temporary unavailability |

---

## Rate Limiting

### Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
X-RateLimit-Policy: tenant
```

### Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| Authentication | 10/min | Per IP |
| API (authenticated) | 1000/min | Per tenant |
| API (unauthenticated) | 100/min | Per IP |
| Webhooks | 10000/hour | Per tenant |
| GraphQL | 1000 points/min | Per tenant |

---

## Pagination

### Cursor-based

```json
GET /v1/identities?limit=20&cursor=eyJpZCI6MTIzfQ

{
  "data": [...],
  "pagination": {
    "hasMore": true,
    "nextCursor": "eyJpZCI6MTQzfQ"
  }
}
```

### Offset-based (deprecated)

```json
GET /v1/identities?limit=20&offset=40

{
  "data": [...],
  "pagination": {
    "total": 156,
    "limit": 20,
    "offset": 40
  }
}
```

---

## Idempotency

### Request

```bash
curl -X POST https://janua.dev/api/v1/identities \
  -H "Idempotency-Key: 27fadde4-312a-49b7-8579-3ce21a58938f" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

### Response

```http
HTTP/1.1 201 Created
Idempotency-Key: 27fadde4-312a-49b7-8579-3ce21a58938f
Idempotent-Replayed: false
```

---

## Webhooks

### Payload Format

```json
{
  "id": "evt_2KtYZKyYvhKRU",
  "type": "identity.created",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "identity": {
      "id": "idt_123",
      "email": "user@example.com"
    }
  },
  "metadata": {
    "tenantId": "tenant_123",
    "apiVersion": "2024-01-01"
  }
}
```

### Signature Verification

```javascript
const crypto = require('crypto');

function verifyWebhook(payload, signature, secret) {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');
    
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  );
}
```

---

## SDK Integration Examples

### JavaScript/TypeScript

```typescript
import { Janua } from '@janua/sdk';

const janua = new Janua({
  apiKey: process.env.JANUA_API_KEY,
  tenant: process.env.JANUA_TENANT_ID
});

// Create identity
const identity = await janua.identities.create({
  email: 'user@example.com',
  password: 'secure-password-123'
});

// Create session
const session = await janua.sessions.create({
  email: 'user@example.com',
  password: 'secure-password-123'
});

// Verify token
const claims = await janua.sessions.verify(token);
```

### Python

```python
from janua import Janua

janua = Janua(
    api_key=os.environ['JANUA_API_KEY'],
    tenant=os.environ['JANUA_TENANT_ID']
)

# Create identity
identity = janua.identities.create(
    email='user@example.com',
    password='secure-password-123'
)

# Create session
session = janua.sessions.create(
    email='user@example.com',
    password='secure-password-123'
)

# Verify token
claims = janua.sessions.verify(token)
```

### Go

```go
import "github.com/madfam-io/janua-go"

client := janua.NewClient(
    janua.WithAPIKey(os.Getenv("JANUA_API_KEY")),
    janua.WithTenant(os.Getenv("JANUA_TENANT_ID")),
)

// Create identity
identity, err := client.Identities.Create(ctx, &janua.CreateIdentityRequest{
    Email:    "user@example.com",
    Password: "secure-password-123",
})

// Create session
session, err := client.Sessions.Create(ctx, &janua.CreateSessionRequest{
    Email:    "user@example.com",
    Password: "secure-password-123",
})

// Verify token
claims, err := client.Sessions.Verify(ctx, token)
```

### Ruby

```ruby
require 'janua'

Janua.api_key = ENV['JANUA_API_KEY']
Janua.tenant = ENV['JANUA_TENANT_ID']

# Create identity
identity = Janua::Identity.create(
  email: 'user@example.com',
  password: 'secure-password-123'
)

# Create session
session = Janua::Session.create(
  email: 'user@example.com',
  password: 'secure-password-123'
)

# Verify token
claims = Janua::Session.verify(token)
```

---

## API Versioning

### Version Strategy

- **URL versioning**: `/v1/`, `/v2/`
- **Backwards compatibility**: 12 months minimum
- **Deprecation notices**: 6 months advance warning
- **Version header**: `X-API-Version: 2024-01-01`

### Version Negotiation

```bash
# Request specific version
curl https://janua.dev/api/v1/identities \
  -H "X-API-Version: 2024-01-01"

# Response includes version
HTTP/1.1 200 OK
X-API-Version: 2024-01-01
X-API-Deprecated: false
X-API-Sunset: 2025-01-01
```

---

## Performance Guarantees

### SLAs

| Endpoint | p50 | p95 | p99 |
|----------|-----|-----|-----|
| Session verification | 10ms | 30ms | 50ms |
| Identity creation | 50ms | 100ms | 200ms |
| Policy evaluation | 5ms | 15ms | 30ms |
| GraphQL query | 20ms | 50ms | 100ms |

### Optimization Tips

1. **Use field selection**: Only request needed fields
2. **Enable caching**: Set appropriate cache headers
3. **Batch requests**: Use GraphQL for complex queries
4. **Regional endpoints**: Use nearest region for lower latency
5. **Connection pooling**: Reuse HTTP connections

This API specification provides a comprehensive, production-ready interface that rivals and exceeds Clerk's capabilities while maintaining simplicity and performance.