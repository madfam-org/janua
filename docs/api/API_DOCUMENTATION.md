# Plinto API Documentation

**Version**: 1.0.0
**Base URL**: `https://api.plinto.dev` (Production) | `http://localhost:8000` (Development)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Authentication](#authentication)
4. [Rate Limiting](#rate-limiting)
5. [Error Handling](#error-handling)
6. [Core Endpoints](#core-endpoints)
7. [Code Examples](#code-examples)
8. [SDK Integration](#sdk-integration)
9. [Webhooks](#webhooks)
10. [Security Best Practices](#security-best-practices)

---

## Introduction

Plinto is a modern, open-core authentication platform that provides enterprise-grade identity management at 4x lower cost than competitors like Clerk ($0.005/MAU vs $0.02/MAU).

### Key Features

- 🔐 **Complete Authentication**: Email/password, OAuth, Magic Links, Passkeys
- 🛡️ **Multi-Factor Authentication**: TOTP, SMS, Backup codes
- 👥 **Multi-Tenancy**: Organizations with RBAC and team management
- 🔄 **Session Management**: Multi-device tracking and revocation
- 🎯 **Enterprise Features**: SAML/SSO, SCIM, Compliance (GDPR, SOC 2)
- 📊 **Developer Experience**: TypeScript SDK, React UI components

### Interactive Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Quick Start

### 1. Create an Account

```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "developer@example.com",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Developer"
  }'
```

**Response**:
```json
{
  "user": {
    "id": "usr_1234567890abcdef",
    "email": "developer@example.com",
    "email_verified": false,
    "first_name": "John",
    "last_name": "Developer",
    "created_at": "2025-11-16T10:30:00Z"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 2. Sign In

```bash
curl -X POST http://localhost:8000/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{
    "email": "developer@example.com",
    "password": "SecurePass123!"
  }'
```

### 3. Access Protected Endpoints

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Authentication

All protected endpoints require a JWT access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Token Lifecycle

1. **Access Token**: Short-lived (1 hour), used for API requests
2. **Refresh Token**: Long-lived (30 days), used to get new access tokens

### Getting Tokens

**Email/Password**:
```http
POST /api/v1/auth/signin
```

**OAuth (Google, GitHub, Microsoft, Apple)**:
```http
POST /api/v1/oauth/{provider}/callback
```

**Magic Link**:
```http
POST /api/v1/auth/magic-link/verify
```

**Passkeys (WebAuthn)**:
```http
POST /api/v1/passkeys/verify
```

### Refreshing Tokens

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Rate Limiting

All endpoints are protected by rate limiting to prevent abuse.

### Limits by Endpoint Type

| Endpoint Type | Rate Limit |
|--------------|------------|
| Sign Up | 3 requests/minute |
| Sign In | 5 requests/minute |
| Password Reset | 3 requests/hour |
| Email Verification | 5 requests/hour |
| Magic Link | 5 requests/hour |
| General Endpoints | 100 requests/minute |

### Rate Limit Headers

Every response includes rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1700150400
```

### Exceeding Rate Limits

**Response (429 Too Many Requests)**:
```json
{
  "detail": "Rate limit exceeded. Try again in 42 seconds.",
  "retry_after": 42
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-11-16T10:30:00Z",
  "path": "/api/v1/auth/signin"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request completed successfully |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid input, validation errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists (e.g., email) |
| 422 | Validation Error | Request body failed validation |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |

### Common Error Scenarios

**Invalid Credentials**:
```json
{
  "detail": "Invalid credentials",
  "status_code": 401
}
```

**Email Already Registered**:
```json
{
  "detail": "Email already registered",
  "status_code": 400
}
```

**Weak Password**:
```json
{
  "detail": "Password must be at least 8 characters and include uppercase, lowercase, number, and special character",
  "status_code": 400
}
```

---

## Core Endpoints

### Authentication (`/api/v1/auth`)

#### Sign Up

```http
POST /api/v1/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe" // optional
}
```

#### Sign In

```http
POST /api/v1/auth/signin
Content-Type: application/json

{
  "email": "user@example.com",  // or "username": "johndoe"
  "password": "SecurePass123!"
}
```

#### Sign Out

```http
POST /api/v1/auth/signout
Authorization: Bearer {access_token}
```

#### Get Current User

```http
GET /api/v1/auth/me
Authorization: Bearer {access_token}
```

#### Change Password

```http
POST /api/v1/auth/password/change
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "current_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

#### Forgot Password

```http
POST /api/v1/auth/password/forgot
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### Reset Password

```http
POST /api/v1/auth/password/reset
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "new_password": "NewPass456!"
}
```

#### Verify Email

```http
POST /api/v1/auth/email/verify
Content-Type: application/json

{
  "token": "verification_token_from_email"
}
```

### Sessions (`/api/v1/sessions`)

#### List Active Sessions

```http
GET /api/v1/sessions
Authorization: Bearer {access_token}
```

**Response**:
```json
{
  "sessions": [
    {
      "id": "sess_1234567890",
      "device": {
        "type": "desktop",
        "name": "Chrome on macOS",
        "os": "macOS",
        "browser": "Chrome"
      },
      "location": {
        "city": "San Francisco",
        "country": "United States",
        "ip": "192.168.1.1"
      },
      "created_at": "2025-11-16T10:00:00Z",
      "last_active_at": "2025-11-16T10:30:00Z",
      "is_current": true
    }
  ],
  "total": 1
}
```

#### Get Current Session

```http
GET /api/v1/sessions/current
Authorization: Bearer {access_token}
```

#### Revoke Session

```http
DELETE /api/v1/sessions/{session_id}
Authorization: Bearer {access_token}
```

#### Revoke All Other Sessions

```http
POST /api/v1/sessions/revoke-all
Authorization: Bearer {access_token}
```

### Organizations (`/api/v1/organizations`)

#### Create Organization

```http
POST /api/v1/organizations
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "description": "Software company"
}
```

#### List Organizations

```http
GET /api/v1/organizations
Authorization: Bearer {access_token}
```

#### Get Organization

```http
GET /api/v1/organizations/{org_id}
Authorization: Bearer {access_token}
```

#### Update Organization

```http
PUT /api/v1/organizations/{org_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Acme Inc.",
  "description": "Updated description"
}
```

#### Delete Organization

```http
DELETE /api/v1/organizations/{org_id}
Authorization: Bearer {access_token}
```

#### List Organization Members

```http
GET /api/v1/organizations/{org_id}/members
Authorization: Bearer {access_token}
```

#### Invite Member

```http
POST /api/v1/organizations/{org_id}/members/invite
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "email": "newmember@example.com",
  "role": "member"  // "owner", "admin", or "member"
}
```

#### Update Member Role

```http
PUT /api/v1/organizations/{org_id}/members/{user_id}/role
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "role": "admin"
}
```

#### Remove Member

```http
DELETE /api/v1/organizations/{org_id}/members/{member_id}
Authorization: Bearer {access_token}
```

### MFA (`/api/v1/mfa`)

#### Enable TOTP

```http
POST /api/v1/mfa/totp/enable
Authorization: Bearer {access_token}
```

**Response**:
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,iVBORw0KG...",
  "backup_codes": [
    "1234-5678",
    "9012-3456",
    "5678-9012"
  ]
}
```

#### Verify TOTP

```http
POST /api/v1/mfa/totp/verify
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "code": "123456"
}
```

#### Disable TOTP

```http
POST /api/v1/mfa/totp/disable
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "code": "123456"
}
```

### Users (`/api/v1/users`)

#### Update Profile

```http
PATCH /api/v1/users/me
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "first_name": "Jane",
  "last_name": "Smith",
  "profile_image_url": "https://example.com/avatar.jpg"
}
```

#### Delete Account

```http
DELETE /api/v1/users/me
Authorization: Bearer {access_token}
```

---

## Code Examples

### JavaScript/TypeScript

#### Using Fetch API

```typescript
// Sign Up
const signUp = async (email: string, password: string) => {
  const response = await fetch('http://localhost:8000/api/v1/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })

  if (!response.ok) {
    throw new Error('Sign up failed')
  }

  const data = await response.json()
  return data
}

// Sign In
const signIn = async (email: string, password: string) => {
  const response = await fetch('http://localhost:8000/api/v1/auth/signin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })

  if (!response.ok) {
    throw new Error('Sign in failed')
  }

  const data = await response.json()
  localStorage.setItem('access_token', data.tokens.access_token)
  localStorage.setItem('refresh_token', data.tokens.refresh_token)
  return data
}

// Get Current User
const getCurrentUser = async () => {
  const token = localStorage.getItem('access_token')

  const response = await fetch('http://localhost:8000/api/v1/auth/me', {
    headers: { 'Authorization': `Bearer ${token}` }
  })

  if (!response.ok) {
    throw new Error('Failed to get user')
  }

  return await response.json()
}

// Refresh Token
const refreshToken = async () => {
  const refreshToken = localStorage.getItem('refresh_token')

  const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  })

  if (!response.ok) {
    throw new Error('Token refresh failed')
  }

  const data = await response.json()
  localStorage.setItem('access_token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)
  return data
}
```

#### Using Axios

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' }
})

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('refresh_token')
      const { data } = await axios.post('/auth/refresh', { refresh_token: refreshToken })

      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)

      originalRequest.headers.Authorization = `Bearer ${data.access_token}`
      return api(originalRequest)
    }

    return Promise.reject(error)
  }
)

// Usage
const user = await api.get('/auth/me')
const sessions = await api.get('/sessions')
```

### Python

```python
import requests
from typing import Dict, Any

class PlintoClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None

    def sign_up(self, email: str, password: str, **kwargs) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/v1/auth/signup",
            json={"email": email, "password": password, **kwargs}
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data['tokens']['access_token']
        self.refresh_token = data['tokens']['refresh_token']

        return data

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/v1/auth/signin",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data['tokens']['access_token']
        self.refresh_token = data['tokens']['refresh_token']

        return data

    def get_current_user(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        response.raise_for_status()
        return response.json()

    def list_sessions(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/v1/sessions",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = PlintoClient()
client.sign_up("user@example.com", "SecurePass123!")
user = client.get_current_user()
sessions = client.list_sessions()
```

### cURL Examples

```bash
# Sign Up
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'

# Sign In
curl -X POST http://localhost:8000/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'

# Get Current User
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# List Sessions
curl -X GET http://localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Create Organization
curl -X POST http://localhost:8000/api/v1/organizations \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","slug":"acme-corp"}'
```

---

## SDK Integration

### TypeScript SDK

```bash
npm install @plinto/typescript-sdk
```

```typescript
import { PlintoClient } from '@plinto/typescript-sdk'

const plinto = new PlintoClient({
  apiUrl: 'http://localhost:8000',
  clientId: 'your_client_id',
  clientSecret: 'your_client_secret'
})

// Sign up
const { user, tokens } = await plinto.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePass123!'
})

// Sign in
const { user, tokens } = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'SecurePass123!'
})

// Get current user
const user = await plinto.auth.getCurrentUser()

// List sessions
const sessions = await plinto.sessions.listSessions()

// Create organization
const org = await plinto.organizations.createOrganization({
  name: 'Acme Corp',
  slug: 'acme-corp'
})
```

### React UI Components

```bash
npm install @plinto/ui @plinto/typescript-sdk
```

```tsx
import { PlintoProvider, SignIn, SignUp, UserButton } from '@plinto/ui'
import { plintoClient } from './lib/plinto-client'

function App() {
  return (
    <PlintoProvider client={plintoClient}>
      <SignIn redirectUrl="/dashboard" />
      <SignUp redirectUrl="/dashboard" />
      <UserButton />
    </PlintoProvider>
  )
}
```

---

## Webhooks

### Supported Events

- `user.created` - New user registration
- `user.updated` - User profile update
- `user.deleted` - User account deletion
- `session.created` - New session created
- `session.revoked` - Session revoked
- `organization.created` - Organization created
- `organization.member.added` - Member added to organization
- `mfa.enabled` - MFA enabled for user
- `mfa.disabled` - MFA disabled for user

### Webhook Payload

```json
{
  "event": "user.created",
  "timestamp": "2025-11-16T10:30:00Z",
  "data": {
    "user": {
      "id": "usr_1234567890",
      "email": "user@example.com",
      "created_at": "2025-11-16T10:30:00Z"
    }
  }
}
```

### Verifying Webhook Signatures

```typescript
import crypto from 'crypto'

function verifyWebhookSignature(
  payload: string,
  signature: string,
  secret: string
): boolean {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex')

  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  )
}
```

---

## Security Best Practices

### 1. Secure Token Storage

**✅ DO**: Store tokens in httpOnly cookies or secure storage
```typescript
// Server-side
res.cookie('access_token', token, {
  httpOnly: true,
  secure: true,
  sameSite: 'strict'
})
```

**❌ DON'T**: Store tokens in localStorage for sensitive applications
```typescript
// Vulnerable to XSS attacks
localStorage.setItem('access_token', token)
```

### 2. Token Refresh

Implement automatic token refresh before expiration:

```typescript
setInterval(async () => {
  const expiresAt = localStorage.getItem('token_expires_at')
  if (Date.now() > expiresAt - 300000) { // 5 minutes before expiry
    await refreshToken()
  }
}, 60000) // Check every minute
```

### 3. HTTPS Only

Always use HTTPS in production to prevent token interception:

```typescript
const plinto = new PlintoClient({
  apiUrl: 'https://api.plinto.dev', // HTTPS only
  enforceHttps: true
})
```

### 4. Rate Limit Handling

Implement exponential backoff for rate limit errors:

```typescript
async function fetchWithRetry(url: string, options: any, retries = 3) {
  try {
    const response = await fetch(url, options)

    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After')
      const delay = retryAfter ? parseInt(retryAfter) * 1000 : 1000 * Math.pow(2, 3 - retries)

      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, delay))
        return fetchWithRetry(url, options, retries - 1)
      }
    }

    return response
  } catch (error) {
    if (retries > 0) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      return fetchWithRetry(url, options, retries - 1)
    }
    throw error
  }
}
```

### 5. Input Validation

Always validate and sanitize user input on the client side:

```typescript
function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

function validatePassword(password: string): boolean {
  return password.length >= 8 &&
         /[A-Z]/.test(password) &&
         /[a-z]/.test(password) &&
         /[0-9]/.test(password) &&
         /[^A-Za-z0-9]/.test(password)
}
```

### 6. Logout on Sensitive Actions

Force re-authentication for sensitive operations:

```typescript
async function deleteSensitiveData() {
  // Require fresh authentication
  const isRecentAuth = checkAuthenticationAge() < 300000 // 5 minutes

  if (!isRecentAuth) {
    await reauthenticate()
  }

  await api.delete('/sensitive-data')
}
```

---

## Support & Resources

### Documentation
- **API Reference**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Developer Guides**: [https://docs.plinto.dev](https://docs.plinto.dev)
- **GitHub**: [https://github.com/plinto/plinto](https://github.com/plinto/plinto)

### Community
- **Discord**: [https://discord.gg/plinto](https://discord.gg/plinto)
- **GitHub Discussions**: [https://github.com/plinto/plinto/discussions](https://github.com/plinto/plinto/discussions)

### Support
- **Email**: support@plinto.dev
- **Enterprise Support**: enterprise@plinto.dev

---

**Last Updated**: November 16, 2025
**API Version**: 1.0.0
