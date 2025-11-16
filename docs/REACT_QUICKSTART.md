# React Quickstart Guide

**Time to Integration**: < 5 minutes ⚡
**Difficulty**: Beginner-friendly

Get authentication running in your React or Next.js app in under 5 minutes with Plinto's pre-built components and TypeScript SDK.

---

## Prerequisites

- Node.js 16+ and npm/yarn installed
- Existing React or Next.js project (or create one)
- 5 minutes of your time ⏱️

---

## Installation (1 minute)

```bash
npm install @plinto/ui @plinto/typescript-sdk
```

**What you get**:
- `@plinto/ui`: Pre-built React components (SignIn, SignUp, UserButton, etc.)
- `@plinto/typescript-sdk`: Type-safe API client for backend communication

---

## Setup (2 minutes)

### Step 1: Configure the Plinto Client

Create `lib/plinto-client.ts`:

```typescript
import { PlintoClient } from '@plinto/typescript-sdk'

export const plintoClient = new PlintoClient({
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
})

export default plintoClient
```

### Step 2: Wrap Your App with PlintoProvider

**For Next.js (App Router)**:

Create `app/providers.tsx`:

```typescript
'use client'

import { PlintoProvider } from '@plinto/ui'
import { plintoClient } from '@/lib/plinto-client'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <PlintoProvider client={plintoClient}>
      {children}
    </PlintoProvider>
  )
}
```

Update `app/layout.tsx`:

```typescript
import { Providers } from './providers'

export default function RootLayout({ children }: { children: React.ReactNode }) {
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

**For Next.js (Pages Router)** or **Create React App**:

Update `pages/_app.tsx` or `App.tsx`:

```typescript
import { PlintoProvider } from '@plinto/ui'
import { plintoClient } from '@/lib/plinto-client'

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <PlintoProvider client={plintoClient}>
      <Component {...pageProps} />
    </PlintoProvider>
  )
}

export default MyApp
```

---

## Add Authentication (1 minute)

### Sign-In Page

Create `app/auth/sign-in/page.tsx` (or `pages/sign-in.tsx`):

```typescript
'use client' // Only for Next.js App Router

import { SignIn } from '@plinto/ui'

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn redirectUrl="/dashboard" />
    </div>
  )
}
```

### Sign-Up Page

Create `app/auth/sign-up/page.tsx`:

```typescript
'use client'

import { SignUp } from '@plinto/ui'

export default function SignUpPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignUp redirectUrl="/dashboard" />
    </div>
  )
}
```

### User Button (Profile Menu)

Add to your navigation/header:

```typescript
import { UserButton } from '@plinto/ui'

export function Header() {
  return (
    <header>
      <nav>
        {/* Your navigation */}
        <UserButton />
      </nav>
    </header>
  )
}
```

---

## Protect Routes (1 minute)

### Using the `useAuth` Hook

```typescript
'use client'

import { useAuth } from '@plinto/ui'
import { SignIn } from '@plinto/ui'

export default function DashboardPage() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div>Loading...</div>
  }

  if (!user) {
    return <SignIn redirectUrl="/dashboard" />
  }

  return (
    <div>
      <h1>Welcome, {user.first_name || user.email}!</h1>
      <p>You are now authenticated.</p>
    </div>
  )
}
```

### Server-Side Protection (Next.js App Router)

Create `app/dashboard/page.tsx`:

```typescript
import { redirect } from 'next/navigation'
import { cookies } from 'next/headers'

async function getUser() {
  const token = cookies().get('access_token')?.value

  if (!token) {
    return null
  }

  const response = await fetch('http://localhost:8000/api/v1/auth/me', {
    headers: { 'Authorization': `Bearer ${token}` }
  })

  if (!response.ok) {
    return null
  }

  return await response.json()
}

export default async function DashboardPage() {
  const user = await getUser()

  if (!user) {
    redirect('/auth/sign-in')
  }

  return (
    <div>
      <h1>Welcome, {user.first_name || user.email}!</h1>
    </div>
  )
}
```

---

## Environment Variables

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**For production**:

```bash
NEXT_PUBLIC_API_URL=https://api.plinto.dev
```

---

## Complete Example

Here's a complete minimal example:

```typescript
// lib/plinto-client.ts
import { PlintoClient } from '@plinto/typescript-sdk'

export const plintoClient = new PlintoClient({
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
})

// app/providers.tsx
'use client'

import { PlintoProvider } from '@plinto/ui'
import { plintoClient } from '@/lib/plinto-client'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <PlintoProvider client={plintoClient}>
      {children}
    </PlintoProvider>
  )
}

// app/layout.tsx
import { Providers } from './providers'
import './globals.css'

export default function RootLayout({ children }: { children: React.ReactNode }) {
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

// app/page.tsx
import Link from 'next/link'

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center">
      <h1 className="text-4xl font-bold mb-8">Welcome to My App</h1>
      <div className="flex gap-4">
        <Link href="/auth/sign-in" className="px-6 py-3 bg-blue-600 text-white rounded">
          Sign In
        </Link>
        <Link href="/auth/sign-up" className="px-6 py-3 bg-green-600 text-white rounded">
          Sign Up
        </Link>
      </div>
    </main>
  )
}

// app/auth/sign-in/page.tsx
'use client'

import { SignIn } from '@plinto/ui'

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn redirectUrl="/dashboard" />
    </div>
  )
}

// app/auth/sign-up/page.tsx
'use client'

import { SignUp } from '@plinto/ui'

export default function SignUpPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignUp redirectUrl="/dashboard" />
    </div>
  )
}

// app/dashboard/page.tsx
'use client'

import { useAuth } from '@plinto/ui'
import { UserButton, SignIn } from '@plinto/ui'

export default function DashboardPage() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  if (!user) {
    return <SignIn redirectUrl="/dashboard" />
  }

  return (
    <div className="min-h-screen p-8">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <UserButton />
      </header>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Welcome back!</h2>
        <div className="space-y-2">
          <p><strong>Email:</strong> {user.email}</p>
          <p><strong>Name:</strong> {user.first_name} {user.last_name}</p>
          <p><strong>Account created:</strong> {new Date(user.created_at).toLocaleDateString()}</p>
        </div>
      </div>
    </div>
  )
}
```

---

## Advanced Features

### Organization Switcher

For multi-tenant applications:

```typescript
import { OrganizationSwitcher } from '@plinto/ui'

export function Header() {
  return (
    <header>
      <OrganizationSwitcher
        plintoClient={plintoClient}
        showCreateOrganization={true}
      />
    </header>
  )
}
```

### Session Management

View and manage active sessions:

```typescript
import { SessionManagement } from '@plinto/ui'

export function SecuritySettings() {
  return (
    <div>
      <h2>Active Sessions</h2>
      <SessionManagement plintoClient={plintoClient} />
    </div>
  )
}
```

### Email Verification

```typescript
import { EmailVerification } from '@plinto/ui'

export function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <EmailVerification plintoClient={plintoClient} />
    </div>
  )
}
```

### Password Reset

```typescript
import { PasswordReset } from '@plinto/ui'

export function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <PasswordReset plintoClient={plintoClient} />
    </div>
  )
}
```

### MFA Setup

```typescript
import { MFASetup } from '@plinto/ui'

export function SecurityPage() {
  return (
    <div>
      <h2>Two-Factor Authentication</h2>
      <MFASetup plintoClient={plintoClient} />
    </div>
  )
}
```

---

## Using the SDK Directly

For custom implementations or advanced use cases:

```typescript
import { plintoClient } from '@/lib/plinto-client'

// Sign up
const { user, tokens } = await plintoClient.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePass123!',
  first_name: 'John',
  last_name: 'Doe'
})

// Sign in
const { user, tokens } = await plintoClient.auth.signIn({
  email: 'user@example.com',
  password: 'SecurePass123!'
})

// Get current user
const user = await plintoClient.auth.getCurrentUser()

// Update profile
const updatedUser = await plintoClient.users.updateProfile({
  first_name: 'Jane',
  profile_image_url: 'https://example.com/avatar.jpg'
})

// List sessions
const sessions = await plintoClient.sessions.listSessions()

// Revoke session
await plintoClient.sessions.revokeSession(sessionId)

// Create organization
const org = await plintoClient.organizations.createOrganization({
  name: 'Acme Corp',
  slug: 'acme-corp'
})

// List organization members
const members = await plintoClient.organizations.listMembers(orgId)
```

---

## Styling

All components are built with Tailwind CSS and support custom styling:

```typescript
<SignIn
  className="my-custom-class"
  redirectUrl="/dashboard"
  logoUrl="/logo.png"
/>
```

**Dark Mode Support**:

```typescript
<PlintoProvider client={plintoClient} theme="dark">
  {children}
</PlintoProvider>
```

---

## TypeScript Support

Full type safety out of the box:

```typescript
import type { User, Organization, Session } from '@plinto/typescript-sdk'

const handleUser = (user: User) => {
  console.log(user.email) // ✅ Type-safe
  console.log(user.invalidField) // ❌ TypeScript error
}
```

---

## Error Handling

```typescript
'use client'

import { SignIn } from '@plinto/ui'
import { useState } from 'react'

export default function SignInPage() {
  const [error, setError] = useState<string | null>(null)

  return (
    <div>
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <SignIn
        redirectUrl="/dashboard"
        onError={(err) => setError(err.message)}
      />
    </div>
  )
}
```

---

## Next Steps

1. **Customize Components**: Add your branding, colors, and styles
2. **Enable OAuth**: Add Google, GitHub, Microsoft, Apple sign-in
3. **Set Up MFA**: Enable two-factor authentication for users
4. **Add Organizations**: Implement multi-tenancy for SaaS apps
5. **Deploy**: Follow our [Production Deployment Guide](./DEPLOYMENT.md)

---

## Troubleshooting

### "Module not found: @plinto/ui"

Make sure you installed the packages:

```bash
npm install @plinto/ui @plinto/typescript-sdk
```

### "PlintoProvider is not a client component"

Add `'use client'` at the top of your `providers.tsx` file (Next.js App Router only):

```typescript
'use client'

import { PlintoProvider } from '@plinto/ui'
```

### CORS errors

Make sure your API URL is correct in `.env.local` and the API server allows your domain:

```bash
# Development
NEXT_PUBLIC_API_URL=http://localhost:8000

# Production
NEXT_PUBLIC_API_URL=https://api.plinto.dev
```

### Styles not loading

Import Tailwind CSS in your global styles:

```css
/* globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

---

## Support

- **Documentation**: [https://docs.plinto.dev](https://docs.plinto.dev)
- **API Reference**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **GitHub**: [https://github.com/plinto/plinto](https://github.com/plinto/plinto)
- **Discord**: [https://discord.gg/plinto](https://discord.gg/plinto)
- **Email**: support@plinto.dev

---

**Congratulations! 🎉** You now have authentication running in your React app. Time to build something amazing!
