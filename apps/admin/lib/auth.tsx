'use client'

/**
 * Admin Authentication Provider with RBAC
 *
 * Requires @janua.dev email and superadmin/admin role
 */

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
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

// Allowed roles (configurable via env)
const DEFAULT_ROLES = ['superadmin', 'admin']
const ALLOWED_ROLES = process.env.NEXT_PUBLIC_ALLOWED_ADMIN_ROLES
  ? process.env.NEXT_PUBLIC_ALLOWED_ADMIN_ROLES.split(',').map((r) => r.trim())
  : DEFAULT_ROLES

// Allow @janua.dev and @madfam.io (platform operators) plus custom domains from environment
const DEFAULT_DOMAINS = ['@janua.dev', '@madfam.io']
const customDomains = process.env.NEXT_PUBLIC_ALLOWED_ADMIN_DOMAINS?.split(',').map(d => d.trim()) || []
const ALLOWED_EMAIL_DOMAINS = [...new Set([...DEFAULT_DOMAINS, ...customDomains])]

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthorized = useCallback(() => {
    if (!user) return false
    const hasAllowedRole = user.roles?.some((role: string) => ALLOWED_ROLES.includes(role)) || false
    const hasAllowedEmail = ALLOWED_EMAIL_DOMAINS.some(domain => user.email?.endsWith(domain)) || false
    return hasAllowedRole && hasAllowedEmail
  }, [user])

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await januaClient.auth.getCurrentUser()
      setUser(currentUser)
      setMiddlewareCookies(currentUser)
    } catch (error) {
      console.error('Failed to fetch user:', error)
      setUser(null)
      setMiddlewareCookies(null)
    }
  }, [])

  // Helper to read cookie value
  const getCookie = (name: string): string | null => {
    if (typeof document === 'undefined') return null
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || null
    }
    return null
  }

  // Helper to set middleware cookies for authorization
  const setMiddlewareCookies = (userData: User | null) => {
    if (typeof document === 'undefined') return

    if (userData) {
      const roles = userData.roles?.join(',') || ''
      document.cookie = `janua_admin_email=${userData.email}; path=/; max-age=86400; SameSite=Strict`
      document.cookie = `janua_admin_roles=${roles}; path=/; max-age=86400; SameSite=Strict`
    } else {
      document.cookie = 'janua_admin_email=; Max-Age=0; path=/'
      document.cookie = 'janua_admin_roles=; Max-Age=0; path=/'
    }
  }

  // Check for existing session via HTTP-only cookies (for SSO)
  const checkSession = useCallback(async (): Promise<boolean> => {
    try {
      // First, check if we have the SSO cookie from dashboard login
      const ssoToken = getCookie('janua_token')
      if (!ssoToken) {
        console.log('[SSO] No janua_token cookie found')
        return false
      }

      const apiBase = process.env.NEXT_PUBLIC_JANUA_API_URL || 'https://api.janua.dev'
      
      // Try to validate the token and get user info using the token from cookie
      const response = await fetch(`${apiBase}/api/v1/auth/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${ssoToken}`,
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const userData = await response.json()
        if (userData && userData.id) {
          console.log('[SSO] Session found via cookie, user:', userData.email)
          // Store the token in localStorage for SDK to use
          localStorage.setItem('janua_access_token', ssoToken)
          // Update local state with user and set middleware cookies
          setUser(userData as User)
          setMiddlewareCookies(userData as User)
          return true
        }
      } else {
        console.log('[SSO] Token validation failed:', response.status)
      }
      setMiddlewareCookies(null)
      return false
    } catch (error) {
      console.error('[SSO] Session check failed:', error)
      return false
    }
  }, [])

  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true)
      await refreshUser()
      setIsLoading(false)
    }

    initAuth()

    const handleSignIn = ({ user: userData }: { user: User }) => {
      setUser(userData)
      setMiddlewareCookies(userData)
    }
    const handleSignOut = () => {
      setUser(null)
      setMiddlewareCookies(null)
    }
    const handleTokenRefresh = () => refreshUser()

    januaClient.on('signIn', handleSignIn)
    januaClient.on('signOut', handleSignOut)
    januaClient.on('tokenRefreshed', handleTokenRefresh)

    return () => {
      januaClient.off('signIn', handleSignIn)
      januaClient.off('signOut', handleSignOut)
      januaClient.off('tokenRefreshed', handleTokenRefresh)
    }
  }, [refreshUser])

  const login = async (email: string, password: string) => {
    const response = await januaClient.auth.signIn({ email, password })
    setUser(response.user)
    setMiddlewareCookies(response.user)
  }

  const logout = async () => {
    await januaClient.auth.signOut()
    setUser(null)
    setMiddlewareCookies(null)
    window.location.href = '/login'
  }

  const hasRole = (role: string): boolean => {
    return user?.roles?.includes(role) || false
  }

  const hasPermission = (permission: string): boolean => {
    return user?.permissions?.includes(permission) || false
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isAuthorized: isAuthorized(),
        isLoading,
        login,
        logout,
        refreshUser,
        checkSession,
        hasRole,
        hasPermission,
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
