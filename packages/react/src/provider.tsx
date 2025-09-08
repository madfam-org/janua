import React, { createContext, useContext, useState, useEffect } from 'react'
import { PlintoClient, type PlintoConfig, type Identity, type Session } from '@plinto/sdk'

interface PlintoContextValue {
  client: PlintoClient
  identity: Identity | null
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
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const token = localStorage.getItem('plinto_access_token')
        if (token) {
          const currentSession = await client.sessions.current(token)
          setSession(currentSession)
          if (currentSession.identity_id) {
            const currentIdentity = await client.identities.get(currentSession.identity_id)
            setIdentity(currentIdentity)
          }
        }
      } catch (error) {
        console.error('Failed to initialize auth:', error)
        localStorage.removeItem('plinto_access_token')
        localStorage.removeItem('plinto_refresh_token')
      } finally {
        setIsLoading(false)
      }
    }

    initializeAuth()
  }, [client])

  const signIn = async (email: string, password: string) => {
    const newSession = await client.sessions.create({ email, password })
    setSession(newSession)
    
    if (newSession.access_token) {
      localStorage.setItem('plinto_access_token', newSession.access_token)
    }
    if (newSession.refresh_token) {
      localStorage.setItem('plinto_refresh_token', newSession.refresh_token)
    }
    
    if (newSession.identity_id) {
      const currentIdentity = await client.identities.get(newSession.identity_id)
      setIdentity(currentIdentity)
    }
  }

  const signOut = async () => {
    if (session?.id) {
      await client.sessions.revoke(session.id)
    }
    setSession(null)
    setIdentity(null)
    localStorage.removeItem('plinto_access_token')
    localStorage.removeItem('plinto_refresh_token')
  }

  const value: PlintoContextValue = {
    client,
    identity,
    session,
    isLoading,
    isAuthenticated: !!session && !!identity,
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