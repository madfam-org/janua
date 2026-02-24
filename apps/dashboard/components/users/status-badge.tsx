'use client'

/**
 * Re-export StatusBadge from @janua/ui shared library
 * This file exists for backward compatibility with existing imports
 */

import { CheckCircle2, Clock, XCircle, Ban } from 'lucide-react'
import { StatusBadge as SharedStatusBadge, type StatusConfigMap } from '@janua/ui'
import type { UserStatus } from './types'

// Custom config for user status with icons
const userStatusConfig: StatusConfigMap<UserStatus> = {
  active: { label: 'Active', variant: 'success', icon: CheckCircle2 },
  inactive: { label: 'Inactive', variant: 'neutral', icon: Clock },
  suspended: { label: 'Suspended', variant: 'warning', icon: Ban },
  banned: { label: 'Banned', variant: 'error', icon: XCircle },
  pending: { label: 'Pending', variant: 'warning', icon: Clock },
}

export function StatusBadge({ status }: { status: UserStatus }) {
  return <SharedStatusBadge status={status} config={userStatusConfig} />
}
