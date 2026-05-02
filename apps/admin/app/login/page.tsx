'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Shield, Loader2, AlertTriangle } from 'lucide-react'
import { SignIn } from '@janua/ui'
import { useAuth } from '@/lib/auth'
import { januaClient } from '@/lib/janua-client'

// localStorage keys written by the Janua SDK. Centralized so they stay in
// sync with @janua/typescript-sdk's tokenStorage='localStorage' contract.
const LS_ACCESS_TOKEN = 'janua_access_token'
const LS_REFRESH_TOKEN = 'janua_refresh_token'
const LS_EXPIRES_AT = 'janua_token_expires_at'

export default function LoginPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, checkSession } = useAuth()
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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
    // The SDK has just persisted access/refresh tokens to localStorage. Mirror
    // them into HttpOnly cookies via the server-side session bridge so the
    // edge middleware can authorize subsequent navigations. Without this step
    // the user lands on /login -> /, the middleware sees no cookies, and
    // bounces them right back to /login.
    try {
      const accessToken =
        typeof window !== 'undefined' ? window.localStorage.getItem(LS_ACCESS_TOKEN) : null
      const refreshToken =
        typeof window !== 'undefined' ? window.localStorage.getItem(LS_REFRESH_TOKEN) : null
      const expiresAtRaw =
        typeof window !== 'undefined' ? window.localStorage.getItem(LS_EXPIRES_AT) : null
      const expiresAt = expiresAtRaw ? Number(expiresAtRaw) : undefined

      if (!accessToken || !user?.email) {
        setErrorMessage(
          'Sign-in succeeded but the session token is missing. Please try again.'
        )
        return
      }

      // Roles may live on user.roles (array), or be derived from is_admin when
      // the upstream API hasn't materialized roles yet. Lib/auth.tsx applies
      // the same fallback for client-side state; the cookies must agree.
      let roles: string[] = Array.isArray(user.roles) ? [...user.roles] : []
      if (roles.length === 0 && user.is_admin) {
        roles = ['admin']
      }

      const res = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access_token: accessToken,
          refresh_token: refreshToken ?? undefined,
          email: user.email,
          roles,
          expires_at: expiresAt,
        }),
      })

      if (!res.ok) {
        setErrorMessage('Failed to establish admin session. Please try again.')
        return
      }

      router.push('/')
    } catch (err) {
      console.error('Session bridge failed:', err)
      setErrorMessage('Failed to establish admin session. Please try again.')
    }
  }

  const handleError = (error: Error) => {
    console.error('Login error:', error)
    setErrorMessage(error?.message || 'Sign-in failed. Please try again.')
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

        {/* Sign-in error banner (AJ-2): surface SignIn onError instead of swallowing it */}
        {errorMessage && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <p className="leading-snug">{errorMessage}</p>
          </div>
        )}

        <SignIn
          januaClient={januaClient}
          afterSignIn={handleAfterSignIn}
          onError={handleError}
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
