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
} from '@janua/ui'
import {
  ArrowLeft,
  Shield,
  Mail,
  Calendar,
  Clock,
  Building2,
  Key,
  Smartphone,
  Loader2,
  AlertCircle,
  RefreshCw,
  Ban,
  Play,
  Pause,
  Trash2,
  Unlock,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { apiCall } from '@/lib/auth'
import { StatusBadge } from '@/components/users/status-badge'
import { RoleBadge } from '@/components/users/role-badge'
import type { UserStatus, UserRole } from '@/components/users/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface UserDetail {
  id: string
  email: string
  first_name?: string
  last_name?: string
  status: UserStatus
  role: UserRole
  is_admin: boolean
  mfa_enabled: boolean
  email_verified: boolean
  phone_number?: string
  avatar_url?: string
  last_sign_in?: string
  last_login?: string
  created_at: string
  updated_at?: string
  sessions_count?: number
  organizations_count?: number
  auth_methods?: string[]
  locked_out?: boolean
  metadata?: Record<string, any>
}

interface SessionInfo {
  id: string
  device_type?: string
  browser?: string
  os?: string
  ip_address: string
  last_active_at: string
  created_at: string
  is_current?: boolean
}

interface OrgMembership {
  id: string
  name: string
  slug: string
  role: string
  joined_at: string
}

export default function UserDetailPage() {
  return (
    <Suspense fallback={<UserDetailLoading />}>
      <UserDetailContent />
    </Suspense>
  )
}

function UserDetailLoading() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="text-muted-foreground size-8 animate-spin" />
      <span className="text-muted-foreground ml-2">Loading user details...</span>
    </div>
  )
}

function UserDetailContent() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const userId = params.id as string
  const initialTab = searchParams.get('tab') || 'profile'

  const [user, setUser] = useState<UserDetail | null>(null)
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [organizations, setOrganizations] = useState<OrgMembership[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchUser = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiCall(`${API_BASE_URL}/api/v1/users/${userId}`)
      if (!response.ok) {
        throw new Error('Failed to fetch user details')
      }
      const userData = await response.json()
      setUser(userData)
    } catch (err) {
      console.error('Failed to fetch user:', err)
      setError(err instanceof Error ? err.message : 'Failed to load user')
    } finally {
      setLoading(false)
    }
  }, [userId])

  const fetchSessions = useCallback(async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/admin/users/${userId}/sessions`)
      if (response.ok) {
        const data = await response.json()
        setSessions(data.items || data || [])
      }
    } catch {
      // Sessions fetch is optional
    }
  }, [userId])

  const fetchOrganizations = useCallback(async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/admin/users/${userId}/organizations`)
      if (response.ok) {
        const data = await response.json()
        setOrganizations(data.items || data || [])
      }
    } catch {
      // Orgs fetch is optional
    }
  }, [userId])

  useEffect(() => {
    fetchUser()
    fetchSessions()
    fetchOrganizations()
  }, [fetchUser, fetchSessions, fetchOrganizations])

  const handleAction = async (action: string) => {
    setActionLoading(action)
    try {
      let endpoint = ''
      let method = 'POST'

      switch (action) {
        case 'suspend':
          endpoint = `/api/v1/users/${userId}/suspend`
          break
        case 'reactivate':
          endpoint = `/api/v1/users/${userId}/reactivate`
          break
        case 'unlock':
          endpoint = `/api/v1/admin/users/${userId}/unlock`
          break
        case 'delete':
          endpoint = `/api/v1/admin/users/${userId}`
          method = 'DELETE'
          break
        case 'reset_password':
          endpoint = `/api/v1/users/${userId}/reset-password`
          break
      }

      const response = await apiCall(`${API_BASE_URL}${endpoint}`, { method })
      if (!response.ok) {
        throw new Error(`Failed to ${action} user`)
      }

      if (action === 'delete') {
        router.push('/users')
        return
      }

      await fetchUser()
    } catch (err) {
      console.error(`Action ${action} failed:`, err)
    } finally {
      setActionLoading(null)
    }
  }

  const revokeSession = async (sessionId: string) => {
    try {
      await apiCall(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, { method: 'DELETE' })
      await fetchSessions()
    } catch (err) {
      console.error('Failed to revoke session:', err)
    }
  }

  if (loading) {
    return <UserDetailLoading />
  }

  if (error || !user) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load User</h3>
        <p className="text-muted-foreground mb-4">{error || 'User not found'}</p>
        <div className="flex gap-2">
          <Button onClick={() => router.push('/users')} variant="outline">
            <ArrowLeft className="mr-2 size-4" />
            Back to Users
          </Button>
          <Button onClick={fetchUser} variant="outline">
            <RefreshCw className="mr-2 size-4" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  const displayName = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.push('/users')}>
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold">{displayName}</h2>
              <StatusBadge status={user.status as UserStatus} />
              <RoleBadge role={user.role as UserRole || (user.is_admin ? 'admin' : 'member')} />
              {user.locked_out && (
                <Badge variant="destructive">Locked</Badge>
              )}
            </div>
            <p className="text-muted-foreground">{user.email}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {user.locked_out && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAction('unlock')}
              disabled={!!actionLoading}
            >
              {actionLoading === 'unlock' ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Unlock className="mr-2 size-4" />}
              Unlock
            </Button>
          )}
          {user.status === 'suspended' ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAction('reactivate')}
              disabled={!!actionLoading}
            >
              {actionLoading === 'reactivate' ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Play className="mr-2 size-4" />}
              Reactivate
            </Button>
          ) : user.status === 'active' ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAction('suspend')}
              disabled={!!actionLoading}
            >
              {actionLoading === 'suspend' ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Pause className="mr-2 size-4" />}
              Suspend
            </Button>
          ) : null}
          <Button
            variant="destructive"
            size="sm"
            onClick={() => handleAction('delete')}
            disabled={!!actionLoading}
          >
            {actionLoading === 'delete' ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Trash2 className="mr-2 size-4" />}
            Delete
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="sessions">Sessions ({sessions.length})</TabsTrigger>
          <TabsTrigger value="organizations">Organizations ({organizations.length})</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="audit">Audit Trail</TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Account Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <InfoRow icon={<Mail className="size-4" />} label="Email" value={user.email} />
                <InfoRow
                  icon={user.email_verified ? <CheckCircle2 className="size-4 text-green-500" /> : <XCircle className="size-4 text-red-500" />}
                  label="Email Verified"
                  value={user.email_verified ? 'Yes' : 'No'}
                />
                {user.phone_number && (
                  <InfoRow icon={<Smartphone className="size-4" />} label="Phone" value={user.phone_number} />
                )}
                <InfoRow icon={<Calendar className="size-4" />} label="Created" value={new Date(user.created_at).toLocaleDateString()} />
                <InfoRow
                  icon={<Clock className="size-4" />}
                  label="Last Sign In"
                  value={user.last_sign_in || user.last_login ? new Date(user.last_sign_in || user.last_login!).toLocaleString() : 'Never'}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Security</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <InfoRow
                  icon={<Shield className="size-4" />}
                  label="MFA"
                  value={user.mfa_enabled ? 'Enabled' : 'Disabled'}
                />
                <InfoRow
                  icon={<Key className="size-4" />}
                  label="Auth Methods"
                  value={(user.auth_methods || ['password']).join(', ')}
                />
                <InfoRow
                  icon={<Building2 className="size-4" />}
                  label="Organizations"
                  value={String(user.organizations_count || organizations.length || 0)}
                />
                <InfoRow
                  icon={<Key className="size-4" />}
                  label="Active Sessions"
                  value={String(user.sessions_count || sessions.length || 0)}
                />
              </CardContent>
            </Card>
          </div>

          {user.metadata && Object.keys(user.metadata).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Metadata</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted overflow-auto rounded-lg p-4 text-sm">
                  {JSON.stringify(user.metadata, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Sessions Tab */}
        <TabsContent value="sessions">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Active Sessions</CardTitle>
              <CardDescription>Sessions currently active for this user.</CardDescription>
            </CardHeader>
            <CardContent>
              {sessions.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center">No active sessions</p>
              ) : (
                <div className="space-y-3">
                  {sessions.map((session) => (
                    <div
                      key={session.id}
                      className="flex items-center justify-between rounded-lg border p-3"
                    >
                      <div className="flex items-center gap-3">
                        <Smartphone className="text-muted-foreground size-5" />
                        <div>
                          <div className="text-sm font-medium">
                            {session.browser || 'Unknown Browser'} on {session.os || session.device_type || 'Unknown Device'}
                          </div>
                          <div className="text-muted-foreground text-xs">
                            IP: {session.ip_address} | Last active: {new Date(session.last_active_at || session.created_at).toLocaleString()}
                          </div>
                        </div>
                        {session.is_current && (
                          <Badge variant="secondary">Current</Badge>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => revokeSession(session.id)}
                        disabled={session.is_current}
                      >
                        Revoke
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Organizations Tab */}
        <TabsContent value="organizations">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Organization Memberships</CardTitle>
              <CardDescription>Organizations this user belongs to.</CardDescription>
            </CardHeader>
            <CardContent>
              {organizations.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center">Not a member of any organization</p>
              ) : (
                <div className="space-y-3">
                  {organizations.map((org) => (
                    <div
                      key={org.id}
                      className="flex items-center justify-between rounded-lg border p-3"
                    >
                      <div className="flex items-center gap-3">
                        <Building2 className="text-muted-foreground size-5" />
                        <div>
                          <div className="text-sm font-medium">{org.name}</div>
                          <div className="text-muted-foreground text-xs">
                            {org.slug} | Joined {new Date(org.joined_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      <Badge variant="outline">{org.role}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Multi-Factor Authentication</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className={`size-5 ${user.mfa_enabled ? 'text-green-500' : 'text-muted-foreground'}`} />
                    <span className="text-sm">{user.mfa_enabled ? 'MFA is enabled' : 'MFA is not enabled'}</span>
                  </div>
                  <Badge variant={user.mfa_enabled ? 'default' : 'secondary'}>
                    {user.mfa_enabled ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Account Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => handleAction('reset_password')}
                  disabled={!!actionLoading}
                >
                  <Key className="mr-2 size-4" />
                  Send Password Reset Email
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Audit Tab */}
        <TabsContent value="audit">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Audit Trail</CardTitle>
              <CardDescription>Recent activity for this user.</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground py-8 text-center">
                Audit trail data is available in the main Audit Logs section.
              </p>
              <div className="flex justify-center">
                <Button variant="outline" onClick={() => router.push(`/?tab=audit&userId=${userId}`)}>
                  View in Audit Logs
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
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
