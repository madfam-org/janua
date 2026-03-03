# @janua/nextjs

Official Janua SDK for Next.js applications. Designed exclusively for the App Router with full support for React Server Components, client components, middleware, and edge runtimes.

## Requirements

- Next.js 14.0.0 or higher
- React 17.0.0 or higher
- Node.js 14.0.0 or higher

## Installation

```bash
npm install @janua/nextjs
# or
yarn add @janua/nextjs
# or
pnpm add @janua/nextjs
```

### NPM Registry Configuration

This package is published to the MADFAM private registry. Add the following to your `.npmrc`:

```
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

---

## Quick Start

### 1. Environment Variables

Add your Janua credentials to `.env.local`:

```env
NEXT_PUBLIC_API_URL=https://api.janua.dev
JANUA_JWT_SECRET=your-jwt-secret
```

### 2. Wrap Your Application with JanuaProvider

Place `JanuaProvider` at the root of your layout. It accepts a `config` object with your Janua API configuration.

```tsx
// app/layout.tsx
import { JanuaProvider } from '@janua/nextjs';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <JanuaProvider config={{ baseURL: process.env.NEXT_PUBLIC_API_URL! }}>
          {children}
        </JanuaProvider>
      </body>
    </html>
  );
}
```

### 3. Add Authentication Components

```tsx
// app/page.tsx
import { SignedIn, SignedOut, SignIn, UserButton } from '@janua/nextjs';

export default function HomePage() {
  return (
    <div>
      <SignedIn>
        <UserButton />
      </SignedIn>
      <SignedOut>
        <SignIn redirectTo="/dashboard" />
      </SignedOut>
    </div>
  );
}
```

### 4. Add Route Protection Middleware

```ts
// middleware.ts
import { withAuth } from '@janua/nextjs/middleware';

export default withAuth({
  publicRoutes: ['/', '/login', '/signup'],
});

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|public).*)'],
};
```

---

## Import Paths

The package exposes four entry points:

| Import path | Contents |
|---|---|
| `@janua/nextjs` | All exports: provider, hooks, components, server utilities, middleware |
| `@janua/nextjs/app` | App Router exports only (provider, hooks, components, server) |
| `@janua/nextjs/middleware` | `createJanuaMiddleware`, `withAuth`, `config` |
| `@janua/nextjs/edge` | `createEdgeMiddleware` (lightweight, edge-runtime safe) |

---

## JanuaProvider

`JanuaProvider` is a React context provider that initializes the Janua client, manages authentication state, handles OAuth callbacks (including PKCE verification), and schedules proactive token refresh.

```tsx
'use client'; // or place in a Server Component layout — JanuaProvider handles the client boundary internally

import { JanuaProvider } from '@janua/nextjs';
import type { JanuaProviderProps } from '@janua/nextjs';
```

### Props

| Prop | Type | Required | Description |
|---|---|---|---|
| `config` | `JanuaConfig` | Yes | Janua client configuration (passed to `JanuaClient`) |
| `children` | `React.ReactNode` | Yes | Child components |
| `onAuthChange` | `(user: User \| null) => void` | No | Callback invoked whenever authentication state changes |

### Token Auto-Refresh

`JanuaProvider` proactively refreshes access tokens before they expire. It reads the `exp` claim from the current access token JWT and schedules a refresh 60 seconds before expiry. If the token has less than 60 seconds remaining, a refresh is attempted immediately. This runs entirely client-side and requires no additional configuration.

### OAuth and PKCE Callback Handling

On mount, `JanuaProvider` inspects the current URL for `code` and `state` query parameters. When found, it:

1. Validates the `state` parameter against the stored PKCE state to prevent CSRF attacks.
2. Retrieves the stored PKCE code verifier.
3. Exchanges the authorization code for tokens via `client.auth.handleOAuthCallback`.
4. Clears PKCE state from storage and removes the query parameters from the URL.

No manual callback handling is required for OAuth flows when `JanuaProvider` is present.

---

## Client Hooks

All hooks must be used within a component that is a descendant of `JanuaProvider`. Mark the component with `'use client'`.

### `useAuth()`

Returns authentication state and the low-level auth client.

```tsx
'use client';
import { useAuth } from '@janua/nextjs';

export function AuthStatus() {
  const { isAuthenticated, isLoading, user, session, signOut, auth } = useAuth();

  if (isLoading) return <p>Loading...</p>;
  if (!isAuthenticated) return <p>Not signed in.</p>;

  return (
    <div>
      <p>Signed in as {user?.email}</p>
      <button onClick={signOut}>Sign out</button>
    </div>
  );
}
```

**Return values:**

| Property | Type | Description |
|---|---|---|
| `isAuthenticated` | `boolean` | `true` when a user and session are both present |
| `isLoading` | `boolean` | `true` while the initial auth state is being resolved |
| `user` | `User \| null` | The current user object, or `null` |
| `session` | `Session \| null` | The current session object, or `null` |
| `signOut` | `() => Promise<void>` | Signs out the current user and clears state |
| `auth` | `JanuaClient['auth']` | The raw auth service for advanced operations |

---

### `useUser()`

Returns the current user and a method to refresh the user from the server.

```tsx
'use client';
import { useUser } from '@janua/nextjs';

export function UserProfile() {
  const { user, isLoading, updateUser } = useUser();

  if (isLoading) return <p>Loading...</p>;
  if (!user) return null;

  return (
    <div>
      <p>{user.first_name} {user.last_name}</p>
      <p>{user.email}</p>
      <button onClick={updateUser}>Refresh</button>
    </div>
  );
}
```

**Return values:**

| Property | Type | Description |
|---|---|---|
| `user` | `User \| null` | The current user object |
| `isLoading` | `boolean` | `true` while the initial auth state is being resolved |
| `updateUser` | `() => Promise<void>` | Re-fetches the current user and updates context state |

---

### `useOrganizations()`

Returns the organizations client for the current user. This exposes the full `JanuaClient['organizations']` service, which includes methods such as listing organizations, creating organizations, and managing membership.

```tsx
'use client';
import { useOrganizations } from '@janua/nextjs';
import { useEffect, useState } from 'react';

export function OrgSwitcher() {
  const organizations = useOrganizations();
  const [orgs, setOrgs] = useState([]);

  useEffect(() => {
    organizations.list().then(setOrgs);
  }, [organizations]);

  return (
    <ul>
      {orgs.map((org) => (
        <li key={org.id}>{org.name}</li>
      ))}
    </ul>
  );
}
```

---

### `useJanua()`

Returns the full context value, including the raw `JanuaClient` instance. Use this when you need access to client services not covered by the more specific hooks.

```tsx
'use client';
import { useJanua } from '@janua/nextjs';

export function AdvancedExample() {
  const { client, user, session, isAuthenticated, isLoading, signOut, updateUser } = useJanua();

  const handleUpdateProfile = async () => {
    await client.users.update(user!.id, { first_name: 'Updated' });
    await updateUser();
  };

  return <button onClick={handleUpdateProfile}>Update name</button>;
}
```

**Return values:**

| Property | Type | Description |
|---|---|---|
| `client` | `JanuaClient` | The initialized Janua client instance |
| `user` | `User \| null` | The current user |
| `session` | `Session \| null` | The current session |
| `isAuthenticated` | `boolean` | Authentication state |
| `isLoading` | `boolean` | Loading state |
| `signOut` | `() => Promise<void>` | Signs out and clears state |
| `updateUser` | `() => Promise<void>` | Re-fetches and updates the user in context |

---

### `useRealtime(options?)`

Establishes a WebSocket connection to the Janua real-time service and returns subscription controls. The connection is authenticated automatically using the current access token.

```tsx
'use client';
import { useRealtime } from '@janua/nextjs';
import { useEffect } from 'react';

export function LiveNotifications() {
  const { status, subscribe, on, off } = useRealtime({
    channels: ['notifications'],
    reconnect: true,
  });

  useEffect(() => {
    const handler = (data: unknown) => {
      console.log('New notification:', data);
    };

    on('message', handler);
    return () => off('message', handler);
  }, [on, off]);

  return <p>Connection: {status}</p>;
}
```

**Options (`UseRealtimeOptions`):**

| Option | Type | Default | Description |
|---|---|---|---|
| `channels` | `string[]` | `[]` | Channels to subscribe to immediately after connecting |
| `url` | `string` | Derived from `baseURL` | WebSocket server URL override |
| `reconnect` | `boolean` | `true` | Enable automatic reconnection on disconnect |
| `autoConnect` | `boolean` | `true` | Connect automatically on mount |

**Return values (`UseRealtimeReturn`):**

| Property | Type | Description |
|---|---|---|
| `status` | `WebSocketStatus` | Current connection state: `'connected'`, `'disconnected'`, `'reconnecting'`, or `'error'` |
| `subscribe` | `(channel: string) => void` | Subscribe to a channel |
| `unsubscribe` | `(channel: string) => void` | Unsubscribe from a channel |
| `on` | `(event, handler) => void` | Register an event handler |
| `off` | `(event, handler) => void` | Remove an event handler |
| `send` | `(message: WebSocketMessage) => void` | Send a message to the server |
| `connect` | `() => Promise<void>` | Manually connect |
| `disconnect` | `() => void` | Manually disconnect |

---

## Components

All components are client components. They must be rendered within `JanuaProvider`.

### `<SignIn>` / `<SignInForm>`

Pre-built sign-in form. `SignIn` and `SignInForm` are identical — `SignIn` is the preferred alias.

```tsx
import { SignIn } from '@janua/nextjs';

<SignIn
  redirectTo="/dashboard"
  onSuccess={() => console.log('Signed in')}
  onError={(err) => console.error(err)}
  socialProviders={['google', 'github']}
  enablePasskey={true}
  enableSSO={true}
  signUpUrl="/signup"
  forgotPasswordUrl="/forgot-password"
/>
```

**Props (`SignInFormProps`):**

| Prop | Type | Default | Description |
|---|---|---|---|
| `redirectTo` | `string` | `'/'` | URL to redirect to after a successful sign-in |
| `onSuccess` | `() => void` | — | Callback on successful sign-in |
| `onError` | `(error: Error) => void` | — | Callback on sign-in error |
| `className` | `string` | — | CSS class for the root element |
| `socialProviders` | `string[]` | — | OAuth providers to display (e.g. `['google', 'github']`) |
| `logoUrl` | `string` | — | Custom logo URL |
| `showRememberMe` | `boolean` | — | Show "Remember me" checkbox |
| `signUpUrl` | `string` | — | Link to the sign-up page |
| `forgotPasswordUrl` | `string` | — | Link to the forgot password page |
| `enablePasskey` | `boolean` | — | Show passkey sign-in option |
| `enableSSO` | `boolean` | — | Show SSO sign-in option |
| `enableMagicLink` | `boolean` | — | Show magic link sign-in option |
| `enableJanuaSSO` | `boolean` | — | Enable Janua-native SSO |
| `headerText` | `string` | — | Custom heading text |
| `headerDescription` | `string` | — | Custom subheading text |
| `layout` | `UISignInProps['layout']` | — | Layout variant passed to the underlying UI component |
| `appearance` | `UISignInProps['appearance']` | — | Appearance overrides passed to the underlying UI component |
| `onMFARequired` | `(session: any) => void` | — | Callback when MFA is required to complete sign-in |

---

### `<SignUp>` / `<SignUpForm>`

Pre-built sign-up form. `SignUp` and `SignUpForm` are identical — `SignUp` is the preferred alias.

```tsx
import { SignUp } from '@janua/nextjs';

<SignUp
  redirectTo="/onboarding"
  onSuccess={() => console.log('Account created')}
  socialProviders={['google']}
  requireEmailVerification={true}
  showPasswordStrength={true}
  termsUrl="/terms"
  privacyUrl="/privacy"
  signInUrl="/login"
/>
```

**Props (`SignUpFormProps`):**

| Prop | Type | Default | Description |
|---|---|---|---|
| `redirectTo` | `string` | `'/'` | URL to redirect to after successful registration |
| `onSuccess` | `() => void` | — | Callback on successful sign-up |
| `onError` | `(error: Error) => void` | — | Callback on sign-up error |
| `className` | `string` | — | CSS class for the root element |
| `includeNames` | `boolean` | — | Show first name and last name fields |
| `socialProviders` | `string[]` | — | OAuth providers to display |
| `logoUrl` | `string` | — | Custom logo URL |
| `signInUrl` | `string` | — | Link to the sign-in page |
| `requireEmailVerification` | `boolean` | — | Require email verification before proceeding |
| `showPasswordStrength` | `boolean` | — | Display a password strength indicator |
| `termsUrl` | `string` | — | URL for terms of service |
| `privacyUrl` | `string` | — | URL for privacy policy |
| `layout` | `UISignUpProps['layout']` | — | Layout variant |
| `appearance` | `UISignUpProps['appearance']` | — | Appearance overrides |

---

### `<UserButton>`

A user profile button that displays the signed-in user's avatar and triggers sign-out. Renders nothing when no user is present.

```tsx
import { UserButton } from '@janua/nextjs';

<UserButton
  showName={true}
  showEmail={true}
  afterSignOut={() => router.push('/')}
  showManageAccount={true}
  manageAccountUrl="/account"
  showOrganizations={true}
/>
```

**Props (`UserButtonProps`):**

| Prop | Type | Default | Description |
|---|---|---|---|
| `className` | `string` | — | CSS class for the root element |
| `showName` | `boolean` | — | Show the user's name |
| `showEmail` | `boolean` | — | Show the user's email |
| `afterSignOut` | `() => void` | — | Callback after sign-out completes |
| `showManageAccount` | `boolean` | — | Show a "Manage account" option |
| `manageAccountUrl` | `string` | — | URL for the account management page |
| `showOrganizations` | `boolean` | — | Show organization switcher |
| `activeOrganization` | `string` | — | ID of the currently active organization |

---

### `<SignedIn>`

Renders its children only when a user is authenticated. Renders nothing while loading or when unauthenticated.

```tsx
import { SignedIn } from '@janua/nextjs';

<SignedIn>
  <p>This content is visible only to signed-in users.</p>
</SignedIn>
```

**Props (`SignedInProps`):**

| Prop | Type | Description |
|---|---|---|
| `children` | `React.ReactNode` | Content to render when authenticated |

---

### `<SignedOut>`

Renders its children only when no user is authenticated. Renders nothing while loading or when authenticated.

```tsx
import { SignedOut } from '@janua/nextjs';

<SignedOut>
  <p>Please sign in to continue.</p>
</SignedOut>
```

**Props (`SignedOutProps`):**

| Prop | Type | Description |
|---|---|---|
| `children` | `React.ReactNode` | Content to render when not authenticated |

---

### `<Protect>`

Guards content that requires authentication. Supports a fallback and an optional redirect.

```tsx
import { Protect } from '@janua/nextjs';

<Protect
  fallback={<p>You must be signed in to view this.</p>}
  redirectTo="/login"
>
  <SensitiveContent />
</Protect>
```

While authentication is being resolved, `Protect` renders the `fallback` (or a default loading indicator). If `redirectTo` is provided and the user is not authenticated, `<RedirectToSignIn>` is rendered with that URL.

**Props (`ProtectProps`):**

| Prop | Type | Default | Description |
|---|---|---|---|
| `children` | `React.ReactNode` | — | Content to render when authenticated |
| `fallback` | `React.ReactNode` | `null` | Content to render while loading or when unauthenticated (without redirect) |
| `redirectTo` | `string` | — | Redirect unauthenticated users to this URL |

---

### `<RedirectToSignIn>`

Performs an immediate client-side redirect to a sign-in page. Appends the current path as a `from` query parameter so the sign-in page can redirect back after authentication.

```tsx
import { RedirectToSignIn } from '@janua/nextjs';

<RedirectToSignIn redirectUrl="/login" />
```

**Props (`RedirectToSignInProps`):**

| Prop | Type | Default | Description |
|---|---|---|---|
| `redirectUrl` | `string` | `'/login'` | The sign-in page URL |

---

## Server-Side API

The server-side utilities use `next/headers` (cookies) and are intended for use in Server Components and Route Handlers. They require your session JWT secret.

### `JanuaServerClient`

A server-only client for reading and writing encrypted session cookies. Sessions are stored as HS256-signed JWTs with a 7-day expiry in an `httpOnly`, `SameSite=lax` cookie named `janua-session`.

```ts
// app/lib/auth.ts
import { JanuaServerClient } from '@janua/nextjs';

export const serverClient = new JanuaServerClient({
  appId: 'your-app-id',
  apiKey: process.env.JANUA_API_KEY!,
  jwtSecret: process.env.JANUA_JWT_SECRET!,
});
```

**Constructor options:**

| Option | Type | Description |
|---|---|---|
| `appId` | `string` | Your Janua application ID |
| `apiKey` | `string` | Your Janua API key |
| `jwtSecret` | `string` | Secret used to sign and verify session cookies |

**Methods:**

| Method | Signature | Description |
|---|---|---|
| `getSession()` | `() => Promise<{ user: User; session: Session } \| null>` | Returns the current session from the cookie, or `null` |
| `requireAuth()` | `() => Promise<{ user: User; session: Session }>` | Returns the session or throws if unauthenticated |
| `signIn()` | `(email, password) => Promise<{ user, session }>` | Authenticates credentials and writes a session cookie |
| `signUp()` | `(data) => Promise<{ user, session }>` | Registers a new user and writes a session cookie |
| `handleOAuthCallback()` | `(code, codeVerifier?) => Promise<{ user, session }>` | Completes an OAuth PKCE flow and writes a session cookie |
| `signOut()` | `() => Promise<void>` | Deletes the session cookie |
| `updateUser()` | `(data) => Promise<User>` | Updates the user and refreshes the session cookie |
| `getClient()` | `() => JanuaClient` | Returns the underlying `JanuaClient` instance |

---

### `getSession(appId, apiKey, jwtSecret)`

A convenience function equivalent to `new JanuaServerClient(...).getSession()`.

```ts
// app/dashboard/page.tsx
import { getSession } from '@janua/nextjs';

export default async function DashboardPage() {
  const session = await getSession(
    'your-app-id',
    process.env.JANUA_API_KEY!,
    process.env.JANUA_JWT_SECRET!,
  );

  if (!session) {
    return <p>Not signed in.</p>;
  }

  return <p>Welcome, {session.user.email}</p>;
}
```

**Signature:** `getSession(appId: string, apiKey: string, jwtSecret: string): Promise<{ user: User; session: Session } | null>`

---

### `requireAuth(appId, apiKey, jwtSecret)`

A convenience function equivalent to `new JanuaServerClient(...).requireAuth()`. Throws an error if the session cookie is absent or invalid.

```ts
// app/account/page.tsx
import { requireAuth } from '@janua/nextjs';

export default async function AccountPage() {
  const { user } = await requireAuth(
    'your-app-id',
    process.env.JANUA_API_KEY!,
    process.env.JANUA_JWT_SECRET!,
  );

  return <p>Signed in as {user.email}</p>;
}
```

**Signature:** `requireAuth(appId: string, apiKey: string, jwtSecret: string): Promise<{ user: User; session: Session }>`

---

### `validateRequest(request, jwtSecret)`

Validates a session cookie present on a `NextRequest`. Intended for use in Route Handlers.

```ts
// app/api/protected/route.ts
import { validateRequest } from '@janua/nextjs';
import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const session = await validateRequest(request, process.env.JANUA_JWT_SECRET!);

  if (!session) {
    return new Response('Unauthorized', { status: 401 });
  }

  return Response.json({ userId: session.user.id });
}
```

**Signature:** `validateRequest(request: NextRequest, jwtSecret: string): Promise<SessionData | null>`

Returns the full `SessionData` object (containing `user`, `session`, `accessToken`, and `refreshToken`) or `null` if the cookie is absent or the JWT is invalid.

---

## Middleware

### `createJanuaMiddleware(config)`

Returns a Next.js middleware function that enforces authentication on routes. Unauthenticated requests to protected routes are redirected with the original path preserved as a `from` query parameter.

Route matching supports exact paths and wildcard suffixes (e.g. `'/dashboard/*'`).

If `protectedRoutes` is omitted or empty, all routes that are not in `publicRoutes` are treated as protected.

```ts
// middleware.ts
import { createJanuaMiddleware, config as januaConfig } from '@janua/nextjs/middleware';

export default createJanuaMiddleware({
  jwtSecret: process.env.JANUA_JWT_SECRET!,
  publicRoutes: ['/', '/login', '/signup', '/forgot-password'],
  protectedRoutes: ['/dashboard/*', '/account/*', '/settings/*'],
  redirectUrl: '/login',
  cookieName: 'janua-session',
});

export const config = januaConfig;
```

**Config options (`JanuaMiddlewareConfig`):**

| Option | Type | Default | Description |
|---|---|---|---|
| `jwtSecret` | `string` | — | Required. Secret used to verify session cookies |
| `publicRoutes` | `string[]` | `['/login', '/signup', '/forgot-password']` | Routes that do not require authentication |
| `protectedRoutes` | `string[]` | `[]` | Routes that require authentication. If empty, all non-public routes are protected |
| `redirectUrl` | `string` | `'/login'` | URL to redirect unauthenticated users to |
| `cookieName` | `string` | `'janua-session'` | Name of the session cookie to verify |

The exported `config` object from `@janua/nextjs/middleware` provides a standard Next.js matcher that excludes static files, image optimization routes, and `favicon.ico`.

---

### `withAuth(config)`

A convenience wrapper around `createJanuaMiddleware` that reads `JANUA_JWT_SECRET` from the environment automatically. The `jwtSecret` option is optional — if omitted, the environment variable must be set.

```ts
// middleware.ts
import { withAuth } from '@janua/nextjs/middleware';

export default withAuth({
  publicRoutes: ['/', '/login', '/signup'],
  redirectUrl: '/login',
});

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|public).*)'],
};
```

Throws at runtime if neither `config.jwtSecret` nor `JANUA_JWT_SECRET` is available.

---

## Edge Middleware

`@janua/nextjs/edge` provides a lightweight alternative to `createJanuaMiddleware` for deployments where the full middleware is too heavy or where stateless JWT verification is preferred. It uses `jose` and fetches public keys from a JWKS endpoint, making it compatible with the Edge Runtime.

Unlike `createJanuaMiddleware`, the edge middleware does not read a symmetric session cookie. It verifies access tokens (JWTs) signed with the keys published at your JWKS endpoint.

### `createEdgeMiddleware(config)`

```ts
// middleware.ts
import { createEdgeMiddleware } from '@janua/nextjs/edge';
import { NextRequest, NextResponse } from 'next/server';

const verify = createEdgeMiddleware({
  jwksUrl: 'https://api.janua.dev/.well-known/jwks.json',
  issuer: 'https://api.janua.dev',
  audience: 'your-app-id',
});

export async function middleware(request: NextRequest) {
  const result = await verify(request);

  if (!result.authenticated) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // result.token.userId  — the 'sub' claim
  // result.token.payload — the full decoded JWT payload
  // result.token.expiresAt — token expiry as a Date

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
```

**Config options (`EdgeMiddlewareConfig`):**

| Option | Type | Default | Description |
|---|---|---|---|
| `jwksUrl` | `string` | — | Required. JWKS endpoint URL for fetching public signing keys |
| `issuer` | `string` | — | Expected JWT issuer (`iss` claim). Omit to skip issuer validation |
| `audience` | `string` | — | Expected JWT audience (`aud` claim). Omit to skip audience validation |
| `cookieName` | `string` | `'janua_session'` | Cookie name to inspect if no `Authorization` header is present |
| `headerName` | `string` | `'authorization'` | HTTP header to inspect for a Bearer token |
| `clockTolerance` | `number` | `5` | Clock skew tolerance in seconds |

**Return value:**

The returned `verifyRequest` function accepts a `Request` (or `NextRequest`) and returns one of:

- `{ authenticated: true; token: VerifiedToken }` — the request carries a valid token
- `{ authenticated: false; error: string }` — no token found or verification failed

**`VerifiedToken` shape:**

| Field | Type | Description |
|---|---|---|
| `payload` | `jose.JWTPayload` | The full decoded JWT payload |
| `userId` | `string \| undefined` | Value of the `sub` claim |
| `expiresAt` | `Date \| undefined` | Token expiry time |

Token lookup order: `Authorization: Bearer <token>` header first, then the configured cookie.

---

## TypeScript Support

The package ships with full TypeScript definitions. Types are exported from both the root entry point and the `/app` sub-path.

```ts
import type {
  JanuaProviderProps,
  SignInFormProps,
  SignUpFormProps,
  UserButtonProps,
  SignedInProps,
  SignedOutProps,
  RedirectToSignInProps,
  ProtectProps,
  UseRealtimeOptions,
  UseRealtimeReturn,
} from '@janua/nextjs';

import type {
  JanuaMiddlewareConfig,
} from '@janua/nextjs/middleware';

import type {
  EdgeMiddlewareConfig,
  VerifiedToken,
} from '@janua/nextjs/edge';
```

Domain types such as `User`, `Session`, and `Organization` are re-exported from `@janua/typescript-sdk`:

```ts
import type { User, Session, Organization } from '@janua/nextjs';
```

---

## Related

- [React SDK](../react-sdk/README.md) — React hooks and components without Next.js-specific features
- [TypeScript SDK](../typescript-sdk/README.md) — Framework-agnostic API client
- [API Reference](https://docs.janua.dev/api) — Complete REST API documentation
- [Error Handling Guide](../../docs/guides/ERROR_HANDLING_GUIDE.md)
- [Rate Limiting](../../docs/api/RATE_LIMITING.md)

---

## License

AGPL-3.0 — see [LICENSE](./LICENSE) for details.
