'use client'

import Link from 'next/link'

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
import { getAuthToken, clearAuthCookie, USER_KEY } from '@/lib/auth-storage'
import { RecentActivity } from '@/components/dashboard/recent-activity'
import { UsersDataTable } from '@/components/users/users-data-table'
import { SessionList } from '@/components/sessions/session-list'
import { OrganizationList } from '@/components/organizations/organization-list'
import { WebhookList } from '@/components/webhooks/webhook-list'
import { AuditList } from '@/components/audit/audit-list'

const VALID_TABS = ['overview', 'users', 'sessions', 'organizations', 'webhooks', 'audit'] as const
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
    <div className="bg-background flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="border-primary mx-auto mb-4 size-8 animate-spin rounded-full border-b-2"></div>
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    </div>
  )
}

function DashboardContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  // Get tab from URL, default to 'overview'
  // Support legacy 'identities' tab by mapping to 'users'
  const tabFromUrl = searchParams.get('tab') as string | null
  const mappedTab = tabFromUrl === 'identities' ? 'users' : tabFromUrl
  const activeTab = mappedTab && VALID_TABS.includes(mappedTab as TabValue) ? mappedTab as TabValue : 'overview'

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
        const token = getAuthToken()
        if (!token) {
          window.location.href = '/login'
          return
        }

        const storedUser = localStorage.getItem(USER_KEY)
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
    clearAuthCookie()
    localStorage.removeItem(USER_KEY)
    window.location.href = '/login'
  }


  if (isLoading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="border-primary mx-auto mb-4 size-8 animate-spin rounded-full border-b-2"></div>
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Shield className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Janua Dashboard</h1>
                <p className="text-muted-foreground text-sm">
                  Welcome back, {user?.name || user?.email || 'User'}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="outline" size="sm" asChild>
                <Link href="/settings">
                  <Settings className="mr-2 size-4" />
                  Settings
                </Link>
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
              <BarChart3 className="mr-2 size-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="users">
              <Users className="mr-2 size-4" />
              Users
            </TabsTrigger>
            <TabsTrigger value="sessions">
              <Key className="mr-2 size-4" />
              Sessions
            </TabsTrigger>
            <TabsTrigger value="organizations">
              <Building2 className="mr-2 size-4" />
              Organizations
            </TabsTrigger>
            <TabsTrigger value="webhooks">
              <Webhook className="mr-2 size-4" />
              Webhooks
            </TabsTrigger>
            <TabsTrigger value="audit">
              <Activity className="mr-2 size-4" />
              Audit
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <DashboardStats />

            <Card>
              <CardHeader>
                <CardTitle>Your recent session activity</CardTitle>
                <CardDescription>
                  Recent session activity for your signed-in account
                </CardDescription>
              </CardHeader>
              <CardContent>
                <RecentActivity />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="users">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Users</CardTitle>
                    <CardDescription>
                      Choose an organization to view its members and organization roles.
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/users">Open full view</Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <UsersDataTable />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="sessions">
            <Card>
              <CardHeader>
                <CardTitle>Active Sessions</CardTitle>
                <CardDescription>
                  Monitor and manage your own active sessions
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
                  Organization audit history is not available yet
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
