'use client'

import { Loader2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@janua/ui'
import type { UserAction } from './types'

interface ActionDialogProps {
  open: boolean
  action: UserAction | null
  loading: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

export function ActionDialog({
  open,
  action,
  loading,
  onOpenChange,
  onConfirm,
}: ActionDialogProps) {
  const getTitle = () => {
    switch (action?.type) {
      case 'delete': return 'Delete User'
      case 'ban': return 'Ban User'
      case 'unban': return 'Unban User'
      case 'reset_password': return 'Reset Password'
      default: return 'Confirm Action'
    }
  }

  const getDescription = () => {
    switch (action?.type) {
      case 'delete':
        return `Are you sure you want to delete ${action.userName}? This action cannot be undone.`
      case 'ban':
        return `Are you sure you want to ban ${action.userName}? They will no longer be able to access the platform.`
      case 'unban':
        return `Are you sure you want to unban ${action.userName}? They will regain access to the platform.`
      case 'reset_password':
        return `A password reset email will be sent to ${action.userName}.`
      default:
        return 'Are you sure you want to perform this action?'
    }
  }

  const isDestructive = action?.type === 'delete' || action?.type === 'ban'

  return (
    <AlertDialog
      open={open}
      onOpenChange={(newOpen) => !loading && onOpenChange(newOpen)}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{getTitle()}</AlertDialogTitle>
          <AlertDialogDescription>{getDescription()}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={loading}
            className={
              isDestructive
                ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                : ''
            }
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Processing...
              </>
            ) : (
              'Confirm'
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
