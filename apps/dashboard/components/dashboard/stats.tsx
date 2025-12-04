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
          icon: <Users className="h-4 w-4 text-muted-foreground" />
        },
        {
          title: 'Active Sessions',
          value: data.active_sessions?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Key className="h-4 w-4 text-muted-foreground" />
        },
        {
          title: 'Organizations',
          value: data.total_organizations?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Shield className="h-4 w-4 text-muted-foreground" />
        },
        {
          title: 'Active Users',
          value: data.active_users?.toLocaleString() || '0',
          change: '+0%',
          trend: 'neutral',
          icon: <Activity className="h-4 w-4 text-muted-foreground" />
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
          icon: <Users className="h-4 w-4 text-muted-foreground" />
        },
        {
          title: 'Active Sessions',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Key className="h-4 w-4 text-muted-foreground" />
        },
        {
          title: 'Organizations',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Shield className="h-4 w-4 text-muted-foreground" />
        },
        {
          title: 'Active Users',
          value: 'Error',
          change: 'N/A',
          trend: 'neutral',
          icon: <Activity className="h-4 w-4 text-muted-foreground" />
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
              <div className="h-4 w-24 bg-muted animate-pulse rounded" />
              <div className="h-4 w-4 bg-muted animate-pulse rounded" />
            </CardHeader>
            <CardContent>
              <div className="h-8 w-16 bg-muted animate-pulse rounded mb-2" />
              <div className="h-3 w-32 bg-muted animate-pulse rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {error && (
        <div className="col-span-full p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">Error loading dashboard stats: {error}</p>
          <button 
            onClick={fetchStats}
            className="mt-2 text-sm text-red-700 underline hover:no-underline"
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
            <p className="text-xs text-muted-foreground flex items-center">
              {stat.trend === 'up' ? (
                <TrendingUp className="h-3 w-3 text-green-500 mr-1" />
              ) : stat.trend === 'down' ? (
                <TrendingDown className="h-3 w-3 text-red-500 mr-1" />
              ) : null}
              <span className={
                stat.trend === 'up' ? 'text-green-500' : 
                stat.trend === 'down' ? 'text-red-500' : 
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