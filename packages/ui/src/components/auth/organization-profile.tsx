import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { Badge } from '../badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../tabs'
import { cn } from '../../lib/utils'

export interface OrganizationMember {
  /** Member ID */
  id: string
  /** Member email */
  email: string
  /** Member name */
  name?: string
  /** Member role */
  role: 'owner' | 'admin' | 'member'
  /** Member avatar URL */
  avatarUrl?: string
  /** Join date */
  joinedAt?: Date
  /** Invite status */
  status?: 'active' | 'invited' | 'suspended'
}

export interface OrganizationProfileProps {
  /** Optional custom class name */
  className?: string
  /** Organization data */
  organization: {
    id: string
    name: string
    slug: string
    logoUrl?: string
    description?: string
    createdAt?: Date
    memberCount?: number
  }
  /** Current user's role in the organization */
  userRole: 'owner' | 'admin' | 'member'
  /** Organization members */
  members?: OrganizationMember[]
  /** Callback to update organization */
  onUpdateOrganization?: (data: {
    name?: string
    slug?: string
    description?: string
  }) => Promise<void>
  /** Callback to upload organization logo */
  onUploadLogo?: (file: File) => Promise<string>
  /** Callback to fetch members */
  onFetchMembers?: () => Promise<OrganizationMember[]>
  /** Callback to invite member */
  onInviteMember?: (email: string, role: 'admin' | 'member') => Promise<void>
  /** Callback to update member role */
  onUpdateMemberRole?: (memberId: string, role: 'admin' | 'member') => Promise<void>
  /** Callback to remove member */
  onRemoveMember?: (memberId: string) => Promise<void>
  /** Callback to delete organization */
  onDeleteOrganization?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
}

export function OrganizationProfile({
  className,
  organization,
  userRole,
  members: initialMembers,
  onUpdateOrganization,
  onUploadLogo,
  onFetchMembers,
  onInviteMember,
  onUpdateMemberRole,
  onRemoveMember,
  onDeleteOrganization,
  onError,
}: OrganizationProfileProps) {
  const [activeTab, setActiveTab] = React.useState<'general' | 'members' | 'danger'>('general')
  const [members, setMembers] = React.useState(initialMembers)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // General settings state
  const [orgName, setOrgName] = React.useState(organization.name)
  const [orgSlug, setOrgSlug] = React.useState(organization.slug)
  const [orgDescription, setOrgDescription] = React.useState(organization.description || '')
  const [isSavingGeneral, setIsSavingGeneral] = React.useState(false)

  // Member management state
  const [inviteEmail, setInviteEmail] = React.useState('')
  const [inviteRole, setInviteRole] = React.useState<'admin' | 'member'>('member')
  const [isInviting, setIsInviting] = React.useState(false)

  // Danger zone state
  const [deleteConfirmation, setDeleteConfirmation] = React.useState('')
  const [isDeleting, setIsDeleting] = React.useState(false)

  const canManageSettings = userRole === 'owner' || userRole === 'admin'
  const canManageMembers = userRole === 'owner' || userRole === 'admin'
  const canDeleteOrg = userRole === 'owner'

  // Fetch members on mount if not provided
  React.useEffect(() => {
    if (!members && onFetchMembers && activeTab === 'members') {
      setIsLoading(true)
      onFetchMembers()
        .then(setMembers)
        .catch((err) => {
          const error = err instanceof Error ? err : new Error('Failed to fetch members')
          setError(error.message)
          onError?.(error)
        })
        .finally(() => setIsLoading(false))
    }
  }, [members, onFetchMembers, onError, activeTab])

  const handleSaveGeneral = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onUpdateOrganization) return

    setIsSavingGeneral(true)
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
      setIsSavingGeneral(false)
    }
  }

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !onUploadLogo) return

    setIsLoading(true)
    setError(null)

    try {
      await onUploadLogo(file)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to upload logo')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onInviteMember || !inviteEmail) return

    setIsInviting(true)
    setError(null)

    try {
      await onInviteMember(inviteEmail, inviteRole)
      setInviteEmail('')
      setInviteRole('member')
      // Refresh members list
      if (onFetchMembers) {
        const updatedMembers = await onFetchMembers()
        setMembers(updatedMembers)
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to invite member')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsInviting(false)
    }
  }

  const handleUpdateMemberRole = async (memberId: string, role: 'admin' | 'member') => {
    if (!onUpdateMemberRole) return

    try {
      await onUpdateMemberRole(memberId, role)
      // Update local state
      setMembers((prev) =>
        prev?.map((m) => (m.id === memberId ? { ...m, role } : m))
      )
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update member role')
      setError(error.message)
      onError?.(error)
    }
  }

  const handleRemoveMember = async (memberId: string) => {
    if (!onRemoveMember) return

    try {
      await onRemoveMember(memberId)
      // Update local state
      setMembers((prev) => prev?.filter((m) => m.id !== memberId))
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to remove member')
      setError(error.message)
      onError?.(error)
    }
  }

  const handleDeleteOrganization = async () => {
    if (!onDeleteOrganization || deleteConfirmation !== organization.slug) return

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

  const getMemberInitials = (member: OrganizationMember) => {
    if (member.name) {
      return member.name
        .split(' ')
        .map((word) => word[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }
    return member.email.slice(0, 2).toUpperCase()
  }

  return (
    <Card className={cn('w-full max-w-4xl mx-auto p-6', className)}>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Organization settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your organization profile and members
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList className="mb-6">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
          {canDeleteOrg && <TabsTrigger value="danger">Danger Zone</TabsTrigger>}
        </TabsList>

        {/* General Tab */}
        <TabsContent value="general">
          <form onSubmit={handleSaveGeneral} className="space-y-6">
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
                      disabled={isLoading}
                    >
                      Upload logo
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
                disabled={!canManageSettings || isSavingGeneral}
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
                disabled={!canManageSettings || isSavingGeneral}
                required
                pattern="[a-z0-9-]+"
              />
              <p className="text-xs text-muted-foreground">
                Used in URLs: plinto.com/{orgSlug}
              </p>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="org-description">Description (optional)</Label>
              <textarea
                id="org-description"
                value={orgDescription}
                onChange={(e) => setOrgDescription(e.target.value)}
                disabled={!canManageSettings || isSavingGeneral}
                className="w-full min-h-[100px] px-3 py-2 border rounded-md resize-none"
                placeholder="Brief description of your organization"
              />
            </div>

            {canManageSettings && onUpdateOrganization && (
              <Button type="submit" disabled={isSavingGeneral}>
                {isSavingGeneral ? 'Saving...' : 'Save changes'}
              </Button>
            )}
          </form>
        </TabsContent>

        {/* Members Tab */}
        <TabsContent value="members">
          <div className="space-y-6">
            {/* Invite Member */}
            {canManageMembers && onInviteMember && (
              <form onSubmit={handleInviteMember} className="space-y-4 pb-6 border-b">
                <h3 className="font-medium">Invite member</h3>
                <div className="flex gap-3">
                  <Input
                    type="email"
                    placeholder="email@example.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    disabled={isInviting}
                    required
                    className="flex-1"
                  />
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as 'admin' | 'member')}
                    disabled={isInviting}
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                  <Button type="submit" disabled={isInviting || !inviteEmail}>
                    {isInviting ? 'Inviting...' : 'Invite'}
                  </Button>
                </div>
              </form>
            )}

            {/* Members List */}
            <div>
              <h3 className="font-medium mb-4">
                Members ({members?.length || 0})
              </h3>

              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                </div>
              ) : members && members.length > 0 ? (
                <div className="space-y-3">
                  {members.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between py-3 px-4 border rounded-lg"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center overflow-hidden shrink-0">
                          {member.avatarUrl ? (
                            <img
                              src={member.avatarUrl}
                              alt={member.name || member.email}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <span className="text-sm font-semibold text-primary">
                              {getMemberInitials(member)}
                            </span>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium truncate">
                              {member.name || member.email}
                            </span>
                            <Badge
                              variant={member.role === 'owner' ? 'default' : 'secondary'}
                              className="text-xs capitalize shrink-0"
                            >
                              {member.role}
                            </Badge>
                            {member.status === 'invited' && (
                              <Badge variant="outline" className="text-xs shrink-0">
                                Invited
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground truncate">
                            {member.email}
                          </p>
                        </div>
                      </div>

                      {canManageMembers && member.role !== 'owner' && (
                        <div className="flex items-center gap-2 shrink-0">
                          {onUpdateMemberRole && (
                            <select
                              value={member.role}
                              onChange={(e) =>
                                handleUpdateMemberRole(
                                  member.id,
                                  e.target.value as 'admin' | 'member'
                                )
                              }
                              className="text-sm px-2 py-1 border rounded"
                            >
                              <option value="member">Member</option>
                              <option value="admin">Admin</option>
                            </select>
                          )}
                          {onRemoveMember && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveMember(member.id)}
                            >
                              Remove
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No members yet
                </p>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Danger Zone Tab */}
        {canDeleteOrg && (
          <TabsContent value="danger">
            <div className="space-y-6">
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
                      Type <code className="text-sm bg-muted px-1 py-0.5 rounded">{organization.slug}</code> to confirm
                    </Label>
                    <Input
                      id="delete-confirm"
                      value={deleteConfirmation}
                      onChange={(e) => setDeleteConfirmation(e.target.value)}
                      disabled={isDeleting}
                      placeholder={organization.slug}
                    />
                  </div>

                  {onDeleteOrganization && (
                    <Button
                      variant="destructive"
                      onClick={handleDeleteOrganization}
                      disabled={deleteConfirmation !== organization.slug || isDeleting}
                    >
                      {isDeleting ? 'Deleting...' : 'Delete organization'}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>
        )}
      </Tabs>
    </Card>
  )
}
