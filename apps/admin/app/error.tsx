'use client'

import { useEffect } from 'react'
import { ShieldAlert, RefreshCw, ArrowLeft } from 'lucide-react'
import { Button, Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@janua/ui'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service with admin context
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        tags: { 
          app: 'admin',
          severity: 'high' // Admin errors are high priority
        },
        user: {
          // Include admin user context if available
          segment: 'admin'
        }
      })
    } else {
      // Error logged to Sentry in production
    }

    // Also log to internal admin monitoring
    if (typeof window !== 'undefined' && error.digest) {
      // Send critical admin errors to monitoring endpoint
      fetch('/api/admin/errors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          error: error.message,
          digest: error.digest,
          timestamp: new Date().toISOString(),
          url: window.location.href,
          userAgent: navigator.userAgent
        })
      }).catch(() => {
        // Error logged to Sentry in production
      })
    }
  }, [error])

  const isPermissionError = error.message?.toLowerCase().includes('permission') ||
                           error.message?.toLowerCase().includes('forbidden') ||
                           error.message?.toLowerCase().includes('unauthorized')

  const isCriticalError = error.message?.toLowerCase().includes('database') ||
                         error.message?.toLowerCase().includes('critical') ||
                         error.message?.toLowerCase().includes('fatal')

  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <Card className="border-destructive/30 w-full max-w-lg">
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldAlert className={`size-5 ${isCriticalError ? 'text-red-600' : 'text-amber-500'}`} />
            <CardTitle>
              {isPermissionError 
                ? 'Access Denied' 
                : isCriticalError 
                  ? 'Critical System Error'
                  : 'Admin Panel Error'}
            </CardTitle>
          </div>
          <CardDescription>
            {isPermissionError 
              ? 'You do not have the required permissions to access this resource.'
              : isCriticalError
                ? 'A critical error has occurred. The incident has been logged and the team has been notified.'
                : 'An error occurred while processing your request in the admin panel.'}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Always show error details in admin panel */}
          <div className="bg-destructive/10 border-destructive/30 rounded-lg border p-3">
            <p className="text-destructive mb-1 text-sm font-semibold">
              Error Details:
            </p>
            <p className="text-destructive/90 break-all font-mono text-sm">
              {error.message}
            </p>
            {error.stack && process.env.NODE_ENV === 'development' && (
              <details className="mt-2">
                <summary className="text-destructive/80 cursor-pointer text-xs">
                  Stack Trace
                </summary>
                <pre className="text-destructive/80 mt-1 max-h-32 overflow-auto font-mono text-xs">
                  {error.stack}
                </pre>
              </details>
            )}
          </div>

          <div className="space-y-1 text-sm">
            <p className="text-muted-foreground">
              Error ID: <code className="font-mono text-xs">{error.digest || 'unknown'}</code>
            </p>
            <p className="text-muted-foreground">
              Time: <code className="font-mono text-xs">{new Date().toISOString()}</code>
            </p>
          </div>

          {isCriticalError && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3">
              <p className="text-sm text-yellow-600 dark:text-yellow-400">
                ⚠️ The technical team has been automatically notified of this issue.
              </p>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex gap-2">
          {!isPermissionError && (
            <Button
              onClick={reset}
              className="flex-1"
              variant={isCriticalError ? 'destructive' : 'default'}
            >
              <RefreshCw className="mr-2 size-4" />
              {isCriticalError ? 'Retry Operation' : 'Try Again'}
            </Button>
          )}
          <Button
            onClick={() => window.history.back()}
            variant="outline"
            className="flex-1"
          >
            <ArrowLeft className="mr-2 size-4" />
            Go Back
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}