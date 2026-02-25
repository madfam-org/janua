'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import { Badge } from '@janua/ui'
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
import { fetchInvitations as apiFetchInvitations, sendInvitation, resendInvitation as apiResendInvitation, revokeInvitation as apiRevokeInvitation, type InvitationInfo } from '@/lib/api'

type Invitation = InvitationInfo

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
  const [_error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [newInvite, setNewInvite] = useState({ email: '', role: 'member', message: '' })
  const [showBulkUpload, setShowBulkUpload] = useState(false)
  const [bulkUploading, setBulkUploading] = useState(false)
  const [bulkCsvText, setBulkCsvText] = useState('')

  useEffect(() => {
    fetchInvitations()
  }, [])

  const fetchInvitations = async () => {
    try {
      setLoading(true)
      setError(null)

      const data = await apiFetchInvitations()
      const invitationList = data.invitations || []
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
      await sendInvitation({
        email: newInvite.email,
        role: newInvite.role,
        message: newInvite.message || undefined,
      })

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
      await apiResendInvitation(id)

      alert('Invitation resent successfully')
      fetchInvitations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to resend invitation')
    }
  }

  const handleRevoke = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this invitation?')) return

    try {
      await apiRevokeInvitation(id)

      fetchInvitations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to revoke invitation')
    }
  }

  const handleBulkUpload = async () => {
    if (!bulkCsvText.trim()) {
      alert('Please enter CSV data')
      return
    }

    setBulkUploading(true)
    const lines = bulkCsvText.trim().split('\n')
    const results = { success: 0, failed: 0, errors: [] as string[] }

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue // Skip empty lines and comments

      const parts = trimmed.split(',').map(p => p.trim())
      const email = parts[0]
      const role = (parts[1] as 'member' | 'admin') || 'member'

      if (!email || !email.includes('@')) {
        results.failed++
        results.errors.push(`Invalid email: ${email || 'empty'}`)
        continue
      }

      try {
        await sendInvitation({ email, role })
        results.success++
      } catch (err) {
        results.failed++
        results.errors.push(`${email}: ${err instanceof Error ? err.message : 'Failed'}`)
      }
    }

    setBulkUploading(false)
    setBulkCsvText('')
    setShowBulkUpload(false)
    fetchInvitations()

    const message = `Bulk upload complete:\n✓ ${results.success} sent successfully\n✗ ${results.failed} failed${results.errors.length > 0 ? '\n\nErrors:\n' + results.errors.slice(0, 5).join('\n') + (results.errors.length > 5 ? '\n...' : '') : ''}`
    alert(message)
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      setBulkCsvText(text)
    }
    reader.readAsText(file)
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
                <Button type="button" variant="outline" onClick={() => setShowBulkUpload(!showBulkUpload)}>
                  <Upload className="mr-2 size-4" />
                  Bulk Upload
                </Button>
              </div>
            </form>

            {/* Bulk Upload Form */}
            {showBulkUpload && (
              <div className="mt-6 space-y-4 rounded-lg border p-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium">Bulk Upload Invitations</h4>
                  <button
                    onClick={() => setShowBulkUpload(false)}
                    className="text-muted-foreground hover:text-foreground text-sm"
                  >
                    Close
                  </button>
                </div>
                <p className="text-muted-foreground text-sm">
                  Upload a CSV file or paste email addresses below. Format: <code className="bg-muted rounded px-1">email,role</code>
                </p>
                <div className="space-y-2">
                  <Label htmlFor="csv-file">Upload CSV File</Label>
                  <Input
                    id="csv-file"
                    type="file"
                    accept=".csv,.txt"
                    onChange={handleFileUpload}
                    className="max-w-xs"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="csv-text">Or paste CSV data</Label>
                  <textarea
                    id="csv-text"
                    value={bulkCsvText}
                    onChange={(e) => setBulkCsvText(e.target.value)}
                    placeholder="john@example.com,member&#10;jane@example.com,admin&#10;# Lines starting with # are ignored"
                    rows={6}
                    className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[120px] w-full rounded-md border px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={handleBulkUpload}
                    disabled={bulkUploading || !bulkCsvText.trim()}
                  >
                    {bulkUploading ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="mr-2 size-4" />
                        Send All Invitations
                      </>
                    )}
                  </Button>
                  <Button variant="outline" onClick={() => { setBulkCsvText(''); setShowBulkUpload(false) }}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
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
                  const config = statusConfig[invitation.status as keyof typeof statusConfig]
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
