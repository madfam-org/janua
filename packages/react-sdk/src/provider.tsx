import React, { createContext, useContext, useState, useEffect } from 'react'
import { PlintoClient, type PlintoConfig, type User, type Session } from '@plinto/typescript-sdk'

interface PlintoContextValue {
  client: PlintoClient
  user: User | null
  session: Session | null
  isLoading: boolean
  isAuthenticated: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const PlintoContext = createContext<PlintoContextValue | undefined>(undefined)

export interface PlintoProviderProps {
  children: React.ReactNode
  config: PlintoConfig
}

export function PlintoProvider({ children, config }: PlintoProviderProps) {
  const [client] = useState(() => new PlintoClient(config))
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const token = localStorage.getItem('plinto_access_token')
        if (token) {
          const currentUser = await client.getCurrentUser()
          if (currentUser) {
            setUser(currentUser)
            // Session management will be handled by the client internally
            // setSession(currentSession) // We'll handle this when session API is ready
          }
        }
      } catch (error) {
        // Error handled silently in production
        localStorage.removeItem('plinto_access_token')
        localStorage.removeItem('plinto_refresh_token')
      } finally {
        setIsLoading(false)
      }
    }

    initializeAuth()
  }, [client])

  const signIn = async (email: string, password: string) => {
    const tokens = await client.signIn({ email, password })
    
    if (tokens.access_token) {
      localStorage.setItem('plinto_access_token', tokens.access_token)
    }
    if (tokens.refresh_token) {
      localStorage.setItem('plinto_refresh_token', tokens.refresh_token)
    }
    
    const currentUser = await client.getCurrentUser()
    if (currentUser) {
      setUser(currentUser)
    }
  }

  const signOut = async () => {
    await client.signOut()
    setSession(null)
    setUser(null)
    localStorage.removeItem('plinto_access_token')
    localStorage.removeItem('plinto_refresh_token')
  }

  const value: PlintoContextValue = {
    client,
    user,
    session,
    isLoading,
    isAuthenticated: !!user,
    signIn,
    signOut,
  }

  return <PlintoContext.Provider value={value}>{children}</PlintoContext.Provider>
}

export function usePlinto() {
  const context = useContext(PlintoContext)
  if (!context) {
    throw new Error('usePlinto must be used within a PlintoProvider')
  }
  return context
}