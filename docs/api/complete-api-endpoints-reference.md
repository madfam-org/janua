# Complete API Endpoints Reference

> **Comprehensive documentation of all 256+ REST API endpoints in the Janua platform**

## Overview

This document provides a complete reference to all API endpoints available in the Janua authentication platform, organized by functional area. All endpoints are prefixed with `/api/v1` unless otherwise noted.

## 🔐 Authentication Endpoints

### Core Authentication
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/auth/signup` | User registration | ✅ |
| POST | `/auth/signin` | User login | ✅ |
| POST | `/auth/refresh` | Refresh access token | ✅ |
| POST | `/auth/logout` | User logout | ✅ |
| GET | `/auth/me` | Get current user | ✅ |
| POST | `/auth/verify-email` | Verify email address | ✅ |
| POST | `/auth/forgot-password` | Request password reset | ✅ |
| POST | `/auth/reset-password` | Reset password with token | ✅ |
| POST | `/auth/change-password` | Change password (authenticated) | ✅ |

### Magic Link Authentication
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/auth/magic-link` | Send magic link | ✅ |
| POST | `/auth/magic-link/verify` | Verify magic link token | ✅ |

### OAuth 2.0 Providers
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/oauth/providers` | List OAuth providers | ✅ |
| GET | `/oauth/{provider}/authorize` | OAuth authorization URL | ✅ |
| POST | `/oauth/{provider}/callback` | OAuth callback handler | ✅ |
| POST | `/oauth/{provider}/refresh` | Refresh OAuth token | ✅ |
| DELETE | `/oauth/{provider}/disconnect` | Disconnect OAuth account | ✅ |

**Supported OAuth Providers:**
- Google (`/oauth/google/*`)
- GitHub (`/oauth/github/*`)
- Microsoft (`/oauth/microsoft/*`)
- Discord (`/oauth/discord/*`)
- Apple (`/oauth/apple/*`)
- Facebook (`/oauth/facebook/*`)
- LinkedIn (`/oauth/linkedin/*`)

## 🔐 Multi-Factor Authentication (MFA)

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/mfa/status` | Get MFA status | ✅ |
| POST | `/mfa/enable` | Enable MFA/TOTP | ✅ |
| POST | `/mfa/verify` | Verify MFA setup | ✅ |
| POST | `/mfa/disable` | Disable MFA | ✅ |
| POST | `/mfa/validate-code` | Validate MFA code | ✅ |
| POST | `/mfa/regenerate-backup-codes` | Regenerate backup codes | ✅ |
| GET | `/mfa/recovery-options` | Get recovery options | ✅ |
| POST | `/mfa/initiate-recovery` | Initiate MFA recovery | ✅ |
| GET | `/mfa/supported-methods` | Get supported MFA methods | ✅ |

## 🔑 WebAuthn/Passkeys

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/passkeys` | List user passkeys | ✅ |
| POST | `/passkeys/register/options` | Get registration options | ✅ |
| POST | `/passkeys/register` | Register new passkey | ✅ |
| POST | `/passkeys/authenticate/options` | Get authentication options | ✅ |
| POST | `/passkeys/authenticate` | Authenticate with passkey | ✅ |
| DELETE | `/passkeys/{id}` | Delete passkey | ✅ |
| PUT | `/passkeys/{id}` | Update passkey name | ✅ |
| GET | `/passkeys/{id}` | Get passkey details | ✅ |

## 👥 User Management

### User Profile
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/users/me` | Get current user profile | ✅ |
| PUT | `/users/me` | Update current user profile | ✅ |
| DELETE | `/users/me` | Delete current user account | ✅ |
| POST | `/users/me/avatar` | Upload user avatar | ✅ |
| DELETE | `/users/me/avatar` | Delete user avatar | ✅ |

### User Preferences
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/users/me/preferences` | Get user preferences | ✅ |
| PUT | `/users/me/preferences` | Update user preferences | ✅ |
| GET | `/users/me/activity` | Get user activity log | ✅ |
| GET | `/users/me/sessions` | Get user sessions | ✅ |

### User Security
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/users/me/password` | Change password | ✅ |
| GET | `/users/me/security` | Get security settings | ✅ |
| POST | `/users/me/security/2fa` | Enable 2FA | ✅ |
| DELETE | `/users/me/security/2fa` | Disable 2FA | ✅ |

## 🏢 Organization Management

### Organization CRUD
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/organizations` | List user organizations | ✅ |
| POST | `/organizations` | Create organization | ✅ |
| GET | `/organizations/{id}` | Get organization details | ✅ |
| PUT | `/organizations/{id}` | Update organization | ✅ |
| DELETE | `/organizations/{id}` | Delete organization | ✅ |

### Organization Members
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/organizations/{id}/members` | List organization members | ✅ |
| POST | `/organizations/{id}/members` | Add organization member | ✅ |
| GET | `/organizations/{id}/members/{user_id}` | Get member details | ✅ |
| PUT | `/organizations/{id}/members/{user_id}` | Update member role | ✅ |
| DELETE | `/organizations/{id}/members/{user_id}` | Remove member | ✅ |

### Organization Invitations
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/organizations/{id}/invitations` | List pending invitations | ✅ |
| POST | `/organizations/{id}/invitations` | Send invitation | ✅ |
| DELETE | `/organizations/{id}/invitations/{invite_id}` | Cancel invitation | ✅ |
| POST | `/invitations/{token}/accept` | Accept invitation | ✅ |
| POST | `/invitations/{token}/decline` | Decline invitation | ✅ |

### Organization Settings
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/organizations/{id}/settings` | Get organization settings | ✅ |
| PUT | `/organizations/{id}/settings` | Update organization settings | ✅ |
| GET | `/organizations/{id}/branding` | Get organization branding | ✅ |
| PUT | `/organizations/{id}/branding` | Update organization branding | ✅ |

## 🎭 Roles & Permissions (RBAC)

### Role Management
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/organizations/{id}/roles` | List organization roles | ✅ |
| POST | `/organizations/{id}/roles` | Create custom role | ✅ |
| GET | `/organizations/{id}/roles/{role_id}` | Get role details | ✅ |
| PUT | `/organizations/{id}/roles/{role_id}` | Update role | ✅ |
| DELETE | `/organizations/{id}/roles/{role_id}` | Delete role | ✅ |

### Permission Management
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/organizations/{id}/permissions` | List available permissions | ✅ |
| GET | `/organizations/{id}/roles/{role_id}/permissions` | Get role permissions | ✅ |
| PUT | `/organizations/{id}/roles/{role_id}/permissions` | Update role permissions | ✅ |
| GET | `/organizations/{id}/members/{user_id}/permissions` | Get user effective permissions | ✅ |

## 🔗 Session Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/sessions` | List active sessions | ✅ |
| GET | `/sessions/{id}` | Get session details | ✅ |
| DELETE | `/sessions/{id}` | Terminate session | ✅ |
| POST | `/sessions/terminate-all` | Terminate all sessions | ✅ |
| POST | `/sessions/{id}/extend` | Extend session | ✅ |
| GET | `/sessions/current` | Get current session info | ✅ |

## 💼 Enterprise SSO

### SAML Configuration
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/sso/providers` | List SSO providers | ✅ |
| POST | `/sso/providers` | Create SSO provider | ✅ |
| GET | `/sso/providers/{id}` | Get SSO provider | ✅ |
| PUT | `/sso/providers/{id}` | Update SSO provider | ✅ |
| DELETE | `/sso/providers/{id}` | Delete SSO provider | ✅ |

### SAML Authentication
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/sso/saml/initiate` | Initiate SAML login | ✅ |
| POST | `/sso/saml/acs` | SAML assertion consumer | ✅ |
| GET | `/sso/saml/metadata` | Get SAML metadata | ✅ |
| POST | `/sso/saml/sls` | SAML single logout | ✅ |

### OIDC Integration
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/sso/oidc/.well-known/openid_configuration` | OIDC discovery | ✅ |
| POST | `/sso/oidc/token` | OIDC token exchange | ✅ |
| GET | `/sso/oidc/jwks` | OIDC JWKS endpoint | ✅ |
| GET | `/sso/oidc/userinfo` | OIDC user info | ✅ |

## 👨‍💼 SCIM 2.0 User Provisioning

### SCIM Users
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/scim/Users` | List SCIM users | ✅ |
| POST | `/scim/Users` | Create SCIM user | ✅ |
| GET | `/scim/Users/{id}` | Get SCIM user | ✅ |
| PUT | `/scim/Users/{id}` | Update SCIM user | ✅ |
| PATCH | `/scim/Users/{id}` | Patch SCIM user | ✅ |
| DELETE | `/scim/Users/{id}` | Delete SCIM user | ✅ |

### SCIM Groups
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/scim/Groups` | List SCIM groups | ✅ |
| POST | `/scim/Groups` | Create SCIM group | ✅ |
| GET | `/scim/Groups/{id}` | Get SCIM group | ✅ |
| PUT | `/scim/Groups/{id}` | Update SCIM group | ✅ |
| PATCH | `/scim/Groups/{id}` | Patch SCIM group | ✅ |
| DELETE | `/scim/Groups/{id}` | Delete SCIM group | ✅ |

### SCIM Schema & Meta
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/scim/Schemas` | Get SCIM schemas | ✅ |
| GET | `/scim/ResourceTypes` | Get SCIM resource types | ✅ |
| GET | `/scim/ServiceProviderConfig` | Get SCIM config | ✅ |

## 🔔 Webhook Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/webhooks` | List webhooks | ✅ |
| POST | `/webhooks` | Create webhook | ✅ |
| GET | `/webhooks/{id}` | Get webhook details | ✅ |
| PUT | `/webhooks/{id}` | Update webhook | ✅ |
| DELETE | `/webhooks/{id}` | Delete webhook | ✅ |
| POST | `/webhooks/{id}/test` | Test webhook | ✅ |
| GET | `/webhooks/{id}/deliveries` | Get webhook deliveries | ✅ |
| POST | `/webhooks/{id}/deliveries/{delivery_id}/redeliver` | Redeliver webhook | ✅ |

### Webhook Events
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/webhooks/events` | List available events | ✅ |
| GET | `/webhooks/events/{event}/schema` | Get event schema | ✅ |

## 🛡️ Audit & Compliance

### Audit Logs
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/audit-logs` | List audit logs | ✅ |
| GET | `/audit-logs/{id}` | Get audit log details | ✅ |
| POST | `/audit-logs/export` | Export audit logs | ✅ |
| GET | `/audit-logs/summary` | Get audit summary | ✅ |

### Compliance Reports
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/compliance/reports` | List compliance reports | ✅ |
| POST | `/compliance/reports` | Generate compliance report | ✅ |
| GET | `/compliance/reports/{id}` | Get compliance report | ✅ |
| GET | `/compliance/frameworks` | List compliance frameworks | ✅ |

### Policy Management
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/policies` | List security policies | ✅ |
| POST | `/policies` | Create security policy | ✅ |
| GET | `/policies/{id}` | Get policy details | ✅ |
| PUT | `/policies/{id}` | Update policy | ✅ |
| DELETE | `/policies/{id}` | Delete policy | ✅ |
| POST | `/policies/{id}/enforce` | Enforce policy | ✅ |

## 👨‍💻 Admin & Management

### User Administration
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/admin/users` | List all users | ✅ |
| POST | `/admin/users` | Create user (admin) | ✅ |
| GET | `/admin/users/{id}` | Get user details | ✅ |
| PUT | `/admin/users/{id}` | Update user | ✅ |
| DELETE | `/admin/users/{id}` | Delete user | ✅ |
| POST | `/admin/users/{id}/suspend` | Suspend user | ✅ |
| POST | `/admin/users/{id}/unsuspend` | Unsuspend user | ✅ |
| POST | `/admin/users/{id}/reset-password` | Admin reset password | ✅ |

### Organization Administration
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/admin/organizations` | List all organizations | ✅ |
| GET | `/admin/organizations/{id}` | Get organization details | ✅ |
| PUT | `/admin/organizations/{id}` | Update organization | ✅ |
| POST | `/admin/organizations/{id}/suspend` | Suspend organization | ✅ |
| POST | `/admin/organizations/{id}/unsuspend` | Unsuspend organization | ✅ |

### System Administration
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/admin/stats` | Get platform statistics | ✅ |
| GET | `/admin/activity` | Get platform activity | ✅ |
| POST | `/admin/maintenance` | Set maintenance mode | ✅ |
| GET | `/admin/logs` | Get system logs | ✅ |
| POST | `/admin/cache/clear` | Clear system cache | ✅ |

## 🎨 White-Label & Branding

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/white-label/themes` | List available themes | ✅ |
| POST | `/white-label/themes` | Create custom theme | ✅ |
| GET | `/white-label/themes/{id}` | Get theme details | ✅ |
| PUT | `/white-label/themes/{id}` | Update theme | ✅ |
| DELETE | `/white-label/themes/{id}` | Delete theme | ✅ |
| POST | `/white-label/themes/{id}/preview` | Preview theme | ✅ |
| POST | `/white-label/themes/{id}/deploy` | Deploy theme | ✅ |

### Custom Domains
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/white-label/domains` | List custom domains | ✅ |
| POST | `/white-label/domains` | Add custom domain | ✅ |
| GET | `/white-label/domains/{id}` | Get domain details | ✅ |
| PUT | `/white-label/domains/{id}` | Update domain | ✅ |
| DELETE | `/white-label/domains/{id}` | Delete domain | ✅ |
| POST | `/white-label/domains/{id}/verify` | Verify domain | ✅ |

## 🌐 Localization & i18n

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/localization/languages` | List supported languages | ✅ |
| GET | `/localization/translations/{lang}` | Get translations | ✅ |
| PUT | `/localization/translations/{lang}` | Update translations | ✅ |
| POST | `/localization/translations/import` | Import translations | ✅ |
| POST | `/localization/translations/export` | Export translations | ✅ |

## 🔄 Migration & Data Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/migration/import/users` | Import users from CSV/JSON | ✅ |
| POST | `/migration/export/users` | Export users to CSV/JSON | ✅ |
| POST | `/migration/import/organizations` | Import organizations | ✅ |
| POST | `/migration/export/organizations` | Export organizations | ✅ |
| GET | `/migration/jobs` | List migration jobs | ✅ |
| GET | `/migration/jobs/{id}` | Get migration job status | ✅ |
| POST | `/migration/jobs/{id}/cancel` | Cancel migration job | ✅ |

## 🏥 Health & Monitoring

### Health Checks
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/health` | Basic health check | ✅ |
| GET | `/health/ready` | Readiness probe | ✅ |
| GET | `/health/live` | Liveness probe | ✅ |
| GET | `/health/detailed` | Detailed health status | ✅ |

### Metrics & APM
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/metrics` | Prometheus metrics | ✅ |
| GET | `/apm/traces` | Get trace data | ✅ |
| GET | `/apm/metrics` | Get APM metrics | ✅ |
| GET | `/apm/errors` | Get error tracking | ✅ |

### Monitoring & Alerts
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/alerts` | List active alerts | ✅ |
| POST | `/alerts` | Create alert rule | ✅ |
| GET | `/alerts/{id}` | Get alert details | ✅ |
| PUT | `/alerts/{id}` | Update alert rule | ✅ |
| DELETE | `/alerts/{id}` | Delete alert rule | ✅ |
| POST | `/alerts/{id}/silence` | Silence alert | ✅ |

## 🤖 IoT & Device Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/iot/devices` | List IoT devices | ✅ |
| POST | `/iot/devices` | Register IoT device | ✅ |
| GET | `/iot/devices/{id}` | Get device details | ✅ |
| PUT | `/iot/devices/{id}` | Update device | ✅ |
| DELETE | `/iot/devices/{id}` | Delete device | ✅ |
| POST | `/iot/devices/{id}/authenticate` | Device authentication | ✅ |
| POST | `/iot/devices/{id}/revoke` | Revoke device access | ✅ |

## 🔌 GraphQL & WebSocket

### GraphQL
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/graphql` | GraphQL query endpoint | ✅ |
| GET | `/graphql/schema` | Get GraphQL schema | ✅ |
| GET | `/graphql/playground` | GraphQL playground | ✅ |

### WebSocket
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| WS | `/ws/auth` | Authentication events | ✅ |
| WS | `/ws/notifications` | Real-time notifications | ✅ |
| WS | `/ws/admin` | Admin real-time updates | ✅ |

## 📊 Rate Limiting

All endpoints implement intelligent rate limiting:

- **Authentication**: 10 requests/minute, 100 requests/hour
- **Magic Links**: 5 requests/hour per email
- **MFA Operations**: 10 requests/minute
- **Admin Operations**: 100 requests/minute
- **Public Endpoints**: 60 requests/minute
- **Webhooks**: 1000 requests/hour
- **GraphQL**: 100 requests/minute

## 🔒 Authentication Requirements

### Public Endpoints (No Auth Required)
- `GET /health/*`
- `POST /auth/signup`
- `POST /auth/signin`
- `POST /auth/magic-link`
- `POST /auth/magic-link/verify`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /oauth/*/authorize`
- `POST /oauth/*/callback`
- `GET /.well-known/*`

### User Authentication Required
- All `/users/*` endpoints
- All `/organizations/*` endpoints (user must be member)
- All `/mfa/*` endpoints
- All `/passkeys/*` endpoints
- All `/sessions/*` endpoints
- All `/webhooks/*` endpoints (user must own organization)

### Admin Authentication Required
- All `/admin/*` endpoints
- System-level `/health/detailed`
- `/metrics` (protected)

### Organization Permission Required
- Organization management endpoints (owner/admin role)
- Member management (admin role)
- SSO configuration (owner role)
- Webhook management (admin role)

### SCIM Token Required
- All `/scim/*` endpoints require special SCIM bearer token

## 📚 Request/Response Formats

### Standard Response Format
```json
{
  "success": true,
  "data": {
    // Response data
  },
  "pagination": {
    "has_next": true,
    "has_previous": false,
    "next_cursor": "eyJpZCI6MTIzfQ==",
    "previous_cursor": null,
    "total_count": 150
  },
  "meta": {
    "request_id": "req_123456789",
    "timestamp": "2025-01-16T10:30:00Z",
    "version": "1.0.0"
  }
}
```

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "email",
      "issue": "Invalid email format"
    }
  },
  "meta": {
    "request_id": "req_123456789",
    "timestamp": "2025-01-16T10:30:00Z"
  }
}
```

### Common Error Codes
- `VALIDATION_ERROR` - Invalid request data
- `AUTHENTICATION_REQUIRED` - Missing or invalid authentication
- `AUTHORIZATION_FAILED` - Insufficient permissions
- `RESOURCE_NOT_FOUND` - Requested resource doesn't exist
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server error

## 🎯 SDK Integration

All endpoints are supported by official SDKs:

- **TypeScript/JavaScript**: `@janua/typescript-sdk`
- **React**: `@janua/react-sdk`
- **Next.js**: `@janua/nextjs`
- **Python**: `janua-python`
- **Go**: `github.com/madfam-org/go-sdk`
- **Vue**: `@janua/vue`
- **Flutter**: `janua_flutter`

### SDK Example
```typescript
import { JanuaClient } from '@janua/typescript-sdk';

const client = new JanuaClient({
  baseUrl: 'https://api.janua.dev',
  apiKey: 'your_api_key'
});

// All endpoints available as typed methods
const user = await client.auth.me();
const orgs = await client.organizations.list();
const webhook = await client.webhooks.create({
  url: 'https://myapp.com/webhook',
  events: ['user.created', 'user.updated']
});
```

## 🔗 Related Documentation

- **[Authentication Guide](authentication.md)** - Detailed auth flows
- **[MFA Implementation](../guides/mfa-2fa-implementation-guide.md)** - Multi-factor setup
- **[Magic Links](../guides/magic-link-authentication-guide.md)** - Passwordless auth
- **[WebAuthn Guide](webauthn.md)** - Passkey implementation
- **[Enterprise Features](enterprise.md)** - SSO, SCIM, RBAC
- **[Webhook Integration](webhooks.md)** - Real-time events
- **[Error Handling](error-handling.md)** - Error codes and handling
- **[Rate Limiting](rate-limiting.md)** - API limits and best practices

---

**📊 Total Endpoints: 256+** • **🔐 Authentication Methods: 7** • **🏢 Enterprise Ready** • **📱 Multi-Platform SDKs**