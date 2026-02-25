'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Loader2,
  Search,
  RefreshCw,
  Play,
  Pause,
  Trash2,
  AlertCircle,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { adminAPI, type AdminUser } from '@/lib/admin-api'

export function UsersSection() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalUsers, setTotalUsers] = useState(0)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const pageSize = 20

  const fetchUsers = useCallback(async (page = currentPage) => {
    try {
      setLoading(true)
      setError(null)
      const data = await adminAPI.getUsers(page, pageSize)
      // Handle both array and paginated response
      if (Array.isArray(data)) {
        setUsers(data)
        setTotalUsers(data.length)
      } else {
        setUsers(data.items || data)
        setTotalUsers(data.total || (data.items || data).length)
      }
      setCurrentPage(page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch users')
    } finally {
      setLoading(false)
    }
  }, [currentPage])

  useEffect(() => {
    fetchUsers(1)
  }, [])

  const handleAction = async (userId: string, action: string) => {
    setActionLoading(`${userId}-${action}`)
    try {
      switch (action) {
        case 'suspend':
          await adminAPI.updateUserStatus(userId, 'suspended')
          break
        case 'reactivate':
          await adminAPI.updateUserStatus(userId, 'active')
          break
        case 'delete':
          if (confirm('Are you sure you want to delete this user? This cannot be undone.')) {
            await adminAPI.deleteUser(userId)
          } else {
            setActionLoading(null)
            return
          }
          break
      }
      await fetchUsers(currentPage)
    } catch (err) {
      alert(`Action failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setActionLoading(null)
    }
  }

  const filteredUsers = users.filter((user) => {
    const matchesSearch = !searchTerm ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      `${user.first_name} ${user.last_name}`.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || user.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const totalPages = Math.ceil(totalUsers / pageSize)

  if (loading && users.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error && users.length === 0) {
    return (
      <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
        <AlertCircle className="text-destructive mx-auto mb-2 size-8" />
        <p className="text-destructive mb-4">{error}</p>
        <button
          onClick={() => fetchUsers(1)}
          className="bg-primary text-primary-foreground rounded px-4 py-2 text-sm"
        >
          Try Again
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-foreground text-2xl font-bold">User Management</h2>
          <p className="text-muted-foreground text-sm">{totalUsers} users total</p>
        </div>
        <button
          onClick={() => fetchUsers(currentPage)}
          disabled={loading}
          className="text-muted-foreground hover:text-foreground flex items-center gap-2 text-sm"
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
          Refresh
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="text-muted-foreground absolute left-3 top-2.5 size-4" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="border-border bg-card text-foreground w-full rounded-md border py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border-border bg-card text-foreground rounded-md border px-3 py-2 text-sm"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="banned">Banned</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-card border-border rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-border border-b">
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">User</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Status</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">MFA</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Orgs</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Sessions</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Last Sign In</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-muted-foreground px-6 py-12 text-center">
                  {searchTerm || statusFilter !== 'all' ? 'No users match your filters' : 'No users found'}
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id} className="border-border hover:bg-muted/50 border-b">
                  <td className="px-6 py-4">
                    <div>
                      <div className="text-foreground text-sm font-medium">
                        {user.first_name} {user.last_name}
                        {user.is_admin && (
                          <span className="bg-destructive/10 text-destructive ml-2 rounded px-1.5 py-0.5 text-xs">Admin</span>
                        )}
                      </div>
                      <div className="text-muted-foreground text-xs">{user.email}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                      user.status === 'active' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' :
                      user.status === 'suspended' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' :
                      user.status === 'banned' ? 'bg-destructive/10 text-destructive' :
                      'bg-muted text-muted-foreground'
                    }`}>
                      {user.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {user.mfa_enabled ? (
                      <Shield className="size-4 text-green-600 dark:text-green-400" />
                    ) : (
                      <span className="text-muted-foreground text-sm">-</span>
                    )}
                  </td>
                  <td className="text-foreground px-6 py-4 text-sm">{user.organizations_count}</td>
                  <td className="text-foreground px-6 py-4 text-sm">{user.sessions_count}</td>
                  <td className="text-muted-foreground px-6 py-4 text-sm">
                    {user.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1">
                      {user.status === 'active' ? (
                        <button
                          onClick={() => handleAction(user.id, 'suspend')}
                          disabled={actionLoading === `${user.id}-suspend`}
                          className="text-muted-foreground hover:text-foreground rounded p-1 hover:bg-yellow-500/10"
                          title="Suspend User"
                        >
                          {actionLoading === `${user.id}-suspend` ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Pause className="size-4" />
                          )}
                        </button>
                      ) : user.status === 'suspended' ? (
                        <button
                          onClick={() => handleAction(user.id, 'reactivate')}
                          disabled={actionLoading === `${user.id}-reactivate`}
                          className="text-muted-foreground hover:text-foreground rounded p-1 hover:bg-green-500/10"
                          title="Reactivate User"
                        >
                          {actionLoading === `${user.id}-reactivate` ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Play className="size-4" />
                          )}
                        </button>
                      ) : null}
                      <button
                        onClick={() => handleAction(user.id, 'delete')}
                        disabled={actionLoading === `${user.id}-delete`}
                        className="text-muted-foreground hover:text-destructive rounded p-1 hover:bg-red-500/10"
                        title="Delete User"
                      >
                        {actionLoading === `${user.id}-delete` ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Trash2 className="size-4" />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-sm">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchUsers(currentPage - 1)}
              disabled={currentPage <= 1 || loading}
              className="border-border text-muted-foreground disabled:text-muted-foreground/50 flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm disabled:cursor-not-allowed"
            >
              <ChevronLeft className="size-4" />
              Previous
            </button>
            <button
              onClick={() => fetchUsers(currentPage + 1)}
              disabled={currentPage >= totalPages || loading}
              className="border-border text-muted-foreground disabled:text-muted-foreground/50 flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
