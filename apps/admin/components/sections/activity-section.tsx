'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { adminAPI, type ActivityLog } from '@/lib/admin-api'

export function ActivitySection() {
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
      <h2 className="text-foreground text-2xl font-bold">Activity Logs</h2>

      <div className="bg-card border-border rounded-lg border">
        <div className="divide-border divide-y">
          {logs.map((log) => (
            <div key={log.id} className="hover:bg-muted/50 p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-foreground text-sm font-medium">{log.action}</p>
                  <p className="text-muted-foreground text-xs">{log.user_email}</p>
                </div>
                <span className="text-muted-foreground text-xs">
                  {new Date(log.created_at).toLocaleString()}
                </span>
              </div>
              {log.ip_address && (
                <p className="text-muted-foreground mt-1 text-xs">IP: {log.ip_address}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
