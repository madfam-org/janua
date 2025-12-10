'use client'

/**
 * Janua SDK Authentication Provider for Dashboard
 *
 * Production-ready authentication with:
 * - Automatic token validation on startup
 * - Graceful handling of algorithm migrations (HS256 → RS256)
 * - Token refresh with retry logic
 * - Comprehensive error handling with user-friendly recovery
 */

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from 'react'
import { januaClient } from './janua-client'
import type { User } from '@janua/typescript-sdk'

// Storage keys for consistency
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'janua_access_token',
  REFRESH_TOKEN: 'janua_refresh_token',
  TOKEN_EXPIRES_AT: 'janua_token_expires_at',
  USER: 'janua_user',
  COOKIE: 'janua_token',
} as const

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

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Validates JWT token structure (not signature - that's server-side)
 * Returns false for malformed tokens or tokens that can't be decoded
 */
function isValidTokenStructure(token: string | null): boolean {
  if (!token) return false

  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false

    // Try to decode the payload
    const payload = JSON.parse(atob(parts[1]!.replace(/-/g, '+').replace(/_/g, '/')))

    // Check for required claims
    if (!payload.exp || !payload.sub) return false

    // Check if token is expired (with 60 second buffer)
    const now = Math.floor(Date.now() / 1000)
    if (payload.exp < now - 60) return false

    return true
  } catch {
    return false
  }
}

/**
 * Clears all authentication state from client storage
 */
function clearAuthState(): void {
  if (typeof window === 'undefined') return

  // Clear localStorage
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.TOKEN_EXPIRES_AT)
  localStorage.removeItem(STORAGE_KEYS.USER)

  // Clear cookie (both local and cross-domain for SSO cleanup)
  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`
  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; secure`
  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; domain=.janua.dev; expires=Thu, 01 Jan 1970 00:00:01 GMT`
}

/**
 * Redirects to login page with optional error message
 */
function redirectToLogin(reason?: string): void {
  if (typeof window === 'undefined') return

  const loginUrl = new URL('/login', window.location.origin)
  if (reason) {
    loginUrl.searchParams.set('reason', reason)
  }
  loginUrl.searchParams.set('redirect', window.location.pathname)
  window.location.href = loginUrl.toString()
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const initializationAttempted = useRef(false)

  /**
   * Validates stored tokens and attempts to refresh if needed
   * Returns true if authentication is valid, false otherwise
   */
  const validateAndRefreshTokens = useCallback(async (): Promise<boolean> => {
    try {
      const accessToken = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
      const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)

      // No tokens stored - user needs to login
      if (!accessToken && !refreshToken) {
        return false
      }

      // Check if access token is structurally valid and not expired
      if (isValidTokenStructure(accessToken)) {
        return true
      }

      // Access token invalid/expired - try to refresh
      if (refreshToken && isValidTokenStructure(refreshToken)) {
        try {
          await januaClient.auth.refreshToken()
          return true
        } catch (refreshError) {
          console.warn('Token refresh failed:', refreshError)
          // Refresh token is also invalid - clear and require re-login
          clearAuthState()
          return false
        }
      }

      // Both tokens invalid - clear state
      clearAuthState()
      return false
    } catch (error) {
      console.error('Token validation error:', error)
      clearAuthState()
      return false
    }
  }, [])

  /**
   * Fetches current user from API
   */
  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await januaClient.auth.getCurrentUser()
      setUser(currentUser)
      setError(null)

      // Sync user to legacy storage for page.tsx compatibility
      if (currentUser) {
        localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(currentUser))
      }
    } catch (err) {
      console.error('Failed to fetch user:', err)
      setUser(null)

      // Determine if this is an auth error requiring re-login
      const errorMessage = err instanceof Error ? err.message : String(err)
      const isAuthError =
        errorMessage.includes('401') ||
        errorMessage.includes('403') ||
        errorMessage.includes('Unauthorized') ||
        errorMessage.includes('token') ||
        errorMessage.includes('refresh')

      if (isAuthError) {
        clearAuthState()
        setError('Your session has expired. Please sign in again.')
      } else {
        setError('Failed to load user information. Please try again.')
      }
    }
  }, [])

  /**
   * Initialize authentication on mount
   * Skip API calls on public pages (login, etc.) to avoid console errors
   */
  useEffect(() => {
    // Prevent double initialization in React Strict Mode
    if (initializationAttempted.current) return
    initializationAttempted.current = true

    const initAuth = async () => {
      setIsLoading(true)

      try {
        // Skip auth initialization on public pages
        const isPublicPage = typeof window !== 'undefined' &&
          (window.location.pathname === '/login' ||
           window.location.pathname.startsWith('/api/'))

        if (isPublicPage) {
          // On login page, just check for existing tokens without API calls
          const accessToken = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
          if (accessToken && isValidTokenStructure(accessToken)) {
            // User has valid token on login page - they might want to go to dashboard
            // But don't make API calls, let them navigate naturally
            const cachedUser = localStorage.getItem(STORAGE_KEYS.USER)
            if (cachedUser) {
              try {
                setUser(JSON.parse(cachedUser))
              } catch {
                // Invalid cached user, ignore
              }
            }
          }
          setIsLoading(false)
          return
        }

        const hasValidTokens = await validateAndRefreshTokens()

        if (hasValidTokens) {
          await refreshUser()
        } else {
          // No valid tokens - user needs to login
          // Don't redirect here, let protected pages handle that
          setUser(null)
        }
      } catch (err) {
        console.error('Auth initialization failed:', err)
        setError('Authentication initialization failed')
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()

    // Set up event listeners for auth state changes
    const handleSignIn = ({ user: userData }: { user: User }) => {
      setUser(userData)
      setError(null)
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userData))
    }

    const handleSignOut = () => {
      setUser(null)
      clearAuthState()
    }

    const handleTokenRefresh = () => {
      // Silently refresh user data after token refresh
      refreshUser().catch(console.error)
    }

    const handleAuthError = () => {
      // Auth error from SDK - clear state and show error
      clearAuthState()
      setUser(null)
      setError('Authentication error. Please sign in again.')
    }

    januaClient.on('signIn', handleSignIn)
    januaClient.on('signOut', handleSignOut)
    januaClient.on('tokenRefreshed', handleTokenRefresh)
    januaClient.on('authError', handleAuthError)

    return () => {
      januaClient.off('signIn', handleSignIn)
      januaClient.off('signOut', handleSignOut)
      januaClient.off('tokenRefreshed', handleTokenRefresh)
      januaClient.off('authError', handleAuthError)
    }
  }, [validateAndRefreshTokens, refreshUser])

  const login = async (email: string, password: string) => {
    setError(null)
    try {
      const response = await januaClient.auth.signIn({ email, password })
      setUser(response.user)

      // Sync to legacy storage
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(response.user))

      // Also set cookie for middleware compatibility
      // Use samesite=lax and domain=.janua.dev for cross-subdomain SSO (app.janua.dev ↔ admin.janua.dev)
      const token = await januaClient.getAccessToken()
      if (token) {
        const cookieDomain = window.location.hostname.includes('janua.dev') ? '; domain=.janua.dev' : ''
        document.cookie = `${STORAGE_KEYS.COOKIE}=${token}; path=/${cookieDomain}; secure; samesite=lax`
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed'
      setError(errorMessage)
      throw err
    }
  }

  const logout = async () => {
    try {
      await januaClient.auth.signOut()
    } catch (err) {
      console.error('Logout API call failed:', err)
      // Continue with local logout even if API fails
    } finally {
      clearAuthState()
      setUser(null)
      setError(null)
      redirectToLogin()
    }
  }

  const clearError = () => setError(null)

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        logout,
        refreshUser,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

/**
 * API helper with automatic token handling and retry logic
 * Handles token refresh transparently and redirects to login on auth failures
 */
export async function apiCall(endpoint: string, options: RequestInit = {}): Promise<Response> {
  // Get token with validation
  let token: string | null = null

  try {
    token = await januaClient.getAccessToken()

    // Validate token structure before using
    if (!isValidTokenStructure(token)) {
      // Try to refresh
      await januaClient.auth.refreshToken()
      token = await januaClient.getAccessToken()
    }
  } catch (err) {
    console.error('Failed to get valid access token:', err)
    clearAuthState()
    redirectToLogin('session_expired')
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

  // Handle auth errors with retry
  if (response.status === 401 || response.status === 403) {
    try {
      // Attempt token refresh
      await januaClient.auth.refreshToken()
      const newToken = await januaClient.getAccessToken()

      if (!newToken) {
        throw new Error('No token after refresh')
      }

      // Retry the original request
      const retryConfig: RequestInit = {
        ...config,
        headers: {
          ...config.headers,
          'Authorization': `Bearer ${newToken}`,
        },
      }

      const retryResponse = await fetch(endpoint, retryConfig)

      // If retry also fails with auth error, give up
      if (retryResponse.status === 401 || retryResponse.status === 403) {
        throw new Error('Authentication failed after token refresh')
      }

      return retryResponse
    } catch (refreshError) {
      console.error('Token refresh failed:', refreshError)
      clearAuthState()
      redirectToLogin('session_expired')
      throw new Error('Session expired. Please sign in again.')
    }
  }

  return response
}
