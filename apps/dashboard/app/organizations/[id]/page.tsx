'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Button,
  Badge,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Input,
} from '@janua/ui'
import {
  ArrowLeft,
  Building2,
  Users,
  Shield,
  Calendar,
  Clock,
  Loader2,
  AlertCircle,
  RefreshCw,
  Trash2,
  UserPlus,
  Crown,
  ArrowRightLeft,
  Settings,
  AlertTriangle,
  Mail,
  ChevronDown,
  X,
  Save,
  Plus,
  Hash,
  FileText,
} from 'lucide-react'
import { apiCall } from '@/lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface Organization {
  id: string
  name: string
  slug: string
  description?: string
  logo_url?: string
  owner_id: string
  members_count?: number
  created_at: string
  updated_at?: string
  metadata?: Record<string, any>
}

interface Member {
  id: string
  user_id: string
  email: string
  first_name?: string
  last_name?: string
  role: string
  joined_at: string
  avatar_url?: string
}

interface OrgRole {
  id: string
  name: string
  description?: string
  permissions: string[]
  is_default?: boolean
  created_at: string
}

export default function OrganizationDetailPage() {
  return (
    <Suspense fallback={<OrganizationDetailLoading />}>
      <OrganizationDetailContent />
    </Suspense>
  )
}

function OrganizationDetailLoading() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="text-muted-foreground size-8 animate-spin" />
      <span className="text-muted-foreground ml-2">Loading organization details...</span>
    </div>
  )
}

function OrganizationDetailContent() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const orgId = params.id as string
  const initialTab = searchParams.get('tab') || 'overview'

  const [org, setOrg] = useState<Organization | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [roles, setRoles] = useState<OrgRole[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Invite member state
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')

  // Settings state
  const [editName, setEditName] = useState('')
  const [editSlug, setEditSlug] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [settingsDirty, setSettingsDirty] = useState(false)

  // Role change state
  const [roleChangeUserId, setRoleChangeUserId] = useState<string | null>(null)
  const [roleChangeValue, setRoleChangeValue] = useState('')

  // Danger zone state
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [transferUserId, setTransferUserId] = useState('')

  const fetchOrg = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}`)
      if (!response.ok) {
        throw new Error('Failed to fetch organization details')
      }
      const orgData = await response.json()
      setOrg(orgData)

      // Initialize settings form
      setEditName(orgData.name || '')
      setEditSlug(orgData.slug || '')
      setEditDescription(orgData.description || '')
      setSettingsDirty(false)
    } catch (err) {
      console.error('Failed to fetch organization:', err)
      setError(err instanceof Error ? err.message : 'Failed to load organization')
    } finally {
      setLoading(false)
    }
  }, [orgId])

  const fetchMembers = useCallback(async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}/members`)
      if (response.ok) {
        const data = await response.json()
        setMembers(data.items || data || [])
      }
    } catch {
      // Members fetch is optional
    }
  }, [orgId])

  const fetchRoles = useCallback(async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}/roles`)
      if (response.ok) {
        const data = await response.json()
        setRoles(data.items || data || [])
      }
    } catch {
      // Roles fetch is optional
    }
  }, [orgId])

  useEffect(() => {
    fetchOrg()
    fetchMembers()
    fetchRoles()
  }, [fetchOrg, fetchMembers, fetchRoles])

  const handleInviteMember = async () => {
    if (!inviteEmail.trim()) return

    setActionLoading('invite')
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}/invite`, {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      })
      if (!response.ok) {
        throw new Error('Failed to invite member')
      }

      setInviteEmail('')
      setInviteRole('member')
      setShowInviteForm(false)
      await fetchMembers()
    } catch (err) {
      console.error('Failed to invite member:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleChangeRole = async (userId: string, newRole: string) => {
    setActionLoading(`role-${userId}`)
    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${orgId}/members/${userId}/role`,
        {
          method: 'PUT',
          body: JSON.stringify({ role: newRole }),
        }
      )
      if (!response.ok) {
        throw new Error('Failed to change role')
      }

      setRoleChangeUserId(null)
      setRoleChangeValue('')
      await fetchMembers()
    } catch (err) {
      console.error('Failed to change role:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    setActionLoading(`remove-${userId}`)
    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${orgId}/members/${userId}`,
        { method: 'DELETE' }
      )
      if (!response.ok) {
        throw new Error('Failed to remove member')
      }

      await fetchMembers()
    } catch (err) {
      console.error('Failed to remove member:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleUpdateSettings = async () => {
    setActionLoading('settings')
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editName,
          slug: editSlug,
          description: editDescription,
        }),
      })
      if (!response.ok) {
        throw new Error('Failed to update organization')
      }

      setSettingsDirty(false)
      await fetchOrg()
    } catch (err) {
      console.error('Failed to update organization:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDeleteOrg = async () => {
    if (deleteConfirmation !== org?.name) return

    setActionLoading('delete')
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error('Failed to delete organization')
      }

      router.push('/organizations')
    } catch (err) {
      console.error('Failed to delete organization:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleTransferOwnership = async () => {
    if (!transferUserId.trim()) return

    setActionLoading('transfer')
    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${orgId}/transfer-ownership`,
        {
          method: 'POST',
          body: JSON.stringify({ user_id: transferUserId }),
        }
      )
      if (!response.ok) {
        throw new Error('Failed to transfer ownership')
      }

      setTransferUserId('')
      await fetchOrg()
      await fetchMembers()
    } catch (err) {
      console.error('Failed to transfer ownership:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleCreateRole = async (roleName: string, roleDescription: string) => {
    setActionLoading('create-role')
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}/roles`, {
        method: 'POST',
        body: JSON.stringify({ name: roleName, description: roleDescription, permissions: [] }),
      })
      if (!response.ok) {
        throw new Error('Failed to create role')
      }

      await fetchRoles()
    } catch (err) {
      console.error('Failed to create role:', err)
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) {
    return <OrganizationDetailLoading />
  }

  if (error || !org) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Organization</h3>
        <p className="text-muted-foreground mb-4">{error || 'Organization not found'}</p>
        <div className="flex gap-2">
          <Button onClick={() => router.push('/organizations')} variant="outline">
            <ArrowLeft className="mr-2 size-4" />
            Back to Organizations
          </Button>
          <Button onClick={fetchOrg} variant="outline">
            <RefreshCw className="mr-2 size-4" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.push('/organizations')}>
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold">{org.name}</h2>
              <Badge variant="outline">{org.slug}</Badge>
            </div>
            <p className="text-muted-foreground">
              {org.description || 'No description'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            <Users className="mr-1 size-3" />
            {org.members_count ?? members.length} members
          </Badge>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="members">Members ({members.length})</TabsTrigger>
          <TabsTrigger value="roles">Roles ({roles.length})</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="danger">Danger Zone</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Organization Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <InfoRow icon={<Building2 className="size-4" />} label="Name" value={org.name} />
                <InfoRow icon={<Hash className="size-4" />} label="Slug" value={org.slug} />
                <InfoRow
                  icon={<FileText className="size-4" />}
                  label="Description"
                  value={org.description || 'None'}
                />
                <InfoRow
                  icon={<Calendar className="size-4" />}
                  label="Created"
                  value={new Date(org.created_at).toLocaleDateString()}
                />
                {org.updated_at && (
                  <InfoRow
                    icon={<Clock className="size-4" />}
                    label="Last Updated"
                    value={new Date(org.updated_at).toLocaleString()}
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Statistics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <InfoRow
                  icon={<Users className="size-4" />}
                  label="Members"
                  value={String(org.members_count ?? members.length)}
                />
                <InfoRow
                  icon={<Shield className="size-4" />}
                  label="Roles"
                  value={String(roles.length)}
                />
                <InfoRow
                  icon={<Crown className="size-4" />}
                  label="Owner ID"
                  value={org.owner_id}
                />
              </CardContent>
            </Card>
          </div>

          {org.metadata && Object.keys(org.metadata).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Metadata</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted overflow-auto rounded-lg p-4 text-sm">
                  {JSON.stringify(org.metadata, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Members Tab */}
        <TabsContent value="members">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">Members</CardTitle>
                  <CardDescription>Manage organization members and their roles.</CardDescription>
                </div>
                <Button size="sm" onClick={() => setShowInviteForm(!showInviteForm)}>
                  {showInviteForm ? (
                    <>
                      <X className="mr-2 size-4" />
                      Cancel
                    </>
                  ) : (
                    <>
                      <UserPlus className="mr-2 size-4" />
                      Invite Member
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Invite Form */}
              {showInviteForm && (
                <div className="mb-6 rounded-lg border p-4">
                  <h4 className="mb-3 text-sm font-medium">Invite New Member</h4>
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label htmlFor="invite-email" className="text-muted-foreground mb-1 block text-xs">
                        Email Address
                      </label>
                      <Input
                        id="invite-email"
                        type="email"
                        placeholder="user@example.com"
                        value={inviteEmail}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInviteEmail(e.target.value)}
                      />
                    </div>
                    <div className="w-40">
                      <label htmlFor="invite-role" className="text-muted-foreground mb-1 block text-xs">
                        Role
                      </label>
                      <select
                        id="invite-role"
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value)}
                        className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                        aria-label="Select role for new member"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                        {roles.map((role) => (
                          <option key={role.id} value={role.name}>
                            {role.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <Button
                      onClick={handleInviteMember}
                      disabled={!inviteEmail.trim() || actionLoading === 'invite'}
                    >
                      {actionLoading === 'invite' ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <Mail className="mr-2 size-4" />
                      )}
                      Send Invite
                    </Button>
                  </div>
                </div>
              )}

              {/* Members List */}
              {members.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center">No members found</p>
              ) : (
                <div className="space-y-3">
                  {members.map((member) => {
                    const displayName =
                      [member.first_name, member.last_name].filter(Boolean).join(' ') ||
                      member.email
                    const isOwner = member.user_id === org.owner_id

                    return (
                      <div
                        key={member.id}
                        className="flex items-center justify-between rounded-lg border p-3"
                      >
                        <div className="flex items-center gap-3">
                          <Users className="text-muted-foreground size-5" />
                          <div>
                            <div className="flex items-center gap-2 text-sm font-medium">
                              {displayName}
                              {isOwner && (
                                <Badge variant="default" className="text-xs">
                                  <Crown className="mr-1 size-3" />
                                  Owner
                                </Badge>
                              )}
                            </div>
                            <div className="text-muted-foreground text-xs">
                              {member.email} | Joined{' '}
                              {new Date(member.joined_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {/* Role Badge / Change Dropdown */}
                          {roleChangeUserId === member.user_id ? (
                            <div className="flex items-center gap-1">
                              <select
                                value={roleChangeValue}
                                onChange={(e) => setRoleChangeValue(e.target.value)}
                                className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-8 rounded-md border px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                                aria-label={`Change role for ${displayName}`}
                              >
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                                {roles.map((role) => (
                                  <option key={role.id} value={role.name}>
                                    {role.name}
                                  </option>
                                ))}
                              </select>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  handleChangeRole(member.user_id, roleChangeValue)
                                }
                                disabled={actionLoading === `role-${member.user_id}`}
                              >
                                {actionLoading === `role-${member.user_id}` ? (
                                  <Loader2 className="size-3 animate-spin" />
                                ) : (
                                  <Save className="size-3" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setRoleChangeUserId(null)
                                  setRoleChangeValue('')
                                }}
                              >
                                <X className="size-3" />
                              </Button>
                            </div>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-xs"
                              onClick={() => {
                                setRoleChangeUserId(member.user_id)
                                setRoleChangeValue(member.role)
                              }}
                              disabled={isOwner}
                            >
                              {member.role}
                              {!isOwner && <ChevronDown className="ml-1 size-3" />}
                            </Button>
                          )}

                          {/* Remove Member */}
                          {!isOwner && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveMember(member.user_id)}
                              disabled={actionLoading === `remove-${member.user_id}`}
                            >
                              {actionLoading === `remove-${member.user_id}` ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <Trash2 className="text-destructive size-4" />
                              )}
                            </Button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Roles Tab */}
        <TabsContent value="roles">
          <RolesTab
            roles={roles}
            actionLoading={actionLoading}
            onCreateRole={handleCreateRole}
          />
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Organization Settings</CardTitle>
              <CardDescription>Update your organization's details.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label htmlFor="org-name" className="text-muted-foreground mb-1 block text-sm">
                  Organization Name
                </label>
                <Input
                  id="org-name"
                  value={editName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    setEditName(e.target.value)
                    setSettingsDirty(true)
                  }}
                  placeholder="Organization name"
                />
              </div>

              <div>
                <label htmlFor="org-slug" className="text-muted-foreground mb-1 block text-sm">
                  Slug
                </label>
                <Input
                  id="org-slug"
                  value={editSlug}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    setEditSlug(e.target.value)
                    setSettingsDirty(true)
                  }}
                  placeholder="organization-slug"
                />
                <p className="text-muted-foreground mt-1 text-xs">
                  Used in URLs. Only lowercase letters, numbers, and hyphens.
                </p>
              </div>

              <div>
                <label htmlFor="org-description" className="text-muted-foreground mb-1 block text-sm">
                  Description
                </label>
                <Input
                  id="org-description"
                  value={editDescription}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    setEditDescription(e.target.value)
                    setSettingsDirty(true)
                  }}
                  placeholder="A brief description of the organization"
                />
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={handleUpdateSettings}
                  disabled={!settingsDirty || actionLoading === 'settings'}
                >
                  {actionLoading === 'settings' ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Save className="mr-2 size-4" />
                  )}
                  Save Changes
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Danger Zone Tab */}
        <TabsContent value="danger" className="space-y-4">
          {/* Transfer Ownership */}
          <Card className="border-orange-200 dark:border-orange-900">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ArrowRightLeft className="size-4 text-orange-500" />
                Transfer Ownership
              </CardTitle>
              <CardDescription>
                Transfer this organization to another member. You will lose owner privileges.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <label htmlFor="transfer-user" className="text-muted-foreground mb-1 block text-xs">
                    New Owner (User ID)
                  </label>
                  <Input
                    id="transfer-user"
                    value={transferUserId}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTransferUserId(e.target.value)}
                    placeholder="Enter the user ID of the new owner"
                  />
                </div>
                <Button
                  variant="outline"
                  onClick={handleTransferOwnership}
                  disabled={!transferUserId.trim() || actionLoading === 'transfer'}
                >
                  {actionLoading === 'transfer' ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <ArrowRightLeft className="mr-2 size-4" />
                  )}
                  Transfer
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Delete Organization */}
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertTriangle className="text-destructive size-4" />
                Delete Organization
              </CardTitle>
              <CardDescription>
                Permanently delete this organization and all associated data. This action cannot be
                undone.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <p className="text-sm">
                  To confirm deletion, type the organization name:{' '}
                  <span className="font-mono font-semibold">{org.name}</span>
                </p>
                <div className="flex items-end gap-3">
                  <div className="flex-1">
                    <Input
                      value={deleteConfirmation}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDeleteConfirmation(e.target.value)}
                      placeholder={org.name}
                      aria-label="Type organization name to confirm deletion"
                    />
                  </div>
                  <Button
                    variant="destructive"
                    onClick={handleDeleteOrg}
                    disabled={deleteConfirmation !== org.name || actionLoading === 'delete'}
                  >
                    {actionLoading === 'delete' ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-2 size-4" />
                    )}
                    Delete Organization
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function RolesTab({
  roles,
  actionLoading,
  onCreateRole,
}: {
  roles: OrgRole[]
  actionLoading: string | null
  onCreateRole: (name: string, description: string) => Promise<void>
}) {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDescription, setNewRoleDescription] = useState('')

  const handleSubmit = async () => {
    if (!newRoleName.trim()) return
    await onCreateRole(newRoleName, newRoleDescription)
    setNewRoleName('')
    setNewRoleDescription('')
    setShowCreateForm(false)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Roles</CardTitle>
            <CardDescription>Manage organization roles and permissions.</CardDescription>
          </div>
          <Button size="sm" onClick={() => setShowCreateForm(!showCreateForm)}>
            {showCreateForm ? (
              <>
                <X className="mr-2 size-4" />
                Cancel
              </>
            ) : (
              <>
                <Plus className="mr-2 size-4" />
                Create Role
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Create Role Form */}
        {showCreateForm && (
          <div className="mb-6 rounded-lg border p-4">
            <h4 className="mb-3 text-sm font-medium">Create New Role</h4>
            <div className="space-y-3">
              <div>
                <label htmlFor="role-name" className="text-muted-foreground mb-1 block text-xs">
                  Role Name
                </label>
                <Input
                  id="role-name"
                  value={newRoleName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewRoleName(e.target.value)}
                  placeholder="e.g. editor, viewer, billing"
                />
              </div>
              <div>
                <label htmlFor="role-description" className="text-muted-foreground mb-1 block text-xs">
                  Description
                </label>
                <Input
                  id="role-description"
                  value={newRoleDescription}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewRoleDescription(e.target.value)}
                  placeholder="Brief description of this role"
                />
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={handleSubmit}
                  disabled={!newRoleName.trim() || actionLoading === 'create-role'}
                >
                  {actionLoading === 'create-role' ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Plus className="mr-2 size-4" />
                  )}
                  Create Role
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Roles List */}
        {roles.length === 0 ? (
          <p className="text-muted-foreground py-8 text-center">No custom roles defined</p>
        ) : (
          <div className="space-y-3">
            {roles.map((role) => (
              <div
                key={role.id}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div className="flex items-center gap-3">
                  <Shield className="text-muted-foreground size-5" />
                  <div>
                    <div className="flex items-center gap-2 text-sm font-medium">
                      {role.name}
                      {role.is_default && (
                        <Badge variant="secondary" className="text-xs">
                          Default
                        </Badge>
                      )}
                    </div>
                    <div className="text-muted-foreground text-xs">
                      {role.description || 'No description'} |{' '}
                      {role.permissions.length} permission
                      {role.permissions.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                </div>
                <Badge variant="outline">{role.permissions.length} permissions</Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        {icon}
        {label}
      </div>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )
}
