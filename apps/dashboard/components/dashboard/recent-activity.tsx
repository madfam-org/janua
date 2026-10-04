'use client'

import { useState, useEffect, useCallback } from 'react'
import { getPersonalSessionActivity } from '@/lib/dashboard-api'
import type { PersonalSessionActivity } from '@/lib/dashboard-data'

export function RecentActivity() {
  const [activities, setActivities] = useState<PersonalSessionActivity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)
  const fetchActivities = useCallback(async () => {
    setIsLoading(true)
    setUnavailable(false)
    try {
      setActivities(await getPersonalSessionActivity())
    } catch {
      setActivities([])
      setUnavailable(true)
    } finally {
      setIsLoading(false)
    }
  }, [])
  useEffect(() => { void fetchActivities() }, [fetchActivities])

  if (isLoading) return <p role="status" className="text-muted-foreground text-sm">Loading your session activity…</p>
  if (unavailable) return (
    <div role="status" className="text-muted-foreground space-y-2 text-sm">
      <p>Your session activity is currently unavailable.</p>
      <button onClick={() => void fetchActivities()} className="text-primary underline">Try again</button>
    </div>
  )
  if (activities.length === 0) return <p className="text-muted-foreground text-sm">No recent session activity for your account.</p>
  return (
    <ul aria-label="Your recent session activity" className="space-y-4">
      {activities.map(activity => (
        <li key={activity.id} className="space-y-1 border-b pb-3 last:border-b-0">
          <p className="text-sm font-medium">{activity.action}{activity.revoked ? ' · Revoked session' : ''}</p>
          <p className="text-muted-foreground text-sm">{activity.device}</p>
          {activity.timestamp
            ? <time dateTime={activity.timestamp} className="text-muted-foreground text-xs">{new Date(activity.timestamp).toLocaleString()}</time>
            : <p className="text-muted-foreground text-xs">Time unavailable</p>}
        </li>
      ))}
    </ul>
  )
}
