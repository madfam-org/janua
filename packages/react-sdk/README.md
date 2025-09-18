# @plinto/react-sdk

> **React-specific authentication hooks and components** for Plinto integration

**Version:** 0.1.0 · **Framework:** React 18+ · **Status:** Production Ready

## 📋 Overview

@plinto/react-sdk provides a complete set of React hooks, components, and utilities for seamless Plinto authentication integration. Built on top of @plinto/sdk with React-specific optimizations for state management, SSR support, and component lifecycle handling.

## 🚀 Quick Start

### Installation

```bash
# npm
npm install @plinto/react-sdk @plinto/sdk

# yarn
yarn add @plinto/react-sdk @plinto/sdk

# pnpm
pnpm add @plinto/react-sdk @plinto/sdk
```

### Basic Setup

```tsx
// app.tsx or _app.tsx
import { PlintoProvider } from '@plinto/react-sdk';

function App() {
  return (
    <PlintoProvider
      appId="your-app-id"
      publicKey="your-public-key"
      apiUrl="https://api.plinto.dev" // Optional
    >
      <YourApp />
    </PlintoProvider>
  );
}
```

### Using Auth Hooks

```tsx
import { useAuth, useUser } from '@plinto/react-sdk';

function Profile() {
  const { isAuthenticated, isLoading } = useAuth();
  const { user, error } = useUser();

  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Please sign in</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h1>Welcome, {user?.name}!</h1>
      <p>Email: {user?.email}</p>
    </div>
  );
}
```

## 🏗️ Architecture

### Package Structure

```
packages/react/
├── src/
│   ├── hooks/               # React hooks
│   │   ├── useAuth.ts      # Authentication state
│   │   ├── useUser.ts      # User data hook
│   │   ├── useSession.ts   # Session management
│   │   ├── useOrganization.ts # Org context
│   │   ├── usePasskey.ts   # WebAuthn hook
│   │   └── useMFA.ts       # Multi-factor auth
│   ├── components/         # React components
│   │   ├── PlintoProvider.tsx # Context provider
│   │   ├── SignIn.tsx      # Sign in component
│   │   ├── SignUp.tsx      # Registration
│   │   ├── UserButton.tsx  # User menu
│   │   ├── AuthGuard.tsx   # Route protection
│   │   └── OrgSwitcher.tsx # Organization switcher
│   ├── context/           # React context
│   │   ├── AuthContext.tsx # Auth state context
│   │   └── OrgContext.tsx  # Organization context
│   ├── utils/            # Utilities
│   │   ├── ssr.ts        # SSR support
│   │   ├── storage.ts    # Token storage
│   │   └── validation.ts # Form validation
│   └── index.ts         # Main export
├── dist/               # Built files
├── tests/             # Test files
└── package.json      # Package config
```

### React Integration Architecture

```
┌─────────────────────────────────────┐
│        PlintoProvider               │
│  ┌─────────────────────────────┐   │
│  │     AuthContext             │   │
│  │  ┌───────────────────┐      │   │
│  │  │   SDK Instance    │      │   │
│  │  └───────────────────┘      │   │
│  │  ┌───────────────────┐      │   │
│  │  │   State Manager   │      │   │
│  │  └───────────────────┘      │   │
│  └─────────────────────────────┘   │
│  ┌─────────────────────────────┐   │
│  │     OrgContext              │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## 🪝 Hooks

### Core Authentication Hooks

#### useAuth

```tsx
const {
  isAuthenticated,
  isLoading,
  error,
  signIn,
  signUp,
  signOut,
  user
} = useAuth();

// Sign in
await signIn({ email, password });

// Sign up
await signUp({ email, password, name });

// Sign out
await signOut();
```

#### useUser

```tsx
const {
  user,
  isLoading,
  error,
  updateUser,
  deleteUser,
  refreshUser
} = useUser();

// Update profile
await updateUser({ name: 'New Name' });

// Refresh user data
await refreshUser();

// Delete account
await deleteUser();
```

#### useSession

```tsx
const {
  session,
  sessions,
  isLoading,
  revokeSession,
  refreshToken
} = useSession();

// Revoke specific session
await revokeSession(sessionId);

// Refresh access token
await refreshToken();
```

### Advanced Hooks

#### useOrganization

```tsx
const {
  organization,
  organizations,
  isLoading,
  createOrg,
  switchOrg,
  inviteMember
} = useOrganization();

// Create organization
await createOrg({ name: 'Acme Corp' });

// Switch organization
await switchOrg(orgId);

// Invite member
await inviteMember({ email, role });
```

#### usePasskey

```tsx
const {
  passkeys,
  isSupported,
  registerPasskey,
  authenticateWithPasskey,
  deletePasskey
} = usePasskey();

// Check support
if (!isSupported) return <div>Passkeys not supported</div>;

// Register passkey
await registerPasskey({ displayName: 'My Device' });

// Authenticate
await authenticateWithPasskey();
```

#### useMFA

```tsx
const {
  mfaEnabled,
  mfaMethods,
  enableTOTP,
  enableSMS,
  verifyCode,
  generateBackupCodes
} = useMFA();

// Enable TOTP
const { qrCode, secret } = await enableTOTP();

// Verify code
await verifyCode({ method: 'totp', code: '123456' });
```

## 🧩 Components

### Provider Component

```tsx
<PlintoProvider
  appId="your-app-id"
  publicKey="your-public-key"
  apiUrl="https://api.plinto.dev"
  defaultAuthState={null}
  onAuthChange={(user) => console.log('Auth changed:', user)}
  storage={localStorage} // or sessionStorage
>
  <App />
</PlintoProvider>
```

### Authentication Components

#### SignIn Component

```tsx
<SignIn
  onSuccess={(user) => navigate('/dashboard')}
  onError={(error) => console.error(error)}
  providers={['google', 'github', 'microsoft']}
  showPasskey={true}
  redirectUrl="/dashboard"
/>
```

#### SignUp Component

```tsx
<SignUp
  onSuccess={(user) => navigate('/onboarding')}
  requireEmailVerification={true}
  fields={[
    { name: 'name', required: true },
    { name: 'company', required: false }
  ]}
  termsUrl="/terms"
  privacyUrl="/privacy"
/>
```

#### UserButton Component

```tsx
<UserButton
  afterSignOutUrl="/"
  showName={true}
  menuItems={[
    { label: 'Settings', href: '/settings' },
    { label: 'Billing', href: '/billing' }
  ]}
/>
```

### Protection Components

#### AuthGuard Component

```tsx
<AuthGuard
  fallback={<SignIn />}
  loading={<Spinner />}
  requireVerified={true}
  requireMFA={false}
  allowedRoles={['admin', 'member']}
>
  <ProtectedContent />
</AuthGuard>
```

#### OrgSwitcher Component

```tsx
<OrgSwitcher
  onSwitch={(org) => console.log('Switched to:', org)}
  showCreateButton={true}
  appearance={{
    theme: 'dark',
    variables: { colorPrimary: '#6366f1' }
  }}
/>
```

## 🎨 Customization

### Theming

```tsx
// Custom theme configuration
const customTheme = {
  colors: {
    primary: '#6366f1',
    secondary: '#8b5cf6',
    error: '#ef4444',
    success: '#10b981'
  },
  fonts: {
    body: 'Inter, sans-serif',
    heading: 'Poppins, sans-serif'
  },
  borderRadius: '0.5rem'
};

<PlintoProvider theme={customTheme}>
  <App />
</PlintoProvider>
```

### Custom Components

```tsx
// Override default components
<PlintoProvider
  components={{
    SignIn: CustomSignIn,
    SignUp: CustomSignUp,
    UserButton: CustomUserButton
  }}
>
  <App />
</PlintoProvider>
```

## 🔄 Server-Side Rendering

### Next.js Integration

```tsx
// pages/_app.tsx
import { PlintoProvider } from '@plinto/react-sdk';
import { getServerSideAuth } from '@plinto/react-sdk/ssr';

function MyApp({ Component, pageProps }) {
  return (
    <PlintoProvider
      appId={process.env.NEXT_PUBLIC_PLINTO_APP_ID}
      initialAuth={pageProps.auth}
    >
      <Component {...pageProps} />
    </PlintoProvider>
  );
}

// pages/api/auth.ts
export async function getServerSideProps(context) {
  const auth = await getServerSideAuth(context);
  
  return {
    props: {
      auth
    }
  };
}
```

### Remix Integration

```tsx
// root.tsx
import { PlintoProvider } from '@plinto/react-sdk';
import { getAuthFromRequest } from '@plinto/react-sdk/remix';

export async function loader({ request }) {
  const auth = await getAuthFromRequest(request);
  return json({ auth });
}

export default function App() {
  const { auth } = useLoaderData();
  
  return (
    <PlintoProvider initialAuth={auth}>
      <Outlet />
    </PlintoProvider>
  );
}
```

## 🔐 Security

### Token Storage

```tsx
// Configure secure token storage
<PlintoProvider
  storage={{
    getItem: (key) => sessionStorage.getItem(key),
    setItem: (key, value) => sessionStorage.setItem(key, value),
    removeItem: (key) => sessionStorage.removeItem(key)
  }}
  tokenRefreshBuffer={300} // Refresh 5 minutes before expiry
/>
```

### CSRF Protection

```tsx
// Enable CSRF protection
<PlintoProvider
  security={{
    enableCSRF: true,
    csrfTokenHeader: 'X-CSRF-Token'
  }}
/>
```

## 🧪 Testing

### Component Testing

```tsx
// Test with React Testing Library
import { render, screen } from '@testing-library/react';
import { PlintoProvider } from '@plinto/react-sdk';
import { mockAuth } from '@plinto/react-sdk/testing';

test('renders user profile', () => {
  render(
    <PlintoProvider {...mockAuth({ user: { name: 'Test User' } })}>
      <Profile />
    </PlintoProvider>
  );
  
  expect(screen.getByText('Test User')).toBeInTheDocument();
});
```

### Hook Testing

```tsx
// Test hooks with renderHook
import { renderHook } from '@testing-library/react-hooks';
import { useAuth } from '@plinto/react-sdk';
import { createWrapper } from '@plinto/react-sdk/testing';

test('authentication flow', async () => {
  const wrapper = createWrapper();
  const { result } = renderHook(() => useAuth(), { wrapper });
  
  await act(async () => {
    await result.current.signIn({ email, password });
  });
  
  expect(result.current.isAuthenticated).toBe(true);
});
```

## 📦 TypeScript Support

### Type Definitions

```typescript
import type { User, Session, Organization } from '@plinto/react-sdk';

interface AuthState {
  user: User | null;
  session: Session | null;
  organization: Organization | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// Custom user metadata
interface CustomUser extends User {
  metadata: {
    subscription: 'free' | 'pro' | 'enterprise';
    onboardingComplete: boolean;
  };
}
```

## 🎯 Common Patterns

### Protected Routes

```tsx
// Route protection with React Router
import { Navigate } from 'react-router-dom';
import { useAuth } from '@plinto/react-sdk';

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" />;
  
  return children;
}
```

### Role-Based Access

```tsx
// Role-based component rendering
import { useUser } from '@plinto/react-sdk';

function AdminPanel() {
  const { user } = useUser();
  
  if (!user?.roles?.includes('admin')) {
    return <div>Access Denied</div>;
  }
  
  return <AdminContent />;
}
```

### Organization Context

```tsx
// Multi-tenant organization support
import { useOrganization } from '@plinto/react-sdk';

function TeamDashboard() {
  const { organization, members } = useOrganization();
  
  return (
    <div>
      <h1>{organization?.name} Team</h1>
      <MemberList members={members} />
    </div>
  );
}
```

## 🚢 Deployment

### Environment Variables

```env
# Public environment variables
NEXT_PUBLIC_PLINTO_APP_ID=your-app-id
NEXT_PUBLIC_PLINTO_PUBLIC_KEY=your-public-key
NEXT_PUBLIC_PLINTO_API_URL=https://api.plinto.dev

# Server-side only
PLINTO_SECRET_KEY=your-secret-key
PLINTO_WEBHOOK_SECRET=your-webhook-secret
```

## 🛠️ Development

### Local Development

```bash
# Clone the repo
git clone https://github.com/plinto/plinto.git

# Navigate to React package
cd packages/react

# Install dependencies
yarn install

# Start development
yarn dev

# Run tests
yarn test

# Build package
yarn build
```

## 📚 Resources

- [React Hooks Documentation](https://docs.plinto.dev/react/hooks)
- [Component Reference](https://docs.plinto.dev/react/components)
- [SSR Guide](https://docs.plinto.dev/react/ssr)
- [Examples](https://github.com/plinto/react-examples)

## 🎯 Roadmap

### Current Version (0.1.0)
- ✅ Core authentication hooks
- ✅ Essential components
- ✅ SSR support
- ✅ TypeScript support

### Next Release (0.2.0)
- [ ] Suspense support
- [ ] React Server Components
- [ ] Advanced caching
- [ ] Optimistic updates

## 🤝 Contributing

See [React Contributing Guide](../../docs/contributing/react.md) for development guidelines.

## 📄 License

Part of the Plinto platform. See [LICENSE](../../LICENSE) in the root directory.