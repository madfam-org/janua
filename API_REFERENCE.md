# Plinto API Reference

## Base URL

```
Production: https://api.plinto.dev/v1
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
  "redirect_url": "https://yourapp.com/auth/callback"
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
  "avatar_url": "https://cdn.plinto.dev/avatars/usr_abc123.jpg",
  "metadata": {
    "preferences": {
      "theme": "dark",
      "language": "en"
    }
  },
  "created_at": "2025-01-18T12:00:00Z",
  "updated_at": "2025-01-18T14:00:00Z"
}
```

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
  "url": "https://yourapp.com/webhook",
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
GET /auth/oauth/{provider}?redirect_url=https://yourapp.com/callback
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
import { PlintoClient } from '@plinto/typescript-sdk';

const client = new PlintoClient({
  baseURL: 'https://api.plinto.dev',
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
from plinto import PlintoClient

client = PlintoClient(base_url="https://api.plinto.dev")

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
import { useAuth } from '@plinto/react-sdk';

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
import { verifyWebhookSignature } from '@plinto/typescript-sdk';

const isValid = verifyWebhookSignature(
  payload,
  signature,
  secret
);
```

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

- **Documentation**: https://docs.plinto.dev
- **Status Page**: https://status.plinto.dev
- **Support Email**: support@plinto.dev
- **GitHub Issues**: https://github.com/madfam-io/plinto/issues