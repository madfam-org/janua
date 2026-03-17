'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Shield, Loader2, AlertTriangle } from 'lucide-react'
import { SignIn } from '@janua/ui'
import { useAuth } from '@/lib/auth'
import { januaClient } from '@/lib/janua-client'

export default function LoginPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, checkSession } = useAuth()
  const [isCheckingSession, setIsCheckingSession] = useState(true)

  // On mount, check for existing SSO session via cookies
  useEffect(() => {
    const checkExistingSession = async () => {
      if (checkSession) {
        try {
          const hasSession = await checkSession()
          if (hasSession) {
            router.push('/')
            return
          }
        } catch (e) {
          // No valid session, show login form
        }
      }
      setIsCheckingSession(false)
    }
    checkExistingSession()
  }, [checkSession, router])

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.push('/')
    }
  }, [isAuthenticated, authLoading, router])

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

  const handleAfterSignIn = async (user: any) => {
    router.push('/')
  }

  return (
    <div className="bg-background flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md px-4">
        <div className="mb-6 flex items-center justify-center">
          <div className="bg-destructive/10 rounded-lg p-3">
            <Shield className="text-destructive size-8" />
          </div>
        </div>
        <h1 className="text-foreground mb-2 text-center text-2xl font-bold">Janua Admin</h1>
        <p className="text-muted-foreground mb-6 text-center text-sm">Internal Platform Management</p>

        {/* Restricted Access Notice */}
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-500" />
          <div className="text-sm">
            <p className="text-foreground font-medium">Restricted Access</p>
            <p className="text-muted-foreground">
              Only authorized platform operators may access Janua Admin.
            </p>
          </div>
        </div>

        <SignIn
          januaClient={januaClient}
          afterSignIn={handleAfterSignIn}
          onError={(error) => console.error('Login error:', error)}
          socialProviders={{}}
          enableJanuaSSO={true}
          showEmailPassword={false}
          showRememberMe={false}
          headerText="Sign in"
          headerDescription="Platform operator access only"
          termsUrl="https://madfam.io/terms"
          privacyUrl="https://madfam.io/privacy"
        />

        <p className="text-muted-foreground mt-4 text-center text-xs">
          admin.janua.dev | Platform Operators Only
        </p>
      </div>
    </div>
  )
}
