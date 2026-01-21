'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Shield, LogIn, Loader2, AlertTriangle } from 'lucide-react'
import { useAuth } from '@/lib/auth'

export default function LoginPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, login, checkSession } = useAuth()
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [isLoggingIn, setIsLoggingIn] = useState(false)
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

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginError('')
    setIsLoggingIn(true)
    try {
      await login(loginEmail, loginPassword)
      router.push('/')
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : 'Login failed')
    } finally {
      setIsLoggingIn(false)
    }
  }

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

  return (
    <div className="bg-background flex min-h-screen items-center justify-center">
      <div className="bg-card border-border w-full max-w-md rounded-lg border p-8">
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

        <form onSubmit={handleLogin} className="space-y-4">
          {loginError && (
            <div className="bg-destructive/10 border-destructive/30 text-destructive rounded-lg border p-3 text-sm">
              {loginError}
            </div>
          )}
          <div>
            <label className="text-foreground mb-1 block text-sm font-medium">Email</label>
            <input
              type="email"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
              className="border-input bg-background text-foreground focus:ring-ring focus:border-ring w-full rounded-lg border px-3 py-2 focus:ring-2"
              placeholder="admin@janua.dev"
              required
            />
          </div>
          <div>
            <label className="text-foreground mb-1 block text-sm font-medium">Password</label>
            <input
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              className="border-input bg-background text-foreground focus:ring-ring focus:border-ring w-full rounded-lg border px-3 py-2 focus:ring-2"
              placeholder="********"
              required
            />
          </div>
          <button
            type="submit"
            disabled={isLoggingIn}
            className="bg-primary text-primary-foreground hover:bg-primary/90 flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {isLoggingIn ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <LogIn className="size-4" />
            )}
            Sign In
          </button>
        </form>

        <p className="text-muted-foreground mt-4 text-center text-xs">
          admin.janua.dev | Platform Operators Only
        </p>
      </div>
    </div>
  )
}
