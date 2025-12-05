# API Reference Documentation

Complete API reference for Janua's authentication and authorization platform.

## Table of Contents

1. [Authentication Endpoints](#authentication-endpoints)
2. [User Management](#user-management)
3. [Organization & Multi-Tenant](#organization--multi-tenant)
4. [RBAC & Permissions](#rbac--permissions)
5. [Session Management](#session-management)
6. [OAuth Providers](#oauth-providers)
7. [Enterprise Features](#enterprise-features)
8. [Webhook Events](#webhook-events)
9. [Rate Limiting](#rate-limiting)
10. [Error Codes](#error-codes)

## Base URLs

```
Production: https://api.janua.dev
Staging: https://api-staging.janua.dev
Development: http://localhost:3000
```

## Authentication

All API requests must include authentication headers:

```http
Authorization: Bearer <jwt_token>
X-API-Key: <api_key>
```

For multi-tenant requests:
```http
X-Tenant-ID: <tenant_id>
X-Organization-ID: <org_id>
```

---

## Authentication Endpoints

### POST /auth/register

Create a new user account with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "firstName": "John",
  "lastName": "Doe",
  "metadata": {
    "source": "web_app",
    "utm_campaign": "signup_flow"
  }
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "emailVerified": false,
      "createdAt": "2025-01-15T10:30:00Z",
      "lastActiveAt": "2025-01-15T10:30:00Z"
    },
    "session": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "rt_abcd1234...",
      "expiresAt": "2025-01-15T11:30:00Z"
    }
  }
}
```

**Errors:**
- `400` - Invalid input data
- `409` - Email already exists
- `422` - Password does not meet requirements

### POST /auth/login

Authenticate user with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "deviceInfo": {
    "userAgent": "Mozilla/5.0...",
    "ipAddress": "192.168.1.1",
    "deviceFingerprint": "fp_abc123"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "emailVerified": true,
      "mfaEnabled": false,
      "lastActiveAt": "2025-01-15T10:30:00Z"
    },
    "session": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "rt_abcd1234...",
      "expiresAt": "2025-01-15T11:30:00Z",
      "deviceId": "dev_xyz789"
    },
    "requiresMfa": false
  }
}
```

### POST /auth/login/mfa

Complete MFA challenge for login.

**Request:**
```json
{
  "tempToken": "tmp_abc123...",
  "method": "totp",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "session": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "rt_abcd1234...",
      "expiresAt": "2025-01-15T11:30:00Z"
    }
  }
}
```

### POST /auth/magic-link/send

Send magic link for passwordless authentication.

**Request:**
```json
{
  "email": "user@example.com",
  "redirectUrl": "https://app.example.com/auth/callback",
  "expiresIn": 3600
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "linkId": "ml_abc123...",
    "expiresAt": "2025-01-15T11:30:00Z"
  }
}
```

### GET /auth/magic-link/verify

Verify magic link token.

**Parameters:**
- `token` (required): Magic link token
- `redirect_uri` (optional): Redirect URL after verification

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@example.com"
    },
    "session": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "rt_abcd1234...",
      "expiresAt": "2025-01-15T11:30:00Z"
    }
  }
}
```

### POST /auth/passkeys/register/begin

Start passkey registration process.

**Request:**
```json
{
  "displayName": "John Doe",
  "authenticatorSelection": {
    "authenticatorAttachment": "platform",
    "userVerification": "required"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "challenge": "Y2hhbGxlbmdl...",
    "rp": {
      "id": "janua.dev",
      "name": "Janua"
    },
    "user": {
      "id": "dXNyXzEyMzQ1Njc4OTA=",
      "name": "user@example.com",
      "displayName": "John Doe"
    },
    "pubKeyCredParams": [
      {
        "type": "public-key",
        "alg": -7
      }
    ],
    "timeout": 60000,
    "attestation": "none"
  }
}
```

### POST /auth/passkeys/register/complete

Complete passkey registration.

**Request:**
```json
{
  "id": "cred_abc123...",
  "rawId": "Y3JlZF9hYmMxMjM=",
  "response": {
    "attestationObject": "o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YVjE...",
    "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIiwiY2hhbGxlbmdl..."
  },
  "type": "public-key"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "credentialId": "cred_abc123...",
    "verified": true
  }
}
```

### POST /auth/passkeys/authenticate/begin

Start passkey authentication.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "challenge": "Y2hhbGxlbmdl...",
    "rpId": "janua.dev",
    "allowCredentials": [
      {
        "id": "Y3JlZF9hYmMxMjM=",
        "type": "public-key"
      }
    ],
    "timeout": 60000,
    "userVerification": "required"
  }
}
```

### POST /auth/passkeys/authenticate/complete

Complete passkey authentication.

**Request:**
```json
{
  "id": "cred_abc123...",
  "rawId": "Y3JlZF9hYmMxMjM=",
  "response": {
    "authenticatorData": "SZYN5YgOjGh0NBcPZHZgW4_krrmihjLHmVzzuoMdl2M=",
    "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdl...",
    "signature": "MEUCIQDNRVdMRY_-IG0qp7QMc8CJYGAKUYQxX..."
  },
  "type": "public-key"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@example.com"
    },
    "session": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "rt_abcd1234...",
      "expiresAt": "2025-01-15T11:30:00Z"
    }
  }
}
```

### POST /auth/refresh

Refresh access token using refresh token.

**Request:**
```json
{
  "refreshToken": "rt_abcd1234..."
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiIs...",
    "refreshToken": "rt_xyz789...",
    "expiresAt": "2025-01-15T12:30:00Z"
  }
}
```

### POST /auth/logout

Logout user and invalidate session.

**Request:**
```json
{
  "refreshToken": "rt_abcd1234..."
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## User Management

### GET /users/me

Get current user profile.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "usr_1234567890",
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "emailVerified": true,
    "phoneNumber": "+1234567890",
    "phoneVerified": false,
    "avatar": "https://cdn.janua.dev/avatars/usr_1234567890.jpg",
    "mfaEnabled": true,
    "createdAt": "2025-01-15T10:30:00Z",
    "lastActiveAt": "2025-01-15T10:30:00Z",
    "metadata": {
      "source": "web_app"
    }
  }
}
```

### PUT /users/me

Update current user profile.

**Request:**
```json
{
  "firstName": "Jane",
  "lastName": "Smith",
  "phoneNumber": "+9876543210",
  "avatar": "https://example.com/avatar.jpg",
  "metadata": {
    "preferences": {
      "theme": "dark",
      "language": "en"
    }
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "usr_1234567890",
    "email": "user@example.com",
    "firstName": "Jane",
    "lastName": "Smith",
    "phoneNumber": "+9876543210",
    "avatar": "https://example.com/avatar.jpg"
  }
}
```

### POST /users/me/change-password

Change user password.

**Request:**
```json
{
  "currentPassword": "OldPassword123!",
  "newPassword": "NewPassword456!",
  "logoutOtherSessions": true
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Password changed successfully",
  "data": {
    "sessionsInvalidated": 3
  }
}
```

### POST /users/me/verify-email/send

Send email verification.

**Response (200):**
```json
{
  "success": true,
  "message": "Verification email sent"
}
```

### POST /users/me/verify-email/confirm

Verify email with token.

**Request:**
```json
{
  "token": "evt_abc123..."
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Email verified successfully"
}
```

### DELETE /users/me

Delete current user account.

**Request:**
```json
{
  "password": "UserPassword123!",
  "confirmation": "DELETE"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Account deleted successfully"
}
```

---

## Organization & Multi-Tenant

### GET /organizations

List user's organizations.

**Parameters:**
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `role` (optional): Filter by user role

**Response (200):**
```json
{
  "success": true,
  "data": {
    "organizations": [
      {
        "id": "org_abc123",
        "name": "Acme Corp",
        "slug": "acme-corp",
        "logo": "https://cdn.janua.dev/logos/org_abc123.jpg",
        "plan": "enterprise",
        "userRole": "admin",
        "userPermissions": ["users:read", "users:write", "billing:read"],
        "createdAt": "2025-01-10T09:00:00Z",
        "memberCount": 25
      }
    ],
    "totalCount": 1,
    "hasMore": false
  }
}
```

### POST /organizations

Create new organization.

**Request:**
```json
{
  "name": "My Organization",
  "slug": "my-org",
  "domain": "myorg.com",
  "settings": {
    "allowedDomains": ["myorg.com"],
    "ssoRequired": false,
    "mfaRequired": true
  }
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "org_xyz789",
    "name": "My Organization",
    "slug": "my-org",
    "domain": "myorg.com",
    "userRole": "owner",
    "createdAt": "2025-01-15T10:30:00Z"
  }
}
```

### GET /organizations/:orgId

Get organization details.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "org_abc123",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "domain": "acme.com",
    "logo": "https://cdn.janua.dev/logos/org_abc123.jpg",
    "plan": "enterprise",
    "settings": {
      "allowedDomains": ["acme.com", "acme.org"],
      "ssoRequired": true,
      "mfaRequired": true,
      "sessionTimeout": 28800,
      "allowedIpRanges": ["192.168.1.0/24"]
    },
    "createdAt": "2025-01-10T09:00:00Z",
    "memberCount": 25,
    "subscriptionStatus": "active"
  }
}
```

### PUT /organizations/:orgId

Update organization.

**Request:**
```json
{
  "name": "Acme Corporation",
  "logo": "https://example.com/new-logo.jpg",
  "settings": {
    "mfaRequired": true,
    "sessionTimeout": 14400
  }
}
```

### GET /organizations/:orgId/members

List organization members.

**Parameters:**
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset
- `role` (optional): Filter by role
- `search` (optional): Search by name or email

**Response (200):**
```json
{
  "success": true,
  "data": {
    "members": [
      {
        "id": "usr_1234567890",
        "email": "john@acme.com",
        "firstName": "John",
        "lastName": "Doe",
        "avatar": "https://cdn.janua.dev/avatars/usr_1234567890.jpg",
        "role": "admin",
        "permissions": ["users:read", "users:write"],
        "status": "active",
        "joinedAt": "2025-01-10T09:00:00Z",
        "lastActiveAt": "2025-01-15T10:30:00Z"
      }
    ],
    "totalCount": 25,
    "hasMore": false
  }
}
```

### POST /organizations/:orgId/invites

Invite user to organization.

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "member",
  "permissions": ["users:read"],
  "message": "Welcome to Acme Corp!"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "inviteId": "inv_abc123",
    "email": "newuser@example.com",
    "role": "member",
    "expiresAt": "2025-01-22T10:30:00Z"
  }
}
```

### POST /organizations/:orgId/members/:userId/role

Update member role and permissions.

**Request:**
```json
{
  "role": "admin",
  "permissions": ["users:read", "users:write", "billing:read"]
}
```

### DELETE /organizations/:orgId/members/:userId

Remove member from organization.

**Response (200):**
```json
{
  "success": true,
  "message": "Member removed successfully"
}
```

---

## RBAC & Permissions

### GET /roles

List available roles in organization.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "roles": [
      {
        "id": "role_admin",
        "name": "Administrator",
        "description": "Full access to organization",
        "permissions": [
          "users:read",
          "users:write",
          "users:delete",
          "billing:read",
          "billing:write"
        ],
        "isSystem": true,
        "memberCount": 3
      },
      {
        "id": "role_custom_123",
        "name": "Content Manager",
        "description": "Manage content and basic user operations",
        "permissions": [
          "content:read",
          "content:write",
          "users:read"
        ],
        "isSystem": false,
        "memberCount": 5
      }
    ]
  }
}
```

### POST /roles

Create custom role.

**Request:**
```json
{
  "name": "Marketing Manager",
  "description": "Manage marketing content and campaigns",
  "permissions": [
    "content:read",
    "content:write",
    "analytics:read",
    "campaigns:read",
    "campaigns:write"
  ]
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "role_custom_456",
    "name": "Marketing Manager",
    "description": "Manage marketing content and campaigns",
    "permissions": [
      "content:read",
      "content:write",
      "analytics:read",
      "campaigns:read",
      "campaigns:write"
    ],
    "isSystem": false
  }
}
```

### GET /permissions

List all available permissions.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "permissions": [
      {
        "id": "users:read",
        "name": "View Users",
        "description": "View user profiles and information",
        "category": "User Management"
      },
      {
        "id": "users:write",
        "name": "Manage Users",
        "description": "Create, update user profiles",
        "category": "User Management"
      },
      {
        "id": "billing:read",
        "name": "View Billing",
        "description": "View billing information and invoices",
        "category": "Billing"
      }
    ]
  }
}
```

### POST /users/:userId/permissions/check

Check if user has specific permissions.

**Request:**
```json
{
  "permissions": ["users:read", "billing:write"],
  "context": {
    "organizationId": "org_abc123",
    "resourceId": "res_xyz789"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "permission": "users:read",
        "granted": true,
        "source": "role_admin"
      },
      {
        "permission": "billing:write",
        "granted": false,
        "reason": "insufficient_privileges"
      }
    ]
  }
}
```

---

## Session Management

### GET /sessions

List user sessions.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "id": "sess_abc123",
        "deviceId": "dev_xyz789",
        "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "ipAddress": "192.168.1.100",
        "location": {
          "country": "US",
          "city": "San Francisco",
          "region": "CA"
        },
        "isCurrent": true,
        "createdAt": "2025-01-15T10:30:00Z",
        "lastActiveAt": "2025-01-15T10:30:00Z",
        "expiresAt": "2025-01-22T10:30:00Z"
      }
    ]
  }
}
```

### DELETE /sessions/:sessionId

Revoke specific session.

**Response (200):**
```json
{
  "success": true,
  "message": "Session revoked successfully"
}
```

### DELETE /sessions

Revoke all sessions except current.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "revokedCount": 3
  }
}
```

---

## OAuth Providers

### GET /auth/oauth/providers

List available OAuth providers.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "providers": [
      {
        "id": "google",
        "name": "Google",
        "enabled": true,
        "icon": "https://cdn.janua.dev/icons/google.svg"
      },
      {
        "id": "github",
        "name": "GitHub",
        "enabled": true,
        "icon": "https://cdn.janua.dev/icons/github.svg"
      },
      {
        "id": "microsoft",
        "name": "Microsoft",
        "enabled": false,
        "icon": "https://cdn.janua.dev/icons/microsoft.svg"
      }
    ]
  }
}
```

### GET /auth/oauth/:provider

Initiate OAuth flow.

**Parameters:**
- `redirect_uri` (required): Redirect URL after authentication
- `state` (optional): State parameter for CSRF protection
- `scope` (optional): Requested scopes

**Response (302):**
Redirects to OAuth provider authorization URL.

### POST /auth/oauth/:provider/callback

Handle OAuth callback.

**Request:**
```json
{
  "code": "oauth_code_123",
  "state": "csrf_state_456"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@example.com",
      "firstName": "John",
      "lastName": "Doe"
    },
    "session": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "rt_abcd1234...",
      "expiresAt": "2025-01-15T11:30:00Z"
    },
    "isNewUser": false
  }
}
```

---

## Enterprise Features

### POST /audit/events

Query audit log events.

**Request:**
```json
{
  "startDate": "2025-01-01T00:00:00Z",
  "endDate": "2025-01-15T23:59:59Z",
  "eventType": "user.login",
  "userId": "usr_1234567890",
  "limit": 100,
  "offset": 0
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "id": "evt_abc123",
        "eventType": "user.login",
        "userId": "usr_1234567890",
        "organizationId": "org_abc123",
        "ipAddress": "192.168.1.100",
        "userAgent": "Mozilla/5.0...",
        "timestamp": "2025-01-15T10:30:00Z",
        "details": {
          "method": "password",
          "success": true
        },
        "hashChain": "h1:abc123...",
        "verified": true
      }
    ],
    "totalCount": 1,
    "hasMore": false
  }
}
```

### POST /scim/v2/Users

SCIM 2.0 user provisioning.

**Request:**
```json
{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "userName": "john.doe@acme.com",
  "name": {
    "givenName": "John",
    "familyName": "Doe"
  },
  "emails": [
    {
      "value": "john.doe@acme.com",
      "type": "work",
      "primary": true
    }
  ],
  "active": true,
  "groups": [
    {
      "value": "grp_developers",
      "display": "Developers"
    }
  ]
}
```

**Response (201):**
```json
{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "id": "usr_1234567890",
  "userName": "john.doe@acme.com",
  "name": {
    "givenName": "John",
    "familyName": "Doe"
  },
  "emails": [
    {
      "value": "john.doe@acme.com",
      "type": "work",
      "primary": true
    }
  ],
  "active": true,
  "meta": {
    "resourceType": "User",
    "created": "2025-01-15T10:30:00Z",
    "lastModified": "2025-01-15T10:30:00Z",
    "location": "https://api.janua.dev/scim/v2/Users/usr_1234567890"
  }
}
```

### POST /webhooks

Create webhook endpoint.

**Request:**
```json
{
  "url": "https://api.example.com/webhooks/janua",
  "events": ["user.created", "user.updated", "user.deleted"],
  "secret": "whsec_abc123...",
  "active": true
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "wh_abc123",
    "url": "https://api.example.com/webhooks/janua",
    "events": ["user.created", "user.updated", "user.deleted"],
    "active": true,
    "createdAt": "2025-01-15T10:30:00Z"
  }
}
```

---

## Webhook Events

### Event Structure

All webhook events follow this structure:

```json
{
  "id": "evt_abc123",
  "type": "user.created",
  "data": {
    "object": {
      "id": "usr_1234567890",
      "email": "user@example.com"
    }
  },
  "organizationId": "org_abc123",
  "timestamp": "2025-01-15T10:30:00Z",
  "apiVersion": "2025-01-15"
}
```

### Available Events

#### User Events
- `user.created` - User account created
- `user.updated` - User profile updated
- `user.deleted` - User account deleted
- `user.email_verified` - User email verified
- `user.password_changed` - User password changed

#### Authentication Events
- `auth.login` - User logged in
- `auth.logout` - User logged out
- `auth.mfa_enabled` - MFA enabled for user
- `auth.mfa_disabled` - MFA disabled for user
- `auth.passkey_registered` - Passkey registered

#### Organization Events
- `organization.member_added` - Member added to organization
- `organization.member_removed` - Member removed from organization
- `organization.role_changed` - Member role changed

### Webhook Security

All webhook requests include:
- `X-Janua-Signature` header with HMAC-SHA256 signature
- `X-Janua-Timestamp` header with Unix timestamp
- Request body signed with webhook secret

Example verification:
```javascript
const crypto = require('crypto');

function verifyWebhook(payload, signature, secret, timestamp) {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(timestamp + '.' + payload)
    .digest('hex');
  
  return `sha256=${expectedSignature}` === signature;
}
```

---

## Rate Limiting

### Rate Limit Headers

All responses include rate limit headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642262400
X-RateLimit-Bucket: auth
```

### Rate Limits by Endpoint

| Endpoint Category | Limit | Window |
|-------------------|-------|---------|
| Authentication | 10 req/min | Per IP |
| Password Reset | 3 req/hour | Per email |
| Email Verification | 5 req/hour | Per email |
| Magic Links | 5 req/hour | Per email |
| API Calls | 1000 req/hour | Per API key |
| Webhook Delivery | 100 req/min | Per endpoint |

### Rate Limit Exceeded Response

```json
{
  "success": false,
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests. Please try again later.",
    "retryAfter": 60
  }
}
```

---

## Error Codes

### HTTP Status Codes

- `200` - OK
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict
- `422` - Unprocessable Entity
- `429` - Too Many Requests
- `500` - Internal Server Error

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `validation_error` | Request validation failed |
| `authentication_required` | Valid authentication required |
| `insufficient_permissions` | User lacks required permissions |
| `resource_not_found` | Requested resource not found |
| `email_already_exists` | Email address already registered |
| `invalid_credentials` | Login credentials are invalid |
| `mfa_required` | Multi-factor authentication required |
| `session_expired` | Access token has expired |
| `organization_not_found` | Organization not found |
| `member_already_exists` | User already member of organization |
| `rate_limit_exceeded` | Rate limit exceeded |
| `webhook_verification_failed` | Webhook signature verification failed |

---

## SDKs and Code Examples

### JavaScript/TypeScript SDK

```javascript
import { JanuaClient } from '@janua/sdk';

const janua = new JanuaClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.janua.dev'
});

// Register user
const user = await janua.auth.register({
  email: 'user@example.com',
  password: 'SecurePassword123!',
  firstName: 'John',
  lastName: 'Doe'
});

// Login
const session = await janua.auth.login({
  email: 'user@example.com',
  password: 'SecurePassword123!'
});
```

### Python SDK

```python
from janua import JanuaClient

janua = JanuaClient(
    api_key="your-api-key",
    base_url="https://api.janua.dev"
)

# Register user
user = janua.auth.register(
    email="user@example.com",
    password="SecurePassword123!",
    first_name="John",
    last_name="Doe"
)

# Login
session = janua.auth.login(
    email="user@example.com",
    password="SecurePassword123!"
)
```

### cURL Examples

```bash
# Register user
curl -X POST https://api.janua.dev/auth/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "firstName": "John",
    "lastName": "Doe"
  }'

# Login
curl -X POST https://api.janua.dev/auth/login \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

---

## Postman Collection

Import our comprehensive Postman collection for API testing:

```json
{
  "info": {
    "name": "Janua API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "baseUrl",
      "value": "https://api.janua.dev"
    },
    {
      "key": "apiKey",
      "value": "your-api-key"
    }
  ]
}
```

Download: [https://api.janua.dev/postman/collection.json](https://api.janua.dev/postman/collection.json)

---

## OpenAPI Specification

Full OpenAPI 3.0 specification available at:
- Interactive docs: [https://api.janua.dev/docs](https://api.janua.dev/docs)
- JSON spec: [https://api.janua.dev/openapi.json](https://api.janua.dev/openapi.json)
- YAML spec: [https://api.janua.dev/openapi.yaml](https://api.janua.dev/openapi.yaml)

---

## Support and Resources

- **Documentation**: [https://docs.janua.dev](https://docs.janua.dev)
- **API Status**: [https://status.janua.dev](https://status.janua.dev)
- **Support**: [support@janua.dev](mailto:support@janua.dev)
- **GitHub**: [https://github.com/madfam-io/janua](https://github.com/madfam-io/janua)

---

*Last updated: 2025-01-15*