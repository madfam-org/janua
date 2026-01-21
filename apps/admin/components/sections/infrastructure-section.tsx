'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { adminAPI, type SystemHealth } from '@/lib/admin-api'
import { ServiceStatus } from './service-status'

export function InfrastructureSection() {
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
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-foreground text-2xl font-bold">Infrastructure</h2>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 text-lg font-semibold">Backend Services</h3>
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

        <div className="bg-card border-border rounded-lg border p-6">
          <h3 className="text-foreground mb-4 text-lg font-semibold">Deployment Info</h3>
          <div className="space-y-2 text-sm">
            {health && (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Environment</span>
                  <span className="text-foreground font-medium">{health.environment}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Version</span>
                  <span className="text-foreground font-medium">{health.version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Uptime</span>
                  <span className="text-foreground font-medium">
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
