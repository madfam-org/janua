'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { adminAPI, type AdminOrganization } from '@/lib/admin-api'

export function TenantsSection() {
  const [orgs, setOrgs] = useState<AdminOrganization[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchOrgs = async () => {
      try {
        const data = await adminAPI.getOrganizations()
        setOrgs(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch organizations')
      } finally {
        setLoading(false)
      }
    }
    fetchOrgs()
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
        <h2 className="text-foreground text-2xl font-bold">Tenant Management</h2>
        <span className="text-muted-foreground text-sm">{orgs.length} organizations</span>
      </div>

      <div className="bg-card border-border rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-border border-b">
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Organization</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Plan</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Members</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Owner</th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">Created</th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((org) => (
              <tr key={org.id} className="border-border hover:bg-muted/50 border-b">
                <td className="px-6 py-4">
                  <div>
                    <div className="text-foreground text-sm font-medium">{org.name}</div>
                    <div className="text-muted-foreground text-xs">{org.slug}</div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                    org.billing_plan === 'enterprise' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' :
                    org.billing_plan === 'pro' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' :
                    'bg-muted text-muted-foreground'
                  }`}>
                    {org.billing_plan}
                  </span>
                </td>
                <td className="text-foreground px-6 py-4 text-sm">{org.members_count}</td>
                <td className="text-muted-foreground px-6 py-4 text-sm">{org.owner_email}</td>
                <td className="text-muted-foreground px-6 py-4 text-sm">
                  {new Date(org.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
