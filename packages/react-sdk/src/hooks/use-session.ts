import { useState } from 'react'
import { useJanua } from '../provider'
import type { TokenResponse, Session } from '@janua/typescript-sdk'

export function useSession() {
  const { client, session } = useJanua()
  const [isRefreshing, setIsRefreshing] = useState(false)

  const refreshTokens = async (): Promise<TokenResponse | null> => {
    const refreshToken = await client.getRefreshToken()
    if (!refreshToken) {
      return null
    }

    setIsRefreshing(true)
    try {
      return await client.auth.refreshToken()
    } catch {
      // The SDK owns fenced persistence and invalidation of the failed session.
      return null
    } finally {
      setIsRefreshing(false)
    }
  }

  const getCurrentSession = async (): Promise<Session | null> => {
    try {
      const currentSession = await client.sessions.getCurrentSession()
      return currentSession
    } catch (error) {
      // Session retrieval failed
      return null
    }
  }

  return {
    session,
    isRefreshing,
    refreshTokens,
    getCurrentSession,
  }
}