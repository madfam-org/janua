'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import {
  Users,
  Shield,
  Key,
  Activity,
  Building2,
  Webhook,
  BarChart3,
  Settings
} from 'lucide-react'
import { DashboardStats } from '@/components/dashboard/stats'
import { RecentActivity } from '@/components/dashboard/recent-activity'
import { SystemHealth } from '@/components/dashboard/system-health'
import { IdentityList } from '@/components/identities/identity-list'
import { SessionList } from '@/components/sessions/session-list'
import { OrganizationList } from '@/components/organizations/organization-list'
import { WebhookList } from '@/components/webhooks/webhook-list'
import { AuditList } from '@/components/audit/audit-list'

const VALID_TABS = ['overview', 'identities', 'sessions', 'organizations', 'webhooks', 'audit'] as const
type TabValue = typeof VALID_TABS[number]

// Wrapper component to handle Suspense for useSearchParams
export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardLoading />}>
      <DashboardContent />
    </Suspense>
  )
}

function DashboardLoading() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    </div>
  )
}

function DashboardContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  // Get tab from URL, default to 'overview'
  const tabFromUrl = searchParams.get('tab') as TabValue | null
  const activeTab = tabFromUrl && VALID_TABS.includes(tabFromUrl) ? tabFromUrl : 'overview'

  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<any>(null)

  // Handle tab change by updating URL
  const handleTabChange = useCallback((value: string) => {
    const newTab = value as TabValue
    if (newTab === 'overview') {
      // Remove tab param for overview (clean URL)
      router.push('/', { scroll: false })
    } else {
      router.push(`/?tab=${newTab}`, { scroll: false })
    }
  }, [router])

  useEffect(() => {
    // Check authentication and load user data
    const initializeDashboard = async () => {
      try {
        const token = getCookie('janua_token')
        if (!token) {
          window.location.href = '/login'
          return
        }

        const storedUser = localStorage.getItem('janua_user')
        if (storedUser) {
          setUser(JSON.parse(storedUser))
        }
        
        setIsLoading(false)
      } catch (error) {
        console.error('Failed to initialize dashboard:', error)
        window.location.href = '/login'
      }
    }

    initializeDashboard()
  }, [])

  const handleLogout = () => {
    // Clear authentication (both local and cross-domain for SSO cleanup)
    document.cookie = 'janua_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT'
    document.cookie = 'janua_token=; path=/; domain=.janua.dev; expires=Thu, 01 Jan 1970 00:00:01 GMT'
    localStorage.removeItem('janua_user')
    window.location.href = '/login'
  }

  // Helper function to get cookie value
  const getCookie = (name: string): string | null => {
    if (typeof document === 'undefined') return null
    
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || null
    }
    return null
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Shield className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold">Janua Dashboard</h1>
                <p className="text-sm text-muted-foreground">
                  Welcome back, {user?.name || user?.email || 'User'}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="outline" size="sm" asChild>
                <a href="/settings">
                  <Settings className="h-4 w-4 mr-2" />
                  Settings
                </a>
              </Button>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                Sign out
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="overview">
              <BarChart3 className="h-4 w-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="identities">
              <Users className="h-4 w-4 mr-2" />
              Identities
            </TabsTrigger>
            <TabsTrigger value="sessions">
              <Key className="h-4 w-4 mr-2" />
              Sessions
            </TabsTrigger>
            <TabsTrigger value="organizations">
              <Building2 className="h-4 w-4 mr-2" />
              Organizations
            </TabsTrigger>
            <TabsTrigger value="webhooks">
              <Webhook className="h-4 w-4 mr-2" />
              Webhooks
            </TabsTrigger>
            <TabsTrigger value="audit">
              <Activity className="h-4 w-4 mr-2" />
              Audit
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <DashboardStats />
            
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Recent Activity</CardTitle>
                  <CardDescription>
                    Latest authentication and user events
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <RecentActivity />
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader>
                  <CardTitle>System Health</CardTitle>
                  <CardDescription>
                    Service status and performance metrics
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <SystemHealth />
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="identities">
            <Card>
              <CardHeader>
                <CardTitle>Identities</CardTitle>
                <CardDescription>
                  Manage user identities and authentication methods
                </CardDescription>
              </CardHeader>
              <CardContent>
                <IdentityList />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="sessions">
            <Card>
              <CardHeader>
                <CardTitle>Active Sessions</CardTitle>
                <CardDescription>
                  Monitor and manage active user sessions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SessionList />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="organizations">
            <Card>
              <CardHeader>
                <CardTitle>Organizations</CardTitle>
                <CardDescription>
                  Manage organizations and team structures
                </CardDescription>
              </CardHeader>
              <CardContent>
                <OrganizationList />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="webhooks">
            <Card>
              <CardHeader>
                <CardTitle>Webhooks</CardTitle>
                <CardDescription>
                  Configure and monitor webhook deliveries
                </CardDescription>
              </CardHeader>
              <CardContent>
                <WebhookList />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="audit">
            <Card>
              <CardHeader>
                <CardTitle>Audit Log</CardTitle>
                <CardDescription>
                  View system audit trail and security events
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AuditList />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}