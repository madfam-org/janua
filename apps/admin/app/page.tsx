'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Users,
  Building2,
  Shield,
  Server,
  Activity,
  Settings,
  AlertTriangle,
  BarChart3,
  CreditCard,
  RefreshCw,
  Loader2
} from 'lucide-react'
import { adminAPI, type AdminStats, type SystemHealth, type AdminUser, type AdminOrganization, type ActivityLog } from '@/lib/admin-api'
import { useAuth } from '@/lib/auth'

export default function AdminPage() {
  const router = useRouter()
  const { user, isAuthenticated, isLoading: authLoading, logout, checkSession } = useAuth()
  const [activeSection, setActiveSection] = useState('overview')
  const [isCheckingSession, setIsCheckingSession] = useState(true)

  const sections = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'tenants', label: 'Tenants', icon: Building2 },
    { id: 'users', label: 'All Users', icon: Users },
    { id: 'infrastructure', label: 'Infrastructure', icon: Server },
    { id: 'activity', label: 'Activity', icon: Activity },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  // On mount, check for existing SSO session via cookies
  useEffect(() => {
    const checkExistingSession = async () => {
      if (checkSession) {
        try {
          const hasSession = await checkSession()
          if (hasSession) {
            // Session found via SSO cookies - no redirect needed, user is authenticated
            setIsCheckingSession(false)
            return
          }
        } catch (e) {
          // No valid session
        }
      }
      setIsCheckingSession(false)
    }
    checkExistingSession()
  }, [checkSession])

  // Redirect to /login if not authenticated (after loading completes)
  useEffect(() => {
    if (!authLoading && !isCheckingSession && !isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, authLoading, isCheckingSession, router])

  if (authLoading || isCheckingSession) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Checking session...</p>
        </div>
      </div>
    )
  }

  // If not authenticated, the useEffect will redirect to /login
  // Show loading while redirect is happening
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Redirecting to login...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-2 bg-red-100 rounded-lg">
                <Shield className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Janua Superadmin</h1>
                <p className="text-sm text-gray-500">Internal Platform Management</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="px-3 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full">
                INTERNAL ONLY
              </span>
              <div className="text-sm text-gray-600">
                {user?.email}
              </div>
              <button
                onClick={logout}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-gray-200 min-h-screen">
          <nav className="p-4 space-y-1">
            {sections.map((section) => {
              const Icon = section.icon
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors ${
                    activeSection === section.id
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span className="text-sm font-medium">{section.label}</span>
                </button>
              )
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6">
          {activeSection === 'overview' && <OverviewSection />}
          {activeSection === 'tenants' && <TenantsSection />}
          {activeSection === 'users' && <UsersSection />}
          {activeSection === 'infrastructure' && <InfrastructureSection />}
          {activeSection === 'activity' && <ActivitySection />}
          {activeSection === 'security' && <SecuritySection />}
          {activeSection === 'settings' && <SettingsSection />}
        </main>
      </div>
    </div>
  )
}

function OverviewSection() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsData, healthData] = await Promise.all([
        adminAPI.getStats(),
        adminAPI.getHealth()
      ])
      setStats(statsData)
      setHealth(healthData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-2" />
        <p className="text-red-700">{error}</p>
        <button
          onClick={fetchData}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    )
  }

  const statItems = stats ? [
    { label: 'Total Users', value: stats.total_users.toLocaleString(), change: `${stats.users_last_24h} new (24h)`, icon: Users },
    { label: 'Active Users', value: stats.active_users.toLocaleString(), change: `${Math.round((stats.active_users / stats.total_users) * 100)}% of total`, icon: Users },
    { label: 'Organizations', value: stats.total_organizations.toLocaleString(), change: '', icon: Building2 },
    { label: 'Active Sessions', value: stats.active_sessions.toLocaleString(), change: `${stats.sessions_last_24h} new (24h)`, icon: Activity },
    { label: 'MFA Enabled', value: stats.mfa_enabled_users.toLocaleString(), change: `${Math.round((stats.mfa_enabled_users / stats.total_users) * 100)}% of users`, icon: Shield },
    { label: 'Passkeys', value: stats.passkeys_registered.toLocaleString(), change: '', icon: CreditCard },
  ] : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Platform Overview</h2>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {statItems.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.label} className="bg-white p-6 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <Icon className="h-5 w-5 text-gray-400" />
                {stat.change && (
                  <span className="text-sm text-gray-500">{stat.change}</span>
                )}
              </div>
              <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
              <div className="text-sm text-gray-500">{stat.label}</div>
            </div>
          )
        })}
      </div>

      {/* System Health */}
      {health && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">System Health</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ServiceStatus name="Database" status={health.database} />
              <ServiceStatus name="Cache (Redis)" status={health.cache} />
              <ServiceStatus name="Storage" status={health.storage} />
              <ServiceStatus name="Email" status={health.email} />
              <ServiceStatus name="Environment" status={health.environment} />
              <ServiceStatus name="Version" status={health.version} />
            </div>
            <div className="mt-4 pt-4 border-t border-gray-200">
              <p className="text-sm text-gray-500">
                Uptime: {Math.floor(health.uptime / 3600)}h {Math.floor((health.uptime % 3600) / 60)}m
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ServiceStatus({ name, status }: { name: string; status: string }) {
  const isHealthy = status === 'healthy' || status === 'connected' || status === 'production'
  const statusColor = isHealthy
    ? 'bg-green-100 text-green-800'
    : status === 'degraded'
    ? 'bg-yellow-100 text-yellow-800'
    : 'bg-gray-100 text-gray-800'

  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <div className="text-sm font-medium text-gray-900">{name}</div>
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColor}`}>
        {status}
      </span>
    </div>
  )
}

function TenantsSection() {
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
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-700">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Tenant Management</h2>
        <span className="text-sm text-gray-500">{orgs.length} organizations</span>
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Organization</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Plan</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Members</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((org) => (
              <tr key={org.id} className="border-b border-gray-200 hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{org.name}</div>
                    <div className="text-xs text-gray-500">{org.slug}</div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    org.billing_plan === 'enterprise' ? 'bg-purple-100 text-purple-800' :
                    org.billing_plan === 'pro' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {org.billing_plan}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-900">{org.members_count}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{org.owner_email}</td>
                <td className="px-6 py-4 text-sm text-gray-500">
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

function UsersSection() {
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
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-700">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">User Management</h2>
        <span className="text-sm text-gray-500">{users.length} users</span>
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">MFA</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Orgs</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sessions</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Sign In</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-b border-gray-200 hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">
                      {user.first_name} {user.last_name}
                      {user.is_admin && (
                        <span className="ml-2 px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded">Admin</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">{user.email}</div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    user.status === 'active' ? 'bg-green-100 text-green-800' :
                    user.status === 'suspended' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {user.status}
                  </span>
                </td>
                <td className="px-6 py-4">
                  {user.mfa_enabled ? (
                    <span className="text-green-600">Enabled</span>
                  ) : (
                    <span className="text-gray-400">Disabled</span>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-gray-900">{user.organizations_count}</td>
                <td className="px-6 py-4 text-sm text-gray-900">{user.sessions_count}</td>
                <td className="px-6 py-4 text-sm text-gray-500">
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

function ActivitySection() {
  const [logs, setLogs] = useState<ActivityLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const data = await adminAPI.getActivityLogs()
        setLogs(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch activity logs')
      } finally {
        setLoading(false)
      }
    }
    fetchLogs()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-700">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Activity Logs</h2>

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="divide-y divide-gray-200">
          {logs.map((log) => (
            <div key={log.id} className="p-4 hover:bg-gray-50">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">{log.action}</p>
                  <p className="text-xs text-gray-500">{log.user_email}</p>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(log.created_at).toLocaleString()}
                </span>
              </div>
              {log.ip_address && (
                <p className="mt-1 text-xs text-gray-400">IP: {log.ip_address}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function InfrastructureSection() {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await adminAPI.getHealth()
        setHealth(data)
      } catch (err) {
        console.error('Failed to fetch health:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchHealth()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Infrastructure</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">Backend Services</h3>
          <div className="space-y-3">
            {health && (
              <>
                <ServiceStatus name="API Server" status={health.status} />
                <ServiceStatus name="Database" status={health.database} />
                <ServiceStatus name="Redis Cache" status={health.cache} />
                <ServiceStatus name="Storage" status={health.storage} />
                <ServiceStatus name="Email" status={health.email} />
              </>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">Deployment Info</h3>
          <div className="space-y-2 text-sm">
            {health && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-600">Environment</span>
                  <span className="font-medium">{health.environment}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Version</span>
                  <span className="font-medium">{health.version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Uptime</span>
                  <span className="font-medium">
                    {Math.floor(health.uptime / 3600)}h {Math.floor((health.uptime % 3600) / 60)}m
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function SecuritySection() {
  const [revoking, setRevoking] = useState(false)

  const handleRevokeAllSessions = async () => {
    if (!confirm('Are you sure you want to revoke ALL user sessions? This will log out everyone.')) {
      return
    }
    setRevoking(true)
    try {
      await adminAPI.revokeAllSessions()
      alert('All sessions revoked successfully')
    } catch (err) {
      alert('Failed to revoke sessions')
    } finally {
      setRevoking(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Security & Compliance</h2>

      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold mb-4">Emergency Actions</h3>
        <div className="space-y-4">
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <h4 className="font-medium text-red-900">Revoke All Sessions</h4>
            <p className="text-sm text-red-700 mt-1">
              This will immediately log out all users from the platform.
            </p>
            <button
              onClick={handleRevokeAllSessions}
              disabled={revoking}
              className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              {revoking ? 'Revoking...' : 'Revoke All Sessions'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SettingsSection() {
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleMaintenanceToggle = async () => {
    setSaving(true)
    try {
      await adminAPI.setMaintenanceMode(!maintenanceMode)
      setMaintenanceMode(!maintenanceMode)
    } catch (err) {
      alert('Failed to update maintenance mode')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Platform Settings</h2>

      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium text-gray-900">Maintenance Mode</h4>
              <p className="text-sm text-gray-500">Temporarily disable access to the platform</p>
            </div>
            <button
              onClick={handleMaintenanceToggle}
              disabled={saving}
              className={`px-4 py-2 rounded-lg ${
                maintenanceMode
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              } disabled:opacity-50`}
            >
              {saving ? 'Saving...' : maintenanceMode ? 'Disable' : 'Enable'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
