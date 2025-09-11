# @plinto/js

Official JavaScript SDK for Plinto - Modern authentication and user management platform.

## Installation

```bash
npm install @plinto/js
# or
yarn add @plinto/js
# or
pnpm add @plinto/js
```

## Quick Start

```javascript
import { PlintoClient } from '@plinto/js';

// Initialize the client
const plinto = new PlintoClient({
  appId: 'your-app-id',
  apiKey: 'your-api-key', // Optional, for server-side usage
});

// Sign up a new user
const { user, session, tokens } = await plinto.auth.signUp({
  email: 'user@example.com',
  password: 'secure-password',
  firstName: 'John',
  lastName: 'Doe',
});

// Sign in
const response = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'secure-password',
});

// Check authentication status
if (plinto.isAuthenticated()) {
  const user = plinto.getUser();
  console.log('Logged in as:', user.email);
}

// Sign out
await plinto.signOut();
```

## Features

- 🔐 **Complete Authentication**: Email/password, magic links, OAuth, passkeys
- 👤 **User Management**: Profiles, metadata, sessions
- 🏢 **Organizations**: Multi-tenant support with RBAC
- 🔑 **Passkeys/WebAuthn**: Passwordless authentication
- 🔒 **MFA Support**: TOTP and SMS-based 2FA
- 🌐 **OAuth Providers**: Google, GitHub, Microsoft, and more
- 📧 **Magic Links**: Passwordless email authentication
- 🔄 **Token Management**: Automatic refresh with JWT
- 💾 **Flexible Storage**: Browser, session, or custom storage adapters

## Documentation

For full documentation, visit [docs.plinto.dev](https://docs.plinto.dev)

## API Reference

### Client Initialization

```javascript
const plinto = new PlintoClient({
  appId: 'required-app-id',
  apiKey: 'optional-api-key',
  apiUrl: 'https://api.plinto.dev', // Optional custom URL
  debug: false, // Enable debug logging
});
```

### Authentication

```javascript
// Sign up
await plinto.auth.signUp({ email, password, firstName, lastName });

// Sign in
await plinto.auth.signIn({ email, password });

// Sign out
await plinto.auth.signOut();

// Magic link
await plinto.auth.sendMagicLink({ email });
await plinto.auth.signInWithMagicLink(token);

// OAuth
const { url } = await plinto.auth.getOAuthUrl({ 
  provider: 'google',
  redirectUrl: 'https://app.example.com/callback' 
});

// Passkeys
const options = await plinto.auth.beginPasskeyRegistration();
await plinto.auth.completePasskeyRegistration(credential);

// MFA
const { qrCode } = await plinto.auth.enableMFA('totp');
await plinto.auth.confirmMFA(code);
```

### User Management

```javascript
// Get current user
const user = await plinto.users.getUser();

// Update user
await plinto.users.updateCurrentUser({ 
  firstName: 'Jane',
  metadata: { theme: 'dark' }
});

// Upload profile image
await plinto.users.uploadProfileImage(file);

// User sessions
const sessions = await plinto.users.getUserSessions();
await plinto.users.revokeSession(sessionId);
```

### Organizations

```javascript
// Create organization
const org = await plinto.organizations.createOrganization({
  name: 'Acme Inc',
  slug: 'acme',
});

// Invite members
await plinto.organizations.inviteMember(orgId, {
  email: 'member@example.com',
  role: 'member',
});

// Manage roles
const roles = await plinto.organizations.getOrganizationRoles(orgId);
await plinto.organizations.updateMember(orgId, userId, { role: 'admin' });
```

## TypeScript Support

This SDK is written in TypeScript and provides full type definitions.

```typescript
import { PlintoClient, User, Session } from '@plinto/js';
import type { SignUpRequest, PlintoConfig } from '@plinto/js';

const config: PlintoConfig = {
  appId: 'your-app-id',
};

const plinto = new PlintoClient(config);

const signUp = async (data: SignUpRequest) => {
  const response = await plinto.auth.signUp(data);
  const user: User = response.user;
  const session: Session = response.session;
};
```

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Node.js Support

- Node.js 14+
- Works in both CommonJS and ESM environments

## License

MIT

## Support

- Documentation: [docs.plinto.dev](https://docs.plinto.dev)
- Issues: [GitHub Issues](https://github.com/plinto/plinto/issues)
- Discord: [Join our community](https://discord.gg/plinto)