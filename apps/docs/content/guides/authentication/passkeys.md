# Passkeys & WebAuthn Authentication

Implement passwordless authentication using passkeys (WebAuthn/FIDO2) for enhanced security and user experience.

## Overview

Passkeys provide a phishing-resistant, passwordless authentication method using biometrics, security keys, or device credentials. Built on WebAuthn/FIDO2 standards, passkeys offer superior security while simplifying the user experience.

## Benefits

- **Phishing Resistant**: Cryptographically bound to specific origins
- **No Passwords**: Eliminate password-related vulnerabilities
- **Better UX**: One-touch authentication with biometrics
- **Cross-Platform**: Works across devices with cloud sync
- **Strong Security**: Public key cryptography with hardware backing

## Quick Start

### 1. Register a Passkey

```typescript
import { plinto } from '@plinto/typescript-sdk'

// Start passkey registration
const { options } = await plinto.auth.passkey.beginRegistration({
  userId: currentUser.id,
  userName: currentUser.email,
  displayName: currentUser.name
})

// Browser WebAuthn API
const credential = await navigator.credentials.create({
  publicKey: options
})

// Complete registration
const { passkey } = await plinto.auth.passkey.completeRegistration({
  userId: currentUser.id,
  credential
})

console.log('Passkey registered:', passkey.id)
```

### 2. Authenticate with Passkey

```typescript
// Start authentication
const { options } = await plinto.auth.passkey.beginAuthentication({
  // Optional: provide email for conditional UI
  email: 'user@example.com'
})

// Browser WebAuthn API
const credential = await navigator.credentials.get({
  publicKey: options,
  mediation: 'conditional' // Enable autofill UI
})

// Complete authentication
const { user, session } = await plinto.auth.passkey.completeAuthentication({
  credential
})

console.log('Authenticated as:', user.email)
```

## Implementation Guide

### Backend Setup

#### Express.js Implementation

```javascript
const express = require('express')
const { Plinto } = require('@plinto/typescript-sdk')

const app = express()
const plinto = new Plinto({
  apiKey: process.env.PLINTO_API_KEY,
  rpId: 'example.com', // Relying Party ID
  rpName: 'Example App', // Display name
  rpOrigin: 'https://example.com' // Expected origin
})

// Begin passkey registration
app.post('/auth/passkey/register/begin', async (req, res) => {
  const { userId } = req.session

  if (!userId) {
    return res.status(401).json({ error: 'Must be logged in to register passkey' })
  }

  try {
    const user = await plinto.users.get(userId)

    const { options, challenge } = await plinto.auth.passkey.beginRegistration({
      userId,
      userName: user.email,
      displayName: user.name,
      authenticatorSelection: {
        authenticatorAttachment: 'platform', // or 'cross-platform'
        residentKey: 'required', // Enable discoverable credentials
        userVerification: 'preferred'
      },
      attestation: 'none', // or 'direct' for enterprise
      excludeCredentials: user.passkeys // Prevent re-registration
    })

    // Store challenge in session
    req.session.challenge = challenge

    res.json({ options })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Complete passkey registration
app.post('/auth/passkey/register/complete', async (req, res) => {
  const { credential } = req.body
  const { userId, challenge } = req.session

  if (!userId || !challenge) {
    return res.status(401).json({ error: 'Invalid session' })
  }

  try {
    const { passkey } = await plinto.auth.passkey.completeRegistration({
      userId,
      credential,
      challenge,
      origin: 'https://example.com',
      verifyHostname: true
    })

    // Log passkey registration
    await plinto.audit.log({
      event: 'passkey.registered',
      userId,
      passkeyId: passkey.id,
      authenticatorType: passkey.authenticatorType
    })

    res.json({
      success: true,
      passkey: {
        id: passkey.id,
        name: passkey.name,
        createdAt: passkey.createdAt,
        lastUsedAt: passkey.lastUsedAt
      }
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Begin passkey authentication
app.post('/auth/passkey/authenticate/begin', async (req, res) => {
  const { email } = req.body // Optional for conditional UI

  try {
    const { options, challenge } = await plinto.auth.passkey.beginAuthentication({
      email,
      userVerification: 'preferred',
      // For conditional UI (autofill)
      mediation: email ? undefined : 'conditional'
    })

    req.session.challenge = challenge

    res.json({ options })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Complete passkey authentication
app.post('/auth/passkey/authenticate/complete', async (req, res) => {
  const { credential } = req.body
  const { challenge } = req.session

  if (!challenge) {
    return res.status(401).json({ error: 'Invalid session' })
  }

  try {
    const { user, session, passkey } = await plinto.auth.passkey.completeAuthentication({
      credential,
      challenge,
      origin: 'https://example.com',
      verifyHostname: true,
      deviceInfo: {
        ip: req.ip,
        userAgent: req.headers['user-agent']
      }
    })

    // Update passkey last used
    await plinto.auth.passkey.updateLastUsed(passkey.id)

    // Set session cookie
    res.cookie('session', session.token, {
      httpOnly: true,
      secure: true,
      sameSite: 'lax'
    })

    res.json({
      user,
      session,
      message: 'Successfully authenticated with passkey'
    })
  } catch (error) {
    // Log failed attempt
    await plinto.audit.log({
      event: 'passkey.failed',
      reason: error.message,
      ip: req.ip
    })

    res.status(401).json({ error: 'Authentication failed' })
  }
})

// List user's passkeys
app.get('/auth/passkeys', async (req, res) => {
  const { userId } = req.session

  if (!userId) {
    return res.status(401).json({ error: 'Not authenticated' })
  }

  try {
    const passkeys = await plinto.auth.passkey.list(userId)

    res.json({
      passkeys: passkeys.map(pk => ({
        id: pk.id,
        name: pk.name,
        createdAt: pk.createdAt,
        lastUsedAt: pk.lastUsedAt,
        authenticatorType: pk.authenticatorType,
        synced: pk.backupEligible,
        platform: pk.platform
      }))
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Delete passkey
app.delete('/auth/passkeys/:passkeyId', async (req, res) => {
  const { userId } = req.session
  const { passkeyId } = req.params

  try {
    await plinto.auth.passkey.delete({
      userId,
      passkeyId
    })

    res.json({ success: true })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})
```

#### Python FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException, Depends, Request
from plinto import Plinto
import os
import json

app = FastAPI()
plinto = Plinto(
    api_key=os.getenv("PLINTO_API_KEY"),
    rp_id="example.com",
    rp_name="Example App",
    rp_origin="https://example.com"
)

@app.post("/auth/passkey/register/begin")
async def begin_registration(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(401, "Must be logged in")

    user = await plinto.users.get(user_id)

    result = await plinto.auth.passkey.begin_registration(
        user_id=user_id,
        user_name=user.email,
        display_name=user.name,
        authenticator_selection={
            "authenticator_attachment": "platform",
            "resident_key": "required",
            "user_verification": "preferred"
        }
    )

    # Store challenge in session
    request.session["challenge"] = result.challenge

    return {"options": result.options}

@app.post("/auth/passkey/register/complete")
async def complete_registration(
    credential: dict,
    request: Request
):
    user_id = request.session.get("user_id")
    challenge = request.session.get("challenge")

    if not user_id or not challenge:
        raise HTTPException(401, "Invalid session")

    try:
        result = await plinto.auth.passkey.complete_registration(
            user_id=user_id,
            credential=credential,
            challenge=challenge,
            origin="https://example.com"
        )

        # Log registration
        await plinto.audit.log(
            event="passkey.registered",
            user_id=user_id,
            passkey_id=result.passkey.id
        )

        return {
            "success": True,
            "passkey": {
                "id": result.passkey.id,
                "name": result.passkey.name,
                "created_at": result.passkey.created_at
            }
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/auth/passkey/authenticate/begin")
async def begin_authentication(
    email: str = None,
    request: Request = None
):
    result = await plinto.auth.passkey.begin_authentication(
        email=email,
        user_verification="preferred"
    )

    request.session["challenge"] = result.challenge

    return {"options": result.options}

@app.post("/auth/passkey/authenticate/complete")
async def complete_authentication(
    credential: dict,
    request: Request
):
    challenge = request.session.get("challenge")

    if not challenge:
        raise HTTPException(401, "Invalid session")

    try:
        result = await plinto.auth.passkey.complete_authentication(
            credential=credential,
            challenge=challenge,
            origin="https://example.com",
            device_info={
                "ip": request.client.host,
                "user_agent": request.headers.get("user-agent")
            }
        )

        # Create session
        request.session["user_id"] = result.user.id

        return {
            "user": result.user,
            "session": result.session
        }
    except Exception as e:
        # Log failed attempt
        await plinto.audit.log(
            event="passkey.failed",
            reason=str(e),
            ip=request.client.host
        )
        raise HTTPException(401, "Authentication failed")
```

### Frontend Implementation

#### React Component with Conditional UI

```jsx
import React, { useState, useEffect } from 'react'
import { usePlinto } from '@plinto/react-sdk'
import { startRegistration, startAuthentication } from '@simplewebauthn/browser'

function PasskeyAuth() {
  const { passkey } = usePlinto()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [passkeys, setPasskeys] = useState([])
  const [supportsPasskeys, setSupportsPasskeys] = useState(false)
  const [supportsConditionalUI, setSupportsConditionalUI] = useState(false)

  useEffect(() => {
    // Check browser support
    const checkSupport = async () => {
      const supported =
        'credentials' in navigator &&
        'create' in navigator.credentials &&
        'get' in navigator.credentials

      setSupportsPasskeys(supported)

      if (supported) {
        // Check for conditional UI support
        const conditional = await PublicKeyCredential.isConditionalMediationAvailable?.()
        setSupportsConditionalUI(conditional || false)

        if (conditional) {
          // Start conditional authentication
          startConditionalAuth()
        }
      }
    }

    checkSupport()
    loadPasskeys()
  }, [])

  const startConditionalAuth = async () => {
    try {
      // Get authentication options
      const { options } = await passkey.beginAuthentication()

      // Set up autofill UI
      const abortController = new AbortController()

      const credential = await navigator.credentials.get({
        publicKey: options,
        mediation: 'conditional',
        signal: abortController.signal
      })

      if (credential) {
        await completeAuthentication(credential)
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Conditional UI error:', error)
      }
    }
  }

  const loadPasskeys = async () => {
    try {
      const userPasskeys = await passkey.list()
      setPasskeys(userPasskeys)
    } catch (error) {
      console.error('Failed to load passkeys:', error)
    }
  }

  const registerPasskey = async () => {
    setLoading(true)
    setError(null)

    try {
      // Get registration options from server
      const { options } = await passkey.beginRegistration()

      // Create credential using browser API
      const credential = await startRegistration(options)

      // Send to server
      const { passkey: newPasskey } = await passkey.completeRegistration({
        credential
      })

      // Update local list
      setPasskeys([...passkeys, newPasskey])

      alert('Passkey registered successfully!')
    } catch (error) {
      setError(error.message)
    } finally {
      setLoading(false)
    }
  }

  const authenticateWithPasskey = async () => {
    setLoading(true)
    setError(null)

    try {
      // Get authentication options
      const { options } = await passkey.beginAuthentication({ email })

      // Get credential from browser
      const credential = await startAuthentication(options)

      await completeAuthentication(credential)
    } catch (error) {
      setError(error.message)
    } finally {
      setLoading(false)
    }
  }

  const completeAuthentication = async (credential) => {
    const { user, session } = await passkey.completeAuthentication({
      credential
    })

    // Handle successful authentication
    window.location.href = '/dashboard'
  }

  const deletePasskey = async (passkeyId) => {
    if (!confirm('Delete this passkey?')) return

    try {
      await passkey.delete(passkeyId)
      setPasskeys(passkeys.filter(pk => pk.id !== passkeyId))
    } catch (error) {
      setError(error.message)
    }
  }

  if (!supportsPasskeys) {
    return (
      <div className="alert alert-warning">
        Your browser doesn't support passkeys. Please use a modern browser.
      </div>
    )
  }

  return (
    <div className="passkey-auth">
      <h2>Passkey Authentication</h2>

      {supportsConditionalUI && (
        <div className="alert alert-info">
          ✨ Passkey autofill is available. Start typing in the email field.
        </div>
      )}

      <div className="auth-form">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email (optional for passkey)"
          autoComplete="username webauthn"
          className="form-control"
        />

        <button
          onClick={authenticateWithPasskey}
          disabled={loading}
          className="btn btn-primary"
        >
          {loading ? 'Authenticating...' : 'Sign in with Passkey'}
        </button>

        {error && (
          <div className="alert alert-danger">{error}</div>
        )}
      </div>

      {/* Passkey Management */}
      <div className="passkey-management mt-4">
        <h3>Your Passkeys</h3>

        {passkeys.length === 0 ? (
          <p>No passkeys registered yet.</p>
        ) : (
          <ul className="passkey-list">
            {passkeys.map(pk => (
              <li key={pk.id} className="passkey-item">
                <div className="passkey-info">
                  <strong>{pk.name || 'Unnamed Passkey'}</strong>
                  <span className="text-muted">
                    Created: {new Date(pk.createdAt).toLocaleDateString()}
                  </span>
                  {pk.lastUsedAt && (
                    <span className="text-muted">
                      Last used: {new Date(pk.lastUsedAt).toLocaleDateString()}
                    </span>
                  )}
                  {pk.synced && (
                    <span className="badge badge-info">Synced</span>
                  )}
                </div>
                <button
                  onClick={() => deletePasskey(pk.id)}
                  className="btn btn-sm btn-danger"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}

        <button
          onClick={registerPasskey}
          disabled={loading}
          className="btn btn-success mt-3"
        >
          Add New Passkey
        </button>
      </div>
    </div>
  )
}
```

#### Next.js App Router Implementation

```typescript
// app/auth/passkey/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { startRegistration, startAuthentication } from '@simplewebauthn/browser'

export default function PasskeyPage() {
  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [loading, setLoading] = useState(false)
  const [supportsPasskeys, setSupportsPasskeys] = useState(false)

  useEffect(() => {
    // Check WebAuthn support
    const checkSupport = () => {
      const supported =
        typeof window !== 'undefined' &&
        'PublicKeyCredential' in window

      setSupportsPasskeys(supported)

      if (supported) {
        // Enable conditional UI
        setupConditionalUI()
      }
    }

    checkSupport()
  }, [])

  const setupConditionalUI = async () => {
    if (!PublicKeyCredential.isConditionalMediationAvailable) return

    const available = await PublicKeyCredential.isConditionalMediationAvailable()
    if (!available) return

    // Get authentication options
    const response = await fetch('/api/auth/passkey/authenticate/begin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })

    const { options } = await response.json()

    // Create AbortController for cleanup
    const controller = new AbortController()

    try {
      const credential = await navigator.credentials.get({
        publicKey: options,
        mediation: 'conditional',
        signal: controller.signal
      })

      if (credential) {
        await completeAuth(credential)
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Conditional UI error:', error)
      }
    }

    // Cleanup on unmount
    return () => controller.abort()
  }

  const handleRegister = async () => {
    setLoading(true)

    try {
      // Begin registration
      const beginResponse = await fetch('/api/auth/passkey/register/begin', {
        method: 'POST',
        credentials: 'include'
      })

      const { options } = await beginResponse.json()

      // Create credential
      const credential = await startRegistration(options)

      // Complete registration
      const completeResponse = await fetch('/api/auth/passkey/register/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ credential })
      })

      const result = await completeResponse.json()

      if (result.success) {
        alert('Passkey registered successfully!')
      }
    } catch (error) {
      console.error('Registration error:', error)
      alert('Registration failed: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAuthenticate = async () => {
    setLoading(true)

    try {
      // Begin authentication
      const beginResponse = await fetch('/api/auth/passkey/authenticate/begin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })

      const { options } = await beginResponse.json()

      // Get credential
      const credential = await startAuthentication(options)

      await completeAuth(credential)
    } catch (error) {
      console.error('Authentication error:', error)
      alert('Authentication failed: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const completeAuth = async (credential: any) => {
    const response = await fetch('/api/auth/passkey/authenticate/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ credential })
    })

    const result = await response.json()

    if (result.user) {
      window.location.href = '/dashboard'
    }
  }

  if (!supportsPasskeys) {
    return (
      <div className="alert">
        Your browser doesn't support passkeys. Please use a modern browser.
      </div>
    )
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Passkey Authentication</h1>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="mb-4">
          <button
            onClick={() => setMode('signin')}
            className={`mr-2 px-4 py-2 rounded ${
              mode === 'signin' ? 'bg-blue-500 text-white' : 'bg-gray-200'
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => setMode('register')}
            className={`px-4 py-2 rounded ${
              mode === 'register' ? 'bg-blue-500 text-white' : 'bg-gray-200'
            }`}
          >
            Register Passkey
          </button>
        </div>

        {mode === 'signin' ? (
          <div>
            <p className="mb-4">
              Use your device's biometric or security key to sign in.
            </p>
            <button
              onClick={handleAuthenticate}
              disabled={loading}
              className="w-full py-2 px-4 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            >
              {loading ? 'Authenticating...' : 'Sign In with Passkey'}
            </button>
          </div>
        ) : (
          <div>
            <p className="mb-4">
              Register a new passkey for passwordless authentication.
            </p>
            <button
              onClick={handleRegister}
              disabled={loading}
              className="w-full py-2 px-4 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
            >
              {loading ? 'Registering...' : 'Register New Passkey'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
```

## Advanced Features

### Conditional UI (Autofill)

Enable passkey autofill in username fields:

```html
<!-- HTML with autocomplete attributes -->
<input
  type="email"
  name="email"
  autocomplete="username webauthn"
  placeholder="Email or use passkey"
/>
```

```javascript
// JavaScript implementation
async function setupConditionalUI() {
  // Check if conditional UI is available
  if (!PublicKeyCredential.isConditionalMediationAvailable) {
    return false
  }

  const available = await PublicKeyCredential.isConditionalMediationAvailable()
  if (!available) return false

  // Get authentication options
  const { options } = await fetch('/api/auth/passkey/authenticate/begin', {
    method: 'POST',
    body: JSON.stringify({ mediation: 'conditional' })
  }).then(r => r.json())

  // Set up conditional authentication
  const abortController = new AbortController()

  const credential = await navigator.credentials.get({
    publicKey: options,
    mediation: 'conditional',
    signal: abortController.signal
  })

  if (credential) {
    // User selected a passkey from autofill
    await completeAuthentication(credential)
  }

  return true
}
```

### Cross-Device Authentication

Support authentication from phones using QR codes:

```typescript
// Generate QR code for cross-device auth
const { qrCode, sessionId } = await plinto.auth.passkey.generateCrossDeviceQR({
  returnUrl: 'https://example.com/auth/complete'
})

// Display QR code
<img src={qrCode} alt="Scan to authenticate" />

// Poll for completion
const interval = setInterval(async () => {
  const result = await plinto.auth.passkey.checkCrossDeviceStatus(sessionId)

  if (result.completed) {
    clearInterval(interval)
    // Authentication successful
    window.location.href = '/dashboard'
  }
}, 2000)
```

### Backup and Sync

Handle synced passkeys across devices:

```typescript
// Check if passkey is backed up
const passkey = await plinto.auth.passkey.get(passkeyId)

if (passkey.backupEligible && passkey.backupState) {
  console.log('This passkey is synced across devices')
}

// Encourage backup for non-synced passkeys
if (!passkey.backupEligible) {
  promptUserToEnableCloudSync()
}
```

### Enterprise Attestation

Verify authenticator authenticity for enterprise:

```typescript
// Configure attestation requirements
const options = await plinto.auth.passkey.beginRegistration({
  userId,
  attestation: 'direct', // Request attestation
  authenticatorSelection: {
    authenticatorAttachment: 'cross-platform', // Security keys only
    requireResidentKey: true,
    userVerification: 'required'
  }
})

// Verify attestation on server
const { passkey, attestation } = await plinto.auth.passkey.completeRegistration({
  credential,
  verifyAttestation: true,
  allowedAuthenticators: ['Yubico', 'Google Titan'] // Whitelist
})
```

## Security Considerations

### 1. Origin Validation

```typescript
// Always verify origin
plinto.configure({
  passkey: {
    rpId: 'example.com',
    rpOrigins: [
      'https://example.com',
      'https://app.example.com'
    ],
    verifyHostname: true
  }
})
```

### 2. Challenge Generation

```typescript
// Secure challenge generation
{
  challengeLength: 32, // Minimum 32 bytes
  challengeTimeout: 60000, // 1 minute expiry
  storageMethod: 'session', // Store in server session
  oneTimeUse: true // Invalidate after use
}
```

### 3. User Verification

```typescript
// Enforce user verification
{
  userVerification: 'required', // Always require
  allowBackupAuthentication: false, // No fallback to device PIN
  minimumAuthenticatorLevel: 2 // FIDO2 Level 2 or higher
}
```

### 4. Rate Limiting

```typescript
// Prevent brute force attempts
{
  maxRegistrationAttempts: 5,
  maxAuthenticationAttempts: 10,
  windowMs: 15 * 60 * 1000, // 15 minutes
  skipSuccessfulRequests: true
}
```

## Browser Support

| Browser | Version | Platform Support | Conditional UI |
|---------|---------|------------------|----------------|
| Chrome | 67+ | ✅ Windows, Mac, Android | 108+ |
| Safari | 14+ | ✅ Mac, iOS | 16+ |
| Edge | 79+ | ✅ Windows | 108+ |
| Firefox | 60+ | ✅ All platforms | Limited |
| Opera | 54+ | ✅ All platforms | 94+ |

### Feature Detection

```javascript
// Comprehensive feature detection
const checkPasskeySupport = () => {
  const support = {
    basic: false,
    conditional: false,
    largeBlob: false,
    prfExtension: false
  }

  // Basic WebAuthn support
  if (window.PublicKeyCredential) {
    support.basic = true
  }

  // Conditional UI
  if (PublicKeyCredential.isConditionalMediationAvailable) {
    PublicKeyCredential.isConditionalMediationAvailable()
      .then(result => support.conditional = result)
  }

  // Large blob storage (for storing data with passkey)
  if (PublicKeyCredential.isExtensionAvailable) {
    PublicKeyCredential.isExtensionAvailable('largeBlob')
      .then(result => support.largeBlob = result)
  }

  return support
}
```

## Testing

### Unit Tests

```typescript
describe('Passkey Authentication', () => {
  it('should generate valid registration options', async () => {
    const options = await plinto.auth.passkey.beginRegistration({
      userId: 'test-user',
      userName: 'test@example.com'
    })

    expect(options.challenge).toBeDefined()
    expect(options.rp.id).toBe('example.com')
    expect(options.user.name).toBe('test@example.com')
  })

  it('should validate origin during authentication', async () => {
    const credential = mockCredential()

    await expect(
      plinto.auth.passkey.completeAuthentication({
        credential,
        challenge: 'test-challenge',
        origin: 'https://evil.com' // Wrong origin
      })
    ).rejects.toThrow('Invalid origin')
  })

  it('should handle attestation verification', async () => {
    const credential = mockCredentialWithAttestation()

    const result = await plinto.auth.passkey.completeRegistration({
      credential,
      verifyAttestation: true
    })

    expect(result.attestation.verified).toBe(true)
    expect(result.attestation.authenticatorInfo).toBeDefined()
  })
})
```

### E2E Tests with Playwright

```typescript
import { test, expect } from '@playwright/test'

test.describe('Passkey Flow', () => {
  test('should register and authenticate with passkey', async ({ page, context }) => {
    // Enable virtual authenticator
    const cdpSession = await context.newCDPSession(page)
    await cdpSession.send('WebAuthn.enable')

    // Add virtual authenticator
    const { authenticatorId } = await cdpSession.send('WebAuthn.addVirtualAuthenticator', {
      options: {
        protocol: 'ctap2',
        transport: 'internal',
        hasResidentKey: true,
        hasUserVerification: true,
        isUserVerified: true
      }
    })

    // Navigate to registration page
    await page.goto('/auth/passkey/register')

    // Register passkey
    await page.click('button:has-text("Register Passkey")')

    // Verify registration success
    await expect(page.locator('.success-message')).toContainText('Passkey registered')

    // Sign out
    await page.click('button:has-text("Sign Out")')

    // Navigate to login
    await page.goto('/auth/login')

    // Authenticate with passkey
    await page.click('button:has-text("Sign in with Passkey")')

    // Verify authentication success
    await expect(page).toHaveURL('/dashboard')

    // Cleanup
    await cdpSession.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId })
  })

  test('should handle conditional UI', async ({ page }) => {
    await page.goto('/auth/login')

    // Type in email field with webauthn autocomplete
    const emailField = page.locator('input[autocomplete="username webauthn"]')
    await emailField.click()

    // Virtual authenticator will trigger conditional UI
    // In real scenario, this would show passkey options
    await page.keyboard.type('user@example.com')

    // Wait for autofill UI (simulated)
    await page.waitForTimeout(1000)

    // Verify passkey option appears
    const passkeyOption = page.locator('.passkey-autofill-option')
    await expect(passkeyOption).toBeVisible()
  })
})
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "NotAllowedError" | User canceled or timeout | Retry with clear user prompt |
| "InvalidStateError" | Authenticator already registered | Check excludeCredentials |
| "NotSupportedError" | Unsupported configuration | Check browser compatibility |
| "SecurityError" | Invalid domain or protocol | Verify HTTPS and RP ID |
| "AbortError" | Operation aborted | Normal for conditional UI |

### Debugging Tips

```javascript
// Enable verbose logging
plinto.configure({
  passkey: {
    debug: true,
    logLevel: 'verbose'
  }
})

// Log all WebAuthn API calls
const originalCreate = navigator.credentials.create
navigator.credentials.create = function(...args) {
  console.log('WebAuthn create:', args)
  return originalCreate.apply(this, args)
}

// Check authenticator info
const info = await plinto.auth.passkey.getAuthenticatorInfo()
console.log('Authenticator capabilities:', info)
```

## Migration Guide

### From Password to Passkey

```typescript
// Progressive enhancement approach
async function migrateToPasskey(email, password) {
  // First, authenticate with password
  const { user, session } = await plinto.auth.signIn({
    email,
    password
  })

  // Prompt to add passkey
  const addPasskey = confirm('Would you like to enable passwordless login?')

  if (addPasskey) {
    // Register passkey while authenticated
    const { options } = await plinto.auth.passkey.beginRegistration({
      userId: user.id,
      userName: user.email
    })

    const credential = await navigator.credentials.create({
      publicKey: options
    })

    await plinto.auth.passkey.completeRegistration({
      userId: user.id,
      credential
    })

    // Optionally remove password
    if (confirm('Remove password and use passkey only?')) {
      await plinto.auth.removePassword(user.id)
    }
  }
}
```

### From Other Providers

```typescript
// Migrate from Auth0 WebAuthn
const auth0Credentials = await getAuth0Credentials()

for (const cred of auth0Credentials) {
  await plinto.auth.passkey.import({
    credentialId: cred.id,
    publicKey: cred.publicKey,
    userId: cred.userId,
    counter: cred.signCount,
    transports: cred.transports
  })
}
```

## Best Practices

1. **Always offer fallback authentication** - Not all users have passkey-capable devices
2. **Enable conditional UI** - Provides the best user experience with autofill
3. **Support multiple passkeys** - Users may have multiple devices
4. **Clear naming** - Let users name their passkeys for easy identification
5. **Show last used** - Help users identify active passkeys
6. **Implement recovery** - Account recovery without passkeys
7. **Test thoroughly** - Use virtual authenticators for testing

## API Reference

### `beginRegistration(options)`

Start passkey registration process.

**Parameters:**
- `userId` (string, required): User identifier
- `userName` (string, required): User email or username
- `displayName` (string): Human-readable name
- `authenticatorSelection` (object): Authenticator requirements
- `attestation` (string): Attestation preference

**Returns:**
- `options` (object): WebAuthn creation options
- `challenge` (string): Server challenge

### `completeRegistration(options)`

Complete passkey registration.

**Parameters:**
- `userId` (string, required): User identifier
- `credential` (object, required): WebAuthn credential
- `challenge` (string, required): Server challenge
- `origin` (string): Expected origin

**Returns:**
- `passkey` (object): Registered passkey details

### `beginAuthentication(options)`

Start passkey authentication.

**Parameters:**
- `email` (string): Optional user email
- `userVerification` (string): Verification requirement

**Returns:**
- `options` (object): WebAuthn request options
- `challenge` (string): Server challenge

### `completeAuthentication(options)`

Complete passkey authentication.

**Parameters:**
- `credential` (object, required): WebAuthn assertion
- `challenge` (string, required): Server challenge
- `origin` (string): Expected origin

**Returns:**
- `user` (object): Authenticated user
- `session` (object): Session details

## Related Guides

- [Multi-Factor Authentication](/guides/authentication/mfa)
- [Session Management](/guides/authentication/sessions)
- [Security Best Practices](/guides/security/best-practices)
- [Account Recovery](/guides/authentication/recovery)