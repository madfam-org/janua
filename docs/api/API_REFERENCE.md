# Janua API Reference

> **⚠️ DEPRECATED**: This file is deprecated and will be removed in a future release.
>
> **Please use the canonical API documentation:**
> - **Endpoint Reference**: [`/apps/api/docs/api/endpoints-reference.md`](/apps/api/docs/api/endpoints-reference.md)
> - **Rate Limiting**: [`/docs/api/RATE_LIMITING.md`](/docs/api/RATE_LIMITING.md)
> - **Error Handling**: [`/docs/guides/ERROR_HANDLING_GUIDE.md`](/docs/guides/ERROR_HANDLING_GUIDE.md)
> - **SDK Selection**: [`/docs/sdks/CHOOSE_YOUR_SDK.md`](/docs/sdks/CHOOSE_YOUR_SDK.md)

---

## Base URL

```
Production: https://api.janua.dev/v1
Development: http://localhost:8000/v1
```

## Authentication

All API requests require authentication using one of the following methods:

### API Key Authentication

Include your API key in the Authorization header:

```http
Authorization: Bearer YOUR_API_KEY
```

### JWT Authentication

After user login, use the JWT access token:

```http
Authorization: Bearer JWT_ACCESS_TOKEN
```

## Rate Limiting

- **Default**: 100 requests per minute per IP
- **Authenticated**: 1000 requests per minute per user
- **Enterprise**: Custom limits available

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1705590000
```

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request body is invalid",
    "details": {
      "field": "email",
      "reason": "Email is required"
    }
  },
  "request_id": "req_abc123"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `INVALID_REQUEST` | 400 | Invalid request parameters |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Authentication Endpoints

### Sign Up

Create a new user account.

```http
POST /auth/signup
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe"
}
```

**Response:**
```json
{
  "user": {
    "id": "usr_abc123",
    "email": "user@example.com",
    "email_verified": false,
    "username": "johndoe",
    "created_at": "2025-01-18T12:00:00Z"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "ref_xyz789",
    "expires_in": 3600
  }
}
```

### Sign In

Authenticate an existing user.

```http
POST /auth/signin
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response:** Same as Sign Up

### Sign Out

Invalidate the current session.

```http
POST /auth/signout
```

**Headers:**
```http
Authorization: Bearer ACCESS_TOKEN
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully signed out"
}
```

### Refresh Token

Get a new access token using a refresh token.

```http
POST /auth/refresh
```

**Request Body:**
```json
{
  "refresh_token": "ref_xyz789"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "ref_new123",
  "expires_in": 3600
}
```

### Magic Link

Send a passwordless authentication link.

```http
POST /auth/magic-link
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "redirect_url": "https://app.example.com/auth/callback"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Magic link sent to email"
}
```

---

## User Management Endpoints

### Get Current User

```http
GET /users/me
```

**Response:**
```json
{
  "id": "usr_abc123",
  "email": "user@example.com",
  "email_verified": true,
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "avatar_url": "https://cdn.janua.dev/avatars/usr_abc123.jpg",
  "metadata": {
    "preferences": {
      "theme": "dark",
      "language": "en"
    }
  },
  "created_at": "2025-01-18T12:00:00Z",
  "updated_at": "2025-01-18T14:00:00Z",
  "is_service_account": false
}
```

`is_service_account` marks an identity as a technical/service account rather
than a person — a development access login, an importer, an integration
principal. Consuming apps read it to keep such identities out of rosters,
assignee pickers and document-signature fields. It is `false` for every person,
and reported on `/users/{id}`, `/users/` and
`/organizations/{id}/members` as well. Not to be confused with
`client_credentials` service tokens, which have no user row at all (see
`docs/service-tokens.md`). Full contract:
[`docs/architecture/CLAIMS_DE_ORGANIZACION_Y_SERVICE_PRINCIPALS.md`](../architecture/CLAIMS_DE_ORGANIZACION_Y_SERVICE_PRINCIPALS.md).

### Update User Profile

```http
PATCH /users/me
```

**Request Body:**
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "metadata": {
    "preferences": {
      "theme": "light"
    }
  }
}
```

### Delete User

```http
DELETE /users/me
```

**Response:**
```json
{
  "success": true,
  "message": "User account deleted"
}
```

### List User Sessions

```http
GET /users/me/sessions
```

**Response:**
```json
{
  "sessions": [
    {
      "id": "ses_123",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "device_info": {
        "browser": "Chrome",
        "os": "macOS",
        "device": "Desktop"
      },
      "location": {
        "city": "San Francisco",
        "country": "US"
      },
      "created_at": "2025-01-18T12:00:00Z",
      "last_active_at": "2025-01-18T14:00:00Z"
    }
  ],
  "total": 3
}
```

---

## Session Management

### Get Current Session

Retrieve information about the current user session.

```http
GET /sessions/current
```

**Headers:**
```http
Authorization: Bearer ACCESS_TOKEN
```

**Response:**
```json
{
  "session": {
    "id": "sess_abc123",
    "userId": "usr_xyz789",
    "createdAt": "2025-01-18T00:00:00Z",
    "expiresAt": "2025-01-18T01:00:00Z",
    "ipAddress": "192.168.1.1",
    "userAgent": "Mozilla/5.0...",
    "isActive": true
  }
}
```

### List User Sessions

Get all active sessions for the authenticated user.

```http
GET /sessions
```

**Headers:**
```http
Authorization: Bearer ACCESS_TOKEN
```

**Response:**
```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "createdAt": "2025-01-18T00:00:00Z",
      "lastActiveAt": "2025-01-18T00:30:00Z",
      "ipAddress": "192.168.1.1",
      "device": "Chrome on Windows",
      "isCurrent": true
    }
  ],
  "total": 3
}
```

### Revoke Session

Terminate a specific session.

```http
DELETE /sessions/:sessionId
```

**Headers:**
```http
Authorization: Bearer ACCESS_TOKEN
```

**Response:**
```json
{
  "success": true,
  "message": "Session revoked successfully"
}
```

### Revoke All Sessions

Terminate all sessions except the current one.

```http
POST /sessions/revoke-all
```

**Headers:**
```http
Authorization: Bearer ACCESS_TOKEN
```

**Response:**
```json
{
  "success": true,
  "revokedCount": 2,
  "message": "All other sessions revoked"
}
```

---

## Organization Management

### Create Organization

```http
POST /organizations
```

**Request Body:**
```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "description": "Enterprise software solutions"
}
```

### Get Organization

```http
GET /organizations/{org_id}
```

### Update Organization

```http
PATCH /organizations/{org_id}
```

### Delete Organization

```http
DELETE /organizations/{org_id}
```

### List Organization Members

```http
GET /organizations/{org_id}/members
```

### Invite Member

```http
POST /organizations/{org_id}/invitations
```

**Request Body:**
```json
{
  "email": "newmember@example.com",
  "role": "member",
  "message": "Join our team!"
}
```

---

## Multi-Factor Authentication

### Enable TOTP

```http
POST /mfa/totp/enable
```

**Response:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,...",
  "backup_codes": [
    "ABC123",
    "DEF456",
    "GHI789"
  ]
}
```

### Verify TOTP

```http
POST /mfa/totp/verify
```

**Request Body:**
```json
{
  "code": "123456"
}
```

### Disable MFA

```http
POST /mfa/disable
```

---

## Passkeys (WebAuthn)

### Register Passkey Options

```http
GET /passkeys/register/options
```

### Verify Passkey Registration

```http
POST /passkeys/register/verify
```

### Authentication Options

```http
GET /passkeys/authenticate/options
```

### Verify Passkey Authentication

```http
POST /passkeys/authenticate/verify
```

---

## Webhooks

### Create Webhook

```http
POST /webhooks
```

**Request Body:**
```json
{
  "url": "https://app.example.com/webhook",
  "events": [
    "user.created",
    "user.updated",
    "user.deleted",
    "session.created"
  ],
  "description": "Main webhook endpoint"
}
```

### List Webhooks

```http
GET /webhooks
```

### Update Webhook

```http
PATCH /webhooks/{webhook_id}
```

### Delete Webhook

```http
DELETE /webhooks/{webhook_id}
```

### Test Webhook

```http
POST /webhooks/{webhook_id}/test
```

---

## OAuth Providers

### Available Providers

- Google: `/auth/oauth/google`
- GitHub: `/auth/oauth/github`  
- Microsoft: `/auth/oauth/microsoft`
- Discord: `/auth/oauth/discord`
- Twitter: `/auth/oauth/twitter`

### OAuth Flow

1. **Initialize OAuth:**
```http
GET /auth/oauth/{provider}?redirect_url=https://app.example.com/callback
```

2. **Handle Callback:**
```http
GET /auth/oauth/{provider}/callback?code=AUTH_CODE&state=STATE_TOKEN
```

---

## Admin Endpoints

### List Users (Admin Only)

```http
GET /admin/users?page=1&limit=50
```

### Get User by ID

```http
GET /admin/users/{user_id}
```

### Suspend User

```http
POST /admin/users/{user_id}/suspend
```

### Audit Logs

```http
GET /admin/audit-logs?start_date=2025-01-01&end_date=2025-01-31
```

---

## SDK Usage Examples

### TypeScript/JavaScript

```typescript
import { JanuaClient } from '@janua/typescript-sdk';

const client = new JanuaClient({
  baseURL: 'https://api.janua.dev',
  apiKey: 'YOUR_API_KEY'
});

// Sign up
const { user, tokens } = await client.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePassword123!'
});

// Get current user
const currentUser = await client.users.getCurrentUser();
```

### Python

```python
from janua import JanuaClient

client = JanuaClient(base_url="https://api.janua.dev")

# Sign in
response = await client.auth.sign_in(
    email="user@example.com",
    password="SecurePassword123!"
)

# Update profile
await client.users.update_profile(
    first_name="Jane",
    last_name="Smith"
)
```

### React

```jsx
import { useAuth } from '@janua/react-sdk';

function MyComponent() {
  const { signIn, user, isAuthenticated } = useAuth();

  const handleLogin = async () => {
    await signIn('user@example.com', 'password');
  };

  return (
    <div>
      {isAuthenticated ? (
        <p>Welcome, {user.email}!</p>
      ) : (
        <button onClick={handleLogin}>Sign In</button>
      )}
    </div>
  );
}
```

---

## Webhook Events

### Event Types

| Event | Description |
|-------|-------------|
| `user.created` | New user registered |
| `user.updated` | User profile updated |
| `user.deleted` | User account deleted |
| `user.email_verified` | Email address verified |
| `session.created` | New login session |
| `session.deleted` | User signed out |
| `organization.created` | New organization |
| `organization.member_added` | Member joined org |
| `mfa.enabled` | MFA activated |
| `passkey.created` | Passkey registered |

### Webhook Payload

```json
{
  "id": "evt_123",
  "type": "user.created",
  "created_at": "2025-01-18T12:00:00Z",
  "data": {
    "user": {
      "id": "usr_abc123",
      "email": "user@example.com"
    }
  }
}
```

### Webhook Security

Verify webhook signatures:

```typescript
import { verifyWebhookSignature } from '@janua/typescript-sdk';

const isValid = verifyWebhookSignature(
  payload,
  signature,
  secret
);
```

---

## Internal API — Application Roles

Service-to-service surface for sibling MADFAM apps. Authenticated with the
`X-Internal-API-Key` header (**not** a user JWT), the same trust boundary as the
other `/api/v1/internal/*` endpoints. A missing header is `422`; a wrong key is
`401`.

An **application role** is authority *inside a product* — `hcm:hr`, `hcm:admin` —
granted to one person in one organization. It is resolved into the token's
`roles` claim as `"<app>:<role>"`. It is deliberately NOT an organization role
(`owner`/`admin`/`member`), which describes authority over the janua account and
rides under `madfam_org_roles`. See
`docs/architecture/CLAIMS_DE_ORGANIZACION_Y_SERVICE_PRINCIPALS.md` §5.

`app` and `role` are **opaque to janua**: there is no enum of valid apps and no
vocabulary of role names, so a new role in a consuming product needs no janua
deploy. Janua validates shape only — no blank strings, no whitespace, and no `:`
inside a component (the claim is `f"{app}:{role}"`, so a separator inside one
could fabricate a role string the resource server matches).

> Requires migration `016_org_member_app_roles`. `promote` runs no migrations —
> it must be applied by hand first.

### Grant an Application Role

```http
POST /api/v1/internal/app-roles/grant
```

**Request Body:**
```json
{
  "organization_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "app": "hcm",
  "role": "hr"
}
```

**Response** — `201` when this call created the grant, `200` when a live one
already existed (idempotent; the original `granted_at` is preserved):
```json
{
  "id": "9f8e7d6c-5b4a-4392-8180-7f6e5d4c3b2a",
  "organization_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "app": "hcm",
  "role": "hr",
  "claim_value": "hcm:hr",
  "granted_at": "2026-09-03T12:00:00Z",
  "revoked_at": null,
  "changed": true
}
```

`404` when the user has no **active** membership in that organization — the same
filter the claims resolver applies, so a grant that could never feed a token is
surfaced rather than silently accepted.

### Revoke an Application Role

```http
POST /api/v1/internal/app-roles/revoke
```

Same request body as grant. Always `200` when the membership exists; `changed`
reports whether this call was the one that revoked it. Revoking a role that was
never granted is success with `changed: false`, not an error.

The row is **retired, never deleted** (`revoked_at` is stamped), so the grant
history stays auditable. A later re-grant creates a NEW row. The revocation
reaches a live session at its next token refresh.

### List Application Roles

```http
GET /api/v1/internal/app-roles/{organization_id}/{user_id}
```

**Response:**
```json
{
  "organization_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "claim_values": ["hcm:hr"],
  "grants": [
    {
      "id": "9f8e7d6c-5b4a-4392-8180-7f6e5d4c3b2a",
      "app": "hcm",
      "role": "hr",
      "claim_value": "hcm:hr",
      "granted_by": "internal-api-key",
      "granted_at": "2026-09-03T12:00:00Z",
      "revoked_at": null,
      "revoked_by": null
    }
  ]
}
```

`claim_values` is the resolved **live** set — exactly what this person's next
token carries under `roles` — so an operator can answer "why can they not see
HR?" without decoding a JWT. `grants` includes revoked rows, because who removed
an authority and when is the question the table exists to answer. Scoped to one
membership, so it never reports another organization's grants.

## Delegated Application-Role Administration

The internal surface above is the **operator** path. This one is the
**self-service** path: a signed-in person (a normal janua-audience bearer token,
the dashboard's — not a product-audience token and not the internal key)
administers ONE app's roles in ONE organization.

**The rule:** an **active** member of an organization who holds a **live
`<app>:admin`** grant in that organization may list, grant and revoke roles of
**that app only** (`<app>:<any role>`) for **active** members of **that same**
organization. Nothing else.

- **Nothing is implicit.** Organization roles (`owner`/`admin`/`member`) never
  confer app administration. An org owner without `<app>:admin` gets `403`.
- **Bootstrap.** The first `<app>:admin` of each app in each organization is
  still granted by an operator through `POST /api/v1/internal/app-roles/grant`.
- **No organization crossing.** The organization and the app come from the path.
  A caller who is not an active member of the organization, an unknown
  organization, and a target who is not an active member all answer the same
  `404` message, so the surface cannot be used to probe membership.
- **Self-change refused.** A caller may not grant or revoke their own
  `<app>:admin` (`403`); another admin of the app must.
- **No lockout.** A revoke that would leave the organization with zero live
  `<app>:admin` grants is refused with `409`.
- **Audit names the person.** `granted_by` / `revoked_by` store the caller's user
  id, and each change is written to the audit log with the caller as the actor.
- **When it takes effect.** A granted or revoked role reaches the member's token
  at their next token mint (sign-in or refresh), and only for a session whose
  primary organization is this one.
- Mutating routes are rate-limited per client (30/minute).

Errors use janua's standard error envelope (`{"error": {"code", "message"}}`).

### List My Application Roles in an Organization

```http
GET /api/v1/organizations/{org_id}/app-roles
Authorization: Bearer <access token>
```

The caller's own live roles in that organization. `administered_apps` lists the
apps whose roles the caller may manage.

```json
{
  "organization_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "claim_values": ["creator-census:admin"],
  "administered_apps": ["creator-census"]
}
```

### List an App's Grants

```http
GET /api/v1/organizations/{org_id}/app-roles/{app}
```

Requires `<app>:admin` in `org_id`. Returns the app's live grants on active
memberships, with each member's user id, email and name, the caller's own roles
for the app, and the organization's active members (the grant picker).

```json
{
  "organization_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  "app": "creator-census",
  "caller_user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "caller_roles": ["admin"],
  "grants": [
    {
      "id": "9f8e7d6c-5b4a-4392-8180-7f6e5d4c3b2a",
      "user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
      "email": "owner@example.com",
      "name": "Product Owner",
      "role": "admin",
      "claim_value": "creator-census:admin",
      "granted_by": "internal-api-key",
      "granted_at": "2026-09-25T12:00:00Z"
    }
  ],
  "members": [
    {"user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", "email": "owner@example.com", "name": "Product Owner"}
  ]
}
```

### Grant a Role of the App

```http
POST /api/v1/organizations/{org_id}/app-roles/{app}/grant
```

Name the member by exactly one of `user_id` or `email`. An `email` is resolved
only among the organization's **active** members, never globally.

```json
{ "email": "colleague@example.com", "role": "viewer" }
```

Same response as the internal grant: `201` when this call created the grant,
`200` when a live one already existed (returned untouched). `404` when the target
is not an active member; `409` when more than one active member has that email
(use `user_id`).

### Revoke a Role of the App

```http
POST /api/v1/organizations/{org_id}/app-roles/{app}/revoke
```

```json
{ "user_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", "role": "viewer" }
```

Always `200` for an active target; `changed` reports whether this call stamped
`revoked_at`. The row is retired, never deleted, and a later re-grant is a new
row. `409` when it would remove the organization's last `<app>:admin`.

### Dashboard

The dashboard page for one app is
`https://app.janua.dev/organizations/{org_id}/app-roles/{app}`. Products link
to it for their access administration (for example Creator Census's
`CENSUS_ACCESS_ADMIN_URL`). The organization page links to it for each app the
caller administers.

---

## Status Codes

| Status | Description |
|--------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Server Error |
| 503 | Service Unavailable |

## Support

- **Documentation**: https://docs.janua.dev
- **Status Page**: https://status.janua.dev
- **Support Email**: support@janua.dev
- **GitHub Issues**: https://github.com/madfam-org/janua/issues