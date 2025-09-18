# React SDK Complete Guide

> **Comprehensive guide to using the Plinto React SDK with hooks, components, and advanced patterns**

## Overview

The `@plinto/react-sdk` SDK provides React-specific hooks, components, and providers for seamless authentication integration. Built on top of the TypeScript SDK, it offers a declarative, React-native approach to authentication.

## 🚀 Quick Start

### Installation

```bash
npm install @plinto/react-sdk @plinto/typescript-sdk
# or
yarn add @plinto/react-sdk @plinto/typescript-sdk
# or
pnpm add @plinto/react-sdk @plinto/typescript-sdk
```

### Basic Setup

```tsx
import React from 'react';
import { PlintoProvider } from '@plinto/react-sdk';

function App() {
  return (
    <PlintoProvider
      config={{
        apiUrl: 'https://api.plinto.dev',
        apiKey: 'your_api_key' // Optional for public apps
      }}
    >
      <YourApp />
    </PlintoProvider>
  );
}

export default App;
```

### Quick Authentication

```tsx
import React from 'react';
import { useAuth, SignIn, SignUp } from '@plinto/react-sdk';

function AuthenticatedApp() {
  const { user, isLoading, isAuthenticated, signOut } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div>
        <h1>Welcome to My App</h1>
        <SignIn onSuccess={() => console.log('Signed in!')} />
        {/* or */}
        <SignUp onSuccess={() => console.log('Account created!')} />
      </div>
    );
  }

  return (
    <div>
      <h1>Welcome, {user?.name}!</h1>
      <button onClick={signOut}>Sign Out</button>
    </div>
  );
}
```

## 🎯 Core Provider

### PlintoProvider

The root provider that manages authentication state and provides the Plinto client to your app.

```tsx
import { PlintoProvider, type PlintoConfig } from '@plinto/react-sdk';

interface AppProps {
  children: React.ReactNode;
}

function App({ children }: AppProps) {
  const config: PlintoConfig = {
    apiUrl: 'https://api.plinto.dev',
    apiKey: process.env.REACT_APP_PLINTO_API_KEY, // Optional
    enableDebug: process.env.NODE_ENV === 'development',

    // Advanced options
    tokenStorage: 'localStorage', // 'localStorage' | 'sessionStorage' | 'memory'
    autoRefresh: true,
    refreshThreshold: 300, // Refresh tokens 5 minutes before expiry
  };

  return (
    <PlintoProvider config={config}>
      {children}
    </PlintoProvider>
  );
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `apiUrl` | string | Required | Base URL for Plinto API |
| `apiKey` | string | Optional | API key for server-side apps |
| `enableDebug` | boolean | false | Enable debug logging |
| `tokenStorage` | string | 'localStorage' | Where to store auth tokens |
| `autoRefresh` | boolean | true | Automatically refresh tokens |
| `refreshThreshold` | number | 300 | Seconds before expiry to refresh |

## 🪝 Authentication Hooks

### useAuth

Primary hook for authentication state and actions.

```tsx
import { useAuth } from '@plinto/react-sdk';

function ProfileComponent() {
  const {
    user,
    session,
    isLoading,
    isAuthenticated,
    signIn,
    signOut
  } = useAuth();

  const handleSignIn = async () => {
    try {
      await signIn('user@example.com', 'password123');
      console.log('Signed in successfully');
    } catch (error) {
      console.error('Sign in failed:', error);
    }
  };

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      {isAuthenticated ? (
        <div>
          <h2>Welcome, {user?.name}!</h2>
          <p>Email: {user?.email}</p>
          <button onClick={signOut}>Sign Out</button>
        </div>
      ) : (
        <button onClick={handleSignIn}>Sign In</button>
      )}
    </div>
  );
}
```

#### useAuth Return Values

| Property | Type | Description |
|----------|------|-------------|
| `user` | User \| null | Current authenticated user |
| `session` | Session \| null | Current session info |
| `isLoading` | boolean | Loading state |
| `isAuthenticated` | boolean | Authentication status |
| `signIn` | Function | Sign in with email/password |
| `signOut` | Function | Sign out current user |

### useSession

Hook for session management and monitoring.

```tsx
import { useSession } from '@plinto/react-sdk';

function SessionMonitor() {
  const {
    session,
    isValid,
    expiresAt,
    timeUntilExpiry,
    refresh,
    terminate
  } = useSession();

  if (!session) return null;

  return (
    <div className="session-monitor">
      <h3>Session Status</h3>
      <p>Valid: {isValid ? '✅' : '❌'}</p>
      <p>Expires: {expiresAt?.toLocaleString()}</p>
      <p>Time until expiry: {Math.floor(timeUntilExpiry / 60)} minutes</p>

      <div>
        <button onClick={refresh}>Refresh Session</button>
        <button onClick={terminate}>End Session</button>
      </div>
    </div>
  );
}
```

#### useSession Return Values

| Property | Type | Description |
|----------|------|-------------|
| `session` | Session \| null | Current session |
| `isValid` | boolean | Session validity |
| `expiresAt` | Date \| null | Session expiration |
| `timeUntilExpiry` | number | Seconds until expiry |
| `refresh` | Function | Refresh session |
| `terminate` | Function | Terminate session |

### useOrganization

Hook for organization management in multi-tenant apps.

```tsx
import { useOrganization } from '@plinto/react-sdk';

function OrganizationSelector() {
  const {
    currentOrganization,
    organizations,
    isLoading,
    switchOrganization,
    createOrganization,
    inviteUser
  } = useOrganization();

  if (isLoading) return <div>Loading organizations...</div>;

  return (
    <div>
      <h3>Current Organization: {currentOrganization?.name}</h3>

      <select
        value={currentOrganization?.id || ''}
        onChange={(e) => switchOrganization(e.target.value)}
      >
        {organizations.map(org => (
          <option key={org.id} value={org.id}>
            {org.name}
          </option>
        ))}
      </select>

      <button
        onClick={() => createOrganization('New Organization')}
      >
        Create Organization
      </button>

      <button
        onClick={() => inviteUser('user@example.com', 'member')}
      >
        Invite User
      </button>
    </div>
  );
}
```

#### useOrganization Return Values

| Property | Type | Description |
|----------|------|-------------|
| `currentOrganization` | Organization \| null | Active organization |
| `organizations` | Organization[] | User's organizations |
| `isLoading` | boolean | Loading state |
| `switchOrganization` | Function | Switch to different org |
| `createOrganization` | Function | Create new organization |
| `inviteUser` | Function | Invite user to org |
| `updateOrganization` | Function | Update org details |
| `deleteOrganization` | Function | Delete organization |

## 🧩 Pre-built Components

### SignIn Component

Complete sign-in form with email/password and passkey support.

```tsx
import { SignIn } from '@plinto/react-sdk';

function LoginPage() {
  return (
    <div className="login-container">
      <h1>Sign In to Your Account</h1>

      <SignIn
        onSuccess={() => {
          console.log('User signed in successfully');
          // Redirect or update state
        }}
        onError={(error) => {
          console.error('Sign in failed:', error);
          // Show error message
        }}
        className="custom-signin-form"
        redirectTo="/dashboard"
        enablePasskeys={true}
      />
    </div>
  );
}
```

#### SignIn Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | () => void | undefined | Called on successful sign in |
| `onError` | (error: Error) => void | undefined | Called on sign in error |
| `className` | string | '' | CSS class for styling |
| `redirectTo` | string | undefined | URL to redirect after sign in |
| `enablePasskeys` | boolean | true | Show passkey sign in option |

### SignUp Component

Complete registration form with validation.

```tsx
import { SignUp } from '@plinto/react-sdk';

function RegisterPage() {
  return (
    <div className="register-container">
      <h1>Create Your Account</h1>

      <SignUp
        onSuccess={(user) => {
          console.log('Account created for:', user.email);
          // Welcome new user
        }}
        onError={(error) => {
          console.error('Registration failed:', error);
        }}
        className="custom-signup-form"
        redirectTo="/onboarding"
        requireEmailVerification={true}
        enableInviteCode={true}
      />
    </div>
  );
}
```

#### SignUp Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | (user: User) => void | undefined | Called on successful sign up |
| `onError` | (error: Error) => void | undefined | Called on sign up error |
| `className` | string | '' | CSS class for styling |
| `redirectTo` | string | undefined | URL to redirect after sign up |
| `requireEmailVerification` | boolean | false | Require email verification |
| `enableInviteCode` | boolean | false | Show invite code field |

### UserProfile Component

User profile display and editing component.

```tsx
import { UserProfile } from '@plinto/react-sdk';

function ProfilePage() {
  return (
    <div className="profile-page">
      <h1>Your Profile</h1>

      <UserProfile
        editable={true}
        showAvatar={true}
        showMFA={true}
        showSessions={true}
        onProfileUpdate={(user) => {
          console.log('Profile updated:', user);
        }}
        onError={(error) => {
          console.error('Profile error:', error);
        }}
        className="user-profile-component"
      />
    </div>
  );
}
```

#### UserProfile Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `editable` | boolean | true | Allow profile editing |
| `showAvatar` | boolean | true | Show avatar upload |
| `showMFA` | boolean | true | Show MFA settings |
| `showSessions` | boolean | false | Show active sessions |
| `onProfileUpdate` | (user: User) => void | undefined | Called on profile update |
| `onError` | (error: Error) => void | undefined | Called on errors |
| `className` | string | '' | CSS class for styling |

## 🔐 Advanced Authentication Patterns

### Protected Routes

Create route guards using authentication state.

```tsx
import { useAuth } from '@plinto/react-sdk';
import { Navigate } from 'react-router-dom';

interface ProtectedRouteProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  redirectTo?: string;
}

function ProtectedRoute({
  children,
  fallback,
  redirectTo = '/login'
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div>Checking authentication...</div>;
  }

  if (!isAuthenticated) {
    return fallback ? <>{fallback}</> : <Navigate to={redirectTo} replace />;
  }

  return <>{children}</>;
}

// Usage
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
      </Routes>
    </Router>
  );
}
```

### Role-Based Access Control

```tsx
import { useAuth } from '@plinto/react-sdk';

interface RoleGuardProps {
  children: React.ReactNode;
  requiredRole: string;
  fallback?: React.ReactNode;
}

function RoleGuard({ children, requiredRole, fallback }: RoleGuardProps) {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated || !user) {
    return fallback ? <>{fallback}</> : null;
  }

  const hasRequiredRole = user.roles?.includes(requiredRole);

  return hasRequiredRole ? <>{children}</> : (fallback ? <>{fallback}</> : null);
}

// Usage
function AdminPanel() {
  return (
    <RoleGuard
      requiredRole="admin"
      fallback={<div>Access denied: Admin role required</div>}
    >
      <AdminDashboard />
    </RoleGuard>
  );
}
```

### Magic Link Authentication

```tsx
import { usePlinto } from '@plinto/react-sdk';
import { useState } from 'react';

function MagicLinkSignIn() {
  const { client } = usePlinto();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const sendMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await client.sendMagicLink({
        email,
        redirectUrl: `${window.location.origin}/auth/callback`
      });
      setSent(true);
    } catch (error) {
      console.error('Failed to send magic link:', error);
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div>
        <h2>Check Your Email</h2>
        <p>We've sent a magic link to {email}</p>
      </div>
    );
  }

  return (
    <form onSubmit={sendMagicLink}>
      <h2>Sign In with Magic Link</h2>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Enter your email"
        required
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Sending...' : 'Send Magic Link'}
      </button>
    </form>
  );
}
```

### Multi-Factor Authentication

```tsx
import { usePlinto } from '@plinto/react-sdk';
import { useState, useEffect } from 'react';

function MFASetup() {
  const { client, user } = usePlinto();
  const [qrCode, setQrCode] = useState<string>('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [verificationCode, setVerificationCode] = useState('');
  const [step, setStep] = useState<'setup' | 'verify' | 'complete'>('setup');

  const setupMFA = async () => {
    try {
      const response = await client.enableMFA(user?.password || '');
      setQrCode(response.qr_code);
      setBackupCodes(response.backup_codes);
      setStep('verify');
    } catch (error) {
      console.error('MFA setup failed:', error);
    }
  };

  const verifyMFA = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await client.verifyMFA(verificationCode);
      setStep('complete');
    } catch (error) {
      console.error('MFA verification failed:', error);
    }
  };

  return (
    <div className="mfa-setup">
      {step === 'setup' && (
        <div>
          <h2>Enable Two-Factor Authentication</h2>
          <button onClick={setupMFA}>Setup MFA</button>
        </div>
      )}

      {step === 'verify' && (
        <div>
          <h2>Scan QR Code</h2>
          <img src={qrCode} alt="MFA QR Code" />

          <h3>Backup Codes</h3>
          <ul>
            {backupCodes.map((code, i) => (
              <li key={i}><code>{code}</code></li>
            ))}
          </ul>

          <form onSubmit={verifyMFA}>
            <input
              type="text"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              placeholder="Enter 6-digit code"
              maxLength={6}
              required
            />
            <button type="submit">Verify & Enable</button>
          </form>
        </div>
      )}

      {step === 'complete' && (
        <div>
          <h2>✅ MFA Enabled</h2>
          <p>Two-factor authentication is now active.</p>
        </div>
      )}
    </div>
  );
}
```

## 🎨 Custom Styling

### Default Styles

The React components include basic Tailwind CSS classes. You can override them:

```tsx
import { SignIn } from '@plinto/react-sdk';
import './custom-auth.css';

function CustomStyledSignIn() {
  return (
    <SignIn
      className="my-custom-signin"
      // Override default styles with CSS
    />
  );
}
```

```css
/* custom-auth.css */
.my-custom-signin {
  max-width: 400px;
  margin: 0 auto;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.my-custom-signin input {
  border: 2px solid #e5e7eb;
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 1rem;
}

.my-custom-signin button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 6px;
  padding: 0.75rem 1.5rem;
  font-weight: 600;
  color: white;
  transition: all 0.2s;
}

.my-custom-signin button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

### Custom Components

Build your own components using the hooks:

```tsx
import { useAuth } from '@plinto/react-sdk';
import { useState } from 'react';

function CustomSignInForm() {
  const { signIn, isLoading } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    rememberMe: false
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    // Custom validation
    const newErrors: Record<string, string> = {};
    if (!formData.email) newErrors.email = 'Email is required';
    if (!formData.password) newErrors.password = 'Password is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    try {
      await signIn(formData.email, formData.password);
      // Handle success
    } catch (error) {
      setErrors({ submit: 'Invalid email or password' });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={formData.email}
          onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
          className={errors.email ? 'border-red-500' : ''}
        />
        {errors.email && <span className="text-red-500">{errors.email}</span>}
      </div>

      <div>
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={formData.password}
          onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
          className={errors.password ? 'border-red-500' : ''}
        />
        {errors.password && <span className="text-red-500">{errors.password}</span>}
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            checked={formData.rememberMe}
            onChange={(e) => setFormData(prev => ({ ...prev, rememberMe: e.target.checked }))}
          />
          Remember me
        </label>
      </div>

      {errors.submit && (
        <div className="text-red-500">{errors.submit}</div>
      )}

      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {isLoading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
}
```

## 🔧 Advanced Patterns

### Error Boundary for Auth

```tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

class AuthErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Authentication error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="auth-error">
          <h2>Authentication Error</h2>
          <p>Something went wrong with authentication.</p>
          <button onClick={() => this.setState({ hasError: false })}>
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// Usage
function App() {
  return (
    <AuthErrorBoundary>
      <PlintoProvider config={config}>
        <YourApp />
      </PlintoProvider>
    </AuthErrorBoundary>
  );
}
```

### Custom Token Storage

```tsx
import { PlintoProvider } from '@plinto/react-sdk';

// Custom storage implementation
class SecureTokenStorage {
  private encryptionKey: string;

  constructor(key: string) {
    this.encryptionKey = key;
  }

  setItem(key: string, value: string): void {
    const encrypted = this.encrypt(value);
    localStorage.setItem(key, encrypted);
  }

  getItem(key: string): string | null {
    const encrypted = localStorage.getItem(key);
    return encrypted ? this.decrypt(encrypted) : null;
  }

  removeItem(key: string): void {
    localStorage.removeItem(key);
  }

  private encrypt(value: string): string {
    // Implement your encryption logic
    return btoa(value); // Simple base64 for demo
  }

  private decrypt(value: string): string {
    // Implement your decryption logic
    return atob(value); // Simple base64 for demo
  }
}

function App() {
  const tokenStorage = new SecureTokenStorage('your-encryption-key');

  const config = {
    apiUrl: 'https://api.plinto.dev',
    customTokenStorage: tokenStorage
  };

  return (
    <PlintoProvider config={config}>
      <YourApp />
    </PlintoProvider>
  );
}
```

### Optimistic Updates

```tsx
import { useAuth, useOrganization } from '@plinto/react-sdk';
import { useState } from 'react';

function OptimisticUserUpdate() {
  const { user, updateProfile } = useAuth();
  const [localUser, setLocalUser] = useState(user);
  const [isUpdating, setIsUpdating] = useState(false);

  const handleUpdate = async (updates: Partial<User>) => {
    // Optimistic update
    setLocalUser(prev => prev ? { ...prev, ...updates } : null);
    setIsUpdating(true);

    try {
      const updatedUser = await updateProfile(updates);
      setLocalUser(updatedUser);
    } catch (error) {
      // Revert optimistic update
      setLocalUser(user);
      console.error('Update failed:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div>
      <h2>Profile: {localUser?.name}</h2>
      {isUpdating && <span>Updating...</span>}

      <button
        onClick={() => handleUpdate({ name: 'New Name' })}
        disabled={isUpdating}
      >
        Update Name
      </button>
    </div>
  );
}
```

## 📊 Testing

### Jest Testing Setup

```tsx
// test-utils.tsx
import React from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { PlintoProvider } from '@plinto/react-sdk';

const mockConfig = {
  apiUrl: 'https://test-api.plinto.dev',
  enableDebug: false
};

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  providerProps?: any;
}

const customRender = (
  ui: React.ReactElement,
  { providerProps, ...renderOptions }: CustomRenderOptions = {}
) => {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <PlintoProvider config={mockConfig} {...providerProps}>
      {children}
    </PlintoProvider>
  );

  return render(ui, { wrapper: Wrapper, ...renderOptions });
};

export * from '@testing-library/react';
export { customRender as render };
```

### Component Testing

```tsx
// SignIn.test.tsx
import { render, screen, fireEvent, waitFor } from './test-utils';
import { SignIn } from '@plinto/react-sdk';

// Mock the Plinto client
jest.mock('@plinto/typescript-sdk', () => ({
  PlintoClient: jest.fn().mockImplementation(() => ({
    signIn: jest.fn(),
    getCurrentUser: jest.fn()
  }))
}));

describe('SignIn Component', () => {
  it('renders sign in form', () => {
    render(<SignIn />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('calls onSuccess when sign in succeeds', async () => {
    const mockOnSuccess = jest.fn();
    render(<SignIn onSuccess={mockOnSuccess} />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' }
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' }
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });
});
```

### Hook Testing

```tsx
// useAuth.test.tsx
import { renderHook, act } from '@testing-library/react';
import { useAuth } from '@plinto/react-sdk';
import { PlintoProvider } from '@plinto/react-sdk';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <PlintoProvider config={{ apiUrl: 'https://test-api.plinto.dev' }}>
    {children}
  </PlintoProvider>
);

describe('useAuth Hook', () => {
  it('provides authentication state', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBe(null);
    expect(typeof result.current.signIn).toBe('function');
    expect(typeof result.current.signOut).toBe('function');
  });

  it('updates state after sign in', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.signIn('test@example.com', 'password123');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toBeTruthy();
  });
});
```

## 📚 API Reference

### Types

```tsx
interface User {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
  roles?: string[];
  organizations?: Organization[];
}

interface Session {
  id: string;
  user_id: string;
  expires_at: string;
  created_at: string;
  last_accessed_at: string;
  ip_address?: string;
  user_agent?: string;
}

interface Organization {
  id: string;
  name: string;
  slug?: string;
  avatar?: string;
  created_at: string;
  updated_at: string;
  role?: string; // User's role in this organization
  member_count?: number;
}

interface PlintoConfig {
  apiUrl: string;
  apiKey?: string;
  enableDebug?: boolean;
  tokenStorage?: 'localStorage' | 'sessionStorage' | 'memory';
  autoRefresh?: boolean;
  refreshThreshold?: number;
  customTokenStorage?: TokenStorage;
}

interface TokenStorage {
  setItem(key: string, value: string): void;
  getItem(key: string): string | null;
  removeItem(key: string): void;
}
```

### Error Handling

```tsx
import { PlintoError, AuthenticationError, ValidationError } from '@plinto/react-sdk';

function ErrorHandlingExample() {
  const { signIn } = useAuth();

  const handleSignIn = async (email: string, password: string) => {
    try {
      await signIn(email, password);
    } catch (error) {
      if (error instanceof AuthenticationError) {
        console.log('Authentication failed:', error.message);
      } else if (error instanceof ValidationError) {
        console.log('Validation error:', error.field, error.message);
      } else if (error instanceof PlintoError) {
        console.log('Plinto API error:', error.code, error.message);
      } else {
        console.log('Unexpected error:', error);
      }
    }
  };
}
```

## 🔗 Related Documentation

- **[TypeScript SDK](../packages/typescript-sdk/README.md)** - Core SDK documentation
- **[Next.js Integration](../packages/nextjs/README.md)** - Next.js specific patterns
- **[API Reference](../api/README.md)** - Complete API documentation
- **[Authentication Flows](../api/authentication.md)** - Auth implementation guide

## 🎯 Best Practices

### 1. Provider Placement
```tsx
// ✅ Good: Single provider at app root
function App() {
  return (
    <PlintoProvider config={config}>
      <Router>
        <Routes>
          <Route path="/*" element={<AppRoutes />} />
        </Routes>
      </Router>
    </PlintoProvider>
  );
}

// ❌ Bad: Multiple providers
function BadExample() {
  return (
    <Router>
      <Routes>
        <Route
          path="/auth"
          element={
            <PlintoProvider config={config}>
              <AuthPage />
            </PlintoProvider>
          }
        />
      </Routes>
    </Router>
  );
}
```

### 2. Error Handling
```tsx
// ✅ Good: Comprehensive error handling
function AuthForm() {
  const { signIn } = useAuth();
  const [error, setError] = useState<string>('');

  const handleSubmit = async (data: SignInData) => {
    try {
      setError('');
      await signIn(data.email, data.password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed');
    }
  };
}

// ❌ Bad: Silent error handling
function BadAuthForm() {
  const { signIn } = useAuth();

  const handleSubmit = async (data: SignInData) => {
    try {
      await signIn(data.email, data.password);
    } catch (err) {
      // Silent failure
    }
  };
}
```

### 3. Loading States
```tsx
// ✅ Good: Proper loading states
function UserDashboard() {
  const { user, isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <SignInPrompt />;
  }

  return <Dashboard user={user} />;
}

// ❌ Bad: No loading states
function BadDashboard() {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <SignInPrompt />;
  }

  return <Dashboard user={user} />; // user might be null
}
```

---

**📦 [Package Repository](https://github.com/plinto-dev/react-sdk)** • **🔗 [API Reference](../api/README.md)** • **🚀 [Quick Start Examples](../examples/react/)**