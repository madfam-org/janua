# @janua/typescript-sdk

[![npm version](https://badge.fury.io/js/@janua%2Ftypescript-sdk.svg)](https://badge.fury.io/js/@janua%2Ftypescript-sdk)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-blue.svg)](https://www.typescriptlang.org/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Official TypeScript SDK for [Janua](https://janua.dev) - Enterprise-grade authentication and user management platform.

## Features

- 🔐 **Complete Authentication System** - Login, registration, password reset, email verification
- 👥 **User Management** - Profile management, account settings, multi-tenancy
- 🛡️ **Multi-Factor Authentication** - TOTP, backup codes, passkey support
- 🏢 **Organization Management** - Team management, role-based access control
- 🔗 **OAuth Integration** - Support for Google, GitHub, Microsoft, and custom providers
- 📱 **Session Management** - Device tracking, session revocation, security monitoring
- 🚀 **TypeScript-First** - Full type safety with comprehensive TypeScript definitions
- ⚡ **Automatic Retries** - Built-in retry logic with exponential backoff
- 🔄 **Token Management** - Automatic token refresh, secure storage options
- 🌐 **Cross-Platform** - Works in browsers, Node.js, React Native, and other JavaScript environments

## Installation

```bash
npm install @janua/typescript-sdk
```

## Quick Start

### Basic Setup

```typescript
import { JanuaClient, createClient } from '@janua/typescript-sdk';

// Create client with API key (server-side)
const client = createClient({
  base_url: 'https://api.janua.dev',
  api_key: 'your-api-key',
  debug: false
});

// Or create client for user authentication (client-side)
const client = new JanuaClient({
  base_url: 'https://api.janua.dev',
  authentication_method: AuthenticationMethod.JWT_TOKEN
});
```

### User Authentication

```typescript
import { JanuaClient, AuthenticationError } from '@janua/typescript-sdk';

const client = new JanuaClient({
  base_url: 'https://api.janua.dev'
});

try {
  // Login user
  const response = await client.login({
    email: 'user@example.com',
    password: 'secure-password',
    remember_me: true
  });

  console.log('Welcome:', response.data.user.name);
  console.log('Token expires in:', response.data.token.expires_in, 'seconds');

  // Get current user profile
  const profile = await client.getCurrentUser();
  console.log('User profile:', profile.data);

  // Check authentication status
  const isAuthenticated = await client.isAuthenticated();
  console.log('Is authenticated:', isAuthenticated);

} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Login failed:', error.message);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

### User Registration

```typescript
try {
  const response = await client.register({
    email: 'newuser@example.com',
    password: 'secure-password',
    name: 'John Doe',
    terms_accepted: true
  });

  console.log('Registration successful:', response.data.user);

  // Email verification will be sent automatically
  console.log('Please check your email for verification');

} catch (error) {
  if (error instanceof ValidationError) {
    // Handle validation errors
    error.validation_errors.forEach(err => {
      console.error(`${err.field}: ${err.message}`);
    });
  }
}
```

### Organization Management

```typescript
// Create organization
const org = await client.createOrganization({
  name: 'Acme Corp',
  slug: 'acme-corp',
  description: 'Leading provider of widgets',
  website_url: 'https://acme.com'
});

// List user's organizations
const organizations = await client.getOrganizations();
console.log('Organizations:', organizations.data);

// Update organization
await client.updateOrganization(org.data.id, {
  description: 'Updated description'
});
```

### Multi-Factor Authentication

```typescript
// Set up MFA for current user
const mfaSetup = await client.setupMFA();
console.log('MFA Secret:', mfaSetup.data.secret);
console.log('QR Code URL:', mfaSetup.data.qr_code_url);
console.log('Backup codes:', mfaSetup.data.backup_codes);

// Verify MFA setup
await client.verifyMFA({
  code: '123456' // Code from authenticator app
});

// Later, during login, verify MFA
await client.verifyMFA({
  code: '654321'
});

// Generate new backup codes
const backupCodes = await client.generateBackupCodes();
console.log('New backup codes:', backupCodes.data.backup_codes);
```

### Passkey Authentication

```typescript
// Register a new passkey
const passkeyRegistration = await client.registerPasskey('My MacBook');

// Authenticate with passkey (WebAuthn)
const authResult = await client.authenticateWithPasskey(credential);
console.log('Authenticated user:', authResult.data.user);

// List user's passkeys
const passkeys = await client.getPasskeys();
console.log('Registered passkeys:', passkeys.data);
```

### Session Management

```typescript
// Get current session
const currentSession = await client.getCurrentSession();
console.log('Current session:', currentSession.data);

// List all user sessions
const sessions = await client.getSessions();
sessions.data.forEach(session => {
  console.log(`Session ${session.id}:`, {
    ip: session.ip_address,
    device: session.user_agent,
    current: session.is_current,
    lastActivity: session.last_activity
  });
});

// Revoke a specific session
await client.revokeSession('session-id');

// Revoke all other sessions (keep current)
await client.revokeAllSessions();
```

### OAuth Integration

```typescript
// Get available OAuth providers
const providers = await client.getOAuthProviders();
console.log('Available providers:', providers.data);

// Initiate OAuth flow
const oauth = await client.initiateOAuth('google', 'https://yourapp.com/callback');
console.log('Redirect to:', oauth.data.authorization_url);

// Complete OAuth flow (in your callback handler)
const result = await client.completeOAuth('google', authorizationCode, state);
console.log('OAuth user:', result.data.user);
```

## Advanced Usage

### Custom Token Storage

```typescript
import { JanuaClient, TokenStorage } from '@janua/typescript-sdk';

// Implement custom token storage (e.g., React Native SecureStore)
class SecureTokenStorage implements TokenStorage {
  async getToken(key: string): Promise<string | null> {
    // Your secure storage implementation
    return await SecureStore.getItemAsync(key);
  }

  async setToken(key: string, value: string, expires_at?: Date): Promise<void> {
    // Your secure storage implementation
    await SecureStore.setItemAsync(key, JSON.stringify({
      value,
      expires_at: expires_at?.toISOString()
    }));
  }

  async removeToken(key: string): Promise<void> {
    await SecureStore.deleteItemAsync(key);
  }

  async clear(): Promise<void> {
    // Clear all Janua tokens
  }
}

const client = new JanuaClient({
  base_url: 'https://api.janua.dev',
  // Custom token storage will be used automatically
});
```

### Error Handling

```typescript
import {
  JanuaClient,
  APIError,
  AuthenticationError,
  ValidationError,
  RateLimitError,
  NetworkError
} from '@janua/typescript-sdk';

try {
  await client.login({ email: 'user@example.com', password: 'wrong' });
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Authentication failed:', error.message);
  } else if (error instanceof ValidationError) {
    console.error('Validation errors:');
    error.validation_errors.forEach(err => {
      console.error(`  ${err.field}: ${err.message}`);
    });
  } else if (error instanceof RateLimitError) {
    console.error('Rate limited. Retry after:', error.retry_after, 'seconds');
  } else if (error instanceof NetworkError) {
    console.error('Network error:', error.message);
  } else if (error instanceof APIError) {
    console.error('API error:', error.status_code, error.message);
  }
}
```

### Configuration Options

```typescript
import { JanuaClient, AuthenticationMethod } from '@janua/typescript-sdk';

const client = new JanuaClient({
  base_url: 'https://api.janua.dev',
  api_key: 'optional-api-key',
  authentication_method: AuthenticationMethod.JWT_TOKEN,
  timeout: 30000, // 30 seconds
  retry_config: {
    max_retries: 3,
    initial_delay_ms: 1000,
    max_delay_ms: 30000,
    backoff_factor: 2,
    retry_on_status_codes: [429, 502, 503, 504]
  },
  user_agent: 'MyApp/1.0.0',
  debug: process.env.NODE_ENV === 'development'
});
```

## Admin Operations

```typescript
// Admin methods require appropriate permissions
try {
  // List all users (paginated)
  const users = await client.getUsers(1, 20);
  console.log('Total users:', users.pagination.total);

  // Get specific user
  const user = await client.getUser('user-id');
  console.log('User details:', user.data);

  // Suspend user
  await client.suspendUser('user-id', 'Policy violation');

  // Unsuspend user
  await client.unsuspendUser('user-id');

} catch (error) {
  if (error instanceof AuthorizationError) {
    console.error('Insufficient permissions for admin operations');
  }
}
```

## React Integration

```tsx
import React, { useEffect, useState } from 'react';
import { JanuaClient, UserProfile } from '@janua/typescript-sdk';

const client = new JanuaClient({
  base_url: 'https://api.janua.dev'
});

function UserDashboard() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      try {
        const isAuth = await client.isAuthenticated();
        if (isAuth) {
          const response = await client.getCurrentUser();
          setUser(response.data);
        }
      } catch (error) {
        console.error('Failed to load user:', error);
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>Please log in</div>;

  return (
    <div>
      <h1>Welcome, {user.name}!</h1>
      <p>Email: {user.email}</p>
      <button onClick={() => client.logout()}>
        Logout
      </button>
    </div>
  );
}
```

## TypeScript Support

The SDK is built with TypeScript and provides comprehensive type definitions:

```typescript
import { JanuaClient, SDKDataResponse, UserProfile } from '@janua/typescript-sdk';

const client = new JanuaClient({ base_url: 'https://api.janua.dev' });

// Full type safety
const response: SDKDataResponse<UserProfile> = await client.getCurrentUser();
const user: UserProfile = response.data;

// Type-safe error handling
try {
  await client.login({ email: 'test', password: 'test' });
} catch (error) {
  if (error instanceof ValidationError) {
    // TypeScript knows this has validation_errors property
    error.validation_errors.forEach(err => {
      console.log(err.field, err.message);
    });
  }
}
```

## Environment Variables

Set these environment variables for configuration:

```bash
JANUA_BASE_URL=https://api.janua.dev
JANUA_API_KEY=your-api-key
JANUA_DEBUG=true
```

## Testing

```bash
npm test
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

AGPL-3.0 License. See [LICENSE](LICENSE) for details.

## Support

- 📖 [Documentation](https://docs.janua.dev)
- 💬 [Discord Community](https://discord.gg/janua)
- 🐛 [Issue Tracker](https://github.com/madfam-io/janua/issues)
- 📧 [Email Support](mailto:support@janua.dev)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.