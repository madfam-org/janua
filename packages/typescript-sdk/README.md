# Janua TypeScript SDK

[![npm version](https://badge.fury.io/js/@janua/typescript-sdk.svg)](https://www.npmjs.com/package/@janua/typescript-sdk)
[![TypeScript](https://img.shields.io/badge/TypeScript-Ready-blue.svg)](https://www.typescriptlang.org)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Official TypeScript/JavaScript SDK for the [Janua](https://janua.dev) authentication API. This SDK provides a complete, type-safe interface for user authentication, MFA, OAuth, passkeys, organization management, webhooks, real-time communication, and administrative operations.

Works in browser and Node.js environments. Ships as both ESM and CommonJS.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Multi-Factor Authentication](#multi-factor-authentication)
- [OAuth Providers](#oauth-providers)
- [Passkeys and WebAuthn](#passkeys-and-webauthn)
- [User Management](#user-management)
- [Organizations](#organizations)
- [Sessions](#sessions)
- [Webhooks](#webhooks)
- [PKCE Utilities](#pkce-utilities)
- [WebSocket Client](#websocket-client)
- [GraphQL Client](#graphql-client)
- [Error Handling](#error-handling)
- [Utility Exports](#utility-exports)
- [Configuration Presets](#configuration-presets)
- [TypeScript Types](#typescript-types)

---

## Installation

```bash
npm install @janua/typescript-sdk
```

This package is published to the MADFAM private registry. Add the following to your `.npmrc` before installing:

```
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

For GraphQL support, also install the optional peer dependencies:

```bash
npm install @apollo/client graphql graphql-ws
```

**Requirements:** Node.js >= 16.0.0

---

## Quick Start

Create a client instance with `createClient` and begin making authenticated requests.

```typescript
import { createClient } from '@janua/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.janua.dev'
});

// Sign up a new user
const result = await client.auth.signUp({
  email: 'user@example.com',
  password: 'securepassword123',
  first_name: 'Jane',
  last_name: 'Smith'
});

console.log(result.user);   // User object
console.log(result.tokens); // Access and refresh tokens

// Sign in
const session = await client.auth.signIn({
  email: 'user@example.com',
  password: 'securepassword123'
});

// Get the authenticated user's profile
const user = await client.users.getCurrentUser();
```

You can also use the factory function with a preset:

```typescript
import { createClientWithPreset } from '@janua/typescript-sdk';

// Merges preset defaults with any overrides you provide
const client = createClientWithPreset('production', {
  baseURL: 'https://api.janua.dev'
});
```

---

## Configuration

`createClient` accepts a `JanuaConfig` object. All fields except `baseURL` are optional.

```typescript
import { createClient } from '@janua/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.janua.dev',  // Required
  timeout: 15000,                    // Request timeout in milliseconds (default: 15000)
  retryAttempts: 3,                  // Automatic retry count on transient failures (default: 3)
  retryDelay: 1000,                  // Base delay between retries in milliseconds
  autoRefreshTokens: true,           // Refresh access tokens before expiry (default: true)
  tokenStorage: 'localStorage',      // Where to persist tokens (see below)
  debug: false                       // Log SDK activity to console
});
```

### Token Storage

| Value | Description | Default for |
|---|---|---|
| `'localStorage'` | Browser `localStorage` | Browser environments |
| `'sessionStorage'` | Browser `sessionStorage` | — |
| `'memory'` | In-process memory, cleared on reload | Node.js environments |
| `'custom'` | Your own storage implementation | — |

**Custom storage example:**

```typescript
const client = createClient({
  baseURL: 'https://api.janua.dev',
  tokenStorage: 'custom',
  customStorage: {
    async getItem(key: string): Promise<string | null> {
      return await yourStore.get(key);
    },
    async setItem(key: string, value: string): Promise<void> {
      await yourStore.set(key, value);
    },
    async removeItem(key: string): Promise<void> {
      await yourStore.delete(key);
    }
  }
});
```

### Event Handling

The client emits events for authentication state changes and token lifecycle:

```typescript
client.on('auth:signedIn', ({ user }) => {
  console.log('Signed in as:', user.email);
});

client.on('auth:signedOut', () => {
  console.log('Session ended');
});

client.on('token:refreshed', ({ tokens }) => {
  // Tokens were automatically refreshed
});

client.on('token:expired', () => {
  // Redirect to login
});

client.on('error', ({ error }) => {
  console.error('SDK error:', error);
});
```

---

## Authentication

All authentication methods are on `client.auth`.

### Sign Up

```typescript
const result = await client.auth.signUp({
  email: 'user@example.com',
  password: 'securepassword123',
  first_name: 'Jane',      // Optional
  last_name: 'Smith'       // Optional
});
// result.user: User
// result.tokens: TokenResponse
```

### Sign In

```typescript
const result = await client.auth.signIn({
  email: 'user@example.com',
  password: 'securepassword123'
});
```

### Sign Out

```typescript
await client.auth.signOut();
// Clears stored tokens and emits 'auth:signedOut'
```

### Refresh Token

```typescript
const tokens = await client.auth.refreshToken({
  refresh_token: 'your-refresh-token'
});
```

### Password Management

```typescript
// Request a password reset email
await client.auth.forgotPassword({ email: 'user@example.com' });

// Reset password using token from email
await client.auth.resetPassword({
  token: 'reset-token-from-email',
  password: 'newSecurePassword123'
});

// Change password while authenticated
await client.auth.changePassword({
  current_password: 'oldPassword',
  new_password: 'newPassword123'
});
```

### Email Verification

```typescript
// Verify email address with token from the verification email
await client.auth.verifyEmail('verification-token');

// Resend the verification email to the authenticated user
await client.auth.resendVerificationEmail();
```

### Magic Links

```typescript
// Send a magic link to the user's email
await client.auth.sendMagicLink({ email: 'user@example.com' });

// Verify the magic link token (from the URL in the email)
const result = await client.auth.verifyMagicLink('magic-link-token');
```

---

## Multi-Factor Authentication

### Enable MFA

```typescript
const setup = await client.auth.enableMFA({
  password: 'currentPassword'
});

// Display to the user so they can scan with an authenticator app
console.log('QR code:', setup.qr_code);

// Store these securely — they are shown only once
console.log('Backup codes:', setup.backup_codes);
```

### Verify MFA Setup

After the user scans the QR code, confirm setup with their first TOTP code:

```typescript
await client.auth.verifyMFA({ code: '123456' });
```

### Check MFA Status

```typescript
const status = await client.auth.getMFAStatus();
// status.enabled: boolean
// status.methods: string[]
```

### Disable MFA

```typescript
await client.auth.disableMFA({ password: 'currentPassword' });
```

### Backup Codes

```typescript
// Regenerate backup codes (invalidates previous codes)
const { backup_codes } = await client.auth.regenerateMFABackupCodes('currentPassword');

// Validate a single TOTP code without a full sign-in
await client.auth.validateMFACode('123456');
```

---

## OAuth Providers

Supported providers: `google`, `github`, `microsoft`, `discord`, `twitter`.

### Initiate an OAuth Flow

```typescript
// Retrieve which providers are configured on your Janua instance
const { providers } = await client.auth.getOAuthProviders();

// Start the OAuth flow — redirects the user to the provider's consent screen
const { authorization_url } = await client.auth.initiateOAuth('google', {
  redirect_uri: 'https://yourapp.com/auth/callback'
});

window.location.href = authorization_url;
```

### Handle the OAuth Callback

```typescript
// In your callback route handler
const result = await client.auth.handleOAuthCallback('google', code, state);
// result.user, result.tokens
```

### Link and Unlink Accounts

```typescript
// Link an additional OAuth provider to an existing account
await client.auth.linkOAuthAccount('github', {
  redirect_uri: 'https://yourapp.com/auth/callback'
});

// Remove a linked OAuth provider
await client.auth.unlinkOAuthAccount('github');

// List all OAuth providers linked to the current user
const { accounts } = await client.auth.getLinkedAccounts();
```

---

## Passkeys and WebAuthn

The SDK provides two levels of WebAuthn support:

- **`WebAuthnHelper`** — high-level class that handles all credential serialization and browser API calls internally.
- **`client.auth` methods** — low-level methods for registering and verifying passkeys when you need full control.

### Using WebAuthnHelper (recommended)

```typescript
import { WebAuthnHelper, checkWebAuthnSupport } from '@janua/typescript-sdk';

// Check browser support before attempting passkey operations
const support = checkWebAuthnSupport();

if (support.available) {
  const helper = new WebAuthnHelper(client.auth);

  // Register a new passkey for the authenticated user
  await helper.registerPasskey('My Laptop');

  // Authenticate with a passkey (optionally pass email for a targeted credential)
  const result = await helper.authenticateWithPasskey('user@example.com');
  // result.user, result.tokens
}
```

`checkWebAuthnSupport()` returns a `WebAuthnSupport` object:

```typescript
{
  available: boolean;   // WebAuthn API is present
  platform: boolean;    // Platform authenticator check (requires async call)
  conditional: boolean; // Conditional mediation check (requires async call)
}
```

For async capability checks:

```typescript
import { checkPlatformAuthenticator, checkConditionalMediation } from '@janua/typescript-sdk';

const hasPlatformKey = await checkPlatformAuthenticator();
const hasConditional = await checkConditionalMediation();
```

### Low-Level Passkey Methods

```typescript
// Get registration options from the server
const options = await client.auth.getPasskeyRegistrationOptions({ name: 'My Key' });

// After calling navigator.credentials.create(), verify with the server
await client.auth.verifyPasskeyRegistration(credential, 'My Key');

// Get authentication options
const authOptions = await client.auth.getPasskeyAuthenticationOptions('user@example.com');

// After calling navigator.credentials.get(), verify with the server
const result = await client.auth.verifyPasskeyAuthentication(credential, challenge, email);

// Manage registered passkeys
const passkeys = await client.auth.listPasskeys();
await client.auth.updatePasskey(passkeyId, 'New Name');
await client.auth.deletePasskey(passkeyId, 'currentPassword');
```

---

## User Management

All user methods are on `client.users`.

```typescript
// Get the authenticated user's profile
const user = await client.users.getCurrentUser();

// Update profile fields
await client.users.updateCurrentUser({
  first_name: 'Jane',
  display_name: 'Jane S.'
});

// Upload an avatar (browser File object)
await client.users.uploadAvatar(file);

// Remove avatar
await client.users.deleteAvatar();

// Retrieve any user by ID (requires appropriate permissions)
const other = await client.users.getUserById('user-uuid');

// List users with pagination
const { users, total } = await client.users.listUsers({
  page: 1,
  limit: 25
});

// Delete the authenticated user's account permanently
await client.users.deleteCurrentUser('currentPassword');
```

### Administrative User Actions

```typescript
// Suspend a user account (admin only)
await client.users.suspendUser('user-uuid', 'Terms of service violation');

// Reactivate a suspended user (admin only)
await client.users.reactivateUser('user-uuid');
```

---

## Organizations

All organization methods are on `client.organizations`.

### Managing Organizations

```typescript
// Create a new organization
const org = await client.organizations.createOrganization({
  name: 'Acme Corp',
  slug: 'acme-corp'
});

// List organizations the authenticated user belongs to
const orgs = await client.organizations.listOrganizations();

// Get organization details
const org = await client.organizations.getOrganization('org-uuid');

// Update organization metadata
await client.organizations.updateOrganization('org-uuid', {
  name: 'Acme Corporation'
});

// Delete an organization
await client.organizations.deleteOrganization('org-uuid');
```

### Managing Members

```typescript
// List all members in an organization
const members = await client.organizations.listMembers('org-uuid');

// Change a member's role
await client.organizations.updateMemberRole('org-uuid', 'user-uuid', 'admin');

// Remove a member
await client.organizations.removeMember('org-uuid', 'user-uuid');

// Transfer ownership to another member
await client.organizations.transferOwnership('org-uuid', 'new-owner-uuid');
```

### Invitations

```typescript
// Invite a new member by email
const invitation = await client.organizations.inviteMember('org-uuid', {
  email: 'colleague@example.com',
  role: 'member'
});

// Accept an invitation using the token from the invitation email
await client.organizations.acceptInvitation('invitation-token');

// List pending and accepted invitations
const invitations = await client.organizations.listInvitations('org-uuid', 'pending');

// Cancel an invitation
await client.organizations.revokeInvitation('org-uuid', 'invitation-uuid');
```

### Custom Roles

```typescript
// Create a custom role for fine-grained access control
await client.organizations.createCustomRole('org-uuid', {
  name: 'billing-admin',
  permissions: ['billing:read', 'billing:write']
});

// List all roles including custom ones
const roles = await client.organizations.listRoles('org-uuid');

// Delete a custom role
await client.organizations.deleteCustomRole('org-uuid', 'role-uuid');
```

---

## Sessions

Session management is available on both `client.users` and `client.sessions`.

```typescript
// List all active sessions for the authenticated user
const sessions = await client.users.listSessions({ page: 1, limit: 10 });

// Get details for a specific session
const session = await client.users.getSession('session-uuid');

// Revoke a specific session (sign out that device)
await client.users.revokeSession('session-uuid');

// Sign out all sessions across all devices
await client.users.revokeAllSessions();

// Refresh a session's expiry
await client.users.refreshSession('session-uuid');

// Audit trail
const activity = await client.users.getRecentActivity(20); // last 20 events
const alerts = await client.users.getSecurityAlerts();
```

---

## Webhooks

All webhook methods are on `client.webhooks`.

### Configuring Endpoints

```typescript
// Register a new webhook endpoint
const endpoint = await client.webhooks.createEndpoint({
  url: 'https://yourapp.com/webhooks/janua',
  events: ['user.created', 'user.signed_in', 'organization.member_added'],
  description: 'Production webhook'
});

// List all registered endpoints
const endpoints = await client.webhooks.listEndpoints();

// List only active endpoints
const active = await client.webhooks.listEndpoints(true);

// Get endpoint details
const ep = await client.webhooks.getEndpoint('endpoint-uuid');

// Update endpoint configuration
await client.webhooks.updateEndpoint('endpoint-uuid', {
  events: ['user.created'],
  description: 'Updated description'
});

// Delete an endpoint
await client.webhooks.deleteEndpoint('endpoint-uuid');

// Send a test event to an endpoint
await client.webhooks.testEndpoint('endpoint-uuid');
```

### Monitoring and Delivery

```typescript
// Get delivery statistics for an endpoint
const stats = await client.webhooks.getEndpointStats('endpoint-uuid', 7); // last 7 days

// List webhook events
const events = await client.webhooks.listEvents('endpoint-uuid', {
  page: 1,
  limit: 25
});

// List delivery attempts with their response status
const deliveries = await client.webhooks.listDeliveries('endpoint-uuid', {
  page: 1,
  limit: 25
});

// Rotate the signing secret for an endpoint
const { secret } = await client.webhooks.regenerateSecret('endpoint-uuid');

// List all supported event type strings
const types = await client.webhooks.getEventTypes();
```

### Verifying Webhook Signatures

Verify that incoming webhook requests originate from Janua by validating the `X-Janua-Signature` header:

```typescript
// In your webhook handler (example using Express)
app.post('/webhooks/janua', express.raw({ type: 'application/json' }), (req, res) => {
  const signature = req.headers['x-janua-signature'] as string;
  const isValid = client.webhooks.verifySignature(
    process.env.WEBHOOK_SECRET,
    req.body.toString(),
    signature
  );

  if (!isValid) {
    return res.status(401).send('Invalid signature');
  }

  const event = JSON.parse(req.body.toString());
  // Process event...
  res.status(200).send('OK');
});
```

### Webhook Event Types

The `WebhookEventType` enum lists all available events:

```typescript
import { WebhookEventType } from '@janua/typescript-sdk';

// user.created, user.updated, user.deleted
// user.signed_in, user.signed_out
// session.created, session.expired
// organization.created, organization.updated, organization.deleted
// organization.member_added, organization.member_removed
```

---

## PKCE Utilities

The SDK exports PKCE (Proof Key for Code Exchange) utilities as the single source of truth for RFC 7636 implementation. Framework SDKs (`@janua/react-sdk`, `@janua/vue-sdk`, etc.) re-export from these functions.

All PKCE state is stored in `sessionStorage` under the keys defined in `PKCE_STORAGE_KEYS`.

### Generating PKCE Parameters

```typescript
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  PKCE_STORAGE_KEYS
} from '@janua/typescript-sdk';

// Generate a cryptographically random code verifier (43-128 characters, RFC 7636)
const verifier = generateCodeVerifier();

// Derive the S256 code challenge from the verifier (async, uses Web Crypto API)
const challenge = await generateCodeChallenge(verifier);

// Generate a random state parameter for CSRF protection
const state = generateState();

// Persist both in sessionStorage before redirecting to the authorization server
storePKCEParams(verifier, state);
```

### Building the Authorization URL

```typescript
import { buildAuthorizationUrl } from '@janua/typescript-sdk';

const url = buildAuthorizationUrl(
  'https://api.janua.dev',     // Janua API base URL
  'google',                    // OAuth provider
  'your-client-id',            // OAuth client ID
  'https://yourapp.com/callback', // Redirect URI
  challenge,                   // Code challenge (from generateCodeChallenge)
  state,                       // State (from generateState)
  'openid profile email'       // Scopes (optional, defaults to 'openid profile email')
);

window.location.href = url;
```

### Handling the Callback

```typescript
import {
  parseOAuthCallback,
  validateState,
  retrievePKCEParams,
  clearPKCEParams
} from '@janua/typescript-sdk';

// In your callback route
const { code, state: callbackState, error } = parseOAuthCallback();

if (error) {
  throw new Error(`OAuth error: ${error}`);
}

// Validate state to prevent CSRF
if (!validateState(callbackState)) {
  throw new Error('State mismatch — possible CSRF attack');
}

// Retrieve the stored verifier
const params = retrievePKCEParams();
if (!params) {
  throw new Error('PKCE parameters not found in session');
}

// Exchange code for tokens using your Janua client
const result = await client.auth.handleOAuthCallback('google', code, callbackState);

// Clean up PKCE state from sessionStorage
clearPKCEParams();
```

### PKCE Storage Keys

```typescript
import { PKCE_STORAGE_KEYS } from '@janua/typescript-sdk';

// PKCE_STORAGE_KEYS.codeVerifier === 'janua_pkce_verifier'
// PKCE_STORAGE_KEYS.state       === 'janua_pkce_state'
```

---

## WebSocket Client

The SDK provides a WebSocket client with automatic reconnection, channel subscriptions, and a heartbeat mechanism.

### Authentication Security

**The authentication token is never sent as a URL query parameter.** Sending credentials in URLs exposes them in server logs, browser history, and HTTP `Referer` headers. Instead, the client connects without credentials and sends the token as the first message after the connection is established:

```
Client connects to wss://your-server/ws
Server accepts the TCP connection
Client sends: { "type": "auth", "token": "your-jwt-token" }
Server validates the token and upgrades the session
```

This approach keeps credentials out of any URL-based logging infrastructure.

### Using WebSocket

```typescript
import { createWebSocketClient } from '@janua/typescript-sdk';

const ws = createWebSocketClient({
  url: 'wss://api.janua.dev/ws',
  getAuthToken: async () => {
    // Return the current access token; the SDK sends it as the first message
    return await client.auth.getAccessToken();
  },
  reconnect: true,             // Automatically reconnect on disconnect (default: true)
  reconnectAttempts: 5,        // Maximum reconnection attempts (default: 5)
  reconnectInterval: 5000,     // Milliseconds between reconnection attempts (default: 5000)
  heartbeatInterval: 30000,    // Milliseconds between ping messages (default: 30000)
  debug: false
});

// Listen for connection events
ws.on('connected', ({ timestamp }) => {
  console.log('Connected at', new Date(timestamp));
});

ws.on('disconnected', ({ code, reason }) => {
  console.log(`Disconnected: ${code} ${reason}`);
});

ws.on('message', (message) => {
  console.log('Received:', message);
});

ws.on('reconnecting', ({ attempt, maxAttempts }) => {
  console.log(`Reconnecting (${attempt}/${maxAttempts})...`);
});

ws.on('error', ({ error }) => {
  console.error('WebSocket error:', error);
});

// Connect
await ws.connect();

// Subscribe to a channel
ws.subscribe('user:notifications');

// Publish a message to a channel
ws.publish('user:notifications', { text: 'Hello' }, 'message.sent');

// Send a raw message
ws.send({ type: 'custom', data: { key: 'value' } });

// Unsubscribe from a channel
ws.unsubscribe('user:notifications');

// Check connection state
console.log(ws.getStatus());    // 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'error'
console.log(ws.isConnected());  // boolean
console.log(ws.getChannels());  // string[]

// Disconnect cleanly
ws.disconnect();
```

### Alternative API: WebSocketClient

`WebSocketClient` offers a callback-based subscription API and wraps the `WebSocket` class internally:

```typescript
import { WebSocketClient } from '@janua/typescript-sdk';

const client = new WebSocketClient('wss://api.janua.dev/ws', {
  token: 'your-jwt-token',   // Sent as first message, not in URL
  autoReconnect: true,
  heartbeatInterval: 30000,
  debug: false
});

await client.connect();

// Subscribe with a per-message callback
await client.subscribe('team:events', (data) => {
  console.log('Team event:', data);
});

await client.publish('team:events', { action: 'file_uploaded' });
await client.unsubscribe('team:events');
await client.disconnect();
```

---

## GraphQL Client

The GraphQL client is built on Apollo Client and supports queries, mutations, and subscriptions. Install the optional peer dependencies before use:

```bash
npm install @apollo/client graphql graphql-ws
```

```typescript
import { createGraphQLClient } from '@janua/typescript-sdk';
import { gql } from '@apollo/client/core';

const graphql = createGraphQLClient({
  httpUrl: 'https://api.janua.dev/graphql',
  wsUrl: 'wss://api.janua.dev/graphql',  // Required for subscriptions
  getAuthToken: async () => await client.auth.getAccessToken(),
  debug: false
});
```

### Queries

```typescript
const GET_USER = gql`
  query GetUser($id: ID!) {
    user(id: $id) {
      id
      email
      first_name
    }
  }
`;

const result = await graphql.query(GET_USER, {
  variables: { id: 'user-uuid' },
  fetchPolicy: 'network-only'
});

console.log(result.data.user);
```

### Mutations

```typescript
const UPDATE_PROFILE = gql`
  mutation UpdateProfile($input: UpdateProfileInput!) {
    updateProfile(input: $input) {
      id
      display_name
    }
  }
`;

const result = await graphql.mutate(UPDATE_PROFILE, {
  variables: { input: { display_name: 'Jane S.' } }
});
```

### Subscriptions

Subscriptions require the `wsUrl` option to be configured:

```typescript
const USER_EVENTS = gql`
  subscription OnUserEvent($userId: ID!) {
    userEvent(userId: $userId) {
      type
      payload
    }
  }
`;

const observable = graphql.subscribe(USER_EVENTS, {
  variables: { userId: 'user-uuid' }
});

const subscription = observable.subscribe({
  next: ({ data }) => console.log('Event:', data.userEvent),
  error: (err) => console.error('Subscription error:', err)
});

// Later, unsubscribe
subscription.unsubscribe();
```

### Cache and Connection Management

```typescript
// Clear the Apollo Client in-memory cache
await graphql.clearCache();

// Reset the store and re-run active queries
await graphql.resetStore();

// Check whether subscriptions are available
const hasSubscriptions = graphql.hasSubscriptionSupport();

// Access the underlying Apollo Client if needed
const apolloClient = graphql.getClient();

// Close the WebSocket connection
await graphql.disconnect();
```

---

## Error Handling

All SDK errors extend `JanuaError`, which itself extends the native `Error` class.

### Error Classes

| Class | HTTP Status | Code | Notes |
|---|---|---|---|
| `JanuaError` | varies | `JANUA_ERROR` | Base class for all SDK errors |
| `AuthenticationError` | 401 | `AUTHENTICATION_ERROR` | Invalid credentials, expired token |
| `PermissionError` | 403 | `PERMISSION_ERROR` | Insufficient permissions |
| `ValidationError` | 400 | `VALIDATION_ERROR` | Invalid request parameters |
| `NotFoundError` | 404 | `NOT_FOUND` | Resource does not exist |
| `ConflictError` | 409 | `CONFLICT` | Duplicate resource (e.g., email taken) |
| `RateLimitError` | 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| `ServerError` | 5xx | `SERVER_ERROR` | Transient server-side failure |
| `NetworkError` | — | `NETWORK_ERROR` | Connection failure |
| `TokenError` | — | `TOKEN_ERROR` | Invalid or expired token |
| `ConfigurationError` | — | `CONFIGURATION_ERROR` | SDK misconfiguration |
| `MFAError` | — | `MFA_ERROR` | MFA challenge or setup failure |
| `WebhookError` | — | `WEBHOOK_ERROR` | Webhook delivery or config failure |
| `OAuthError` | — | `OAUTH_ERROR` | OAuth flow failure |
| `PasskeyError` | — | `PASSKEY_ERROR` | WebAuthn operation failure |

### Type Guards

Use these type guard functions to narrow errors in catch blocks:

```typescript
import {
  isAuthenticationError,
  isValidationError,
  isPermissionError,
  isNotFoundError,
  isRateLimitError,
  isNetworkError,
  isServerError,
  isJanuaError
} from '@janua/typescript-sdk';

try {
  await client.auth.signIn({ email: 'user@example.com', password: 'wrong' });
} catch (error) {
  if (isAuthenticationError(error)) {
    // error.message, error.statusCode === 401
    console.log('Invalid credentials:', error.message);

  } else if (isValidationError(error)) {
    // error.violations: Array<{ field: string, message: string }>
    error.violations?.forEach(v => console.log(`${v.field}: ${v.message}`));

  } else if (isRateLimitError(error)) {
    // error.retryAfter: number (seconds)
    console.log(`Rate limited. Retry after ${error.retryAfter}s`);

  } else if (isNetworkError(error)) {
    console.log('Network unavailable');

  } else if (isJanuaError(error)) {
    // Catch-all for any SDK error
    console.log(`SDK error [${error.code}]: ${error.message}`);
  }
}
```

### Error Properties

Every `JanuaError` instance exposes:

```typescript
error.message    // Human-readable description
error.code       // Machine-readable error code string
error.statusCode // HTTP status code if applicable
error.details    // Additional context from the server
error.toJSON()   // Serialize error to a plain object
```

Specialized properties by type:

- `ValidationError`: `.violations` — array of field-level validation failures
- `RateLimitError`: `.retryAfter` — seconds to wait before retrying
- `MFAError`: `.mfaRequired` — whether MFA must be completed; `.availableMethods`
- `OAuthError`: `.provider` — the OAuth provider name; `.oauthCode`
- `PasskeyError`: `.webauthnError` — the underlying WebAuthn error string

### ErrorHandler Utility

`ErrorHandler` provides static helpers for retry logic and user-facing messages:

```typescript
import { ErrorHandler } from '@janua/typescript-sdk';

// Check if an error should be retried (NetworkError, ServerError 5xx, RateLimitError)
if (ErrorHandler.isRetryable(error)) {
  const delay = ErrorHandler.getRetryDelay(error, attempt);
  await sleep(delay); // Implements exponential backoff with jitter
  // retry...
}

// Get a safe, user-presentable message
const message = ErrorHandler.getUserMessage(error);
```

---

## Utility Exports

### Base64Url

```typescript
import { Base64Url } from '@janua/typescript-sdk';
```

Utilities for encoding and decoding Base64URL strings (RFC 4648 Section 5), used internally for WebAuthn and PKCE.

### JwtUtils

```typescript
import { JwtUtils } from '@janua/typescript-sdk';
```

Helpers for decoding JWT payloads and checking expiry without a cryptographic library.

### Token Storage Classes

```typescript
import {
  LocalTokenStorage,
  SessionTokenStorage,
  MemoryTokenStorage,
  TokenManager
} from '@janua/typescript-sdk';
```

These classes implement the `TokenStorage` interface and can be used to build custom token management solutions.

```typescript
import type { TokenStorage } from '@janua/typescript-sdk';

class MyStorage implements TokenStorage {
  async getItem(key: string): Promise<string | null> { ... }
  async setItem(key: string, value: string): Promise<void> { ... }
  async removeItem(key: string): Promise<void> { ... }
}
```

### Other Utilities

| Export | Description |
|---|---|
| `DateUtils` | Date formatting and comparison helpers |
| `UrlUtils` | URL parsing and construction helpers |
| `ValidationUtils` | Input validation (email, password strength, etc.) |
| `EnvUtils` | Detect browser vs. Node.js environment |
| `RetryUtils` | Exponential backoff and retry helpers |
| `EventEmitter` | Typed event emitter (used internally by the client) |

---

## Configuration Presets

The SDK exports four ready-to-use configuration presets. Use `createClientWithPreset` to apply a preset with optional overrides.

```typescript
import { createClientWithPreset, presets } from '@janua/typescript-sdk';
```

| Preset | Key settings |
|---|---|
| `development` | `baseURL: 'http://localhost:8000'`, `debug: true`, `retryAttempts: 1` |
| `production` | `debug: false`, `timeout: 15000`, `retryAttempts: 3`, `autoRefreshTokens: true` |
| `browser` | `tokenStorage: 'localStorage'`, `autoRefreshTokens: true` |
| `server` | `tokenStorage: 'memory'`, `autoRefreshTokens: false` |

```typescript
// Production client targeting your API
const client = createClientWithPreset('production', {
  baseURL: 'https://api.janua.dev'
});

// Development client with all defaults
const devClient = createClientWithPreset('development');

// Access preset values directly
console.log(presets.production.timeout); // 15000
```

---

## TypeScript Types

### Core Types

```typescript
import type {
  UUID,              // string alias for UUIDs
  ISODateString,     // string alias for ISO 8601 dates
  Environment,       // 'production' | 'staging' | 'development'
  JanuaConfig,       // Client configuration interface
  User,              // User profile
  Session,           // Authentication session
  Organization,      // Organization record
  OrganizationMember,
  OrganizationInvitation,
  Passkey,
  WebhookEndpoint,
  WebhookEvent,
  WebhookDelivery,
  TokenResponse,     // { access_token, refresh_token, token_type, expires_in }
  AuthResponse,      // { user: User, tokens: TokenResponse }
  PaginatedResponse, // { items: T[], total: number, page: number, limit: number }
  ApiError           // Raw error shape from the API
} from '@janua/typescript-sdk';
```

### Auth Request Types

```typescript
import type {
  SignUpRequest,
  SignInRequest,
  RefreshTokenRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  MagicLinkRequest,
  MFAEnableRequest,
  MFAEnableResponse,
  MFAVerifyRequest,
  MFADisableRequest,
  MFAStatusResponse,
  MFABackupCodesResponse,
  OAuthProvidersResponse,
  LinkedAccountsResponse
} from '@janua/typescript-sdk';
```

### Enum Types

```typescript
import {
  UserStatus,         // ACTIVE | SUSPENDED | DELETED
  OrganizationRole,   // OWNER | ADMIN | MEMBER | VIEWER
  OAuthProvider,      // GOOGLE | GITHUB | MICROSOFT | DISCORD | TWITTER
  WebhookEventType    // USER_CREATED | USER_SIGNED_IN | ... (13 values)
} from '@janua/typescript-sdk';
```

### WebSocket Types

```typescript
import type {
  WebSocketConfig,
  WebSocketClientOptions,
  WebSocketMessage,
  WebSocketEventMap,
  WebSocketStatus
} from '@janua/typescript-sdk';
```

### GraphQL Types

```typescript
import type {
  GraphQLConfig,
  GraphQLQueryOptions,
  GraphQLMutationOptions,
  GraphQLSubscriptionOptions
} from '@janua/typescript-sdk';
```

### SDK Event Types

```typescript
import type {
  SdkEventMap,     // Map of event name to payload type
  SdkEventType,    // Union of all event name strings
  SdkEventHandler  // Generic handler function type
} from '@janua/typescript-sdk';
```

---

## Related Resources

- [API Reference](https://docs.janua.dev/api) — Complete REST API documentation
- [React SDK](../react-sdk/README.md) — React hooks and components built on this SDK
- [Vue SDK](../vue-sdk/README.md) — Vue 3 composables built on this SDK
- [Next.js SDK](../nextjs-sdk/README.md) — Next.js App Router integration
- [SDK Selection Guide](/docs/sdks/CHOOSE_YOUR_SDK.md) — Choosing the right SDK for your stack
- [Error Handling Guide](/docs/guides/ERROR_HANDLING_GUIDE.md) — Error codes and retry patterns
- [Changelog](../../docs/CHANGELOG.md) — Release history and migration guides

---

## License

AGPL-3.0. See the [LICENSE](../../LICENSE) file for details.

## Support

- Documentation: [docs.janua.dev](https://docs.janua.dev)
- GitHub Issues: [github.com/madfam-org/janua/issues](https://github.com/madfam-org/janua/issues)
- Email: support@janua.dev
