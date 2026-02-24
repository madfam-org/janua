'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Loader2,
  Search,
  RefreshCw,
  Building2,
  Users,
  AlertCircle,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { adminAPI, type AdminOrganization } from '@/lib/admin-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface OrgMember {
  id: string
  email: string
  first_name?: string
  last_name?: string
  role: string
  joined_at?: string
}

export function TenantsSection() {
  const [orgs, setOrgs] = useState<AdminOrganization[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [planFilter, setPlanFilter] = useState<string>('all')
  const [expandedOrg, setExpandedOrg] = useState<string | null>(null)
  const [orgMembers, setOrgMembers] = useState<Record<string, OrgMember[]>>({})
  const [membersLoading, setMembersLoading] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 20

  const fetchOrgs = useCallback(async (page = currentPage) => {
    try {
      setLoading(true)
      setError(null)
      const data = await adminAPI.getOrganizations(page, pageSize)
      if (Array.isArray(data)) {
        setOrgs(data)
      } else {
        setOrgs((data as any).items || data)
      }
      setCurrentPage(page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch organizations')
    } finally {
      setLoading(false)
    }
  }, [currentPage])

  useEffect(() => {
    fetchOrgs(1)
  }, [])

  const fetchMembers = async (orgId: string) => {
    if (orgMembers[orgId]) return
    setMembersLoading(orgId)
    try {
      const token = localStorage.getItem('janua_access_token')
      const response = await fetch(`${API_URL}/api/v1/organizations/${orgId}/members`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
      if (response.ok) {
        const data = await response.json()
        setOrgMembers((prev) => ({ ...prev, [orgId]: data.items || data || [] }))
      }
    } catch (err) {
      console.error('Failed to fetch members:', err)
    } finally {
      setMembersLoading(null)
    }
  }

  const toggleExpanded = (orgId: string) => {
    if (expandedOrg === orgId) {
      setExpandedOrg(null)
    } else {
      setExpandedOrg(orgId)
      fetchMembers(orgId)
    }
  }

  const deleteOrg = async (orgId: string) => {
    if (!confirm('Are you sure you want to delete this organization? This cannot be undone.')) return
    setActionLoading(`delete-${orgId}`)
    try {
      const token = localStorage.getItem('janua_access_token')
      const response = await fetch(`${API_URL}/api/v1/admin/organizations/${orgId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
      if (response.ok) {
        await fetchOrgs(currentPage)
      } else {
        alert('Failed to delete organization')
      }
    } catch (err) {
      alert('Failed to delete organization')
    } finally {
      setActionLoading(null)
    }
  }

  const filteredOrgs = orgs.filter((org) => {
    const matchesSearch =
      !searchTerm ||
      org.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      org.slug.toLowerCase().includes(searchTerm.toLowerCase()) ||
      org.owner_email.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesPlan = planFilter === 'all' || org.billing_plan === planFilter
    return matchesSearch && matchesPlan
  })

  if (loading && orgs.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error && orgs.length === 0) {
    return (
      <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
        <AlertCircle className="text-destructive mx-auto mb-2 size-8" />
        <p className="text-destructive mb-4">{error}</p>
        <button
          onClick={() => fetchOrgs(1)}
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
          <h2 className="text-foreground text-2xl font-bold">Tenant Management</h2>
          <p className="text-muted-foreground text-sm">{orgs.length} organizations</p>
        </div>
        <button
          onClick={() => fetchOrgs(currentPage)}
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
            placeholder="Search by name, slug, or owner email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="border-border bg-card text-foreground w-full rounded-md border py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={planFilter}
          onChange={(e) => setPlanFilter(e.target.value)}
          className="border-border bg-card text-foreground rounded-md border px-3 py-2 text-sm"
        >
          <option value="all">All Plans</option>
          <option value="enterprise">Enterprise</option>
          <option value="pro">Pro</option>
          <option value="free">Free</option>
          <option value="community">Community</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-card border-border rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-border border-b">
              <th className="text-muted-foreground w-8 px-3 py-3"></th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">
                Organization
              </th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">
                Plan
              </th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">
                Members
              </th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">
                Owner
              </th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">
                Created
              </th>
              <th className="text-muted-foreground px-6 py-3 text-left text-xs font-medium uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredOrgs.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-muted-foreground px-6 py-12 text-center">
                  {searchTerm || planFilter !== 'all'
                    ? 'No organizations match your filters'
                    : 'No organizations found'}
                </td>
              </tr>
            ) : (
              filteredOrgs.map((org) => (
                <>
                  <tr
                    key={org.id}
                    className="border-border hover:bg-muted/50 cursor-pointer border-b"
                    onClick={() => toggleExpanded(org.id)}
                  >
                    <td className="px-3 py-4">
                      {expandedOrg === org.id ? (
                        <ChevronUp className="text-muted-foreground size-4" />
                      ) : (
                        <ChevronDown className="text-muted-foreground size-4" />
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="bg-muted flex size-8 items-center justify-center rounded">
                          <Building2 className="size-4" />
                        </div>
                        <div>
                          <div className="text-foreground text-sm font-medium">{org.name}</div>
                          <div className="text-muted-foreground text-xs">{org.slug}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-medium ${
                          org.billing_plan === 'enterprise'
                            ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
                            : org.billing_plan === 'pro'
                              ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                              : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {org.billing_plan}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        <Users className="text-muted-foreground size-3" />
                        <span className="text-foreground text-sm">{org.members_count}</span>
                      </div>
                    </td>
                    <td className="text-muted-foreground px-6 py-4 text-sm">{org.owner_email}</td>
                    <td className="text-muted-foreground px-6 py-4 text-sm">
                      {new Date(org.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => deleteOrg(org.id)}
                        disabled={actionLoading === `delete-${org.id}`}
                        className="text-muted-foreground hover:text-destructive rounded p-1 hover:bg-red-500/10"
                        title="Delete Organization"
                      >
                        {actionLoading === `delete-${org.id}` ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Trash2 className="size-4" />
                        )}
                      </button>
                    </td>
                  </tr>
                  {/* Expanded Member List */}
                  {expandedOrg === org.id && (
                    <tr key={`${org.id}-members`}>
                      <td colSpan={7} className="bg-muted/30 px-6 py-4">
                        {membersLoading === org.id ? (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="size-5 animate-spin" />
                            <span className="text-muted-foreground ml-2 text-sm">
                              Loading members...
                            </span>
                          </div>
                        ) : (orgMembers[org.id] || []).length === 0 ? (
                          <p className="text-muted-foreground py-4 text-center text-sm">
                            No members found
                          </p>
                        ) : (
                          <div>
                            <h4 className="text-foreground mb-2 text-sm font-medium">
                              Members ({(orgMembers[org.id] || []).length})
                            </h4>
                            <div className="grid gap-2">
                              {(orgMembers[org.id] || []).map((member) => (
                                <div
                                  key={member.id}
                                  className="bg-card flex items-center justify-between rounded border px-4 py-2"
                                >
                                  <div>
                                    <span className="text-foreground text-sm font-medium">
                                      {member.first_name
                                        ? `${member.first_name} ${member.last_name || ''}`
                                        : member.email}
                                    </span>
                                    <span className="text-muted-foreground ml-2 text-xs">
                                      {member.email}
                                    </span>
                                  </div>
                                  <span
                                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                                      member.role === 'owner'
                                        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
                                        : member.role === 'admin'
                                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                                          : 'bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {member.role}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground text-sm">
          Showing {filteredOrgs.length} organizations
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchOrgs(currentPage - 1)}
            disabled={currentPage <= 1 || loading}
            className="border-border text-muted-foreground disabled:text-muted-foreground/50 flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm disabled:cursor-not-allowed"
          >
            <ChevronLeft className="size-4" />
            Previous
          </button>
          <button
            onClick={() => fetchOrgs(currentPage + 1)}
            disabled={filteredOrgs.length < pageSize || loading}
            className="border-border text-muted-foreground disabled:text-muted-foreground/50 flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm disabled:cursor-not-allowed"
          >
            Next
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
