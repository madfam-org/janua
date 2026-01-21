'use client'

import { KeyRound, Ban, Trash2, X } from 'lucide-react'
import { Button } from '@janua/ui'
import type { UserActionType } from './types'

interface BulkActionsToolbarProps {
  selectedCount: number
  onAction: (action: UserActionType) => void
  onClear: () => void
}

export function BulkActionsToolbar({
  selectedCount,
  onAction,
  onClear,
}: BulkActionsToolbarProps) {
  return (
    <div className="bg-muted animate-fade-in flex items-center gap-2 rounded-lg p-2">
      <span className="text-sm font-medium">
        {selectedCount} selected
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAction('reset_password')}
      >
        <KeyRound className="mr-2 size-4" />
        Reset Passwords
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAction('ban')}
      >
        <Ban className="mr-2 size-4" />
        Ban Selected
      </Button>
      <Button
        variant="destructive"
        size="sm"
        onClick={() => onAction('delete')}
      >
        <Trash2 className="mr-2 size-4" />
        Delete Selected
      </Button>
      <Button variant="ghost" size="sm" onClick={onClear}>
        <X className="size-4" />
      </Button>
    </div>
  )
}
