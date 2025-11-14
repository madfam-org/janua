# Multi-Factor Authentication (MFA)

Enhance your application's security with comprehensive multi-factor authentication supporting TOTP, SMS, email, and hardware tokens.

## Overview

Multi-Factor Authentication (MFA) adds an essential layer of security by requiring users to provide multiple forms of verification. Plinto's MFA implementation supports multiple authentication factors and provides a seamless user experience while maintaining the highest security standards.

### Supported MFA Methods

- **Time-based One-Time Passwords (TOTP)** - Google Authenticator, Authy, 1Password
- **SMS Authentication** - Text message verification codes
- **Email Authentication** - Email-based verification codes  
- **Hardware Tokens** - WebAuthn-compatible security keys
- **Backup Codes** - Single-use recovery codes
- **Push Notifications** - Mobile app-based approvals

### Benefits

- **Enhanced Security**: Protect against password breaches and credential stuffing
- **Regulatory Compliance**: Meet SOX, HIPAA, and PCI DSS requirements
- **User Trust**: Build confidence with enterprise-grade security
- **Flexible Implementation**: Support multiple authentication flows
- **Recovery Options**: Secure account recovery mechanisms

## Quick Start

### 1. Enable MFA for User

```typescript
import { plinto } from '@plinto/typescript-sdk'

// Enable TOTP for user
const mfaSetup = await plinto.auth.enableMFA({
  userId: user.id,
  method: 'totp',
  label: 'MyApp Account'
})

// Present QR code to user
console.log('QR Code URL:', mfaSetup.qrCodeUrl)
console.log('Manual Entry Key:', mfaSetup.secret)
```

### 2. Verify MFA Setup

```typescript
// User enters code from authenticator app
const verificationResult = await plinto.auth.verifyMFA({
  userId: user.id,
  method: 'totp',
  code: '123456'
})

if (verificationResult.success) {
  // MFA is now active for the user
  console.log('MFA enabled successfully')
  
  // Generate backup codes
  const backupCodes = await plinto.auth.regenerateMFABackupCodes({
    userId: user.id
  })
  
  // Display backup codes to user (one-time display)
  console.log('Backup codes:', backupCodes.codes)
}
```

### 3. Authenticate with MFA

```typescript
// Step 1: Primary authentication
const primaryAuth = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'password123'
})

// Step 2: MFA challenge (if enabled for user)
if (primaryAuth.requiresMfa) {
  const availableMethods = primaryAuth.mfaMethods
  // ['totp', 'sms', 'email']
  
  // User chooses TOTP
  const mfaResult = await plinto.auth.mfa.challenge({
    sessionId: primaryAuth.sessionId,
    method: 'totp',
    code: '654321'
  })
  
  if (mfaResult.success) {
    const { user, session } = mfaResult
    console.log('Authentication complete')
  }
}
```

## Implementation Guides

### Express.js Implementation

#### Basic Setup

```typescript
// server.js
import express from 'express'
import { plinto } from '@plinto/typescript-sdk'
import rateLimit from 'express-rate-limit'

const app = express()

// Rate limiting for MFA endpoints
const mfaLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // 5 attempts per window
  message: 'Too many MFA attempts, please try again later'
})

// MFA setup endpoint
app.post('/api/auth/mfa/setup', authenticate, async (req, res) => {
  try {
    const { method, phoneNumber, label } = req.body
    
    const mfaSetup = await plinto.auth.enableMFA({
      userId: req.user.id,
      method,
      phoneNumber, // for SMS
      label: label || 'MyApp'
    })
    
    res.json({
      success: true,
      qrCodeUrl: mfaSetup.qrCodeUrl,
      secret: mfaSetup.secret,
      backupCodes: mfaSetup.backupCodes
    })
  } catch (error) {
    console.error('MFA setup error:', error)
    res.status(400).json({ 
      error: 'Failed to setup MFA',
      details: error.message
    })
  }
})

// MFA verification endpoint
app.post('/api/auth/mfa/verify', mfaLimiter, async (req, res) => {
  try {
    const { sessionId, method, code } = req.body
    
    const result = await plinto.auth.verifyMFA({
      sessionId,
      method,
      code
    })
    
    if (result.success) {
      // Set session cookie
      res.cookie('session', result.session.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: result.session.expiresIn * 1000
      })
      
      res.json({
        success: true,
        user: result.user,
        session: result.session
      })
    } else {
      res.status(401).json({
        error: 'Invalid MFA code',
        attemptsRemaining: result.attemptsRemaining
      })
    }
  } catch (error) {
    console.error('MFA verification error:', error)
    res.status(400).json({ 
      error: 'MFA verification failed',
      details: error.message
    })
  }
})

// MFA status endpoint
app.get('/api/auth/mfa/status', authenticate, async (req, res) => {
  try {
    const status = await plinto.auth.getMFAStatus({
      userId: req.user.id
    })
    
    res.json({
      enabled: status.enabled,
      methods: status.methods,
      backupCodesRemaining: status.backupCodesRemaining,
      lastUsed: status.lastUsed
    })
  } catch (error) {
    console.error('MFA status error:', error)
    res.status(500).json({ error: 'Failed to get MFA status' })
  }
})

// Disable MFA endpoint
app.post('/api/auth/mfa/disable', authenticate, async (req, res) => {
  try {
    const { password, confirmationCode } = req.body
    
    // Verify password for security
    await plinto.auth.verifyPassword({
      userId: req.user.id,
      password
    })
    
    await plinto.auth.disableMFA({
      userId: req.user.id,
      confirmationCode
    })
    
    res.json({ success: true, message: 'MFA disabled' })
  } catch (error) {
    console.error('MFA disable error:', error)
    res.status(400).json({ 
      error: 'Failed to disable MFA',
      details: error.message
    })
  }
})

// Backup codes management
app.post('/api/auth/mfa/backup-codes/regenerate', authenticate, async (req, res) => {
  try {
    const { password } = req.body
    
    // Verify password for security
    await plinto.auth.verifyPassword({
      userId: req.user.id,
      password
    })
    
    const backupCodes = await plinto.auth.regenerateMFABackupCodes({
      userId: req.user.id
    })
    
    res.json({
      success: true,
      codes: backupCodes.codes,
      generatedAt: backupCodes.generatedAt
    })
  } catch (error) {
    console.error('Backup codes regeneration error:', error)
    res.status(400).json({ 
      error: 'Failed to regenerate backup codes',
      details: error.message
    })
  }
})

// Authentication middleware with MFA support
async function authenticate(req, res, next) {
  try {
    const token = req.cookies.session || req.headers.authorization?.split(' ')[1]
    
    if (!token) {
      return res.status(401).json({ error: 'No authentication token' })
    }
    
    const session = await plinto.auth.verifySession(token)
    
    if (!session.valid) {
      return res.status(401).json({ error: 'Invalid or expired session' })
    }
    
    // Check if MFA is required but not completed
    if (session.requiresMfa && !session.mfaCompleted) {
      return res.status(403).json({ 
        error: 'MFA required',
        requiresMfa: true,
        sessionId: session.id,
        availableMethods: session.mfaMethods
      })
    }
    
    req.user = session.user
    req.session = session
    next()
  } catch (error) {
    console.error('Authentication error:', error)
    res.status(401).json({ error: 'Authentication failed' })
  }
}
```

#### Advanced MFA Middleware

```typescript
// middleware/mfa.js
import { plinto } from '@plinto/typescript-sdk'

// MFA requirement levels
export const MfaLevel = {
  NONE: 'none',
  OPTIONAL: 'optional',
  REQUIRED: 'required',
  ADMIN_ONLY: 'admin_only'
}

// MFA enforcement middleware
export function requireMfa(level = MfaLevel.REQUIRED) {
  return async (req, res, next) => {
    try {
      const { user, session } = req
      
      // Check if MFA is required based on level
      const mfaRequired = shouldRequireMfa(user, level)
      
      if (!mfaRequired) {
        return next()
      }
      
      // Check if user has MFA enabled
      const mfaStatus = await plinto.auth.getMFAStatus({
        userId: user.id
      })
      
      if (!mfaStatus.enabled) {
        return res.status(403).json({
          error: 'MFA required but not configured',
          requiresMfaSetup: true,
          redirectTo: '/settings/security'
        })
      }
      
      // Check if current session has MFA verified
      if (!session.mfaVerified) {
        return res.status(403).json({
          error: 'MFA verification required',
          requiresMfa: true,
          sessionId: session.id,
          availableMethods: mfaStatus.methods
        })
      }
      
      next()
    } catch (error) {
      console.error('MFA middleware error:', error)
      res.status(500).json({ error: 'MFA verification failed' })
    }
  }
}

function shouldRequireMfa(user, level) {
  switch (level) {
    case MfaLevel.NONE:
      return false
    case MfaLevel.OPTIONAL:
      return false // Let through, but suggest MFA
    case MfaLevel.REQUIRED:
      return true
    case MfaLevel.ADMIN_ONLY:
      return user.role === 'admin' || user.role === 'super_admin'
    default:
      return false
  }
}

// Usage in routes
app.post('/api/admin/users', 
  authenticate, 
  requireMfa(MfaLevel.ADMIN_ONLY), 
  createUser
)

app.post('/api/payments', 
  authenticate, 
  requireMfa(MfaLevel.REQUIRED), 
  processPayment
)
```

### FastAPI Implementation

#### Basic Setup

```python
# main.py
from fastapi import FastAPI, HTTPException, Depends, Cookie
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Optional, List
import plinto

app = FastAPI()
security = HTTPBearer()

class MfaSetupRequest(BaseModel):
    method: str
    phone_number: Optional[str] = None
    label: Optional[str] = "MyApp"

class MfaVerifyRequest(BaseModel):
    session_id: str
    method: str
    code: str

class MfaStatusResponse(BaseModel):
    enabled: bool
    methods: List[str]
    backup_codes_remaining: int
    last_used: Optional[str]

@app.post("/api/auth/mfa/setup")
async def setup_mfa(
    request: MfaSetupRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        mfa_setup = await plinto.auth.enableMFA(
            user_id=current_user["id"],
            method=request.method,
            phone_number=request.phone_number,
            label=request.label
        )
        
        return {
            "success": True,
            "qr_code_url": mfa_setup.qr_code_url,
            "secret": mfa_setup.secret,
            "backup_codes": mfa_setup.backup_codes
        }
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to setup MFA: {str(error)}"
        )

@app.post("/api/auth/mfa/verify")
async def verify_mfa(request: MfaVerifyRequest):
    try:
        result = await plinto.auth.verifyMFA(
            session_id=request.session_id,
            method=request.method,
            code=request.code
        )
        
        if result.success:
            response = {
                "success": True,
                "user": result.user,
                "session": result.session
            }
            
            # Set session cookie
            response = JSONResponse(content=response)
            response.set_cookie(
                key="session",
                value=result.session.token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=result.session.expires_in
            )
            return response
        else:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Invalid MFA code",
                    "attempts_remaining": result.attempts_remaining
                }
            )
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"MFA verification failed: {str(error)}"
        )

@app.get("/api/auth/mfa/status", response_model=MfaStatusResponse)
async def get_mfa_status(current_user: dict = Depends(get_current_user)):
    try:
        status = await plinto.auth.getMFAStatus(
            user_id=current_user["id"]
        )
        
        return MfaStatusResponse(
            enabled=status.enabled,
            methods=status.methods,
            backup_codes_remaining=status.backup_codes_remaining,
            last_used=status.last_used
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Failed to get MFA status"
        )

@app.post("/api/auth/mfa/disable")
async def disable_mfa(
    password: str,
    confirmation_code: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Verify password for security
        await plinto.auth.verify_password(
            user_id=current_user["id"],
            password=password
        )
        
        await plinto.auth.disableMFA(
            user_id=current_user["id"],
            confirmation_code=confirmation_code
        )
        
        return {"success": True, "message": "MFA disabled"}
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to disable MFA: {str(error)}"
        )

# Authentication dependency
async def get_current_user(
    session: Optional[str] = Cookie(None),
    token: Optional[str] = Depends(security)
):
    auth_token = session or (token.credentials if token else None)
    
    if not auth_token:
        raise HTTPException(
            status_code=401,
            detail="No authentication token"
        )
    
    try:
        session_data = await plinto.auth.verify_session(auth_token)
        
        if not session_data.valid:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session"
            )
        
        # Check if MFA is required but not completed
        if session_data.requires_mfa and not session_data.mfa_completed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "MFA required",
                    "requires_mfa": True,
                    "session_id": session_data.id,
                    "available_methods": session_data.mfa_methods
                }
            )
        
        return session_data.user
    except Exception as error:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

# MFA requirement decorator
def require_mfa(level: str = "required"):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Implementation similar to Express.js middleware
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

#### Advanced MFA Dependency

```python
# dependencies/mfa.py
from fastapi import HTTPException, Depends
from enum import Enum
from typing import Optional
import plinto

class MfaLevel(str, Enum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"
    ADMIN_ONLY = "admin_only"

class MfaRequirement:
    def __init__(self, level: MfaLevel = MfaLevel.REQUIRED):
        self.level = level
    
    async def __call__(
        self,
        current_user: dict = Depends(get_current_user),
        current_session: dict = Depends(get_current_session)
    ):
        # Check if MFA is required based on level
        mfa_required = self._should_require_mfa(current_user, self.level)
        
        if not mfa_required:
            return current_user
        
        # Check if user has MFA enabled
        mfa_status = await plinto.auth.getMFAStatus(
            user_id=current_user["id"]
        )
        
        if not mfa_status.enabled:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "MFA required but not configured",
                    "requires_mfa_setup": True,
                    "redirect_to": "/settings/security"
                }
            )
        
        # Check if current session has MFA verified
        if not current_session.get("mfa_verified", False):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "MFA verification required",
                    "requires_mfa": True,
                    "session_id": current_session["id"],
                    "available_methods": mfa_status.methods
                }
            )
        
        return current_user
    
    def _should_require_mfa(self, user: dict, level: MfaLevel) -> bool:
        if level == MfaLevel.NONE:
            return False
        elif level == MfaLevel.OPTIONAL:
            return False  # Let through, but suggest MFA
        elif level == MfaLevel.REQUIRED:
            return True
        elif level == MfaLevel.ADMIN_ONLY:
            return user.get("role") in ["admin", "super_admin"]
        return False

# Usage in routes
require_mfa_admin = MfaRequirement(MfaLevel.ADMIN_ONLY)
require_mfa_always = MfaRequirement(MfaLevel.REQUIRED)

@app.post("/api/admin/users")
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_mfa_admin)
):
    # Implementation
    pass

@app.post("/api/payments")
async def process_payment(
    payment_data: PaymentCreate,
    current_user: dict = Depends(require_mfa_always)
):
    # Implementation
    pass
```

### React Implementation

#### MFA Setup Component

```tsx
// components/MfaSetup.tsx
import React, { useState, useEffect } from 'react'
import QRCode from 'qrcode.react'
import { plinto } from '@plinto/typescript-sdk'

interface MfaSetupProps {
  onComplete: () => void
  onCancel: () => void
}

export const MfaSetup: React.FC<MfaSetupProps> = ({ onComplete, onCancel }) => {
  const [step, setStep] = useState<'method' | 'setup' | 'verify'>('method')
  const [selectedMethod, setSelectedMethod] = useState<string>('')
  const [setupData, setSetupData] = useState<any>(null)
  const [verificationCode, setVerificationCode] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const methods = [
    {
      id: 'totp',
      name: 'Authenticator App',
      description: 'Use Google Authenticator, Authy, or similar apps',
      icon: '📱'
    },
    {
      id: 'sms',
      name: 'SMS Messages',
      description: 'Receive codes via text message',
      icon: '💬'
    },
    {
      id: 'email',
      name: 'Email',
      description: 'Receive codes via email',
      icon: '✉️'
    }
  ]

  const handleMethodSelect = (method: string) => {
    setSelectedMethod(method)
    setStep('setup')
  }

  const setupMfa = async () => {
    try {
      setLoading(true)
      setError('')

      const setup = await plinto.auth.enableMFA({
        method: selectedMethod,
        phoneNumber: selectedMethod === 'sms' ? phoneNumber : undefined,
        label: 'MyApp Account'
      })

      setSetupData(setup)
      setStep('verify')
    } catch (err: any) {
      setError(err.message || 'Setup failed')
    } finally {
      setLoading(false)
    }
  }

  const verifySetup = async () => {
    try {
      setLoading(true)
      setError('')

      const result = await plinto.auth.verifyMFA({
        method: selectedMethod,
        code: verificationCode
      })

      if (result.success) {
        // Show backup codes
        if (result.backupCodes) {
          alert(`Save these backup codes: ${result.backupCodes.join(', ')}`)
        }
        onComplete()
      }
    } catch (err: any) {
      setError(err.message || 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mfa-setup">
      {step === 'method' && (
        <div>
          <h2>Choose Authentication Method</h2>
          <div className="method-grid">
            {methods.map(method => (
              <button
                key={method.id}
                className="method-card"
                onClick={() => handleMethodSelect(method.id)}
              >
                <span className="method-icon">{method.icon}</span>
                <h3>{method.name}</h3>
                <p>{method.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {step === 'setup' && (
        <div>
          <h2>Setup {methods.find(m => m.id === selectedMethod)?.name}</h2>
          
          {selectedMethod === 'sms' && (
            <div>
              <label>
                Phone Number:
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+1234567890"
                  required
                />
              </label>
            </div>
          )}

          <button onClick={setupMfa} disabled={loading}>
            {loading ? 'Setting up...' : 'Continue'}
          </button>
          <button onClick={onCancel}>Cancel</button>
        </div>
      )}

      {step === 'verify' && (
        <div>
          <h2>Verify Setup</h2>
          
          {selectedMethod === 'totp' && setupData?.qrCodeUrl && (
            <div>
              <p>Scan this QR code with your authenticator app:</p>
              <QRCode value={setupData.qrCodeUrl} />
              <p>Or enter this key manually: <code>{setupData.secret}</code></p>
            </div>
          )}

          {(selectedMethod === 'sms' || selectedMethod === 'email') && (
            <p>
              A verification code has been sent to your{' '}
              {selectedMethod === 'sms' ? 'phone' : 'email'}.
            </p>
          )}

          <label>
            Verification Code:
            <input
              type="text"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              placeholder="123456"
              maxLength={6}
            />
          </label>

          <button onClick={verifySetup} disabled={loading || !verificationCode}>
            {loading ? 'Verifying...' : 'Verify'}
          </button>
          <button onClick={() => setStep('setup')}>Back</button>
        </div>
      )}

      {error && <div className="error">{error}</div>}
    </div>
  )
}
```

#### MFA Challenge Component

```tsx
// components/MfaChallenge.tsx
import React, { useState } from 'react'
import { plinto } from '@plinto/typescript-sdk'

interface MfaChallengeProps {
  sessionId: string
  availableMethods: string[]
  onSuccess: (user: any, session: any) => void
  onCancel: () => void
}

export const MfaChallenge: React.FC<MfaChallengeProps> = ({
  sessionId,
  availableMethods,
  onSuccess,
  onCancel
}) => {
  const [selectedMethod, setSelectedMethod] = useState(availableMethods[0])
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [attemptsRemaining, setAttemptsRemaining] = useState(3)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      setLoading(true)
      setError('')

      const result = await plinto.auth.mfa.challenge({
        sessionId,
        method: selectedMethod,
        code
      })

      if (result.success) {
        onSuccess(result.user, result.session)
      } else {
        setError('Invalid code')
        setAttemptsRemaining(result.attemptsRemaining)
        setCode('')
      }
    } catch (err: any) {
      setError(err.message || 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  const requestNewCode = async () => {
    if (selectedMethod === 'totp') return // TOTP doesn't need new codes

    try {
      await plinto.auth.mfa.requestNewCode({
        sessionId,
        method: selectedMethod
      })
      alert('New code sent!')
    } catch (err: any) {
      setError(err.message || 'Failed to send new code')
    }
  }

  const methodNames = {
    totp: 'Authenticator App',
    sms: 'SMS',
    email: 'Email',
    backup: 'Backup Code'
  }

  return (
    <div className="mfa-challenge">
      <h2>Two-Factor Authentication</h2>
      <p>Please verify your identity to continue.</p>

      <form onSubmit={handleSubmit}>
        {availableMethods.length > 1 && (
          <div className="method-selector">
            <label>Authentication Method:</label>
            <select
              value={selectedMethod}
              onChange={(e) => setSelectedMethod(e.target.value)}
            >
              {availableMethods.map(method => (
                <option key={method} value={method}>
                  {methodNames[method as keyof typeof methodNames] || method}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="code-input">
          <label>
            {selectedMethod === 'totp' 
              ? 'Code from authenticator app:'
              : `Code sent via ${selectedMethod}:`
            }
          </label>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="123456"
            required
            autoComplete="one-time-code"
          />
        </div>

        <div className="actions">
          <button type="submit" disabled={loading || !code}>
            {loading ? 'Verifying...' : 'Verify'}
          </button>
          
          {selectedMethod !== 'totp' && (
            <button type="button" onClick={requestNewCode}>
              Send New Code
            </button>
          )}
          
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>

      {error && (
        <div className="error">
          {error}
          {attemptsRemaining > 0 && (
            <p>{attemptsRemaining} attempts remaining</p>
          )}
        </div>
      )}

      {availableMethods.includes('backup') && (
        <div className="backup-option">
          <p>
            Can't access your device?{' '}
            <button onClick={() => setSelectedMethod('backup')}>
              Use backup code
            </button>
          </p>
        </div>
      )}
    </div>
  )
}
```

#### MFA Settings Component

```tsx
// components/MfaSettings.tsx
import React, { useState, useEffect } from 'react'
import { plinto } from '@plinto/typescript-sdk'
import { MfaSetup } from './MfaSetup'

interface MfaStatus {
  enabled: boolean
  methods: string[]
  backupCodesRemaining: number
  lastUsed?: string
}

export const MfaSettings: React.FC = () => {
  const [mfaStatus, setMfaStatus] = useState<MfaStatus | null>(null)
  const [showSetup, setShowSetup] = useState(false)
  const [showBackupCodes, setShowBackupCodes] = useState(false)
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadMfaStatus()
  }, [])

  const loadMfaStatus = async () => {
    try {
      setLoading(true)
      const status = await plinto.auth.getMFAStatus()
      setMfaStatus(status)
    } catch (err: any) {
      setError(err.message || 'Failed to load MFA status')
    } finally {
      setLoading(false)
    }
  }

  const disableMfa = async () => {
    if (!confirm('Are you sure you want to disable MFA? This will reduce your account security.')) {
      return
    }

    const password = prompt('Enter your password to confirm:')
    if (!password) return

    try {
      await plinto.auth.disableMFA({ password })
      await loadMfaStatus()
      alert('MFA has been disabled')
    } catch (err: any) {
      setError(err.message || 'Failed to disable MFA')
    }
  }

  const regenerateBackupCodes = async () => {
    if (!confirm('This will invalidate your existing backup codes. Continue?')) {
      return
    }

    const password = prompt('Enter your password to confirm:')
    if (!password) return

    try {
      const result = await plinto.auth.regenerateMFABackupCodes({ password })
      setBackupCodes(result.codes)
      setShowBackupCodes(true)
      await loadMfaStatus()
    } catch (err: any) {
      setError(err.message || 'Failed to regenerate backup codes')
    }
  }

  if (loading) {
    return <div>Loading MFA settings...</div>
  }

  if (showSetup) {
    return (
      <MfaSetup
        onComplete={() => {
          setShowSetup(false)
          loadMfaStatus()
        }}
        onCancel={() => setShowSetup(false)}
      />
    )
  }

  return (
    <div className="mfa-settings">
      <h2>Two-Factor Authentication</h2>
      
      {error && <div className="error">{error}</div>}

      {!mfaStatus?.enabled ? (
        <div className="mfa-disabled">
          <h3>🔒 Secure your account</h3>
          <p>
            Two-factor authentication adds an extra layer of security to your account.
            Enable it to protect against unauthorized access.
          </p>
          <button onClick={() => setShowSetup(true)} className="primary">
            Enable Two-Factor Authentication
          </button>
        </div>
      ) : (
        <div className="mfa-enabled">
          <h3>✅ Two-Factor Authentication is enabled</h3>
          
          <div className="mfa-info">
            <p><strong>Active methods:</strong> {mfaStatus.methods.join(', ')}</p>
            <p><strong>Backup codes remaining:</strong> {mfaStatus.backupCodesRemaining}</p>
            {mfaStatus.lastUsed && (
              <p><strong>Last used:</strong> {new Date(mfaStatus.lastUsed).toLocaleString()}</p>
            )}
          </div>

          <div className="mfa-actions">
            <button onClick={regenerateBackupCodes}>
              Generate New Backup Codes
            </button>
            <button onClick={() => setShowSetup(true)}>
              Add Another Method
            </button>
            <button onClick={disableMfa} className="danger">
              Disable MFA
            </button>
          </div>
        </div>
      )}

      {showBackupCodes && (
        <div className="backup-codes-modal">
          <h3>Your New Backup Codes</h3>
          <p>Save these codes in a secure location. You can use each code only once.</p>
          <div className="codes-grid">
            {backupCodes.map((code, index) => (
              <code key={index} className="backup-code">{code}</code>
            ))}
          </div>
          <button onClick={() => setShowBackupCodes(false)}>
            I've saved these codes
          </button>
        </div>
      )}
    </div>
  )
}
```

#### Custom Hook for MFA

```tsx
// hooks/useMfa.ts
import { useState, useEffect, useCallback } from 'react'
import { plinto } from '@plinto/typescript-sdk'

interface MfaState {
  isEnabled: boolean
  methods: string[]
  backupCodesRemaining: number
  lastUsed?: string
}

interface MfaHookReturn {
  mfaState: MfaState | null
  loading: boolean
  error: string | null
  setupMfa: (method: string, options?: any) => Promise<any>
  verifyMfa: (sessionId: string, method: string, code: string) => Promise<any>
  disableMfa: (password: string) => Promise<void>
  regenerateBackupCodes: (password: string) => Promise<string[]>
  refresh: () => Promise<void>
}

export const useMfa = (): MfaHookReturn => {
  const [mfaState, setMfaState] = useState<MfaState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadMfaStatus = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const status = await plinto.auth.getMFAStatus()
      setMfaState({
        isEnabled: status.enabled,
        methods: status.methods,
        backupCodesRemaining: status.backupCodesRemaining,
        lastUsed: status.lastUsed
      })
    } catch (err: any) {
      setError(err.message || 'Failed to load MFA status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMfaStatus()
  }, [loadMfaStatus])

  const setupMfa = useCallback(async (method: string, options: any = {}) => {
    try {
      setError(null)
      const result = await plinto.auth.enableMFA({
        method,
        ...options
      })
      await loadMfaStatus() // Refresh status
      return result
    } catch (err: any) {
      setError(err.message || 'Failed to setup MFA')
      throw err
    }
  }, [loadMfaStatus])

  const verifyMfa = useCallback(async (sessionId: string, method: string, code: string) => {
    try {
      setError(null)
      const result = await plinto.auth.verifyMFA({
        sessionId,
        method,
        code
      })
      return result
    } catch (err: any) {
      setError(err.message || 'Failed to verify MFA')
      throw err
    }
  }, [])

  const disableMfa = useCallback(async (password: string) => {
    try {
      setError(null)
      await plinto.auth.disableMFA({ password })
      await loadMfaStatus()
    } catch (err: any) {
      setError(err.message || 'Failed to disable MFA')
      throw err
    }
  }, [loadMfaStatus])

  const regenerateBackupCodes = useCallback(async (password: string) => {
    try {
      setError(null)
      const result = await plinto.auth.regenerateMFABackupCodes({ password })
      await loadMfaStatus()
      return result.codes
    } catch (err: any) {
      setError(err.message || 'Failed to regenerate backup codes')
      throw err
    }
  }, [loadMfaStatus])

  return {
    mfaState,
    loading,
    error,
    setupMfa,
    verifyMfa,
    disableMfa,
    regenerateBackupCodes,
    refresh: loadMfaStatus
  }
}
```

## Security Best Practices

### Rate Limiting

```typescript
// Rate limiting configuration for MFA endpoints
const mfaRateLimits = {
  setup: {
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 3, // 3 setup attempts per window
    message: 'Too many MFA setup attempts'
  },
  verify: {
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 5, // 5 verification attempts per window
    message: 'Too many MFA verification attempts'
  },
  disable: {
    windowMs: 60 * 60 * 1000, // 1 hour
    max: 2, // 2 disable attempts per hour
    message: 'Too many MFA disable attempts'
  }
}

// Progressive delays for failed attempts
const getVerificationDelay = (failedAttempts: number): number => {
  const baseDelay = 1000 // 1 second
  return Math.min(baseDelay * Math.pow(2, failedAttempts), 30000) // Max 30 seconds
}
```

### Secure Session Management

```typescript
// Enhanced session security with MFA
interface SecureSession {
  id: string
  userId: string
  mfaVerified: boolean
  mfaVerifiedAt: Date
  mfaMethod: string
  requiresReauth: boolean
  securityLevel: 'basic' | 'elevated'
  ipAddress: string
  userAgent: string
}

const createSecureSession = async (
  user: any, 
  mfaMethod?: string
): Promise<SecureSession> => {
  return {
    id: generateSessionId(),
    userId: user.id,
    mfaVerified: !!mfaMethod,
    mfaVerifiedAt: mfaMethod ? new Date() : null,
    mfaMethod: mfaMethod || null,
    requiresReauth: false,
    securityLevel: mfaMethod ? 'elevated' : 'basic',
    ipAddress: getClientIP(),
    userAgent: getUserAgent()
  }
}

// Step-up authentication for sensitive operations
const requireStepUp = async (session: SecureSession, operation: string) => {
  const sensitiveOperations = [
    'password_change',
    'email_change',
    'mfa_disable',
    'account_delete',
    'payment_method_add'
  ]

  if (sensitiveOperations.includes(operation)) {
    const mfaAge = Date.now() - session.mfaVerifiedAt.getTime()
    const maxAge = 10 * 60 * 1000 // 10 minutes

    if (mfaAge > maxAge) {
      throw new Error('Recent MFA verification required')
    }
  }
}
```

### Hardware Token Support

```typescript
// WebAuthn integration for hardware tokens
const setupHardwareToken = async (userId: string) => {
  const challenge = await plinto.auth.getPasskeyRegistrationOptions({
    userId,
    type: 'registration'
  })

  // Client-side WebAuthn registration
  const credential = await navigator.credentials.create({
    publicKey: {
      challenge: new Uint8Array(challenge.challenge),
      rp: { name: 'MyApp', id: 'myapp.com' },
      user: {
        id: new Uint8Array(challenge.userId),
        name: challenge.userEmail,
        displayName: challenge.userDisplayName
      },
      pubKeyCredParams: [{ alg: -7, type: 'public-key' }],
      authenticatorSelection: {
        authenticatorAttachment: 'cross-platform',
        userVerification: 'required'
      },
      timeout: 60000,
      attestation: 'direct'
    }
  })

  // Verify and store credential
  const verification = await plinto.auth.verifyPasskeyRegistration({
    challengeId: challenge.id,
    credential: {
      id: credential.id,
      rawId: Array.from(new Uint8Array(credential.rawId)),
      response: {
        attestationObject: Array.from(new Uint8Array(credential.response.attestationObject)),
        clientDataJSON: Array.from(new Uint8Array(credential.response.clientDataJSON))
      },
      type: credential.type
    }
  })

  return verification
}

const verifyHardwareToken = async (sessionId: string) => {
  const challenge = await plinto.auth.getPasskeyRegistrationOptions({
    sessionId,
    type: 'authentication'
  })

  const assertion = await navigator.credentials.get({
    publicKey: {
      challenge: new Uint8Array(challenge.challenge),
      timeout: 60000,
      userVerification: 'required',
      allowCredentials: challenge.allowCredentials.map(cred => ({
        id: new Uint8Array(cred.id),
        type: 'public-key'
      }))
    }
  })

  const verification = await plinto.auth.verifyPasskeyRegistration({
    challengeId: challenge.id,
    assertion: {
      id: assertion.id,
      rawId: Array.from(new Uint8Array(assertion.rawId)),
      response: {
        authenticatorData: Array.from(new Uint8Array(assertion.response.authenticatorData)),
        clientDataJSON: Array.from(new Uint8Array(assertion.response.clientDataJSON)),
        signature: Array.from(new Uint8Array(assertion.response.signature)),
        userHandle: assertion.response.userHandle ? 
          Array.from(new Uint8Array(assertion.response.userHandle)) : null
      },
      type: assertion.type
    }
  })

  return verification
}
```

## Error Handling

### Common Error Scenarios

```typescript
// MFA-specific error handling
class MfaError extends Error {
  constructor(
    message: string,
    public code: string,
    public context?: any
  ) {
    super(message)
    this.name = 'MfaError'
  }
}

const MfaErrorCodes = {
  SETUP_FAILED: 'mfa_setup_failed',
  INVALID_CODE: 'mfa_invalid_code',
  EXPIRED_CODE: 'mfa_expired_code',
  METHOD_NOT_SUPPORTED: 'mfa_method_not_supported',
  RATE_LIMITED: 'mfa_rate_limited',
  BACKUP_CODE_USED: 'mfa_backup_code_already_used',
  NO_BACKUP_CODES: 'mfa_no_backup_codes_remaining'
}

const handleMfaError = (error: any): MfaError => {
  if (error.code === 'INVALID_TOTP_CODE') {
    return new MfaError(
      'Invalid authenticator code. Please check your authenticator app and try again.',
      MfaErrorCodes.INVALID_CODE,
      { method: 'totp', attemptsRemaining: error.attemptsRemaining }
    )
  }

  if (error.code === 'SMS_DELIVERY_FAILED') {
    return new MfaError(
      'Failed to send SMS code. Please check your phone number and try again.',
      MfaErrorCodes.SETUP_FAILED,
      { method: 'sms', phoneNumber: error.phoneNumber }
    )
  }

  if (error.code === 'RATE_LIMIT_EXCEEDED') {
    return new MfaError(
      `Too many attempts. Please wait ${error.retryAfter} seconds before trying again.`,
      MfaErrorCodes.RATE_LIMITED,
      { retryAfter: error.retryAfter }
    )
  }

  return new MfaError(error.message || 'An unexpected error occurred', 'unknown', error)
}

// Error recovery strategies
const recoverFromMfaError = async (error: MfaError, context: any) => {
  switch (error.code) {
    case MfaErrorCodes.INVALID_CODE:
      // Allow user to try again or switch methods
      return {
        action: 'retry',
        alternativeMethods: context.availableMethods.filter(m => m !== context.currentMethod)
      }

    case MfaErrorCodes.RATE_LIMITED:
      // Show cooldown timer and suggest backup methods
      return {
        action: 'wait',
        retryAfter: error.context.retryAfter,
        fallbackOptions: ['backup_codes', 'admin_unlock']
      }

    case MfaErrorCodes.NO_BACKUP_CODES:
      // Suggest admin recovery or alternative verification
      return {
        action: 'contact_support',
        supportEmail: 'support@myapp.com',
        recoveryOptions: ['admin_verification', 'identity_verification']
      }

    default:
      return {
        action: 'generic_error',
        message: error.message
      }
  }
}
```

### Graceful Degradation

```typescript
// Fallback strategies when MFA services are unavailable
const mfaServiceHealth = {
  sms: 'healthy',
  email: 'healthy',
  totp: 'healthy',
  push: 'degraded'
}

const getMfaFallbackStrategy = (primaryMethod: string, serviceHealth: any) => {
  const fallbackChain = {
    sms: ['email', 'totp', 'backup_codes'],
    email: ['sms', 'totp', 'backup_codes'],
    totp: ['backup_codes', 'sms', 'email'],
    push: ['totp', 'sms', 'email', 'backup_codes']
  }

  return fallbackChain[primaryMethod]?.filter(method => 
    serviceHealth[method] === 'healthy'
  ) || []
}

const handleMfaServiceDegradation = async (error: any, context: any) => {
  // Log service degradation
  console.warn('MFA service degradation:', error)

  // Determine fallback options
  const fallbackMethods = getMfaFallbackStrategy(
    context.primaryMethod, 
    mfaServiceHealth
  )

  if (fallbackMethods.length > 0) {
    return {
      success: false,
      fallbackAvailable: true,
      recommendedMethod: fallbackMethods[0],
      allFallbacks: fallbackMethods,
      message: `${context.primaryMethod} is temporarily unavailable. Try ${fallbackMethods[0]} instead.`
    }
  }

  // Emergency bypass for critical situations (with admin approval)
  if (context.emergencyOverride) {
    await logSecurityEvent('mfa_emergency_bypass', context)
    return {
      success: true,
      bypassUsed: true,
      requiresAdminReview: true
    }
  }

  return {
    success: false,
    fallbackAvailable: false,
    message: 'MFA services are temporarily unavailable. Please contact support.',
    supportContact: 'support@myapp.com'
  }
}
```

## Testing

### Unit Tests

```typescript
// mfa.test.ts
import { describe, it, expect, jest, beforeEach } from '@jest/globals'
import { plinto } from '@plinto/typescript-sdk'

describe('MFA Implementation', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('TOTP Setup', () => {
    it('should generate TOTP secret and QR code', async () => {
      const mockSetup = {
        secret: 'JBSWY3DPEHPK3PXP',
        qrCodeUrl: 'otpauth://totp/MyApp:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=MyApp',
        backupCodes: ['123456', '789012']
      }

      jest.spyOn(plinto.auth.mfa, 'setup').mockResolvedValue(mockSetup)

      const result = await plinto.auth.enableMFA({
        userId: 'user123',
        method: 'totp',
        label: 'MyApp'
      })

      expect(result.secret).toBe('JBSWY3DPEHPK3PXP')
      expect(result.qrCodeUrl).toContain('otpauth://totp/')
      expect(result.backupCodes).toHaveLength(2)
    })

    it('should verify TOTP code correctly', async () => {
      const mockVerification = {
        success: true,
        user: { id: 'user123' },
        session: { token: 'session123' }
      }

      jest.spyOn(plinto.auth.mfa, 'verify').mockResolvedValue(mockVerification)

      const result = await plinto.auth.verifyMFA({
        sessionId: 'session123',
        method: 'totp',
        code: '123456'
      })

      expect(result.success).toBe(true)
      expect(result.session.token).toBe('session123')
    })

    it('should handle invalid TOTP code', async () => {
      const mockVerification = {
        success: false,
        attemptsRemaining: 2,
        error: 'Invalid code'
      }

      jest.spyOn(plinto.auth.mfa, 'verify').mockResolvedValue(mockVerification)

      const result = await plinto.auth.verifyMFA({
        sessionId: 'session123',
        method: 'totp',
        code: 'invalid'
      })

      expect(result.success).toBe(false)
      expect(result.attemptsRemaining).toBe(2)
    })
  })

  describe('SMS MFA', () => {
    it('should setup SMS MFA with phone number', async () => {
      const mockSetup = {
        phoneNumber: '+1234567890',
        codeSent: true,
        expiresIn: 300
      }

      jest.spyOn(plinto.auth.mfa, 'setup').mockResolvedValue(mockSetup)

      const result = await plinto.auth.enableMFA({
        userId: 'user123',
        method: 'sms',
        phoneNumber: '+1234567890'
      })

      expect(result.phoneNumber).toBe('+1234567890')
      expect(result.codeSent).toBe(true)
    })

    it('should handle SMS delivery failure', async () => {
      jest.spyOn(plinto.auth.mfa, 'setup').mockRejectedValue(
        new Error('SMS delivery failed')
      )

      await expect(
        plinto.auth.enableMFA({
          userId: 'user123',
          method: 'sms',
          phoneNumber: 'invalid'
        })
      ).rejects.toThrow('SMS delivery failed')
    })
  })

  describe('Backup Codes', () => {
    it('should generate backup codes', async () => {
      const mockCodes = {
        codes: Array.from({ length: 10 }, (_, i) => 
          Math.random().toString(36).substr(2, 8)
        ),
        generatedAt: new Date()
      }

      jest.spyOn(plinto.auth.mfa, 'generateBackupCodes')
        .mockResolvedValue(mockCodes)

      const result = await plinto.auth.regenerateMFABackupCodes({
        userId: 'user123'
      })

      expect(result.codes).toHaveLength(10)
      expect(result.generatedAt).toBeInstanceOf(Date)
    })

    it('should verify backup code only once', async () => {
      const mockVerifications = [
        { success: true, codeUsed: true },
        { success: false, error: 'Code already used' }
      ]

      jest.spyOn(plinto.auth.mfa, 'verify')
        .mockResolvedValueOnce(mockVerifications[0])
        .mockResolvedValueOnce(mockVerifications[1])

      // First use - should work
      const result1 = await plinto.auth.verifyMFA({
        sessionId: 'session123',
        method: 'backup',
        code: 'backup123'
      })
      expect(result1.success).toBe(true)

      // Second use - should fail
      const result2 = await plinto.auth.verifyMFA({
        sessionId: 'session123',
        method: 'backup',
        code: 'backup123'
      })
      expect(result2.success).toBe(false)
    })
  })

  describe('Rate Limiting', () => {
    it('should enforce rate limits on verification attempts', async () => {
      const mockResponses = [
        { success: false, attemptsRemaining: 4 },
        { success: false, attemptsRemaining: 3 },
        { success: false, attemptsRemaining: 2 },
        { success: false, attemptsRemaining: 1 },
        { success: false, attemptsRemaining: 0, rateLimited: true }
      ]

      jest.spyOn(plinto.auth.mfa, 'verify')
        .mockImplementation((_, index) => 
          Promise.resolve(mockResponses[index] || mockResponses[4])
        )

      // Make 5 failed attempts
      const attempts = []
      for (let i = 0; i < 5; i++) {
        const result = await plinto.auth.verifyMFA({
          sessionId: 'session123',
          method: 'totp',
          code: 'wrong'
        })
        attempts.push(result)
      }

      expect(attempts[4].rateLimited).toBe(true)
      expect(attempts[4].attemptsRemaining).toBe(0)
    })
  })
})
```

### Integration Tests

```typescript
// mfa.integration.test.ts
import { describe, it, expect, beforeAll, afterAll } from '@jest/globals'
import request from 'supertest'
import { app } from '../server'
import { plinto } from '@plinto/typescript-sdk'

describe('MFA Integration Tests', () => {
  let testUser: any
  let authToken: string

  beforeAll(async () => {
    // Create test user
    testUser = await plinto.auth.signUp({
      email: 'mfa-test@example.com',
      password: 'TestPassword123!'
    })
    authToken = testUser.session.token
  })

  afterAll(async () => {
    // Cleanup test user
    await plinto.auth.deleteUser({ userId: testUser.user.id })
  })

  describe('TOTP Flow', () => {
    let totpSecret: string

    it('should setup TOTP MFA', async () => {
      const response = await request(app)
        .post('/api/auth/mfa/setup')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          method: 'totp',
          label: 'Integration Test'
        })

      expect(response.status).toBe(200)
      expect(response.body.success).toBe(true)
      expect(response.body.secret).toBeDefined()
      expect(response.body.qrCodeUrl).toContain('otpauth://')

      totpSecret = response.body.secret
    })

    it('should complete authentication with TOTP', async () => {
      // Generate TOTP code (in real test, use authenticator library)
      const totpCode = generateTotpCode(totpSecret)

      // First, sign in with password
      const signInResponse = await request(app)
        .post('/api/auth/signin')
        .send({
          email: 'mfa-test@example.com',
          password: 'TestPassword123!'
        })

      expect(signInResponse.status).toBe(200)
      expect(signInResponse.body.requiresMfa).toBe(true)

      // Then verify with TOTP
      const mfaResponse = await request(app)
        .post('/api/auth/mfa/verify')
        .send({
          sessionId: signInResponse.body.sessionId,
          method: 'totp',
          code: totpCode
        })

      expect(mfaResponse.status).toBe(200)
      expect(mfaResponse.body.success).toBe(true)
      expect(mfaResponse.body.session.token).toBeDefined()
    })
  })

  describe('SMS Flow', () => {
    it('should setup SMS MFA', async () => {
      const response = await request(app)
        .post('/api/auth/mfa/setup')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          method: 'sms',
          phoneNumber: '+1234567890'
        })

      expect(response.status).toBe(200)
      expect(response.body.success).toBe(true)
    })

    it('should handle SMS verification', async () => {
      // This would typically use a test SMS service
      const mockSmsCode = '123456'

      const response = await request(app)
        .post('/api/auth/mfa/verify')
        .send({
          sessionId: 'test-session-id',
          method: 'sms',
          code: mockSmsCode
        })

      // Response depends on test SMS service configuration
      expect(response.status).toBeOneOf([200, 400])
    })
  })

  describe('Backup Codes', () => {
    it('should generate and use backup codes', async () => {
      // Generate backup codes
      const generateResponse = await request(app)
        .post('/api/auth/mfa/backup-codes/regenerate')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          password: 'TestPassword123!'
        })

      expect(generateResponse.status).toBe(200)
      expect(generateResponse.body.codes).toHaveLength(10)

      const backupCode = generateResponse.body.codes[0]

      // Use backup code for authentication
      const authResponse = await request(app)
        .post('/api/auth/mfa/verify')
        .send({
          sessionId: 'test-session-id',
          method: 'backup',
          code: backupCode
        })

      expect(authResponse.status).toBe(200)
      expect(authResponse.body.success).toBe(true)

      // Try to use the same backup code again (should fail)
      const reusedResponse = await request(app)
        .post('/api/auth/mfa/verify')
        .send({
          sessionId: 'test-session-id-2',
          method: 'backup',
          code: backupCode
        })

      expect(reusedResponse.status).toBe(401)
    })
  })

  describe('Security Features', () => {
    it('should enforce rate limits', async () => {
      const sessionId = 'rate-limit-test-session'
      const promises = []

      // Make 6 concurrent failed attempts
      for (let i = 0; i < 6; i++) {
        promises.push(
          request(app)
            .post('/api/auth/mfa/verify')
            .send({
              sessionId,
              method: 'totp',
              code: 'wrong'
            })
        )
      }

      const responses = await Promise.all(promises)
      
      // At least one should be rate limited
      const rateLimited = responses.some(r => r.status === 429)
      expect(rateLimited).toBe(true)
    })

    it('should require password for disabling MFA', async () => {
      const response = await request(app)
        .post('/api/auth/mfa/disable')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          // Missing password
          confirmationCode: '123456'
        })

      expect(response.status).toBe(400)
    })
  })
})

// Helper function to generate TOTP code
function generateTotpCode(secret: string): string {
  // Implementation would use a TOTP library like 'otplib'
  // This is a placeholder for the actual implementation
  return '123456'
}
```

### End-to-End Tests

```typescript
// mfa.e2e.test.ts
import { test, expect } from '@playwright/test'

test.describe('MFA E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to app and create test user
    await page.goto('/')
    await page.click('text=Sign Up')
    await page.fill('[name="email"]', 'e2e-test@example.com')
    await page.fill('[name="password"]', 'TestPassword123!')
    await page.click('button:has-text("Sign Up")')
    
    // Wait for dashboard
    await expect(page.locator('h1')).toContainText('Dashboard')
  })

  test('should complete TOTP setup flow', async ({ page }) => {
    // Navigate to security settings
    await page.click('text=Settings')
    await page.click('text=Security')
    
    // Start MFA setup
    await page.click('text=Enable Two-Factor Authentication')
    
    // Select authenticator app
    await page.click('text=Authenticator App')
    await page.click('text=Continue')
    
    // QR code should be displayed
    await expect(page.locator('canvas')).toBeVisible() // QR code
    await expect(page.locator('code')).toBeVisible()   // Manual entry key
    
    // Enter verification code (in real test, would scan QR code)
    await page.fill('[name="verificationCode"]', '123456')
    await page.click('text=Verify')
    
    // Should show backup codes
    await expect(page.locator('.backup-codes')).toBeVisible()
    await page.click('text=I\'ve saved these codes')
    
    // Should return to settings with MFA enabled
    await expect(page.locator('text=✅ Two-Factor Authentication is enabled')).toBeVisible()
  })

  test('should require MFA during sign in', async ({ page, context }) => {
    // Setup MFA first (abbreviated)
    await setupMfaForUser(page, 'totp')
    
    // Sign out
    await page.click('text=Sign Out')
    
    // Create new page to simulate new session
    const newPage = await context.newPage()
    await newPage.goto('/')
    
    // Sign in with password
    await newPage.click('text=Sign In')
    await newPage.fill('[name="email"]', 'e2e-test@example.com')
    await newPage.fill('[name="password"]', 'TestPassword123!')
    await newPage.click('button:has-text("Sign In")')
    
    // Should be prompted for MFA
    await expect(newPage.locator('h2')).toContainText('Two-Factor Authentication')
    await expect(newPage.locator('select')).toBeVisible() // Method selector
    
    // Enter TOTP code
    await newPage.fill('[name="code"]', '123456')
    await newPage.click('text=Verify')
    
    // Should be signed in
    await expect(newPage.locator('h1')).toContainText('Dashboard')
  })

  test('should handle backup code authentication', async ({ page, context }) => {
    // Setup MFA and get backup codes
    const backupCodes = await setupMfaWithBackupCodes(page)
    
    // Sign out and in again
    await page.click('text=Sign Out')
    const newPage = await context.newPage()
    await newPage.goto('/')
    
    await newPage.click('text=Sign In')
    await newPage.fill('[name="email"]', 'e2e-test@example.com')
    await newPage.fill('[name="password"]', 'TestPassword123!')
    await newPage.click('button:has-text("Sign In")')
    
    // Switch to backup code method
    await newPage.click('text=Use backup code')
    await expect(newPage.locator('select')).toHaveValue('backup')
    
    // Use backup code
    await newPage.fill('[name="code"]', backupCodes[0])
    await newPage.click('text=Verify')
    
    // Should be signed in
    await expect(newPage.locator('h1')).toContainText('Dashboard')
  })

  test('should handle MFA setup errors gracefully', async ({ page }) => {
    await page.click('text=Settings')
    await page.click('text=Security')
    await page.click('text=Enable Two-Factor Authentication')
    
    // Select SMS method
    await page.click('text=SMS Messages')
    await page.click('text=Continue')
    
    // Enter invalid phone number
    await page.fill('[name="phoneNumber"]', 'invalid')
    await page.click('text=Continue')
    
    // Should show error message
    await expect(page.locator('.error')).toContainText('Invalid phone number')
    
    // Should allow correcting the error
    await page.fill('[name="phoneNumber"]', '+1234567890')
    await page.click('text=Continue')
    
    // Should proceed to verification step
    await expect(page.locator('h2')).toContainText('Verify Setup')
  })

  test('should enforce rate limiting', async ({ page, context }) => {
    await setupMfaForUser(page, 'totp')
    
    // Sign out and attempt sign in
    await page.click('text=Sign Out')
    const newPage = await context.newPage()
    await newPage.goto('/')
    
    await newPage.click('text=Sign In')
    await newPage.fill('[name="email"]', 'e2e-test@example.com')
    await newPage.fill('[name="password"]', 'TestPassword123!')
    await newPage.click('button:has-text("Sign In")')
    
    // Make multiple failed MFA attempts
    for (let i = 0; i < 6; i++) {
      await newPage.fill('[name="code"]', 'wrong')
      await newPage.click('text=Verify')
      
      if (i < 5) {
        await expect(newPage.locator('.error')).toContainText('Invalid code')
      }
    }
    
    // Should be rate limited
    await expect(newPage.locator('.error')).toContainText('Too many attempts')
    
    // Verify button should be disabled
    await expect(newPage.locator('button:has-text("Verify")')).toBeDisabled()
  })
})

// Helper functions
async function setupMfaForUser(page: any, method: string) {
  await page.click('text=Settings')
  await page.click('text=Security')
  await page.click('text=Enable Two-Factor Authentication')
  
  if (method === 'totp') {
    await page.click('text=Authenticator App')
    await page.click('text=Continue')
    await page.fill('[name="verificationCode"]', '123456')
    await page.click('text=Verify')
    await page.click('text=I\'ve saved these codes')
  }
  
  // Navigate back to main page
  await page.click('text=Dashboard')
}

async function setupMfaWithBackupCodes(page: any): Promise<string[]> {
  await setupMfaForUser(page, 'totp')
  
  // Generate new backup codes to capture them
  await page.click('text=Settings')
  await page.click('text=Security')
  await page.click('text=Generate New Backup Codes')
  await page.fill('[name="password"]', 'TestPassword123!')
  await page.click('text=Generate')
  
  // Extract backup codes from the page
  const codes = await page.locator('.backup-code').allTextContents()
  await page.click('text=I\'ve saved these codes')
  
  return codes
}
```

## Migration Guides

### Migrating from Basic Auth to MFA

```typescript
// Step 1: Add MFA fields to user schema
interface User {
  id: string
  email: string
  // Existing fields...
  
  // New MFA fields
  mfaEnabled: boolean
  mfaMethods: string[]
  mfaBackupCodes: string[]
  totpSecret?: string
  phoneNumber?: string
  lastMfaUsed?: Date
}

// Step 2: Create migration script
async function migrateMfaFeatures() {
  console.log('Starting MFA migration...')
  
  // Add new columns to users table
  await plinto.db.query(`
    ALTER TABLE users 
    ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN mfa_methods TEXT[] DEFAULT '{}',
    ADD COLUMN mfa_backup_codes TEXT[] DEFAULT '{}',
    ADD COLUMN totp_secret TEXT,
    ADD COLUMN phone_number TEXT,
    ADD COLUMN last_mfa_used TIMESTAMP
  `)
  
  // Create MFA sessions table
  await plinto.db.query(`
    CREATE TABLE mfa_sessions (
      id VARCHAR(255) PRIMARY KEY,
      user_id VARCHAR(255) REFERENCES users(id),
      challenge_type VARCHAR(50) NOT NULL,
      challenge_data TEXT,
      expires_at TIMESTAMP NOT NULL,
      attempts INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW()
    )
  `)
  
  // Create MFA audit log
  await plinto.db.query(`
    CREATE TABLE mfa_audit_log (
      id SERIAL PRIMARY KEY,
      user_id VARCHAR(255) REFERENCES users(id),
      action VARCHAR(100) NOT NULL,
      method VARCHAR(50),
      success BOOLEAN NOT NULL,
      ip_address INET,
      user_agent TEXT,
      created_at TIMESTAMP DEFAULT NOW()
    )
  `)
  
  console.log('MFA migration completed')
}

// Step 3: Gradual rollout strategy
class MfaRolloutManager {
  private rolloutPercentage: number = 0
  
  async setRolloutPercentage(percentage: number) {
    this.rolloutPercentage = percentage
    await plinto.config.set('mfa_rollout_percentage', percentage)
  }
  
  shouldEnableMfaForUser(user: any): boolean {
    // Hash user ID to get consistent assignment
    const userHash = this.hashUserId(user.id)
    const userPercentile = userHash % 100
    
    return userPercentile < this.rolloutPercentage
  }
  
  async getEligibleUsers(batchSize: number = 1000) {
    return plinto.db.query(`
      SELECT id, email FROM users 
      WHERE mfa_enabled = FALSE 
      LIMIT $1
    `, [batchSize])
  }
  
  private hashUserId(userId: string): number {
    // Simple hash function for consistent user assignment
    let hash = 0
    for (let i = 0; i < userId.length; i++) {
      hash = ((hash << 5) - hash + userId.charCodeAt(i)) & 0xffffffff
    }
    return Math.abs(hash)
  }
}

// Step 4: Backwards compatibility layer
const authenticationMiddleware = async (req: any, res: any, next: any) => {
  try {
    const token = req.headers.authorization?.split(' ')[1]
    const session = await plinto.auth.verifySession(token)
    
    if (!session.valid) {
      return res.status(401).json({ error: 'Invalid session' })
    }
    
    req.user = session.user
    req.session = session
    
    // Check MFA requirements based on route sensitivity
    const routeRequiresMfa = getMfaRequirement(req.path)
    const userHasMfa = session.user.mfaEnabled
    const sessionMfaVerified = session.mfaVerified
    
    if (routeRequiresMfa && userHasMfa && !sessionMfaVerified) {
      return res.status(403).json({
        error: 'MFA required',
        requiresMfa: true,
        sessionId: session.id,
        availableMethods: session.user.mfaMethods
      })
    }
    
    next()
  } catch (error) {
    res.status(401).json({ error: 'Authentication failed' })
  }
}

// Step 5: Data migration utilities
async function migrateUserMfaSettings(userId: string, settings: any) {
  await plinto.db.transaction(async (trx) => {
    // Update user record
    await trx.query(`
      UPDATE users 
      SET mfa_enabled = $1, mfa_methods = $2, phone_number = $3
      WHERE id = $4
    `, [settings.enabled, settings.methods, settings.phoneNumber, userId])
    
    // Migrate existing 2FA data if present
    if (settings.existingTotpSecret) {
      await trx.query(`
        UPDATE users 
        SET totp_secret = $1 
        WHERE id = $2
      `, [settings.existingTotpSecret, userId])
    }
    
    // Generate backup codes
    if (settings.enabled) {
      const backupCodes = generateBackupCodes()
      await trx.query(`
        UPDATE users 
        SET mfa_backup_codes = $1 
        WHERE id = $2
      `, [backupCodes, userId])
    }
  })
}

function getMfaRequirement(path: string): boolean {
  const mfaRequiredPaths = [
    '/api/admin',
    '/api/payments',
    '/api/user/profile/delete',
    '/api/settings/security'
  ]
  
  return mfaRequiredPaths.some(requiredPath => 
    path.startsWith(requiredPath)
  )
}

function generateBackupCodes(count: number = 10): string[] {
  return Array.from({ length: count }, () => 
    Math.random().toString(36).substr(2, 8).toUpperCase()
  )
}
```

### Progressive Enhancement Strategy

```typescript
// Phase 1: Optional MFA (0-25% users)
const MfaPhase = {
  DISABLED: 0,
  OPTIONAL: 1,
  ENCOURAGED: 2,
  REQUIRED_ADMIN: 3,
  REQUIRED_ALL: 4
}

class MfaProgressiveRollout {
  private currentPhase: number = MfaPhase.DISABLED
  
  async advanceToPhase(phase: number) {
    console.log(`Advancing MFA rollout to phase ${phase}`)
    
    switch (phase) {
      case MfaPhase.OPTIONAL:
        await this.enableOptionalMfa()
        break
      case MfaPhase.ENCOURAGED:
        await this.encourageMfaAdoption()
        break
      case MfaPhase.REQUIRED_ADMIN:
        await this.requireMfaForAdmins()
        break
      case MfaPhase.REQUIRED_ALL:
        await this.requireMfaForAllUsers()
        break
    }
    
    this.currentPhase = phase
    await plinto.config.set('mfa_current_phase', phase)
  }
  
  private async enableOptionalMfa() {
    // Phase 1: Make MFA available but not required
    await plinto.config.set('mfa_available', true)
    await this.notifyUsers('mfa_now_available')
    
    // Add MFA setup prompts to dashboard
    await this.addMfaPrompts(['dashboard', 'settings'])
  }
  
  private async encourageMfaAdoption() {
    // Phase 2: Actively encourage MFA adoption
    await this.implementMfaIncentives()
    await this.showMfaReminders()
    await this.sendMfaEducationEmails()
  }
  
  private async requireMfaForAdmins() {
    // Phase 3: Require MFA for admin users
    const adminUsers = await plinto.db.query(
      'SELECT id FROM users WHERE role IN (?, ?)',
      ['admin', 'super_admin']
    )
    
    for (const admin of adminUsers) {
      if (!admin.mfaEnabled) {
        await this.enforceMfaForUser(admin.id)
        await this.notifyUser(admin.id, 'mfa_now_required')
      }
    }
  }
  
  private async requireMfaForAllUsers() {
    // Phase 4: Require MFA for all users (gradual rollout)
    const batchSize = 1000
    let offset = 0
    
    while (true) {
      const users = await plinto.db.query(`
        SELECT id, email FROM users 
        WHERE mfa_enabled = FALSE 
        ORDER BY created_at ASC 
        LIMIT ? OFFSET ?
      `, [batchSize, offset])
      
      if (users.length === 0) break
      
      for (const user of users) {
        await this.enforceMfaForUser(user.id)
        await this.notifyUser(user.id, 'mfa_enforcement_coming')
        
        // Stagger enforcement to avoid overwhelming support
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      offset += batchSize
      
      // Monitor support ticket volume and adjust pace
      const supportLoad = await this.getSupportTicketVolume()
      if (supportLoad > 50) {
        await new Promise(resolve => setTimeout(resolve, 60000)) // Wait 1 minute
      }
    }
  }
  
  private async enforceMfaForUser(userId: string) {
    // Set MFA requirement flag
    await plinto.db.query(`
      UPDATE users 
      SET mfa_required = TRUE, mfa_deadline = ? 
      WHERE id = ?
    `, [new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), userId]) // 30 days
  }
  
  private async addMfaPrompts(locations: string[]) {
    // Add in-app prompts encouraging MFA setup
    await plinto.config.set('mfa_prompt_locations', locations)
  }
  
  private async implementMfaIncentives() {
    // Offer incentives for early MFA adoption
    const incentives = {
      extended_session_duration: true,
      priority_support: true,
      beta_feature_access: true
    }
    
    await plinto.config.set('mfa_incentives', incentives)
  }
  
  private async getSupportTicketVolume(): Promise<number> {
    const result = await plinto.db.query(`
      SELECT COUNT(*) as count 
      FROM support_tickets 
      WHERE created_at > ? AND tags LIKE '%mfa%'
    `, [new Date(Date.now() - 24 * 60 * 60 * 1000)])
    
    return result[0].count
  }
}

// Usage
const rollout = new MfaProgressiveRollout()

// Week 1: Enable optional MFA
await rollout.advanceToPhase(MfaPhase.OPTIONAL)

// Week 4: Encourage adoption
await rollout.advanceToPhase(MfaPhase.ENCOURAGED)

// Week 8: Require for admins
await rollout.advanceToPhase(MfaPhase.REQUIRED_ADMIN)

// Week 12: Require for all users
await rollout.advanceToPhase(MfaPhase.REQUIRED_ALL)
```

## API Reference

### Core MFA Methods

#### `plinto.auth.enableMFA(options)`

Setup MFA for a user.

**Parameters:**
- `userId` (string): User ID
- `method` (string): MFA method ('totp', 'sms', 'email')
- `phoneNumber` (string, optional): Required for SMS method
- `label` (string, optional): Label for TOTP apps (default: app name)

**Returns:**
```typescript
{
  success: boolean
  secret?: string          // TOTP secret
  qrCodeUrl?: string      // TOTP QR code URL
  backupCodes?: string[]  // Generated backup codes
  challengeId?: string    // For SMS/email verification
  expiresIn?: number      // Challenge expiration (seconds)
}
```

**Example:**
```typescript
const result = await plinto.auth.enableMFA({
  userId: 'user123',
  method: 'totp',
  label: 'MyApp Account'
})
```

#### `plinto.auth.verifyMFA(options)`

Verify MFA code during authentication or setup.

**Parameters:**
- `sessionId` (string): Session ID from sign-in
- `method` (string): MFA method used
- `code` (string): Verification code
- `challengeId` (string, optional): For setup verification

**Returns:**
```typescript
{
  success: boolean
  user?: object           // User object if successful
  session?: object        // Session object if successful
  attemptsRemaining?: number
  rateLimited?: boolean
  error?: string
}
```

#### `plinto.auth.getMFAStatus(options)`

Get MFA status for a user.

**Parameters:**
- `userId` (string): User ID

**Returns:**
```typescript
{
  enabled: boolean
  methods: string[]       // Active MFA methods
  backupCodesRemaining: number
  lastUsed?: string      // ISO date string
  setupDate?: string     // ISO date string
}
```

#### `plinto.auth.disableMFA(options)`

Disable MFA for a user.

**Parameters:**
- `userId` (string): User ID
- `password` (string): User's current password
- `confirmationCode` (string): MFA code for verification

**Returns:**
```typescript
{
  success: boolean
  disabledAt: string     // ISO date string
}
```

#### `plinto.auth.regenerateMFABackupCodes(options)`

Generate new backup codes for a user.

**Parameters:**
- `userId` (string): User ID
- `count` (number, optional): Number of codes to generate (default: 10)

**Returns:**
```typescript
{
  codes: string[]        // Array of backup codes
  generatedAt: string    // ISO date string
}
```

### Advanced MFA Methods

#### `plinto.auth.getPasskeyRegistrationOptions(options)`

Generate WebAuthn challenge for hardware token registration or authentication.

**Parameters:**
- `userId` (string): User ID
- `type` ('registration' | 'authentication'): Challenge type
- `sessionId` (string, optional): Required for authentication type

**Returns:**
```typescript
{
  challenge: ArrayBuffer
  challengeId: string
  timeout: number
  userInfo?: {           // Only for registration
    id: ArrayBuffer
    name: string
    displayName: string
  }
  allowCredentials?: Array<{  // Only for authentication
    id: ArrayBuffer
    type: string
  }>
}
```

#### `plinto.auth.verifyPasskeyRegistration(options)`

Verify WebAuthn credential.

**Parameters:**
- `challengeId` (string): Challenge ID from generateChallenge
- `credential` (object): WebAuthn credential response
- `type` ('registration' | 'authentication'): Verification type

**Returns:**
```typescript
{
  success: boolean
  credentialId?: string  // For registration
  user?: object         // For authentication
  session?: object      // For authentication
}
```

#### `plinto.auth.mfa.requestNewCode(options)`

Request a new verification code for SMS or email methods.

**Parameters:**
- `sessionId` (string): Session ID
- `method` ('sms' | 'email'): Method to send new code

**Returns:**
```typescript
{
  success: boolean
  expiresIn: number     // Seconds until expiration
  attemptsRemaining: number
}
```

### Configuration Methods

#### `plinto.auth.mfa.configure(options)`

Configure global MFA settings.

**Parameters:**
```typescript
{
  methods: {
    totp: {
      enabled: boolean
      issuer: string
      algorithm: 'SHA1' | 'SHA256' | 'SHA512'
      digits: 6 | 8
      period: number      // Seconds
    }
    sms: {
      enabled: boolean
      provider: 'twilio' | 'aws-sns'
      rateLimits: {
        perMinute: number
        perHour: number
        perDay: number
      }
    }
    email: {
      enabled: boolean
      rateLimits: {
        perMinute: number
        perHour: number
        perDay: number
      }
    }
    webauthn: {
      enabled: boolean
      rpId: string
      rpName: string
      requireResidentKey: boolean
      userVerification: 'required' | 'preferred' | 'discouraged'
    }
  }
  backupCodes: {
    enabled: boolean
    count: number
    length: number
    algorithm: 'alphanumeric' | 'numeric'
  }
  rateLimiting: {
    maxAttempts: number
    windowMinutes: number
    lockoutMinutes: number
  }
  security: {
    requireForAdmins: boolean
    gracePeriodDays: number
    stepUpRequired: string[]  // Operations requiring recent MFA
  }
}
```

**Returns:**
```typescript
{
  success: boolean
  appliedAt: string    // ISO date string
}
```

This comprehensive MFA guide provides everything needed to implement secure multi-factor authentication with Plinto, from basic setup to advanced security features and testing strategies.