/**
 * Danger zone tab for organization profile (organization deletion)
 */

import * as React from 'react'
import { Button } from '../../button'
import { Input } from '../../input'
import { Label } from '../../label'

export interface DangerZoneTabProps {
  organizationSlug: string
  onDeleteOrganization?: () => Promise<void>
  onError?: (error: Error) => void
}

export function DangerZoneTab({
  organizationSlug,
  onDeleteOrganization,
  onError,
}: DangerZoneTabProps) {
  const [deleteConfirmation, setDeleteConfirmation] = React.useState('')
  const [isDeleting, setIsDeleting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleDelete = async () => {
    if (deleteConfirmation !== organizationSlug || !onDeleteOrganization) return

    setIsDeleting(true)
    setError(null)

    try {
      await onDeleteOrganization()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to delete organization')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
          {error}
        </div>
      )}

      <div className="border border-destructive rounded-lg p-6">
        <h3 className="text-lg font-semibold text-destructive mb-2">
          Delete organization
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          Once you delete an organization, there is no going back. This will permanently
          delete the organization and all associated data.
        </p>

        <div className="space-y-4">
          <div>
            <Label htmlFor="delete-confirm">
              Type <code className="text-sm bg-muted px-1 py-0.5 rounded">{organizationSlug}</code> to confirm
            </Label>
            <Input
              id="delete-confirm"
              value={deleteConfirmation}
              onChange={(e) => setDeleteConfirmation(e.target.value)}
              disabled={isDeleting}
              placeholder={organizationSlug}
            />
          </div>

          {onDeleteOrganization && (
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteConfirmation !== organizationSlug || isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete organization'}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
