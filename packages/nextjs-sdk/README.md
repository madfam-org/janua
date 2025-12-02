# @janua/nextjs

Official Janua SDK for Next.js applications with App Router and Pages Router support.

## Installation

```bash
npm install @janua/nextjs
# or
yarn add @janua/nextjs
# or
pnpm add @janua/nextjs
```

## Features

- 🚀 **App Router Support** - Full support for Next.js 13+ App Router
- 📁 **Pages Router Support** - Compatible with traditional Pages Router
- 🔐 **Authentication Components** - Pre-built sign-in/sign-up forms
- ⚡ **Server Components** - Optimized for React Server Components
- 🛡️ **Middleware Protection** - Route-level authentication middleware
- 🔑 **Session Management** - Automatic token refresh and session handling
- 📱 **Multi-Factor Auth** - TOTP, SMS, and Passkey support
- 🏢 **Organizations** - Built-in multi-tenant organization support

## Quick Start

### 1. Environment Configuration

Add your Janua credentials to `.env.local`:

```env
JANUA_PUBLISHABLE_KEY=pk_live_...
JANUA_SECRET_KEY=sk_live_...
JANUA_API_URL=https://api.janua.dev
```

### 2. App Router Setup

Wrap your app with the `JanuaProvider`:

```tsx
// app/layout.tsx
import { JanuaProvider } from '@janua/nextjs';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <JanuaProvider>
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
import { SignedIn, SignedOut, SignInForm, UserButton } from '@janua/nextjs';

export default function HomePage() {
  return (
    <div>
      <SignedIn>
        <h1>Welcome back!</h1>
        <UserButton />
      </SignedIn>

      <SignedOut>
        <h1>Please sign in</h1>
        <SignInForm />
      </SignedOut>
    </div>
  );
}
```

### 4. Protect Routes with Middleware

```tsx
// middleware.ts
import { createJanuaMiddleware } from '@janua/nextjs';

export default createJanuaMiddleware({
  publicRoutes: ["/", "/sign-in", "/sign-up"],
  protectedRoutes: ["/dashboard", "/profile"]
});

export const config = {
  matcher: ['/((?!.*\\..*|_next).*)', '/', '/(api|trpc)(.*)'],
};
```

## App Router Usage

### Server Components

```tsx
// app/dashboard/page.tsx
import { getSession, requireAuth } from '@janua/nextjs';

export default async function DashboardPage() {
  // Require authentication (redirects if not signed in)
  const session = await requireAuth();

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Welcome, {session.user.email}!</p>
    </div>
  );
}
```

### Client Components

```tsx
'use client';
import { useAuth, useUser } from '@janua/nextjs';

export default function ProfileComponent() {
  const { isSignedIn, isLoading } = useAuth();
  const { user } = useUser();

  if (isLoading) return <div>Loading...</div>;

  if (!isSignedIn) return <div>Please sign in</div>;

  return (
    <div>
      <h2>Profile</h2>
      <p>Email: {user.email}</p>
    </div>
  );
}
```

### Organizations

```tsx
'use client';
import { useOrganizations } from '@janua/nextjs';

export default function OrganizationsComponent() {
  const { organizations, activeOrganization, setActiveOrganization } = useOrganizations();

  return (
    <div>
      <h2>Organizations</h2>
      {organizations.map(org => (
        <button
          key={org.id}
          onClick={() => setActiveOrganization(org.id)}
          className={activeOrganization?.id === org.id ? 'active' : ''}
        >
          {org.name}
        </button>
      ))}
    </div>
  );
}
```

## API Reference

### Components

#### `<JanuaProvider>`
Root provider component that wraps your app.

```tsx
<JanuaProvider>
  {children}
</JanuaProvider>
```

#### `<SignInForm>`
Pre-built sign-in form component.

```tsx
<SignInForm
  redirectUrl="/dashboard"
  onSuccess={(user) => console.log('Signed in:', user)}
  onError={(error) => console.error('Sign-in error:', error)}
/>
```

#### `<SignUpForm>`
Pre-built sign-up form component.

```tsx
<SignUpForm
  redirectUrl="/onboarding"
  onSuccess={(user) => console.log('Signed up:', user)}
  onError={(error) => console.error('Sign-up error:', error)}
/>
```

#### `<UserButton>`
User profile button with dropdown menu.

```tsx
<UserButton
  showName={true}
  showEmail={true}
  afterSignOutUrl="/"
/>
```

#### `<SignedIn>` / `<SignedOut>`
Conditional rendering based on authentication state.

```tsx
<SignedIn>
  <div>User is signed in</div>
</SignedIn>

<SignedOut>
  <div>User is signed out</div>
</SignedOut>
```

#### `<Protect>`
Protect components that require authentication.

```tsx
<Protect role="admin" organization="org_123">
  <AdminPanel />
</Protect>
```

### Hooks

#### `useAuth()`
Get authentication state and methods.

```tsx
const {
  isSignedIn,
  isLoading,
  signOut
} = useAuth();
```

#### `useUser()`
Get current user data.

```tsx
const {
  user,
  isLoading
} = useUser();
```

#### `useJanua()`
Access the Janua client instance.

```tsx
const janua = useJanua();
await janua.users.updateProfile({ name: 'New Name' });
```

### Server Functions

#### `getSession()`
Get session in Server Components.

```tsx
const session = await getSession();
if (session) {
  console.log('User ID:', session.userId);
}
```

#### `requireAuth()`
Require authentication (redirects if not signed in).

```tsx
const session = await requireAuth();
// User is guaranteed to be authenticated here
```

#### `validateRequest()`
Validate request in API routes.

```tsx
// app/api/protected/route.ts
import { validateRequest } from '@janua/nextjs';

export async function GET() {
  const session = await validateRequest();
  if (!session) {
    return new Response('Unauthorized', { status: 401 });
  }

  return Response.json({ userId: session.userId });
}
```

### Middleware

#### `createJanuaMiddleware()`
Create authentication middleware.

```tsx
import { createJanuaMiddleware } from '@janua/nextjs';

export default createJanuaMiddleware({
  publicRoutes: ["/", "/about"],
  protectedRoutes: ["/dashboard/*"],
  signInUrl: "/sign-in",
  signUpUrl: "/sign-up",
  afterSignInUrl: "/dashboard",
  afterSignUpUrl: "/onboarding"
});
```

## TypeScript Support

This package includes full TypeScript definitions. All components and hooks are fully typed.

```tsx
import type { User, Organization, Session } from '@janua/nextjs';

const user: User = await janua.users.getCurrent();
const org: Organization = await janua.organizations.get('org_123');
```

## Requirements

- Next.js 12.0.0 or higher
- React 17.0.0 or higher
- Node.js 14.0.0 or higher

## License

AGPL-3.0 License - see [LICENSE](./LICENSE) file for details.

## Support

- 📖 [Documentation](https://docs.janua.dev)
- 💬 [Discord Community](https://discord.gg/janua)
- 🐛 [Report Issues](https://github.com/madfam-io/janua/issues)
- 📧 [Email Support](mailto:support@janua.dev)