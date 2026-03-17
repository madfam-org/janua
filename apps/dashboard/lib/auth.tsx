'use client'

/**
 * Janua Dashboard Authentication Provider
 *
 * Uses @janua/nextjs JanuaProvider as the foundation, with a bridge
 * component that syncs cookies for middleware compatibility and
 * cross-subdomain SSO (app.janua.dev <-> admin.janua.dev).
 */

import { ReactNode, createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  JanuaProvider,
  useJanua,
  useAuth as useJanuaAuth,
} from '@janua/nextjs'
import { januaClient } from './janua-client'
import type { User } from '@janua/typescript-sdk'

const COOKIE_NAME = 'janua_access_token'

/**
 * Syncs the access token to a cookie for Next.js middleware route protection
 * and cross-subdomain SSO across *.janua.dev
 */
function syncTokenCookie(token: string | null): void {
  if (typeof window === 'undefined') return

  if (token) {
    const cookieDomain = window.location.hostname.includes('janua.dev') ? '; domain=.janua.dev' : ''
    document.cookie = `${COOKIE_NAME}=${token}; path=/${cookieDomain}; secure; samesite=lax`
  } else {
    document.cookie = `${COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`
    document.cookie = `${COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; secure`
    document.cookie = `${COOKIE_NAME}=; path=/; domain=.janua.dev; expires=Thu, 01 Jan 1970 00:00:01 GMT`
  }
}

// ── Auth context with dashboard-specific additions ──

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  clearError: () => void
}

const DashboardAuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Bridge that lives inside JanuaProvider and syncs auth state
 * to cookies + provides the dashboard-specific context.
 */
function DashboardAuthBridge({ children }: { children: ReactNode }) {
  const { client, user, isLoading, isAuthenticated, signOut } = useJanua()
  const [error, setError] = useState<string | null>(null)

  // Sync token to cookie whenever auth state changes
  useEffect(() => {
    async function syncCookie() {
      if (isAuthenticated) {
        const token = await client.getAccessToken()
        syncTokenCookie(token)
      } else if (!isLoading) {
        syncTokenCookie(null)
      }
    }
    syncCookie()
  }, [client, isAuthenticated, isLoading])

  const login = useCallback(async (email: string, password: string) => {
    setError(null)
    try {
      await client.auth.signIn({ email, password })
      // Cookie sync happens via the useEffect above
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed'
      setError(errorMessage)
      throw err
    }
  }, [client])

  const logout = useCallback(async () => {
    try {
      await signOut()
    } catch (err) {
      console.error('Logout API call failed:', err)
    } finally {
      syncTokenCookie(null)
      setError(null)
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }
  }, [signOut])

  const refreshUser = useCallback(async () => {
    try {
      await client.auth.getCurrentUser()
    } catch (err) {
      console.error('Failed to refresh user:', err)
      setError('Failed to load user information.')
    }
  }, [client])

  const clearError = useCallback(() => setError(null), [])

  return (
    <DashboardAuthContext.Provider
      value={{
        user: user as User | null,
        isAuthenticated,
        isLoading,
        error,
        login,
        logout,
        refreshUser,
        clearError,
      }}
    >
      {children}
    </DashboardAuthContext.Provider>
  )
}

// ── JanuaProvider config ──

const januaConfig = {
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev',
  audience: process.env.NEXT_PUBLIC_JANUA_AUDIENCE || 'janua.dev',
  debug: process.env.NODE_ENV === 'development',
  tokenStorage: 'localStorage' as const,
  autoRefreshTokens: true,
}

/**
 * AuthProvider wraps JanuaProvider from @janua/nextjs with a bridge
 * that handles cookie sync and provides backward-compatible useAuth().
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <JanuaProvider config={januaConfig}>
      <DashboardAuthBridge>
        {children}
      </DashboardAuthBridge>
    </JanuaProvider>
  )
}

/**
 * Dashboard auth hook. Returns user, auth state, and auth actions.
 */
export function useAuth(): AuthContextType {
  const context = useContext(DashboardAuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

/**
 * @deprecated Use `januaClient` methods from `lib/janua-client` or typed wrappers
 * from `lib/api.ts` instead. This function will be removed in a future release.
 */
export async function apiCall(endpoint: string, options: RequestInit = {}): Promise<Response> {
  let token: string | null = null

  try {
    token = await januaClient.getAccessToken()
  } catch (err) {
    console.error('Failed to get access token:', err)
    throw new Error('Authentication required')
  }

  const config: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...options.headers,
    },
  }

  const response = await fetch(endpoint, config)

  if (response.status === 401) {
    try {
      await januaClient.auth.refreshToken()
      const newToken = await januaClient.getAccessToken()
      if (!newToken) throw new Error('No token after refresh')

      return fetch(endpoint, {
        ...config,
        headers: { ...config.headers, 'Authorization': `Bearer ${newToken}` },
      })
    } catch {
      throw new Error('Session expired. Please sign in again.')
    }
  }

  return response
}
