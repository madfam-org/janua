# @janua/react-sdk Quick Start

Add authentication to your React app in minutes using pre-built components and hooks.

---

## 1. Install

```bash
# npm
npm install @janua/react-sdk

# yarn
yarn add @janua/react-sdk

# pnpm
pnpm add @janua/react-sdk
```

Requires React 18+. Add the MADFAM registry to your `.npmrc`:

```ini
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

---

## 2. Wrap your app with JanuaProvider

Place `JanuaProvider` at the root of your application. It initializes the Janua client and makes authentication state available to all hooks and components below it.

```tsx
// main.tsx or App.tsx
import { JanuaProvider } from '@janua/react-sdk';

function App() {
  return (
    <JanuaProvider
      config={{
        baseURL: 'https://api.janua.dev',
        clientId: 'your-client-id',
        redirectUri: `${window.location.origin}/auth/callback`,
      }}
    >
      <YourApp />
    </JanuaProvider>
  );
}
```

---

## 3. Add a sign-in form with the SignIn component

The `SignIn` component renders a complete sign-in form backed by `@janua/ui`. Theming is inherited from the `appearance` prop on `JanuaProvider`.

```tsx
import { SignIn } from '@janua/react-sdk';

export function SignInPage() {
  return (
    <SignIn
      onSuccess={() => {
        window.location.href = '/dashboard';
      }}
      socialProviders={{ google: true, github: true }}
      enablePasskeys={true}
      signUpUrl="/sign-up"
    />
  );
}
```

---

## 4. Check auth state with useAuth

Use `useAuth` anywhere inside `JanuaProvider` to access the current user, session, and auth methods.

```tsx
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

## 5. Protect routes

Use `AuthGuard` to redirect unauthenticated users at the route level:

```tsx
import { AuthGuard } from '@janua/react-sdk';

function ProtectedPage() {
  return (
    <AuthGuard redirectTo="/sign-in">
      <Dashboard />
    </AuthGuard>
  );
}
```

Use `Protect` when you want to render fallback content instead of redirecting:

```tsx
import { Protect } from '@janua/react-sdk';

function AdminSection() {
  return (
    <Protect role="admin" fallback={<p>You do not have access to this section.</p>}>
      <AdminPanel />
    </Protect>
  );
}
```

Use `SignedIn` and `SignedOut` for simple conditional rendering in layouts:

```tsx
import { SignedIn, SignedOut, UserButton } from '@janua/react-sdk';

function Header() {
  return (
    <nav>
      <SignedIn>
        <UserButton showManageAccount={true} manageAccountUrl="/settings" />
      </SignedIn>
      <SignedOut>
        <a href="/sign-in">Sign in</a>
      </SignedOut>
    </nav>
  );
}
```

---

## 6. Handle OAuth callback

When using `signInWithOAuth`, the provider redirects to your `redirectUri` with `code` and `state` parameters. Handle the callback with `handleOAuthCallback`:

```tsx
import { useEffect } from 'react';
import { useAuth } from '@janua/react-sdk';

function AuthCallback() {
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

## 7. Enable passkeys

```tsx
import { usePasskey } from '@janua/react-sdk';

function PasskeyOption() {
  const { register, authenticate, isSupported, isLoading, error } = usePasskey();

  if (!isSupported) return null;

  return (
    <div>
      {error && <p>{error.message}</p>}
      <button onClick={() => register('My device')} disabled={isLoading}>
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

## 8. Enable two-factor authentication

```tsx
import { useMFA } from '@janua/react-sdk';
import { useState } from 'react';

function MFAEnrollment() {
  const { enable, verify, isLoading, error } = useMFA();
  const [qrCode, setQrCode] = useState('');
  const [code, setCode] = useState('');

  const handleEnable = async () => {
    const result = await enable('totp');
    setQrCode(result.qr_code);
  };

  const handleVerify = async () => {
    await verify(code);
    alert('Two-factor authentication enabled.');
  };

  return (
    <div>
      {error && <p>{error.message}</p>}
      {!qrCode ? (
        <button onClick={handleEnable} disabled={isLoading}>
          Enable 2FA
        </button>
      ) : (
        <div>
          <img src={qrCode} alt="Scan this QR code with your authenticator app" />
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Enter 6-digit code"
            maxLength={6}
          />
          <button onClick={handleVerify} disabled={isLoading}>
            Verify and activate
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## 9. Apply theming

Pass an `appearance` object to `JanuaProvider` to theme all components in the tree:

```tsx
import { JanuaProvider } from '@janua/react-sdk';
import type { JanuaAppearance } from '@janua/react-sdk';

const appearance: JanuaAppearance = {
  accentColor: '#6366f1',
  darkMode: false,
};

function App() {
  return (
    <JanuaProvider config={config} appearance={appearance}>
      <YourApp />
    </JanuaProvider>
  );
}
```

---

## Common patterns at a glance

| Goal | API |
|------|-----|
| Sign in with email/password | `useAuth().signIn(email, password)` |
| Sign in with OAuth | `useAuth().signInWithOAuth(provider)` |
| Sign out | `useAuth().signOut()` |
| Read current user | `useAuth().user` or `useUser().user` |
| Update user profile | `useUser().updateUser({ firstName, lastName })` |
| Access session | `useSession().session` |
| List organizations | `useOrganization().organizations` |
| Register a passkey | `usePasskey().register(name?)` |
| Authenticate with passkey | `usePasskey().authenticate(email?)` |
| Enable MFA | `useMFA().enable('totp')` |
| Verify MFA code | `useMFA().verify(code)` |
| Listen to real-time events | `useRealtime({ channels: ['...'] })` |
| Protect a route | `<AuthGuard redirectTo="/sign-in">` |
| Conditional rendering | `<SignedIn>` / `<SignedOut>` |
| Show user menu | `<UserButton />` |
| Show full profile panel | `<UserProfile />` |

---

## Next steps

- [Full API reference](./README.md) — all hooks, components, and types
- [TypeScript SDK](../typescript-sdk/README.md) — direct API client for advanced use
- [Next.js SDK](../nextjs-sdk/README.md) — server-side rendering and App Router support
- [Janua API docs](https://api.janua.dev/docs) — REST API reference
- [docs.janua.dev](https://docs.janua.dev) — guides and examples
