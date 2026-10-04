'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Loader2,
  Database,
  HardDrive,
  Wifi,
  WifiOff,
  RefreshCw,
  Clock,
  Activity,
  Server,
  Mail,
  Archive,
} from 'lucide-react'
import { adminAPI, type SystemHealth } from '@/lib/admin-api'
import { ServiceStatus } from './service-status'

interface HealthMetrics {
  db_pool_size: number
  db_pool_used: number
  db_pool_available: number
  redis_memory_used_mb: number
  redis_memory_max_mb: number
  redis_hit_rate: number
  redis_connected_clients: number
  api_avg_response_ms: number
  api_p95_response_ms: number
  api_p99_response_ms: number
  api_requests_per_minute: number
}

type ReportedMetrics = { [Key in keyof HealthMetrics]: number | null }

function reportedMetric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

const AUTO_REFRESH_INTERVAL = 30_000

function MetricBar({
  label,
  value,
  max,
  unit,
  warningThreshold = 0.75,
  criticalThreshold = 0.9,
}: {
  label: string
  value: number | null
  max: number | null
  unit?: string
  warningThreshold?: number
  criticalThreshold?: number
}) {
  const ratio = value !== null && max !== null && max > 0 ? value / max : null
  const percentage = ratio !== null ? Math.min(ratio * 100, 100) : null

  const barColor =
    ratio !== null && ratio >= criticalThreshold
      ? 'bg-red-500 dark:bg-red-400'
      : ratio !== null && ratio >= warningThreshold
        ? 'bg-yellow-500 dark:bg-yellow-400'
        : 'bg-green-500 dark:bg-green-400'

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-foreground font-mono text-xs">
          {value ?? 'Unavailable'}
          {value !== null && unit ? ` ${unit}` : ''}
          {ratio !== null && ` / ${max}${unit ? ` ${unit}` : ''}`}
        </span>
      </div>
      {percentage !== null ? (
        <div
          className="bg-muted h-2 overflow-hidden rounded-full"
          role="progressbar"
          aria-label={label}
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      ) : (
        <p className="text-muted-foreground text-xs">
          Utilization unavailable · Capacity: {max ?? 'Unavailable'}
          {max !== null && unit ? ` ${unit}` : ''}
        </p>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  unit,
  icon: Icon,
  description,
}: {
  label: string
  value: string | number | null
  unit?: string
  icon: React.ElementType
  description?: string
}) {
  return (
    <div className="bg-muted/50 rounded-lg p-3">
      <div className="flex items-center gap-2">
        <Icon className="text-muted-foreground size-4" />
        <span className="text-muted-foreground text-xs">{label}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-foreground text-xl font-semibold">{value ?? 'Unavailable'}</span>
        {value !== null && unit && <span className="text-muted-foreground text-xs">{unit}</span>}
      </div>
      {description && (
        <p className="text-muted-foreground mt-0.5 text-xs">{description}</p>
      )}
    </div>
  )
}

export function InfrastructureSection() {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [metrics, setMetrics] = useState<ReportedMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchHealth = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    try {
      const data = await adminAPI.getHealth()
      setHealth(data)
      setError(null)

      // Dependency health does not measure utilization or traffic. Only show
      // telemetry actually reported by the backend, preserving measured zeroes.
      const extended = data as SystemHealth & Partial<HealthMetrics>
      setMetrics({
        db_pool_size: reportedMetric(extended.db_pool_size),
        db_pool_used: reportedMetric(extended.db_pool_used),
        db_pool_available: reportedMetric(extended.db_pool_available),
        redis_memory_used_mb: reportedMetric(extended.redis_memory_used_mb),
        redis_memory_max_mb: reportedMetric(extended.redis_memory_max_mb),
        redis_hit_rate: reportedMetric(extended.redis_hit_rate),
        redis_connected_clients: reportedMetric(extended.redis_connected_clients),
        api_avg_response_ms: reportedMetric(extended.api_avg_response_ms),
        api_p95_response_ms: reportedMetric(extended.api_p95_response_ms),
        api_p99_response_ms: reportedMetric(extended.api_p99_response_ms),
        api_requests_per_minute: reportedMetric(extended.api_requests_per_minute),
      })

      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch health data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(() => fetchHealth(), AUTO_REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchHealth])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error && !health) {
    return (
      <div className="space-y-6">
        <h2 className="text-foreground text-2xl font-bold">Infrastructure</h2>
        <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
          <WifiOff className="text-destructive mx-auto mb-3 size-8" />
          <p className="text-destructive font-medium">Unable to reach health endpoint</p>
          <p className="text-destructive/70 mt-1 text-sm">{error}</p>
          <button
            onClick={() => fetchHealth(true)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-4 rounded-lg px-4 py-2 text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!health || !metrics) return null

  const overallHealthy =
    health?.status === 'healthy' &&
    health?.database === 'healthy' &&
    health?.cache === 'healthy'

  const serviceList: { name: string; status: string; icon: React.ElementType }[] = [
    { name: 'PostgreSQL', status: health?.database ?? 'unknown', icon: Database },
    { name: 'Redis Cache', status: health?.cache ?? 'unknown', icon: HardDrive },
    { name: 'Email Service', status: health?.email ?? 'unknown', icon: Mail },
    { name: 'Object Storage', status: health?.storage ?? 'unknown', icon: Archive },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-foreground text-2xl font-bold">Infrastructure</h2>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
              overallHealthy
                ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                : 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
            }`}
          >
            <span
              className={`inline-block size-1.5 rounded-full ${
                overallHealthy ? 'bg-green-500' : 'bg-yellow-500'
              }`}
            />
            {overallHealthy ? 'All Systems Operational' : 'Degraded'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-muted-foreground flex items-center gap-1 text-xs">
              <Clock className="size-3" />
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => fetchHealth(true)}
            disabled={refreshing}
            className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg p-2 transition-colors disabled:opacity-50"
            aria-label="Refresh health data"
          >
            <RefreshCw className={`size-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Service Dependencies */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
          <Wifi className="size-5" />
          Service Dependencies
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {serviceList.map((service) => (
            <ServiceStatus
              key={service.name}
              name={service.name}
              status={service.status}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Database Health */}
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
            <Database className="size-5" />
            Database
          </h3>
          <div className="space-y-4">
            <MetricBar
              label="Connection Pool"
              value={metrics.db_pool_used}
              max={metrics.db_pool_size}
              warningThreshold={0.7}
              criticalThreshold={0.9}
            />
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-muted/50 rounded-lg p-2.5 text-center">
                <p className="text-muted-foreground text-xs">Pool Size</p>
                <p className="text-foreground mt-0.5 font-mono text-lg font-semibold">
                  {metrics.db_pool_size ?? 'Unavailable'}
                </p>
              </div>
              <div className="bg-muted/50 rounded-lg p-2.5 text-center">
                <p className="text-muted-foreground text-xs">In Use</p>
                <p className="text-foreground mt-0.5 font-mono text-lg font-semibold">
                  {metrics.db_pool_used ?? 'Unavailable'}
                </p>
              </div>
              <div className="bg-muted/50 rounded-lg p-2.5 text-center">
                <p className="text-muted-foreground text-xs">Available</p>
                <p className="text-foreground mt-0.5 font-mono text-lg font-semibold">
                  {metrics.db_pool_available ?? 'Unavailable'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Redis Cache */}
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
            <HardDrive className="size-5" />
            Redis Cache
          </h3>
          <div className="space-y-4">
            <MetricBar
              label="Memory Usage"
              value={metrics.redis_memory_used_mb}
              max={metrics.redis_memory_max_mb}
              unit="MB"
            />
            <div className="grid grid-cols-2 gap-3">
              <MetricCard
                label="Hit Rate"
                value={metrics.redis_hit_rate?.toFixed(1) ?? null}
                unit="%"
                icon={Activity}
              />
              <MetricCard
                label="Connected Clients"
                value={metrics.redis_connected_clients}
                icon={Wifi}
              />
            </div>
          </div>
        </div>

        {/* API Response Times */}
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
            <Activity className="size-5" />
            API Response Times
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="Average"
              value={metrics.api_avg_response_ms}
              unit="ms"
              icon={Clock}
            />
            <MetricCard
              label="p95"
              value={metrics.api_p95_response_ms}
              unit="ms"
              icon={Clock}
              description="95th percentile"
            />
            <MetricCard
              label="p99"
              value={metrics.api_p99_response_ms}
              unit="ms"
              icon={Clock}
              description="99th percentile"
            />
          </div>
          <div className="mt-4">
            <MetricCard
              label="Throughput"
              value={metrics.api_requests_per_minute}
              unit="req/min"
              icon={Activity}
            />
          </div>
        </div>

        {/* Deployment Info */}
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
            <Server className="size-5" />
            Deployment Info
          </h3>
          <div className="space-y-3 text-sm">
            {health && (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Environment</span>
                  <span className="text-foreground font-medium">{health.environment}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Version</span>
                  <span className="text-foreground font-mono text-xs font-medium">
                    {health.version}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Uptime</span>
                  <span className="text-foreground font-medium">
                    {Math.floor(health.uptime / 86400)}d{' '}
                    {Math.floor((health.uptime % 86400) / 3600)}h{' '}
                    {Math.floor((health.uptime % 3600) / 60)}m
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">API Status</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      health.status === 'healthy'
                        ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                        : 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
                    }`}
                  >
                    {health.status}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Auto-refresh indicator */}
      <p className="text-muted-foreground flex items-center gap-1.5 text-xs">
        <RefreshCw className="size-3" />
        Auto-refreshes every 30 seconds
      </p>
    </div>
  )
}
