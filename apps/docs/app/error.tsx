'use client'

import { useEffect } from 'react'
import { FileQuestion, RefreshCw, Search, Home } from 'lucide-react'
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
        tags: { app: 'docs' }
      })
    } else {
      console.error('Documentation error:', error)
    }
  }, [error])

  const is404 = error.message?.includes('404') || 
                error.message?.toLowerCase().includes('not found')
  
  const isSearchError = error.message?.toLowerCase().includes('search')

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gray-50 dark:bg-gray-950">
      <Card className="max-w-lg w-full">
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileQuestion className="h-5 w-5 text-blue-500" />
            <CardTitle>
              {is404 
                ? 'Documentation Not Found' 
                : isSearchError
                  ? 'Search Error'
                  : 'Documentation Error'}
            </CardTitle>
          </div>
          <CardDescription>
            {is404 
              ? "The documentation page you're looking for doesn't exist or has been moved."
              : isSearchError
                ? 'We encountered an error while searching the documentation.'
                : 'We encountered an error while loading the documentation.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {is404 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                This might help you find what you're looking for:
              </p>
              <div className="space-y-2">
                <a 
                  href="/docs"
                  className="block p-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                  📚 Documentation Home
                </a>
                <a 
                  href="/docs/getting-started"
                  className="block p-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                  🚀 Getting Started Guide
                </a>
                <a 
                  href="/docs/api-reference"
                  className="block p-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                  📖 API Reference
                </a>
              </div>
            </div>
          )}

          {!is404 && process.env.NODE_ENV === 'development' && (
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
        </CardContent>

        <CardFooter className="flex gap-2">
          {is404 ? (
            <>
              <Button
                onClick={() => window.location.href = '/docs'}
                className="flex-1"
              >
                <Home className="mr-2 h-4 w-4" />
                Documentation Home
              </Button>
              <Button
                onClick={() => {
                  // Open search modal or navigate to search
                  const searchButton = document.querySelector('[data-search-trigger]') as HTMLElement
                  if (searchButton) {
                    searchButton.click()
                  } else {
                    window.location.href = '/docs/search'
                  }
                }}
                variant="outline"
                className="flex-1"
              >
                <Search className="mr-2 h-4 w-4" />
                Search Docs
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
                onClick={() => window.location.href = '/docs'}
                variant="outline"
                className="flex-1"
              >
                <Home className="mr-2 h-4 w-4" />
                Docs Home
              </Button>
            </>
          )}
        </CardFooter>
      </Card>
    </div>
  )
}