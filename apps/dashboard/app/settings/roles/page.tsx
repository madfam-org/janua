'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import Link from 'next/link'
import {
  Shield,
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Plus,
  Trash2,
  Edit2,
  Users,
  Lock,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Star,
} from 'lucide-react'
import { listRoles, listSystemRoles, listPermissions, createRole, updateRole, deleteRole } from '@/lib/api'
import { TOAST_DISMISS_MS } from '@/lib/constants'

interface Role {
  id: string
  organization_id: string
  name: string
  description: string | null
  permissions: string[]
  is_system: boolean
  created_at: string
  updated_at: string
}

interface Permission {
  permission: string
  description: string
  category: string
}

interface SystemRole {
  name: string
  key: string
  description: string
  permissions: string[]
  is_system: boolean
}

// Group permissions by category for better UX
const permissionCategories = [
  { key: 'system', label: 'System', icon: Star },
  { key: 'organization', label: 'Organization', icon: Shield },
  { key: 'users', label: 'Users', icon: Users },
  { key: 'settings', label: 'Settings', icon: Lock },
  { key: 'integrations', label: 'Integrations', icon: Shield },
  { key: 'webhooks', label: 'Webhooks', icon: Shield },
  { key: 'api_keys', label: 'API Keys', icon: Lock },
  { key: 'billing', label: 'Billing', icon: Shield },
]

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [systemRoles, setSystemRoles] = useState<SystemRole[]>([])
  const [availablePermissions, setAvailablePermissions] = useState<Permission[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Form state
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingRole, setEditingRole] = useState<Role | null>(null)
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formPermissions, setFormPermissions] = useState<string[]>([])

  // Expanded categories for permission selection
  const [expandedCategories, setExpandedCategories] = useState<string[]>(['organization', 'users'])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch roles, system roles, and permissions in parallel
      const [rolesData, systemRolesData, permissionsData] = await Promise.all([
        listRoles(),
        listSystemRoles(),
        listPermissions(),
      ])

      const rolesResult = rolesData as unknown as Role[] | { items?: Role[] }
      setRoles(Array.isArray(rolesResult) ? rolesResult : rolesResult.items || [])
      setSystemRoles(systemRolesData as unknown as SystemRole[])
      setAvailablePermissions(permissionsData as unknown as Permission[])
    } catch (err) {
      console.error('Failed to fetch roles data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load roles')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateRole = async () => {
    if (!formName.trim()) {
      setError('Please enter a role name')
      return
    }

    setSaving(true)
    setError(null)

    try {
      await createRole({
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        permissions: formPermissions,
      })

      setSuccess('Role created successfully')
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
      resetForm()
      fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create role')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateRole = async () => {
    if (!editingRole) return
    if (!formName.trim()) {
      setError('Please enter a role name')
      return
    }

    setSaving(true)
    setError(null)

    try {
      await updateRole(editingRole.id, {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        permissions: formPermissions,
      })

      setSuccess('Role updated successfully')
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
      resetForm()
      fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteRole = async (roleId: string, roleName: string) => {
    if (!confirm(`Are you sure you want to delete the role "${roleName}"? This action cannot be undone.`)) {
      return
    }

    try {
      await deleteRole(roleId)

      setSuccess('Role deleted successfully')
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
      fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete role')
    }
  }

  const startEditing = (role: Role) => {
    setEditingRole(role)
    setFormName(role.name)
    setFormDescription(role.description || '')
    setFormPermissions(role.permissions || [])
    setShowCreateForm(false)
  }

  const resetForm = () => {
    setShowCreateForm(false)
    setEditingRole(null)
    setFormName('')
    setFormDescription('')
    setFormPermissions([])
  }

  const togglePermission = (permission: string) => {
    setFormPermissions((prev) =>
      prev.includes(permission)
        ? prev.filter((p) => p !== permission)
        : [...prev, permission]
    )
  }

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    )
  }

  const getPermissionsByCategory = (category: string) => {
    return availablePermissions.filter((p) => p.category === category)
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading roles...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/settings" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="size-5" />
              </Link>
              <Shield className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Roles & Permissions</h1>
                <p className="text-muted-foreground text-sm">
                  Manage role-based access control for your organization
                </p>
              </div>
            </div>
            <Button onClick={() => { resetForm(); setShowCreateForm(true); }}>
              <Plus className="mr-2 size-4" />
              Create Role
            </Button>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {success && (
          <Card className="border-green-500">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-5" />
                <span>{success}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Create/Edit Form */}
        {(showCreateForm || editingRole) && (
          <Card className="border-primary">
            <CardHeader>
              <CardTitle>
                {editingRole ? `Edit Role: ${editingRole.name}` : 'Create New Role'}
              </CardTitle>
              <CardDescription>
                {editingRole
                  ? editingRole.is_system
                    ? 'System roles can only have their description updated'
                    : 'Update this role\'s name, description, and permissions'
                  : 'Create a custom role with specific permissions'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="role_name">Role Name</Label>
                  <Input
                    id="role_name"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g., Developer, Support, Billing Admin"
                    disabled={editingRole?.is_system}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="role_description">Description</Label>
                  <Input
                    id="role_description"
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                    placeholder="Brief description of this role"
                  />
                </div>
              </div>

              {/* Permission Selection */}
              {!editingRole?.is_system && (
                <div className="space-y-4">
                  <Label>Permissions</Label>
                  <div className="rounded-lg border">
                    {permissionCategories.map((category) => {
                      const perms = getPermissionsByCategory(category.key)
                      if (perms.length === 0) return null
                      const isExpanded = expandedCategories.includes(category.key)
                      const selectedCount = perms.filter((p) =>
                        formPermissions.includes(p.permission)
                      ).length

                      return (
                        <div key={category.key} className="border-b last:border-b-0">
                          <button
                            type="button"
                            onClick={() => toggleCategory(category.key)}
                            className="hover:bg-muted/50 flex w-full items-center justify-between p-4"
                          >
                            <div className="flex items-center gap-3">
                              <category.icon className="text-muted-foreground size-5" />
                              <span className="font-medium">{category.label}</span>
                              {selectedCount > 0 && (
                                <Badge variant="secondary">{selectedCount} selected</Badge>
                              )}
                            </div>
                            {isExpanded ? (
                              <ChevronDown className="text-muted-foreground size-5" />
                            ) : (
                              <ChevronRight className="text-muted-foreground size-5" />
                            )}
                          </button>
                          {isExpanded && (
                            <div className="border-t bg-muted/20 p-4">
                              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                                {perms.map((perm) => (
                                  <label
                                    key={perm.permission}
                                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                                      formPermissions.includes(perm.permission)
                                        ? 'border-primary bg-primary/5'
                                        : 'hover:bg-muted bg-background'
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={formPermissions.includes(perm.permission)}
                                      onChange={() => togglePermission(perm.permission)}
                                      className="mt-1"
                                    />
                                    <div>
                                      <div className="font-mono text-sm">{perm.permission}</div>
                                      <div className="text-muted-foreground text-sm">
                                        {perm.description}
                                      </div>
                                    </div>
                                  </label>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={resetForm}>
                  Cancel
                </Button>
                <Button
                  onClick={editingRole ? handleUpdateRole : handleCreateRole}
                  disabled={saving}
                >
                  {saving ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : editingRole ? (
                    <CheckCircle2 className="mr-2 size-4" />
                  ) : (
                    <Plus className="mr-2 size-4" />
                  )}
                  {editingRole ? 'Save Changes' : 'Create Role'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* System Roles */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Star className="size-5" />
                  System Roles
                </CardTitle>
                <CardDescription>
                  Built-in roles that cannot be deleted (permissions are predefined)
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {systemRoles.map((role) => (
                <div
                  key={role.key}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="bg-muted rounded-lg p-2">
                      <Shield className="size-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{role.name}</span>
                        <Badge variant="secondary">System</Badge>
                      </div>
                      <p className="text-muted-foreground mt-1 text-sm">
                        {role.description}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {role.permissions.slice(0, 5).map((perm) => (
                          <Badge key={perm} variant="outline" className="text-xs">
                            {perm}
                          </Badge>
                        ))}
                        {role.permissions.length > 5 && (
                          <Badge variant="outline" className="text-xs">
                            +{role.permissions.length - 5} more
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Custom Roles */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users className="size-5" />
                  Custom Roles
                </CardTitle>
                <CardDescription>
                  Organization-specific roles with custom permissions
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={fetchData}>
                <RefreshCw className="mr-2 size-4" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {roles.filter((r) => !r.is_system).length === 0 ? (
              <div className="py-8 text-center">
                <Shield className="text-muted-foreground mx-auto size-12" />
                <h3 className="mt-4 text-lg font-medium">No custom roles yet</h3>
                <p className="text-muted-foreground mt-2">
                  Create custom roles to define specific permission sets for your team.
                </p>
                <Button
                  className="mt-4"
                  onClick={() => {
                    resetForm()
                    setShowCreateForm(true)
                  }}
                >
                  <Plus className="mr-2 size-4" />
                  Create Custom Role
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {roles
                  .filter((r) => !r.is_system)
                  .map((role) => (
                    <div
                      key={role.id}
                      className="flex items-center justify-between rounded-lg border p-4"
                    >
                      <div className="flex items-center gap-4">
                        <div className="bg-muted rounded-lg p-2">
                          <Shield className="size-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{role.name}</span>
                            <Badge variant="default">Custom</Badge>
                          </div>
                          {role.description && (
                            <p className="text-muted-foreground mt-1 text-sm">
                              {role.description}
                            </p>
                          )}
                          <div className="text-muted-foreground mt-1 text-sm">
                            Created {new Date(role.created_at).toLocaleDateString()}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {role.permissions.slice(0, 5).map((perm) => (
                              <Badge key={perm} variant="outline" className="text-xs">
                                {perm}
                              </Badge>
                            ))}
                            {role.permissions.length > 5 && (
                              <Badge variant="outline" className="text-xs">
                                +{role.permissions.length - 5} more
                              </Badge>
                            )}
                            {role.permissions.length === 0 && (
                              <Badge variant="outline" className="text-muted-foreground text-xs">
                                No permissions
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => startEditing(role)}
                        >
                          <Edit2 className="mr-2 size-4" />
                          Edit
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                          onClick={() => handleDeleteRole(role.id, role.name)}
                        >
                          <Trash2 className="mr-2 size-4" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Documentation */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Understanding Roles & Permissions</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground space-y-4 text-sm">
            <div>
              <h4 className="text-foreground mb-1 font-medium">Role Hierarchy</h4>
              <p>
                System roles follow a hierarchy: <strong>Owner</strong> &gt; <strong>Admin</strong>{' '}
                &gt; <strong>Member</strong> &gt; <strong>Viewer</strong>. Higher roles inherit
                permissions from lower roles.
              </p>
            </div>
            <div>
              <h4 className="text-foreground mb-1 font-medium">Permission Format</h4>
              <p>
                Permissions use the format <code>resource:action</code> (e.g.,{' '}
                <code>users:read</code>). Wildcards like <code>users:*</code> grant all actions on a
                resource.
              </p>
            </div>
            <div>
              <h4 className="text-foreground mb-1 font-medium">Custom Roles</h4>
              <p>
                Create custom roles to define specific permission sets for your organization. Custom
                roles can be assigned to members alongside or instead of system roles.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
