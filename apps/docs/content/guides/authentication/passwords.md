# Password Authentication

Secure password-based authentication with industry best practices and advanced security features.

## Overview

Password authentication provides a familiar and secure way for users to access your application. Plinto implements password authentication with multiple layers of security including bcrypt hashing, rate limiting, and breach detection.

## Quick Start

### 1. Sign Up with Password

```typescript
import { plinto } from '@plinto/typescript-sdk'

const { user, session } = await plinto.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePassword123!',
  metadata: {
    source: 'web',
    referrer: 'landing-page'
  }
})

// User is now authenticated
console.log('Welcome', user.email)
```

### 2. Sign In with Password

```typescript
const { user, session } = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'SecurePassword123!',
  rememberMe: true // Extended session duration
})

// Store session token
setCookie('session', session.token, {
  httpOnly: true,
  secure: true,
  sameSite: 'lax',
  maxAge: session.expiresIn
})
```

### 3. Password Reset Flow

```typescript
// Request password reset
await plinto.auth.requestPasswordReset({
  email: 'user@example.com'
})

// User receives email with reset token
// In your reset handler:
await plinto.auth.resetPassword({
  token: resetToken,
  newPassword: 'NewSecurePassword456!',
  logoutEverywhere: true // Invalidate all sessions
})
```

## Implementation Guide

### Backend Setup

#### Express.js Implementation

```javascript
const express = require('express')
const { Plinto } = require('@plinto/typescript-sdk')

const app = express()
const plinto = new Plinto({
  apiKey: process.env.PLINTO_API_KEY
})

// Sign up endpoint
app.post('/auth/signup', async (req, res) => {
  const { email, password, name } = req.body

  try {
    // Validate password strength
    const strength = await plinto.auth.checkPasswordStrength(password)
    if (strength.score < 3) {
      return res.status(400).json({
        error: 'Password too weak',
        suggestions: strength.suggestions
      })
    }

    // Check for breached passwords
    const breached = await plinto.auth.checkPasswordBreach(password)
    if (breached) {
      return res.status(400).json({
        error: 'This password has been found in data breaches'
      })
    }

    // Create account
    const { user, session } = await plinto.auth.signUp({
      email,
      password,
      name,
      emailVerification: 'required' // Send verification email
    })

    res.json({
      user,
      session,
      message: 'Please check your email to verify your account'
    })
  } catch (error) {
    if (error.code === 'user_exists') {
      res.status(409).json({ error: 'Email already registered' })
    } else {
      res.status(400).json({ error: error.message })
    }
  }
})

// Sign in endpoint with rate limiting
app.post('/auth/signin', async (req, res) => {
  const { email, password, rememberMe } = req.body
  const ip = req.ip

  try {
    // Check rate limit
    const rateLimited = await plinto.auth.checkRateLimit(ip, 'signin')
    if (rateLimited) {
      return res.status(429).json({
        error: 'Too many attempts. Please try again later.',
        retryAfter: rateLimited.retryAfter
      })
    }

    const { user, session, requiresMfa } = await plinto.auth.signIn({
      email,
      password,
      rememberMe,
      deviceInfo: {
        ip,
        userAgent: req.headers['user-agent']
      }
    })

    if (requiresMfa) {
      // MFA required
      return res.json({
        requiresMfa: true,
        mfaToken: session.mfaToken,
        methods: user.mfaMethods
      })
    }

    // Set secure session cookie
    res.cookie('session', session.token, {
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      maxAge: rememberMe ? 30 * 24 * 60 * 60 * 1000 : undefined
    })

    res.json({ user, session })
  } catch (error) {
    // Log failed attempt
    await plinto.audit.log({
      event: 'auth.failed',
      email,
      ip,
      reason: error.message
    })

    res.status(401).json({ error: 'Invalid credentials' })
  }
})

// Password reset request
app.post('/auth/password/reset-request', async (req, res) => {
  const { email } = req.body

  try {
    await plinto.auth.requestPasswordReset({
      email,
      redirectUrl: `${process.env.APP_URL}/reset-password`
    })

    // Always return success to prevent email enumeration
    res.json({
      message: 'If an account exists, a reset link has been sent'
    })
  } catch (error) {
    // Log but don't expose error
    console.error('Password reset error:', error)
    res.json({
      message: 'If an account exists, a reset link has been sent'
    })
  }
})

// Password reset completion
app.post('/auth/password/reset', async (req, res) => {
  const { token, newPassword } = req.body

  try {
    const { user, session } = await plinto.auth.resetPassword({
      token,
      newPassword,
      logoutEverywhere: true
    })

    res.json({
      message: 'Password reset successful',
      user,
      session
    })
  } catch (error) {
    res.status(400).json({
      error: 'Invalid or expired reset token'
    })
  }
})
```

#### Python FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from plinto import Plinto
import os

app = FastAPI()
plinto = Plinto(api_key=os.getenv("PLINTO_API_KEY"))
security = HTTPBearer()

@app.post("/auth/signup")
async def signup(
    email: str,
    password: str,
    name: str = None
):
    # Check password strength
    strength = await plinto.auth.check_password_strength(password)
    if strength.score < 3:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Password too weak",
                "suggestions": strength.suggestions
            }
        )

    # Check for breached passwords
    if await plinto.auth.check_password_breach(password):
        raise HTTPException(
            status_code=400,
            detail="This password has been found in data breaches"
        )

    try:
        result = await plinto.auth.sign_up(
            email=email,
            password=password,
            name=name,
            email_verification="required"
        )
        return {
            "user": result.user,
            "session": result.session,
            "message": "Please verify your email"
        }
    except Exception as e:
        if "user_exists" in str(e):
            raise HTTPException(409, "Email already registered")
        raise HTTPException(400, str(e))

@app.post("/auth/signin")
async def signin(
    email: str,
    password: str,
    remember_me: bool = False,
    request: Request = None
):
    # Check rate limit
    ip = request.client.host
    rate_limited = await plinto.auth.check_rate_limit(ip, "signin")
    if rate_limited:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too many attempts",
                "retry_after": rate_limited.retry_after
            }
        )

    try:
        result = await plinto.auth.sign_in(
            email=email,
            password=password,
            remember_me=remember_me,
            device_info={
                "ip": ip,
                "user_agent": request.headers.get("user-agent")
            }
        )

        if result.requires_mfa:
            return {
                "requires_mfa": True,
                "mfa_token": result.session.mfa_token,
                "methods": result.user.mfa_methods
            }

        return {
            "user": result.user,
            "session": result.session
        }
    except Exception as e:
        # Log failed attempt
        await plinto.audit.log(
            event="auth.failed",
            email=email,
            ip=ip,
            reason=str(e)
        )
        raise HTTPException(401, "Invalid credentials")

@app.post("/auth/password/change")
async def change_password(
    current_password: str,
    new_password: str,
    logout_other_devices: bool = False,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        # Verify current session
        session = await plinto.auth.verify_session(credentials.credentials)

        # Validate new password
        strength = await plinto.auth.check_password_strength(new_password)
        if strength.score < 3:
            raise HTTPException(400, "New password too weak")

        # Change password
        result = await plinto.auth.change_password(
            user_id=session.user_id,
            current_password=current_password,
            new_password=new_password,
            logout_other_devices=logout_other_devices
        )

        return {"message": "Password changed successfully"}
    except Exception as e:
        raise HTTPException(400, str(e))
```

### Frontend Implementation

#### React Component

```jsx
import React, { useState } from 'react'
import { usePlinto } from '@plinto/react-sdk'
import { EyeIcon, EyeOffIcon } from '@heroicons/react/24/outline'

function PasswordAuth() {
  const { signUp, signIn, checkPasswordStrength } = usePlinto()
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [passwordStrength, setPasswordStrength] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handlePasswordChange = async (value) => {
    setPassword(value)
    if (mode === 'signup' && value.length > 0) {
      const strength = await checkPasswordStrength(value)
      setPasswordStrength(strength)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      if (mode === 'signup') {
        if (password !== confirmPassword) {
          throw new Error('Passwords do not match')
        }
        if (passwordStrength?.score < 3) {
          throw new Error('Password is too weak')
        }
        await signUp({ email, password })
      } else {
        await signIn({ email, password })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="mt-1 block w-full rounded-md border-gray-300"
          autoComplete="email"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium">
          Password
        </label>
        <div className="relative mt-1">
          <input
            id="password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => handlePasswordChange(e.target.value)}
            required
            className="block w-full rounded-md border-gray-300 pr-10"
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center"
          >
            {showPassword ? (
              <EyeOffIcon className="h-5 w-5 text-gray-400" />
            ) : (
              <EyeIcon className="h-5 w-5 text-gray-400" />
            )}
          </button>
        </div>

        {mode === 'signup' && passwordStrength && (
          <PasswordStrengthIndicator strength={passwordStrength} />
        )}
      </div>

      {mode === 'signup' && (
        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium">
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            type={showPassword ? 'text' : 'password'}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className="mt-1 block w-full rounded-md border-gray-300"
            autoComplete="new-password"
          />
        </div>
      )}

      {error && (
        <div className="text-red-600 text-sm">{error}</div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Loading...' : mode === 'signin' ? 'Sign In' : 'Sign Up'}
      </button>

      <div className="text-center">
        <button
          type="button"
          onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
          className="text-sm text-blue-600 hover:underline"
        >
          {mode === 'signin'
            ? "Don't have an account? Sign up"
            : 'Already have an account? Sign in'}
        </button>
      </div>
    </form>
  )
}

function PasswordStrengthIndicator({ strength }) {
  const colors = ['red', 'orange', 'yellow', 'green', 'green']
  const labels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong']

  return (
    <div className="mt-2">
      <div className="flex space-x-1">
        {[0, 1, 2, 3, 4].map((level) => (
          <div
            key={level}
            className={`h-2 flex-1 rounded ${
              level <= strength.score
                ? `bg-${colors[strength.score]}-500`
                : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
      <p className="text-sm mt-1 text-gray-600">
        {labels[strength.score]}
        {strength.suggestions?.length > 0 && (
          <span className="block text-xs">
            {strength.suggestions[0]}
          </span>
        )}
      </p>
    </div>
  )
}
```

## Password Security Features

### Password Strength Requirements

```typescript
// Default requirements (customizable)
{
  minLength: 8,
  maxLength: 128,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSymbols: true,
  preventCommonPasswords: true,
  preventUserInfo: true, // Can't contain email/name
  preventRepeatingChars: true,
  preventSequentialChars: true
}
```

### Breach Detection

```typescript
// Check if password has been compromised
const breached = await plinto.auth.checkPasswordBreach(password)

if (breached) {
  // Password found in breach databases
  console.log(`This password has appeared ${breached.count} times in breaches`)
  // Require user to choose different password
}
```

### Rate Limiting

```typescript
// Configure rate limits
{
  signin: {
    maxAttempts: 5,
    windowMs: 15 * 60 * 1000, // 15 minutes
    blockDuration: 60 * 60 * 1000 // 1 hour after limit
  },
  passwordReset: {
    maxAttempts: 3,
    windowMs: 60 * 60 * 1000, // 1 hour
    perEmail: true
  }
}
```

### Account Lockout

```typescript
// After multiple failed attempts
{
  lockoutThreshold: 5, // Failed attempts
  lockoutDuration: 30 * 60 * 1000, // 30 minutes
  notifyUser: true, // Send email on lockout
  requireUnlock: false // Admin unlock vs auto-unlock
}
```

## Advanced Features

### Password History

Prevent users from reusing recent passwords:

```typescript
await plinto.auth.changePassword({
  userId,
  newPassword,
  enforceHistory: true,
  historyCount: 5 // Can't reuse last 5 passwords
})
```

### Password Expiration

Force periodic password changes:

```typescript
// Configure password expiration
{
  passwordExpiration: {
    enabled: true,
    maxAge: 90 * 24 * 60 * 60 * 1000, // 90 days
    warningPeriod: 14 * 24 * 60 * 60 * 1000, // Warn 14 days before
    graceLogins: 3 // Allow 3 logins after expiration
  }
}

// Check if password is expired
const status = await plinto.auth.checkPasswordStatus(userId)
if (status.expired) {
  // Redirect to password change
}
```

### Passwordless Fallback

Offer alternatives when users forget passwords:

```typescript
// If password reset fails, offer magic link
await plinto.auth.sendMagicLink({
  email,
  reason: 'password_recovery'
})

// Or use security questions
const verified = await plinto.auth.verifySecurityQuestions({
  userId,
  answers: {
    question1: 'answer1',
    question2: 'answer2'
  }
})
```

### Delegated Authentication

Allow administrators to set temporary passwords:

```typescript
// Admin sets temporary password
await plinto.auth.setTemporaryPassword({
  userId,
  tempPassword: generateSecurePassword(),
  requireChange: true, // Force change on first login
  expiresIn: 24 * 60 * 60 * 1000 // 24 hours
})
```

## Security Best Practices

### 1. Password Storage

- Passwords hashed using bcrypt with cost factor 12
- Salts automatically generated and stored
- Timing-safe comparison to prevent timing attacks
- Never log or transmit plaintext passwords

### 2. Transport Security

```typescript
// Always use HTTPS
if (req.protocol !== 'https' && process.env.NODE_ENV === 'production') {
  throw new Error('Password authentication requires HTTPS')
}

// Implement HSTS
res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
```

### 3. Session Security

```typescript
// Secure session configuration
{
  cookie: {
    httpOnly: true, // Prevent XSS access
    secure: true, // HTTPS only
    sameSite: 'lax', // CSRF protection
    maxAge: null, // Session cookie by default
    domain: '.example.com', // Scope appropriately
    path: '/' // Available site-wide
  },
  regenerate: true, // New session ID on login
  rolling: true // Extend on activity
}
```

### 4. Brute Force Protection

```typescript
// Progressive delays after failed attempts
const delay = Math.min(1000 * Math.pow(2, failedAttempts), 30000)
await new Promise(resolve => setTimeout(resolve, delay))

// CAPTCHA after threshold
if (failedAttempts > 3) {
  requireCaptcha = true
}

// IP-based blocking
if (failedAttempts > 10) {
  await blockIP(clientIP, '24h')
}
```

## Error Handling

### Common Errors

| Error Code | Description | User Action |
|------------|-------------|-------------|
| `invalid_credentials` | Wrong email/password | Check credentials |
| `account_locked` | Too many failed attempts | Wait or contact support |
| `password_expired` | Password needs update | Change password |
| `weak_password` | Password doesn't meet requirements | Choose stronger password |
| `password_breached` | Password found in breaches | Choose different password |
| `rate_limited` | Too many requests | Wait before retrying |

### Error Response Examples

```typescript
// Handle specific errors
try {
  await plinto.auth.signIn({ email, password })
} catch (error) {
  switch (error.code) {
    case 'invalid_credentials':
      showError('Invalid email or password')
      break
    case 'account_locked':
      showError(`Account locked. Try again in ${error.unlockIn} minutes`)
      break
    case 'email_not_verified':
      promptEmailVerification()
      break
    case 'mfa_required':
      redirectToMfa(error.mfaToken)
      break
    default:
      showError('An error occurred. Please try again.')
  }
}
```

## Testing

### Unit Tests

```typescript
describe('Password Authentication', () => {
  it('should enforce password strength requirements', async () => {
    const weakPassword = '12345678'
    const result = await plinto.auth.checkPasswordStrength(weakPassword)
    expect(result.score).toBeLessThan(3)
    expect(result.suggestions).toContain('Add uppercase letters')
  })

  it('should detect breached passwords', async () => {
    const commonPassword = 'password123'
    const breached = await plinto.auth.checkPasswordBreach(commonPassword)
    expect(breached).toBeTruthy()
    expect(breached.count).toBeGreaterThan(0)
  })

  it('should handle rate limiting', async () => {
    // Make multiple failed attempts
    for (let i = 0; i < 6; i++) {
      try {
        await plinto.auth.signIn({
          email: 'test@example.com',
          password: 'wrong'
        })
      } catch (e) {
        // Expected to fail
      }
    }

    // Next attempt should be rate limited
    await expect(plinto.auth.signIn({
      email: 'test@example.com',
      password: 'correct'
    })).rejects.toThrow('rate_limited')
  })
})
```

### Integration Tests

```typescript
describe('Password Flow E2E', () => {
  it('should complete full authentication flow', async () => {
    // Sign up
    const { user } = await plinto.auth.signUp({
      email: 'newuser@example.com',
      password: 'SecurePass123!'
    })
    expect(user.emailVerified).toBe(false)

    // Verify email
    const verifyToken = await getEmailVerificationToken('newuser@example.com')
    await plinto.auth.verifyEmail({ token: verifyToken })

    // Sign in
    const { session } = await plinto.auth.signIn({
      email: 'newuser@example.com',
      password: 'SecurePass123!'
    })
    expect(session.token).toBeDefined()

    // Change password
    await plinto.auth.changePassword({
      currentPassword: 'SecurePass123!',
      newPassword: 'NewSecurePass456!'
    })

    // Verify old password no longer works
    await expect(plinto.auth.signIn({
      email: 'newuser@example.com',
      password: 'SecurePass123!'
    })).rejects.toThrow('invalid_credentials')
  })
})
```

## Migration Guide

### From Basic Auth to Plinto

```typescript
// Before: Basic implementation
const hashedPassword = await bcrypt.hash(password, 10)
await db.users.create({ email, password: hashedPassword })

// After: Plinto with full security
const { user, session } = await plinto.auth.signUp({
  email,
  password,
  // Automatic: hashing, breach check, strength validation,
  // rate limiting, audit logging, session management
})
```

### From Other Providers

```typescript
// Migrate from Auth0
const auth0Users = await auth0.getUsers()
for (const user of auth0Users) {
  await plinto.auth.importUser({
    email: user.email,
    hashedPassword: user.password_hash,
    hashAlgorithm: 'bcrypt',
    emailVerified: user.email_verified,
    metadata: user.user_metadata
  })
}

// Migrate from Firebase
const firebaseUsers = await admin.auth().listUsers()
for (const user of firebaseUsers.users) {
  await plinto.auth.importUser({
    email: user.email,
    hashedPassword: user.passwordHash,
    hashAlgorithm: 'scrypt',
    salt: user.salt,
    emailVerified: user.emailVerified,
    metadata: user.customClaims
  })
}
```

## Compliance Considerations

### GDPR Compliance

```typescript
// Right to be forgotten
await plinto.auth.deleteUser({
  userId,
  deleteData: true,
  anonymize: false // Or true to keep anonymized records
})

// Data portability
const userData = await plinto.auth.exportUserData({
  userId,
  format: 'json' // or 'csv'
})
```

### HIPAA Compliance

```typescript
// Audit all authentication events
plinto.configure({
  audit: {
    enabled: true,
    events: ['auth.*'],
    retention: 6 * 365 * 24 * 60 * 60 * 1000, // 6 years
    encryption: true
  }
})
```

### SOC 2 Requirements

```typescript
// Enforce strong passwords
plinto.configure({
  password: {
    minLength: 12,
    requireMfa: true, // For privileged accounts
    expiration: 90 * 24 * 60 * 60 * 1000,
    history: 12 // Can't reuse last 12 passwords
  }
})
```

## Troubleshooting

### Users Can't Sign In

1. Check if account is locked from failed attempts
2. Verify email is verified (if required)
3. Check if password has expired
4. Verify rate limiting isn't blocking legitimate attempts
5. Ensure cookies are enabled for session storage

### Password Reset Not Working

1. Check email delivery and spam folders
2. Verify reset token hasn't expired (default 1 hour)
3. Ensure password meets new requirements
4. Check if user account exists and is active
5. Verify redirect URLs are whitelisted

### Session Issues

1. Verify cookie settings match domain
2. Check if session has expired
3. Ensure HTTPS is used in production
4. Verify CORS settings for API calls
5. Check if refresh token is valid

## API Reference

### `signUp(options)`

Create new account with password.

**Parameters:**
- `email` (string, required): User email
- `password` (string, required): User password
- `name` (string): User's name
- `metadata` (object): Additional user data
- `emailVerification` (string): 'required' | 'optional' | 'skip'

**Returns:**
- `user` (object): User profile
- `session` (object): Session details

### `signIn(options)`

Authenticate with email and password.

**Parameters:**
- `email` (string, required): User email
- `password` (string, required): User password
- `rememberMe` (boolean): Extended session
- `deviceInfo` (object): Device metadata

**Returns:**
- `user` (object): User profile
- `session` (object): Session details
- `requiresMfa` (boolean): If MFA needed

### `changePassword(options)`

Change user password.

**Parameters:**
- `currentPassword` (string, required): Current password
- `newPassword` (string, required): New password
- `logoutOtherDevices` (boolean): Invalidate other sessions

**Returns:**
- `success` (boolean): Operation result
- `session` (object): New session

## Related Guides

- [Session Management](/guides/authentication/sessions)
- [Multi-Factor Authentication](/guides/authentication/mfa)
- [Security Best Practices](/guides/security/best-practices)
- [Rate Limiting](/guides/security/rate-limiting)