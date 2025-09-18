# Magic Link Authentication

Implement passwordless authentication with secure email-based magic links.

## Overview

Magic links provide a passwordless authentication experience by sending a secure, time-limited link to the user's email. When clicked, the user is automatically authenticated without needing to remember or type a password.

## Benefits

- **No Password Fatigue**: Users don't need to remember complex passwords
- **Enhanced Security**: No passwords to steal or breach
- **Better UX**: Simplified login flow with fewer steps
- **Reduced Support**: No password reset requests

## Quick Start

### 1. Send Magic Link

```typescript
import { plinto } from '@plinto/typescript-sdk'

// Request magic link
const { success, message } = await plinto.auth.sendMagicLink({
  email: 'user@example.com',
  redirectUrl: 'https://app.example.com/dashboard',
  expiresIn: 15 * 60, // 15 minutes
})

if (success) {
  console.log('Magic link sent to', email)
}
```

### 2. Verify Magic Link

```typescript
// In your callback route
const { user, session } = await plinto.auth.verifyMagicLink({
  token: request.query.token,
})

if (session) {
  // User is authenticated
  setCookie('session', session.token)
  redirect('/dashboard')
}
```

## Implementation Guide

### Backend Setup

#### Express.js

```javascript
const express = require('express')
const { Plinto } = require('@plinto/node')

const app = express()
const plinto = new Plinto({
  apiKey: process.env.PLINTO_API_KEY,
})

// Send magic link endpoint
app.post('/auth/magic-link', async (req, res) => {
  const { email } = req.body

  try {
    const result = await plinto.auth.sendMagicLink({
      email,
      redirectUrl: `${process.env.APP_URL}/auth/callback`,
      metadata: {
        ip: req.ip,
        userAgent: req.headers['user-agent'],
      }
    })

    res.json({
      success: true,
      message: 'Check your email for the magic link'
    })
  } catch (error) {
    res.status(400).json({
      success: false,
      error: error.message
    })
  }
})

// Verify magic link callback
app.get('/auth/callback', async (req, res) => {
  const { token } = req.query

  try {
    const { user, session } = await plinto.auth.verifyMagicLink({
      token,
    })

    // Set session cookie
    res.cookie('session', session.token, {
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
    })

    res.redirect('/dashboard')
  } catch (error) {
    res.redirect('/login?error=invalid_token')
  }
})
```

#### Python FastAPI

```python
from fastapi import FastAPI, HTTPException
from plinto import Plinto
import os

app = FastAPI()
plinto = Plinto(api_key=os.getenv("PLINTO_API_KEY"))

@app.post("/auth/magic-link")
async def send_magic_link(email: str):
    try:
        result = await plinto.auth.send_magic_link(
            email=email,
            redirect_url=f"{os.getenv('APP_URL')}/auth/callback",
            expires_in=900  # 15 minutes
        )
        return {"success": True, "message": "Check your email"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/callback")
async def verify_magic_link(token: str):
    try:
        result = await plinto.auth.verify_magic_link(token=token)
        # Create session and redirect
        return {"user": result.user, "session": result.session}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Frontend Implementation

#### React

```jsx
import { useState } from 'react'
import { usePlinto } from '@plinto/react-sdk'

function MagicLinkLogin() {
  const { sendMagicLink } = usePlinto()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      await sendMagicLink({ email })
      setSent(true)
    } catch (error) {
      console.error('Failed to send magic link:', error)
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="success-message">
        <h2>Check Your Email</h2>
        <p>We've sent a magic link to {email}</p>
        <p>Click the link to sign in instantly.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit}>
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
  )
}
```

#### Next.js App Router

```typescript
// app/auth/magic-link/page.tsx
'use client'

import { useState } from 'react'
import { sendMagicLink } from '@/lib/auth'

export default function MagicLinkPage() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'sent'>('idle')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('loading')

    const result = await sendMagicLink(email)

    if (result.success) {
      setStatus('sent')
    }
  }

  // ... rest of component
}

// app/auth/callback/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { verifyMagicLink } from '@/lib/auth'
import { cookies } from 'next/headers'

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token')

  if (!token) {
    return NextResponse.redirect('/login?error=missing_token')
  }

  try {
    const { session } = await verifyMagicLink(token)

    cookies().set('session', session.token, {
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      maxAge: 30 * 24 * 60 * 60,
    })

    return NextResponse.redirect('/dashboard')
  } catch {
    return NextResponse.redirect('/login?error=invalid_token')
  }
}
```

## Configuration Options

### Token Settings

```typescript
{
  // Token expiration time in seconds
  expiresIn: 900, // 15 minutes (default)

  // Maximum uses for the token
  maxUses: 1, // Single use (default)

  // Custom token length
  tokenLength: 32, // 32 characters (default)

  // Token type
  tokenType: 'alphanumeric', // or 'numeric' for OTP-style
}
```

### Email Customization

```typescript
{
  // Email template ID (if using custom templates)
  templateId: 'magic-link-custom',

  // Template variables
  templateData: {
    appName: 'Your App',
    userName: user.name,
    actionUrl: magicLink,
    expiryTime: '15 minutes',
  },

  // Email sender
  from: {
    name: 'Your App',
    email: 'noreply@yourapp.com',
  },

  // Email subject
  subject: 'Your sign-in link for Your App',
}
```

### Security Options

```typescript
{
  // Rate limiting
  rateLimit: {
    maxAttempts: 5,
    windowMs: 15 * 60 * 1000, // 15 minutes
  },

  // IP validation
  validateIp: true, // Ensure same IP for request and verification

  // Device fingerprinting
  validateDevice: true, // Ensure same device

  // Require user to exist
  requireExistingUser: false, // Auto-create if not exists
}
```

## Advanced Features

### Custom Redirect Logic

```typescript
const { session } = await plinto.auth.verifyMagicLink({
  token,
  onSuccess: async (user) => {
    // Custom logic before redirect
    if (user.isNewUser) {
      return '/onboarding'
    }
    if (user.role === 'admin') {
      return '/admin'
    }
    return '/dashboard'
  },
})
```

### Multi-Factor Authentication

```typescript
// Require additional factor after magic link
const { requiresMfa, mfaToken } = await plinto.auth.verifyMagicLink({
  token,
  checkMfa: true,
})

if (requiresMfa) {
  // Redirect to MFA verification
  return redirect(`/mfa/verify?token=${mfaToken}`)
}
```

### Organization Context

```typescript
// Send magic link with organization context
await plinto.auth.sendMagicLink({
  email,
  organizationId: 'org_123',
  redirectUrl: 'https://org.example.com/dashboard',
})
```

## Security Best Practices

### 1. Token Security

- Use secure random token generation
- Set appropriate expiration times (10-30 minutes)
- Implement single-use tokens
- Store tokens hashed in database

### 2. Rate Limiting

```typescript
// Implement rate limiting
const rateLimiter = new RateLimiter({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // 5 requests per window
})

app.post('/auth/magic-link', rateLimiter, async (req, res) => {
  // ... handle request
})
```

### 3. Email Verification

```typescript
// Verify email ownership
if (!user.emailVerified) {
  await plinto.auth.sendEmailVerification(email)
  return {
    requiresVerification: true,
    message: 'Please verify your email first'
  }
}
```

### 4. Monitoring

```typescript
// Log authentication events
plinto.events.on('auth.magicLink.sent', (event) => {
  console.log('Magic link sent:', event)
})

plinto.events.on('auth.magicLink.used', (event) => {
  console.log('Magic link used:', event)
})

plinto.events.on('auth.magicLink.expired', (event) => {
  console.log('Magic link expired:', event)
})
```

## Error Handling

### Common Errors

| Error Code | Description | Solution |
|------------|-------------|----------|
| `invalid_email` | Email format invalid | Validate email format |
| `user_not_found` | User doesn't exist | Check `requireExistingUser` setting |
| `token_expired` | Magic link expired | Request new magic link |
| `token_used` | Token already used | Request new magic link |
| `rate_limited` | Too many requests | Wait before retrying |

### Error Handling Example

```typescript
try {
  const result = await plinto.auth.verifyMagicLink({ token })
  // Success handling
} catch (error) {
  switch (error.code) {
    case 'token_expired':
      showError('This link has expired. Please request a new one.')
      break
    case 'token_used':
      showError('This link has already been used.')
      break
    case 'invalid_token':
      showError('This link is invalid.')
      break
    default:
      showError('Something went wrong. Please try again.')
  }
}
```

## Testing

### Unit Tests

```typescript
describe('Magic Link Authentication', () => {
  it('should send magic link email', async () => {
    const result = await plinto.auth.sendMagicLink({
      email: 'test@example.com',
    })

    expect(result.success).toBe(true)
    expect(mockEmailService).toHaveBeenCalledWith(
      expect.objectContaining({
        to: 'test@example.com',
        subject: expect.stringContaining('sign-in link'),
      })
    )
  })

  it('should verify valid token', async () => {
    const token = 'valid_token_123'
    const result = await plinto.auth.verifyMagicLink({ token })

    expect(result.session).toBeDefined()
    expect(result.user.email).toBe('test@example.com')
  })

  it('should reject expired token', async () => {
    const token = 'expired_token_123'

    await expect(
      plinto.auth.verifyMagicLink({ token })
    ).rejects.toThrow('token_expired')
  })
})
```

### E2E Tests

```typescript
test('complete magic link flow', async ({ page }) => {
  // Request magic link
  await page.goto('/login')
  await page.fill('input[type="email"]', 'test@example.com')
  await page.click('button:has-text("Send Magic Link")')

  // Check success message
  await expect(page.locator('text=Check Your Email')).toBeVisible()

  // Simulate clicking magic link
  const magicLink = await getMagicLinkFromEmail('test@example.com')
  await page.goto(magicLink)

  // Verify redirect to dashboard
  await expect(page).toHaveURL('/dashboard')
  await expect(page.locator('text=Welcome')).toBeVisible()
})
```

## Migration Guide

### From Password Authentication

```typescript
// Before: Password-based
const user = await plinto.auth.signIn({
  email,
  password,
})

// After: Magic link
const result = await plinto.auth.sendMagicLink({
  email,
})
// User clicks link in email to authenticate
```

### From Other Providers

```typescript
// Auth0
auth0.passwordlessStart({
  connection: 'email',
  send: 'link',
  email,
})

// Plinto equivalent
plinto.auth.sendMagicLink({
  email,
})
```

## Troubleshooting

### Magic Link Not Received

1. Check spam/junk folder
2. Verify email address is correct
3. Check email service status
4. Verify SMTP configuration
5. Check rate limiting

### Invalid Token Error

1. Token may be expired (default 15 minutes)
2. Token already used (single-use)
3. Token tampered with
4. Different IP/device (if validation enabled)

### Redirect Issues

1. Verify redirect URL is whitelisted
2. Check CORS configuration
3. Ensure cookies are enabled
4. Verify session storage

## API Reference

### `sendMagicLink(options)`

Send a magic link to user's email.

**Parameters:**
- `email` (string, required): User's email address
- `redirectUrl` (string): URL to redirect after verification
- `expiresIn` (number): Token expiry in seconds
- `metadata` (object): Additional metadata to store

**Returns:**
- `success` (boolean): Whether email was sent
- `message` (string): Status message

### `verifyMagicLink(options)`

Verify a magic link token.

**Parameters:**
- `token` (string, required): Magic link token
- `createSession` (boolean): Auto-create session

**Returns:**
- `user` (object): User profile
- `session` (object): Session details
- `isNewUser` (boolean): Whether user is new

## Related Guides

- [Session Management](/guides/authentication/sessions)
- [Multi-Factor Authentication](/guides/authentication/mfa)
- [Email Templates](/guides/customization/email-templates)
- [Rate Limiting](/guides/security/rate-limiting)