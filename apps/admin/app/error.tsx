'use client'

import { useEffect } from 'react'
import { ShieldAlert, RefreshCw, ArrowLeft } from 'lucide-react'
import { Button, Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@plinto/ui'

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
      console.error('Admin panel error:', error)
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
      }).catch(console.error)
    }
  }, [error])

  const isPermissionError = error.message?.toLowerCase().includes('permission') ||
                           error.message?.toLowerCase().includes('forbidden') ||
                           error.message?.toLowerCase().includes('unauthorized')

  const isCriticalError = error.message?.toLowerCase().includes('database') ||
                         error.message?.toLowerCase().includes('critical') ||
                         error.message?.toLowerCase().includes('fatal')

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gray-50 dark:bg-gray-950">
      <Card className="max-w-lg w-full border-red-200 dark:border-red-900">
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldAlert className={`h-5 w-5 ${isCriticalError ? 'text-red-600' : 'text-amber-500'}`} />
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
          <div className="p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-lg">
            <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-1">
              Error Details:
            </p>
            <p className="text-sm font-mono text-red-600 dark:text-red-500 break-all">
              {error.message}
            </p>
            {error.stack && process.env.NODE_ENV === 'development' && (
              <details className="mt-2">
                <summary className="text-xs text-red-500 cursor-pointer">
                  Stack Trace
                </summary>
                <pre className="mt-1 text-xs font-mono text-red-500 overflow-auto max-h-32">
                  {error.stack}
                </pre>
              </details>
            )}
          </div>

          <div className="text-sm space-y-1">
            <p className="text-muted-foreground">
              Error ID: <code className="font-mono text-xs">{error.digest || 'unknown'}</code>
            </p>
            <p className="text-muted-foreground">
              Time: <code className="font-mono text-xs">{new Date().toISOString()}</code>
            </p>
          </div>

          {isCriticalError && (
            <div className="p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 rounded-lg">
              <p className="text-sm text-amber-700 dark:text-amber-400">
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
              <RefreshCw className="mr-2 h-4 w-4" />
              {isCriticalError ? 'Retry Operation' : 'Try Again'}
            </Button>
          )}
          <Button
            onClick={() => window.history.back()}
            variant="outline"
            className="flex-1"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Go Back
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}