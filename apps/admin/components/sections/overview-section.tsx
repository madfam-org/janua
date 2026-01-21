'use client'

import { useState, useEffect } from 'react'
import {
  Users,
  Building2,
  Shield,
  Activity,
  CreditCard,
  RefreshCw,
  Loader2,
  AlertTriangle,
} from 'lucide-react'
import { adminAPI, type AdminStats, type SystemHealth } from '@/lib/admin-api'
import { ServiceStatus } from './service-status'

export function OverviewSection() {
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
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
        <AlertTriangle className="text-destructive mx-auto mb-2 size-8" />
        <p className="text-destructive">{error}</p>
        <button
          onClick={fetchData}
          className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-4 rounded-lg px-4 py-2"
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
        <h2 className="text-foreground text-2xl font-bold">Platform Overview</h2>
        <button
          onClick={fetchData}
          className="text-muted-foreground hover:text-foreground border-border hover:bg-muted flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
        >
          <RefreshCw className="size-4" />
          Refresh
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {statItems.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.label} className="bg-card border-border rounded-lg border p-6">
              <div className="mb-2 flex items-center justify-between">
                <Icon className="text-muted-foreground size-5" />
                {stat.change && (
                  <span className="text-muted-foreground text-sm">{stat.change}</span>
                )}
              </div>
              <div className="text-foreground text-2xl font-bold">{stat.value}</div>
              <div className="text-muted-foreground text-sm">{stat.label}</div>
            </div>
          )
        })}
      </div>

      {/* System Health */}
      {health && (
        <div className="bg-card border-border rounded-lg border">
          <div className="border-border border-b px-6 py-4">
            <h3 className="text-foreground text-lg font-semibold">System Health</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <ServiceStatus name="Database" status={health.database} />
              <ServiceStatus name="Cache (Redis)" status={health.cache} />
              <ServiceStatus name="Storage" status={health.storage} />
              <ServiceStatus name="Email" status={health.email} />
              <ServiceStatus name="Environment" status={health.environment} />
              <ServiceStatus name="Version" status={health.version} />
            </div>
            <div className="border-border mt-4 border-t pt-4">
              <p className="text-muted-foreground text-sm">
                Uptime: {Math.floor(health.uptime / 3600)}h {Math.floor((health.uptime % 3600) / 60)}m
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
