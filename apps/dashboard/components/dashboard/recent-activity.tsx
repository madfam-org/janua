'use client'

import { Avatar } from '@radix-ui/react-avatar'
import { useState, useEffect } from 'react'
import { apiCall } from '@/lib/auth'

// API base URL for production
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface Activity {
  id: string
  user: string
  action: string
  timestamp: string
  type: 'signin' | 'signup' | 'passkey' | 'session' | 'error'
}

interface ActivityLog {
  id: string
  user_id: string
  user_email: string
  action: string
  details: {
    method?: string
  }
  ip_address: string
  user_agent: string
  created_at: string
}

export function RecentActivity() {
  const [activities, setActivities] = useState<Activity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchActivities()
  }, [])

  const fetchActivities = async () => {
    try {
      setIsLoading(true)
      setError(null)

      // Use the real admin activity-logs endpoint
      const response = await apiCall(`${API_BASE_URL}/api/v1/admin/activity-logs?per_page=10`)

      if (!response.ok) {
        throw new Error('Failed to fetch recent activity')
      }

      const data: ActivityLog[] = await response.json()

      // Transform API response to Activity format
      const transformedActivities: Activity[] = data.map((log) => ({
        id: log.id,
        user: log.user_email,
        action: formatAction(log.action, log.details),
        timestamp: formatTimeAgo(log.created_at),
        type: mapActionType(log.action)
      }))

      setActivities(transformedActivities)
    } catch (err) {
      console.error('Error fetching activities:', err)
      setError(err instanceof Error ? err.message : 'Failed to load activities')
      setActivities([])
    } finally {
      setIsLoading(false)
    }
  }

  const formatAction = (action: string, details: { method?: string }): string => {
    const method = details?.method ? ` via ${details.method}` : ''
    switch (action) {
      case 'signin':
        return `Signed in${method}`
      case 'signout':
        return 'Signed out'
      case 'signup':
        return 'Created account'
      case 'password_reset':
        return 'Reset password'
      case 'mfa_enabled':
        return 'Enabled MFA'
      case 'mfa_disabled':
        return 'Disabled MFA'
      case 'passkey_registered':
        return 'Registered passkey'
      default:
        return action.replace(/_/g, ' ')
    }
  }

  const mapActionType = (action: string): Activity['type'] => {
    switch (action) {
      case 'signin':
        return 'signin'
      case 'signup':
        return 'signup'
      case 'passkey_registered':
        return 'passkey'
      case 'signout':
        return 'session'
      default:
        return 'signin'
    }
  }

  const formatTimeAgo = (dateString: string): string => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
    return date.toLocaleDateString()
  }

  const getActivityColor = (type: Activity['type']) => {
    switch (type) {
      case 'signin':
      case 'passkey':
        return 'text-green-600 dark:text-green-400'
      case 'signup':
        return 'text-primary'
      case 'session':
        return 'text-yellow-600 dark:text-yellow-400'
      case 'error':
        return 'text-destructive'
      default:
        return 'text-muted-foreground'
    }
  }

  const getActivityIcon = (type: Activity['type']) => {
    switch (type) {
      case 'signin':
        return '→'
      case 'signup':
        return '+'
      case 'passkey':
        return '🔑'
      case 'session':
        return '⏱'
      case 'error':
        return '⚠'
      default:
        return '•'
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, index) => (
          <div key={index} className="flex items-start space-x-3">
            <div className="bg-muted size-6 animate-pulse rounded" />
            <div className="flex-1 space-y-2">
              <div className="bg-muted h-4 w-32 animate-pulse rounded" />
              <div className="bg-muted h-3 w-24 animate-pulse rounded" />
              <div className="bg-muted h-3 w-16 animate-pulse rounded" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border-destructive/30 rounded-md border p-4">
        <p className="text-destructive text-sm">Error loading recent activity: {error}</p>
        <button
          onClick={fetchActivities}
          className="text-destructive mt-2 text-sm underline hover:no-underline"
        >
          Try again
        </button>
      </div>
    )
  }

  if (activities.length === 0) {
    return (
      <div className="text-muted-foreground p-4 text-center">
        <p className="text-sm">No recent activity found</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {activities.map((activity) => (
        <div key={activity.id} className="flex items-start space-x-3">
          <div className={`mt-1 text-lg ${getActivityColor(activity.type)}`}>
            {getActivityIcon(activity.type)}
          </div>
          <div className="flex-1 space-y-1">
            <p className="text-sm font-medium leading-none">
              {activity.user}
            </p>
            <p className="text-muted-foreground text-sm">
              {activity.action}
            </p>
            <p className="text-muted-foreground text-xs">
              {activity.timestamp}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}