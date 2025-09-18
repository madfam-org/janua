import { useState } from 'react'
import { usePlinto } from '../provider'
import type { TokenPair } from '@plinto/typescript-sdk'

export function useSession() {
  const { client, session } = usePlinto()
  const [isRefreshing, setIsRefreshing] = useState(false)

  const refreshTokens = async (): Promise<TokenPair | null> => {
    const refreshToken = localStorage.getItem('plinto_refresh_token')
    if (!refreshToken) {
      return null
    }

    setIsRefreshing(true)
    try {
      const tokens = await client.sessions.refresh(refreshToken)
      
      localStorage.setItem('plinto_access_token', tokens.access_token)
      if (tokens.refresh_token) {
        localStorage.setItem('plinto_refresh_token', tokens.refresh_token)
      }
      
      return tokens
    } catch (error) {
      // Token refresh failed, removing invalid tokens
      localStorage.removeItem('plinto_access_token')
      localStorage.removeItem('plinto_refresh_token')
      return null
    } finally {
      setIsRefreshing(false)
    }
  }

  const verifyToken = async (token?: string) => {
    const tokenToVerify = token || localStorage.getItem('plinto_access_token')
    if (!tokenToVerify) {
      return null
    }

    try {
      const payload = await client.sessions.verify(tokenToVerify)
      return payload
    } catch (error) {
      // Token verification failed
      return null
    }
  }

  return {
    session,
    isRefreshing,
    refreshTokens,
    verifyToken,
  }
}