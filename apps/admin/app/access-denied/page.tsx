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
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6 text-center">
        {/* Icon */}
        <div className="bg-destructive/10 border-destructive/20 inline-flex rounded-full border p-4">
          <Shield className="text-destructive size-12" />
        </div>

        {/* Message */}
        <div className="space-y-2">
          <h1 className="text-foreground text-2xl font-semibold">Access Denied</h1>
          <p className="text-muted-foreground">
            Janua Admin is restricted to platform operators only.
          </p>
          {user && (
            <p className="text-muted-foreground text-sm">
              Signed in as: <span className="text-foreground font-mono">{user.email}</span>
            </p>
          )}
        </div>

        {/* Info Box */}
        <div className="border-border bg-card rounded-lg border p-4 text-left">
          <h3 className="text-foreground mb-2 font-medium">What is Janua Admin?</h3>
          <p className="text-muted-foreground text-sm">
            Janua Admin is the internal management interface for the Janua authentication platform.
            Access requires:
          </p>
          <ul className="text-muted-foreground mt-2 list-inside list-disc space-y-1 text-sm">
            <li>Email from an authorized domain (e.g., <span className="text-primary font-mono">@janua.dev</span>, <span className="text-primary font-mono">@madfam.io</span>)</li>
            <li>Admin role (<span className="text-primary font-mono">superadmin</span> or <span className="text-primary font-mono">admin</span>)</li>
          </ul>
        </div>

        {/* Actions */}
        <div className="flex flex-col justify-center gap-3 sm:flex-row">
          <button
            onClick={() => router.push('https://app.janua.dev')}
            className="border-input hover:bg-accent flex items-center justify-center gap-2 rounded-lg border px-4 py-2"
          >
            <ArrowLeft className="size-4" />
            Go to Dashboard
          </button>
          <button
            onClick={logout}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 flex items-center justify-center gap-2 rounded-lg px-4 py-2"
          >
            <LogOut className="size-4" />
            Sign Out
          </button>
        </div>

        {/* Footer */}
        <p className="text-muted-foreground text-xs">
          If you believe you should have access, contact the platform team.
        </p>
      </div>
    </div>
  )
}
