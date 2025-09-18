# Plinto React SDK Quick Start

> **Add authentication to your React app in minutes with pre-built components and hooks**

## Installation

```bash
npm install @plinto/react-sdk @plinto/typescript-sdk
# or
yarn add @plinto/react-sdk @plinto/typescript-sdk
# or
pnpm add @plinto/react-sdk @plinto/typescript-sdk
```

## Quick Setup

### 1. Wrap Your App with PlintoProvider

```tsx
// App.tsx or index.tsx
import { PlintoProvider } from '@plinto/react-sdk';

function App() {
  return (
    <PlintoProvider
      config={{
        baseUrl: 'https://plinto.dev',
        tenantId: 'your-tenant-id', // Get from Plinto Dashboard
      }}
    >
      <YourApp />
    </PlintoProvider>
  );
}
```

### 2. Add Pre-built Auth Components

```tsx
import { SignIn, SignUp, UserButton } from '@plinto/react-sdk';

// Sign In Page
export function SignInPage() {
  return (
    <SignIn
      redirectUrl="/dashboard"
      appearance={{
        theme: 'light', // or 'dark', 'auto'
        primaryColor: '#6366f1',
        borderRadius: 'md',
      }}
    />
  );
}

// Sign Up Page
export function SignUpPage() {
  return (
    <SignUp
      redirectUrl="/onboarding"
      additionalFields={['firstName', 'lastName', 'company']}
      termsUrl="/terms"
      privacyUrl="/privacy"
    />
  );
}

// User Menu in Header
export function Header() {
  return (
    <header>
      <nav>
        <UserButton
          afterSignOutUrl="/"
          appearance={{
            elements: {
              avatarBox: 'w-10 h-10',
            },
          }}
        />
      </nav>
    </header>
  );
}
```

## React Hooks

### useAuth Hook

```tsx
import { useAuth } from '@plinto/react-sdk';

function Dashboard() {
  const { 
    user,
    session,
    isAuthenticated,
    isLoading,
    signOut,
    updateProfile,
  } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <div>Please sign in</div>;
  }

  return (
    <div>
      <h1>Welcome, {user.email}!</h1>
      <p>User ID: {user.id}</p>
      <p>Session expires: {new Date(session.expiresAt).toLocaleString()}</p>
      
      <button onClick={() => updateProfile({ firstName: 'New Name' })}>
        Update Name
      </button>
      
      <button onClick={signOut}>
        Sign Out
      </button>
    </div>
  );
}
```

### useUser Hook

```tsx
import { useUser } from '@plinto/react-sdk';

function Profile() {
  const { user, isLoaded, update } = useUser();

  if (!isLoaded) return <div>Loading user...</div>;
  if (!user) return <div>No user found</div>;

  return (
    <div>
      <h2>{user.firstName} {user.lastName}</h2>
      <p>{user.email}</p>
      
      <button onClick={() => update({ phoneNumber: '+1234567890' })}>
        Add Phone
      </button>
    </div>
  );
}
```

### useSession Hook

```tsx
import { useSession } from '@plinto/react-sdk';

function SessionInfo() {
  const { session, refresh, revoke } = useSession();

  if (!session) return null;

  return (
    <div>
      <p>Session ID: {session.id}</p>
      <p>Expires in: {session.expiresIn} seconds</p>
      
      <button onClick={refresh}>Refresh Token</button>
      <button onClick={revoke}>Revoke Session</button>
    </div>
  );
}
```

### useOrganization Hook

```tsx
import { useOrganization } from '@plinto/react-sdk';

function OrgSwitcher() {
  const {
    organization,
    organizations,
    isLoaded,
    setActive,
    create,
    inviteMember,
  } = useOrganization();

  const handleCreateOrg = async () => {
    const newOrg = await create({
      name: 'New Company',
      slug: 'new-company',
    });
    await setActive(newOrg.id);
  };

  return (
    <div>
      <h3>Current Org: {organization?.name}</h3>
      
      <select 
        value={organization?.id}
        onChange={(e) => setActive(e.target.value)}
      >
        {organizations.map(org => (
          <option key={org.id} value={org.id}>
            {org.name}
          </option>
        ))}
      </select>
      
      <button onClick={handleCreateOrg}>
        Create Organization
      </button>
      
      <button onClick={() => inviteMember('user@example.com', 'member')}>
        Invite Member
      </button>
    </div>
  );
}
```

## Component Customization

### Theming

```tsx
import { SignIn } from '@plinto/react-sdk';

<SignIn
  appearance={{
    theme: 'dark',
    primaryColor: '#8b5cf6',
    borderRadius: 'lg',
    fontFamily: 'Inter, sans-serif',
    elements: {
      card: 'shadow-2xl',
      formButtonPrimary: 'bg-gradient-to-r from-purple-500 to-pink-500',
      formFieldInput: 'border-gray-300 focus:border-purple-500',
      headerTitle: 'text-3xl font-bold',
      headerSubtitle: 'text-gray-600',
      footer: 'hidden', // Hide footer
    },
  }}
/>
```

### Custom Fields

```tsx
import { SignUp } from '@plinto/react-sdk';

<SignUp
  additionalFields={[
    {
      name: 'company',
      label: 'Company Name',
      type: 'text',
      required: true,
      placeholder: 'Acme Inc.',
    },
    {
      name: 'role',
      label: 'Your Role',
      type: 'select',
      options: [
        { value: 'developer', label: 'Developer' },
        { value: 'designer', label: 'Designer' },
        { value: 'manager', label: 'Manager' },
      ],
    },
    {
      name: 'acceptTerms',
      label: 'I accept the terms and conditions',
      type: 'checkbox',
      required: true,
    },
  ]}
  onSuccess={(user) => {
    console.log('User signed up:', user);
    // Custom logic after signup
  }}
/>
```

### Custom Components

```tsx
import { useAuth } from '@plinto/react-sdk';

function CustomSignIn() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await signIn({ email, password });
      // Redirect handled by provider
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      
      {error && <div className="error">{error}</div>}
      
      <button type="submit" disabled={loading}>
        {loading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
}
```

## Protected Routes

### React Router

```tsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@plinto/react-sdk';

function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/sign-in" />;
}

// Usage in router
<Routes>
  <Route path="/sign-in" element={<SignIn />} />
  <Route path="/sign-up" element={<SignUp />} />
  
  <Route element={<ProtectedRoute />}>
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/profile" element={<Profile />} />
    <Route path="/settings" element={<Settings />} />
  </Route>
</Routes>
```

### Custom Guard Component

```tsx
import { useAuth } from '@plinto/react-sdk';

interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  requiredRole?: string;
  requiredPermission?: string;
}

function AuthGuard({ 
  children, 
  fallback = <Navigate to="/sign-in" />,
  requiredRole,
  requiredPermission,
}: AuthGuardProps) {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div>Checking authentication...</div>;
  }

  if (!isAuthenticated) {
    return <>{fallback}</>;
  }

  if (requiredRole && user.role !== requiredRole) {
    return <div>Insufficient permissions</div>;
  }

  if (requiredPermission && !user.permissions?.includes(requiredPermission)) {
    return <div>Permission denied</div>;
  }

  return <>{children}</>;
}

// Usage
<AuthGuard requiredRole="admin">
  <AdminPanel />
</AuthGuard>
```

## Social Login

```tsx
import { SignIn } from '@plinto/react-sdk';

<SignIn
  providers={['google', 'github', 'microsoft']}
  appearance={{
    elements: {
      socialButtonsContainer: 'flex gap-2',
      socialButton: 'flex-1',
    },
  }}
/>

// Or with custom social buttons
import { useAuth } from '@plinto/react-sdk';

function SocialAuth() {
  const { signInWithProvider } = useAuth();

  return (
    <div>
      <button onClick={() => signInWithProvider('google')}>
        <img src="/google-logo.svg" alt="Google" />
        Continue with Google
      </button>
      
      <button onClick={() => signInWithProvider('github')}>
        <img src="/github-logo.svg" alt="GitHub" />
        Continue with GitHub
      </button>
    </div>
  );
}
```

## Passkeys (WebAuthn)

```tsx
import { usePasskeys } from '@plinto/react-sdk';

function PasskeySetup() {
  const { 
    passkeys,
    register,
    authenticate,
    remove,
    isSupported,
  } = usePasskeys();

  if (!isSupported) {
    return <div>Passkeys not supported on this device</div>;
  }

  const handleRegister = async () => {
    try {
      await register({
        displayName: 'My MacBook',
      });
      alert('Passkey registered successfully!');
    } catch (error) {
      console.error('Failed to register passkey:', error);
    }
  };

  return (
    <div>
      <h3>Passkeys</h3>
      
      {passkeys.length === 0 ? (
        <button onClick={handleRegister}>
          Add Passkey
        </button>
      ) : (
        <ul>
          {passkeys.map(passkey => (
            <li key={passkey.id}>
              {passkey.displayName}
              <button onClick={() => remove(passkey.id)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      
      <button onClick={authenticate}>
        Sign in with Passkey
      </button>
    </div>
  );
}
```

## Multi-Factor Authentication

```tsx
import { useMFA } from '@plinto/react-sdk';

function MFASettings() {
  const {
    isMFAEnabled,
    availableMethods,
    enabledMethods,
    enable,
    disable,
    verify,
  } = useMFA();

  const [showQR, setShowQR] = useState(false);
  const [qrCode, setQRCode] = useState('');
  const [verifyCode, setVerifyCode] = useState('');

  const handleEnableTOTP = async () => {
    const { qrCode, secret } = await enable('totp');
    setQRCode(qrCode);
    setShowQR(true);
  };

  const handleVerify = async () => {
    try {
      await verify('totp', verifyCode);
      alert('MFA enabled successfully!');
      setShowQR(false);
    } catch (error) {
      alert('Invalid code. Please try again.');
    }
  };

  return (
    <div>
      <h3>Two-Factor Authentication</h3>
      
      {!isMFAEnabled ? (
        <button onClick={handleEnableTOTP}>
          Enable 2FA
        </button>
      ) : (
        <button onClick={() => disable('totp')}>
          Disable 2FA
        </button>
      )}
      
      {showQR && (
        <div>
          <img src={qrCode} alt="QR Code" />
          <p>Scan with your authenticator app</p>
          
          <input
            type="text"
            value={verifyCode}
            onChange={(e) => setVerifyCode(e.target.value)}
            placeholder="Enter 6-digit code"
            maxLength={6}
          />
          
          <button onClick={handleVerify}>
            Verify and Enable
          </button>
        </div>
      )}
    </div>
  );
}
```

## TypeScript Support

All components and hooks are fully typed:

```tsx
import type { 
  User, 
  Session, 
  Organization,
  SignInProps,
  SignUpProps,
  UserButtonProps,
  Appearance,
} from '@plinto/react-sdk';

// Type-safe component props
const signInProps: SignInProps = {
  redirectUrl: '/dashboard',
  appearance: {
    theme: 'light',
    primaryColor: '#6366f1',
  },
};

// Type-safe hooks
const { user }: { user: User | null } = useUser();
```

## Error Handling

```tsx
import { ErrorBoundary } from '@plinto/react-sdk';

<ErrorBoundary
  fallback={({ error, retry }) => (
    <div>
      <h2>Something went wrong</h2>
      <p>{error.message}</p>
      <button onClick={retry}>Try Again</button>
    </div>
  )}
>
  <YourApp />
</ErrorBoundary>
```

## Testing

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { PlintoProvider, MockPlintoProvider } from '@plinto/react-sdk';
import { Dashboard } from './Dashboard';

// Mock provider for testing
test('renders dashboard for authenticated user', async () => {
  const mockUser = {
    id: '123',
    email: 'test@example.com',
    firstName: 'Test',
    lastName: 'User',
  };

  render(
    <MockPlintoProvider user={mockUser} isAuthenticated={true}>
      <Dashboard />
    </MockPlintoProvider>
  );

  await waitFor(() => {
    expect(screen.getByText('Welcome, test@example.com!')).toBeInTheDocument();
  });
});
```

## Best Practices

1. **Always wrap your app with PlintoProvider** at the root level
2. **Use built-in components** when possible for consistency
3. **Handle loading states** appropriately in your UI
4. **Implement error boundaries** for graceful error handling
5. **Use TypeScript** for better type safety and IDE support
6. **Test with MockPlintoProvider** for unit tests
7. **Secure sensitive routes** with authentication guards
8. **Implement proper logout** to clear all session data

## Support

- **Documentation**: [docs.plinto.dev](https://docs.plinto.dev)
- **Examples**: [github.com/plinto/examples](https://github.com/plinto/examples)
- **Discord**: [discord.gg/plinto](https://discord.gg/plinto)
- **Email**: react-support@plinto.dev

## License

MIT - See [LICENSE](./LICENSE) for details