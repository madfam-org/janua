import * as React from 'react'
import { Separator } from '../separator'
import { cn } from '../../lib/utils'

export interface AuthDividerProps {
  /** Text label displayed in the divider. Defaults to "Or continue with" */
  label?: string
  className?: string
}

export function AuthDivider({ label = 'Or continue with', className }: AuthDividerProps) {
  return (
    <div className={cn('relative my-6', className)}>
      <Separator />
      <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-xs text-muted-foreground">
        {label}
      </span>
    </div>
  )
}
