'use client'

import { useState, Suspense, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import { Shield, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react'

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
  // Only clear if there was a reason (session expired, etc.)
  if (!reason) return

  // Clear localStorage
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.TOKEN_EXPIRES_AT)
  localStorage.removeItem(STORAGE_KEYS.USER)

  // Clear cookie (both local and cross-domain for SSO cleanup)
  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`
  document.cookie = `${STORAGE_KEYS.COOKIE}=; path=/; domain=.janua.dev; expires=Thu, 01 Jan 1970 00:00:01 GMT`
}

function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessionMessage, setSessionMessage] = useState('')

  const router = useRouter()
  const searchParams = useSearchParams()
  const redirectTo = searchParams.get('redirect') || '/'
  const reason = searchParams.get('reason')

  // Handle session expired or other reasons on page load
  useEffect(() => {
    if (reason === 'session_expired') {
      setSessionMessage('Your session has expired. Please sign in again.')
      clearAuthStateOnLoad(reason)
    } else if (reason) {
      setSessionMessage('Please sign in to continue.')
      clearAuthStateOnLoad(reason)
    }
  }, [reason])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')
    setSessionMessage('')

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.message || 'Login failed')
      }

      // Store token in cookie (for middleware)
      // Use samesite=lax and domain=.janua.dev for cross-subdomain SSO (app.janua.dev ↔ admin.janua.dev)
      const cookieDomain = window.location.hostname.includes('janua.dev') ? '; domain=.janua.dev' : ''
      document.cookie = `${STORAGE_KEYS.COOKIE}=${data.token}; path=/${cookieDomain}; secure; samesite=lax`

      // Store tokens in localStorage (for SDK)
      if (data.token) {
        localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.token)
      }
      if (data.refresh_token) {
        localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token)
      }
      if (data.expires_in) {
        const expiresAt = Date.now() + (data.expires_in * 1000)
        localStorage.setItem(STORAGE_KEYS.TOKEN_EXPIRES_AT, expiresAt.toString())
      }

      // Store user info in localStorage for quick access
      if (data.user) {
        localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(data.user))
      }

      // Redirect to intended page
      router.push(redirectTo)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <div className="flex justify-center mb-4">
          <Shield className="h-12 w-12 text-primary" />
        </div>
        <CardTitle className="text-2xl">Sign in to Janua</CardTitle>
        <CardDescription>
          Enter your credentials to access your dashboard
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sessionMessage && (
          <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-md flex items-start gap-2">
            <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-700 dark:text-amber-300">{sessionMessage}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              autoComplete="email"
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
                autoComplete="current-password"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                onClick={() => setShowPassword(!showPassword)}
                disabled={isLoading}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md flex items-start gap-2">
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign in'
            )}
          </Button>

          <div className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <a href="#" className="text-primary hover:underline">
              Contact support
            </a>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function LoginFormFallback() {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <div className="flex justify-center mb-4">
          <Shield className="h-12 w-12 text-primary" />
        </div>
        <CardTitle className="text-2xl">Sign in to Janua</CardTitle>
        <CardDescription>
          Loading...
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Suspense fallback={<LoginFormFallback />}>
        <LoginForm />
      </Suspense>
    </div>
  )
}
