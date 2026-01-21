'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import { Separator } from '@janua/ui'
import Link from 'next/link'
import {
  UserPlus,
  ArrowLeft,
  Mail,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  Send,
  Upload,
  Trash2,
} from 'lucide-react'
import { apiCall } from '../../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface Invitation {
  id: string
  email: string
  role: 'member' | 'admin' | 'owner'
  status: 'pending' | 'accepted' | 'expired' | 'revoked'
  invited_by: string
  invited_by_email?: string
  expires_at: string
  created_at: string
  accepted_at?: string
}

interface InvitationStats {
  total: number
  pending: number
  accepted: number
  expired: number
}

const statusConfig = {
  pending: { icon: Clock, color: 'text-yellow-600 dark:text-yellow-400', badge: 'secondary' as const },
  accepted: { icon: CheckCircle2, color: 'text-green-600 dark:text-green-400', badge: 'default' as const },
  expired: { icon: AlertCircle, color: 'text-muted-foreground', badge: 'outline' as const },
  revoked: { icon: XCircle, color: 'text-destructive', badge: 'destructive' as const },
}

export default function InvitationsPage() {
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [stats, setStats] = useState<InvitationStats>({ total: 0, pending: 0, accepted: 0, expired: 0 })
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [newInvite, setNewInvite] = useState({ email: '', role: 'member', message: '' })

  useEffect(() => {
    fetchInvitations()
  }, [])

  const fetchInvitations = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiCall(`${API_BASE_URL}/api/v1/invitations`)

      if (!response.ok) {
        throw new Error('Failed to fetch invitations')
      }

      const data = await response.json()
      const invitationList = data.invitations || data || []
      setInvitations(invitationList)

      // Calculate stats
      const pending = invitationList.filter((i: Invitation) => i.status === 'pending').length
      const accepted = invitationList.filter((i: Invitation) => i.status === 'accepted').length
      const expired = invitationList.filter((i: Invitation) => i.status === 'expired').length
      setStats({
        total: invitationList.length,
        pending,
        accepted,
        expired,
      })
    } catch (err) {
      console.error('Failed to fetch invitations:', err)
      setError(err instanceof Error ? err.message : 'Failed to load invitations')
    } finally {
      setLoading(false)
    }
  }

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newInvite.email) return

    setSending(true)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/invitations`, {
        method: 'POST',
        body: JSON.stringify({
          email: newInvite.email,
          role: newInvite.role,
          message: newInvite.message || undefined,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to send invitation')
      }

      setNewInvite({ email: '', role: 'member', message: '' })
      fetchInvitations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to send invitation')
    } finally {
      setSending(false)
    }
  }

  const handleResend = async (id: string) => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/invitations/${id}/resend`, {
        method: 'POST',
      })

      if (!response.ok) throw new Error('Failed to resend invitation')

      alert('Invitation resent successfully')
      fetchInvitations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to resend invitation')
    }
  }

  const handleRevoke = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this invitation?')) return

    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/invitations/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to revoke invitation')

      fetchInvitations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to revoke invitation')
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const isExpired = (expiresAt: string) => new Date(expiresAt) < new Date()

  const filteredInvitations = invitations.filter((inv) => {
    if (statusFilter === 'all') return true
    return inv.status === statusFilter
  })

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading invitations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center space-x-4">
            <Link href="/settings" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="size-5" />
            </Link>
            <UserPlus className="text-primary size-8" />
            <div>
              <h1 className="text-2xl font-bold">Team Invitations</h1>
              <p className="text-muted-foreground text-sm">
                Invite team members to join your organization
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{stats.total}</div>
              <p className="text-muted-foreground text-sm">Total Invitations</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{stats.pending}</div>
              <p className="text-muted-foreground text-sm">Pending</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">{stats.accepted}</div>
              <p className="text-muted-foreground text-sm">Accepted</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-muted-foreground text-2xl font-bold">{stats.expired}</div>
              <p className="text-muted-foreground text-sm">Expired</p>
            </CardContent>
          </Card>
        </div>

        {/* Invite Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Send className="size-5" />
              Send Invitation
            </CardTitle>
            <CardDescription>
              Invite a new team member by email
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSendInvite} className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="colleague@company.com"
                    value={newInvite.email}
                    onChange={(e) => setNewInvite({ ...newInvite, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <select
                    id="role"
                    className="bg-background h-10 w-full rounded-md border px-3"
                    value={newInvite.role}
                    onChange={(e) => setNewInvite({ ...newInvite, role: e.target.value as 'member' | 'admin' })}
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="message">Custom Message (optional)</Label>
                  <Input
                    id="message"
                    placeholder="Welcome to the team!"
                    value={newInvite.message}
                    onChange={(e) => setNewInvite({ ...newInvite, message: e.target.value })}
                    maxLength={500}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={sending || !newInvite.email}>
                  {sending ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 size-4" />
                      Send Invitation
                    </>
                  )}
                </Button>
                <Button type="button" variant="outline">
                  <Upload className="mr-2 size-4" />
                  Bulk Upload
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Invitations List */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>All Invitations</CardTitle>
                <CardDescription>
                  Manage pending and past invitations
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <select
                  className="bg-background h-9 rounded-md border px-3 text-sm"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="all">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="accepted">Accepted</option>
                  <option value="expired">Expired</option>
                  <option value="revoked">Revoked</option>
                </select>
                <Button variant="outline" size="sm" onClick={fetchInvitations}>
                  <RefreshCw className="size-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {filteredInvitations.length === 0 ? (
              <div className="text-muted-foreground py-8 text-center">
                <Mail className="mx-auto mb-4 size-12 opacity-50" />
                <p>No invitations found</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredInvitations.map((invitation) => {
                  const config = statusConfig[invitation.status]
                  const StatusIcon = config.icon

                  return (
                    <div
                      key={invitation.id}
                      className="flex items-center justify-between rounded-lg border p-4"
                    >
                      <div className="flex items-center gap-4">
                        <div className={`bg-muted rounded-full p-2`}>
                          <StatusIcon className={`size-4 ${config.color}`} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{invitation.email}</span>
                            <Badge variant={config.badge}>{invitation.status}</Badge>
                            <Badge variant="outline">{invitation.role}</Badge>
                          </div>
                          <div className="text-muted-foreground text-sm">
                            Invited {formatDate(invitation.created_at)}
                            {invitation.status === 'pending' && !isExpired(invitation.expires_at) && (
                              <> &bull; Expires {formatDate(invitation.expires_at)}</>
                            )}
                            {invitation.accepted_at && (
                              <> &bull; Accepted {formatDate(invitation.accepted_at)}</>
                            )}
                          </div>
                        </div>
                      </div>
                      {invitation.status === 'pending' && !isExpired(invitation.expires_at) && (
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleResend(invitation.id)}
                          >
                            <Send className="mr-1 size-4" />
                            Resend
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRevoke(invitation.id)}
                          >
                            <Trash2 className="mr-1 size-4" />
                            Revoke
                          </Button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
