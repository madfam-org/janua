/**
 * General settings tab for organization profile
 */

import * as React from 'react'
import { Button } from '../../button'
import { Input } from '../../input'
import { Label } from '../../label'
import type { Organization } from './types'

export interface GeneralSettingsTabProps {
  organization: Organization
  canManageSettings: boolean
  onUpdateOrganization?: (data: { name?: string; slug?: string; description?: string }) => Promise<void>
  onUploadLogo?: (file: File) => Promise<string>
  onError?: (error: Error) => void
}

export function GeneralSettingsTab({
  organization,
  canManageSettings,
  onUpdateOrganization,
  onUploadLogo,
  onError,
}: GeneralSettingsTabProps) {
  const [orgName, setOrgName] = React.useState(organization.name)
  const [orgSlug, setOrgSlug] = React.useState(organization.slug)
  const [orgDescription, setOrgDescription] = React.useState(organization.description || '')
  const [isSaving, setIsSaving] = React.useState(false)
  const [isUploadingLogo, setIsUploadingLogo] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onUpdateOrganization) return

    setIsSaving(true)
    setError(null)

    try {
      await onUpdateOrganization({
        name: orgName,
        slug: orgSlug,
        description: orgDescription,
      })
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update organization')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !onUploadLogo) return

    setIsUploadingLogo(true)
    setError(null)

    try {
      await onUploadLogo(file)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to upload logo')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsUploadingLogo(false)
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
          {error}
        </div>
      )}

      {/* Organization Logo */}
      <div>
        <Label>Organization logo</Label>
        <div className="flex items-center gap-4 mt-2">
          <div className="w-20 h-20 rounded-lg bg-muted flex items-center justify-center overflow-hidden">
            {organization.logoUrl ? (
              <img
                src={organization.logoUrl}
                alt={organization.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-2xl font-bold text-muted-foreground">
                {organization.name.slice(0, 2).toUpperCase()}
              </span>
            )}
          </div>
          {canManageSettings && onUploadLogo && (
            <div>
              <input
                type="file"
                id="logo-upload"
                accept="image/*"
                onChange={handleLogoUpload}
                className="hidden"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => document.getElementById('logo-upload')?.click()}
                disabled={isUploadingLogo}
              >
                {isUploadingLogo ? 'Uploading...' : 'Upload logo'}
              </Button>
              <p className="text-xs text-muted-foreground mt-1">
                PNG, JPG up to 2MB
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Organization Name */}
      <div className="space-y-2">
        <Label htmlFor="org-name">Organization name</Label>
        <Input
          id="org-name"
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          disabled={!canManageSettings || isSaving}
          required
        />
      </div>

      {/* Organization Slug */}
      <div className="space-y-2">
        <Label htmlFor="org-slug">Organization slug</Label>
        <Input
          id="org-slug"
          value={orgSlug}
          onChange={(e) => setOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
          disabled={!canManageSettings || isSaving}
          required
          pattern="[a-z0-9-]+"
        />
        <p className="text-xs text-muted-foreground">
          Used in URLs: janua.com/{orgSlug}
        </p>
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="org-description">Description (optional)</Label>
        <textarea
          id="org-description"
          value={orgDescription}
          onChange={(e) => setOrgDescription(e.target.value)}
          disabled={!canManageSettings || isSaving}
          className="w-full min-h-[100px] px-3 py-2 border rounded-md resize-none"
          placeholder="Brief description of your organization"
        />
      </div>

      {canManageSettings && onUpdateOrganization && (
        <Button type="submit" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save changes'}
        </Button>
      )}
    </form>
  )
}
