import React, { type ReactNode } from 'react'
import { useJanua } from '../provider'

export interface SignedOutProps {
  /** Content to render when not authenticated */
  children: ReactNode
}

/**
 * SignedOut component - renders children only when user is not authenticated
 *
 * Does not render during the loading state to prevent flash of content.
 */
export function SignedOut({ children }: SignedOutProps) {
  const { isAuthenticated, isLoading } = useJanua()

  if (isLoading || isAuthenticated) {
    return null
  }

  return <>{children}</>
}
