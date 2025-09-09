import * as Sentry from '@sentry/nextjs'

export interface SentryConfig {
  dsn: string
  environment: string
  tracesSampleRate: number
  debug: boolean
  app: 'marketing' | 'dashboard' | 'admin' | 'docs'
  release?: string
}

export function initSentry(config: SentryConfig) {
  const { dsn, environment, tracesSampleRate, debug, app, release } = config

  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || dsn,
    
    // Environment configuration
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV || environment,
    
    // Performance monitoring
    tracesSampleRate: process.env.NODE_ENV === 'production' ? tracesSampleRate : 1.0,
    
    // Debug mode
    debug: process.env.NODE_ENV === 'development' || debug,
    
    // Release tracking
    release: release || process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA,
    
    // Session tracking
    autoSessionTracking: true,
    
    // Integrations
    integrations: [
      new Sentry.BrowserTracing({
        // Set tracingOrigins to control what URLs are traced
        tracingOrigins: ['localhost', 'plinto.dev', /^\//],
        // Route change tracking for Next.js
        routingInstrumentation: Sentry.nextRouterInstrumentation(),
      }),
      new Sentry.Replay({
        // Mask all text and inputs for privacy
        maskAllText: true,
        maskAllInputs: true,
        // Only capture replays on errors in production
        sessionSampleRate: process.env.NODE_ENV === 'production' ? 0 : 0.1,
        errorSampleRate: 1.0,
      }),
    ],
    
    // Filtering
    ignoreErrors: [
      // Browser extensions
      'top.GLOBALS',
      // Random network errors
      'Network request failed',
      'NetworkError',
      'Failed to fetch',
      // User-triggered errors
      'Non-Error promise rejection captured',
      // React errors we handle with error boundaries
      'ResizeObserver loop limit exceeded',
      'ResizeObserver loop completed with undelivered notifications',
    ],
    
    // Before send hook for additional filtering and data sanitization
    beforeSend(event, hint) {
      // Filter out non-critical errors in production
      if (process.env.NODE_ENV === 'production') {
        // Don't send events for ignored user agents (bots, crawlers)
        const userAgent = navigator?.userAgent || ''
        const isBot = /bot|crawler|spider|crawling/i.test(userAgent)
        if (isBot) {
          return null
        }
        
        // Sanitize sensitive data
        if (event.request?.cookies) {
          delete event.request.cookies
        }
        if (event.request?.headers) {
          delete event.request.headers['Authorization']
          delete event.request.headers['Cookie']
        }
      }
      
      // Add app context
      event.tags = {
        ...event.tags,
        app,
      }
      
      return event
    },
    
    // User context
    initialScope: {
      tags: {
        app,
        environment: process.env.NODE_ENV,
      },
    },
  })
}

// App-specific configurations
export const sentryConfigs = {
  marketing: {
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV || 'development',
    tracesSampleRate: 0.1, // 10% of transactions
    debug: false,
    app: 'marketing' as const,
  },
  dashboard: {
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV || 'development',
    tracesSampleRate: 0.5, // 50% for dashboard (more critical)
    debug: false,
    app: 'dashboard' as const,
  },
  admin: {
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV || 'development',
    tracesSampleRate: 1.0, // 100% for admin (most critical)
    debug: false,
    app: 'admin' as const,
  },
  docs: {
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV || 'development',
    tracesSampleRate: 0.05, // 5% for docs (less critical)
    debug: false,
    app: 'docs' as const,
  },
}

// Error boundary integration helper
export function reportErrorToBoundary(error: Error, errorInfo?: any) {
  if (typeof window !== 'undefined' && window.Sentry) {
    window.Sentry.captureException(error, {
      contexts: {
        react: {
          componentStack: errorInfo?.componentStack,
        },
      },
      tags: {
        errorBoundary: true,
      },
    })
  }
}