'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@plinto/ui'
import { 
  User, 
  Shield, 
  Key, 
  Activity, 
  Settings, 
  LogOut,
  Mail,
  Calendar,
  CheckCircle,
  XCircle,
  Clock,
  Users,
  Smartphone,
  RefreshCw,
  Zap,
  Globe,
  Database,
  Info
} from 'lucide-react'
import { useEnvironment, useDemoFeatures } from '@/hooks/useEnvironment'

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [sessions, setSessions] = useState<any[]>([])
  const [resettingDemo, setResettingDemo] = useState(false)

  const { 
    isDemo, 
    environment,
    performanceMetrics,
    showDemoNotice,
    mounted 
  } = useEnvironment()
  
  const { 
    generateSampleUsers, 
    resetDemoData, 
    shouldSimulatePerformance 
  } = useDemoFeatures()

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const plinto = (window as any).plinto
      if (!plinto) {
        throw new Error('Plinto SDK not initialized')
      }

      const currentUser = await plinto.getUser()
      if (!currentUser) {
        router.push('/signin')
        return
      }

      setUser(currentUser)
      
      // Get user sessions
      const userSessions = await plinto.getSessions()
      setSessions(userSessions || [])
    } catch (err) {
      console.error('Auth check failed:', err)
      router.push('/signin')
    } finally {
      setLoading(false)
    }
  }

  const handleSignOut = async () => {
    try {
      const plinto = (window as any).plinto
      await plinto.signOut()
      router.push('/signin')
    } catch (err) {
      console.error('Sign out failed:', err)
    }
  }

  const handleResetDemo = async () => {
    if (!isDemo) return
    
    setResettingDemo(true)
    try {
      const success = await resetDemoData()
      if (success) {
        // Refresh the page after reset
        window.location.reload()
      }
    } catch (err) {
      console.error('Demo reset failed:', err)
    } finally {
      setResettingDemo(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">P</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-xl font-bold text-gray-900 dark:text-white">Plinto Dashboard</span>
                {mounted && isDemo && showDemoNotice?.() && (
                  <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs font-medium rounded">
                    DEMO
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {mounted && isDemo && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResetDemo}
                  disabled={resettingDemo}
                >
                  {resettingDemo ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Resetting...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Reset Demo
                    </>
                  )}
                </Button>
              )}
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {user?.email}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSignOut}
              >
                <LogOut className="h-4 w-4 mr-2" />
                Sign out
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-8">
            Welcome back{user?.name ? `, ${user.name}` : ''}!
          </h1>

          {/* Stats Grid */}
          <div className={`grid grid-cols-1 md:grid-cols-2 ${mounted && isDemo ? 'lg:grid-cols-5' : 'lg:grid-cols-4'} gap-6 mb-8`}>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Account Status</CardTitle>
                <Shield className="h-4 w-4 text-gray-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">Active</div>
                <p className="text-xs text-gray-500">
                  {user?.email_verified ? 'Email verified' : 'Email not verified'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
                <Activity className="h-4 w-4 text-gray-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{sessions.length}</div>
                <p className="text-xs text-gray-500">Across all devices</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">MFA Status</CardTitle>
                <Smartphone className="h-4 w-4 text-gray-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {user?.mfa_enabled ? 'Enabled' : 'Disabled'}
                </div>
                <p className="text-xs text-gray-500">
                  {user?.mfa_enabled ? 'Your account is protected' : 'Add extra security'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Organizations</CardTitle>
                <Users className="h-4 w-4 text-gray-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">1</div>
                <p className="text-xs text-gray-500">Personal workspace</p>
              </CardContent>
            </Card>

            {mounted && isDemo && (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Edge Performance</CardTitle>
                  <Zap className="h-4 w-4 text-gray-400" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{performanceMetrics.edgeVerificationMs}ms</div>
                  <p className="text-xs text-gray-500">
                    {performanceMetrics.globalLocations} edge locations
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* User Profile Card */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle>Profile Information</CardTitle>
                  <CardDescription>Your account details and preferences</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center space-x-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-purple-600 rounded-full flex items-center justify-center">
                      <User className="h-8 w-8 text-white" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {user?.name || 'User'}
                      </h3>
                      <p className="text-sm text-gray-500">{user?.email}</p>
                    </div>
                  </div>

                  <div className="border-t pt-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Mail className="h-4 w-4 text-gray-400" />
                        <span className="text-sm text-gray-600 dark:text-gray-400">Email</span>
                      </div>
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {user?.email}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Calendar className="h-4 w-4 text-gray-400" />
                        <span className="text-sm text-gray-600 dark:text-gray-400">Joined</span>
                      </div>
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'Recently'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <CheckCircle className="h-4 w-4 text-gray-400" />
                        <span className="text-sm text-gray-600 dark:text-gray-400">Verification</span>
                      </div>
                      <span className="text-sm font-medium">
                        {user?.email_verified ? (
                          <span className="text-green-600 dark:text-green-400">Verified</span>
                        ) : (
                          <span className="text-yellow-600 dark:text-yellow-400">Pending</span>
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <Button className="w-full" variant="outline">
                      <Settings className="h-4 w-4 mr-2" />
                      Account Settings
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div>
              <Card>
                <CardHeader>
                  <CardTitle>Security</CardTitle>
                  <CardDescription>Manage your security preferences</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Button className="w-full" variant="outline">
                    <Key className="h-4 w-4 mr-2" />
                    Change Password
                  </Button>
                  <Button 
                    className="w-full" 
                    variant={user?.mfa_enabled ? "outline" : "default"}
                  >
                    <Smartphone className="h-4 w-4 mr-2" />
                    {user?.mfa_enabled ? 'Manage MFA' : 'Enable MFA'}
                  </Button>
                  <Button className="w-full" variant="outline">
                    <Activity className="h-4 w-4 mr-2" />
                    View Sessions
                  </Button>
                </CardContent>
              </Card>

              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button 
                    className="w-full justify-start" 
                    variant="ghost"
                    onClick={() => window.open('https://docs.plinto.dev', '_blank')}
                  >
                    View Documentation →
                  </Button>
                  <Button 
                    className="w-full justify-start" 
                    variant="ghost"
                    onClick={() => window.open('https://plinto.dev/pricing', '_blank')}
                  >
                    Upgrade Plan →
                  </Button>
                  <Button 
                    className="w-full justify-start" 
                    variant="ghost"
                    onClick={() => window.open('https://plinto.dev/contact', '_blank')}
                  >
                    Get Support →
                  </Button>
                </CardContent>
              </Card>

              {mounted && isDemo && (
                <Card className="mt-6">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Info className="h-4 w-4" />
                      Demo Environment
                    </CardTitle>
                    <CardDescription>Simulated performance and features</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Environment:</span>
                      <span className="font-medium">{environment?.name?.toUpperCase()}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Auth Flow:</span>
                      <span className="font-medium">{performanceMetrics.authFlowMs}ms</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Token Gen:</span>
                      <span className="font-medium">{performanceMetrics.tokenGenerationMs}ms</span>
                    </div>
                    <div className="border-t pt-3">
                      <p className="text-xs text-gray-500">
                        This environment uses sample data and simulated performance metrics for demonstration purposes.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  )
}