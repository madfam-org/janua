'use client'

import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Badge } from './badge'
import { cn } from '../lib/utils'
import type { LucideIcon } from 'lucide-react'

/**
 * Status Badge - A configurable badge for displaying status indicators
 * 
 * @example
 * // Basic usage
 * <StatusBadge status="active" />
 * 
 * // With custom config
 * <StatusBadge 
 *   status="pending" 
 *   config={{
 *     pending: { label: 'Awaiting', variant: 'warning', icon: Clock }
 *   }}
 * />
 */

export type StatusVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral'

export interface StatusConfig {
  label: string
  variant: StatusVariant
  icon?: LucideIcon
}

export type StatusConfigMap<T extends string = string> = Record<T, StatusConfig>

const statusVariants = cva('', {
  variants: {
    variant: {
      success: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20',
      warning: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20',
      error: 'bg-destructive/10 text-destructive border-destructive/20',
      info: 'bg-primary/10 text-primary border-primary/20',
      neutral: 'bg-muted text-muted-foreground border-border',
    },
  },
  defaultVariants: {
    variant: 'neutral',
  },
})

// Default status configurations
const defaultStatusConfig: StatusConfigMap = {
  active: { label: 'Active', variant: 'success' },
  inactive: { label: 'Inactive', variant: 'neutral' },
  pending: { label: 'Pending', variant: 'warning' },
  banned: { label: 'Banned', variant: 'error' },
  suspended: { label: 'Suspended', variant: 'error' },
  expired: { label: 'Expired', variant: 'warning' },
  revoked: { label: 'Revoked', variant: 'error' },
  rotating: { label: 'Rotating', variant: 'info' },
  enabled: { label: 'Enabled', variant: 'success' },
  disabled: { label: 'Disabled', variant: 'neutral' },
  error: { label: 'Error', variant: 'error' },
}

export interface StatusBadgeProps<T extends string = string>
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children'>,
    VariantProps<typeof statusVariants> {
  status: T
  config?: Partial<StatusConfigMap<T>>
  showIcon?: boolean
}

export function StatusBadge<T extends string = string>({
  status,
  config,
  showIcon = true,
  className,
  variant: _variant, // Extract variant from props to prevent passing to Badge
  ...props
}: StatusBadgeProps<T>) {
  const mergedConfig = { ...defaultStatusConfig, ...config } as StatusConfigMap
  const statusConfig = mergedConfig[status] || {
    label: status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' '),
    variant: 'neutral' as StatusVariant,
  }

  const Icon = statusConfig.icon

  return (
    <Badge
      variant="outline"
      className={cn(statusVariants({ variant: statusConfig.variant }), className)}
      {...props}
    >
      {showIcon && Icon && <Icon className="h-3 w-3 mr-1" />}
      {statusConfig.label}
    </Badge>
  )
}

export { statusVariants }
