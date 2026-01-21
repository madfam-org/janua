'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Users, Shield, Key, Activity, TrendingUp, TrendingDown } from 'lucide-react'
import { useState, useEffect } from 'react'
import { apiCall } from '@/lib/auth'

// API base URL for production
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface StatCard {
  title: string
  value: string | number
  change: string
  trend: 'up' | 'down' | 'neutral'
  icon: React.ReactNode
}

export function DashboardStats() {
  const [stats, setStats] = useState<StatCard[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      setIsLoading(true)
      setError(null)

      // Use the real admin stats endpoint
      const response = await apiCall(`${API_BASE_URL}/api/v1/admin/stats`)

      if (!response.ok) {
        throw new Error('Failed to fetch stats')
      }

      const data = await response.json()

      // Map API response to stat cards
      // API returns: total_users, active_users, suspended_users, total_sessions, active_sessions, total_organizations
      const statsData: StatCard[] = [
        {
          title: 'Total Identities',
          value: data.total_users?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Users className="text-muted-foreground size-4" />
        },
        {
          title: 'Active Sessions',
          value: data.active_sessions?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Key className="text-muted-foreground size-4" />
        },
        {
          title: 'Organizations',
          value: data.total_organizations?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Shield className="text-muted-foreground size-4" />
        },
        {
          title: 'Active Users',
          value: data.active_users?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Activity className="text-muted-foreground size-4" />
        }
      ]

      setStats(statsData)
    } catch (err) {
      console.error('Error fetching stats:', err)
      setError(err instanceof Error ? err.message : 'Failed to load stats')

      // Fallback to empty stats with error indicators
      setStats([
        {
          title: 'Total Identities',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Users className="text-muted-foreground size-4" />
        },
        {
          title: 'Active Sessions',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Key className="text-muted-foreground size-4" />
        },
        {
          title: 'Organizations',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Shield className="text-muted-foreground size-4" />
        },
        {
          title: 'Active Users',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Activity className="text-muted-foreground size-4" />
        }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, index) => (
          <Card key={index}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <div className="bg-muted h-4 w-24 animate-pulse rounded" />
              <div className="bg-muted size-4 animate-pulse rounded" />
            </CardHeader>
            <CardContent>
              <div className="bg-muted mb-2 h-8 w-16 animate-pulse rounded" />
              <div className="bg-muted h-3 w-32 animate-pulse rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {error && (
        <div className="bg-destructive/10 border-destructive/30 col-span-full rounded-md border p-4">
          <p className="text-destructive text-sm">Error loading dashboard stats: {error}</p>
          <button
            onClick={fetchStats}
            className="text-destructive mt-2 text-sm underline hover:no-underline"
          >
            Try again
          </button>
        </div>
      )}
      
      {stats.map((stat, index) => (
        <Card key={index}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {stat.title}
            </CardTitle>
            {stat.icon}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
            <p className="text-muted-foreground flex items-center text-xs">
              {stat.trend === 'up' ? (
                <TrendingUp className="mr-1 size-3 text-green-600 dark:text-green-400" />
              ) : stat.trend === 'down' ? (
                <TrendingDown className="text-destructive mr-1 size-3" />
              ) : null}
              <span className={
                stat.trend === 'up' ? 'text-green-600 dark:text-green-400' :
                stat.trend === 'down' ? 'text-destructive' :
                'text-muted-foreground'
              }>
                {stat.change}
              </span>
              <span className="text-muted-foreground ml-1">from last month</span>
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}