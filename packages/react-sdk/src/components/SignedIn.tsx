import React, { type ReactNode } from 'react'
import { useJanua } from '../provider'

export interface SignedInProps {
  /** Content to render when authenticated */
  children: ReactNode
}

/**
 * SignedIn component - renders children only when user is authenticated
 *
 * Does not render during the loading state to prevent flash of content.
 */
export function SignedIn({ children }: SignedInProps) {
  const { isAuthenticated, isLoading } = useJanua()

  if (isLoading || !isAuthenticated) {
    return null
  }

  return <>{children}</>
}
