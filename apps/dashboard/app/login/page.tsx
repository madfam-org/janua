'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { SignIn } from '@janua/ui'
import { Shield, Loader2, AlertCircle } from 'lucide-react'
import { januaClient } from '@/lib/janua-client'

// Storage keys - must match auth.tsx
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'janua_access_token',
  REFRESH_TOKEN: 'janua_refresh_token',
  TOKEN_EXPIRES_AT: 'janua_token_expires_at',
  USER: 'janua_user',
  COOKIE: 'janua_token',
} as const

/**
 * Clears all authentication state - called on login page load
 * to ensure clean state when user arrives here
 */
function clearAuthStateOnLoad(reason: string | null): void {
  if (!reason) return

  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.TOKEN_EXPIRES_AT)
  localStorage.removeItem(STORAGE_KEYS.USER)

  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`
  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; domain=.janua.dev; expires=Thu, 01 Jan 1970 00:00:01 GMT`
}

function isSafeRedirectPath(path: string): boolean {
  if (!path || !path.startsWith('/')) return false
  if (path.startsWith('//')) return false
  if (path.includes('\\')) return false
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(path)) return false
  return true
}

function LoginForm() {
  const [sessionMessage, setSessionMessage] = useState('')

  const router = useRouter()
  const searchParams = useSearchParams()
  const rawRedirect = searchParams.get('redirect') || '/'
  const redirectTo = isSafeRedirectPath(rawRedirect) ? rawRedirect : '/'
  const reason = searchParams.get('reason')

  useEffect(() => {
    if (reason === 'session_expired') {
      setSessionMessage('Your session has expired. Please sign in again.')
      clearAuthStateOnLoad(reason)
    } else if (reason) {
      setSessionMessage('Please sign in to continue.')
      clearAuthStateOnLoad(reason)
    }
  }, [reason])

  const handleAfterSignIn = (user: any) => {
    // Sync cookie for middleware compatibility
    const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
    if (token) {
      const cookieDomain = window.location.hostname.includes('janua.dev') ? '; domain=.janua.dev' : ''
      document.cookie = `${STORAGE_KEYS.COOKIE}=${token}; path=/${cookieDomain}; secure; samesite=lax`
    }
    if (user) {
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user))
    }
    router.push(redirectTo)
  }

  return (
    <div className="w-full max-w-md">
      <div className="text-center mb-6">
        <div className="mb-4 flex justify-center">
          <Shield className="text-primary size-12" />
        </div>
        <h2 className="text-2xl font-bold">Sign in to Janua</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Enter your credentials to access your dashboard
        </p>
      </div>

      {sessionMessage && (
        <div className="mb-4 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-sm text-amber-700 dark:text-amber-300">{sessionMessage}</p>
        </div>
      )}

      <SignIn
        januaClient={januaClient}
        afterSignIn={handleAfterSignIn}
        redirectUrl={redirectTo}
        socialProviders={{ google: false, github: false, microsoft: false, apple: false }}
        showRememberMe={false}
      />

      <div className="text-muted-foreground text-center text-sm mt-4">
        Don&apos;t have an account?{' '}
        <a href="#" className="text-primary hover:underline">
          Contact support
        </a>
      </div>
    </div>
  )
}

function LoginFormFallback() {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <div className="mb-4 flex justify-center">
          <Shield className="text-primary size-12" />
        </div>
        <CardTitle className="text-2xl">Sign in to Janua</CardTitle>
        <CardDescription>
          Loading...
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex justify-center py-8">
          <Loader2 className="text-primary size-8 animate-spin" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function LoginPage() {
  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <Suspense fallback={<LoginFormFallback />}>
        <LoginForm />
      </Suspense>
    </div>
  )
}
