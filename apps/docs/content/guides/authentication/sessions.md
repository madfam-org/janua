# Session Management

Comprehensive user session handling with JWT tokens, refresh tokens, and device management.

## Overview

Plinto provides robust session management with JWT-based authentication, automatic token refresh, device tracking, and comprehensive security controls. Sessions can be managed across multiple devices with granular control over timeout policies and security constraints.

## Quick Start

### 1. Create Session After Authentication

```typescript
import { plinto } from '@plinto/typescript-sdk'

// After successful authentication
const { user, session } = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'userPassword',
  deviceInfo: {
    name: 'Chrome on MacBook',
    type: 'web',
    fingerprint: 'unique-device-id'
  }
})

// Session contains access and refresh tokens
console.log('Access token:', session.accessToken)
console.log('Refresh token:', session.refreshToken)
console.log('Expires at:', session.expiresAt)
```

### 2. Verify Session

```typescript
// Verify current session
const currentSession = await plinto.auth.verifySession({
  token: accessToken
})

if (currentSession.valid) {
  console.log('User:', currentSession.user)
  console.log('Expires in:', currentSession.expiresIn)
} else {
  // Token expired or invalid, try refresh
  await refreshSession()
}
```

### 3. Refresh Tokens

```typescript
// Refresh expired access token
const { accessToken, refreshToken, expiresAt } = await plinto.auth.refreshToken({
  refreshToken: currentRefreshToken
})

// Update stored tokens
localStorage.setItem('accessToken', accessToken)
if (refreshToken) { // New refresh token provided
  localStorage.setItem('refreshToken', refreshToken)
}
```

### 4. Manage User Sessions

```typescript
// Get all user sessions
const sessions = await plinto.auth.sessions.list({
  userId: currentUser.id
})

sessions.forEach(session => {
  console.log(`Device: ${session.device.name}`)
  console.log(`Location: ${session.location}`)
  console.log(`Last active: ${session.lastActiveAt}`)
  console.log(`Current: ${session.isCurrent}`)
})

// Revoke specific session
await plinto.auth.sessions.revoke({
  sessionId: 'session-id-to-revoke'
})

// Revoke all other sessions (keep current)
await plinto.auth.sessions.revokeAll({
  userId: currentUser.id,
  exceptCurrent: true
})
```

## Implementation Guide

### Backend Setup

#### Express.js Implementation

```javascript
const express = require('express')
const jwt = require('jsonwebtoken')
const { Plinto } = require('@plinto/typescript-sdk')

const app = express()
const plinto = new Plinto({
  apiKey: process.env.PLINTO_API_KEY,
  session: {
    accessTokenTTL: 15 * 60, // 15 minutes
    refreshTokenTTL: 30 * 24 * 60 * 60, // 30 days
    algorithm: 'RS256',
    issuer: 'your-app.com',
    audience: 'your-app-users'
  }
})

// Session verification middleware
const verifySession = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization
    const token = authHeader && authHeader.split(' ')[1] // Bearer TOKEN

    if (!token) {
      return res.status(401).json({ error: 'No token provided' })
    }

    const sessionInfo = await plinto.auth.verifySession({
      token,
      ipAddress: req.ip,
      userAgent: req.headers['user-agent']
    })

    if (!sessionInfo.valid) {
      return res.status(401).json({
        error: 'Invalid session',
        code: sessionInfo.reason // expired, revoked, invalid
      })
    }

    // Update last activity
    await plinto.auth.sessions.updateActivity({
      sessionId: sessionInfo.sessionId,
      ipAddress: req.ip,
      userAgent: req.headers['user-agent']
    })

    req.user = sessionInfo.user
    req.sessionId = sessionInfo.sessionId
    next()
  } catch (error) {
    res.status(401).json({ error: 'Session verification failed' })
  }
}

// Create session after successful authentication
app.post('/auth/signin', async (req, res) => {
  const { email, password, rememberMe, deviceInfo } = req.body

  try {
    const { user, session } = await plinto.auth.signIn({
      email,
      password,
      deviceInfo: {
        name: deviceInfo?.name || 'Unknown Device',
        type: deviceInfo?.type || 'web',
        fingerprint: deviceInfo?.fingerprint,
        ip: req.ip,
        userAgent: req.headers['user-agent']
      },
      sessionOptions: {
        rememberMe,
        maxAge: rememberMe ? 30 * 24 * 60 * 60 : undefined, // 30 days if remembered
        securityLevel: 'standard' // standard, high, maximum
      }
    })

    // Set secure HTTP-only cookies for web clients
    const cookieOptions = {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: rememberMe ? 30 * 24 * 60 * 60 * 1000 : undefined
    }

    res.cookie('accessToken', session.accessToken, {
      ...cookieOptions,
      maxAge: 15 * 60 * 1000 // 15 minutes
    })

    res.cookie('refreshToken', session.refreshToken, cookieOptions)

    // Log session creation
    await plinto.audit.log({
      event: 'session.created',
      userId: user.id,
      sessionId: session.id,
      deviceInfo,
      ipAddress: req.ip
    })

    res.json({
      user: {
        id: user.id,
        email: user.email,
        name: user.name
      },
      session: {
        id: session.id,
        expiresAt: session.expiresAt,
        device: session.device
      }
    })
  } catch (error) {
    res.status(401).json({ error: error.message })
  }
})

// Refresh token endpoint
app.post('/auth/refresh', async (req, res) => {
  try {
    const refreshToken = req.cookies.refreshToken || req.body.refreshToken

    if (!refreshToken) {
      return res.status(401).json({ error: 'No refresh token provided' })
    }

    const {
      accessToken,
      refreshToken: newRefreshToken,
      expiresAt,
      user
    } = await plinto.auth.refreshToken({
      refreshToken,
      deviceInfo: {
        ip: req.ip,
        userAgent: req.headers['user-agent']
      }
    })

    // Update cookies
    res.cookie('accessToken', accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 15 * 60 * 1000
    })

    if (newRefreshToken) {
      res.cookie('refreshToken', newRefreshToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 30 * 24 * 60 * 60 * 1000
      })
    }

    res.json({
      accessToken,
      expiresAt,
      user: {
        id: user.id,
        email: user.email,
        name: user.name
      }
    })
  } catch (error) {
    // Clear invalid refresh token
    res.clearCookie('refreshToken')
    res.status(401).json({ error: 'Invalid refresh token' })
  }
})

// Get user sessions
app.get('/auth/sessions', verifySession, async (req, res) => {
  try {
    const sessions = await plinto.auth.sessions.list({
      userId: req.user.id,
      includeExpired: false
    })

    const sessionData = sessions.map(session => ({
      id: session.id,
      device: {
        name: session.device.name,
        type: session.device.type,
        os: session.device.os,
        browser: session.device.browser
      },
      location: {
        country: session.location.country,
        region: session.location.region,
        city: session.location.city
      },
      createdAt: session.createdAt,
      lastActiveAt: session.lastActiveAt,
      expiresAt: session.expiresAt,
      isCurrent: session.id === req.sessionId,
      ipAddress: session.maskedIpAddress // Masked for privacy
    }))

    res.json({ sessions: sessionData })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Revoke session
app.delete('/auth/sessions/:sessionId', verifySession, async (req, res) => {
  try {
    const { sessionId } = req.params

    // Verify user owns the session or is revoking their own current session
    const session = await plinto.auth.sessions.get(sessionId)

    if (session.userId !== req.user.id) {
      return res.status(403).json({ error: 'Cannot revoke other user\'s session' })
    }

    await plinto.auth.sessions.revoke({
      sessionId,
      reason: 'user_requested'
    })

    // Log session revocation
    await plinto.audit.log({
      event: 'session.revoked',
      userId: req.user.id,
      sessionId,
      reason: 'user_requested'
    })

    res.json({ success: true })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Revoke all sessions except current
app.post('/auth/sessions/revoke-all', verifySession, async (req, res) => {
  try {
    const revokedCount = await plinto.auth.sessions.revokeAll({
      userId: req.user.id,
      exceptSessionId: req.sessionId,
      reason: 'user_requested_revoke_all'
    })

    // Log bulk revocation
    await plinto.audit.log({
      event: 'sessions.revoked_all',
      userId: req.user.id,
      revokedCount,
      keptSessionId: req.sessionId
    })

    res.json({
      success: true,
      revokedCount,
      message: `${revokedCount} sessions revoked`
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Sign out (revoke current session)
app.post('/auth/signout', verifySession, async (req, res) => {
  try {
    await plinto.auth.sessions.revoke({
      sessionId: req.sessionId,
      reason: 'user_signout'
    })

    // Clear cookies
    res.clearCookie('accessToken')
    res.clearCookie('refreshToken')

    // Log sign out
    await plinto.audit.log({
      event: 'session.ended',
      userId: req.user.id,
      sessionId: req.sessionId,
      reason: 'user_signout'
    })

    res.json({ success: true })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Session health check
app.get('/auth/session/health', verifySession, async (req, res) => {
  try {
    const health = await plinto.auth.sessions.getHealth({
      sessionId: req.sessionId
    })

    res.json({
      sessionId: req.sessionId,
      userId: req.user.id,
      isValid: true,
      expiresAt: health.expiresAt,
      expiresIn: health.expiresIn,
      lastActivity: health.lastActivity,
      securityLevel: health.securityLevel,
      deviceTrust: health.deviceTrust
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Update session security level
app.put('/auth/session/security', verifySession, async (req, res) => {
  const { level } = req.body // standard, high, maximum

  try {
    const updatedSession = await plinto.auth.sessions.updateSecurity({
      sessionId: req.sessionId,
      securityLevel: level,
      requireMfa: level === 'maximum'
    })

    res.json({
      sessionId: req.sessionId,
      securityLevel: updatedSession.securityLevel,
      expiresAt: updatedSession.expiresAt // May change based on security level
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})
```

#### Python FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.security import HTTPBearer
from plinto import Plinto
import os
from datetime import datetime, timedelta

app = FastAPI()
plinto = Plinto(
    api_key=os.getenv("PLINTO_API_KEY"),
    session={
        "access_token_ttl": 900,  # 15 minutes
        "refresh_token_ttl": 2592000,  # 30 days
        "algorithm": "RS256",
        "issuer": "your-app.com"
    }
)
security = HTTPBearer()

async def verify_session(request: Request):
    """Session verification dependency"""
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header:
            raise HTTPException(401, "No token provided")

        token = auth_header.split(" ")[1] if " " in auth_header else None
        if not token:
            raise HTTPException(401, "Invalid token format")

        session_info = await plinto.auth.verify_session(
            token=token,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )

        if not session_info.valid:
            raise HTTPException(401, f"Invalid session: {session_info.reason}")

        # Update last activity
        await plinto.auth.sessions.update_activity(
            session_id=session_info.session_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )

        return {
            "user": session_info.user,
            "session_id": session_info.session_id
        }
    except Exception as e:
        raise HTTPException(401, f"Session verification failed: {str(e)}")

@app.post("/auth/signin")
async def signin(
    email: str,
    password: str,
    remember_me: bool = False,
    device_info: dict = None,
    request: Request = None,
    response: Response = None
):
    try:
        result = await plinto.auth.sign_in(
            email=email,
            password=password,
            device_info={
                "name": device_info.get("name", "Unknown Device") if device_info else "Unknown Device",
                "type": device_info.get("type", "web") if device_info else "web",
                "fingerprint": device_info.get("fingerprint") if device_info else None,
                "ip": request.client.host,
                "user_agent": request.headers.get("user-agent")
            },
            session_options={
                "remember_me": remember_me,
                "max_age": 30 * 24 * 60 * 60 if remember_me else None,
                "security_level": "standard"
            }
        )

        # Set secure cookies
        cookie_options = {
            "httponly": True,
            "secure": os.getenv("NODE_ENV") == "production",
            "samesite": "lax"
        }

        response.set_cookie(
            "accessToken",
            result.session.access_token,
            max_age=900,  # 15 minutes
            **cookie_options
        )

        response.set_cookie(
            "refreshToken",
            result.session.refresh_token,
            max_age=30 * 24 * 60 * 60 if remember_me else None,
            **cookie_options
        )

        # Log session creation
        await plinto.audit.log(
            event="session.created",
            user_id=result.user.id,
            session_id=result.session.id,
            device_info=device_info,
            ip_address=request.client.host
        )

        return {
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "name": result.user.name
            },
            "session": {
                "id": result.session.id,
                "expires_at": result.session.expires_at,
                "device": result.session.device
            }
        }
    except Exception as e:
        raise HTTPException(401, str(e))

@app.post("/auth/refresh")
async def refresh_token(
    refresh_token: str = None,
    request: Request = None,
    response: Response = None
):
    try:
        # Get refresh token from cookie or body
        if not refresh_token:
            refresh_token = request.cookies.get("refreshToken")

        if not refresh_token:
            raise HTTPException(401, "No refresh token provided")

        result = await plinto.auth.refresh_token(
            refresh_token=refresh_token,
            device_info={
                "ip": request.client.host,
                "user_agent": request.headers.get("user-agent")
            }
        )

        # Update cookies
        response.set_cookie(
            "accessToken",
            result.access_token,
            max_age=900,
            httponly=True,
            secure=os.getenv("NODE_ENV") == "production",
            samesite="lax"
        )

        if result.refresh_token:  # New refresh token provided
            response.set_cookie(
                "refreshToken",
                result.refresh_token,
                max_age=30 * 24 * 60 * 60,
                httponly=True,
                secure=os.getenv("NODE_ENV") == "production",
                samesite="lax"
            )

        return {
            "access_token": result.access_token,
            "expires_at": result.expires_at,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "name": result.user.name
            }
        }
    except Exception as e:
        # Clear invalid refresh token
        response.delete_cookie("refreshToken")
        raise HTTPException(401, "Invalid refresh token")

@app.get("/auth/sessions")
async def list_sessions(session_info = Depends(verify_session)):
    try:
        sessions = await plinto.auth.sessions.list(
            user_id=session_info["user"].id,
            include_expired=False
        )

        session_data = []
        for session in sessions:
            session_data.append({
                "id": session.id,
                "device": {
                    "name": session.device.name,
                    "type": session.device.type,
                    "os": session.device.os,
                    "browser": session.device.browser
                },
                "location": {
                    "country": session.location.country,
                    "region": session.location.region,
                    "city": session.location.city
                },
                "created_at": session.created_at,
                "last_active_at": session.last_active_at,
                "expires_at": session.expires_at,
                "is_current": session.id == session_info["session_id"],
                "ip_address": session.masked_ip_address
            })

        return {"sessions": session_data}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.delete("/auth/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    session_info = Depends(verify_session)
):
    try:
        # Verify ownership
        session = await plinto.auth.sessions.get(session_id)
        if session.user_id != session_info["user"].id:
            raise HTTPException(403, "Cannot revoke other user's session")

        await plinto.auth.sessions.revoke(
            session_id=session_id,
            reason="user_requested"
        )

        # Log revocation
        await plinto.audit.log(
            event="session.revoked",
            user_id=session_info["user"].id,
            session_id=session_id,
            reason="user_requested"
        )

        return {"success": True}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/auth/signout")
async def signout(
    session_info = Depends(verify_session),
    response: Response = None
):
    try:
        await plinto.auth.sessions.revoke(
            session_id=session_info["session_id"],
            reason="user_signout"
        )

        # Clear cookies
        response.delete_cookie("accessToken")
        response.delete_cookie("refreshToken")

        # Log sign out
        await plinto.audit.log(
            event="session.ended",
            user_id=session_info["user"].id,
            session_id=session_info["session_id"],
            reason="user_signout"
        )

        return {"success": True}
    except Exception as e:
        raise HTTPException(400, str(e))
```

### Frontend Implementation

#### React Session Hook

```jsx
import { createContext, useContext, useEffect, useState } from 'react'
import { usePlinto } from '@plinto/react-sdk'

const SessionContext = createContext()

export function SessionProvider({ children }) {
  const { auth } = usePlinto()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!session?.expiresAt) return

    const expiresAt = new Date(session.expiresAt)
    const now = new Date()
    const msUntilExpiry = expiresAt.getTime() - now.getTime()

    // Refresh 2 minutes before expiry
    const refreshAt = msUntilExpiry - 2 * 60 * 1000

    if (refreshAt > 0) {
      const timeout = setTimeout(() => {
        refreshSession()
      }, refreshAt)

      return () => clearTimeout(timeout)
    }
  }, [session?.expiresAt])

  // Check for existing session on load
  useEffect(() => {
    checkExistingSession()
  }, [])

  const checkExistingSession = async () => {
    setLoading(true)
    try {
      const sessionInfo = await auth.verifySession()
      if (sessionInfo.valid) {
        setSession({
          user: sessionInfo.user,
          sessionId: sessionInfo.sessionId,
          expiresAt: sessionInfo.expiresAt
        })
      }
    } catch (error) {
      // No valid session
      console.log('No existing session found')
    } finally {
      setLoading(false)
    }
  }

  const refreshSession = async () => {
    setRefreshing(true)
    try {
      const refreshed = await auth.refreshToken()
      setSession({
        user: refreshed.user,
        sessionId: refreshed.sessionId,
        expiresAt: refreshed.expiresAt
      })
      return true
    } catch (error) {
      // Refresh failed, user needs to sign in again
      setSession(null)
      return false
    } finally {
      setRefreshing(false)
    }
  }

  const signIn = async (credentials) => {
    const result = await auth.signIn(credentials)
    setSession({
      user: result.user,
      sessionId: result.session.id,
      expiresAt: result.session.expiresAt
    })
    return result
  }

  const signOut = async () => {
    try {
      await auth.signOut()
    } catch (error) {
      console.error('Sign out error:', error)
    } finally {
      setSession(null)
    }
  }

  const value = {
    session,
    loading,
    refreshing,
    signIn,
    signOut,
    refreshSession,
    isAuthenticated: !!session
  }

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession must be used within SessionProvider')
  }
  return context
}

// Session management component
function SessionManager() {
  const { auth } = usePlinto()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const { sessions } = await auth.sessions.list()
      setSessions(sessions)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const revokeSession = async (sessionId) => {
    try {
      await auth.sessions.revoke(sessionId)
      setSessions(sessions.filter(s => s.id !== sessionId))
    } catch (error) {
      console.error('Failed to revoke session:', error)
    }
  }

  const revokeAllOthers = async () => {
    if (!confirm('This will sign you out of all other devices. Continue?')) {
      return
    }

    try {
      const { revokedCount } = await auth.sessions.revokeAll()
      await loadSessions() // Reload to show current state
      alert(`Signed out of ${revokedCount} other sessions`)
    } catch (error) {
      console.error('Failed to revoke sessions:', error)
    }
  }

  const formatLastActive = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
    return `${Math.floor(diffMins / 1440)}d ago`
  }

  if (loading) return <div>Loading sessions...</div>

  return (
    <div className="session-manager">
      <div className="session-header">
        <h2>Active Sessions</h2>
        <button onClick={revokeAllOthers} className="revoke-all-button">
          Sign Out Other Sessions
        </button>
      </div>

      <div className="sessions-list">
        {sessions.map(session => (
          <div key={session.id} className={`session-item ${session.isCurrent ? 'current' : ''}`}>
            <div className="session-info">
              <div className="device-info">
                <strong>{session.device.name}</strong>
                {session.isCurrent && <span className="current-badge">Current</span>}
              </div>

              <div className="session-details">
                <span className="location">
                  {session.location.city}, {session.location.country}
                </span>
                <span className="last-active">
                  Last active: {formatLastActive(session.lastActiveAt)}
                </span>
                <span className="ip-address">
                  IP: {session.ipAddress}
                </span>
              </div>
            </div>

            {!session.isCurrent && (
              <button
                onClick={() => revokeSession(session.id)}
                className="revoke-button"
              >
                Sign Out
              </button>
            )}
          </div>
        ))}
      </div>

      {sessions.length === 0 && (
        <div className="no-sessions">
          No active sessions found.
        </div>
      )}
    </div>
  )
}
```

#### Next.js Session Middleware

```typescript
// middleware.ts
import { NextRequest, NextResponse } from 'next/server'
import { Plinto } from '@plinto/typescript-sdk'

const plinto = new Plinto({
  apiKey: process.env.PLINTO_API_KEY!
})

export async function middleware(request: NextRequest) {
  // Check if route requires authentication
  if (request.nextUrl.pathname.startsWith('/dashboard') ||
      request.nextUrl.pathname.startsWith('/api/protected')) {

    const accessToken = request.cookies.get('accessToken')?.value
    const refreshToken = request.cookies.get('refreshToken')?.value

    if (!accessToken) {
      if (refreshToken) {
        // Try to refresh token
        try {
          const refreshed = await plinto.auth.refreshToken({
            refreshToken
          })

          const response = NextResponse.next()

          response.cookies.set('accessToken', refreshed.accessToken, {
            httpOnly: true,
            secure: true,
            sameSite: 'lax',
            maxAge: 15 * 60 // 15 minutes
          })

          if (refreshed.refreshToken) {
            response.cookies.set('refreshToken', refreshed.refreshToken, {
              httpOnly: true,
              secure: true,
              sameSite: 'lax',
              maxAge: 30 * 24 * 60 * 60 // 30 days
            })
          }

          return response
        } catch (error) {
          // Refresh failed, redirect to login
          return NextResponse.redirect(new URL('/login', request.url))
        }
      } else {
        // No tokens, redirect to login
        return NextResponse.redirect(new URL('/login', request.url))
      }
    }

    // Verify access token
    try {
      const sessionInfo = await plinto.auth.verifySession({
        token: accessToken,
        ipAddress: request.ip,
        userAgent: request.headers.get('user-agent')
      })

      if (!sessionInfo.valid) {
        // Token invalid, try refresh
        if (refreshToken) {
          const refreshed = await plinto.auth.refreshToken({ refreshToken })

          const response = NextResponse.next()
          response.cookies.set('accessToken', refreshed.accessToken, {
            httpOnly: true,
            secure: true,
            sameSite: 'lax',
            maxAge: 15 * 60
          })

          return response
        } else {
          return NextResponse.redirect(new URL('/login', request.url))
        }
      }

      // Session valid, continue
      return NextResponse.next()
    } catch (error) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/api/protected/:path*']
}
```

## Advanced Features

### Session Security Levels

Configure different security levels for sessions:

```typescript
// Security levels
const securityLevels = {
  standard: {
    accessTokenTTL: 15 * 60, // 15 minutes
    refreshTokenTTL: 30 * 24 * 60 * 60, // 30 days
    ipValidation: false,
    deviceFingerprinting: false,
    requireMfa: false
  },
  high: {
    accessTokenTTL: 5 * 60, // 5 minutes
    refreshTokenTTL: 7 * 24 * 60 * 60, // 7 days
    ipValidation: true,
    deviceFingerprinting: true,
    requireMfa: false
  },
  maximum: {
    accessTokenTTL: 2 * 60, // 2 minutes
    refreshTokenTTL: 24 * 60 * 60, // 1 day
    ipValidation: true,
    deviceFingerprinting: true,
    requireMfa: true,
    stepUpRequired: 5 * 60 // Require re-auth every 5 minutes
  }
}

// Set session security level
await plinto.auth.sessions.updateSecurity({
  sessionId,
  securityLevel: 'high',
  reason: 'admin_role_detected'
})
```

### Device Trust Management

Track and manage trusted devices:

```typescript
// Check device trust
const deviceTrust = await plinto.auth.devices.checkTrust({
  userId,
  deviceFingerprint: 'unique-device-id',
  ipAddress: req.ip
})

if (!deviceTrust.trusted) {
  // New or untrusted device
  await plinto.auth.mfa.requireVerification({
    userId,
    reason: 'new_device',
    methods: ['totp', 'sms']
  })
}

// Trust device after successful verification
await plinto.auth.devices.trust({
  userId,
  deviceFingerprint: 'unique-device-id',
  deviceInfo: {
    name: 'Chrome on iPhone',
    type: 'mobile',
    os: 'iOS 15.0'
  },
  trustDuration: 30 * 24 * 60 * 60 * 1000 // 30 days
})
```

### Session Analytics

Track session patterns and detect anomalies:

```typescript
// Get session analytics
const analytics = await plinto.auth.sessions.getAnalytics({
  userId,
  timeRange: {
    start: new Date('2024-01-01'),
    end: new Date('2024-12-31')
  }
})

console.log('Session patterns:', {
  totalSessions: analytics.totalSessions,
  averageDuration: analytics.averageDuration,
  uniqueDevices: analytics.uniqueDevices,
  topLocations: analytics.topLocations,
  suspiciousActivity: analytics.suspiciousActivity
})

// Detect anomalies
const anomalies = await plinto.auth.sessions.detectAnomalies({
  userId,
  currentSession: {
    ipAddress: req.ip,
    location: req.geoLocation,
    device: req.deviceFingerprint
  }
})

if (anomalies.riskScore > 0.7) {
  // High risk session
  await plinto.auth.sessions.requireVerification({
    sessionId,
    method: 'mfa',
    reason: 'anomaly_detected'
  })
}
```

## Security Best Practices

### 1. Token Security

```typescript
{
  // JWT Configuration
  algorithm: 'RS256', // Use asymmetric algorithm
  keyRotation: 24 * 60 * 60 * 1000, // Rotate keys daily

  // Token claims
  issuer: 'your-app.com',
  audience: 'your-app-users',

  // Security headers
  securityHeaders: {
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
  }
}
```

### 2. Cookie Security

```typescript
{
  httpOnly: true, // Prevent XSS access
  secure: true, // HTTPS only
  sameSite: 'lax', // CSRF protection
  domain: '.yourapp.com', // Scope appropriately
  path: '/', // Available site-wide
  maxAge: undefined // Session cookie by default
}
```

### 3. Session Storage

```typescript
// Secure session storage
{
  storage: 'database', // Don't store in memory for production
  encryption: {
    algorithm: 'AES-256-GCM',
    keyRotation: 7 * 24 * 60 * 60 * 1000 // Weekly rotation
  },
  cleanup: {
    expiredSessions: 60 * 60 * 1000, // Clean every hour
    inactiveSessions: 30 * 24 * 60 * 60 * 1000 // Remove after 30 days
  }
}
```

### 4. IP and Device Validation

```typescript
// Strict validation for high-security scenarios
{
  ipValidation: {
    enabled: true,
    allowSubnets: true, // Allow same subnet
    maxChanges: 3, // Max IP changes per session
    geoFencing: ['US', 'CA'] // Restrict by country
  },

  deviceFingerprinting: {
    enabled: true,
    strictMode: false, // Don't break on minor changes
    trackComponents: [
      'userAgent',
      'screenResolution',
      'timezone',
      'language',
      'platform'
    ]
  }
}
```

## Error Handling

### Session Errors

| Error Code | Description | Action Required |
|------------|-------------|-----------------|
| `session_expired` | Access token expired | Refresh token |
| `session_revoked` | Session manually revoked | Re-authenticate |
| `invalid_token` | Malformed or invalid token | Clear and re-authenticate |
| `refresh_expired` | Refresh token expired | Full re-authentication |
| `device_changed` | Device fingerprint mismatch | Verify identity |
| `ip_changed` | IP address validation failed | Security verification |
| `concurrent_limit` | Too many active sessions | Revoke old sessions |

### Error Handling Implementation

```typescript
// Comprehensive session error handling
const handleSessionError = async (error, retryCount = 0) => {
  switch (error.code) {
    case 'session_expired':
      if (retryCount < 3) {
        try {
          await refreshSession()
          return true // Retry original request
        } catch (refreshError) {
          return handleSessionError(refreshError, retryCount + 1)
        }
      }
      break

    case 'refresh_expired':
    case 'session_revoked':
      // Force re-authentication
      clearTokens()
      redirectToLogin()
      break

    case 'device_changed':
    case 'ip_changed':
      // Require additional verification
      await requireSecurityVerification({
        reason: error.code,
        methods: ['mfa', 'email_verification']
      })
      break

    case 'concurrent_limit':
      // Show session management dialog
      showSessionManagementDialog()
      break

    default:
      console.error('Unhandled session error:', error)
      // Fallback to re-authentication
      redirectToLogin()
  }

  return false
}

// Automatic retry with exponential backoff
const apiCallWithRetry = async (apiCall, maxRetries = 3) => {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await apiCall()
    } catch (error) {
      if (error.code && await handleSessionError(error, attempt)) {
        // Session was refreshed, retry the call
        continue
      }

      if (attempt === maxRetries - 1) {
        throw error // Final attempt failed
      }

      // Wait with exponential backoff
      await new Promise(resolve =>
        setTimeout(resolve, Math.pow(2, attempt) * 1000)
      )
    }
  }
}
```

## Testing

### Unit Tests

```typescript
describe('Session Management', () => {
  it('should create session with correct expiry', async () => {
    const { session } = await plinto.auth.signIn({
      email: 'test@example.com',
      password: 'password123'
    })

    expect(session.accessToken).toBeDefined()
    expect(session.refreshToken).toBeDefined()

    const expiresAt = new Date(session.expiresAt)
    const now = new Date()
    const diffMinutes = (expiresAt - now) / 60000

    expect(diffMinutes).toBeCloseTo(15, 1) // ~15 minutes
  })

  it('should refresh tokens correctly', async () => {
    const { session: originalSession } = await plinto.auth.signIn({
      email: 'test@example.com',
      password: 'password123'
    })

    // Wait a moment to ensure new tokens are different
    await new Promise(resolve => setTimeout(resolve, 1000))

    const refreshed = await plinto.auth.refreshToken({
      refreshToken: originalSession.refreshToken
    })

    expect(refreshed.accessToken).not.toBe(originalSession.accessToken)
    expect(refreshed.accessToken).toBeDefined()
  })

  it('should revoke sessions correctly', async () => {
    const { session } = await plinto.auth.signIn({
      email: 'test@example.com',
      password: 'password123'
    })

    // Verify session is valid
    const verified = await plinto.auth.verifySession({
      token: session.accessToken
    })
    expect(verified.valid).toBe(true)

    // Revoke session
    await plinto.auth.sessions.revoke({
      sessionId: session.id
    })

    // Verify session is no longer valid
    const revokedCheck = await plinto.auth.verifySession({
      token: session.accessToken
    })
    expect(revokedCheck.valid).toBe(false)
    expect(revokedCheck.reason).toBe('revoked')
  })

  it('should handle concurrent session limits', async () => {
    const user = await plinto.users.create({
      email: 'concurrent@example.com',
      maxConcurrentSessions: 2
    })

    // Create maximum allowed sessions
    const sessions = []
    for (let i = 0; i < 2; i++) {
      const { session } = await plinto.auth.signIn({
        email: user.email,
        password: 'password123'
      })
      sessions.push(session)
    }

    // Try to create one more session (should fail or revoke oldest)
    const { session: newSession } = await plinto.auth.signIn({
      email: user.email,
      password: 'password123'
    })

    // Check that oldest session was revoked
    const oldestSessionCheck = await plinto.auth.verifySession({
      token: sessions[0].accessToken
    })
    expect(oldestSessionCheck.valid).toBe(false)
  })
})
```

### Integration Tests

```typescript
describe('Session Flow Integration', () => {
  it('should handle full authentication lifecycle', async () => {
    // 1. Sign in
    const { user, session } = await plinto.auth.signIn({
      email: 'lifecycle@example.com',
      password: 'password123'
    })

    expect(user.email).toBe('lifecycle@example.com')
    expect(session.accessToken).toBeDefined()

    // 2. Verify session works
    const verified = await plinto.auth.verifySession({
      token: session.accessToken
    })
    expect(verified.valid).toBe(true)
    expect(verified.user.id).toBe(user.id)

    // 3. Refresh token
    const refreshed = await plinto.auth.refreshToken({
      refreshToken: session.refreshToken
    })
    expect(refreshed.accessToken).toBeDefined()

    // 4. List sessions
    const { sessions } = await plinto.auth.sessions.list({
      userId: user.id
    })
    expect(sessions.length).toBe(1)
    expect(sessions[0].device.type).toBe('test')

    // 5. Sign out
    await plinto.auth.sessions.revoke({
      sessionId: session.id
    })

    // 6. Verify session is revoked
    const finalCheck = await plinto.auth.verifySession({
      token: refreshed.accessToken
    })
    expect(finalCheck.valid).toBe(false)
  })
})
```

## Migration Guide

### From JWT Libraries

```typescript
// Before: Manual JWT handling
const jwt = require('jsonwebtoken')

const token = jwt.sign(
  { userId: user.id },
  process.env.JWT_SECRET,
  { expiresIn: '15m' }
)

const verified = jwt.verify(token, process.env.JWT_SECRET)

// After: Plinto session management
const { session } = await plinto.auth.signIn({
  email: user.email,
  password: password
})

const sessionInfo = await plinto.auth.verifySession({
  token: session.accessToken
})
```

### From Other Providers

```typescript
// Migrate from Auth0 sessions
const migrateAuth0Sessions = async (auth0Users) => {
  for (const auth0User of auth0Users) {
    // Import user
    const plintoUser = await plinto.auth.importUser({
      email: auth0User.email,
      auth0Id: auth0User.user_id
    })

    // Migrate active sessions if needed
    if (auth0User.last_login) {
      const lastLogin = new Date(auth0User.last_login)
      const sessionAge = Date.now() - lastLogin.getTime()

      // If recent login, create equivalent session
      if (sessionAge < 24 * 60 * 60 * 1000) { // Less than 24 hours
        await plinto.auth.createSession({
          userId: plintoUser.id,
          deviceInfo: {
            type: 'migrated',
            name: 'Migrated Session'
          },
          createdAt: lastLogin
        })
      }
    }
  }
}
```

## API Reference

### `signIn(options)`

Create authenticated session.

**Parameters:**
- `email` (string, required): User email
- `password` (string, required): User password
- `deviceInfo` (object): Device information
- `sessionOptions` (object): Session configuration

**Returns:**
- `user` (object): User profile
- `session` (object): Session details with tokens

### `verifySession(options)`

Verify session token validity.

**Parameters:**
- `token` (string, required): Access token
- `ipAddress` (string): Client IP for validation
- `userAgent` (string): User agent for device tracking

**Returns:**
- `valid` (boolean): Token validity
- `user` (object): User if valid
- `sessionId` (string): Session identifier
- `reason` (string): Invalid reason if applicable

### `refreshToken(options)`

Refresh expired access token.

**Parameters:**
- `refreshToken` (string, required): Refresh token
- `deviceInfo` (object): Device information

**Returns:**
- `accessToken` (string): New access token
- `refreshToken` (string): New refresh token (optional)
- `expiresAt` (string): Token expiry time

### `sessions.list(options)`

List user's active sessions.

**Parameters:**
- `userId` (string, required): User identifier
- `includeExpired` (boolean): Include expired sessions

**Returns:**
- `sessions` (array): Session list with details

### `sessions.revoke(options)`

Revoke specific session.

**Parameters:**
- `sessionId` (string, required): Session to revoke
- `reason` (string): Revocation reason

**Returns:**
- `success` (boolean): Operation result

## Related Guides

- [Password Authentication](/guides/authentication/passwords)
- [Multi-Factor Authentication](/guides/authentication/mfa)
- [Security Best Practices](/guides/security/best-practices)
- [Rate Limiting](/guides/security/rate-limiting)