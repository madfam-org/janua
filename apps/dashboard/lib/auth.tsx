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
} from '@janua/nextjs/app/client'
import { januaClient } from './janua-client'
import type { User } from '@janua/typescript-sdk'
import { browserConsoleConfig, parseConsoleRuntimeConfig, type ConsoleRuntimeConfig } from '@janua/ui/console-runtime'
import { setAuthCookie, clearAuthCookie } from './auth-storage'


/**
 * Syncs the access token to a cookie for Next.js middleware route protection
 * and cross-subdomain SSO across *.janua.dev
 */
function syncTokenCookie(token: string | null): void {
  if (typeof window === 'undefined') return

  if (token) setAuthCookie(token)
  else clearAuthCookie()
}

// ── Auth context with dashboard-specific additions ──

/**
 * Result of {@link AuthContextType.login}. When the account has a second factor,
 * `mfaRequired` is true and `login` does NOT complete the session — the caller
 * must collect a code and call {@link AuthContextType.verifyMfa} with the
 * returned `mfaToken`.
 */
interface LoginResult {
  mfaRequired: boolean
  mfaToken?: string
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  /**
   * Sign in with email + password. Resolves to `{ mfaRequired: true, mfaToken }`
   * when a second factor is needed (no session is established yet); resolves to
   * `{ mfaRequired: false }` on a completed sign-in.
   */
  login: (email: string, password: string) => Promise<LoginResult>
  /**
   * Complete an MFA challenge raised by {@link login}. Pass the `mfaToken` from
   * the login result plus the user's TOTP or backup code.
   */
  verifyMfa: (mfaToken: string, code: string) => Promise<void>
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

  const login = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    setError(null)
    try {
      const result = await client.auth.signIn({ email, password })
      // A second factor is required: surface the challenge instead of treating
      // the (token-less) response as a completed sign-in. Previously this method
      // ignored the MFA fields entirely, so an MFA-enabled user's login appeared
      // to "succeed" with no session — the dashboard's user-visible instance of
      // the audit's P1 #1.
      if (result.mfa_required) {
        return { mfaRequired: true, mfaToken: result.mfa_token }
      }
      // Cookie sync happens via the useEffect above.
      return { mfaRequired: false }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed'
      setError(errorMessage)
      throw err
    }
  }, [client])

  const verifyMfa = useCallback(async (mfaToken: string, code: string): Promise<void> => {
    setError(null)
    try {
      await client.auth.verifyMfaChallenge(mfaToken, code)
      // Tokens are now persisted by the SDK; the useEffect above syncs the cookie.
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Verification failed'
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
        verifyMfa,
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


/**
 * AuthProvider wraps JanuaProvider from @janua/nextjs with a bridge
 * that handles cookie sync and provides backward-compatible useAuth().
 */
export function AuthProvider({ children, runtimeConfig }: { children: ReactNode; runtimeConfig?: ConsoleRuntimeConfig }) {
  const config = parseConsoleRuntimeConfig(runtimeConfig || browserConsoleConfig('dashboard'), 'dashboard')
  const januaConfig = { baseURL: config.apiOrigin, issuer: config.issuer, audience: config.audience,
    tokenStorage: 'localStorage' as const, autoRefreshTokens: true }
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
