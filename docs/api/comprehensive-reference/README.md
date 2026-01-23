# Janua API Comprehensive Reference

Complete reference documentation for the Janua Identity Platform API with enterprise features, authentication methods, and integration patterns.

## 🎯 API Overview

**Base URL**: `https://api.janua.dev`
**Version**: `v1`
**Authentication**: Bearer Token, API Key, OAuth 2.0
**Rate Limiting**: Adaptive rate limiting based on user tier and reputation

### Quick Start
```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     https://api.janua.dev/v1/auth/me
```

## 🔐 Authentication

### 1. Email/Password Authentication

#### Sign Up
```http
POST /v1/auth/signup
Content-Type: application/json

{
  "email": "user@company.com",
  "password": "securePassword123!",
  "firstName": "John",
  "lastName": "Doe",
  "username": "johndoe" // optional
}
```

**Response**:
```json
{
  "user": {
    "id": "usr_1234567890",
    "email": "user@company.com",
    "firstName": "John",
    "lastName": "Doe",
    "username": "johndoe",
    "emailVerified": false,
    "createdAt": "2024-01-15T10:30:00Z"
  },
  "tokens": {
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "rt_1234567890abcdef",
    "expiresIn": 3600,
    "tokenType": "Bearer"
  },
  "requiresEmailVerification": true
}
```

#### Sign In
```http
POST /v1/auth/signin
Content-Type: application/json

{
  "email": "user@company.com",
  "password": "securePassword123!"
}
```

**Response**:
```json
{
  "user": {
    "id": "usr_1234567890",
    "email": "user@company.com",
    "firstName": "John",
    "lastName": "Doe",
    "lastSignInAt": "2024-01-15T10:30:00Z",
    "mfaEnabled": false
  },
  "tokens": {
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "rt_1234567890abcdef",
    "expiresIn": 3600,
    "tokenType": "Bearer"
  },
  "requiresMfa": false
}
```

### 2. OAuth 2.0 Social Authentication

#### Get OAuth URL
```http
GET /v1/auth/oauth/{provider}/url?redirect_uri=https://app.example.com/callback&state=csrf_token
```

**Supported Providers**: `google`, `github`, `microsoft`, `apple`, `discord`, `twitter`, `linkedin`

**Response**:
```json
{
  "authUrl": "https://accounts.google.com/oauth/v2/auth?client_id=...",
  "state": "csrf_token_12345"
}
```

#### Handle OAuth Callback
```http
POST /v1/auth/oauth/{provider}/callback
Content-Type: application/json

{
  "code": "authorization_code_from_provider",
  "state": "csrf_token_12345"
}
```

### 3. Multi-Factor Authentication (MFA)

#### Enable MFA
```http
POST /v1/auth/mfa/enable
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "type": "totp" // or "sms"
}
```

**Response**:
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qrCodeUrl": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "backupCodes": [
    "backup-code-1",
    "backup-code-2",
    "backup-code-3"
  ]
}
```

#### Verify MFA
```http
POST /v1/auth/mfa/verify
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "code": "123456",
  "type": "totp"
}
```

### 4. Passwordless Authentication

#### Send Magic Link
```http
POST /v1/auth/magic-link/send
Content-Type: application/json

{
  "email": "user@company.com",
  "redirectUri": "https://app.example.com/dashboard"
}
```

#### Verify Magic Link
```http
POST /v1/auth/magic-link/verify
Content-Type: application/json

{
  "token": "magic_link_token_from_email"
}
```

### 5. Passkey/WebAuthn

#### Register Passkey
```http
POST /v1/auth/passkeys/register
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "username": "user@company.com",
  "displayName": "John Doe"
}
```

#### Authenticate with Passkey
```http
POST /v1/auth/passkeys/authenticate
Content-Type: application/json

{
  "credential": {
    "id": "passkey_credential_id",
    "rawId": "binary_credential_id",
    "response": {
      "authenticatorData": "...",
      "clientDataJSON": "...",
      "signature": "..."
    }
  }
}
```

## 👥 User Management

### Get Current User
```http
GET /v1/auth/me
Authorization: Bearer ACCESS_TOKEN
```

**Response**:
```json
{
  "id": "usr_1234567890",
  "email": "user@company.com",
  "firstName": "John",
  "lastName": "Doe",
  "username": "johndoe",
  "profileImageUrl": "https://cdn.janua.dev/avatars/usr_1234567890.jpg",
  "emailVerified": true,
  "phoneVerified": false,
  "mfaEnabled": true,
  "isAdmin": false,
  "status": "active",
  "timezone": "UTC",
  "locale": "en-US",
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-15T10:30:00Z",
  "lastSignInAt": "2024-01-15T10:30:00Z"
}
```

### Update User Profile
```http
PATCH /v1/users/me
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "firstName": "John",
  "lastName": "Smith",
  "bio": "Software Engineer at Acme Corp",
  "timezone": "America/New_York",
  "locale": "en-US"
}
```

### Change Password
```http
POST /v1/users/me/password
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "currentPassword": "oldPassword123!",
  "newPassword": "newSecurePassword456!"
}
```

### List Users (Admin)
```http
GET /v1/users?page=1&limit=50&status=active&search=john
Authorization: Bearer ADMIN_ACCESS_TOKEN
```

**Query Parameters**:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50, max: 100)
- `status`: Filter by status (`active`, `inactive`, `suspended`, `deleted`)
- `search`: Search by name or email
- `organizationId`: Filter by organization
- `createdAfter`: Filter by creation date
- `createdBefore`: Filter by creation date

## 🏢 Organization Management

### Create Organization
```http
POST /v1/organizations
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "description": "Leading provider of anvils and roadrunner traps",
  "billingEmail": "billing@acme.com",
  "logoUrl": "https://acme.com/logo.png",
  "settings": {
    "allowSelfSignup": false,
    "requireEmailVerification": true,
    "defaultRole": "member"
  }
}
```

### Get Organization
```http
GET /v1/organizations/{organizationId}
Authorization: Bearer ACCESS_TOKEN
```

**Response**:
```json
{
  "id": "org_1234567890",
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "description": "Leading provider of anvils and roadrunner traps",
  "logoUrl": "https://acme.com/logo.png",
  "billingEmail": "billing@acme.com",
  "memberCount": 150,
  "plan": "enterprise",
  "settings": {
    "allowSelfSignup": false,
    "requireEmailVerification": true,
    "defaultRole": "member",
    "ssoEnabled": true,
    "mfaRequired": true
  },
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-15T10:30:00Z"
}
```

### Invite User to Organization
```http
POST /v1/organizations/{organizationId}/invitations
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "email": "newuser@company.com",
  "role": "member",
  "customRole": "content-editor", // optional custom role
  "message": "Welcome to our organization!",
  "expiresIn": 604800 // 7 days in seconds
}
```

### Manage Organization Members
```http
GET /v1/organizations/{organizationId}/members?page=1&limit=50&role=admin
Authorization: Bearer ACCESS_TOKEN
```

```http
PATCH /v1/organizations/{organizationId}/members/{userId}
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "role": "admin"
}
```

```http
DELETE /v1/organizations/{organizationId}/members/{userId}
Authorization: Bearer ACCESS_TOKEN
```

## 🔑 Enterprise SSO & SAML

### Configure SSO
```http
POST /v1/organizations/{organizationId}/sso
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "provider": "azure_ad",
  "samlMetadataUrl": "https://login.microsoftonline.com/{tenant-id}/federationmetadata/2007-06/federationmetadata.xml",
  "jitProvisioning": true,
  "defaultRole": "member",
  "attributeMapping": {
    "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",`
    "firstName": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",`
    "lastName": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",`
    "groups": "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
  },
  "allowedDomains": ["company.com"]
}
```

### SAML Authentication Flow
```http
GET /v1/sso/saml/{organizationId}/login?RelayState=dashboard
```

```http
POST /v1/sso/saml/{organizationId}/acs
Content-Type: application/x-www-form-urlencoded

SAMLResponse=PHNhbWxwOlJlc3BvbnNlIHhtbG5z...&RelayState=dashboard
```

## 👤 SCIM 2.0 User Provisioning

### List Users (SCIM)
```http
GET /v1/scim/v2/Users?filter=userName eq "john.doe@company.com"&startIndex=1&count=100
Authorization: Bearer SCIM_TOKEN
Content-Type: application/scim+json
```

### Create User (SCIM)
```http
POST /v1/scim/v2/Users
Authorization: Bearer SCIM_TOKEN
Content-Type: application/scim+json

{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "userName": "john.doe@company.com",
  "name": {
    "familyName": "Doe",
    "givenName": "John"
  },
  "emails": [{
    "primary": true,
    "value": "john.doe@company.com",
    "type": "work"
  }],
  "active": true,
  "groups": [{
    "value": "employees",
    "display": "Employees"
  }]
}
```

### Update User (SCIM)
```http
PATCH /v1/scim/v2/Users/{userId}
Authorization: Bearer SCIM_TOKEN
Content-Type: application/scim+json

{
  "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
  "Operations": [{
    "op": "replace",
    "path": "active",
    "value": false
  }]
}
```

### Group Management (SCIM)
```http
POST /v1/scim/v2/Groups
Authorization: Bearer SCIM_TOKEN
Content-Type: application/scim+json

{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
  "displayName": "Engineering Team",
  "members": [{
    "value": "usr_1234567890",
    "display": "John Doe"
  }]
}
```

## 🔗 Webhooks

### Create Webhook
```http
POST /v1/webhooks
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "url": "https://app.example.com/webhooks/janua",
  "events": [
    "user.created",
    "user.updated",
    "user.deleted",
    "user.signin",
    "user.signout",
    "organization.member_added",
    "organization.member_removed",
    "organization.member_role_changed",
    "session.created",
    "session.expired",
    "mfa.enabled",
    "mfa.disabled"
  ],
  "secret": "your-webhook-secret",
  "active": true,
  "description": "Production webhook for user events"
}
```

### Webhook Event Format
```json
{
  "id": "evt_1234567890",
  "eventType": "user.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "organizationId": "org_1234567890",
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@company.com",
      "firstName": "John",
      "lastName": "Doe",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  },
  "previousData": null // for update events
}
```

### Verify Webhook Signature
```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)
```

## 📊 Analytics & Audit Logs

### Get User Analytics
```http
GET /v1/analytics/users/{userId}?startDate=2024-01-01&endDate=2024-01-31&granularity=day
Authorization: Bearer ACCESS_TOKEN
```

**Response**:
```json
{
  "user": {
    "id": "usr_1234567890",
    "email": "user@company.com"
  },
  "period": {
    "startDate": "2024-01-01T00:00:00Z",
    "endDate": "2024-01-31T23:59:59Z"
  },
  "metrics": {
    "totalSessions": 45,
    "totalSignIns": 42,
    "averageSessionDuration": 3600,
    "devicesUsed": ["Chrome/Win", "Safari/Mac", "Mobile/iOS"],
    "ipAddresses": ["192.168.1.100", "10.0.0.50"],
    "locations": ["New York, NY", "San Francisco, CA"]
  },
  "timeline": [
    {
      "date": "2024-01-01",
      "sessions": 2,
      "signIns": 2,
      "duration": 7200
    }
  ]
}
```

### Get Audit Logs
```http
GET /v1/audit-logs?page=1&limit=50&eventType=user.signin&userId=usr_1234567890&startDate=2024-01-01
Authorization: Bearer ADMIN_ACCESS_TOKEN
```

**Response**:
```json
{
  "logs": [
    {
      "id": "log_1234567890",
      "eventType": "user.signin",
      "timestamp": "2024-01-15T10:30:00Z",
      "userId": "usr_1234567890",
      "organizationId": "org_1234567890",
      "ipAddress": "192.168.1.100",
      "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "location": {
        "country": "US",
        "region": "California",
        "city": "San Francisco"
      },
      "details": {
        "method": "email_password",
        "success": true,
        "mfaRequired": false
      },
      "risk": {
        "score": 15,
        "factors": ["unusual_location"]
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1250,
    "pages": 25
  }
}
```

## 🚨 Security & Rate Limiting

### Rate Limit Headers
All API responses include rate limit information:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642262400
X-RateLimit-Window: 3600
```

### Rate Limit Response
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retryAfter": 60,
  "limit": 1000,
  "remaining": 0,
  "resetTime": "2024-01-15T11:00:00Z"
}
```

### Security Headers
```http
GET /v1/auth/me
Authorization: Bearer ACCESS_TOKEN
X-Request-ID: req_1234567890
X-Forwarded-For: 192.168.1.100
User-Agent: MyApp/1.0
```

## 🔧 Admin API

### System Health
```http
GET /v1/admin/health
Authorization: Bearer ADMIN_ACCESS_TOKEN
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.2.3",
  "checks": {
    "database": {
      "status": "healthy",
      "responseTime": 15,
      "connections": {
        "active": 45,
        "idle": 15,
        "max": 100
      }
    },
    "redis": {
      "status": "healthy",
      "responseTime": 2,
      "memory": {
        "used": "256MB",
        "max": "1GB",
        "percentage": 25
      }
    },
    "external_services": {
      "email_service": "healthy",
      "sms_service": "healthy",
      "webhook_delivery": "healthy"
    }
  },
  "metrics": {
    "requests_per_second": 125,
    "active_sessions": 1500,
    "cpu_usage": 45,
    "memory_usage": 67
  }
}
```

### System Metrics
```http
GET /v1/admin/metrics?metric=active_users&period=24h&granularity=hour
Authorization: Bearer ADMIN_ACCESS_TOKEN
```

### Manage Users (Admin)
```http
POST /v1/admin/users/{userId}/suspend
Authorization: Bearer ADMIN_ACCESS_TOKEN
Content-Type: application/json

{
  "reason": "Suspicious activity detected",
  "duration": 86400 // 24 hours in seconds
}
```

```http
POST /v1/admin/users/{userId}/unlock
Authorization: Bearer ADMIN_ACCESS_TOKEN
```

## 📱 Mobile & IoT APIs

### Device Registration
```http
POST /v1/devices
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "deviceId": "mobile_device_12345",
  "deviceType": "mobile",
  "platform": "ios",
  "platformVersion": "17.1",
  "appVersion": "1.2.3",
  "pushToken": "fcm_or_apns_token",
  "biometricCapabilities": ["face_id", "touch_id"]
}
```

### Push Notifications
```http
POST /v1/notifications/push
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "deviceId": "mobile_device_12345",
  "title": "Security Alert",
  "body": "New sign-in from unknown device",
  "data": {
    "type": "security_alert",
    "sessionId": "sess_1234567890"
  }
}
```

## 🌐 GraphQL API

### GraphQL Endpoint
```http
POST /v1/graphql
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json

{
  "query": "query GetUser($id: ID!) { user(id: $id) { id email firstName lastName organizations { id name role } } }",
  "variables": {
    "id": "usr_1234567890"
  }
}
```

### Sample Queries

#### Get User with Organizations
```graphql
query GetUserWithOrganizations($userId: ID!) {
  user(id: $userId) {
    id
    email
    firstName
    lastName
    profileImageUrl
    organizations {
      id
      name
      role
      permissions
    }
    sessions {
      id
      deviceInfo
      location
      lastActiveAt
    }
  }
}
```

#### Get Organization with Members
```graphql
query GetOrganizationWithMembers($orgId: ID!, $limit: Int = 50) {
  organization(id: $orgId) {
    id
    name
    description
    memberCount
    members(limit: $limit) {
      user {
        id
        email
        firstName
        lastName
      }
      role
      joinedAt
    }
    ssoConfiguration {
      provider
      enabled
      domains
    }
  }
}
```

#### Create User Mutation
```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    user {
      id
      email
      firstName
      lastName
    }
    success
    errors {
      field
      message
    }
  }
}
```

## 📈 WebSocket Real-time API

### Connection
```javascript
const ws = new WebSocket('wss://api.janua.dev/v1/ws?token=ACCESS_TOKEN');

ws.onopen = function() {
  // Subscribe to user events
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'user.events',
    userId: 'usr_1234567890'
  }));
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};
```

### Real-time Events
```json
{
  "type": "event",
  "channel": "user.events",
  "event": "session.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "sessionId": "sess_1234567890",
    "deviceInfo": "Chrome/Mac",
    "location": "San Francisco, CA"
  }
}
```

## 🚀 API SDKs & Code Examples

### JavaScript/TypeScript
```javascript
import { JanuaClient } from '@janua/typescript-sdk';

const janua = new JanuaClient({
  baseURL: 'https://api.janua.dev',
  apiKey: 'your-api-key'
});

// Authenticate user
const result = await janua.auth.signIn({
  email: 'user@company.com',
  password: 'password'
});

// Get current user
const user = await janua.auth.getCurrentUser();

// Create organization
const org = await janua.organizations.create({
  name: 'My Company',
  slug: 'my-company'
});
```

### Python
```python
from janua import JanuaClient

janua = JanuaClient(
    api_key="your-api-key",
    base_url="https://api.janua.dev"
)

# Authenticate user
result = await janua.auth.sign_in(
    email="user@company.com",
    password="password"
)

# Get current user
user = await janua.auth.get_current_user()

# Create organization
org = await janua.organizations.create(
    name="My Company",
    slug="my-company"
)
```

### Go
```go
package main

import (
    "context"
    "github.com/madfam-org/go-sdk"
)

func main() {
    client := janua.NewClient(&janua.Config{
        APIKey:  "your-api-key",
        BaseURL: "https://api.janua.dev",
    })

    // Authenticate user
    result, err := client.Auth.SignIn(context.Background(), &janua.SignInRequest{
        Email:    "user@company.com",
        Password: "password",
    })

    // Get current user
    user, err := client.Auth.GetCurrentUser(context.Background())

    // Create organization
    org, err := client.Organizations.Create(context.Background(), &janua.CreateOrgRequest{
        Name: "My Company",
        Slug: "my-company",
    })
}
```

## 🚨 Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password",
    "details": {
      "field": "password",
      "reason": "incorrect_password",
      "attempts_remaining": 4
    },
    "requestId": "req_1234567890",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes
- `INVALID_CREDENTIALS`: Invalid email or password
- `ACCOUNT_LOCKED`: Account locked due to too many failed attempts
- `MFA_REQUIRED`: Multi-factor authentication required
- `EMAIL_NOT_VERIFIED`: Email verification required
- `RATE_LIMITED`: Too many requests
- `INSUFFICIENT_PERMISSIONS`: User lacks required permissions
- `ORGANIZATION_NOT_FOUND`: Organization does not exist
- `USER_NOT_FOUND`: User does not exist
- `INVALID_TOKEN`: Access token is invalid or expired
- `WEBHOOK_DELIVERY_FAILED`: Webhook delivery failed

## 📚 Additional Resources

### Postman Collection
Import our comprehensive Postman collection:
```
https://api.janua.dev/postman/collection.json
```

### OpenAPI Specification
Download the complete OpenAPI 3.0 specification:
```
https://api.janua.dev/openapi.json
```

### Interactive API Explorer
Test APIs directly in your browser:
```
https://docs.janua.dev/api-explorer
```

### SDK Documentation
- [TypeScript SDK](https://docs.janua.dev/sdks/typescript)
- [Python SDK](https://docs.janua.dev/sdks/python)
- [Go SDK](https://docs.janua.dev/sdks/go)
- [React SDK](https://docs.janua.dev/sdks/react)
- [Vue SDK](https://docs.janua.dev/sdks/vue)
- [Flutter SDK](https://docs.janua.dev/sdks/flutter)

### Support
- **API Support**: [api-support@janua.dev](mailto:api-support@janua.dev)
- **Discord Community**: [https://discord.gg/janua](https://discord.gg/janua)
- **GitHub Issues**: [https://github.com/madfam-org/api-issues](https://github.com/madfam-org/api-issues)

---

*This documentation is automatically updated with each API release. Last updated: January 15, 2025*