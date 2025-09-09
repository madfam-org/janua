'use client'

import { useEffect } from 'react'
import { AlertTriangle, RefreshCw, LogOut } from 'lucide-react'
import { Button, Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@plinto/ui'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        tags: { app: 'dashboard' }
      })
    } else {
      console.error('Dashboard error:', error)
    }
  }, [error])

  // Check if it's an authentication error
  const isAuthError = error.message?.toLowerCase().includes('auth') || 
                      error.message?.toLowerCase().includes('unauthorized') ||
                      error.message?.toLowerCase().includes('forbidden')

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gray-50 dark:bg-gray-950">
      <Card className="max-w-lg w-full">
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <CardTitle>
              {isAuthError ? 'Authentication Error' : 'Something went wrong'}
            </CardTitle>
          </div>
          <CardDescription>
            {isAuthError 
              ? 'Your session may have expired or you lack the necessary permissions.'
              : 'We encountered an error while loading this page.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {process.env.NODE_ENV === 'development' && (
            <div className="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg">
              <p className="text-sm font-mono text-gray-700 dark:text-gray-300 break-all">
                {error.message}
              </p>
              {error.digest && (
                <p className="text-xs text-gray-500 mt-2">
                  Error ID: {error.digest}
                </p>
              )}
            </div>
          )}

          {!process.env.NODE_ENV && error.digest && (
            <div className="text-sm text-muted-foreground">
              Reference ID: <code className="font-mono">{error.digest}</code>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex gap-2">
          {isAuthError ? (
            <>
              <Button
                onClick={() => window.location.href = '/sign-in'}
                className="flex-1"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign In Again
              </Button>
              <Button
                onClick={reset}
                variant="outline"
                className="flex-1"
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
            </>
          ) : (
            <>
              <Button
                onClick={reset}
                className="flex-1"
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
              <Button
                onClick={() => window.location.href = '/'}
                variant="outline"
                className="flex-1"
              >
                Go to Dashboard
              </Button>
            </>
          )}
        </CardFooter>
      </Card>
    </div>
  )
}