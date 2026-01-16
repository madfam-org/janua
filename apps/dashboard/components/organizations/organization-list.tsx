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
        return 'bg-purple-100 text-purple-800'
      case 'scale':
        return 'bg-blue-100 text-blue-800'
      case 'pro':
        return 'bg-green-100 text-green-800'
      case 'community':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusColor = (status: Organization['status']) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'inactive':
        return 'bg-yellow-100 text-yellow-800'
      case 'suspended':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
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
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading organizations...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <h3 className="text-lg font-semibold mb-2">Failed to Load Organizations</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchOrganizations} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Search and Create Bar */}
      <div className="flex items-center justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            placeholder="Search organizations..."
            className="w-full pl-8 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchOrganizations}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Create Organization
          </Button>
        </div>
      </div>

      {/* Organization Cards */}
      {filteredOrganizations.length === 0 ? (
        <div className="text-center py-12">
          <Building2 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Organizations Found</h3>
          <p className="text-muted-foreground">
            {searchTerm ? 'No organizations match your search' : 'Create your first organization to get started'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredOrganizations.map((org) => (
            <div key={org.id} className="rounded-lg border bg-card p-6 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-muted rounded-lg">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{org.name}</h3>
                    <p className="text-sm text-muted-foreground">/{org.slug}</p>
                  </div>
                </div>
                <Button variant="ghost" size="sm">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Plan</span>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getPlanColor(org.plan)}`}>
                    {org.plan}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(org.status)}`}>
                    {org.status}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Members</span>
                  <div className="flex items-center gap-1">
                    <Users className="h-3 w-3" />
                    <span className="text-sm font-medium">{org.members}</span>
                  </div>
                </div>

                <div className="pt-3 border-t">
                  <div className="text-xs text-muted-foreground">
                    Owner: {org.owner}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Created: {org.createdAt}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
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
