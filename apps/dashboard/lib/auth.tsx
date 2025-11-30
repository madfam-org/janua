'use client'

/**
 * Janua SDK Authentication Provider for Dashboard
 *
 * This replaces the custom auth implementation with @janua/react-sdk
 * to dogfood our own authentication platform.
 */

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
import { januaClient } from './janua-client'
import type { User } from '@janua/typescript-sdk'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await januaClient.auth.getCurrentUser()
      setUser(currentUser)
    } catch (error) {
      console.error('Failed to fetch user:', error)
      setUser(null)
    }
  }, [])

  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true)
      await refreshUser()
      setIsLoading(false)
    }

    initAuth()

    // Set up event listeners for auth state changes
    const handleSignIn = ({ user: userData }: { user: User }) => {
      setUser(userData)
    }

    const handleSignOut = () => {
      setUser(null)
    }

    const handleTokenRefresh = () => {
      refreshUser()
    }

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
    try {
      const response = await januaClient.auth.signIn({ email, password })
      setUser(response.user)
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }

  const logout = async () => {
    try {
      await januaClient.auth.signOut()
      setUser(null)
      window.location.href = '/login'
    } catch (error) {
      console.error('Logout failed:', error)
      // Force logout on client side even if API call fails
      setUser(null)
      window.location.href = '/login'
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        refreshUser,
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

// API helper using Janua SDK
export async function apiCall(endpoint: string, options: RequestInit = {}) {
  const token = await januaClient.getAccessToken()

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
    // Token expired - Janua SDK will handle refresh
    await januaClient.auth.refreshToken()
    // Retry request with new token
    const newToken = await januaClient.getAccessToken()
    config.headers = {
      ...config.headers,
      'Authorization': `Bearer ${newToken}`,
    }
    return fetch(endpoint, config)
  }

  return response
}
