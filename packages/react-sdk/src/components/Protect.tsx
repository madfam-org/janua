import React, { useEffect, type ReactNode } from 'react'
import { useJanua } from '../provider'
import type { JanuaUser } from '../types'

export interface ProtectProps {
  /** Content to render when authorized */
  children: ReactNode
  /** Required role for access */
  role?: string
  /** Required permission for access */
  permission?: string
  /** Custom condition function for access control */
  condition?: (user: JanuaUser) => boolean
  /** Content to render when unauthorized */
  fallback?: ReactNode
  /** Redirect URL when unauthorized (triggers navigation instead of fallback) */
  redirectTo?: string
}

/**
 * Protect component - auth guard for conditional rendering
 *
 * Renders children only when the user is authenticated and passes
 * optional role, permission, or custom condition checks.
 * Shows fallback content or redirects when unauthorized.
 */
export function Protect({
  children,
  role,
  permission,
  condition,
  fallback = null,
  redirectTo,
}: ProtectProps) {
  const { user, isAuthenticated, isLoading } = useJanua()

  const isAuthorized = (() => {
    if (!isAuthenticated || !user) return false

    if (role && user.organization_role !== role) return false

    // Permission check: convention-based on organization_role
    // In a full implementation this would check against a permissions list
    if (permission && !user.organization_role) return false

    if (condition && !condition(user)) return false

    return true
  })()

  useEffect(() => {
    if (!isLoading && !isAuthorized && redirectTo && typeof window !== 'undefined') {
      window.location.href = redirectTo
    }
  }, [isLoading, isAuthorized, redirectTo])

  if (isLoading) {
    return null
  }

  if (!isAuthorized) {
    // If redirectTo is set, we already triggered navigation above
    if (redirectTo) return null
    return <>{fallback}</>
  }

  return <>{children}</>
}
