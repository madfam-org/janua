'use client'

import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Badge } from './badge'
import { cn } from '../lib/utils'
import { Crown, Shield, User, Eye, type LucideIcon } from 'lucide-react'

/**
 * Role Badge - A configurable badge for displaying user roles
 * 
 * @example
 * // Basic usage
 * <RoleBadge role="admin" />
 * 
 * // With custom config
 * <RoleBadge 
 *   role="moderator" 
 *   config={{
 *     moderator: { label: 'Mod', variant: 'info', icon: Shield }
 *   }}
 * />
 */

export type RoleVariant = 'owner' | 'admin' | 'member' | 'viewer' | 'custom'

export interface RoleConfig {
  label: string
  variant: RoleVariant
  icon?: LucideIcon
}

export type RoleConfigMap<T extends string = string> = Record<T, RoleConfig>

const roleVariants = cva('', {
  variants: {
    variant: {
      owner: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      admin: 'bg-primary/10 text-primary border-primary/20',
      member: 'bg-muted text-muted-foreground border-border',
      viewer: 'bg-muted/50 text-muted-foreground border-border',
      custom: 'bg-muted text-muted-foreground border-border',
    },
  },
  defaultVariants: {
    variant: 'member',
  },
})

// Default role configurations
const defaultRoleConfig: RoleConfigMap = {
  owner: { label: 'Owner', variant: 'owner', icon: Crown },
  admin: { label: 'Admin', variant: 'admin', icon: Shield },
  member: { label: 'Member', variant: 'member', icon: User },
  viewer: { label: 'Viewer', variant: 'viewer', icon: Eye },
}

export interface RoleBadgeProps<T extends string = string>
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children'>,
    VariantProps<typeof roleVariants> {
  role: T
  config?: Partial<RoleConfigMap<T>>
  showIcon?: boolean
}

export function RoleBadge<T extends string = string>({
  role,
  config,
  showIcon = false,
  className,
  variant: _variant, // Extract variant from props to prevent passing to Badge
  ...props
}: RoleBadgeProps<T>) {
  const mergedConfig = { ...defaultRoleConfig, ...config } as RoleConfigMap
  const roleConfig = mergedConfig[role] || {
    label: role.charAt(0).toUpperCase() + role.slice(1).replace(/_/g, ' '),
    variant: 'custom' as RoleVariant,
  }

  const Icon = roleConfig.icon

  return (
    <Badge
      variant="outline"
      className={cn(roleVariants({ variant: roleConfig.variant }), className)}
      {...props}
    >
      {showIcon && Icon && <Icon className="h-3 w-3 mr-1" />}
      {roleConfig.label}
    </Badge>
  )
}

export { roleVariants }
