# Plinto TypeScript SDK

[![npm version](https://badge.fury.io/js/@plinto/typescript-sdk.svg)](https://www.npmjs.com/package/@plinto/typescript-sdk)
[![TypeScript](https://img.shields.io/badge/TypeScript-Ready-blue.svg)](https://www.typescriptlang.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Official TypeScript/JavaScript SDK for the Plinto authentication API. This SDK provides a complete interface for user authentication, organization management, webhooks, and administrative operations.

## Features

- 🔐 **Complete Authentication** - Sign up, sign in, password reset, magic links
- 👥 **User Management** - Profile management, session handling, user operations
- 🏢 **Organization Management** - Create, manage organizations and members
- 🔑 **Multi-Factor Authentication** - TOTP, backup codes, recovery options
- 🔗 **OAuth Integration** - Google, GitHub, Microsoft, Discord, Twitter
- 🛡️ **Passkey Support** - WebAuthn/FIDO2 passwordless authentication
- 🪝 **Webhook Management** - Configure and manage webhook endpoints
- ⚡ **TypeScript First** - Full type safety and IntelliSense support
- 🌐 **Cross-Platform** - Works in browser and Node.js environments
- 🔄 **Automatic Token Refresh** - Seamless token management
- 📱 **Tree Shakeable** - Import only what you need
- 🛠️ **Error Handling** - Comprehensive error types and handling

## Installation

```bash
npm install @plinto/typescript-sdk
```

Or with yarn:

```bash
yarn add @plinto/typescript-sdk
```

## Quick Start

### Basic Setup

```typescript
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.yourapp.com'
});
```

### Authentication

```typescript
// Sign up a new user
const signUpResult = await client.auth.signUp({
  email: 'user@example.com',
  password: 'securepassword123',
  first_name: 'John',
  last_name: 'Doe'
});

// Sign in existing user
const signInResult = await client.auth.signIn({
  email: 'user@example.com',
  password: 'securepassword123'
});

// Get current user
const user = await client.users.getCurrentUser();
```

### Organization Management

```typescript
// Create an organization
const organization = await client.organizations.createOrganization({
  name: 'My Company',
  slug: 'my-company'
});

// Invite a member
const invitation = await client.organizations.inviteMember(organization.id, {
  email: 'member@example.com',
  role: 'member'
});

// List organization members
const members = await client.organizations.listMembers(organization.id);
```

### Multi-Factor Authentication

```typescript
// Enable MFA
const mfaSetup = await client.auth.enableMFA({
  password: 'userpassword'
});

console.log('QR Code:', mfaSetup.qr_code);
console.log('Backup codes:', mfaSetup.backup_codes);

// Verify MFA setup
await client.auth.verifyMFA({ code: '123456' });

// Get MFA status
const status = await client.auth.getMFAStatus();
```

### Webhook Management

```typescript
// Create a webhook endpoint
const webhook = await client.webhooks.createEndpoint({
  url: 'https://myapp.com/webhooks/plinto',
  events: ['user.created', 'user.signed_in'],
  description: 'User events webhook'
});

// List webhook endpoints
const webhooks = await client.webhooks.listEndpoints();

// Test webhook endpoint
await client.webhooks.testEndpoint(webhook.id);
```

### OAuth Integration

```typescript
// Get available OAuth providers
const providers = await client.auth.getOAuthProviders();

// Initiate OAuth flow
const oauthUrl = await client.auth.initiateOAuth('google', {
  redirect_uri: 'https://myapp.com/auth/callback'
});

// Redirect user to oauthUrl.authorization_url

// Handle OAuth callback (in your callback endpoint)
const result = await client.auth.handleOAuthCallback('google', code, state);
```

### Passkey Authentication

```typescript
// Check passkey availability
const availability = await client.auth.checkPasskeyAvailability();

if (availability.available) {
  // Register a new passkey
  const options = await client.auth.getPasskeyRegistrationOptions();
  
  // Use WebAuthn API to create credential
  const credential = await navigator.credentials.create({
    publicKey: options
  });
  
  // Verify registration
  await client.auth.verifyPasskeyRegistration(credential, 'My Security Key');
}
```

## Configuration

The SDK supports various configuration options:

```typescript
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.yourapp.com',
  timeout: 30000,                    // Request timeout in milliseconds
  retryAttempts: 3,                  // Number of retry attempts
  retryDelay: 1000,                  // Delay between retries
  autoRefreshTokens: true,           // Automatically refresh tokens
  tokenStorage: 'localStorage',      // Token storage method
  debug: false                       // Enable debug logging
});
```

### Token Storage Options

- `'localStorage'` - Browser localStorage (default for browser)
- `'sessionStorage'` - Browser sessionStorage
- `'memory'` - In-memory storage (default for Node.js)
- `'custom'` - Custom storage implementation

```typescript
// Custom storage example
const client = createClient({
  baseURL: 'https://api.yourapp.com',
  tokenStorage: 'custom',
  customStorage: {
    async getItem(key: string) {
      // Your custom get implementation
      return await yourStorage.get(key);
    },
    async setItem(key: string, value: string) {
      // Your custom set implementation
      await yourStorage.set(key, value);
    },
    async removeItem(key: string) {
      // Your custom remove implementation
      await yourStorage.remove(key);
    }
  }
});
```

## Error Handling

The SDK provides comprehensive error handling with specific error types:

```typescript
import { 
  isAuthenticationError, 
  isValidationError, 
  isNetworkError 
} from '@plinto/typescript-sdk';

try {
  await client.auth.signIn({
    email: 'invalid@email.com',
    password: 'wrongpassword'
  });
} catch (error) {
  if (isAuthenticationError(error)) {
    console.log('Authentication failed:', error.message);
  } else if (isValidationError(error)) {
    console.log('Validation errors:', error.violations);
  } else if (isNetworkError(error)) {
    console.log('Network error:', error.message);
  } else {
    console.log('Other error:', error.message);
  }
}
```

### Error Types

- `AuthenticationError` - Authentication/authorization failures
- `ValidationError` - Input validation failures  
- `NotFoundError` - Resource not found
- `ConflictError` - Resource conflicts (e.g., email already exists)
- `RateLimitError` - Rate limiting errors
- `NetworkError` - Network connectivity issues
- `ServerError` - Server-side errors
- `TokenError` - Token-related errors
- `MFAError` - Multi-factor authentication errors
- `WebhookError` - Webhook-related errors
- `OAuthError` - OAuth-related errors
- `PasskeyError` - Passkey/WebAuthn errors

## Event Handling

The SDK emits events for important state changes:

```typescript
// Authentication events
client.on('auth:signedIn', ({ user }) => {
  console.log('User signed in:', user);
});

client.on('auth:signedOut', () => {
  console.log('User signed out');
});

// Token events
client.on('token:refreshed', ({ tokens }) => {
  console.log('Tokens refreshed automatically');
});

client.on('token:expired', () => {
  console.log('Tokens expired');
});

// Error events
client.on('error', ({ error }) => {
  console.error('SDK error:', error);
});
```

## API Reference

### Client

- `createClient(config)` - Create a new Plinto client
- `client.isAuthenticated()` - Check authentication status
- `client.getCurrentUser()` - Get current user
- `client.setTokens(tokens)` - Set authentication tokens
- `client.signOut()` - Sign out and clear tokens

### Auth Module

#### Basic Authentication
- `auth.signUp(request)` - Create new user account
- `auth.signIn(request)` - Sign in user
- `auth.signOut()` - Sign out current user
- `auth.refreshToken(request)` - Refresh access token
- `auth.getCurrentUser()` - Get current user info

#### Password Management
- `auth.forgotPassword(request)` - Request password reset
- `auth.resetPassword(request)` - Reset password with token
- `auth.changePassword(request)` - Change password

#### Email Verification
- `auth.verifyEmail(token)` - Verify email with token
- `auth.resendVerificationEmail()` - Resend verification email

#### Magic Links
- `auth.sendMagicLink(request)` - Send magic link
- `auth.verifyMagicLink(token)` - Verify magic link

#### Multi-Factor Authentication
- `auth.getMFAStatus()` - Get MFA status
- `auth.enableMFA(request)` - Enable MFA
- `auth.verifyMFA(request)` - Verify MFA setup
- `auth.disableMFA(request)` - Disable MFA
- `auth.regenerateMFABackupCodes(password)` - Regenerate backup codes
- `auth.validateMFACode(code)` - Validate MFA code

#### OAuth
- `auth.getOAuthProviders()` - Get available providers
- `auth.initiateOAuth(provider, options)` - Start OAuth flow
- `auth.handleOAuthCallback(provider, code, state)` - Handle callback
- `auth.linkOAuthAccount(provider, options)` - Link OAuth account
- `auth.unlinkOAuthAccount(provider)` - Unlink OAuth account
- `auth.getLinkedAccounts()` - Get linked accounts

#### Passkeys
- `auth.checkPasskeyAvailability()` - Check WebAuthn support
- `auth.getPasskeyRegistrationOptions(options)` - Get registration options
- `auth.verifyPasskeyRegistration(credential, name)` - Verify registration
- `auth.getPasskeyAuthenticationOptions(email)` - Get auth options
- `auth.verifyPasskeyAuthentication(credential, challenge, email)` - Verify auth
- `auth.listPasskeys()` - List user's passkeys
- `auth.updatePasskey(id, name)` - Update passkey name
- `auth.deletePasskey(id, password)` - Delete passkey

### Users Module

- `users.getCurrentUser()` - Get current user profile
- `users.updateCurrentUser(request)` - Update user profile
- `users.uploadAvatar(file)` - Upload user avatar
- `users.deleteAvatar()` - Delete user avatar
- `users.getUserById(userId)` - Get user by ID
- `users.listUsers(params)` - List users
- `users.deleteCurrentUser(password)` - Delete current user
- `users.suspendUser(userId, reason)` - Suspend user (admin)
- `users.reactivateUser(userId)` - Reactivate user (admin)

#### Session Management
- `users.listSessions(params)` - List user sessions
- `users.getSession(sessionId)` - Get session details
- `users.revokeSession(sessionId)` - Revoke specific session
- `users.revokeAllSessions()` - Revoke all sessions
- `users.refreshSession(sessionId)` - Refresh session
- `users.getRecentActivity(limit)` - Get recent activity
- `users.getSecurityAlerts()` - Get security alerts

### Organizations Module

#### Organization Management
- `organizations.createOrganization(request)` - Create organization
- `organizations.listOrganizations()` - List user's organizations
- `organizations.getOrganization(orgId)` - Get organization details
- `organizations.updateOrganization(orgId, request)` - Update organization
- `organizations.deleteOrganization(orgId)` - Delete organization

#### Member Management
- `organizations.listMembers(orgId)` - List organization members
- `organizations.updateMemberRole(orgId, userId, role)` - Update member role
- `organizations.removeMember(orgId, userId)` - Remove member

#### Invitation Management
- `organizations.inviteMember(orgId, request)` - Invite member
- `organizations.acceptInvitation(token)` - Accept invitation
- `organizations.listInvitations(orgId, status)` - List invitations
- `organizations.revokeInvitation(orgId, invitationId)` - Revoke invitation

#### Role Management
- `organizations.createCustomRole(orgId, request)` - Create custom role
- `organizations.listRoles(orgId)` - List organization roles
- `organizations.deleteCustomRole(orgId, roleId)` - Delete custom role
- `organizations.transferOwnership(orgId, newOwnerId)` - Transfer ownership

### Webhooks Module

- `webhooks.createEndpoint(request)` - Create webhook endpoint
- `webhooks.listEndpoints(isActive)` - List webhook endpoints
- `webhooks.getEndpoint(endpointId)` - Get endpoint details
- `webhooks.updateEndpoint(endpointId, request)` - Update endpoint
- `webhooks.deleteEndpoint(endpointId)` - Delete endpoint
- `webhooks.testEndpoint(endpointId)` - Test endpoint
- `webhooks.getEndpointStats(endpointId, days)` - Get statistics
- `webhooks.listEvents(endpointId, options)` - List events
- `webhooks.listDeliveries(endpointId, options)` - List deliveries
- `webhooks.regenerateSecret(endpointId)` - Regenerate secret
- `webhooks.getEventTypes()` - Get available event types
- `webhooks.verifySignature(secret, payload, signature)` - Verify signature

### Admin Module

- `admin.getStats()` - Get system statistics
- `admin.getSystemHealth()` - Get system health
- `admin.getSystemConfig()` - Get system configuration
- `admin.listAllUsers(params)` - List all users (admin)
- `admin.updateUser(userId, updates)` - Update user (admin)
- `admin.deleteUser(userId, permanent)` - Delete user (admin)
- `admin.listAllOrganizations(params)` - List all organizations (admin)
- `admin.deleteOrganization(orgId)` - Delete organization (admin)
- `admin.getActivityLogs(options)` - Get activity logs (admin)
- `admin.revokeAllSessions(userId)` - Revoke all sessions (admin)
- `admin.toggleMaintenanceMode(enabled, message)` - Toggle maintenance mode

## Environment Support

### Browser

```typescript
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.yourapp.com',
  tokenStorage: 'localStorage'
});
```

### Node.js

```typescript
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.yourapp.com',
  tokenStorage: 'memory'
});
```

### React

```typescript
import { createClient } from '@plinto/typescript-sdk';
import { createContext, useContext } from 'react';

const PlintoContext = createContext(null);

export function PlintoProvider({ children }) {
  const client = createClient({
    baseURL: process.env.REACT_APP_API_URL
  });

  return (
    <PlintoContext.Provider value={client}>
      {children}
    </PlintoContext.Provider>
  );
}

export function usePlinto() {
  return useContext(PlintoContext);
}
```

### Next.js

```typescript
// pages/_app.tsx
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: process.env.NEXT_PUBLIC_API_URL
});

export default function App({ Component, pageProps }) {
  return <Component {...pageProps} plintoClient={client} />;
}
```

### Vue.js

```typescript
// main.ts
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: process.env.VUE_APP_API_URL
});

app.provide('plinto', client);
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: [https://docs.plinto.dev](https://docs.plinto.dev)
- GitHub Issues: [https://github.com/plinto/plinto/issues](https://github.com/plinto/plinto/issues)
- Discord: [https://discord.gg/plinto](https://discord.gg/plinto)
- Email: support@plinto.dev

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and migration guides.