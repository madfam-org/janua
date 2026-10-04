'use client'

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from 'react'
import { januaClient } from './janua-client'
import type { User } from '@janua/typescript-sdk'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isAuthorized: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  checkSession: () => Promise<boolean>
  hasRole: (role: string) => boolean
  hasPermission: (permission: string) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

function sharedSsoToken(): string | null {
  return document.cookie.split('; ').find(cookie => cookie.startsWith('janua_access_token='))?.split('=').slice(1).join('=') || null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const pending = useRef<Promise<boolean> | null>(null)
  const generation = useRef(0)

  const checkSession = useCallback((): Promise<boolean> => {
    // The page and SDK events can all request hydration at once. Publish auth
    // state only after the bridge has set the HttpOnly cookie, avoiding the
    // previous redirect-before-cookie race on direct sign-in.
    if (pending.current) return pending.current
    const currentGeneration = generation.current
    const establish = async () => {
      try {
        const storedToken = await januaClient.getAccessToken()
        const ssoToken = sharedSsoToken()
        let token = storedToken || ssoToken
        if (!token) {
          if (currentGeneration === generation.current) setUser(null)
          return false
        }
        const bridge = (accessToken: string) => fetch('/api/auth/session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ access_token: accessToken }),
        })
        let response = await bridge(token)
        // A returning operator may have an expired local access token. Prefer
        // the SDK refresh path; an existing dashboard session can also recover
        // an admin tab whose local access token is stale.
        if (response.status === 401 && storedToken) {
          if (await januaClient.getRefreshToken()) {
            try {
              await januaClient.auth.refreshToken()
              token = await januaClient.getAccessToken() || token
              response = await bridge(token)
            } catch {
              // A shared SSO token may still be usable after a failed refresh.
            }
          }
          if (response.status === 401 && ssoToken && ssoToken !== token) {
            token = ssoToken
            response = await bridge(token)
          }
        }
        if (!response.ok) {
          if (currentGeneration === generation.current) setUser(null)
          return false
        }
        const session = await response.json()
        if (currentGeneration !== generation.current) return false
        // A shared dashboard cookie is only copied after the server has checked
        // its signature AND the current platform operator record.
        if (token === ssoToken && token !== storedToken) {
          localStorage.removeItem('janua_refresh_token')
          localStorage.removeItem('janua_token_expires_at')
          localStorage.setItem('janua_access_token', token)
        }
        setUser(session.user as User)
        return true
      } catch {
        if (currentGeneration === generation.current) setUser(null)
        return false
      }
    }
    pending.current = establish().finally(() => { pending.current = null })
    return pending.current
  }, [])

  const refreshUser = useCallback(async () => { await checkSession() }, [checkSession])

  useEffect(() => {
    void checkSession().finally(() => setIsLoading(false))
    const synchronize = () => {
      // A refresh can finish while the bridge still checks the previous token.
      // Queue another bridge instead of losing that token-change event.
      if (pending.current) void pending.current.then(() => checkSession())
      else void checkSession()
    }
    const handleSignIn = () => {
      generation.current += 1
      synchronize()
    }
    const handleSignOut = () => {
      generation.current += 1
      setUser(null)
      // Clear the HttpOnly session even when sign-out is initiated by the SDK.
      void Promise.resolve(pending.current).then(() => fetch('/api/auth/session', { method: 'DELETE' })).catch(() => undefined)
    }
    const handleTokenRefresh = synchronize
    januaClient.on('auth:signedIn', handleSignIn)
    januaClient.on('auth:signedOut', handleSignOut)
    januaClient.on('token:refreshed', handleTokenRefresh)
    return () => {
      januaClient.off('auth:signedIn', handleSignIn)
      januaClient.off('auth:signedOut', handleSignOut)
      januaClient.off('token:refreshed', handleTokenRefresh)
    }
  }, [checkSession])

  const login = async (email: string, password: string) => {
    await januaClient.auth.signIn({ email, password })
    if (!await checkSession()) throw new Error('Unable to establish admin session')
  }

  const logout = async () => {
    generation.current += 1
    setUser(null)
    try {
      await januaClient.auth.signOut()
    } finally {
      // Wait for any bridge response to finish setting cookies before deleting.
      await pending.current
      await fetch('/api/auth/session', { method: 'DELETE' })
      localStorage.removeItem('janua_access_token')
      localStorage.removeItem('janua_refresh_token')
      localStorage.removeItem('janua_token_expires_at')
      document.cookie = 'janua_access_token=; path=/; domain=.janua.dev; max-age=0; secure; samesite=lax'
      window.location.href = '/login'
    }
  }

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      // Only a successful, authoritative bridge response populates user.
      isAuthorized: !!user,
      isLoading,
      login,
      logout,
      refreshUser,
      checkSession,
      hasRole: (role) => !!user && role === 'admin',
      hasPermission: (permission) => user?.permissions?.includes(permission) || false,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
