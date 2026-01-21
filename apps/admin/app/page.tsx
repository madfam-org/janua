'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  Users,
  Building2,
  Shield,
  Server,
  Activity,
  Settings,
  BarChart3,
  Loader2,
  KeyRound
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import {
  OverviewSection,
  TenantsSection,
  UsersSection,
  VaultSection,
  InfrastructureSection,
  ActivitySection,
  SecuritySection,
  SettingsSection,
} from '@/components/sections'

const sections = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'tenants', label: 'Tenants', icon: Building2 },
  { id: 'users', label: 'All Users', icon: Users },
  { id: 'vault', label: 'Ecosystem Vault', icon: KeyRound },
  { id: 'infrastructure', label: 'Infrastructure', icon: Server },
  { id: 'activity', label: 'Activity', icon: Activity },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'settings', label: 'Settings', icon: Settings },
]

function AdminPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, isAuthenticated, isLoading: authLoading, logout, checkSession } = useAuth()
  const [isCheckingSession, setIsCheckingSession] = useState(true)

  // Get section from URL or default to 'overview'
  const sectionFromUrl = searchParams.get('section') || 'overview'
  const validSections = sections.map(s => s.id)
  const activeSection = validSections.includes(sectionFromUrl) ? sectionFromUrl : 'overview'

  // Navigate to section by updating URL
  const setActiveSection = (sectionId: string) => {
    router.push(`/?section=${sectionId}`, { scroll: false })
  }

  // On mount, check for existing SSO session via cookies
  useEffect(() => {
    const checkExistingSession = async () => {
      if (checkSession) {
        try {
          const hasSession = await checkSession()
          if (hasSession) {
            setIsCheckingSession(false)
            return
          }
        } catch {
          // No valid session
        }
      }
      setIsCheckingSession(false)
    }
    checkExistingSession()
  }, [checkSession])

  // Redirect to /login if not authenticated (after loading completes)
  useEffect(() => {
    if (!authLoading && !isCheckingSession && !isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, authLoading, isCheckingSession, router])

  if (authLoading || isCheckingSession) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-primary mx-auto mb-4 size-8 animate-spin" />
          <p className="text-muted-foreground">Checking session...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-primary mx-auto mb-4 size-8 animate-spin" />
          <p className="text-muted-foreground">Redirecting to login...</p>
        </div>
      </div>
    )
  }

  const renderSection = () => {
    switch (activeSection) {
      case 'overview': return <OverviewSection />
      case 'tenants': return <TenantsSection />
      case 'users': return <UsersSection />
      case 'vault': return <VaultSection />
      case 'infrastructure': return <InfrastructureSection />
      case 'activity': return <ActivitySection />
      case 'security': return <SecuritySection />
      case 'settings': return <SettingsSection />
      default: return <OverviewSection />
    }
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="bg-card border-border border-b">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="bg-destructive/10 rounded-lg p-2">
                <Shield className="text-destructive size-6" />
              </div>
              <div>
                <h1 className="text-foreground text-xl font-bold">Janua Superadmin</h1>
                <p className="text-muted-foreground text-sm">Internal Platform Management</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="bg-destructive/10 text-destructive rounded-full px-3 py-1 text-xs font-medium">
                INTERNAL ONLY
              </span>
              <div className="text-muted-foreground text-sm">
                {user?.email}
              </div>
              <button
                onClick={logout}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="bg-card border-border min-h-screen w-64 border-r">
          <nav className="space-y-1 p-4">
            {sections.map((section) => {
              const Icon = section.icon
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`flex w-full items-center space-x-3 rounded-lg px-3 py-2 transition-colors ${
                    activeSection === section.id
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted'
                  }`}
                >
                  <Icon className="size-5" />
                  <span className="text-sm font-medium">{section.label}</span>
                </button>
              )
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6">
          {renderSection()}
        </main>
      </div>
    </div>
  )
}

export default function AdminPage() {
  return (
    <Suspense fallback={
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-primary mx-auto mb-4 size-8 animate-spin" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    }>
      <AdminPageContent />
    </Suspense>
  )
}
