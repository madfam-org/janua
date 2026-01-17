'use client'

import { Shield, ArrowLeft, LogOut } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'

/**
 * Access Denied Page
 *
 * Shown when a user without proper authorization attempts to access Janua Admin.
 */
export default function AccessDeniedPage() {
  const router = useRouter()
  const { logout, user } = useAuth()

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center space-y-6">
        {/* Icon */}
        <div className="inline-flex p-4 rounded-full bg-destructive/10 border border-destructive/20">
          <Shield className="h-12 w-12 text-destructive" />
        </div>

        {/* Message */}
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-foreground">Access Denied</h1>
          <p className="text-muted-foreground">
            Janua Admin is restricted to platform operators only.
          </p>
          {user && (
            <p className="text-sm text-muted-foreground">
              Signed in as: <span className="font-mono text-foreground">{user.email}</span>
            </p>
          )}
        </div>

        {/* Info Box */}
        <div className="rounded-lg border border-border bg-card p-4 text-left">
          <h3 className="font-medium text-foreground mb-2">What is Janua Admin?</h3>
          <p className="text-sm text-muted-foreground">
            Janua Admin is the internal management interface for the Janua authentication platform.
            Access requires:
          </p>
          <ul className="mt-2 text-sm text-muted-foreground list-disc list-inside space-y-1">
            <li>Email from an authorized domain (e.g., <span className="font-mono text-primary">@janua.dev</span>, <span className="font-mono text-primary">@madfam.io</span>)</li>
            <li>Admin role (<span className="font-mono text-primary">superadmin</span> or <span className="font-mono text-primary">admin</span>)</li>
          </ul>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => router.push('https://app.janua.dev')}
            className="flex items-center justify-center gap-2 px-4 py-2 border border-input rounded-lg hover:bg-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            Go to Dashboard
          </button>
          <button
            onClick={logout}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:bg-destructive/90"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>

        {/* Footer */}
        <p className="text-xs text-muted-foreground">
          If you believe you should have access, contact the platform team.
        </p>
      </div>
    </div>
  )
}
