'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@janua/ui'
import { Building2, Key } from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { getPersonalDashboardStats } from '@/lib/dashboard-api'
import type { PersonalDashboardStats } from '@/lib/dashboard-data'

export function DashboardStats() {
  const [stats, setStats] = useState<PersonalDashboardStats>({ organizations: null, activeSessions: null })
  const [isLoading, setIsLoading] = useState(true)
  const fetchStats = useCallback(async () => {
    setIsLoading(true)
    try {
      setStats(await getPersonalDashboardStats())
    } catch {
      setStats({ organizations: null, activeSessions: null })
    } finally {
      setIsLoading(false)
    }
  }, [])
  useEffect(() => { void fetchStats() }, [fetchStats])

  const cards = [
    { title: 'Your organizations', value: stats.organizations, icon: Building2, description: 'Organizations associated with your account' },
    { title: 'Your active sessions', value: stats.activeSessions, icon: Key, description: 'Your unrevoked sessions that have not expired' },
  ]
  const unavailable = !isLoading && cards.some(card => card.value === null)
  return (
    <section aria-label="Your account overview" className="space-y-3">
      <div className="grid gap-4 md:grid-cols-2">
        {cards.map(({ title, value, icon: Icon, description }) => (
          <Card key={title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{title}</CardTitle>
              <Icon className="text-muted-foreground size-4" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{isLoading ? 'Loading…' : value === null ? 'Unavailable' : value.toLocaleString()}</div>
              <p className="text-muted-foreground text-xs">{description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      {unavailable && (
        <div role="status" className="text-muted-foreground text-sm">
          Some account data could not be loaded.{' '}
          <button onClick={() => void fetchStats()} className="text-primary underline">Try again</button>
        </div>
      )}
      <p className="text-muted-foreground text-xs">Organization-wide identity and authentication analytics are not available here yet.</p>
    </section>
  )
}
