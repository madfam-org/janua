# API Endpoints Reference

Comprehensive reference for all Janua API endpoints.

**Base URL**: `https://api.janua.dev` (or your self-hosted instance)
**Current Version**: v1
**Total Endpoints**: 202

## Authentication

All authenticated endpoints require a Bearer token in the Authorization header:

```http
Authorization: Bearer {access_token}
```

## Core Authentication

### Auth Router (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/signup` | Create new user account | No |
| POST | `/signin` | Sign in with email/password | No |
| POST | `/signout` | Sign out current session | Yes |
| POST | `/refresh` | Refresh access token | No |
| POST | `/forgot-password` | Request password reset | No |
| POST | `/reset-password` | Reset password with token | No |
| POST | `/verify-email` | Verify email address | No |
| POST | `/resend-verification` | Resend verification email | No |
| GET | `/me` | Get current user profile | Yes |

### OAuth Router (`/api/v1/oauth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/{provider}/authorize` | Initiate OAuth flow | No |
| GET | `/{provider}/callback` | OAuth callback handler | No |
| POST | `/{provider}/link` | Link OAuth provider to account | Yes |
| DELETE | `/{provider}/unlink` | Unlink OAuth provider | Yes |

**Supported Providers**: Google, GitHub, Microsoft, Discord, Twitter

### Magic Links Router (`/api/v1/auth/magic`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/send` | Send magic link email | No |
| GET | `/verify` | Verify magic link token | No |

## User Management

### Users Router (`/api/v1/users`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List users (admin) | Yes (Admin) |
| GET | `/{user_id}` | Get user by ID | Yes |
| PUT | `/{user_id}` | Update user profile | Yes |
| DELETE | `/{user_id}` | Delete user account | Yes |
| GET | `/{user_id}/sessions` | List user sessions | Yes |
| GET | `/{user_id}/organizations` | Get user's organizations | Yes |
| POST | `/{user_id}/change-password` | Change password | Yes |

### Sessions Router (`/api/v1/sessions`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List active sessions | Yes |
| GET | `/{session_id}` | Get session details | Yes |
| DELETE | `/{session_id}` | Revoke specific session | Yes |
| DELETE | `/all` | Revoke all sessions | Yes |

## Multi-Factor Authentication

### MFA Router (`/api/v1/mfa`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/totp/generate` | Generate TOTP secret | Yes |
| POST | `/totp/verify` | Verify and enable TOTP | Yes |
| DELETE | `/totp/disable` | Disable TOTP | Yes |
| POST | `/totp/verify-code` | Verify TOTP code | Yes |
| GET | `/backup-codes` | Get backup codes | Yes |
| POST | `/backup-codes/regenerate` | Regenerate backup codes | Yes |
| POST | `/backup-codes/verify` | Use backup code | Yes |
| GET | `/status` | Get MFA status | Yes |

### Passkeys Router (`/api/v1/passkeys`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/register/begin` | Start passkey registration | Yes |
| POST | `/register/complete` | Complete passkey registration | Yes |
| POST | `/authenticate/begin` | Start passkey authentication | No |
| POST | `/authenticate/complete` | Complete passkey authentication | No |
| GET | `/` | List user's passkeys | Yes |
| DELETE | `/{passkey_id}` | Remove passkey | Yes |

## Organization Management

### Organizations Router (`/api/v1/organizations`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List user's organizations | Yes |
| POST | `/` | Create organization | Yes |
| GET | `/{org_id}` | Get organization details | Yes |
| PUT | `/{org_id}` | Update organization | Yes |
| DELETE | `/{org_id}` | Delete organization | Yes |
| GET | `/{org_id}/members` | List organization members | Yes |
| POST | `/{org_id}/members` | Add member | Yes |
| DELETE | `/{org_id}/members/{user_id}` | Remove member | Yes |
| PUT | `/{org_id}/members/{user_id}/role` | Update member role | Yes |

### Invitations Router (`/api/invitations`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/organizations/{org_id}/invitations` | Create invitation | Yes |
| GET | `/organizations/{org_id}/invitations` | List invitations | Yes |
| GET | `/invitations/{invite_id}` | Get invitation details | No |
| POST | `/invitations/{invite_id}/accept` | Accept invitation | Yes |
| DELETE | `/invitations/{invite_id}` | Revoke invitation | Yes |
| POST | `/invitations/{invite_id}/resend` | Resend invitation email | Yes |

## Access Control

### RBAC Router (`/api/v1/rbac`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/roles` | List available roles | Yes |
| POST | `/roles` | Create custom role | Yes (Admin) |
| GET | `/roles/{role_id}` | Get role details | Yes |
| PUT | `/roles/{role_id}` | Update role | Yes (Admin) |
| DELETE | `/roles/{role_id}` | Delete role | Yes (Admin) |
| POST | `/users/{user_id}/roles` | Assign role to user | Yes (Admin) |
| DELETE | `/users/{user_id}/roles/{role_id}` | Remove role from user | Yes (Admin) |
| GET | `/permissions` | List all permissions | Yes |

### Policies Router (`/api/policies`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List policies | Yes |
| POST | `/` | Create policy | Yes (Admin) |
| GET | `/{policy_id}` | Get policy details | Yes |
| PUT | `/{policy_id}` | Update policy | Yes (Admin) |
| DELETE | `/{policy_id}` | Delete policy | Yes (Admin) |
| POST | `/{policy_id}/evaluate` | Evaluate policy | Yes |

## Enterprise Features

### SSO Router (`/api/v1/sso`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/configurations` | List SSO configurations | Yes (Admin) |
| POST | `/configurations` | Create SSO configuration | Yes (Admin) |
| GET | `/configurations/{config_id}` | Get SSO configuration | Yes (Admin) |
| PUT | `/configurations/{config_id}` | Update SSO configuration | Yes (Admin) |
| DELETE | `/configurations/{config_id}` | Delete SSO configuration | Yes (Admin) |
| POST | `/saml/acs` | SAML Assertion Consumer Service | No |
| POST | `/saml/slo` | SAML Single Logout | No |
| POST | `/oidc/callback` | OIDC callback handler | No |

### SCIM 2.0 Router (`/api/v1/scim`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/Users` | List users (SCIM format) | Yes (SCIM Token) |
| POST | `/Users` | Create user (SCIM format) | Yes (SCIM Token) |
| GET | `/Users/{user_id}` | Get user (SCIM format) | Yes (SCIM Token) |
| PUT | `/Users/{user_id}` | Update user (SCIM format) | Yes (SCIM Token) |
| PATCH | `/Users/{user_id}` | Patch user (SCIM format) | Yes (SCIM Token) |
| DELETE | `/Users/{user_id}` | Deactivate user | Yes (SCIM Token) |
| GET | `/Groups` | List groups (SCIM format) | Yes (SCIM Token) |
| POST | `/Groups` | Create group (SCIM format) | Yes (SCIM Token) |
| GET | `/ServiceProviderConfig` | Get SCIM configuration | No |
| GET | `/Schemas` | Get SCIM schemas | No |

## Webhooks

### Webhooks Router (`/api/v1/webhooks`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List webhooks | Yes |
| POST | `/` | Create webhook | Yes |
| GET | `/{webhook_id}` | Get webhook details | Yes |
| PUT | `/{webhook_id}` | Update webhook | Yes |
| DELETE | `/{webhook_id}` | Delete webhook | Yes |
| POST | `/{webhook_id}/test` | Send test event | Yes |
| GET | `/{webhook_id}/deliveries` | List delivery attempts | Yes |
| POST | `/{webhook_id}/deliveries/{delivery_id}/redeliver` | Retry delivery | Yes |

## Audit & Compliance

### Audit Logs Router (`/api/audit-logs`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List audit logs | Yes (Admin) |
| GET | `/{log_id}` | Get audit log details | Yes (Admin) |
| GET | `/events` | List event types | Yes (Admin) |
| GET | `/users/{user_id}` | Get user's audit logs | Yes (Admin) |
| GET | `/organizations/{org_id}` | Get org's audit logs | Yes (Admin) |
| POST | `/export` | Export audit logs | Yes (Admin) |

### Compliance Router (`/api/v1/compliance`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/frameworks` | List compliance frameworks | Yes (Admin) |
| GET | `/controls` | List compliance controls | Yes (Admin) |
| GET | `/reports` | List compliance reports | Yes (Admin) |
| POST | `/reports` | Generate compliance report | Yes (Admin) |
| GET | `/privacy/data-subject-requests` | List DSR requests | Yes (Admin) |
| POST | `/privacy/data-subject-requests` | Create DSR | Yes |
| POST | `/privacy/data-export` | Export user data | Yes |
| POST | `/privacy/data-deletion` | Request data deletion | Yes |

## Localization

### Localization Router (`/api/v1/localization`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/locales` | List available locales | No |
| POST | `/translations` | Create/update translation | Yes (Admin) |
| GET | `/translations/{locale_code}` | Get translations for locale | No |
| GET | `/translation-keys` | List translation keys | Yes (Admin) |
| POST | `/translation-keys` | Create translation key | Yes (Admin) |

## Real-time Features

### WebSocket Router (`/api/v1/websocket`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| WS | `/ws` | WebSocket connection endpoint | Yes (via query param) |

**Events**: `user.updated`, `session.expired`, `organization.updated`, `notification.created`

## Monitoring & Health

### Health Router (`/api/v1/health`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | Basic health check | No |
| GET | `/detailed` | Detailed health status | Yes (Admin) |
| GET | `/ready` | Readiness probe | No |
| GET | `/live` | Liveness probe | No |

### Admin Router (`/api/v1/admin`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/stats` | Get system statistics | Yes (Admin) |
| GET | `/users` | List all users | Yes (Admin) |
| POST | `/users/{user_id}/suspend` | Suspend user account | Yes (Admin) |
| POST | `/users/{user_id}/unsuspend` | Unsuspend user account | Yes (Admin) |
| DELETE | `/users/{user_id}/force-delete` | Force delete user | Yes (Admin) |
| POST | `/cache/clear` | Clear Redis cache | Yes (Admin) |

## Rate Limiting

All endpoints are rate-limited based on user/IP:

- **Anonymous**: 100 requests/minute
- **Authenticated**: 1000 requests/minute
- **Admin**: 5000 requests/minute

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1705234567
```

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect",
    "details": {
      "field": "email"
    }
  }
}
```

Common error codes:
- `INVALID_CREDENTIALS` - Authentication failed
- `UNAUTHORIZED` - No valid token provided
- `FORBIDDEN` - Insufficient permissions
- `NOT_FOUND` - Resource not found
- `VALIDATION_ERROR` - Input validation failed
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server error

## SDK Support

Official SDKs available for:
- **TypeScript/JavaScript**: `@janua/typescript-sdk`
- **React**: `@janua/react-sdk`
- **Python**: `janua`
- **Vue**: `@janua/vue-sdk`
- **Next.js**: `@janua/nextjs-sdk`
- **Go**: `github.com/madfam-io/go-sdk`
- **Flutter**: `janua_flutter`

## Related Documentation

- [API Overview](/docs/api/README.md)
- [Authentication Guide](/docs/api/authentication.md)
- [Localization Guide](/docs/api/localization.md)
- [SDK Documentation](/docs/development/sdks.md)
