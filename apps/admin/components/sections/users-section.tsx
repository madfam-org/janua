'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { adminAPI, type AdminUser } from '@/lib/admin-api'

export function UsersSection() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const data = await adminAPI.getUsers()
        setUsers(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch users')
      } finally {
        setLoading(false)
      }
    }
    fetchUsers()
  }, [])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
        <p className="text-destructive">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-2xl font-bold">User Management</h2>
        <span className="text-muted-foreground text-sm">{users.length} users</span>
      </div>

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
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
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
                    user.status === 'suspended' ? 'bg-destructive/10 text-destructive' :
                    'bg-muted text-muted-foreground'
                  }`}>
                    {user.status}
                  </span>
                </td>
                <td className="px-6 py-4">
                  {user.mfa_enabled ? (
                    <span className="text-green-600 dark:text-green-400">Enabled</span>
                  ) : (
                    <span className="text-muted-foreground">Disabled</span>
                  )}
                </td>
                <td className="text-foreground px-6 py-4 text-sm">{user.organizations_count}</td>
                <td className="text-foreground px-6 py-4 text-sm">{user.sessions_count}</td>
                <td className="text-muted-foreground px-6 py-4 text-sm">
                  {user.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleString() : 'Never'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
