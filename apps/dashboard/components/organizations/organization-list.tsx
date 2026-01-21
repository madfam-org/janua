'use client'

import { useState, useEffect } from 'react'
import { Button } from '@janua/ui'
import { MoreHorizontal, Search, Plus, Building2, Users, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { apiCall } from '../../lib/auth'

// API base URL for production
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface Organization {
  id: string
  name: string
  slug: string
  plan: 'community' | 'pro' | 'scale' | 'enterprise'
  members: number
  owner: string
  createdAt: string
  status: 'active' | 'inactive' | 'suspended'
}

interface ApiOrganization {
  id: string
  name: string
  slug: string
  plan?: string
  member_count?: number
  members_count?: number
  owner_email?: string
  owner?: {
    email?: string
  }
  created_at: string
  is_active?: boolean
  status?: string
}

export function OrganizationList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchOrganizations()
  }, [])

  const fetchOrganizations = async () => {
    try {
      setLoading(true)
      setError(null)

      // Try admin endpoint first (for admin users), fall back to regular endpoint
      let response = await apiCall(`${API_BASE_URL}/api/v1/admin/organizations`)

      if (!response.ok) {
        // Fall back to regular endpoint for non-admin users
        response = await apiCall(`${API_BASE_URL}/api/v1/organizations/`)
      }

      if (!response.ok) {
        throw new Error('Failed to fetch organizations')
      }

      const data = await response.json()

      // Handle both array and paginated response formats
      const orgList: ApiOrganization[] = Array.isArray(data) ? data : (data.organizations || data.items || [])

      // Transform API response to match our interface
      const transformedOrgs: Organization[] = orgList.map((org: ApiOrganization) => ({
        id: org.id,
        name: org.name,
        slug: org.slug,
        plan: normalizePlan(org.plan),
        members: org.member_count || org.members_count || 0,
        owner: org.owner_email || org.owner?.email || 'Unknown',
        createdAt: formatDate(org.created_at),
        status: normalizeStatus(org.is_active, org.status)
      }))

      setOrganizations(transformedOrgs)
    } catch (err) {
      console.error('Failed to fetch organizations:', err)
      setError(err instanceof Error ? err.message : 'Failed to load organizations')
    } finally {
      setLoading(false)
    }
  }

  const normalizePlan = (plan?: string): Organization['plan'] => {
    const normalizedPlan = plan?.toLowerCase()
    if (normalizedPlan === 'enterprise') return 'enterprise'
    if (normalizedPlan === 'scale') return 'scale'
    if (normalizedPlan === 'pro') return 'pro'
    return 'community'
  }

  const normalizeStatus = (isActive?: boolean, status?: string): Organization['status'] => {
    if (status) {
      const normalizedStatus = status.toLowerCase()
      if (normalizedStatus === 'suspended') return 'suspended'
      if (normalizedStatus === 'inactive') return 'inactive'
      if (normalizedStatus === 'active') return 'active'
    }
    if (isActive === false) return 'inactive'
    return 'active'
  }

  const formatDate = (dateString: string): string => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    } catch {
      return dateString
    }
  }

  const getPlanColor = (plan: Organization['plan']) => {
    switch (plan) {
      case 'enterprise':
        return 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
      case 'scale':
        return 'bg-primary/10 text-primary'
      case 'pro':
        return 'bg-green-500/10 text-green-600 dark:text-green-400'
      case 'community':
        return 'bg-muted text-muted-foreground'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const getStatusColor = (status: Organization['status']) => {
    switch (status) {
      case 'active':
        return 'bg-green-500/10 text-green-600 dark:text-green-400'
      case 'inactive':
        return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
      case 'suspended':
        return 'bg-destructive/10 text-destructive'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const filteredOrganizations = organizations.filter(org =>
    org.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    org.slug.toLowerCase().includes(searchTerm.toLowerCase()) ||
    org.owner.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading organizations...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Organizations</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchOrganizations} variant="outline">
          <RefreshCw className="mr-2 size-4" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Search and Create Bar */}
      <div className="flex items-center justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="text-muted-foreground absolute left-2 top-2.5 size-4" />
          <input
            placeholder="Search organizations..."
            className="focus:ring-primary w-full rounded-md border py-2 pl-8 pr-4 focus:outline-none focus:ring-2"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchOrganizations}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button size="sm">
            <Plus className="mr-2 size-4" />
            Create Organization
          </Button>
        </div>
      </div>

      {/* Organization Cards */}
      {filteredOrganizations.length === 0 ? (
        <div className="py-12 text-center">
          <Building2 className="text-muted-foreground mx-auto mb-4 size-12" />
          <h3 className="mb-2 text-lg font-semibold">No Organizations Found</h3>
          <p className="text-muted-foreground">
            {searchTerm ? 'No organizations match your search' : 'Create your first organization to get started'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredOrganizations.map((org) => (
            <div key={org.id} className="bg-card rounded-lg border p-6 transition-shadow hover:shadow-md">
              <div className="mb-4 flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="bg-muted rounded-lg p-2">
                    <Building2 className="size-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{org.name}</h3>
                    <p className="text-muted-foreground text-sm">/{org.slug}</p>
                  </div>
                </div>
                <Button variant="ghost" size="sm">
                  <MoreHorizontal className="size-4" />
                </Button>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground text-sm">Plan</span>
                  <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${getPlanColor(org.plan)}`}>
                    {org.plan}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground text-sm">Status</span>
                  <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${getStatusColor(org.status)}`}>
                    {org.status}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground text-sm">Members</span>
                  <div className="flex items-center gap-1">
                    <Users className="size-3" />
                    <span className="text-sm font-medium">{org.members}</span>
                  </div>
                </div>

                <div className="border-t pt-3">
                  <div className="text-muted-foreground text-xs">
                    Owner: {org.owner}
                  </div>
                  <div className="text-muted-foreground text-xs">
                    Created: {org.createdAt}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      <div className="text-muted-foreground flex items-center justify-between text-sm">
        <div>
          Showing {filteredOrganizations.length} of {organizations.length} organizations
        </div>
        <div className="flex items-center gap-4">
          <div>
            Total members: {organizations.reduce((sum, org) => sum + org.members, 0)}
          </div>
        </div>
      </div>
    </div>
  )
}
