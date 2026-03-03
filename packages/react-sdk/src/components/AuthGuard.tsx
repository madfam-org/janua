import React, { type ReactNode } from 'react'
import { Protect } from './Protect'
import type { JanuaUser } from '../types'

export interface AuthGuardProps {
  /** Content to render when authorized */
  children: ReactNode
  /** Redirect URL when unauthorized (required for route-level guards) */
  redirectTo: string
  /** Required role for access */
  role?: string
  /** Required permission for access */
  permission?: string
  /** Custom condition function for access control */
  condition?: (user: JanuaUser) => boolean
}

/**
 * AuthGuard component - route-level auth guard that always redirects
 *
 * A convenience wrapper around Protect with `redirectTo` required,
 * designed for use at route boundaries where unauthorized users
 * should always be redirected (e.g., to a login page).
 */
export function AuthGuard({
  children,
  redirectTo,
  role,
  permission,
  condition,
}: AuthGuardProps) {
  return (
    <Protect
      redirectTo={redirectTo}
      role={role}
      permission={permission}
      condition={condition}
    >
      {children}
    </Protect>
  )
}
