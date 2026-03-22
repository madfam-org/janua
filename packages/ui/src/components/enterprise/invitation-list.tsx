import * as React from 'react'
import { Button } from '../button'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface Invitation {
  id: string
  organization_id: string
  email: string
  role: string
  status: 'pending' | 'accepted' | 'expired' | 'revoked'
  invited_by: string
  message?: string
  expires_at: string
  created_at: string
  invite_url: string
  email_sent: boolean
}

export interface InvitationListParams {
  organization_id?: string
  status?: 'pending' | 'accepted' | 'expired' | 'revoked'
  email?: string
  skip?: number
  limit?: number
}

export interface InvitationListResponse {
  invitations: Invitation[]
  total: number
  pending_count: number
  accepted_count: number
  expired_count: number
}

export interface InvitationListProps {
  className?: string
  organizationId?: string
  invitations?: Invitation[]
  onFetchInvitations?: (params?: InvitationListParams) => Promise<InvitationListResponse>
  onResend?: (invitationId: string) => Promise<void>
  onRevoke?: (invitationId: string) => Promise<void>
  onError?: (error: Error) => void
  januaClient?: any
  apiUrl?: string
  showBulkActions?: boolean
  pageSize?: number
}

export function InvitationList({
  className,
  organizationId,
  invitations: initialInvitations,
  onFetchInvitations,
  onResend,
  onRevoke,
  onError,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  showBulkActions = false,
  pageSize = 20,
}: InvitationListProps) {
  const [invitations, setInvitations] = React.useState<Invitation[]>(initialInvitations || [])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [statusFilter, setStatusFilter] = React.useState<string>('all')
  const [searchEmail, setSearchEmail] = React.useState('')
  const [selectedInvitations, setSelectedInvitations] = React.useState<Set<string>>(new Set())
  const [currentPage, setCurrentPage] = React.useState(0)
  const [stats, setStats] = React.useState({
    total: 0,
    pending_count: 0,
    accepted_count: 0,
    expired_count: 0,
  })

  // Fetch invitations
  const fetchInvitations = React.useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const params: InvitationListParams = {
        organization_id: organizationId,
        skip: currentPage * pageSize,
        limit: pageSize,
      }

      if (statusFilter !== 'all') {
        params.status = statusFilter as any
      }

      if (searchEmail) {
        params.email = searchEmail
      }

      let response: InvitationListResponse

      if (januaClient) {
        response = await januaClient.invitations.listInvitations(params)
      } else if (onFetchInvitations) {
        response = await onFetchInvitations(params)
      } else {
        const queryParams = new URLSearchParams()
        if (params.organization_id) queryParams.append('organization_id', params.organization_id)
        if (params.status) queryParams.append('status', params.status)
        if (params.email) queryParams.append('email', params.email)
        if (params.skip !== undefined) queryParams.append('skip', params.skip.toString())
        if (params.limit !== undefined) queryParams.append('limit', params.limit.toString())

        const url = `${apiUrl}/api/v1/invitations?${queryParams.toString()}`
        const res = await fetch(url, { credentials: 'include' })

        if (!res.ok) {
          throw new Error('Failed to fetch invitations')
        }

        response = await res.json()
      }

      setInvitations(response.invitations)
      setStats({
        total: response.total,
        pending_count: response.pending_count,
        accepted_count: response.accepted_count,
        expired_count: response.expired_count,
      })
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch invitations')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }, [organizationId, statusFilter, searchEmail, currentPage, pageSize, januaClient, onFetchInvitations, apiUrl, onError])

  React.useEffect(() => {
    if (!initialInvitations) {
      fetchInvitations()
    }
  }, [initialInvitations, fetchInvitations])

  // Handle resend invitation
  const handleResend = async (invitationId: string) => {
    try {
      if (januaClient) {
        await januaClient.invitations.resendInvitation(invitationId)
      } else if (onResend) {
        await onResend(invitationId)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/invitations/${invitationId}/resend`, {
          method: 'POST',
          credentials: 'include',
        })

        if (!res.ok) {
          throw new Error('Failed to resend invitation')
        }
      }

      await fetchInvitations()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to resend invitation')
      setError(error.message)
      onError?.(error)
    }
  }

  // Handle revoke invitation
  const handleRevoke = async (invitationId: string) => {
    if (!confirm('Are you sure you want to revoke this invitation?')) {
      return
    }

    try {
      if (januaClient) {
        await januaClient.invitations.revokeInvitation(invitationId)
      } else if (onRevoke) {
        await onRevoke(invitationId)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/invitations/${invitationId}`, {
          method: 'DELETE',
          credentials: 'include',
        })

        if (!res.ok) {
          throw new Error('Failed to revoke invitation')
        }
      }

      await fetchInvitations()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to revoke invitation')
      setError(error.message)
      onError?.(error)
    }
  }

  // Copy invite URL to clipboard
  const handleCopyUrl = (inviteUrl: string) => {
    navigator.clipboard.writeText(inviteUrl)
  }

  // Toggle selection
  const toggleSelection = (invitationId: string) => {
    const newSelection = new Set(selectedInvitations)
    if (newSelection.has(invitationId)) {
      newSelection.delete(invitationId)
    } else {
      newSelection.add(invitationId)
    }
    setSelectedInvitations(newSelection)
  }

  // Select all/none
  const toggleSelectAll = () => {
    if (selectedInvitations.size === invitations.length) {
      setSelectedInvitations(new Set())
    } else {
      setSelectedInvitations(new Set(invitations.map(inv => inv.id)))
    }
  }

  // Get status badge
  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: any; label: string }> = {
      pending: { variant: 'default', label: 'Pending' },
      accepted: { variant: 'success', label: 'Accepted' },
      expired: { variant: 'secondary', label: 'Expired' },
      revoked: { variant: 'destructive', label: 'Revoked' },
    }

    const config = variants[status] ?? { variant: 'default' as const, label: 'Pending' }

    return (
      <Badge variant={config.variant as any} className="capitalize">
        {config.label}
      </Badge>
    )
  }

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(date)
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 border rounded-lg">
          <div className="text-2xl font-bold">{stats.total}</div>
          <div className="text-sm text-muted-foreground">Total</div>
        </div>
        <div className="p-4 border rounded-lg">
          <div className="text-2xl font-bold text-blue-600">{stats.pending_count}</div>
          <div className="text-sm text-muted-foreground">Pending</div>
        </div>
        <div className="p-4 border rounded-lg">
          <div className="text-2xl font-bold text-green-600">{stats.accepted_count}</div>
          <div className="text-sm text-muted-foreground">Accepted</div>
        </div>
        <div className="p-4 border rounded-lg">
          <div className="text-2xl font-bold text-gray-600">{stats.expired_count}</div>
          <div className="text-sm text-muted-foreground">Expired</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search by email..."
            value={searchEmail}
            onChange={(e) => setSearchEmail(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border rounded-md"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="accepted">Accepted</option>
          <option value="expired">Expired</option>
          <option value="revoked">Revoked</option>
        </select>
        <Button onClick={() => fetchInvitations()} disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Refresh'}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 border border-red-200 bg-red-50 text-red-800 rounded-md">
          {error}
        </div>
      )}

      {/* Bulk Actions */}
      {showBulkActions && selectedInvitations.size > 0 && (
        <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
          <span className="text-sm font-medium">
            {selectedInvitations.size} selected
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedInvitations(new Set())}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {showBulkActions && (
                  <th className="px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedInvitations.size === invitations.length && invitations.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded"
                    />
                  </th>
                )}
                <th className="px-4 py-3 text-left text-sm font-medium">Email</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Role</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Expires</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {isLoading ? (
                <tr>
                  <td colSpan={showBulkActions ? 6 : 5} className="px-4 py-8 text-center text-muted-foreground">
                    Loading invitations...
                  </td>
                </tr>
              ) : invitations.length === 0 ? (
                <tr>
                  <td colSpan={showBulkActions ? 6 : 5} className="px-4 py-8 text-center text-muted-foreground">
                    No invitations found
                  </td>
                </tr>
              ) : (
                invitations.map((invitation) => (
                  <tr key={invitation.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    {showBulkActions && (
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedInvitations.has(invitation.id)}
                          onChange={() => toggleSelection(invitation.id)}
                          className="rounded"
                        />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium">{invitation.email}</div>
                      {invitation.message && (
                        <div className="text-xs text-muted-foreground mt-1 truncate max-w-xs">
                          {invitation.message}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm capitalize">{invitation.role}</span>
                    </td>
                    <td className="px-4 py-3">{getStatusBadge(invitation.status)}</td>
                    <td className="px-4 py-3">
                      <span className="text-sm">{formatDate(invitation.expires_at)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {invitation.status === 'pending' && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleResend(invitation.id)}
                              title="Resend invitation"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                              </svg>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCopyUrl(invitation.invite_url)}
                              title="Copy invite URL"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRevoke(invitation.id)}
                              title="Revoke invitation"
                              className="text-red-600 hover:text-red-700"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {stats.total > pageSize && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {currentPage * pageSize + 1} to {Math.min((currentPage + 1) * pageSize, stats.total)} of {stats.total}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
              disabled={currentPage === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              onClick={() => setCurrentPage(p => p + 1)}
              disabled={(currentPage + 1) * pageSize >= stats.total}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
