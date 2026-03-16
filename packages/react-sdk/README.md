# @janua/react-sdk

Official Janua SDK for React applications. Provides authentication context, hooks, pre-built components, and utilities for integrating Janua into any React 18+ application.

**Version:** 0.1.2 | **React:** 18+ | **License:** AGPL-3.0

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [JanuaProvider](#januaprovider)
- [Hooks](#hooks)
  - [useJanua](#usejanua)
  - [useAuth](#useauth)
  - [useSession](#usesession)
  - [useOrganization](#useorganization)
  - [useUser](#useuser)
  - [usePasskey](#usepasskey)
  - [useMFA](#usemfa)
  - [useRealtime](#userealtime)
- [Components](#components)
  - [SignIn](#signin)
  - [SignUp](#signup)
  - [UserProfile](#userprofile)
  - [UserButton](#userbutton)
  - [Protect](#protect)
  - [AuthGuard](#authguard)
  - [OrgSwitcher](#orgswitcher)
  - [SignedIn](#signedin)
  - [SignedOut](#signedout)
  - [MFAChallenge](#mfachallenge)
- [Theming](#theming)
- [OAuth and PKCE Utilities](#oauth-and-pkce-utilities)
- [Error Handling](#error-handling)
- [TypeScript](#typescript)
- [Related Documentation](#related-documentation)

---

## Installation

```bash
# npm
npm install @janua/react-sdk

# yarn
yarn add @janua/react-sdk

# pnpm
pnpm add @janua/react-sdk
```

The SDK requires React 18 or later as a peer dependency. `@janua/typescript-sdk` and `@janua/ui` are bundled dependencies — you do not need to install them separately.

**Registry configuration** (required for MADFAM private registry):

```ini
# .npmrc
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

---

## Quick Start

Wrap your application with `JanuaProvider` and use `useAuth` to access authentication state:

```tsx
// main.tsx or App.tsx
import { JanuaProvider } from '@janua/react-sdk';

function App() {
  return (
    <JanuaProvider
      config={{
        baseURL: 'https://api.janua.dev',
        clientId: 'your-client-id',
        redirectUri: 'https://yourapp.com/auth/callback',
      }}
    >
      <YourApp />
    </JanuaProvider>
  );
}
```

```tsx
// components/Dashboard.tsx
import { useAuth } from '@janua/react-sdk';

function Dashboard() {
  const { isAuthenticated, isLoading, user, signOut } = useAuth();

  if (isLoading) return <p>Loading...</p>;
  if (!isAuthenticated) return <p>Please sign in.</p>;

  return (
    <div>
      <p>Signed in as {user?.email}</p>
      <button onClick={signOut}>Sign out</button>
    </div>
  );
}
```

---

## JanuaProvider

`JanuaProvider` must wrap your application at the root level. It initializes the Janua client, manages authentication state, and makes context available to all hooks and components.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `config` | `JanuaConfig \| JanuaProviderConfig` | Yes | API configuration |
| `appearance` | `JanuaAppearance` | No | Theming for UI components |
| `children` | `ReactNode` | Yes | Application tree |

### JanuaProviderConfig

```typescript
interface JanuaProviderConfig {
  baseURL: string;                // Janua API base URL
  apiKey?: string;                // API key for server-side requests
  clientId?: string;              // OAuth client ID
  redirectUri?: string;           // OAuth callback URL
  environment?: 'development' | 'staging' | 'production';
  debug?: boolean;                // Enable debug logging
  autoRefreshTokens?: boolean;    // Auto-refresh before expiry
  tokenStorage?: 'localStorage' | 'sessionStorage' | 'memory';
}
```

### Example

```tsx
import { JanuaProvider } from '@janua/react-sdk';
import type { JanuaAppearance } from '@janua/react-sdk';

const appearance: JanuaAppearance = {
  preset: 'default',
  accentColor: '#6366f1',
  darkMode: false,
};

function App() {
  return (
    <JanuaProvider
      config={{
        baseURL: process.env.NEXT_PUBLIC_JANUA_API_URL,
        clientId: process.env.NEXT_PUBLIC_JANUA_CLIENT_ID,
        redirectUri: `${window.location.origin}/auth/callback`,
        environment: 'production',
      }}
      appearance={appearance}
    >
      <YourApp />
    </JanuaProvider>
  );
}
```

**Security note:** Tokens are stored in `localStorage` by default. User data is held only in React state and is never written to storage (CWE-312 mitigation). The access token is automatically refreshed if expired on initialization and before it reaches expiry.

---

## Hooks

All hooks must be called inside the `JanuaProvider` component tree.

### useJanua

The primary hook that exposes the full `JanuaContextValue`. Other specialized hooks are thin wrappers around this hook. Use `useJanua` when you need direct access to the underlying client or when no specialized hook covers your use case.

```typescript
const {
  client,           // JanuaClient instance for advanced usage
  user,             // JanuaUser | null
  session,          // Session | null
  isLoading,        // boolean
  isAuthenticated,  // boolean
  error,            // JanuaErrorState | null
  appearance,       // JanuaAppearance | undefined
  signIn,           // (email, password) => Promise<void>
  signUp,           // (email, password, options?) => Promise<void>
  signOut,          // () => Promise<void>
  refreshSession,   // () => Promise<void>
  signInWithOAuth,  // (provider) => Promise<void>
  handleOAuthCallback, // (code, state) => Promise<void>
  getAccessToken,   // () => Promise<string | null>
  getIdToken,       // () => Promise<string | null>
  clearError,       // () => void
} = useJanua();
```

### useAuth

A convenience hook for authentication state and actions. Returns the same shape as `useJanua` but communicates intent clearly when only authentication operations are needed.

```typescript
import { useAuth } from '@janua/react-sdk';

const {
  user,               // JanuaUser | null
  session,            // Session | null
  isLoading,          // boolean
  isAuthenticated,    // boolean
  error,              // JanuaErrorState | null
  signIn,             // (email: string, password: string) => Promise<void>
  signUp,             // (email: string, password: string, options?: SignUpOptions) => Promise<void>
  signOut,            // () => Promise<void>
  refreshSession,     // () => Promise<void>
  signInWithOAuth,    // (provider: OAuthProviderName) => Promise<void>
  handleOAuthCallback, // (code: string, state: string) => Promise<void>
  getAccessToken,     // () => Promise<string | null>
  getIdToken,         // () => Promise<string | null>
  clearError,         // () => void
} = useAuth();
```

**SignUpOptions:**

```typescript
interface SignUpOptions {
  firstName?: string;
  lastName?: string;
  username?: string;
}
```

**OAuthProviderName:** `'google' | 'github' | 'microsoft' | 'apple' | 'discord' | 'twitter'`

**Example — custom sign-in form:**

```tsx
import { useAuth } from '@janua/react-sdk';
import { getUserFriendlyMessage } from '@janua/react-sdk';

function LoginForm() {
  const { signIn, isLoading, error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    await signIn(email, password);
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && <p>{getUserFriendlyMessage(error)}</p>}
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Signing in...' : 'Sign in'}
      </button>
    </form>
  );
}
```

**Example — OAuth sign-in:**

```tsx
import { useAuth } from '@janua/react-sdk';

function OAuthButtons() {
  const { signInWithOAuth } = useAuth();

  return (
    <div>
      <button onClick={() => signInWithOAuth('google')}>
        Continue with Google
      </button>
      <button onClick={() => signInWithOAuth('github')}>
        Continue with GitHub
      </button>
    </div>
  );
}
```

The `signInWithOAuth` method generates PKCE parameters, stores them, and redirects to the provider. After the provider redirects back, call `handleOAuthCallback` with the `code` and `state` query parameters.

```tsx
// pages/auth/callback.tsx
import { useEffect } from 'react';
import { useAuth } from '@janua/react-sdk';

function OAuthCallback() {
  const { handleOAuthCallback } = useAuth();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');

    if (code && state) {
      handleOAuthCallback(code, state).then(() => {
        window.location.href = '/dashboard';
      });
    }
  }, [handleOAuthCallback]);

  return <p>Completing sign in...</p>;
}
```

---

### useSession

Provides access to session data and token management operations.

```typescript
import { useSession } from '@janua/react-sdk';

const {
  session,           // Session | null — current session from context
  isRefreshing,      // boolean
  refreshTokens,     // () => Promise<TokenResponse | null>
  getCurrentSession, // () => Promise<Session | null>
} = useSession();
```

**Example:**

```tsx
function SessionPanel() {
  const { session, refreshTokens, isRefreshing } = useSession();

  return (
    <div>
      <p>Session ID: {session?.id ?? 'none'}</p>
      <button onClick={refreshTokens} disabled={isRefreshing}>
        {isRefreshing ? 'Refreshing...' : 'Refresh tokens'}
      </button>
    </div>
  );
}
```

---

### useOrganization

Fetches the user's organizations and provides organization management.

```typescript
import { useOrganization } from '@janua/react-sdk';

const {
  organizations,        // Organization[]
  isLoading,            // boolean
  createOrganization,   // (data: { name, slug, description? }) => Promise<Organization>
} = useOrganization();
```

Organizations are fetched automatically when the user is authenticated and cleared on sign-out.

**Example:**

```tsx
function OrgList() {
  const { organizations, isLoading, createOrganization } = useOrganization();

  const handleCreate = async () => {
    await createOrganization({ name: 'Acme Corp', slug: 'acme-corp' });
  };

  if (isLoading) return <p>Loading organizations...</p>;

  return (
    <div>
      <ul>
        {organizations.map((org) => (
          <li key={org.id}>{org.name}</li>
        ))}
      </ul>
      <button onClick={handleCreate}>Create organization</button>
    </div>
  );
}
```

---

### useUser

Provides the current user and a method to update user profile data.

```typescript
import { useUser } from '@janua/react-sdk';

const {
  user,       // JanuaUser | null
  isLoading,  // boolean — true while context is loading or an update is in flight
  updateUser, // (data: { firstName?, lastName?, username? }) => Promise<void>
} = useUser();
```

`updateUser` calls the API and then calls `refreshSession` to propagate the changes into context.

**Example:**

```tsx
function ProfileEditor() {
  const { user, updateUser, isLoading } = useUser();
  const [firstName, setFirstName] = useState(user?.name?.split(' ')[0] ?? '');

  const handleSave = async () => {
    await updateUser({ firstName });
  };

  return (
    <div>
      <input
        value={firstName}
        onChange={(e) => setFirstName(e.target.value)}
      />
      <button onClick={handleSave} disabled={isLoading}>
        Save
      </button>
    </div>
  );
}
```

---

### usePasskey

Provides WebAuthn/FIDO2 passkey registration and authentication with automatic browser support detection.

```typescript
import { usePasskey } from '@janua/react-sdk';

const {
  register,     // (name?: string) => Promise<void>
  authenticate, // (email?: string) => Promise<void>
  isSupported,  // boolean — true if WebAuthn is available in this browser
  isLoading,    // boolean
  error,        // Error | null
} = usePasskey();
```

**Example:**

```tsx
function PasskeySection() {
  const { register, authenticate, isSupported, isLoading, error } = usePasskey();

  if (!isSupported) {
    return <p>Passkeys are not supported in this browser.</p>;
  }

  return (
    <div>
      {error && <p>{error.message}</p>}
      <button onClick={() => register('My laptop')} disabled={isLoading}>
        Register passkey
      </button>
      <button onClick={() => authenticate()} disabled={isLoading}>
        Sign in with passkey
      </button>
    </div>
  );
}
```

---

### useMFA

Manages multi-factor authentication enrollment and verification for the current user.

```typescript
import { useMFA } from '@janua/react-sdk';

const {
  enable,     // (type?: string) => Promise<{ secret, qr_code, backup_codes, provisioning_uri }>
  verify,     // (code: string) => Promise<void>
  disable,    // (password: string) => Promise<void>
  isLoading,  // boolean
  error,      // Error | null
} = useMFA();
```

The `type` parameter for `enable` defaults to `'totp'`. The returned `qr_code` is a data URI suitable for use in an `<img>` tag.

**Example — TOTP enrollment:**

```tsx
function MFASetup() {
  const { enable, verify, isLoading, error } = useMFA();
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [code, setCode] = useState('');

  const handleEnable = async () => {
    const result = await enable('totp');
    setQrCode(result.qr_code);
    setSecret(result.secret);
  };

  const handleVerify = async () => {
    await verify(code);
  };

  return (
    <div>
      {error && <p>{error.message}</p>}
      {!qrCode ? (
        <button onClick={handleEnable} disabled={isLoading}>
          Enable two-factor authentication
        </button>
      ) : (
        <div>
          <img src={qrCode} alt="Scan with your authenticator app" />
          <p>Manual key: {secret}</p>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="6-digit code"
            maxLength={6}
          />
          <button onClick={handleVerify} disabled={isLoading}>
            Verify and enable
          </button>
        </div>
      )}
    </div>
  );
}
```

---

### useRealtime

Connects to the Janua WebSocket server and provides real-time event subscriptions. The connection is managed automatically with the component lifecycle.

```typescript
import { useRealtime } from '@janua/react-sdk';
import type { UseRealtimeOptions, UseRealtimeReturn } from '@janua/react-sdk';
```

**UseRealtimeOptions:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `channels` | `string[]` | `[]` | Channels to subscribe to on connect |
| `url` | `string` | derived from `baseURL` | WebSocket server URL override |
| `reconnect` | `boolean` | `true` | Enable automatic reconnection |
| `autoConnect` | `boolean` | `true` | Connect automatically on mount |

**UseRealtimeReturn:**

```typescript
{
  status,      // WebSocketStatus: 'connected' | 'disconnected' | 'reconnecting' | 'error'
  subscribe,   // (channel: string) => void
  unsubscribe, // (channel: string) => void
  on,          // <K>(event: K, handler) => void
  off,         // <K>(event: K, handler) => void
  send,        // (message: WebSocketMessage) => void
  connect,     // () => Promise<void>
  disconnect,  // () => void
}
```

**Example:**

```tsx
import { useRealtime } from '@janua/react-sdk';
import { useEffect } from 'react';

function NotificationListener() {
  const { status, on, off, subscribe } = useRealtime({
    channels: ['notifications'],
    autoConnect: true,
  });

  useEffect(() => {
    const handler = (data: unknown) => {
      console.log('Notification received:', data);
    };

    on('message', handler);
    return () => off('message', handler);
  }, [on, off]);

  return <p>Real-time status: {status}</p>;
}
```

The WebSocket URL defaults to the `baseURL` from config with the scheme replaced (`https://` becomes `wss://`, `http://` becomes `ws://`) and `/ws` appended. Override with the `url` option if your deployment uses a different path.

---

## Components

All components wrap counterparts from `@janua/ui/components/auth`, inject the Janua client and user from context, and forward relevant props to the underlying UI layer. Theming is controlled via the `appearance` prop on `JanuaProvider` (see [Theming](#theming)).

### SignIn

Renders the Janua sign-in form with optional social providers, passkey support, SSO domain detection, and magic link.

```tsx
import { SignIn } from '@janua/react-sdk';
import type { SignInProps } from '@janua/react-sdk';
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | `() => void` | — | Called after successful sign-in |
| `onError` | `(error: Error) => void` | — | Called on sign-in error |
| `className` | `string` | — | CSS class for the container |
| `redirectTo` | `string` | — | URL to redirect to after sign-in |
| `enablePasskeys` | `boolean` | `true` | Show passkey sign-in option |
| `signUpUrl` | `string` | — | Link to sign-up page |
| `socialProviders` | `{ google?, github?, microsoft?, apple? }` | — | Enable social login buttons |
| `logoUrl` | `string` | — | Custom logo URL |
| `showRememberMe` | `boolean` | — | Show "Remember me" checkbox |
| `enableSSO` | `boolean` | — | Enable SSO email domain detection |
| `enableMagicLink` | `boolean` | — | Enable magic link option |

```tsx
<SignIn
  onSuccess={() => router.push('/dashboard')}
  onError={(err) => console.error(err)}
  redirectTo="/dashboard"
  enablePasskeys={true}
  socialProviders={{ google: true, github: true }}
  signUpUrl="/sign-up"
/>
```

---

### SignUp

Renders the Janua sign-up form.

```tsx
import { SignUp } from '@janua/react-sdk';
import type { SignUpProps } from '@janua/react-sdk';
```

Props are forwarded to `@janua/ui SignUp`. See the UI package for the full prop reference.

```tsx
<SignUp onSuccess={() => router.push('/onboarding')} />
```

---

### UserProfile

Renders a full user profile management panel including profile editing, security settings, and danger zone.

```tsx
import { UserProfile } from '@janua/react-sdk';
import type { UserProfileProps } from '@janua/react-sdk';
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `className` | `string` | — | CSS class for the container |
| `onSignOut` | `() => void` | — | Called after sign-out |
| `allowEdit` | `boolean` | `true` | Allow profile field editing |
| `showSecurityTab` | `boolean` | `true` | Show the security tab |
| `showDangerZone` | `boolean` | `true` | Show the danger zone section |

```tsx
<UserProfile
  allowEdit={true}
  showSecurityTab={true}
  onSignOut={() => router.push('/')}
/>
```

---

### UserButton

Renders a user avatar button with a dropdown menu for account management and sign-out. Returns `null` when no user is authenticated.

```tsx
import { UserButton } from '@janua/react-sdk';
import type { UserButtonProps } from '@janua/react-sdk';
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `className` | `string` | — | CSS class for the container |
| `showManageAccount` | `boolean` | — | Show manage account link |
| `manageAccountUrl` | `string` | — | URL for the manage account link |
| `showOrganizations` | `boolean` | — | Show organization switcher in dropdown |
| `activeOrganization` | `string` | — | Name of the currently active organization |

```tsx
<UserButton
  showManageAccount={true}
  manageAccountUrl="/settings"
  showOrganizations={true}
/>
```

---

### Protect

Conditionally renders content based on authentication status and optional role, permission, or custom condition checks. Does not render during loading to prevent flash of content.

```tsx
import { Protect } from '@janua/react-sdk';
import type { ProtectProps } from '@janua/react-sdk';
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | — | Content to render when authorized |
| `role` | `string` | — | Required `organization_role` value |
| `permission` | `string` | — | Required permission (convention-based on role) |
| `condition` | `(user: JanuaUser) => boolean` | — | Custom authorization function |
| `fallback` | `ReactNode` | `null` | Rendered when unauthorized |
| `redirectTo` | `string` | — | Redirect URL when unauthorized (instead of fallback) |

```tsx
// Show content only to admins
<Protect role="admin" fallback={<p>Access denied.</p>}>
  <AdminPanel />
</Protect>

// Use a custom condition
<Protect condition={(user) => user.email_verified} redirectTo="/verify-email">
  <SensitiveContent />
</Protect>
```

---

### AuthGuard

A route-level guard that always redirects unauthorized users. A convenience wrapper around `Protect` where `redirectTo` is required.

```tsx
import { AuthGuard } from '@janua/react-sdk';
import type { AuthGuardProps } from '@janua/react-sdk';
```

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `children` | `ReactNode` | Yes | Content to render when authorized |
| `redirectTo` | `string` | Yes | URL to redirect unauthorized users |
| `role` | `string` | No | Required organization role |
| `permission` | `string` | No | Required permission |
| `condition` | `(user: JanuaUser) => boolean` | No | Custom authorization function |

```tsx
// Protect a route — redirect to sign-in if not authenticated
<AuthGuard redirectTo="/sign-in">
  <Dashboard />
</AuthGuard>

// Role-based route guard
<AuthGuard redirectTo="/403" role="admin">
  <AdminDashboard />
</AuthGuard>
```

Use `Protect` when you want to show fallback content in place. Use `AuthGuard` when unauthorized users must always be redirected.

---

### OrgSwitcher

Renders an organization switcher dropdown that allows the user to switch between or create organizations.

```tsx
import { OrgSwitcher } from '@janua/react-sdk';
import type { OrgSwitcherProps } from '@janua/react-sdk';
```

| Prop | Type | Description |
|------|------|-------------|
| `className` | `string` | CSS class for the container |
| `onSwitchOrganization` | `(org: { id, name, slug }) => void` | Called when user selects an organization |
| `onCreateOrganization` | `() => void` | Called when user clicks create |
| `showCreateOrganization` | `boolean` | Show the create organization option |
| `showPersonalWorkspace` | `boolean` | Show personal workspace entry |
| `onError` | `(error: Error) => void` | Called on error |

```tsx
<OrgSwitcher
  showCreateOrganization={true}
  showPersonalWorkspace={true}
  onSwitchOrganization={(org) => console.log('Switched to', org.name)}
  onCreateOrganization={() => router.push('/organizations/new')}
/>
```

---

### SignedIn

Renders children only when the user is authenticated. Returns `null` during loading and when unauthenticated.

```tsx
import { SignedIn } from '@janua/react-sdk';

<SignedIn>
  <UserButton />
</SignedIn>
```

---

### SignedOut

Renders children only when the user is not authenticated. Returns `null` during loading and when authenticated.

```tsx
import { SignedOut } from '@janua/react-sdk';

<SignedOut>
  <a href="/sign-in">Sign in</a>
</SignedOut>
```

Use `SignedIn` and `SignedOut` together for conditional navigation:

```tsx
<nav>
  <SignedIn>
    <UserButton />
  </SignedIn>
  <SignedOut>
    <a href="/sign-in">Sign in</a>
    <a href="/sign-up">Sign up</a>
  </SignedOut>
</nav>
```

---

### MFAChallenge

Renders the MFA verification prompt. Injects the current user's email from context for display. Wraps `@janua/ui MFAChallenge`.

```tsx
import { MFAChallenge } from '@janua/react-sdk';
import type { MFAChallengeProps } from '@janua/react-sdk';
```

| Prop | Type | Description |
|------|------|-------------|
| `className` | `string` | CSS class for the container |
| `onVerify` | `(code: string) => Promise<void>` | Called when user submits a code |
| `onUseBackupCode` | `() => void` | Called when user requests backup code flow |
| `onRequestNewCode` | `() => Promise<void>` | Called when user requests a new SMS code |
| `onError` | `(error: Error) => void` | Called on error |
| `method` | `'totp' \| 'sms'` | MFA method to display |
| `showBackupCodeOption` | `boolean` | Show the backup code link |
| `allowResend` | `boolean` | Show the resend code link (for SMS) |

```tsx
<MFAChallenge
  method="totp"
  showBackupCodeOption={true}
  onVerify={async (code) => {
    const { verify } = useMFA();
    await verify(code);
    router.push('/dashboard');
  }}
/>
```

---

## Theming

All pre-built components inherit theming from the `appearance` prop on `JanuaProvider`. Components are built on `@janua/ui`, so appearance configuration is applied at the provider level and propagates to every component in the tree.

```typescript
interface JanuaAppearance {
  preset?: string;      // Theme preset name
  accentColor?: string; // Primary accent color (hex, rgb, etc.)
  darkMode?: boolean;   // Force dark mode
}
```

```tsx
<JanuaProvider
  config={config}
  appearance={{
    accentColor: '#8b5cf6',
    darkMode: true,
  }}
>
  <App />
</JanuaProvider>
```

For component-level style overrides, pass a `className` prop to any component and use CSS or a utility framework.

---

## OAuth and PKCE Utilities

The SDK exports PKCE utilities for custom OAuth flows. These are the same functions used internally by `signInWithOAuth`.

```typescript
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
  parseOAuthCallback,
  buildAuthorizationUrl,
  PKCE_STORAGE_KEYS,
} from '@janua/react-sdk';
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `generateCodeVerifier` | `() => string` | Generate a cryptographically random PKCE verifier |
| `generateCodeChallenge` | `(verifier: string) => Promise<string>` | Derive S256 challenge from verifier |
| `generateState` | `() => string` | Generate a random state parameter |
| `storePKCEParams` | `(verifier, state) => void` | Persist verifier and state to sessionStorage |
| `retrievePKCEParams` | `() => { verifier, state } \| null` | Retrieve stored PKCE params |
| `clearPKCEParams` | `() => void` | Remove stored PKCE params |
| `validateState` | `(state: string) => boolean` | Validate returned state matches stored state |
| `parseOAuthCallback` | `(url: string) => OAuthCallbackResult` | Parse code and state from callback URL |
| `buildAuthorizationUrl` | `(baseURL, provider, clientId, redirectUri, challenge, state) => string` | Construct the authorization URL |

**Example — custom OAuth flow:**

```typescript
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  buildAuthorizationUrl,
} from '@janua/react-sdk';

async function initiateOAuth(provider: string) {
  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  const state = generateState();

  storePKCEParams(verifier, state);

  const url = buildAuthorizationUrl(
    'https://api.janua.dev',
    provider,
    'your-client-id',
    'https://yourapp.com/auth/callback',
    challenge,
    state
  );

  window.location.href = url;
}
```

---

## Error Handling

The SDK exports error utilities for consistent, user-facing error handling.

### Error types

```typescript
import {
  JanuaError,
  AuthenticationError,
  ValidationError,
  NetworkError,
  TokenError,
  OAuthError,
  isAuthenticationError,
  isValidationError,
  isNetworkError,
  isJanuaError,
  ReactJanuaError,
} from '@janua/react-sdk';
```

### Error state

Auth operations that fail set `error` in context as a `JanuaErrorState`:

```typescript
interface JanuaErrorState {
  code: JanuaErrorCode;
  message: string;
  status?: number;
  details?: unknown;
}
```

`JanuaErrorCode` values: `'INVALID_CREDENTIALS' | 'TOKEN_EXPIRED' | 'TOKEN_INVALID' | 'REFRESH_FAILED' | 'NETWORK_ERROR' | 'MFA_REQUIRED' | 'EMAIL_NOT_VERIFIED' | 'ACCOUNT_SUSPENDED' | 'OAUTH_ERROR' | 'PKCE_ERROR' | 'UNAUTHORIZED' | 'UNKNOWN_ERROR'`

### Error utilities

```typescript
import {
  createErrorState,
  mapErrorToState,
  isAuthRequiredError,
  isNetworkIssue,
  getUserFriendlyMessage,
} from '@janua/react-sdk';
```

| Utility | Description |
|---------|-------------|
| `createErrorState(code, message, status?, details?)` | Create a `JanuaErrorState` object |
| `mapErrorToState(error)` | Map any caught error to a `JanuaErrorState` |
| `isAuthRequiredError(error)` | Returns `true` for token or session errors that require re-authentication |
| `isNetworkIssue(error)` | Returns `true` when the error is a network connectivity failure |
| `getUserFriendlyMessage(error)` | Returns a localized, user-readable string for the error code |

**Example — handling errors after a failed sign-in:**

```tsx
import { useAuth, isAuthRequiredError, getUserFriendlyMessage } from '@janua/react-sdk';

function LoginPage() {
  const { signIn, error, clearError } = useAuth();

  const handleSignIn = async (email: string, password: string) => {
    clearError();
    try {
      await signIn(email, password);
    } catch {
      // error is already set in context via useAuth
    }
  };

  return (
    <div>
      {error && (
        <div>
          <p>{getUserFriendlyMessage(error)}</p>
          {isAuthRequiredError(error) && (
            <a href="/sign-in">Sign in again</a>
          )}
        </div>
      )}
      {/* form */}
    </div>
  );
}
```

---

## TypeScript

The SDK is written in TypeScript and ships declaration files. All hooks and components are fully typed.

### Core types exported

```typescript
import type {
  // Provider
  JanuaProviderProps,
  JanuaProviderConfig,
  JanuaContextValue,
  JanuaAppearance,
  SignUpOptions,

  // Hooks
  UseAuthReturn,
  UseUserReturn,
  UsePasskeyReturn,
  UseMFAReturn,
  UseRealtimeOptions,
  UseRealtimeReturn,

  // Components
  SignInProps,
  SignUpProps,
  UserProfileProps,
  UserButtonProps,
  ProtectProps,
  AuthGuardProps,
  OrgSwitcherProps,
  SignedInProps,
  SignedOutProps,
  MFAChallengeProps,

  // Domain types (re-exported from @janua/typescript-sdk)
  User,
  Session,
  Organization,
  TokenResponse,
  JanuaConfig,

  // SDK-specific types
  JanuaUser,
  JanuaErrorCode,
  JanuaErrorState,
  OAuthProviderName,
  OAuthCallbackResult,
  JanuaProviderConfig,
} from '@janua/react-sdk';
```

### Constants exported

```typescript
import { STORAGE_KEYS, PKCE_STORAGE_KEYS, SDK_VERSION, SDK_NAME } from '@janua/react-sdk';
```

### JanuaUser shape

Components and hooks expose users as `JanuaUser` rather than the raw API `User` type:

```typescript
interface JanuaUser {
  id: string;
  email: string;
  name: string | null;
  display_name: string | null;
  picture?: string;
  locale: string;
  timezone: string;
  mfa_enabled: boolean;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
  organization_id?: string;
  organization_role?: string;
}
```

---

## Related Documentation

- [Quick Start guide](./QUICK_START.md) — condensed setup steps for common patterns
- [TypeScript SDK](../typescript-sdk/README.md) — the core API client this package builds on
- [Next.js SDK](../nextjs-sdk/README.md) — server-side rendering and App Router support
- [API Reference](../../apps/api/docs/) — full REST API documentation
- [SDK Selection Guide](../../docs/sdks/CHOOSE_YOUR_SDK.md) — compare all Janua SDKs
- [Error Handling Guide](../../docs/guides/ERROR_HANDLING_GUIDE.md) — error codes and patterns
- [Architecture Overview](../../docs/architecture/INDEX.md) — system design documentation
