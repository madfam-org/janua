'use client'

import { useEffect } from 'react'

export default function GlobalError({
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
        tags: { errorBoundary: 'global' }
      })
    } else {
      console.error('Global marketing app error:', error)
    }
  }, [error])

  return (
    <html>
      <body>
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="max-w-md w-full mx-4 p-8 bg-white rounded-lg shadow-lg">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">
              Critical Application Error
            </h1>
            <p className="text-gray-600 mb-6">
              The application encountered a critical error and needs to restart.
            </p>
            <button
              onClick={reset}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Reload Application
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}