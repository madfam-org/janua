# SDK Documentation

Official Software Development Kits (SDKs) for integrating Janua's authentication and authorization platform.

## Available SDKs

- **[TypeScript/JavaScript SDK](#typescript-sdk)** - For Node.js, React, Vue, Angular applications
- **[React SDK](#react-sdk)** - React-specific hooks and components
- **[Python SDK](#python-sdk)** - For Python applications and APIs
- **[Vue SDK](#vue-sdk)** - Vue.js-specific composables and components
- **[Next.js SDK](#nextjs-sdk)** - Server and client components for Next.js

## Quick Start

### TypeScript SDK

```bash
npm install @janua/sdk
```

```typescript
import { JanuaClient } from '@janua/sdk';

const janua = new JanuaClient({
  apiKey: process.env.JANUA_API_KEY,
  baseUrl: 'https://api.janua.dev'
});

// Register a new user
const user = await janua.auth.register({
  email: 'user@example.com',
  password: 'SecurePassword123!',
  firstName: 'John',
  lastName: 'Doe'
});

// Login user
const session = await janua.auth.login({
  email: 'user@example.com',
  password: 'SecurePassword123!'
});
```

### React SDK

```bash
npm install @janua/react-sdk
```

```jsx
import { JanuaProvider, useAuth } from '@janua/react-sdk';

function App() {
  return (
    <JanuaProvider apiKey="your-api-key">
      <AuthenticatedApp />
    </JanuaProvider>
  );
}

function AuthenticatedApp() {
  const { user, login, logout, loading } = useAuth();

  if (loading) return <div>Loading...</div>;

  if (!user) {
    return (
      <button onClick={() => login({ email: 'user@example.com', password: 'password' })}>
        Login
      </button>
    );
  }

  return (
    <div>
      <p>Welcome, {user.firstName}!</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
}
```

### Python SDK

```bash
pip install janua-python
```

```python
from janua import JanuaClient

janua = JanuaClient(
    api_key=os.getenv('JANUA_API_KEY'),
    base_url='https://api.janua.dev'
)

# Register a new user
user = janua.auth.register(
    email='user@example.com',
    password='SecurePassword123!',
    first_name='John',
    last_name='Doe'
)

# Login user
session = janua.auth.login(
    email='user@example.com',
    password='SecurePassword123!'
)
```

---

# TypeScript SDK

## Installation

```bash
npm install @janua/sdk
# or
yarn add @janua/sdk
# or
pnpm add @janua/sdk
```

## Configuration

```typescript
import { JanuaClient } from '@janua/sdk';

const janua = new JanuaClient({
  apiKey: process.env.JANUA_API_KEY,
  baseUrl: 'https://api.janua.dev', // Optional, defaults to production
  timeout: 10000, // Optional, request timeout in ms
  retries: 3, // Optional, number of retries for failed requests
  organizationId: 'org_123', // Optional, for multi-tenant applications
});
```

## Authentication Methods

### Email/Password Authentication

```typescript
// Register new user
const registerResult = await janua.auth.register({
  email: 'user@example.com',
  password: 'SecurePassword123!',
  firstName: 'John',
  lastName: 'Doe',
  metadata: {
    source: 'web_app',
    utm_campaign: 'signup_flow'
  }
});

// Login user
const loginResult = await janua.auth.login({
  email: 'user@example.com',
  password: 'SecurePassword123!',
  deviceInfo: {
    userAgent: navigator.userAgent,
    ipAddress: '192.168.1.1',
    deviceFingerprint: 'fp_abc123'
  }
});

// Handle MFA if required
if (loginResult.requiresMfa) {
  const mfaResult = await janua.auth.completeMfa({
    tempToken: loginResult.tempToken,
    method: 'totp',
    code: '123456'
  });
}

// Logout
await janua.auth.logout({
  refreshToken: session.refreshToken
});
```

### Magic Link Authentication

```typescript
// Send magic link
await janua.auth.sendMagicLink({
  email: 'user@example.com',
  redirectUrl: 'https://app.example.com/auth/callback',
  expiresIn: 3600 // 1 hour
});

// Verify magic link (typically called from callback page)
const verifyResult = await janua.auth.verifyMagicLink({
  token: 'ml_token_from_url'
});
```

### Passkeys Authentication

```typescript
// Start passkey registration
const registrationOptions = await janua.auth.passkeys.beginRegistration({
  displayName: 'John Doe',
  authenticatorSelection: {
    authenticatorAttachment: 'platform',
    userVerification: 'required'
  }
});

// Complete registration with WebAuthn API response
const registrationResult = await janua.auth.passkeys.completeRegistration({
  id: credential.id,
  rawId: credential.rawId,
  response: credential.response,
  type: credential.type
});

// Start passkey authentication
const authOptions = await janua.auth.passkeys.beginAuthentication({
  email: 'user@example.com'
});

// Complete authentication
const authResult = await janua.auth.passkeys.completeAuthentication({
  id: credential.id,
  rawId: credential.rawId,
  response: credential.response,
  type: credential.type
});
```

### OAuth Authentication

```typescript
// Get OAuth providers
const providers = await janua.auth.oauth.getProviders();

// Initiate OAuth flow
const authUrl = janua.auth.oauth.getAuthUrl('google', {
  redirectUri: 'https://app.example.com/auth/callback',
  state: 'csrf_state_token',
  scope: 'openid profile email'
});

// Handle OAuth callback
const oauthResult = await janua.auth.oauth.handleCallback('google', {
  code: 'oauth_code_from_callback',
  state: 'csrf_state_token'
});
```

### Session Management

```typescript
// Refresh access token
const refreshResult = await janua.auth.refresh({
  refreshToken: 'rt_refresh_token'
});

// Get current user
const user = await janua.users.me();

// List user sessions
const sessions = await janua.sessions.list();

// Revoke session
await janua.sessions.revoke('sess_session_id');

// Revoke all other sessions
await janua.sessions.revokeAll();
```

## User Management

```typescript
// Get current user profile
const user = await janua.users.me();

// Update user profile
const updatedUser = await janua.users.update({
  firstName: 'Jane',
  lastName: 'Smith',
  phoneNumber: '+1234567890',
  metadata: {
    preferences: {
      theme: 'dark',
      language: 'en'
    }
  }
});

// Change password
await janua.users.changePassword({
  currentPassword: 'OldPassword123!',
  newPassword: 'NewPassword456!',
  logoutOtherSessions: true
});

// Send email verification
await janua.users.sendEmailVerification();

// Verify email
await janua.users.verifyEmail({
  token: 'verification_token'
});

// Delete account
await janua.users.deleteAccount({
  password: 'UserPassword123!',
  confirmation: 'DELETE'
});
```

## Multi-Factor Authentication

```typescript
// Enable TOTP MFA
const totpSecret = await janua.mfa.enableTotp();
console.log('TOTP Secret:', totpSecret.secret);
console.log('QR Code:', totpSecret.qrCode);

// Verify TOTP setup
await janua.mfa.verifyTotp({
  code: '123456'
});

// Enable SMS MFA
await janua.mfa.enableSms({
  phoneNumber: '+1234567890'
});

// Enable Email MFA
await janua.mfa.enableEmail();

// Generate backup codes
const backupCodes = await janua.mfa.generateBackupCodes();

// Disable MFA
await janua.mfa.disable({
  method: 'totp',
  code: '123456'
});
```

## Organization Management

```typescript
// List user organizations
const organizations = await janua.organizations.list();

// Create organization
const newOrg = await janua.organizations.create({
  name: 'My Organization',
  slug: 'my-org',
  domain: 'myorg.com',
  settings: {
    allowedDomains: ['myorg.com'],
    ssoRequired: false,
    mfaRequired: true
  }
});

// Get organization details
const org = await janua.organizations.get('org_123');

// Update organization
const updatedOrg = await janua.organizations.update('org_123', {
  name: 'Updated Organization Name',
  settings: {
    mfaRequired: true,
    sessionTimeout: 14400
  }
});

// List organization members
const members = await janua.organizations.listMembers('org_123', {
  limit: 50,
  role: 'admin'
});

// Invite user to organization
const invitation = await janua.organizations.inviteMember('org_123', {
  email: 'newuser@example.com',
  role: 'member',
  permissions: ['users:read'],
  message: 'Welcome to our organization!'
});

// Update member role
await janua.organizations.updateMemberRole('org_123', 'usr_456', {
  role: 'admin',
  permissions: ['users:read', 'users:write', 'billing:read']
});

// Remove member
await janua.organizations.removeMember('org_123', 'usr_456');
```

## Role-Based Access Control (RBAC)

```typescript
// List roles
const roles = await janua.rbac.listRoles();

// Create custom role
const customRole = await janua.rbac.createRole({
  name: 'Marketing Manager',
  description: 'Manage marketing content and campaigns',
  permissions: [
    'content:read',
    'content:write',
    'analytics:read',
    'campaigns:read',
    'campaigns:write'
  ]
});

// List all permissions
const permissions = await janua.rbac.listPermissions();

// Check user permissions
const permissionCheck = await janua.rbac.checkPermissions('usr_123', {
  permissions: ['users:read', 'billing:write'],
  context: {
    organizationId: 'org_abc123',
    resourceId: 'res_xyz789'
  }
});

// Assign role to user
await janua.rbac.assignRole('usr_123', 'role_admin');

// Remove role from user
await janua.rbac.removeRole('usr_123', 'role_admin');
```

## Enterprise Features

### Audit Logging

```typescript
// Query audit events
const auditEvents = await janua.audit.queryEvents({
  startDate: '2025-01-01T00:00:00Z',
  endDate: '2025-01-15T23:59:59Z',
  eventType: 'user.login',
  userId: 'usr_123',
  limit: 100
});

// Verify audit chain integrity
const verificationResult = await janua.audit.verifyChain({
  startEventId: 'evt_start',
  endEventId: 'evt_end'
});
```

### SCIM 2.0 Provisioning

```typescript
// Create SCIM user
const scimUser = await janua.scim.createUser({
  schemas: ['urn:ietf:params:scim:schemas:core:2.0:User'],
  userName: 'john.doe@acme.com',
  name: {
    givenName: 'John',
    familyName: 'Doe'
  },
  emails: [{
    value: 'john.doe@acme.com',
    type: 'work',
    primary: true
  }],
  active: true
});

// Update SCIM user
const updatedScimUser = await janua.scim.updateUser('usr_123', {
  active: false
});

// Delete SCIM user
await janua.scim.deleteUser('usr_123');

// List SCIM users
const scimUsers = await janua.scim.listUsers({
  startIndex: 1,
  count: 50,
  filter: 'userName eq "john.doe@acme.com"'
});
```

### Webhooks

```typescript
// Create webhook
const webhook = await janua.webhooks.create({
  url: 'https://api.example.com/webhooks/janua',
  events: ['user.created', 'user.updated', 'user.deleted'],
  secret: 'whsec_abc123',
  active: true
});

// List webhooks
const webhooks = await janua.webhooks.list();

// Update webhook
const updatedWebhook = await janua.webhooks.update('wh_123', {
  events: ['user.created', 'user.deleted'],
  active: false
});

// Delete webhook
await janua.webhooks.delete('wh_123');

// Verify webhook signature (server-side)
import crypto from 'crypto';

function verifyWebhookSignature(
  payload: string,
  signature: string,
  secret: string,
  timestamp: string
): boolean {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(timestamp + '.' + payload)
    .digest('hex');
  
  return `sha256=${expectedSignature}` === signature;
}
```

## Error Handling

```typescript
import { JanuaError } from '@janua/sdk';

try {
  const user = await janua.auth.login({
    email: 'user@example.com',
    password: 'wrongpassword'
  });
} catch (error) {
  if (error instanceof JanuaError) {
    console.log('Error Code:', error.code);
    console.log('Error Message:', error.message);
    console.log('HTTP Status:', error.statusCode);
    console.log('Request ID:', error.requestId);
    
    // Handle specific errors
    switch (error.code) {
      case 'invalid_credentials':
        // Show login error
        break;
      case 'mfa_required':
        // Redirect to MFA flow
        break;
      case 'rate_limit_exceeded':
        // Show rate limit message
        break;
      default:
        // Handle generic error
    }
  }
}
```

## TypeScript Types

```typescript
interface JanuaUser {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  emailVerified: boolean;
  phoneNumber?: string;
  phoneVerified: boolean;
  avatar?: string;
  mfaEnabled: boolean;
  createdAt: string;
  lastActiveAt: string;
  metadata?: Record<string, any>;
}

interface JanuaSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
  deviceId?: string;
}

interface JanuaOrganization {
  id: string;
  name: string;
  slug: string;
  domain?: string;
  logo?: string;
  plan: 'free' | 'pro' | 'enterprise';
  userRole: string;
  userPermissions: string[];
  createdAt: string;
  memberCount: number;
}

interface JanuaError extends Error {
  code: string;
  statusCode: number;
  requestId: string;
  details?: any;
}
```

---

# React SDK

## Installation

```bash
npm install @janua/react-sdk
```

## Setup

```jsx
import React from 'react';
import { JanuaProvider } from '@janua/react-sdk';

function App() {
  return (
    <JanuaProvider
      apiKey={process.env.REACT_APP_JANUA_API_KEY}
      baseUrl="https://api.janua.dev"
      organizationId="org_123" // Optional for multi-tenant
    >
      <YourApp />
    </JanuaProvider>
  );
}
```

## Authentication Hooks

### useAuth

```jsx
import { useAuth } from '@janua/react-sdk';

function AuthComponent() {
  const { 
    user, 
    loading, 
    error,
    login, 
    register, 
    logout,
    refreshToken 
  } = useAuth();

  const handleLogin = async () => {
    try {
      await login({
        email: 'user@example.com',
        password: 'password123'
      });
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  const handleRegister = async () => {
    try {
      await register({
        email: 'user@example.com',
        password: 'password123',
        firstName: 'John',
        lastName: 'Doe'
      });
    } catch (error) {
      console.error('Registration failed:', error);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      {user ? (
        <div>
          <p>Welcome, {user.firstName}!</p>
          <button onClick={logout}>Logout</button>
        </div>
      ) : (
        <div>
          <button onClick={handleLogin}>Login</button>
          <button onClick={handleRegister}>Register</button>
        </div>
      )}
    </div>
  );
}
```

### useMagicLink

```jsx
import { useMagicLink } from '@janua/react-sdk';

function MagicLinkComponent() {
  const { sendMagicLink, loading, error, sent } = useMagicLink();

  const handleSendMagicLink = async () => {
    await sendMagicLink({
      email: 'user@example.com',
      redirectUrl: window.location.origin + '/auth/callback'
    });
  };

  return (
    <div>
      <button onClick={handleSendMagicLink} disabled={loading}>
        {loading ? 'Sending...' : 'Send Magic Link'}
      </button>
      {sent && <p>Magic link sent! Check your email.</p>}
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

### usePasskey

```jsx
import { usePasskey } from '@janua/react-sdk';

function PasskeyComponent() {
  const {
    register,
    authenticate,
    isLoading: loading,
    error,
    isSupported: supported
  } = usePasskey();

  if (!supported) {
    return <p>Passkeys not supported in this browser</p>;
  }

  const handleRegister = async () => {
    try {
      await registerPasskey({
        displayName: 'John Doe'
      });
    } catch (error) {
      console.error('Passkey registration failed:', error);
    }
  };

  const handleAuthenticate = async () => {
    try {
      await authenticateWithPasskey({
        email: 'user@example.com'
      });
    } catch (error) {
      console.error('Passkey authentication failed:', error);
    }
  };

  return (
    <div>
      <button onClick={handleRegister} disabled={loading}>
        Register Passkey
      </button>
      <button onClick={handleAuthenticate} disabled={loading}>
        Login with Passkey
      </button>
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

### useOAuth

```jsx
import { useOAuth } from '@janua/react-sdk';

function OAuthComponent() {
  const { providers, loginWithProvider, loading, error } = useOAuth();

  const handleOAuthLogin = async (provider) => {
    await loginWithProvider(provider, {
      redirectUri: window.location.origin + '/auth/callback'
    });
  };

  return (
    <div>
      {providers.map(provider => (
        <button
          key={provider.id}
          onClick={() => handleOAuthLogin(provider.id)}
          disabled={loading}
        >
          Login with {provider.name}
        </button>
      ))}
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

## User Management Hooks

### useUser

```jsx
import { useUser } from '@janua/react-sdk';

function UserProfile() {
  const { 
    user, 
    updateUser, 
    changePassword,
    deleteAccount,
    loading, 
    error 
  } = useUser();

  const handleUpdateProfile = async () => {
    await updateUser({
      firstName: 'Jane',
      lastName: 'Smith'
    });
  };

  const handleChangePassword = async () => {
    await changePassword({
      currentPassword: 'old-password',
      newPassword: 'new-password'
    });
  };

  return (
    <div>
      {user && (
        <div>
          <h2>{user.firstName} {user.lastName}</h2>
          <p>{user.email}</p>
          <button onClick={handleUpdateProfile}>Update Profile</button>
          <button onClick={handleChangePassword}>Change Password</button>
        </div>
      )}
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

### useMFA

```jsx
import { useMFA } from '@janua/react-sdk';

function MFAComponent() {
  const { 
    enableTotp,
    enableSms,
    disableMfa,
    generateBackupCodes,
    totpSecret,
    backupCodes,
    loading,
    error 
  } = useMFA();

  const handleEnableTotp = async () => {
    await enableTotp();
  };

  const handleVerifyTotp = async (code) => {
    await verifyTotp({ code });
  };

  return (
    <div>
      <button onClick={handleEnableTotp} disabled={loading}>
        Enable TOTP
      </button>
      
      {totpSecret && (
        <div>
          <p>Secret: {totpSecret.secret}</p>
          <img src={totpSecret.qrCode} alt="TOTP QR Code" />
          <input 
            type="text" 
            placeholder="Enter TOTP code"
            onBlur={(e) => handleVerifyTotp(e.target.value)}
          />
        </div>
      )}
      
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

## Organization Hooks

### useOrganization

```jsx
import { useOrganization } from '@janua/react-sdk';

function OrganizationComponent() {
  const { 
    organizations,
    currentOrganization,
    createOrganization,
    switchOrganization,
    loading,
    error 
  } = useOrganization();

  const handleCreateOrg = async () => {
    await createOrganization({
      name: 'New Organization',
      slug: 'new-org'
    });
  };

  return (
    <div>
      <h2>Organizations</h2>
      {organizations.map(org => (
        <div key={org.id}>
          <p>{org.name} ({org.userRole})</p>
          <button onClick={() => switchOrganization(org.id)}>
            Switch
          </button>
        </div>
      ))}
      <button onClick={handleCreateOrg}>Create Organization</button>
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

### useMembers

```jsx
import { useMembers } from '@janua/react-sdk';

function MembersComponent({ organizationId }) {
  const { 
    members,
    inviteMember,
    updateMemberRole,
    removeMember,
    loading,
    error 
  } = useMembers(organizationId);

  const handleInvite = async () => {
    await inviteMember({
      email: 'newuser@example.com',
      role: 'member'
    });
  };

  return (
    <div>
      <h2>Members</h2>
      {members.map(member => (
        <div key={member.id}>
          <p>{member.firstName} {member.lastName} ({member.role})</p>
          <button 
            onClick={() => updateMemberRole(member.id, { role: 'admin' })}
          >
            Make Admin
          </button>
          <button onClick={() => removeMember(member.id)}>
            Remove
          </button>
        </div>
      ))}
      <button onClick={handleInvite}>Invite Member</button>
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

## Permission Components

### ProtectedRoute

```jsx
import { ProtectedRoute } from '@janua/react-sdk';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/admin" 
          element={
            <ProtectedRoute 
              permissions={['admin:read', 'admin:write']}
              fallback={<UnauthorizedPage />}
            >
              <AdminPanel />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </Router>
  );
}
```

### PermissionGuard

```jsx
import { PermissionGuard } from '@janua/react-sdk';

function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>
      
      <PermissionGuard permissions={['users:read']}>
        <UsersList />
      </PermissionGuard>
      
      <PermissionGuard 
        permissions={['billing:read']}
        fallback={<p>You don't have billing access</p>}
      >
        <BillingSection />
      </PermissionGuard>
    </div>
  );
}
```

### HasPermission

```jsx
import { HasPermission } from '@janua/react-sdk';

function UserRow({ user }) {
  return (
    <tr>
      <td>{user.name}</td>
      <td>{user.email}</td>
      <HasPermission permissions={['users:write']}>
        <td>
          <button>Edit</button>
        </td>
      </HasPermission>
      <HasPermission permissions={['users:delete']}>
        <td>
          <button>Delete</button>
        </td>
      </HasPermission>
    </tr>
  );
}
```

## Form Components

### LoginForm

```jsx
import { LoginForm } from '@janua/react-sdk';

function LoginPage() {
  return (
    <div>
      <h1>Login</h1>
      <LoginForm
        onSuccess={(user) => {
          console.log('Login successful:', user);
          // Redirect to dashboard
        }}
        onError={(error) => {
          console.error('Login failed:', error);
        }}
        showRememberMe={true}
        showForgotPassword={true}
      />
    </div>
  );
}
```

### RegisterForm

```jsx
import { RegisterForm } from '@janua/react-sdk';

function RegisterPage() {
  return (
    <div>
      <h1>Create Account</h1>
      <RegisterForm
        onSuccess={(user) => {
          console.log('Registration successful:', user);
          // Show welcome message
        }}
        onError={(error) => {
          console.error('Registration failed:', error);
        }}
        requireFirstName={true}
        requireLastName={true}
        showTermsCheckbox={true}
      />
    </div>
  );
}
```

### MFASetupForm

```jsx
import { MFASetupForm } from '@janua/react-sdk';

function MFASetupPage() {
  return (
    <div>
      <h1>Setup Multi-Factor Authentication</h1>
      <MFASetupForm
        methods={['totp', 'sms']}
        onComplete={() => {
          console.log('MFA setup complete');
          // Redirect to dashboard
        }}
        onError={(error) => {
          console.error('MFA setup failed:', error);
        }}
      />
    </div>
  );
}
```

---

# Python SDK

## Installation

```bash
pip install janua-python
# or
poetry add janua-python
```

## Configuration

```python
import os
from janua import JanuaClient

janua = JanuaClient(
    api_key=os.getenv('JANUA_API_KEY'),
    base_url='https://api.janua.dev',  # Optional
    timeout=30,  # Optional, request timeout in seconds
    retries=3,  # Optional, number of retries
    organization_id='org_123',  # Optional, for multi-tenant
)
```

## Authentication

### Email/Password Authentication

```python
# Register new user
user = janua.auth.register(
    email='user@example.com',
    password='SecurePassword123!',
    first_name='John',
    last_name='Doe',
    metadata={
        'source': 'web_app',
        'utm_campaign': 'signup_flow'
    }
)

# Login user
session = janua.auth.login(
    email='user@example.com',
    password='SecurePassword123!',
    device_info={
        'user_agent': 'Python SDK',
        'ip_address': '192.168.1.1'
    }
)

# Handle MFA if required
if session.get('requires_mfa'):
    mfa_result = janua.auth.complete_mfa(
        temp_token=session['temp_token'],
        method='totp',
        code='123456'
    )

# Logout
janua.auth.logout(refresh_token=session['refresh_token'])
```

### Magic Link Authentication

```python
# Send magic link
janua.auth.send_magic_link(
    email='user@example.com',
    redirect_url='https://app.example.com/auth/callback',
    expires_in=3600
)

# Verify magic link
result = janua.auth.verify_magic_link(token='ml_token_from_url')
```

### Passkeys Authentication

```python
# Start passkey registration
registration_options = janua.auth.passkeys.begin_registration(
    display_name='John Doe',
    authenticator_selection={
        'authenticator_attachment': 'platform',
        'user_verification': 'required'
    }
)

# Complete registration (with WebAuthn credential data)
registration_result = janua.auth.passkeys.complete_registration(
    id='cred_abc123',
    raw_id='Y3JlZF9hYmMxMjM=',
    response={
        'attestation_object': 'o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YVjE...',
        'client_data_json': 'eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIiwiY2hhbGxlbmdl...'
    },
    type='public-key'
)

# Start passkey authentication
auth_options = janua.auth.passkeys.begin_authentication(
    email='user@example.com'
)

# Complete authentication
auth_result = janua.auth.passkeys.complete_authentication(
    id='cred_abc123',
    raw_id='Y3JlZF9hYmMxMjM=',
    response={
        'authenticator_data': 'SZYN5YgOjGh0NBcPZHZgW4_krrmihjLHmVzzuoMdl2M=',
        'client_data_json': 'eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdl...',
        'signature': 'MEUCIQDNRVdMRY_-IG0qp7QMc8CJYGAKUYQxX...'
    },
    type='public-key'
)
```

### Session Management

```python
# Refresh token
refresh_result = janua.auth.refresh(refresh_token='rt_refresh_token')

# List sessions
sessions = janua.sessions.list()

# Revoke session
janua.sessions.revoke('sess_session_id')

# Revoke all other sessions
janua.sessions.revoke_all()
```

## User Management

```python
# Get current user
user = janua.users.me()

# Update user profile
updated_user = janua.users.update(
    first_name='Jane',
    last_name='Smith',
    phone_number='+1234567890',
    metadata={
        'preferences': {
            'theme': 'dark',
            'language': 'en'
        }
    }
)

# Change password
janua.users.change_password(
    current_password='OldPassword123!',
    new_password='NewPassword456!',
    logout_other_sessions=True
)

# Send email verification
janua.users.send_email_verification()

# Verify email
janua.users.verify_email(token='verification_token')

# Delete account
janua.users.delete_account(
    password='UserPassword123!',
    confirmation='DELETE'
)
```

## Multi-Factor Authentication

```python
# Enable TOTP MFA
totp_secret = janua.mfa.enable_totp()
print(f'TOTP Secret: {totp_secret["secret"]}')
print(f'QR Code: {totp_secret["qr_code"]}')

# Verify TOTP setup
janua.mfa.verify_totp(code='123456')

# Enable SMS MFA
janua.mfa.enable_sms(phone_number='+1234567890')

# Enable Email MFA
janua.mfa.enable_email()

# Generate backup codes
backup_codes = janua.mfa.generate_backup_codes()

# Disable MFA
janua.mfa.disable(method='totp', code='123456')
```

## Organization Management

```python
# List organizations
organizations = janua.organizations.list()

# Create organization
new_org = janua.organizations.create(
    name='My Organization',
    slug='my-org',
    domain='myorg.com',
    settings={
        'allowed_domains': ['myorg.com'],
        'sso_required': False,
        'mfa_required': True
    }
)

# Get organization details
org = janua.organizations.get('org_123')

# Update organization
updated_org = janua.organizations.update(
    organization_id='org_123',
    name='Updated Organization Name',
    settings={
        'mfa_required': True,
        'session_timeout': 14400
    }
)

# List organization members
members = janua.organizations.list_members(
    organization_id='org_123',
    limit=50,
    role='admin'
)

# Invite user to organization
invitation = janua.organizations.invite_member(
    organization_id='org_123',
    email='newuser@example.com',
    role='member',
    permissions=['users:read'],
    message='Welcome to our organization!'
)

# Update member role
janua.organizations.update_member_role(
    organization_id='org_123',
    user_id='usr_456',
    role='admin',
    permissions=['users:read', 'users:write', 'billing:read']
)

# Remove member
janua.organizations.remove_member(
    organization_id='org_123',
    user_id='usr_456'
)
```

## RBAC (Role-Based Access Control)

```python
# List roles
roles = janua.rbac.list_roles()

# Create custom role
custom_role = janua.rbac.create_role(
    name='Marketing Manager',
    description='Manage marketing content and campaigns',
    permissions=[
        'content:read',
        'content:write',
        'analytics:read',
        'campaigns:read',
        'campaigns:write'
    ]
)

# List all permissions
permissions = janua.rbac.list_permissions()

# Check user permissions
permission_check = janua.rbac.check_permissions(
    user_id='usr_123',
    permissions=['users:read', 'billing:write'],
    context={
        'organization_id': 'org_abc123',
        'resource_id': 'res_xyz789'
    }
)

# Assign role to user
janua.rbac.assign_role(user_id='usr_123', role_id='role_admin')

# Remove role from user
janua.rbac.remove_role(user_id='usr_123', role_id='role_admin')
```

## Enterprise Features

### Audit Logging

```python
# Query audit events
audit_events = janua.audit.query_events(
    start_date='2025-01-01T00:00:00Z',
    end_date='2025-01-15T23:59:59Z',
    event_type='user.login',
    user_id='usr_123',
    limit=100
)

# Verify audit chain integrity
verification_result = janua.audit.verify_chain(
    start_event_id='evt_start',
    end_event_id='evt_end'
)
```

### SCIM 2.0 Provisioning

```python
# Create SCIM user
scim_user = janua.scim.create_user(
    schemas=['urn:ietf:params:scim:schemas:core:2.0:User'],
    user_name='john.doe@acme.com',
    name={
        'given_name': 'John',
        'family_name': 'Doe'
    },
    emails=[{
        'value': 'john.doe@acme.com',
        'type': 'work',
        'primary': True
    }],
    active=True
)

# Update SCIM user
updated_scim_user = janua.scim.update_user(
    user_id='usr_123',
    active=False
)

# Delete SCIM user
janua.scim.delete_user('usr_123')

# List SCIM users
scim_users = janua.scim.list_users(
    start_index=1,
    count=50,
    filter='userName eq "john.doe@acme.com"'
)
```

### Webhooks

```python
import hmac
import hashlib

# Create webhook
webhook = janua.webhooks.create(
    url='https://api.example.com/webhooks/janua',
    events=['user.created', 'user.updated', 'user.deleted'],
    secret='whsec_abc123',
    active=True
)

# List webhooks
webhooks = janua.webhooks.list()

# Update webhook
updated_webhook = janua.webhooks.update(
    webhook_id='wh_123',
    events=['user.created', 'user.deleted'],
    active=False
)

# Delete webhook
janua.webhooks.delete('wh_123')

# Verify webhook signature (Flask example)
def verify_webhook_signature(payload, signature, secret, timestamp):
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        f'{timestamp}.{payload}'.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f'sha256={expected_signature}' == signature

# Flask webhook endpoint
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhooks/janua', methods=['POST'])
def handle_webhook():
    payload = request.get_data(as_text=True)
    signature = request.headers.get('X-Janua-Signature')
    timestamp = request.headers.get('X-Janua-Timestamp')
    secret = 'whsec_your_secret'
    
    if not verify_webhook_signature(payload, signature, secret, timestamp):
        return jsonify({'error': 'Invalid signature'}), 401
    
    event = request.json
    
    # Handle different event types
    if event['type'] == 'user.created':
        # Handle new user
        pass
    elif event['type'] == 'user.updated':
        # Handle user update
        pass
    elif event['type'] == 'user.deleted':
        # Handle user deletion
        pass
    
    return jsonify({'status': 'success'})
```

## Error Handling

```python
from janua.exceptions import JanuaError, AuthenticationError, ValidationError

try:
    user = janua.auth.login(
        email='user@example.com',
        password='wrongpassword'
    )
except AuthenticationError as e:
    print(f'Authentication failed: {e.message}')
    print(f'Error code: {e.code}')
except ValidationError as e:
    print(f'Validation error: {e.message}')
    print(f'Field errors: {e.details}')
except JanuaError as e:
    print(f'Janua API error: {e.message}')
    print(f'Status code: {e.status_code}')
    print(f'Request ID: {e.request_id}')
except Exception as e:
    print(f'Unexpected error: {str(e)}')
```

## Django Integration

```python
# settings.py
JANUA_API_KEY = 'your-api-key'
JANUA_BASE_URL = 'https://api.janua.dev'

# middleware.py
from django.utils.deprecation import MiddlewareMixin
from janua import JanuaClient

class JanuaAuthMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.janua = JanuaClient(
            api_key=settings.JANUA_API_KEY,
            base_url=settings.JANUA_BASE_URL
        )

    def process_request(self, request):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if token:
            try:
                # Verify token and get user
                user_data = self.janua.auth.verify_token(token)
                request.janua_user = user_data
            except JanuaError:
                request.janua_user = None

# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def register(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        
        try:
            user = janua.auth.register(
                email=data['email'],
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name']
            )
            return JsonResponse({'success': True, 'user': user})
        except JanuaError as e:
            return JsonResponse({
                'success': False, 
                'error': e.message
            }, status=e.status_code)
```

## FastAPI Integration

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from janua import JanuaClient
from janua.exceptions import JanuaError

app = FastAPI()
security = HTTPBearer()

janua = JanuaClient(
    api_key='your-api-key',
    base_url='https://api.janua.dev'
)

class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str

class LoginRequest(BaseModel):
    email: str
    password: str

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        user = janua.auth.verify_token(credentials.credentials)
        return user
    except JanuaError:
        raise HTTPException(status_code=401, detail="Invalid authentication")

@app.post("/auth/register")
async def register(request: RegisterRequest):
    try:
        user = janua.auth.register(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        return {"success": True, "user": user}
    except JanuaError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@app.post("/auth/login")
async def login(request: LoginRequest):
    try:
        session = janua.auth.login(
            email=request.email,
            password=request.password
        )
        return {"success": True, "session": session}
    except JanuaError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@app.get("/users/me")
async def get_me(current_user = Depends(get_current_user)):
    return current_user
```

---

# Vue SDK

## Installation

```bash
npm install @janua/vue
```

## Setup

```javascript
// main.js
import { createApp } from 'vue'
import { createJanua } from '@janua/vue-sdk'
import App from './App.vue'

const app = createApp(App)

const janua = createJanua({
  apiKey: import.meta.env.VITE_JANUA_API_KEY,
  baseUrl: 'https://api.janua.dev',
  organizationId: 'org_123' // Optional for multi-tenant
})

app.use(janua)
app.mount('#app')
```

## Composables

### useAuth

```vue
<template>
  <div>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">Error: {{ error.message }}</div>
    <div v-else-if="user">
      <p>Welcome, {{ user.firstName }}!</p>
      <button @click="logout">Logout</button>
    </div>
    <div v-else>
      <button @click="handleLogin">Login</button>
      <button @click="handleRegister">Register</button>
    </div>
  </div>
</template>

<script setup>
import { useAuth } from '@janua/vue-sdk'

const { 
  user, 
  loading, 
  error, 
  login, 
  register, 
  logout 
} = useAuth()

const handleLogin = async () => {
  try {
    await login({
      email: 'user@example.com',
      password: 'password123'
    })
  } catch (error) {
    console.error('Login failed:', error)
  }
}

const handleRegister = async () => {
  try {
    await register({
      email: 'user@example.com',
      password: 'password123',
      firstName: 'John',
      lastName: 'Doe'
    })
  } catch (error) {
    console.error('Registration failed:', error)
  }
}
</script>
```

### useMagicLink

```vue
<template>
  <div>
    <button @click="sendLink" :disabled="loading">
      {{ loading ? 'Sending...' : 'Send Magic Link' }}
    </button>
    <p v-if="sent">Magic link sent! Check your email.</p>
    <p v-if="error">Error: {{ error.message }}</p>
  </div>
</template>

<script setup>
import { useMagicLink } from '@janua/vue-sdk'

const { sendMagicLink, loading, error, sent } = useMagicLink()

const sendLink = async () => {
  await sendMagicLink({
    email: 'user@example.com',
    redirectUrl: window.location.origin + '/auth/callback'
  })
}
</script>
```

### usePasskeys

```vue
<template>
  <div>
    <p v-if="!supported">Passkeys not supported in this browser</p>
    <div v-else>
      <button @click="registerPasskey" :disabled="loading">
        Register Passkey
      </button>
      <button @click="authenticateWithPasskey" :disabled="loading">
        Login with Passkey
      </button>
      <p v-if="error">Error: {{ error.message }}</p>
    </div>
  </div>
</template>

<script setup>
import { usePasskeys } from '@janua/vue-sdk'

const { 
  registerPasskey, 
  authenticateWithPasskey, 
  loading, 
  error, 
  supported 
} = usePasskeys()

const registerPasskey = async () => {
  try {
    await registerPasskey({
      displayName: 'John Doe'
    })
  } catch (error) {
    console.error('Passkey registration failed:', error)
  }
}

const authenticateWithPasskey = async () => {
  try {
    await authenticateWithPasskey({
      email: 'user@example.com'
    })
  } catch (error) {
    console.error('Passkey authentication failed:', error)
  }
}
</script>
```

### useUser

```vue
<template>
  <div>
    <div v-if="user">
      <h2>{{ user.firstName }} {{ user.lastName }}</h2>
      <p>{{ user.email }}</p>
      <form @submit.prevent="updateProfile">
        <input v-model="firstName" placeholder="First Name" />
        <input v-model="lastName" placeholder="Last Name" />
        <button type="submit" :disabled="loading">Update</button>
      </form>
    </div>
    <p v-if="error">Error: {{ error.message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useUser } from '@janua/vue-sdk'

const { user, updateUser, loading, error } = useUser()

const firstName = ref(user.value?.firstName || '')
const lastName = ref(user.value?.lastName || '')

const updateProfile = async () => {
  await updateUser({
    firstName: firstName.value,
    lastName: lastName.value
  })
}
</script>
```

### useOrganization

```vue
<template>
  <div>
    <h2>Organizations</h2>
    <div v-for="org in organizations" :key="org.id">
      <p>{{ org.name }} ({{ org.userRole }})</p>
      <button @click="switchOrganization(org.id)">Switch</button>
    </div>
    <button @click="createOrg">Create Organization</button>
    <p v-if="error">Error: {{ error.message }}</p>
  </div>
</template>

<script setup>
import { useOrganization } from '@janua/vue-sdk'

const { 
  organizations,
  currentOrganization,
  createOrganization,
  switchOrganization,
  loading,
  error 
} = useOrganization()

const createOrg = async () => {
  await createOrganization({
    name: 'New Organization',
    slug: 'new-org'
  })
}
</script>
```

## Permission Components

### JanuaProtectedRoute

```vue
<template>
  <RouterView v-if="hasPermission" />
  <div v-else-if="loading">Loading...</div>
  <UnauthorizedPage v-else />
</template>

<script setup>
import { usePermissions } from '@janua/vue-sdk'

const props = defineProps({
  permissions: Array,
  requireAll: { type: Boolean, default: false }
})

const { hasPermission, loading } = usePermissions(
  props.permissions, 
  props.requireAll
)
</script>
```

### JanuaPermissionGuard

```vue
<template>
  <slot v-if="hasPermission" />
  <slot v-else name="fallback" />
</template>

<script setup>
import { usePermissions } from '@janua/vue-sdk'

const props = defineProps({
  permissions: { type: Array, required: true },
  requireAll: { type: Boolean, default: false }
})

const { hasPermission } = usePermissions(
  props.permissions, 
  props.requireAll
)
</script>
```

Usage:
```vue
<template>
  <div>
    <h1>Dashboard</h1>
    
    <JanuaPermissionGuard :permissions="['users:read']">
      <UsersList />
      <template #fallback>
        <p>You don't have permission to view users</p>
      </template>
    </JanuaPermissionGuard>
  </div>
</template>
```

---

# Next.js SDK

## Installation

```bash
npm install @janua/nextjs
```

## Setup

### App Router (app directory)

```javascript
// app/providers.tsx
'use client'

import { JanuaProvider } from '@janua/nextjs'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <JanuaProvider
      apiKey={process.env.NEXT_PUBLIC_JANUA_API_KEY!}
      baseUrl="https://api.janua.dev"
    >
      {children}
    </JanuaProvider>
  )
}

// app/layout.tsx
import { Providers } from './providers'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
```

### App Router Layout

```javascript
// app/layout.tsx
import { JanuaProvider } from '@janua/nextjs'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <JanuaProvider config={{ baseURL: process.env.NEXT_PUBLIC_API_URL! }}>
          {children}
        </JanuaProvider>
      </body>
    </html>
  )
}
```

> **Note:** The Next.js SDK supports App Router only. Pages Router is not supported.

## Server-Side Integration

### API Routes

```typescript
// app/api/auth/login/route.ts (App Router)
import { NextRequest, NextResponse } from 'next/server'
import { JanuaServerClient } from '@janua/nextjs/server'

const janua = new JanuaServerClient({
  apiKey: process.env.JANUA_API_KEY!
})

export async function POST(request: NextRequest) {
  try {
    const { email, password } = await request.json()
    
    const result = await janua.auth.login({
      email,
      password
    })
    
    // Set secure HTTP-only cookie
    const response = NextResponse.json({
      success: true,
      user: result.user
    })
    
    response.cookies.set('janua-token', result.session.accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 60 * 24 * 7 // 7 days
    })
    
    return response
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 400 }
    )
  }
}

// app/api/auth/callback/route.ts (App Router)
import { NextRequest, NextResponse } from 'next/server'
import { JanuaServerClient } from '@janua/nextjs'

const janua = new JanuaServerClient({
  appId: process.env.JANUA_APP_ID!,
  apiKey: process.env.JANUA_API_KEY!,
  jwtSecret: process.env.JANUA_JWT_SECRET!,
})

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')

  if (!code) {
    return NextResponse.json({ error: 'Missing code' }, { status: 400 })
  }

  try {
    const result = await janua.handleOAuthCallback(code)
    return NextResponse.redirect(new URL('/dashboard', request.url))
  } catch (error) {
    return NextResponse.json({ error: 'Auth failed' }, { status: 400 })
  }
}
```

### Middleware

```typescript
// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { JanuaServerClient } from '@janua/nextjs/server'

const janua = new JanuaServerClient({
  apiKey: process.env.JANUA_API_KEY!
})

export async function middleware(request: NextRequest) {
  const token = request.cookies.get('janua-token')?.value
  
  // Protect routes that require authentication
  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    if (!token) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
    
    try {
      const user = await janua.auth.verifyToken(token)
      
      // Add user info to request headers
      const response = NextResponse.next()
      response.headers.set('x-user-id', user.id)
      response.headers.set('x-user-email', user.email)
      
      return response
    } catch (error) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }
  
  // Protect admin routes
  if (request.nextUrl.pathname.startsWith('/admin')) {
    if (!token) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
    
    try {
      const user = await janua.auth.verifyToken(token)
      
      // Check admin permissions
      const hasAdminAccess = await janua.rbac.checkPermissions(user.id, {
        permissions: ['admin:read']
      })
      
      if (!hasAdminAccess) {
        return NextResponse.redirect(new URL('/unauthorized', request.url))
      }
      
      return NextResponse.next()
    } catch (error) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }
  
  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/admin/:path*']
}
```

## Server Components

### User Profile Server Component

```tsx
// app/dashboard/profile/page.tsx
import { cookies } from 'next/headers'
import { JanuaServerClient } from '@janua/nextjs/server'
import { redirect } from 'next/navigation'

const janua = new JanuaServerClient({
  apiKey: process.env.JANUA_API_KEY!
})

export default async function ProfilePage() {
  const cookieStore = cookies()
  const token = cookieStore.get('janua-token')?.value
  
  if (!token) {
    redirect('/login')
  }
  
  try {
    const user = await janua.users.me(token)
    
    return (
      <div>
        <h1>Profile</h1>
        <p>Name: {user.firstName} {user.lastName}</p>
        <p>Email: {user.email}</p>
        <p>Verified: {user.emailVerified ? 'Yes' : 'No'}</p>
        <p>MFA: {user.mfaEnabled ? 'Enabled' : 'Disabled'}</p>
      </div>
    )
  } catch (error) {
    redirect('/login')
  }
}
```

### Organization Members Server Component

```tsx
// app/dashboard/members/page.tsx
import { cookies, headers } from 'next/headers'
import { JanuaServerClient } from '@janua/nextjs/server'

const janua = new JanuaServerClient({
  apiKey: process.env.JANUA_API_KEY!
})

export default async function MembersPage() {
  const cookieStore = cookies()
  const token = cookieStore.get('janua-token')?.value
  const headersList = headers()
  const organizationId = headersList.get('x-organization-id')
  
  if (!token || !organizationId) {
    return <div>Access denied</div>
  }
  
  try {
    const members = await janua.organizations.listMembers(
      organizationId,
      { limit: 50 },
      token
    )
    
    return (
      <div>
        <h1>Team Members</h1>
        <div className="grid gap-4">
          {members.members.map(member => (
            <div key={member.id} className="border p-4 rounded">
              <h3>{member.firstName} {member.lastName}</h3>
              <p>{member.email}</p>
              <p>Role: {member.role}</p>
              <p>Joined: {new Date(member.joinedAt).toLocaleDateString()}</p>
            </div>
          ))}
        </div>
      </div>
    )
  } catch (error) {
    return <div>Error loading members</div>
  }
}
```

## Client Components

### Login Form

```tsx
// app/login/page.tsx
'use client'

import { useState } from 'react'
import { useAuth } from '@janua/nextjs'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      await login({ email, password })
      router.push('/dashboard')
    } catch (error) {
      console.error('Login failed:', error)
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <h1>Login</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          required
          className="w-full p-2 border rounded"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          required
          className="w-full p-2 border rounded"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full p-2 bg-blue-500 text-white rounded disabled:opacity-50"
        >
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
      {error && (
        <p className="text-red-500 mt-2">{error.message}</p>
      )}
    </div>
  )
}
```

### Protected Dashboard

```tsx
// app/dashboard/page.tsx
'use client'

import { useAuth } from '@janua/nextjs'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function DashboardPage() {
  const { user, loading, logout } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  if (loading) {
    return <div>Loading...</div>
  }

  if (!user) {
    return null
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1>Dashboard</h1>
        <div className="flex items-center gap-4">
          <span>Welcome, {user.firstName}!</span>
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-500 text-white rounded"
          >
            Logout
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border p-6 rounded">
          <h2>Profile Info</h2>
          <p>Email: {user.email}</p>
          <p>Verified: {user.emailVerified ? 'Yes' : 'No'}</p>
          <p>MFA: {user.mfaEnabled ? 'Enabled' : 'Disabled'}</p>
        </div>
        
        <div className="border p-6 rounded">
          <h2>Quick Actions</h2>
          <div className="space-y-2">
            <button className="block w-full text-left p-2 hover:bg-gray-100 rounded">
              Update Profile
            </button>
            <button className="block w-full text-left p-2 hover:bg-gray-100 rounded">
              Change Password
            </button>
            <button className="block w-full text-left p-2 hover:bg-gray-100 rounded">
              Setup MFA
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

## Deployment Configuration

### Environment Variables

```bash
# .env.local
JANUA_API_KEY=your-server-side-api-key
NEXT_PUBLIC_JANUA_API_KEY=your-client-side-api-key
NEXT_PUBLIC_JANUA_BASE_URL=https://api.janua.dev
```

### Vercel Deployment

```json
// vercel.json
{
  "functions": {
    "app/api/**/*.ts": {
      "maxDuration": 30
    }
  },
  "env": {
    "JANUA_API_KEY": "@janua-api-key",
    "NEXT_PUBLIC_JANUA_API_KEY": "@janua-public-api-key"
  }
}
```

---

## Support and Resources

- **Documentation**: [https://docs.janua.dev](https://docs.janua.dev)
- **GitHub**: [https://github.com/madfam-org/janua](https://github.com/madfam-org/janua)
- **npm**: [@janua/sdk](https://www.npmjs.com/package/@janua/sdk)
- **PyPI**: [janua-python](https://pypi.org/project/janua-python/)
- **Support**: [support@janua.dev](mailto:support@janua.dev)

---

*Last updated: 2025-01-15*